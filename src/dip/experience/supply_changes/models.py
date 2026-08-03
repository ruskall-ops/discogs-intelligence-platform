"""Immutable presentation models for Supply Changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from dip.experience.results_presentation import (
    ComparisonContextViewModel,
    PresentationStateCopy,
    PresentationStateKind,
    SummaryCount,
    SummaryCountIdentifier,
    presentation_state_copy,
)
from dip.marketplace_intelligence import MarketplaceDataStatus, SupplyChangeKind, SupplyChangesComparisonState


class SupplyChangesDetailConsistencyError(ValueError):
    """Raised when Supply Changes presentation values contradict one another."""


class SupplyChangesDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class SupplyChangesSnapshotViewModel:
    snapshot_id: str
    captured_at: datetime
    source: str
    status: MarketplaceDataStatus
    source_version: str | None = None

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        if type(self.captured_at) is not datetime or self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise SupplyChangesDetailConsistencyError("captured_at must be timezone-aware.")
        _text(self.source, "source")
        if type(self.status) is not MarketplaceDataStatus:
            raise TypeError("status must be a MarketplaceDataStatus.")
        if self.source_version is not None:
            _text(self.source_version, "source_version")


@dataclass(frozen=True)
class ReleaseSupplyChangeViewModel:
    release_id: int
    previous_supply: int | None
    latest_supply: int | None
    delta: int | None
    change_kind: SupplyChangeKind
    previous_snapshot_id: str
    latest_snapshot_id: str
    evidence: tuple[str, ...]
    artist: str | None = None
    title: str | None = None
    display_label: str | None = None
    uses_current_metadata: bool = False
    previous_observed_at: datetime | None = None
    latest_observed_at: datetime | None = None
    observation_diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _count(self.release_id, "release_id", positive=True)
        _optional_count(self.previous_supply, "previous_supply")
        _optional_count(self.latest_supply, "latest_supply")
        if self.delta is not None and type(self.delta) is not int:
            raise TypeError("delta must be an integer or None.")
        if type(self.change_kind) is not SupplyChangeKind:
            raise TypeError("change_kind must be a SupplyChangeKind.")
        _text(self.previous_snapshot_id, "previous_snapshot_id")
        _text(self.latest_snapshot_id, "latest_snapshot_id")
        evidence = _strings(self.evidence, "evidence")
        if not evidence:
            raise SupplyChangesDetailConsistencyError("A supply change requires evidence.")
        object.__setattr__(self, "evidence", evidence)
        for name, value in (("artist", self.artist), ("title", self.title)):
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None.")
        if self.display_label is not None:
            _text(self.display_label, "display_label")
        if type(self.uses_current_metadata) is not bool:
            raise TypeError("uses_current_metadata must be a boolean.")
        if self.uses_current_metadata:
            if self.display_label is None or (self.artist is None and self.title is None):
                raise SupplyChangesDetailConsistencyError("Current metadata requires a current label value.")
        elif self.display_label is not None and self.display_label != f"Release {self.release_id}":
            raise SupplyChangesDetailConsistencyError("Fallback labels must preserve release identity.")
        for name, value in (("previous_observed_at", self.previous_observed_at), ("latest_observed_at", self.latest_observed_at)):
            if value is not None and (type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None):
                raise SupplyChangesDetailConsistencyError(f"{name} must be timezone-aware or None.")
        object.__setattr__(self, "observation_diagnostics", _strings(self.observation_diagnostics, "observation_diagnostics"))
        expected_delta = None if self.previous_supply is None or self.latest_supply is None else self.latest_supply - self.previous_supply
        if self.delta != expected_delta:
            raise SupplyChangesDetailConsistencyError("delta must equal latest minus previous supply.")
        valid = {
            SupplyChangeKind.INCREASED: self.delta is not None and self.delta > 0,
            SupplyChangeKind.DECREASED: self.delta is not None and self.delta < 0,
            SupplyChangeKind.NEWLY_AVAILABLE: self.previous_supply == 0 and self.latest_supply is not None and self.latest_supply > 0,
            SupplyChangeKind.NO_LONGER_AVAILABLE: self.previous_supply is not None and self.previous_supply > 0 and self.latest_supply == 0,
            SupplyChangeKind.INCOMPARABLE: self.delta is None and (self.previous_supply is None or self.latest_supply is None),
        }[self.change_kind]
        if not valid:
            raise SupplyChangesDetailConsistencyError("Supply change kind contradicts its values.")


@dataclass(frozen=True)
class SupplyChangesDetailViewModel:
    state: SupplyChangesDetailState
    summary: str
    comparison_state: SupplyChangesComparisonState | None = None
    previous_snapshot: SupplyChangesSnapshotViewModel | None = None
    latest_snapshot: SupplyChangesSnapshotViewModel | None = None
    source: str | None = None
    change_count: int | None = None
    unchanged_count: int | None = None
    incomparable_count: int | None = None
    changes: tuple[ReleaseSupplyChangeViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Supply Changes")
    state_copy: PresentationStateCopy | None = field(init=False, default=None)
    comparison_context: ComparisonContextViewModel | None = field(
        init=False,
        default=None,
    )
    summary_counts: tuple[SummaryCount, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        if type(self.state) is not SupplyChangesDetailState:
            raise TypeError("state must be a SupplyChangesDetailState.")
        _text(self.summary, "summary")
        object.__setattr__(self, "changes", tuple(self.changes))
        if any(type(value) is not ReleaseSupplyChangeViewModel for value in self.changes):
            raise TypeError("changes must contain ReleaseSupplyChangeViewModel values.")
        object.__setattr__(self, "diagnostics", _strings(self.diagnostics, "diagnostics"))
        if self.state in {SupplyChangesDetailState.LOADING, SupplyChangesDetailState.UNAVAILABLE}:
            if self.comparison_state is not None or self.previous_snapshot is not None or self.latest_snapshot is not None or self.source is not None or self.changes or any(value is not None for value in (self.change_count, self.unchanged_count, self.incomparable_count)):
                raise SupplyChangesDetailConsistencyError("Loading or unavailable detail cannot contain result context.")
            _set_shared_presentation(self)
            return
        if self.comparison_state is None or self.change_count is None or self.unchanged_count is None or self.incomparable_count is None:
            raise SupplyChangesDetailConsistencyError("A supplied result requires comparison state and summary counts.")
        if type(self.change_count) is not int or type(self.unchanged_count) is not int or type(self.incomparable_count) is not int:
            raise TypeError("Summary counts must be integers.")
        if min(self.change_count, self.unchanged_count, self.incomparable_count) < 0:
            raise SupplyChangesDetailConsistencyError("Summary counts must not be negative.")
        if self.change_count != len(self.changes):
            raise SupplyChangesDetailConsistencyError("change_count must match the complete change list.")
        if tuple(c.release_id for c in self.changes) != tuple(sorted(c.release_id for c in self.changes)):
            raise SupplyChangesDetailConsistencyError("Supply changes must retain release_id order.")
        if self.incomparable_count != sum(c.change_kind is SupplyChangeKind.INCOMPARABLE for c in self.changes):
            raise SupplyChangesDetailConsistencyError("incomparable_count must match detailed changes.")
        expected_state = {
            SupplyChangesComparisonState.PARTIAL: SupplyChangesDetailState.PARTIAL,
            SupplyChangesComparisonState.INSUFFICIENT_HISTORY: SupplyChangesDetailState.INSUFFICIENT_HISTORY,
            SupplyChangesComparisonState.INSUFFICIENT_DATA: SupplyChangesDetailState.INSUFFICIENT_DATA,
            SupplyChangesComparisonState.FAILED: SupplyChangesDetailState.ERROR,
        }.get(self.comparison_state)
        if expected_state is None:
            expected_state = SupplyChangesDetailState.AVAILABLE if self.change_count else SupplyChangesDetailState.EMPTY
        if self.state is not expected_state:
            raise SupplyChangesDetailConsistencyError("Supply state contradicts comparison state.")
        both = self.previous_snapshot is not None and self.latest_snapshot is not None
        if self.state is SupplyChangesDetailState.INSUFFICIENT_HISTORY:
            if self.previous_snapshot is not None or self.changes or any((self.change_count, self.unchanged_count, self.incomparable_count)):
                raise SupplyChangesDetailConsistencyError("Insufficient history cannot contain a baseline or facts.")
        elif self.state is not SupplyChangesDetailState.ERROR and not both:
            raise SupplyChangesDetailConsistencyError("A comparison requires both snapshot contexts.")
        if both:
            if self.previous_snapshot.captured_at.astimezone(timezone.utc) >= self.latest_snapshot.captured_at.astimezone(timezone.utc):
                raise SupplyChangesDetailConsistencyError("Baseline must be strictly earlier than current.")
            if self.previous_snapshot.source != self.latest_snapshot.source or self.source != self.previous_snapshot.source:
                raise SupplyChangesDetailConsistencyError("Comparison source must match both snapshots.")
            if self.previous_snapshot.source_version != self.latest_snapshot.source_version:
                raise SupplyChangesDetailConsistencyError("Comparison source versions must match.")
            for change in self.changes:
                if (change.previous_snapshot_id, change.latest_snapshot_id) != (self.previous_snapshot.snapshot_id, self.latest_snapshot.snapshot_id):
                    raise SupplyChangesDetailConsistencyError("Supply detail references must match snapshots.")
        if self.state is SupplyChangesDetailState.INSUFFICIENT_DATA and (self.unchanged_count or any(change.change_kind is not SupplyChangeKind.INCOMPARABLE for change in self.changes)):
            raise SupplyChangesDetailConsistencyError("Insufficient data may contain only incomparable details.")
        if self.state is SupplyChangesDetailState.ERROR and (self.changes or any((self.change_count, self.unchanged_count, self.incomparable_count))):
            raise SupplyChangesDetailConsistencyError("An error result cannot contain successful supply evidence.")
        _set_shared_presentation(self)

    @classmethod
    def loading(cls) -> "SupplyChangesDetailViewModel":
        return cls(SupplyChangesDetailState.LOADING, "Supply Changes is loading.")

    @classmethod
    def unavailable(cls) -> "SupplyChangesDetailViewModel":
        return cls(SupplyChangesDetailState.UNAVAILABLE, "Supply Changes is unavailable.")


def supply_presentation_state_kind(
    detail: SupplyChangesDetailViewModel,
) -> PresentationStateKind | None:
    """Adapt the typed Supply state without parsing copy or recalculating facts."""

    if type(detail) is not SupplyChangesDetailViewModel:
        raise TypeError("detail must be a SupplyChangesDetailViewModel.")
    if detail.state in {
        SupplyChangesDetailState.LOADING,
        SupplyChangesDetailState.UNAVAILABLE,
    }:
        return None
    if detail.state is SupplyChangesDetailState.EMPTY:
        return (
            PresentationStateKind.NO_CHANGES
            if detail.unchanged_count
            else PresentationStateKind.EMPTY
        )
    return {
        SupplyChangesDetailState.AVAILABLE: PresentationStateKind.AVAILABLE,
        SupplyChangesDetailState.PARTIAL: PresentationStateKind.PARTIAL,
        SupplyChangesDetailState.INSUFFICIENT_HISTORY: (
            PresentationStateKind.INSUFFICIENT_HISTORY
        ),
        SupplyChangesDetailState.INSUFFICIENT_DATA: (
            PresentationStateKind.INSUFFICIENT_DATA
        ),
        SupplyChangesDetailState.ERROR: PresentationStateKind.ERROR,
    }[detail.state]


def _set_shared_presentation(detail: SupplyChangesDetailViewModel) -> None:
    kind = supply_presentation_state_kind(detail)
    object.__setattr__(
        detail,
        "state_copy",
        None if kind is None else presentation_state_copy(kind),
    )
    previous = detail.previous_snapshot
    latest = detail.latest_snapshot
    context = None
    if previous is not None and latest is not None:
        context = ComparisonContextViewModel.from_snapshot_values(
            previous_snapshot_id=previous.snapshot_id,
            previous_captured_at=previous.captured_at,
            previous_source=previous.source,
            previous_source_version=previous.source_version,
            latest_snapshot_id=latest.snapshot_id,
            latest_captured_at=latest.captured_at,
            latest_source=latest.source,
            latest_source_version=latest.source_version,
        )
    object.__setattr__(detail, "comparison_context", context)
    values = (
        (
            SummaryCountIdentifier.RELEASE_CHANGES,
            "Release changes",
            detail.change_count,
        ),
        (
            SummaryCountIdentifier.UNCHANGED,
            "Unchanged releases",
            detail.unchanged_count,
        ),
        (
            SummaryCountIdentifier.INCOMPARABLE,
            "Incomparable releases",
            detail.incomparable_count,
        ),
    )
    if detail.state in {
        SupplyChangesDetailState.ERROR,
        SupplyChangesDetailState.INSUFFICIENT_HISTORY,
    }:
        counts = ()
    elif detail.state is SupplyChangesDetailState.INSUFFICIENT_DATA:
        counts = (
            ()
            if detail.incomparable_count is None or detail.incomparable_count == 0
            else (
                SummaryCount(
                    SummaryCountIdentifier.INCOMPARABLE,
                    "Incomparable releases",
                    detail.incomparable_count,
                ),
            )
        )
    else:
        counts = (
            ()
            if any(value is None for _, _, value in values)
            else tuple(
                SummaryCount(identifier, label, value)
                for identifier, label, value in values
                if value is not None
            )
        )
    object.__setattr__(detail, "summary_counts", counts)


def _text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value.strip() != value:
        raise SupplyChangesDetailConsistencyError(f"{name} must be non-empty and trimmed.")


def _count(value: object, name: str, *, positive: bool = False) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < (1 if positive else 0):
        raise SupplyChangesDetailConsistencyError(f"{name} has an invalid count.")


def _optional_count(value: object, name: str) -> None:
    if value is not None:
        _count(value, name)


def _strings(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list.")
    result = tuple(values)
    for value in result:
        _text(value, name)
    return result
