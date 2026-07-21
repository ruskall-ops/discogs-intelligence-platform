"""SQLite adapter for immutable Marketplace snapshot history."""

from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Protocol

from dip.marketplace_history import (
    MAX_RECENT_SNAPSHOT_LIMIT,
    MarketplaceHistoryIntegrityError,
    MarketplaceHistoryPersistenceError,
    MarketplaceHistoryRepository,
    MarketplaceSnapshotConflictError,
)
from dip.marketplace_intelligence import (
    MARKETPLACE_SCHEMA_VERSION,
    MarketplaceDeserializationError,
    MarketplaceSnapshot,
    dumps_marketplace_snapshot,
    loads_marketplace_snapshot,
)


class _SQLiteDatabaseBoundary(Protocol):
    def locked_connection(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...

    def transaction(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...


class SQLiteMarketplaceHistoryRepository(MarketplaceHistoryRepository):
    """Append-only SQLite storage for canonical Marketplace snapshots."""

    def __init__(self, database: _SQLiteDatabaseBoundary) -> None:
        self._database = database

    def save_snapshot(self, snapshot: MarketplaceSnapshot) -> None:
        """Insert a snapshot, accepting only an identical repeated save."""

        if type(snapshot) is not MarketplaceSnapshot:
            raise TypeError("snapshot must be a MarketplaceSnapshot.")

        # Canonical serialization is deliberately completed before any database
        # mutation so an unsupported value cannot leave partial history behind.
        payload_json = dumps_marketplace_snapshot(snapshot)
        captured_at = _capture_sort_value(snapshot.captured_at)

        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO marketplace_snapshots (
                        snapshot_id,
                        captured_at,
                        source,
                        status,
                        schema_version,
                        payload_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(snapshot_id) DO NOTHING
                    """,
                    (
                        snapshot.snapshot_id,
                        captured_at,
                        snapshot.source,
                        snapshot.status.value,
                        MARKETPLACE_SCHEMA_VERSION,
                        payload_json,
                    ),
                )
                if cursor.rowcount == 1:
                    return

                row = connection.execute(
                    """
                    SELECT *
                    FROM marketplace_snapshots
                    WHERE snapshot_id = ?
                    """,
                    (snapshot.snapshot_id,),
                ).fetchone()
                if row is None:
                    raise MarketplaceHistoryIntegrityError(
                        "A conflicting Marketplace snapshot disappeared during save."
                    )

                self._snapshot_from_row(row)
                if row["payload_json"] == payload_json:
                    return

                raise MarketplaceSnapshotConflictError(
                    f"Marketplace snapshot ID {snapshot.snapshot_id!r} is already "
                    "stored with different immutable content."
                )
        except sqlite3.Error as exc:
            raise MarketplaceHistoryPersistenceError(
                f"Unable to save Marketplace snapshot {snapshot.snapshot_id!r}."
            ) from exc

    def get_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None:
        """Return one snapshot by its stable domain identifier."""

        _validate_snapshot_id(snapshot_id)
        try:
            with self._database.locked_connection() as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM marketplace_snapshots
                    WHERE snapshot_id = ?
                    """,
                    (snapshot_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise MarketplaceHistoryPersistenceError(
                f"Unable to retrieve Marketplace snapshot {snapshot_id!r}."
            ) from exc

        return None if row is None else self._snapshot_from_row(row)

    def latest_snapshot(self) -> MarketplaceSnapshot | None:
        """Return the newest snapshot using the complete history order."""

        try:
            with self._database.locked_connection() as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM marketplace_snapshots
                    ORDER BY captured_at DESC, snapshot_id DESC
                    LIMIT 1
                    """
                ).fetchone()
        except sqlite3.Error as exc:
            raise MarketplaceHistoryPersistenceError(
                "Unable to retrieve the latest Marketplace snapshot."
            ) from exc

        return None if row is None else self._snapshot_from_row(row)

    def recent_snapshots(
        self,
        limit: int,
    ) -> tuple[MarketplaceSnapshot, ...]:
        """Return bounded snapshots in deterministic newest-first order."""

        _validate_limit(limit)
        try:
            with self._database.locked_connection() as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM marketplace_snapshots
                    ORDER BY captured_at DESC, snapshot_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise MarketplaceHistoryPersistenceError(
                "Unable to retrieve recent Marketplace snapshots."
            ) from exc

        return tuple(self._snapshot_from_row(row) for row in rows)

    def previous_snapshot(
        self,
        snapshot_id: str,
    ) -> MarketplaceSnapshot | None:
        """Return the next older snapshot in the complete history order."""

        _validate_snapshot_id(snapshot_id)
        try:
            with self._database.locked_connection() as connection:
                current_row = connection.execute(
                    """
                    SELECT *
                    FROM marketplace_snapshots
                    WHERE snapshot_id = ?
                    """,
                    (snapshot_id,),
                ).fetchone()
                if current_row is None:
                    return None

                # Validate the reference row before trusting its indexed key.
                self._snapshot_from_row(current_row)
                row = connection.execute(
                    """
                    SELECT *
                    FROM marketplace_snapshots
                    WHERE captured_at < ?
                       OR (captured_at = ? AND snapshot_id < ?)
                    ORDER BY captured_at DESC, snapshot_id DESC
                    LIMIT 1
                    """,
                    (
                        current_row["captured_at"],
                        current_row["captured_at"],
                        snapshot_id,
                    ),
                ).fetchone()
        except sqlite3.Error as exc:
            raise MarketplaceHistoryPersistenceError(
                f"Unable to retrieve the snapshot before {snapshot_id!r}."
            ) from exc

        return None if row is None else self._snapshot_from_row(row)

    @staticmethod
    def _snapshot_from_row(row: sqlite3.Row) -> MarketplaceSnapshot:
        try:
            snapshot_id = row["snapshot_id"]
            captured_at = row["captured_at"]
            source = row["source"]
            status = row["status"]
            schema_version = row["schema_version"]
            payload_json = row["payload_json"]
        except (IndexError, KeyError, TypeError) as exc:
            raise MarketplaceHistoryIntegrityError(
                "Stored Marketplace History row has an incompatible shape."
            ) from exc

        if type(snapshot_id) is not str or not snapshot_id:
            raise MarketplaceHistoryIntegrityError(
                "Stored Marketplace snapshot has an invalid indexed identifier."
            )
        if type(schema_version) is not int:
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} has a non-integer "
                "schema version."
            )
        if schema_version != MARKETPLACE_SCHEMA_VERSION:
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} uses unsupported "
                f"schema version {schema_version!r}."
            )

        try:
            snapshot = loads_marketplace_snapshot(payload_json)
        except MarketplaceDeserializationError as exc:
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} has an invalid payload."
            ) from exc

        canonical_payload = dumps_marketplace_snapshot(snapshot)
        if payload_json != canonical_payload:
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} payload is not canonical."
            )
        if snapshot.snapshot_id != snapshot_id:
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} payload has a different "
                "snapshot ID."
            )
        if captured_at != _capture_sort_value(snapshot.captured_at):
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} has inconsistent "
                "capture time metadata."
            )
        if source != snapshot.source:
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} has inconsistent "
                "source metadata."
            )
        if status != snapshot.status.value:
            raise MarketplaceHistoryIntegrityError(
                f"Stored Marketplace snapshot {snapshot_id!r} has inconsistent "
                "status metadata."
            )
        return snapshot


def _capture_sort_value(captured_at: datetime) -> str:
    """Return a stable UTC key without changing the serialized domain value."""

    return captured_at.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _validate_snapshot_id(snapshot_id: object) -> None:
    if not isinstance(snapshot_id, str):
        raise TypeError("snapshot_id must be a string.")
    if not snapshot_id or snapshot_id != snapshot_id.strip():
        raise ValueError("snapshot_id must be non-empty and trimmed.")


def _validate_limit(limit: object) -> None:
    if type(limit) is not int:
        raise TypeError("limit must be an integer.")
    if not 1 <= limit <= MAX_RECENT_SNAPSHOT_LIMIT:
        raise ValueError(
            f"limit must be between 1 and {MAX_RECENT_SNAPSHOT_LIMIT}."
        )


__all__ = ["SQLiteMarketplaceHistoryRepository"]
