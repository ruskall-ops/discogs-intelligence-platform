from __future__ import annotations

import sqlite3
import re

from ..base import Migration


class AddProjectsMigration(Migration):
    version = 4
    name = "Add Project persistence"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                last_opened_order INTEGER
                    CHECK (last_opened_order IS NULL OR last_opened_order > 0),
                insertion_order INTEGER NOT NULL UNIQUE
                    CHECK (insertion_order > 0)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_state (
                singleton_id INTEGER PRIMARY KEY
                    CHECK (singleton_id = 1),
                active_project_id TEXT,
                FOREIGN KEY (active_project_id)
                    REFERENCES projects(project_id)
                    ON DELETE RESTRICT
            )
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO project_state (
                singleton_id,
                active_project_id
            )
            VALUES (1, NULL)
            """
        )
        _validate_schema(connection)


def _validate_schema(connection: sqlite3.Connection) -> None:
    project_columns = tuple(
        (row["name"], row["type"].upper(), row["notnull"], row["pk"])
        for row in connection.execute("PRAGMA table_info(projects)").fetchall()
    )
    expected_project_columns = (
        ("project_id", "TEXT", 1, 1),
        ("name", "TEXT", 1, 0),
        ("description", "TEXT", 1, 0),
        ("last_opened_order", "INTEGER", 0, 0),
        ("insertion_order", "INTEGER", 1, 0),
    )
    if project_columns != expected_project_columns:
        raise sqlite3.OperationalError(
            "Existing projects table has an incompatible shape."
        )

    state_columns = tuple(
        (row["name"], row["type"].upper(), row["notnull"], row["pk"])
        for row in connection.execute(
            "PRAGMA table_info(project_state)"
        ).fetchall()
    )
    expected_state_columns = (
        ("singleton_id", "INTEGER", 0, 1),
        ("active_project_id", "TEXT", 0, 0),
    )
    if state_columns != expected_state_columns:
        raise sqlite3.OperationalError(
            "Existing project_state table has an incompatible shape."
        )

    unique_indexes = tuple(
        tuple(
            column["name"]
            for column in connection.execute(
                f"PRAGMA index_info({row['name']})"
            ).fetchall()
        )
        for row in connection.execute("PRAGMA index_list(projects)").fetchall()
        if row["unique"]
    )
    if ("project_id",) not in unique_indexes or (
        "insertion_order",
    ) not in unique_indexes:
        raise sqlite3.OperationalError(
            "Project identity or insertion ordering constraint is missing."
        )

    foreign_keys = tuple(
        (
            row["from"],
            row["table"],
            row["to"],
            row["on_delete"],
        )
        for row in connection.execute(
            "PRAGMA foreign_key_list(project_state)"
        ).fetchall()
    )
    if foreign_keys != (
        ("active_project_id", "projects", "project_id", "RESTRICT"),
    ):
        raise sqlite3.OperationalError(
            "Project active-state foreign key is incompatible."
        )

    definitions = {}
    for table in ("projects", "project_state"):
        row = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            (table,),
        ).fetchone()
        if row is None or type(row["sql"]) is not str:
            raise sqlite3.OperationalError(
                f"{table} table definition is unavailable."
            )
        definitions[table] = re.sub(
            r"\s+",
            "",
            row["sql"].casefold(),
        )

    required_project_fragments = (
        "check(last_opened_orderisnullorlast_opened_order>0)",
        "check(insertion_order>0)",
    )
    if any(
        fragment not in definitions["projects"]
        for fragment in required_project_fragments
    ):
        raise sqlite3.OperationalError(
            "Projects table constraints are incompatible."
        )
    if "check(singleton_id=1)" not in definitions["project_state"]:
        raise sqlite3.OperationalError(
            "Project state singleton constraint is missing."
        )

    state_rows = connection.execute(
        "SELECT singleton_id FROM project_state"
    ).fetchall()
    if tuple(row["singleton_id"] for row in state_rows) != (1,):
        raise sqlite3.OperationalError(
            "Project state must contain exactly the singleton row."
        )


migration = AddProjectsMigration()
