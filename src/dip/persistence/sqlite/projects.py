"""SQLite implementation of the storage-independent Project repository."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from typing import Protocol

from dip.projects import (
    ManagedProject,
    ProjectPersistenceError,
    ProjectRepository,
)


class _SQLiteDatabaseBoundary(Protocol):
    def locked_connection(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...

    def transaction(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...


class SQLiteProjectRepository(ProjectRepository):
    """Persist Projects using the shared SQLite database boundary."""

    def __init__(self, database: _SQLiteDatabaseBoundary) -> None:
        self._database = database

    def list_projects(self) -> tuple[ManagedProject, ...]:
        try:
            with self._database.locked_connection() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        project_id,
                        name,
                        description,
                        last_opened_order
                    FROM projects
                    ORDER BY insertion_order ASC
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                "Unable to list Projects."
            ) from exc
        return tuple(self._project_from_row(row) for row in rows)

    def get(self, project_id: str) -> ManagedProject | None:
        try:
            with self._database.locked_connection() as connection:
                row = connection.execute(
                    """
                    SELECT
                        project_id,
                        name,
                        description,
                        last_opened_order
                    FROM projects
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                f"Unable to retrieve Project {project_id!r}."
            ) from exc
        return None if row is None else self._project_from_row(row)

    def add(self, project: ManagedProject) -> None:
        if type(project) is not ManagedProject:
            raise TypeError("project must be ManagedProject.")
        try:
            with self._database.transaction() as connection:
                if self._project_exists(connection, project.project_id):
                    raise ValueError("Project identity already exists.")
                insertion_order = self._next_order(
                    connection, "insertion_order"
                )
                connection.execute(
                    """
                    INSERT INTO projects (
                        project_id,
                        name,
                        description,
                        last_opened_order,
                        insertion_order
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        project.project_id,
                        project.name,
                        project.description,
                        project.last_opened_order,
                        insertion_order,
                    ),
                )
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                f"Unable to add Project {project.project_id!r}."
            ) from exc

    def active_project_id(self) -> str | None:
        try:
            with self._database.locked_connection() as connection:
                row = connection.execute(
                    """
                    SELECT active_project_id
                    FROM project_state
                    WHERE singleton_id = 1
                    """
                ).fetchone()
                if row is not None and row["active_project_id"] is not None:
                    active_exists = self._project_exists(
                        connection,
                        row["active_project_id"],
                    )
                else:
                    active_exists = True
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                "Unable to retrieve active Project state."
            ) from exc
        if row is None:
            raise ProjectPersistenceError(
                "Project state singleton row is missing."
            )
        project_id = row["active_project_id"]
        if not active_exists:
            raise ProjectPersistenceError(
                "Active Project state references a missing Project."
            )
        return project_id

    def set_active(self, project_id: str) -> None:
        try:
            with self._database.transaction() as connection:
                self._require(connection, project_id)
                self._set_active(connection, project_id)
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                f"Unable to activate Project {project_id!r}."
            ) from exc

    def update_last_opened(self, project_id: str) -> ManagedProject:
        try:
            with self._database.transaction() as connection:
                self._require(connection, project_id)
                project = self._update_last_opened(connection, project_id)
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                f"Unable to update Project {project_id!r}."
            ) from exc
        return project

    def open(self, project_id: str) -> ManagedProject:
        """Atomically activate a Project and advance its open order."""

        try:
            with self._database.transaction() as connection:
                self._require(connection, project_id)
                project = self._update_last_opened(connection, project_id)
                self._set_active(connection, project_id)
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                f"Unable to open Project {project_id!r}."
            ) from exc
        return project

    def ensure_default_project(self, project: ManagedProject) -> ManagedProject:
        """Create the first-run Project once and activate it only if needed."""

        if type(project) is not ManagedProject:
            raise TypeError("project must be ManagedProject.")
        try:
            with self._database.transaction() as connection:
                row = self._row(connection, project.project_id)
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO projects (
                            project_id,
                            name,
                            description,
                            last_opened_order,
                            insertion_order
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            project.project_id,
                            project.name,
                            project.description,
                            project.last_opened_order,
                            self._next_order(connection, "insertion_order"),
                        ),
                    )
                    stored = project
                else:
                    stored = self._project_from_row(row)

                state = connection.execute(
                    """
                    SELECT active_project_id
                    FROM project_state
                    WHERE singleton_id = 1
                    """
                ).fetchone()
                if state is None:
                    raise ProjectPersistenceError(
                        "Project state singleton row is missing."
                    )
                if state["active_project_id"] is None:
                    self._set_active(connection, stored.project_id)
        except sqlite3.Error as exc:
            raise ProjectPersistenceError(
                f"Unable to initialise Project {project.project_id!r}."
            ) from exc
        return stored

    @staticmethod
    def _next_order(
        connection: sqlite3.Connection,
        column: str,
    ) -> int:
        if column not in {"insertion_order", "last_opened_order"}:
            raise ValueError("Unsupported Project ordering column.")
        row = connection.execute(
            f"SELECT COALESCE(MAX({column}), 0) + 1 AS next_order FROM projects"
        ).fetchone()
        return int(row["next_order"])

    def _update_last_opened(
        self,
        connection: sqlite3.Connection,
        project_id: str,
    ) -> ManagedProject:
        order = self._next_order(connection, "last_opened_order")
        connection.execute(
            """
            UPDATE projects
            SET last_opened_order = ?
            WHERE project_id = ?
            """,
            (order, project_id),
        )
        row = self._row(connection, project_id)
        if row is None:
            raise ProjectPersistenceError(
                "Project disappeared while updating last-opened state."
            )
        return self._project_from_row(row)

    @staticmethod
    def _set_active(
        connection: sqlite3.Connection,
        project_id: str,
    ) -> None:
        cursor = connection.execute(
            """
            UPDATE project_state
            SET active_project_id = ?
            WHERE singleton_id = 1
            """,
            (project_id,),
        )
        if cursor.rowcount != 1:
            raise ProjectPersistenceError(
                "Project state singleton row is missing."
            )

    def _require(
        self,
        connection: sqlite3.Connection,
        project_id: str,
    ) -> ManagedProject:
        if type(project_id) is not str or not project_id:
            raise TypeError("project_id must be a non-empty string.")
        row = self._row(connection, project_id)
        if row is None:
            raise ValueError("Project does not exist.")
        return self._project_from_row(row)

    @staticmethod
    def _project_exists(
        connection: sqlite3.Connection,
        project_id: str,
    ) -> bool:
        return connection.execute(
            "SELECT 1 FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone() is not None

    @staticmethod
    def _row(
        connection: sqlite3.Connection,
        project_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT
                project_id,
                name,
                description,
                last_opened_order
            FROM projects
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchone()

    @staticmethod
    def _project_from_row(row: sqlite3.Row) -> ManagedProject:
        try:
            return ManagedProject(
                project_id=row["project_id"],
                name=row["name"],
                description=row["description"],
                last_opened_order=row["last_opened_order"],
            )
        except (TypeError, ValueError) as exc:
            raise ProjectPersistenceError(
                "Stored Project data is invalid."
            ) from exc


__all__ = ["SQLiteProjectRepository"]
