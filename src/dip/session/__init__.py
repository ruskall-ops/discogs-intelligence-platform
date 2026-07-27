"""Desktop session restoration models and repository boundary."""

from .models import (
    CollectionReviewDestination,
    DecisionPriorityFilter,
    DecisionStateFilter,
    DesktopSession,
    DesktopSessionCapture,
    MAX_COORDINATE,
    MAX_WINDOW_DIMENSION,
    MIN_COORDINATE,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    QueueStatusFilter,
    SESSION_FORMAT_VERSION,
    SessionCompatibilityError,
    SessionIntegrityError,
    SessionPersistenceError,
    SessionValidationError,
    TopLevelDestination,
)
from .repository import SessionRepository

__all__ = [
    "CollectionReviewDestination",
    "DecisionPriorityFilter",
    "DecisionStateFilter",
    "DesktopSession",
    "DesktopSessionCapture",
    "MAX_COORDINATE",
    "MAX_WINDOW_DIMENSION",
    "MIN_COORDINATE",
    "MIN_WINDOW_HEIGHT",
    "MIN_WINDOW_WIDTH",
    "QueueStatusFilter",
    "SESSION_FORMAT_VERSION",
    "SessionCompatibilityError",
    "SessionIntegrityError",
    "SessionPersistenceError",
    "SessionRepository",
    "SessionValidationError",
    "TopLevelDestination",
]
