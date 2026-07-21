"""Append-only persistence contracts for raw Marketplace observations."""

from .repository import (
    DEFAULT_RECENT_SNAPSHOT_LIMIT,
    MAX_RECENT_SNAPSHOT_LIMIT,
    MarketplaceHistoryIntegrityError,
    MarketplaceHistoryPersistenceError,
    MarketplaceHistoryRepository,
    MarketplaceSnapshotConflictError,
)

__all__ = [
    "DEFAULT_RECENT_SNAPSHOT_LIMIT",
    "MAX_RECENT_SNAPSHOT_LIMIT",
    "MarketplaceHistoryIntegrityError",
    "MarketplaceHistoryPersistenceError",
    "MarketplaceHistoryRepository",
    "MarketplaceSnapshotConflictError",
]
