"""Application command and query boundaries for Marketplace History."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from dip.marketplace_history import (
    DEFAULT_RECENT_SNAPSHOT_LIMIT,
    MAX_RECENT_SNAPSHOT_LIMIT,
    MarketplaceHistoryRepository,
)
from dip.marketplace_intelligence import MarketplaceSnapshot


class MarketplaceHistoryConsistencyError(RuntimeError):
    """Raised when a repository violates the Marketplace History contract."""


class MarketplaceHistoryCommandService:
    """Persist an already-created Marketplace snapshot without enriching it."""

    def __init__(self, repository: MarketplaceHistoryRepository) -> None:
        self._repository = repository

    def record_snapshot(self, snapshot: MarketplaceSnapshot) -> MarketplaceSnapshot:
        """Record and return the exact immutable snapshot supplied by the caller."""

        if type(snapshot) is not MarketplaceSnapshot:
            raise TypeError("snapshot must be a MarketplaceSnapshot.")
        self._repository.save_snapshot(snapshot)
        return snapshot


class MarketplaceHistoryQueryService:
    """Expose bounded, read-only Marketplace snapshot history queries."""

    def __init__(self, repository: MarketplaceHistoryRepository) -> None:
        self._repository = repository

    def get_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None:
        """Return one snapshot by stable identifier, if it exists."""

        _validate_snapshot_id(snapshot_id)
        snapshot = self._repository.get_snapshot(snapshot_id)
        if snapshot is None:
            return None
        snapshot = _repository_snapshot(snapshot)
        if snapshot.snapshot_id != snapshot_id:
            raise MarketplaceHistoryConsistencyError(
                f"Repository returned snapshot {snapshot.snapshot_id!r} for requested "
                f"snapshot {snapshot_id!r}."
            )
        return snapshot

    def latest_snapshot(self) -> MarketplaceSnapshot | None:
        """Return the newest snapshot regardless of capture status."""

        snapshot = self._repository.latest_snapshot()
        return None if snapshot is None else _repository_snapshot(snapshot)

    def recent_snapshots(
        self,
        limit: int = DEFAULT_RECENT_SNAPSHOT_LIMIT,
    ) -> tuple[MarketplaceSnapshot, ...]:
        """Return a bounded immutable sequence in repository-defined order."""

        _validate_limit(limit)
        snapshots = tuple(self._repository.recent_snapshots(limit))
        if len(snapshots) > limit:
            raise MarketplaceHistoryConsistencyError(
                "Repository returned more Marketplace snapshots than requested."
            )
        validated = tuple(_repository_snapshot(value) for value in snapshots)
        identifiers = tuple(value.snapshot_id for value in validated)
        if len(set(identifiers)) != len(identifiers):
            raise MarketplaceHistoryConsistencyError(
                "Repository returned duplicate Marketplace snapshot identifiers."
            )
        return validated

    def all_snapshots(self) -> tuple[MarketplaceSnapshot, ...]:
        """Return complete immutable history in chronological order."""

        snapshots = tuple(self._repository.all_snapshots())
        validated = tuple(_repository_snapshot(value) for value in snapshots)
        identifiers = tuple(value.snapshot_id for value in validated)
        if len(set(identifiers)) != len(identifiers):
            raise MarketplaceHistoryConsistencyError(
                "Repository returned duplicate Marketplace snapshot identifiers."
            )
        order = tuple(
            (value.captured_at.astimezone(timezone.utc), value.snapshot_id)
            for value in validated
        )
        if order != tuple(sorted(order)):
            raise MarketplaceHistoryConsistencyError(
                "Repository returned complete Marketplace History outside chronological order."
            )
        return validated

    def previous_snapshot(
        self,
        snapshot_id: str,
    ) -> MarketplaceSnapshot | None:
        """Return the immediate global chronological predecessor, if present."""

        _validate_snapshot_id(snapshot_id)
        snapshot = self._repository.previous_snapshot(snapshot_id)
        if snapshot is None:
            return None
        snapshot = _repository_snapshot(snapshot)
        if snapshot.snapshot_id == snapshot_id:
            raise MarketplaceHistoryConsistencyError(
                "Repository returned the requested snapshot as its own predecessor."
            )
        return snapshot


def _repository_snapshot(value: Any) -> MarketplaceSnapshot:
    if type(value) is not MarketplaceSnapshot:
        raise MarketplaceHistoryConsistencyError(
            "Repository returned a value that is not a MarketplaceSnapshot."
        )
    return value


def _validate_snapshot_id(snapshot_id: Any) -> None:
    if not isinstance(snapshot_id, str):
        raise TypeError("snapshot_id must be a string.")
    if not snapshot_id or snapshot_id != snapshot_id.strip():
        raise ValueError("snapshot_id must be non-empty and trimmed.")


def _validate_limit(limit: Any) -> None:
    if type(limit) is not int:
        raise TypeError("limit must be an integer.")
    if not 1 <= limit <= MAX_RECENT_SNAPSHOT_LIMIT:
        raise ValueError(
            f"limit must be between 1 and {MAX_RECENT_SNAPSHOT_LIMIT}."
        )


__all__ = [
    "MarketplaceHistoryCommandService",
    "MarketplaceHistoryConsistencyError",
    "MarketplaceHistoryQueryService",
]
