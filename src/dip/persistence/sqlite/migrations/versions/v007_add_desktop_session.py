"""Migration 7: add database-scoped desktop session restoration."""

from __future__ import annotations

import sqlite3

from ..base import Migration
from .v006_add_weekend_review_queue import _canonical_create_table


_TABLE = "desktop_session"
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS desktop_session (
    singleton_id INTEGER PRIMARY KEY
        CHECK (singleton_id = 1),
    format_version INTEGER NOT NULL
        CHECK (format_version = 1),
    saved_at TEXT NOT NULL
        CHECK (length(trim(saved_at)) > 0),
    active_project_id TEXT
        CHECK (
            active_project_id IS NULL
            OR (
                length(active_project_id) > 0
                AND active_project_id = trim(active_project_id)
            )
        ),
    window_width INTEGER NOT NULL
        CHECK (window_width BETWEEN 1050 AND 32767),
    window_height INTEGER NOT NULL
        CHECK (window_height BETWEEN 650 AND 32767),
    window_x INTEGER NOT NULL
        CHECK (window_x BETWEEN -2147483648 AND 2147483647),
    window_y INTEGER NOT NULL
        CHECK (window_y BETWEEN -2147483648 AND 2147483647),
    top_level_destination TEXT NOT NULL
        CHECK (
            top_level_destination IN (
                'project',
                'dashboard',
                'collection_review'
            )
        ),
    collection_review_destination TEXT NOT NULL
        CHECK (
            collection_review_destination IN (
                'observations',
                'weekend_review_queue',
                'collection_decisions'
            )
        ),
    observation_source TEXT NOT NULL
        CHECK (observation_source IN ('hot_now', 'hidden_gem')),
    queue_filter TEXT NOT NULL
        CHECK (queue_filter IN ('active', 'resolved', 'all')),
    decision_priority_filter TEXT NOT NULL
        CHECK (
            decision_priority_filter IN (
                'all',
                'high_priority_review',
                'worth_reviewing',
                'possible_candidate',
                'low_priority',
                'not_scored'
            )
        ),
    decision_state_filter TEXT NOT NULL
        CHECK (
            decision_state_filter IN (
                'all',
                'review',
                'keep',
                'list_for_sale',
                'maybe',
                'ignore'
            )
        ),
    selected_observation_source TEXT
        CHECK (
            selected_observation_source IS NULL
            OR selected_observation_source IN ('hot_now', 'hidden_gem')
        ),
    selected_observation_release_id INTEGER
        CHECK (
            selected_observation_release_id IS NULL
            OR selected_observation_release_id > 0
        ),
    selected_queue_item_id INTEGER
        CHECK (
            selected_queue_item_id IS NULL
            OR selected_queue_item_id > 0
        ),
    selected_decision_release_id INTEGER
        CHECK (
            selected_decision_release_id IS NULL
            OR selected_decision_release_id > 0
        ),
    CHECK (
        (selected_observation_source IS NULL)
        =
        (selected_observation_release_id IS NULL)
    )
)
"""


class AddDesktopSessionMigration(Migration):
    version = 7
    name = "Add Desktop Session restoration"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        connection.execute(_CREATE_TABLE_SQL)
        _validate_schema(connection)


def _validate_schema(connection: sqlite3.Connection) -> None:
    table = connection.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (_TABLE,),
    ).fetchone()
    if table is None or type(table["sql"]) is not str:
        raise sqlite3.OperationalError("Desktop Session table is missing.")
    columns = tuple(
        (
            row["name"],
            str(row["type"]).upper(),
            row["notnull"],
            row["dflt_value"],
            row["pk"],
        )
        for row in connection.execute(
            f"PRAGMA table_info({_TABLE})"
        ).fetchall()
    )
    expected = (
        ("singleton_id", "INTEGER", 0, None, 1),
        ("format_version", "INTEGER", 1, None, 0),
        ("saved_at", "TEXT", 1, None, 0),
        ("active_project_id", "TEXT", 0, None, 0),
        ("window_width", "INTEGER", 1, None, 0),
        ("window_height", "INTEGER", 1, None, 0),
        ("window_x", "INTEGER", 1, None, 0),
        ("window_y", "INTEGER", 1, None, 0),
        ("top_level_destination", "TEXT", 1, None, 0),
        ("collection_review_destination", "TEXT", 1, None, 0),
        ("observation_source", "TEXT", 1, None, 0),
        ("queue_filter", "TEXT", 1, None, 0),
        ("decision_priority_filter", "TEXT", 1, None, 0),
        ("decision_state_filter", "TEXT", 1, None, 0),
        ("selected_observation_source", "TEXT", 0, None, 0),
        ("selected_observation_release_id", "INTEGER", 0, None, 0),
        ("selected_queue_item_id", "INTEGER", 0, None, 0),
        ("selected_decision_release_id", "INTEGER", 0, None, 0),
    )
    if columns != expected:
        raise sqlite3.OperationalError(
            "Desktop Session columns are incompatible."
        )
    if connection.execute(
        f"PRAGMA foreign_key_list({_TABLE})"
    ).fetchall():
        raise sqlite3.OperationalError(
            "Desktop Session must not contain foreign keys."
        )
    indexes = tuple(
        row
        for row in connection.execute(
            f"PRAGMA index_list({_TABLE})"
        ).fetchall()
        if not row["name"].startswith("sqlite_autoindex")
    )
    if indexes:
        raise sqlite3.OperationalError(
            "Desktop Session must not contain additional indexes."
        )
    if _canonical_create_table(table["sql"]) != _canonical_create_table(
        _CREATE_TABLE_SQL
    ):
        raise sqlite3.OperationalError(
            "Desktop Session constraints are incompatible."
        )


migration = AddDesktopSessionMigration()


__all__ = ["migration"]
