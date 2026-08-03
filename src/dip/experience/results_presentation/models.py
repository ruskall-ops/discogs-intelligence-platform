"""Small immutable primitives shared by factual result presentations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class PresentationStateKind(str, Enum):
    """Closed factual states available to presentation adapters."""

    AVAILABLE = "available"
    NO_CHANGES = "no_changes"
    EMPTY = "empty"
    PARTIAL = "partial"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    NO_IMPORTED_COLLECTION = "no_imported_collection"
    IMPORTED_NOT_ANALYSED = "imported_not_analysed"
    POST_IMPORT_DISPLAY_WARNING = "post_import_display_warning"


class SummaryCountIdentifier(str, Enum):
    """Stable identifiers for the existing Price and Supply summary counts."""

    LISTING_CHANGES = "listing_changes"
    RELEASE_CHANGES = "release_changes"
    UNCHANGED = "unchanged"
    INCOMPARABLE = "incomparable"


@dataclass(frozen=True)
class PresentationStateCopy:
    """Allowlisted user-facing copy for one canonical factual state."""

    kind: PresentationStateKind
    heading: str
    body: str
    action_label: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not PresentationStateKind:
            raise TypeError("kind must be a PresentationStateKind.")
        _text(self.heading, "heading")
        _text(self.body, "body")
        if self.action_label is not None:
            _text(self.action_label, "action_label")


@dataclass(frozen=True)
class SummaryCount:
    """One established non-negative result count ready for presentation."""

    identifier: SummaryCountIdentifier
    label: str
    value: int

    def __post_init__(self) -> None:
        if type(self.identifier) is not SummaryCountIdentifier:
            raise TypeError("identifier must be a SummaryCountIdentifier.")
        _text(self.label, "label")
        if type(self.value) is not int:
            raise TypeError("value must be a non-boolean integer.")
        if self.value < 0:
            raise ValueError("value must be non-negative.")


@dataclass(frozen=True)
class ComparisonContextViewModel:
    """Detached provenance for one strictly ordered Marketplace comparison."""

    previous_snapshot_id: str
    previous_captured_at: datetime
    latest_snapshot_id: str
    latest_captured_at: datetime
    source: str
    source_version: str | None

    def __post_init__(self) -> None:
        _text(self.previous_snapshot_id, "previous_snapshot_id")
        _text(self.latest_snapshot_id, "latest_snapshot_id")
        if self.previous_snapshot_id == self.latest_snapshot_id:
            raise ValueError("Comparison snapshot IDs must be distinct.")
        _aware(self.previous_captured_at, "previous_captured_at")
        _aware(self.latest_captured_at, "latest_captured_at")
        if self.previous_captured_at.astimezone(timezone.utc) >= (
            self.latest_captured_at.astimezone(timezone.utc)
        ):
            raise ValueError("The previous capture instant must be strictly earlier.")
        _text(self.source, "source")
        if self.source_version is not None:
            _text(self.source_version, "source_version")

    @classmethod
    def from_snapshot_values(
        cls,
        *,
        previous_snapshot_id: str,
        previous_captured_at: datetime,
        previous_source: str,
        previous_source_version: str | None,
        latest_snapshot_id: str,
        latest_captured_at: datetime,
        latest_source: str,
        latest_source_version: str | None,
    ) -> "ComparisonContextViewModel":
        """Validate both source identities before exposing one shared context."""

        _text(previous_source, "previous_source")
        _text(latest_source, "latest_source")
        if previous_source != latest_source:
            raise ValueError("Comparison snapshot sources must match.")
        if previous_source_version != latest_source_version:
            raise ValueError("Comparison snapshot source versions must match.")
        return cls(
            previous_snapshot_id=previous_snapshot_id,
            previous_captured_at=previous_captured_at,
            latest_snapshot_id=latest_snapshot_id,
            latest_captured_at=latest_captured_at,
            source=previous_source,
            source_version=previous_source_version,
        )


def _text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be non-empty and trimmed.")


def _aware(value: object, name: str) -> None:
    if (
        type(value) is not datetime
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime.")


__all__ = [
    "ComparisonContextViewModel",
    "PresentationStateCopy",
    "PresentationStateKind",
    "SummaryCount",
    "SummaryCountIdentifier",
]
