"""SQLite adapter for a transactionally consistent database backup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from dip.database_backup import DatabaseBackupManifest, database_manifest


class SQLiteDatabaseBackupError(RuntimeError):
    """Value-neutral SQLite backup adapter failure."""


class SQLiteDatabaseBackupAdapter:
    def __init__(self, database) -> None:
        self._database = database

    @property
    def source_path(self) -> Path:
        return self._database.path

    def create_backup(self, destination: Path) -> DatabaseBackupManifest:
        if not isinstance(destination, Path):
            raise TypeError("destination must be a Path.")
        target: sqlite3.Connection | None = None
        failure: BaseException | None = None
        manifest: DatabaseBackupManifest | None = None
        try:
            target = sqlite3.connect(destination)
            with self._database.locked_connection() as source:
                if source.in_transaction:
                    raise SQLiteDatabaseBackupError(
                        "SQLite database backup is unavailable."
                    )
                manifest = database_manifest(source)
                source.backup(target)
        except SQLiteDatabaseBackupError as exc:
            failure = exc
        except Exception as exc:
            failure = _translated(
                "SQLite database backup failed.",
                exc,
            )
        finally:
            if target is not None:
                try:
                    target.close()
                except Exception as exc:
                    if failure is None:
                        failure = _translated(
                            "SQLite backup destination could not be closed.",
                            exc,
                        )
        if failure is not None:
            raise failure
        if manifest is None:
            raise SQLiteDatabaseBackupError(
                "SQLite database backup failed."
            )
        return manifest

    def verify_backup(
        self,
        backup_path: Path,
        *,
        expected_manifest: DatabaseBackupManifest,
    ) -> None:
        if not isinstance(backup_path, Path):
            raise TypeError("backup_path must be a Path.")
        if type(expected_manifest) is not DatabaseBackupManifest:
            raise TypeError(
                "expected_manifest must be a DatabaseBackupManifest."
            )
        connection: sqlite3.Connection | None = None
        failure: BaseException | None = None
        try:
            connection = sqlite3.connect(backup_path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            quick_check = tuple(
                row[0]
                for row in connection.execute("PRAGMA quick_check").fetchall()
            )
            if quick_check != ("ok",):
                raise SQLiteDatabaseBackupError(
                    "SQLite backup verification failed."
                )
            if (
                connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchone()
                is not None
            ):
                raise SQLiteDatabaseBackupError(
                    "SQLite backup verification failed."
                )
            if (
                database_manifest(connection) != expected_manifest
                or connection.in_transaction
            ):
                raise SQLiteDatabaseBackupError(
                    "SQLite backup verification failed."
                )
        except SQLiteDatabaseBackupError as exc:
            failure = exc
        except Exception as exc:
            failure = _translated(
                "SQLite backup verification failed.",
                exc,
            )
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception as exc:
                    if failure is None:
                        failure = _translated(
                            "SQLite backup verification could not be closed.",
                            exc,
                        )
        if failure is not None:
            raise failure


def _translated(message: str, cause: BaseException) -> SQLiteDatabaseBackupError:
    try:
        raise SQLiteDatabaseBackupError(message) from cause
    except SQLiteDatabaseBackupError as translated:
        return translated


__all__ = ["SQLiteDatabaseBackupAdapter", "SQLiteDatabaseBackupError"]
