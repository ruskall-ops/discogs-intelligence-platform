"""Immutable application models for desktop session restoration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from dip.collector_review import ObservationIdentity, WeekendObservationSource


SESSION_FORMAT_VERSION = 1
MIN_WINDOW_WIDTH = 1050
MIN_WINDOW_HEIGHT = 650
MAX_WINDOW_DIMENSION = 32767
MIN_COORDINATE = -2147483648
MAX_COORDINATE = 2147483647


class SessionValidationError(ValueError):
    """Raised when proposed desktop session state is invalid."""


class SessionCompatibilityError(RuntimeError):
    """Raised when stored session state uses an unsupported format."""


class SessionIntegrityError(RuntimeError):
    """Raised when persisted session state cannot be reconstructed safely."""


class SessionPersistenceError(RuntimeError):
    """Raised when session persistence cannot be completed."""


class TopLevelDestination(str, Enum):
    PROJECT = "project"
    DASHBOARD = "dashboard"
    COLLECTION_REVIEW = "collection_review"


class CollectionReviewDestination(str, Enum):
    OBSERVATIONS = "observations"
    WEEKEND_REVIEW_QUEUE = "weekend_review_queue"
    COLLECTION_DECISIONS = "collection_decisions"


class QueueStatusFilter(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ALL = "all"


class DecisionPriorityFilter(str, Enum):
    ALL = "all"
    HIGH_PRIORITY_REVIEW = "high_priority_review"
    WORTH_REVIEWING = "worth_reviewing"
    POSSIBLE_CANDIDATE = "possible_candidate"
    LOW_PRIORITY = "low_priority"
    NOT_SCORED = "not_scored"


class DecisionStateFilter(str, Enum):
    ALL = "all"
    REVIEW = "review"
    KEEP = "keep"
    LIST_FOR_SALE = "list_for_sale"
    MAYBE = "maybe"
    IGNORE = "ignore"


@dataclass(frozen=True)
class DesktopSessionCapture:
    """Typed desktop state awaiting one application-owned save timestamp."""

    active_project_id: str | None
    window_width: int
    window_height: int
    window_x: int
    window_y: int
    top_level_destination: TopLevelDestination
    collection_review_destination: CollectionReviewDestination
    observation_source: WeekendObservationSource
    queue_filter: QueueStatusFilter
    decision_priority_filter: DecisionPriorityFilter
    decision_state_filter: DecisionStateFilter
    selected_observation: ObservationIdentity | None = None
    selected_queue_item_id: int | None = None
    selected_decision_release_id: int | None = None

    def __post_init__(self) -> None:
        _validate_values(self)


@dataclass(frozen=True)
class DesktopSession:
    """One complete persisted desktop session."""

    format_version: int
    saved_at: datetime
    active_project_id: str | None
    window_width: int
    window_height: int
    window_x: int
    window_y: int
    top_level_destination: TopLevelDestination
    collection_review_destination: CollectionReviewDestination
    observation_source: WeekendObservationSource
    queue_filter: QueueStatusFilter
    decision_priority_filter: DecisionPriorityFilter
    decision_state_filter: DecisionStateFilter
    selected_observation: ObservationIdentity | None = None
    selected_queue_item_id: int | None = None
    selected_decision_release_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.format_version) is not int:
            raise TypeError("format_version must be an integer.")
        if self.format_version != SESSION_FORMAT_VERSION:
            raise SessionCompatibilityError(
                "Desktop session format is not supported."
            )
        if type(self.saved_at) is not datetime:
            raise TypeError("saved_at must be a datetime.")
        if self.saved_at.tzinfo is None or self.saved_at.utcoffset() is None:
            raise SessionValidationError("saved_at must be timezone-aware.")
        _validate_values(self)


def _validate_values(value: DesktopSession | DesktopSessionCapture) -> None:
    _optional_identifier(value.active_project_id, "active_project_id")
    _bounded_integer(
        value.window_width,
        "window_width",
        MIN_WINDOW_WIDTH,
        MAX_WINDOW_DIMENSION,
    )
    _bounded_integer(
        value.window_height,
        "window_height",
        MIN_WINDOW_HEIGHT,
        MAX_WINDOW_DIMENSION,
    )
    _bounded_integer(
        value.window_x,
        "window_x",
        MIN_COORDINATE,
        MAX_COORDINATE,
    )
    _bounded_integer(
        value.window_y,
        "window_y",
        MIN_COORDINATE,
        MAX_COORDINATE,
    )
    for name, enum_type in (
        ("top_level_destination", TopLevelDestination),
        ("collection_review_destination", CollectionReviewDestination),
        ("observation_source", WeekendObservationSource),
        ("queue_filter", QueueStatusFilter),
        ("decision_priority_filter", DecisionPriorityFilter),
        ("decision_state_filter", DecisionStateFilter),
    ):
        if type(getattr(value, name)) is not enum_type:
            raise TypeError(f"{name} must be {enum_type.__name__}.")
    if (
        value.selected_observation is not None
        and type(value.selected_observation) is not ObservationIdentity
    ):
        raise TypeError(
            "selected_observation must be ObservationIdentity or None."
        )
    _optional_positive_integer(
        value.selected_queue_item_id,
        "selected_queue_item_id",
    )
    _optional_positive_integer(
        value.selected_decision_release_id,
        "selected_decision_release_id",
    )


def _optional_identifier(value: object, name: str) -> None:
    if value is None:
        return
    if type(value) is not str or not value or value != value.strip():
        raise TypeError(f"{name} must be a non-empty stripped string or None.")


def _bounded_integer(value: object, name: str, minimum: int, maximum: int) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if not minimum <= value <= maximum:
        raise SessionValidationError(
            f"{name} must be between {minimum} and {maximum}."
        )


def _optional_positive_integer(value: object, name: str) -> None:
    if value is None:
        return
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer or None.")
    if value <= 0:
        raise SessionValidationError(f"{name} must be positive or None.")


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
    "SessionValidationError",
    "TopLevelDestination",
]
