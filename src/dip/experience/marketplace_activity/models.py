"""Immutable presentation values for composite Marketplace Activity."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from dip.marketplace_intelligence import MarketplaceActivityState


class MarketplaceActivityDetailConsistencyError(ValueError):
    """Raised when Marketplace Activity presentation values are inconsistent."""


class MarketplaceActivityDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class ReleaseActivityViewModel:
    release_id: int
    total_activity_count: int
    historical_price_change_count: int
    historical_supply_change_count: int
    appearance_count: int
    appearance_ratio: Decimal
    longest_absence: int
    first_observation_snapshot_id: str
    first_observation_at: datetime
    latest_observation_snapshot_id: str
    latest_observation_at: datetime

    def __post_init__(self) -> None:
        for name, value in (("release_id", self.release_id), ("total_activity_count", self.total_activity_count), ("historical_price_change_count", self.historical_price_change_count), ("historical_supply_change_count", self.historical_supply_change_count), ("appearance_count", self.appearance_count), ("longest_absence", self.longest_absence)):
            if type(value) is not int or value < (1 if name in {"release_id", "appearance_count"} else 0):
                raise MarketplaceActivityDetailConsistencyError(f"{name} is invalid.")
        if self.total_activity_count != self.historical_price_change_count + self.historical_supply_change_count + self.appearance_count:
            raise MarketplaceActivityDetailConsistencyError("total_activity_count is inconsistent.")
        if type(self.appearance_ratio) is not Decimal or not Decimal(0) < self.appearance_ratio <= Decimal(1):
            raise MarketplaceActivityDetailConsistencyError("appearance_ratio is invalid.")
        for name, value in (("first_observation_snapshot_id", self.first_observation_snapshot_id), ("latest_observation_snapshot_id", self.latest_observation_snapshot_id)):
            if not isinstance(value, str) or not value or value.strip() != value:
                raise MarketplaceActivityDetailConsistencyError(f"{name} is invalid.")
        for name, value in (("first_observation_at", self.first_observation_at), ("latest_observation_at", self.latest_observation_at)):
            if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
                raise MarketplaceActivityDetailConsistencyError(f"{name} must be timezone-aware.")


@dataclass(frozen=True)
class MarketplaceActivityDetailViewModel:
    state: MarketplaceActivityDetailState
    summary: str
    activity_state: MarketplaceActivityState | None = None
    release_count: int | None = None
    total_activity_count: int | None = None
    activities: tuple[ReleaseActivityViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Marketplace Activity")

    def __post_init__(self) -> None:
        activities = tuple(self.activities)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not ReleaseActivityViewModel for value in activities) or any(not isinstance(value, str) for value in diagnostics):
            raise TypeError("Marketplace Activity collections contain invalid values.")
        if len({value.release_id for value in activities}) != len(activities):
            raise MarketplaceActivityDetailConsistencyError("Release activity IDs must be unique.")
        if activities != tuple(sorted(activities, key=lambda value: (-value.total_activity_count, value.appearance_count, value.release_id))):
            raise MarketplaceActivityDetailConsistencyError("Release activities must retain canonical order.")
        if self.state in {MarketplaceActivityDetailState.LOADING, MarketplaceActivityDetailState.UNAVAILABLE}:
            if self.activity_state is not None or activities:
                raise MarketplaceActivityDetailConsistencyError("Unavailable detail cannot contain activity output.")
        else:
            if self.activity_state is None or self.release_count is None or self.total_activity_count is None:
                raise MarketplaceActivityDetailConsistencyError("Supplied detail requires summary context.")
            if self.release_count != len(activities) or self.total_activity_count != sum(value.total_activity_count for value in activities):
                raise MarketplaceActivityDetailConsistencyError("Detail summary counts must match activities.")
        object.__setattr__(self, "activities", activities)
        object.__setattr__(self, "diagnostics", diagnostics)

    @classmethod
    def loading(cls) -> "MarketplaceActivityDetailViewModel":
        return cls(MarketplaceActivityDetailState.LOADING, "Marketplace Activity is loading.")

    @classmethod
    def unavailable(cls) -> "MarketplaceActivityDetailViewModel":
        return cls(MarketplaceActivityDetailState.UNAVAILABLE, "Marketplace Activity is unavailable.")
