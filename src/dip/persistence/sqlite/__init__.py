"""SQLite persistence implementation."""

from .backup import SQLiteDatabaseBackupAdapter, SQLiteDatabaseBackupError
from .intelligence_history import SQLiteIntelligenceHistoryRepository
from .marketplace_history import SQLiteMarketplaceHistoryRepository
from .projects import SQLiteProjectRepository
from .session import SQLiteSessionRepository
from .collector_review import (
    SQLiteHotNowCalculatedStateRepository,
    SQLiteWeekendReviewQueueRepository,
)
from .current_release_metadata import (
    CurrentReleaseMetadataPersistenceError,
    SQLiteCurrentReleaseMetadataRepository,
)
from .repository import Database

__all__ = [
    "Database",
    "SQLiteDatabaseBackupAdapter",
    "SQLiteDatabaseBackupError",
    "SQLiteIntelligenceHistoryRepository",
    "SQLiteCurrentReleaseMetadataRepository",
    "CurrentReleaseMetadataPersistenceError",
    "SQLiteHotNowCalculatedStateRepository",
    "SQLiteMarketplaceHistoryRepository",
    "SQLiteProjectRepository",
    "SQLiteSessionRepository",
    "SQLiteWeekendReviewQueueRepository",
]
