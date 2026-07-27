"""SQLite adapters for collector-review observations and queue state."""

from __future__ import annotations

import re
import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Protocol

from dip.collector_review import (
    CollectorReviewIntegrityError,
    CollectorReviewPersistenceError,
    HotNowCalculatedState,
    NewWeekendReviewQueueEntry,
    QueueAddOutcome,
    QueueAddResult,
    WeekendObservationSource,
    WeekendReviewConflictError,
    WeekendReviewItemNotFoundError,
    WeekendReviewQueueItem,
    WeekendReviewStatus,
)


_QUEUE_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00$"
)
_LEGACY_NAIVE_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$"
)


class _SQLiteDatabaseBoundary(Protocol):
    def locked_connection(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...

    def transaction(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...


class SQLiteHotNowCalculatedStateRepository:
    """Read exact stored Hot-now rows without invoking calculation."""

    def __init__(self, database: _SQLiteDatabaseBoundary) -> None:
        self._database = database

    def list_hot_now(self) -> tuple[HotNowCalculatedState, ...]:
        try:
            with self._database.locked_connection() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        r.release_id,
                        COALESCE(r.artist, '') AS artist,
                        COALESCE(r.title, '') AS title,
                        s.calculated_at,
                        s.value_score,
                        s.demand_score,
                        s.liquidity_score,
                        s.momentum_score,
                        s.opportunity_score,
                        s.sell_window,
                        COALESCE(s.priority, '') AS priority,
                        COALESCE(s.explanation, '') AS explanation,
                        ms.id AS legacy_snapshot_id,
                        ms.analysis_run_id AS legacy_analysis_run_id,
                        ar.status AS legacy_analysis_run_status,
                        ms.captured_at AS legacy_captured_at,
                        ms.wants,
                        ms.haves,
                        ms.copies_for_sale,
                        ms.lowest_price,
                        ms.currency,
                        ms.discogs_uri
                    FROM scores s
                    JOIN releases r
                        ON r.release_id = s.release_id
                    LEFT JOIN market_snapshots ms
                        ON ms.release_id = s.release_id
                       AND ms.captured_at = s.calculated_at
                    LEFT JOIN analysis_runs ar
                        ON ar.id = ms.analysis_run_id
                    WHERE s.sell_window = 'Hot now'
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise CollectorReviewPersistenceError(
                "Hot-now calculated state is unavailable."
            ) from exc

        try:
            values = tuple(self._from_row(row) for row in rows)
            return tuple(
                sorted(
                    values,
                    key=lambda value: (
                        -float(value.opportunity_score),
                        -float(value.momentum_score),
                        -value.calculated_at.astimezone(
                            timezone.utc
                        ).timestamp(),
                        value.release_id,
                    ),
                )
            )
        except (TypeError, ValueError, InvalidOperation, OverflowError) as exc:
            raise CollectorReviewIntegrityError(
                "Stored Hot-now calculated state is inconsistent."
            ) from exc

    @staticmethod
    def _from_row(row: sqlite3.Row) -> HotNowCalculatedState:
        calculated_at = _parse_legacy_timestamp(row["calculated_at"])
        legacy_captured_at = (
            None
            if row["legacy_captured_at"] is None
            else _parse_legacy_timestamp(row["legacy_captured_at"])
        )
        if (
            legacy_captured_at is not None
            and legacy_captured_at != calculated_at
        ):
            raise ValueError(
                "The score-origin legacy snapshot timestamp is contradictory."
            )
        lowest_price = (
            None
            if row["legacy_snapshot_id"] is None
            else _decimal(row["lowest_price"], "lowest_price")
        )
        return HotNowCalculatedState(
            release_id=row["release_id"],
            artist=row["artist"],
            title=row["title"],
            calculated_at=calculated_at,
            value_score=row["value_score"],
            demand_score=row["demand_score"],
            liquidity_score=row["liquidity_score"],
            momentum_score=row["momentum_score"],
            opportunity_score=row["opportunity_score"],
            sell_window=row["sell_window"],
            priority=row["priority"],
            explanation=row["explanation"],
            legacy_snapshot_id=row["legacy_snapshot_id"],
            legacy_analysis_run_id=row["legacy_analysis_run_id"],
            legacy_analysis_run_status=row["legacy_analysis_run_status"],
            legacy_captured_at=legacy_captured_at,
            wants=(
                None if row["legacy_snapshot_id"] is None else row["wants"]
            ),
            haves=(
                None if row["legacy_snapshot_id"] is None else row["haves"]
            ),
            copies_for_sale=(
                None
                if row["legacy_snapshot_id"] is None
                else row["copies_for_sale"]
            ),
            lowest_price=lowest_price,
            currency=(
                None
                if row["legacy_snapshot_id"] is None
                else row["currency"] or None
            ),
            discogs_uri=(
                None
                if row["legacy_snapshot_id"] is None
                else row["discogs_uri"] or None
            ),
        )


class SQLiteWeekendReviewQueueRepository:
    """Durable queue storage through the shared SQLite transaction boundary."""

    def __init__(self, database: _SQLiteDatabaseBoundary) -> None:
        self._database = database

    def add_or_get_existing(
        self,
        entry: NewWeekendReviewQueueEntry,
    ) -> QueueAddResult:
        if type(entry) is not NewWeekendReviewQueueEntry:
            raise TypeError("entry must be a NewWeekendReviewQueueEntry.")
        values = _entry_values(entry)
        try:
            with self._database.transaction() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO weekend_review_queue (
                        release_id,
                        added_at,
                        status,
                        review_note,
                        updated_at,
                        resolved_at,
                        source_type,
                        source_observed_at,
                        source_summary,
                        source_intelligence_run_id,
                        source_marketplace_snapshot_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(release_id) DO NOTHING
                    """,
                    values,
                )
                if cursor.rowcount == 1:
                    row = self._row_by_id(connection, int(cursor.lastrowid))
                    if row is None:
                        raise CollectorReviewIntegrityError(
                            "The added queue item could not be reconstructed."
                        )
                    return QueueAddResult(
                        QueueAddOutcome.ADDED,
                        self._from_row(row),
                    )

                row = self._row_by_release(connection, entry.release_id)
                if row is None:
                    raise CollectorReviewIntegrityError(
                        "A duplicate queue identity disappeared during insertion."
                    )
                item = self._from_row(row)
                return QueueAddResult(_existing_outcome(item), item)
        except (
            CollectorReviewIntegrityError,
            WeekendReviewConflictError,
            WeekendReviewItemNotFoundError,
        ):
            raise
        except sqlite3.Error as exc:
            raise CollectorReviewPersistenceError(
                "The Weekend Review Queue item could not be added."
            ) from exc

    def get_by_id(
        self,
        queue_item_id: int,
    ) -> WeekendReviewQueueItem | None:
        _positive_integer(queue_item_id, "queue_item_id")
        try:
            with self._database.locked_connection() as connection:
                row = self._row_by_id(connection, queue_item_id)
            return None if row is None else self._from_row(row)
        except CollectorReviewIntegrityError:
            raise
        except sqlite3.Error as exc:
            raise CollectorReviewPersistenceError(
                "The Weekend Review Queue item could not be loaded."
            ) from exc

    def get_by_release_id(
        self,
        release_id: int,
    ) -> WeekendReviewQueueItem | None:
        _positive_integer(release_id, "release_id")
        try:
            with self._database.locked_connection() as connection:
                row = self._row_by_release(connection, release_id)
            return None if row is None else self._from_row(row)
        except CollectorReviewIntegrityError:
            raise
        except sqlite3.Error as exc:
            raise CollectorReviewPersistenceError(
                "The Weekend Review Queue item could not be loaded."
            ) from exc

    def list_queue(
        self,
        statuses: tuple[WeekendReviewStatus, ...] | None = None,
    ) -> tuple[WeekendReviewQueueItem, ...]:
        params: tuple[str, ...] = ()
        clause = ""
        if statuses is not None:
            if type(statuses) is not tuple:
                raise TypeError("statuses must be a tuple or None.")
            if not statuses:
                return ()
            if any(type(value) is not WeekendReviewStatus for value in statuses):
                raise TypeError(
                    "statuses must contain only WeekendReviewStatus values."
                )
            if len(set(statuses)) != len(statuses):
                raise ValueError("statuses must not contain duplicates.")
            placeholders = ", ".join("?" for _ in statuses)
            clause = f"WHERE status IN ({placeholders})"
            params = tuple(value.value for value in statuses)
        try:
            with self._database.locked_connection() as connection:
                rows = connection.execute(
                    f"""
                    SELECT *
                    FROM weekend_review_queue
                    {clause}
                    ORDER BY added_at ASC, id ASC
                    """,
                    params,
                ).fetchall()
            return tuple(self._from_row(row) for row in rows)
        except CollectorReviewIntegrityError:
            raise
        except sqlite3.Error as exc:
            raise CollectorReviewPersistenceError(
                "The Weekend Review Queue could not be loaded."
            ) from exc

    def save(
        self,
        item: WeekendReviewQueueItem,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        if type(item) is not WeekendReviewQueueItem:
            raise TypeError("item must be a WeekendReviewQueueItem.")
        expected = _timestamp(expected_updated_at, "expected_updated_at")
        values = _item_update_values(item)
        try:
            with self._database.transaction() as connection:
                current = self._row_by_id(connection, item.queue_item_id)
                if current is None:
                    raise WeekendReviewItemNotFoundError(
                        "The Weekend Review Queue item no longer exists."
                    )
                if current["updated_at"] != expected:
                    raise WeekendReviewConflictError(
                        "The Weekend Review Queue item changed after it was loaded."
                    )
                cursor = connection.execute(
                    """
                    UPDATE weekend_review_queue
                    SET
                        status = ?,
                        review_note = ?,
                        updated_at = ?,
                        resolved_at = ?
                    WHERE id = ? AND updated_at = ?
                    """,
                    (*values, item.queue_item_id, expected),
                )
                if cursor.rowcount != 1:
                    raise WeekendReviewConflictError(
                        "The Weekend Review Queue item changed during save."
                    )
                row = self._row_by_id(connection, item.queue_item_id)
                if row is None:
                    raise CollectorReviewIntegrityError(
                        "The saved queue item could not be reconstructed."
                    )
                return self._from_row(row)
        except (
            CollectorReviewIntegrityError,
            WeekendReviewConflictError,
            WeekendReviewItemNotFoundError,
        ):
            raise
        except sqlite3.Error as exc:
            raise CollectorReviewPersistenceError(
                "The Weekend Review Queue item could not be saved."
            ) from exc

    def delete(
        self,
        queue_item_id: int,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        _positive_integer(queue_item_id, "queue_item_id")
        expected = _timestamp(expected_updated_at, "expected_updated_at")
        try:
            with self._database.transaction() as connection:
                current = self._row_by_id(connection, queue_item_id)
                if current is None:
                    raise WeekendReviewItemNotFoundError(
                        "The Weekend Review Queue item no longer exists."
                    )
                if current["updated_at"] != expected:
                    raise WeekendReviewConflictError(
                        "The Weekend Review Queue item changed after it was loaded."
                    )
                item = self._from_row(current)
                cursor = connection.execute(
                    """
                    DELETE FROM weekend_review_queue
                    WHERE id = ? AND updated_at = ?
                    """,
                    (queue_item_id, expected),
                )
                if cursor.rowcount != 1:
                    raise WeekendReviewConflictError(
                        "The Weekend Review Queue item changed during removal."
                    )
                return item
        except (
            CollectorReviewIntegrityError,
            WeekendReviewConflictError,
            WeekendReviewItemNotFoundError,
        ):
            raise
        except sqlite3.Error as exc:
            raise CollectorReviewPersistenceError(
                "The Weekend Review Queue item could not be removed."
            ) from exc

    @staticmethod
    def _row_by_id(
        connection: sqlite3.Connection,
        queue_item_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT *
            FROM weekend_review_queue
            WHERE id = ?
            """,
            (queue_item_id,),
        ).fetchone()

    @staticmethod
    def _row_by_release(
        connection: sqlite3.Connection,
        release_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT *
            FROM weekend_review_queue
            WHERE release_id = ?
            """,
            (release_id,),
        ).fetchone()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> WeekendReviewQueueItem:
        try:
            return WeekendReviewQueueItem(
                queue_item_id=row["id"],
                release_id=row["release_id"],
                added_at=_parse_queue_timestamp(row["added_at"]),
                status=WeekendReviewStatus(row["status"]),
                review_note=row["review_note"],
                updated_at=_parse_queue_timestamp(row["updated_at"]),
                resolved_at=(
                    None
                    if row["resolved_at"] is None
                    else _parse_queue_timestamp(row["resolved_at"])
                ),
                source_type=WeekendObservationSource(row["source_type"]),
                source_observed_at=_parse_queue_timestamp(
                    row["source_observed_at"]
                ),
                source_summary=row["source_summary"],
                source_intelligence_run_id=row["source_intelligence_run_id"],
                source_marketplace_snapshot_id=(
                    row["source_marketplace_snapshot_id"]
                ),
            )
        except (
            IndexError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise CollectorReviewIntegrityError(
                "Stored Weekend Review Queue state is inconsistent."
            ) from exc


def _entry_values(entry: NewWeekendReviewQueueEntry) -> tuple[object, ...]:
    return (
        entry.release_id,
        _timestamp(entry.added_at, "added_at"),
        entry.status.value,
        entry.review_note,
        _timestamp(entry.updated_at, "updated_at"),
        (
            None
            if entry.resolved_at is None
            else _timestamp(entry.resolved_at, "resolved_at")
        ),
        entry.source_type.value,
        _timestamp(entry.source_observed_at, "source_observed_at"),
        entry.source_summary,
        entry.source_intelligence_run_id,
        entry.source_marketplace_snapshot_id,
    )


def _item_update_values(item: WeekendReviewQueueItem) -> tuple[object, ...]:
    return (
        item.status.value,
        item.review_note,
        _timestamp(item.updated_at, "updated_at"),
        (
            None
            if item.resolved_at is None
            else _timestamp(item.resolved_at, "resolved_at")
        ),
    )


def _timestamp(value: datetime, name: str) -> str:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _parse_queue_timestamp(value: object) -> datetime:
    if type(value) is not str or not _QUEUE_TIMESTAMP.fullmatch(value):
        raise ValueError("Queue timestamp is not canonical UTC.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Queue timestamp is not timezone-aware.")
    return parsed


def _parse_legacy_timestamp(value: object) -> datetime:
    if type(value) is not str or not value:
        raise ValueError("Legacy timestamp must be a non-empty string.")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("Legacy timestamp is not supported.") from exc
    if parsed.tzinfo is None:
        if not _LEGACY_NAIVE_TIMESTAMP.fullmatch(value):
            raise ValueError("Legacy naive timestamp is not supported.")
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed.utcoffset() is None:
        raise ValueError("Legacy timestamp has no usable offset.")
    return parsed.astimezone(timezone.utc)


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError(f"{name} is not numeric.")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


def _positive_integer(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _existing_outcome(item: WeekendReviewQueueItem) -> QueueAddOutcome:
    return (
        QueueAddOutcome.EXISTING_RESOLVED
        if item.status is WeekendReviewStatus.RESOLVED
        else QueueAddOutcome.EXISTING_ACTIVE
    )


__all__ = [
    "SQLiteHotNowCalculatedStateRepository",
    "SQLiteWeekendReviewQueueRepository",
]
