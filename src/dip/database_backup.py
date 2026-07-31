"""Storage-neutral structural values used by database backup boundaries."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseBackupManifest:
    migration_versions: tuple[int, ...]
    table_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in self.migration_versions):
            raise ValueError("migration_versions must contain positive integers.")
        if self.migration_versions != tuple(sorted(set(self.migration_versions))):
            raise ValueError("migration_versions must be unique and ordered.")
        if any(type(value) is not str or not value for value in self.table_names):
            raise ValueError("table_names must contain non-empty strings.")
        if self.table_names != tuple(sorted(set(self.table_names))):
            raise ValueError("table_names must be unique and ordered.")


def database_manifest(connection: sqlite3.Connection) -> DatabaseBackupManifest:
    versions = tuple(
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    )
    tables = tuple(
        str(row[0])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_schema
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    )
    return DatabaseBackupManifest(versions, tables)


__all__ = ["DatabaseBackupManifest", "database_manifest"]
