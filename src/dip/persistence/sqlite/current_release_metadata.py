"""SQLite current catalogue metadata adapter."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from typing import Protocol

from dip.app.current_release_metadata import CurrentReleaseMetadata


_BATCH_SIZE = 900


class CurrentReleaseMetadataPersistenceError(RuntimeError):
    """Raised when current-label metadata cannot be reconstructed safely."""


class _DatabaseBoundary(Protocol):
    def locked_connection(self) -> AbstractContextManager[sqlite3.Connection]: ...


class SQLiteCurrentReleaseMetadataRepository:
    """Return detached artist/title labels for an exact release-ID scope."""

    def __init__(self, database: _DatabaseBoundary) -> None:
        self._database = database

    def metadata_for_release_ids(
        self,
        release_ids: tuple[int, ...],
    ) -> tuple[CurrentReleaseMetadata, ...]:
        if type(release_ids) is not tuple:
            raise TypeError("release_ids must be a tuple.")
        if not release_ids:
            return ()
        for index, value in enumerate(release_ids):
            if type(value) is not int:
                raise TypeError(f"release_ids[{index}] must be an integer.")
            if value <= 0:
                raise ValueError(f"release_ids[{index}] must be positive.")
        if release_ids != tuple(sorted(set(release_ids))):
            raise ValueError("release_ids must be unique and ordered.")
        found: dict[int, CurrentReleaseMetadata] = {}
        try:
            with self._database.locked_connection() as connection:
                for offset in range(0, len(release_ids), _BATCH_SIZE):
                    batch = release_ids[offset : offset + _BATCH_SIZE]
                    placeholders = ", ".join("?" for _ in batch)
                    rows = connection.execute(
                        "SELECT release_id, artist, title, "
                        "typeof(release_id) AS release_id_type, "
                        "typeof(artist) AS artist_type, typeof(title) AS title_type "
                        "FROM releases "
                        f"WHERE release_id IN ({placeholders}) ORDER BY release_id",
                        batch,
                    ).fetchall()
                    for row in rows:
                        release_id = row["release_id"]
                        if row["release_id_type"] != "integer" or type(release_id) is not int or release_id <= 0:
                            raise CurrentReleaseMetadataPersistenceError("Stored release identity is malformed.")
                        if row["artist_type"] not in {"text", "null"} or row["title_type"] not in {"text", "null"}:
                            raise CurrentReleaseMetadataPersistenceError("Stored release metadata is malformed.")
                        value = CurrentReleaseMetadata(release_id, row["artist"], row["title"])
                        if value.release_id not in release_ids or value.release_id in found:
                            raise CurrentReleaseMetadataPersistenceError("Metadata query returned an invalid identity.")
                        found[value.release_id] = value
        except CurrentReleaseMetadataPersistenceError:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise CurrentReleaseMetadataPersistenceError(
                "Current release metadata could not be read safely."
            ) from exc
        return tuple(found[value] for value in sorted(found))


__all__ = ["CurrentReleaseMetadataPersistenceError", "SQLiteCurrentReleaseMetadataRepository"]
