"""Immutable presentation models for Supply Changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

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

    def __post_init__(self) -> None:
        if type(self.state) is not SupplyChangesDetailState:
            raise TypeError("state must be a SupplyChangesDetailState.")
        _text(self.summary, "summary")
        object.__setattr__(self, "changes", tuple(self.changes))
        if any(type(value) is not ReleaseSupplyChangeViewModel for value in self.changes):
            raise TypeError("changes must contain ReleaseSupplyChangeViewModel values.")
        object.__setattr__(self, "diagnostics", _strings(self.diagnostics, "diagnostics"))
        if self.state in {SupplyChangesDetailState.LOADING, SupplyChangesDetailState.UNAVAILABLE}:
            if self.comparison_state is not None or self.changes or self.change_count is not None:
                raise SupplyChangesDetailConsistencyError("Loading or unavailable detail cannot contain result context.")
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

    @classmethod
    def loading(cls) -> "SupplyChangesDetailViewModel":
        return cls(SupplyChangesDetailState.LOADING, "Supply Changes is loading.")

    @classmethod
    def unavailable(cls) -> "SupplyChangesDetailViewModel":
        return cls(SupplyChangesDetailState.UNAVAILABLE, "Supply Changes is unavailable.")


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
