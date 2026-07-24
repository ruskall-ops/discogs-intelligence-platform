"""Immutable presentation values for Listing Lifecycle Intelligence."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from dip.marketplace_intelligence import ListingLifecycleAnalysisState, ListingLifecycleState


class ListingLifecycleDetailConsistencyError(ValueError):
    """Raised when Listing Lifecycle presentation values are inconsistent."""


class ListingLifecycleDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_HISTORY = "insufficient_history"
    ERROR = "error"


@dataclass(frozen=True)
class ListingLifecycleViewModel:
    release_id: int
    listing_id: str
    lifecycle_state: ListingLifecycleState
    currently_present: bool
    first_observation_snapshot_id: str
    first_observation_at: datetime
    latest_observation_snapshot_id: str
    latest_observation_at: datetime
    snapshots_observed: int
    history_snapshot_count: int
    observation_ratio: Decimal
    continuous_lifetime: int
    disappearance_count: int
    reappearance_count: int
    longest_absence: int
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.release_id) is not int or self.release_id <= 0:
            raise ListingLifecycleDetailConsistencyError("release_id must be a positive integer.")
        _text(self.listing_id, "listing_id")
        if type(self.lifecycle_state) is not ListingLifecycleState:
            raise TypeError("lifecycle_state must be a ListingLifecycleState.")
        if type(self.currently_present) is not bool:
            raise TypeError("currently_present must be a boolean.")
        for name, value in (("snapshots_observed", self.snapshots_observed), ("history_snapshot_count", self.history_snapshot_count), ("continuous_lifetime", self.continuous_lifetime), ("disappearance_count", self.disappearance_count), ("reappearance_count", self.reappearance_count), ("longest_absence", self.longest_absence)):
            if type(value) is not int or value < (1 if name in {"snapshots_observed", "history_snapshot_count", "continuous_lifetime"} else 0):
                raise ListingLifecycleDetailConsistencyError(f"{name} is invalid.")
        if self.snapshots_observed > self.history_snapshot_count or self.continuous_lifetime > self.snapshots_observed:
            raise ListingLifecycleDetailConsistencyError("Lifecycle observation counts are inconsistent.")
        if type(self.observation_ratio) is not Decimal or self.observation_ratio != Decimal(self.snapshots_observed) / Decimal(self.history_snapshot_count):
            raise ListingLifecycleDetailConsistencyError("observation_ratio is inconsistent.")
        for name, value in (("first_observation_snapshot_id", self.first_observation_snapshot_id), ("latest_observation_snapshot_id", self.latest_observation_snapshot_id)):
            _text(value, name)
        for name, value in (("first_observation_at", self.first_observation_at), ("latest_observation_at", self.latest_observation_at)):
            if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
                raise ListingLifecycleDetailConsistencyError(f"{name} must be timezone-aware.")
        object.__setattr__(self, "diagnostics", _strings(self.diagnostics, "diagnostics"))


@dataclass(frozen=True)
class ListingLifecycleDetailViewModel:
    state: ListingLifecycleDetailState
    summary: str
    analysis_state: ListingLifecycleAnalysisState | None = None
    history_snapshot_count: int | None = None
    listing_count: int | None = None
    currently_present_count: int | None = None
    lifecycles: tuple[ListingLifecycleViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Listing Lifecycle")

    def __post_init__(self) -> None:
        lifecycles = tuple(self.lifecycles)
        diagnostics = _strings(self.diagnostics, "diagnostics")
        if any(type(value) is not ListingLifecycleViewModel for value in lifecycles):
            raise TypeError("lifecycles must contain ListingLifecycleViewModel values.")
        identities = tuple((value.release_id, value.listing_id) for value in lifecycles)
        if len(set(identities)) != len(identities):
            raise ListingLifecycleDetailConsistencyError("Listing identities must be unique.")
        if lifecycles != tuple(sorted(lifecycles, key=lambda value: (tuple(ListingLifecycleState).index(value.lifecycle_state), -value.observation_ratio, value.release_id, value.listing_id))):
            raise ListingLifecycleDetailConsistencyError("Lifecycles must retain canonical order.")
        if self.state in {ListingLifecycleDetailState.LOADING, ListingLifecycleDetailState.UNAVAILABLE}:
            if self.analysis_state is not None or lifecycles:
                raise ListingLifecycleDetailConsistencyError("Unavailable detail cannot contain lifecycle output.")
        else:
            if self.analysis_state is None or self.history_snapshot_count is None or self.listing_count is None or self.currently_present_count is None:
                raise ListingLifecycleDetailConsistencyError("Supplied detail requires complete summary context.")
            if self.listing_count != len(lifecycles) or self.currently_present_count != sum(value.currently_present for value in lifecycles):
                raise ListingLifecycleDetailConsistencyError("Detail summary counts must match lifecycles.")
        object.__setattr__(self, "lifecycles", lifecycles)
        object.__setattr__(self, "diagnostics", diagnostics)

    @classmethod
    def loading(cls) -> "ListingLifecycleDetailViewModel":
        return cls(ListingLifecycleDetailState.LOADING, "Listing Lifecycle is loading.")

    @classmethod
    def unavailable(cls) -> "ListingLifecycleDetailViewModel":
        return cls(ListingLifecycleDetailState.UNAVAILABLE, "Listing Lifecycle is unavailable.")


def _text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value.strip() != value:
        raise ListingLifecycleDetailConsistencyError(f"{name} must be non-empty and trimmed.")


def _strings(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list.")
    result = tuple(values)
    for value in result:
        _text(value, name)
    return result
