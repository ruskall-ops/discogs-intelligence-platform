"""Immutable presentation models for historical appearance frequency."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from dip.marketplace_intelligence import RareAppearancesAnalysisState


class RareAppearancesDetailConsistencyError(ValueError):
    """Raised when presentation values contradict typed module output."""


class RareAppearancesDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_HISTORY = "insufficient_history"
    ERROR = "error"


@dataclass(frozen=True)
class RareAppearanceViewModel:
    release_id: int
    appearance_count: int
    history_snapshot_count: int
    appearance_ratio: Decimal
    first_observed_snapshot_id: str
    first_observed_at: datetime
    latest_observed_snapshot_id: str
    latest_observed_at: datetime
    longest_absence: int
    observation_snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.release_id) is not int or self.release_id <= 0:
            raise RareAppearancesDetailConsistencyError("release_id must be a positive integer.")
        for name, value in (("appearance_count", self.appearance_count), ("history_snapshot_count", self.history_snapshot_count), ("longest_absence", self.longest_absence)):
            if type(value) is not int or value < 0:
                raise RareAppearancesDetailConsistencyError(f"{name} must be a non-negative integer.")
        if self.appearance_count <= 0 or self.appearance_count > self.history_snapshot_count:
            raise RareAppearancesDetailConsistencyError("Appearance counts are inconsistent.")
        if type(self.appearance_ratio) is not Decimal or self.appearance_ratio != Decimal(self.appearance_count) / Decimal(self.history_snapshot_count):
            raise RareAppearancesDetailConsistencyError("appearance_ratio is inconsistent.")
        for name, value in (("first_observed_snapshot_id", self.first_observed_snapshot_id), ("latest_observed_snapshot_id", self.latest_observed_snapshot_id)):
            if not isinstance(value, str) or not value or value.strip() != value:
                raise RareAppearancesDetailConsistencyError(f"{name} must be non-empty and trimmed.")
        for name, value in (("first_observed_at", self.first_observed_at), ("latest_observed_at", self.latest_observed_at)):
            if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
                raise RareAppearancesDetailConsistencyError(f"{name} must be timezone-aware.")
        if self.first_observed_at > self.latest_observed_at:
            raise RareAppearancesDetailConsistencyError("First observation cannot follow latest observation.")
        ids = tuple(self.observation_snapshot_ids)
        if len(ids) != self.appearance_count or len(set(ids)) != len(ids):
            raise RareAppearancesDetailConsistencyError("Observation snapshot IDs are inconsistent.")
        if ids[0] != self.first_observed_snapshot_id or ids[-1] != self.latest_observed_snapshot_id:
            raise RareAppearancesDetailConsistencyError("Observation boundary snapshots are inconsistent.")
        if self.appearance_count == 1 and self.longest_absence != 0:
            raise RareAppearancesDetailConsistencyError("A single appearance cannot have an internal absence.")
        object.__setattr__(self, "observation_snapshot_ids", ids)


@dataclass(frozen=True)
class RareAppearancesDetailViewModel:
    state: RareAppearancesDetailState
    summary: str
    analysis_state: RareAppearancesAnalysisState | None = None
    threshold: int | None = None
    history_snapshot_count: int | None = None
    release_count: int | None = None
    excluded_snapshot_count: int | None = None
    appearances: tuple[RareAppearanceViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Rare Appearances")

    def __post_init__(self) -> None:
        appearances = tuple(self.appearances)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not RareAppearanceViewModel for value in appearances) or any(not isinstance(value, str) for value in diagnostics):
            raise TypeError("Rare Appearances collections contain invalid values.")
        if appearances != tuple(sorted(appearances, key=lambda value: (value.appearance_count, -value.longest_absence, value.release_id))):
            raise RareAppearancesDetailConsistencyError("Appearances must retain canonical order.")
        if self.state in {RareAppearancesDetailState.LOADING, RareAppearancesDetailState.UNAVAILABLE}:
            if self.analysis_state is not None or appearances:
                raise RareAppearancesDetailConsistencyError("Unavailable detail cannot contain module output.")
        elif self.analysis_state is None or self.threshold is None or self.history_snapshot_count is None or self.release_count is None or self.excluded_snapshot_count is None:
            raise RareAppearancesDetailConsistencyError("Supplied detail requires complete summary context.")
        object.__setattr__(self, "appearances", appearances)
        object.__setattr__(self, "diagnostics", diagnostics)

    @classmethod
    def loading(cls) -> "RareAppearancesDetailViewModel":
        return cls(RareAppearancesDetailState.LOADING, "Rare Appearances is loading.")

    @classmethod
    def unavailable(cls) -> "RareAppearancesDetailViewModel":
        return cls(RareAppearancesDetailState.UNAVAILABLE, "Rare Appearances is unavailable.")
