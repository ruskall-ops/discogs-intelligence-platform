from __future__ import annotations

import importlib
import pkgutil
import sqlite3
from dataclasses import dataclass

from .base import Migration


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    name: str


def run_migrations(connection: sqlite3.Connection) -> list[AppliedMigration]:
    """
    Discover and apply all pending migrations in version order.

    Returns the migrations applied during this run.
    """

    _ensure_migrations_table(connection)

    applied_versions = {
        int(row["version"])
        for row in connection.execute(
            """
            SELECT version
            FROM schema_migrations
            """
        ).fetchall()
    }

    migrations = _discover_migrations()
    applied_now: list[AppliedMigration] = []

    for migration in migrations:
        if migration.version in applied_versions:
            continue

        try:
            with connection:
                migration.upgrade(connection)

                connection.execute(
                    """
                    INSERT INTO schema_migrations (
                        version,
                        name
                    )
                    VALUES (?, ?)
                    """,
                    (
                        migration.version,
                        migration.name,
                    ),
                )

        except sqlite3.DatabaseError as exc:
            raise RuntimeError(
                f"Migration {migration.version} "
                f"({migration.name}) failed"
            ) from exc

        applied_now.append(
            AppliedMigration(
                version=migration.version,
                name=migration.name,
            )
        )

    return applied_now


def _ensure_migrations_table(
    connection: sqlite3.Connection,
) -> None:
    with connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(schema_migrations)"
            ).fetchall()
        }

        if "name" not in columns:
            connection.execute(
                """
                ALTER TABLE schema_migrations
                ADD COLUMN name TEXT NOT NULL DEFAULT ''
                """
            )


def _discover_migrations() -> list[Migration]:
    from . import versions

    discovered: list[Migration] = []

    for module_info in pkgutil.iter_modules(
        versions.__path__,
        prefix=f"{versions.__name__}.",
    ):
        module = importlib.import_module(module_info.name)

        migration = getattr(module, "migration", None)

        if migration is None:
            continue

        if not isinstance(migration, Migration):
            raise TypeError(
                f"{module_info.name} does not expose a valid migration"
            )

        discovered.append(migration)

    discovered.sort(key=lambda item: item.version)

    versions_seen: set[int] = set()

    for migration in discovered:
        if migration.version in versions_seen:
            raise ValueError(
                f"Duplicate migration version: {migration.version}"
            )

        versions_seen.add(migration.version)

    return discovered
