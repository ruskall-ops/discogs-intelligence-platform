"""Persistence boundary for immutable Marketplace snapshot history."""

from typing import Protocol

from dip.marketplace_intelligence import MarketplaceSnapshot


DEFAULT_RECENT_SNAPSHOT_LIMIT = 20
MAX_RECENT_SNAPSHOT_LIMIT = 100


class MarketplaceSnapshotConflictError(RuntimeError):
    """Raised when a snapshot ID is reused for different immutable content."""


class MarketplaceHistoryPersistenceError(RuntimeError):
    """Raised when Marketplace History storage cannot complete an operation."""


class MarketplaceHistoryIntegrityError(MarketplaceHistoryPersistenceError):
    """Raised when stored Marketplace History is malformed or inconsistent."""


class MarketplaceHistoryRepository(Protocol):
    """Append and retrieve Marketplace snapshots without storage coupling."""

    def save_snapshot(self, snapshot: MarketplaceSnapshot) -> None:
        """Idempotently persist one snapshot without replacing its identity."""
        ...

    def get_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None:
        """Return one snapshot by its stable domain identifier, if present."""
        ...

    def latest_snapshot(self) -> MarketplaceSnapshot | None:
        """Return the first snapshot in deterministic newest-first order."""
        ...

    def recent_snapshots(
        self,
        limit: int,
    ) -> tuple[MarketplaceSnapshot, ...]:
        """Return at most ``limit`` snapshots in deterministic newest-first order."""
        ...

    def all_snapshots(self) -> tuple[MarketplaceSnapshot, ...]:
        """Return complete history in deterministic oldest-first order."""
        ...

    def previous_snapshot(
        self,
        snapshot_id: str,
    ) -> MarketplaceSnapshot | None:
        """Return the snapshot immediately before the identified snapshot."""
        ...


__all__ = [
    "DEFAULT_RECENT_SNAPSHOT_LIMIT",
    "MAX_RECENT_SNAPSHOT_LIMIT",
    "MarketplaceHistoryIntegrityError",
    "MarketplaceHistoryPersistenceError",
    "MarketplaceHistoryRepository",
    "MarketplaceSnapshotConflictError",
]
