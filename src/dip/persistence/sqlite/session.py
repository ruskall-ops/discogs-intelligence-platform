"""SQLite adapter for the desktop session repository."""

from __future__ import annotations

import re
import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Protocol

from dip.collector_review import ObservationIdentity, WeekendObservationSource
from dip.session import (
    CollectionReviewDestination,
    DecisionPriorityFilter,
    DecisionStateFilter,
    DesktopSession,
    QueueStatusFilter,
    SESSION_FORMAT_VERSION,
    SessionCompatibilityError,
    SessionIntegrityError,
    SessionPersistenceError,
    SessionRepository,
    TopLevelDestination,
)


_CANONICAL_TIMESTAMP = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00"
)


class _SQLiteDatabaseBoundary(Protocol):
    def locked_connection(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...

    def transaction(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...


class SQLiteSessionRepository(SessionRepository):
    """Store the one current desktop session through the shared database."""

    def __init__(self, database: _SQLiteDatabaseBoundary) -> None:
        self._database = database

    def get(self) -> DesktopSession | None:
        try:
            with self._database.locked_connection() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        singleton_id,
                        format_version,
                        saved_at,
                        active_project_id,
                        window_width,
                        window_height,
                        window_x,
                        window_y,
                        top_level_destination,
                        collection_review_destination,
                        observation_source,
                        queue_filter,
                        decision_priority_filter,
                        decision_state_filter,
                        selected_observation_source,
                        selected_observation_release_id,
                        selected_queue_item_id,
                        selected_decision_release_id
                    FROM desktop_session
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise SessionPersistenceError(
                "Unable to retrieve desktop session."
            ) from exc
        if not rows:
            return None
        if len(rows) != 1 or rows[0]["singleton_id"] != 1:
            raise SessionIntegrityError(
                "Desktop session singleton state is invalid."
            )
        return self._from_row(rows[0])

    def save(self, session: DesktopSession) -> None:
        if type(session) is not DesktopSession:
            raise TypeError("session must be DesktopSession.")
        values = self._values(session)
        try:
            with self._database.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO desktop_session (
                        singleton_id,
                        format_version,
                        saved_at,
                        active_project_id,
                        window_width,
                        window_height,
                        window_x,
                        window_y,
                        top_level_destination,
                        collection_review_destination,
                        observation_source,
                        queue_filter,
                        decision_priority_filter,
                        decision_state_filter,
                        selected_observation_source,
                        selected_observation_release_id,
                        selected_queue_item_id,
                        selected_decision_release_id
                    )
                    VALUES (
                        1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(singleton_id) DO UPDATE SET
                        format_version = excluded.format_version,
                        saved_at = excluded.saved_at,
                        active_project_id = excluded.active_project_id,
                        window_width = excluded.window_width,
                        window_height = excluded.window_height,
                        window_x = excluded.window_x,
                        window_y = excluded.window_y,
                        top_level_destination =
                            excluded.top_level_destination,
                        collection_review_destination =
                            excluded.collection_review_destination,
                        observation_source = excluded.observation_source,
                        queue_filter = excluded.queue_filter,
                        decision_priority_filter =
                            excluded.decision_priority_filter,
                        decision_state_filter =
                            excluded.decision_state_filter,
                        selected_observation_source =
                            excluded.selected_observation_source,
                        selected_observation_release_id =
                            excluded.selected_observation_release_id,
                        selected_queue_item_id =
                            excluded.selected_queue_item_id,
                        selected_decision_release_id =
                            excluded.selected_decision_release_id
                    """,
                    values,
                )
        except sqlite3.Error as exc:
            raise SessionPersistenceError(
                "Unable to save desktop session."
            ) from exc

    @staticmethod
    def _values(session: DesktopSession) -> tuple[object, ...]:
        selected = session.selected_observation
        return (
            session.format_version,
            _timestamp(session.saved_at),
            session.active_project_id,
            session.window_width,
            session.window_height,
            session.window_x,
            session.window_y,
            session.top_level_destination.value,
            session.collection_review_destination.value,
            session.observation_source.value,
            session.queue_filter.value,
            session.decision_priority_filter.value,
            session.decision_state_filter.value,
            None if selected is None else selected.source.value,
            None if selected is None else selected.release_id,
            session.selected_queue_item_id,
            session.selected_decision_release_id,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> DesktopSession:
        try:
            format_version = _integer(row["format_version"], "format_version")
            if format_version != SESSION_FORMAT_VERSION:
                raise SessionCompatibilityError(
                    "Desktop session format is not supported."
                )
            source_value = row["selected_observation_source"]
            release_value = row["selected_observation_release_id"]
            if (source_value is None) != (release_value is None):
                raise SessionIntegrityError(
                    "Stored observation identity is incomplete."
                )
            selected = (
                None
                if source_value is None
                else ObservationIdentity(
                    _enum(
                        source_value,
                        WeekendObservationSource,
                        "selected_observation_source",
                    ),
                    _positive_integer(
                        release_value,
                        "selected_observation_release_id",
                    ),
                )
            )
            return DesktopSession(
                format_version,
                _parse_timestamp(row["saved_at"]),
                _optional_identifier(
                    row["active_project_id"],
                    "active_project_id",
                ),
                _integer(row["window_width"], "window_width"),
                _integer(row["window_height"], "window_height"),
                _integer(row["window_x"], "window_x"),
                _integer(row["window_y"], "window_y"),
                _enum(
                    row["top_level_destination"],
                    TopLevelDestination,
                    "top_level_destination",
                ),
                _enum(
                    row["collection_review_destination"],
                    CollectionReviewDestination,
                    "collection_review_destination",
                ),
                _enum(
                    row["observation_source"],
                    WeekendObservationSource,
                    "observation_source",
                ),
                _enum(row["queue_filter"], QueueStatusFilter, "queue_filter"),
                _enum(
                    row["decision_priority_filter"],
                    DecisionPriorityFilter,
                    "decision_priority_filter",
                ),
                _enum(
                    row["decision_state_filter"],
                    DecisionStateFilter,
                    "decision_state_filter",
                ),
                selected,
                _optional_positive_integer(
                    row["selected_queue_item_id"],
                    "selected_queue_item_id",
                ),
                _optional_positive_integer(
                    row["selected_decision_release_id"],
                    "selected_decision_release_id",
                ),
            )
        except SessionCompatibilityError:
            raise
        except SessionIntegrityError:
            raise
        except Exception as exc:
            raise SessionIntegrityError(
                "Stored desktop session is invalid."
            ) from exc


def _timestamp(value: datetime) -> str:
    if type(value) is not datetime:
        raise TypeError("saved_at must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("saved_at must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _parse_timestamp(value: object) -> datetime:
    if type(value) is not str or not _CANONICAL_TIMESTAMP.fullmatch(value):
        raise SessionIntegrityError(
            "Stored session timestamp is not canonical UTC."
        )
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise SessionIntegrityError(
            "Stored session timestamp is not canonical UTC."
        )
    return parsed


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise SessionIntegrityError(f"Stored {name} is not an integer.")
    return value


def _positive_integer(value: object, name: str) -> int:
    result = _integer(value, name)
    if result <= 0:
        raise SessionIntegrityError(f"Stored {name} is not positive.")
    return result


def _optional_positive_integer(value: object, name: str) -> int | None:
    return None if value is None else _positive_integer(value, name)


def _optional_identifier(value: object, name: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value or value != value.strip():
        raise SessionIntegrityError(f"Stored {name} is invalid.")
    return value


def _enum(value: object, enum_type: type, name: str):
    if type(value) is not str:
        raise SessionIntegrityError(f"Stored {name} is invalid.")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise SessionIntegrityError(f"Stored {name} is invalid.") from exc


__all__ = ["SQLiteSessionRepository"]
