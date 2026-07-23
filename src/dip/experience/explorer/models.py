"""Immutable unified Explorer models plus the legacy compatibility models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
from typing import Any

from dip.experience.collection_health import CollectionHealthDetailViewModel
from dip.experience.collection_trends import (
    CollectionTrendsState,
    CollectionTrendsViewModel,
)
from dip.experience.dashboard import (
    DashboardCardState,
    DashboardComponentScore,
    DashboardHiddenGemViewModel,
    DashboardReleaseViewModel,
    DashboardSectionState,
)
from dip.experience.hidden_gems import HiddenGemsDetailViewModel
from dip.experience.price_changes import PriceChangesDetailViewModel
from dip.experience.supply_changes import SupplyChangesDetailViewModel
from dip.experience.rare_appearances import RareAppearancesDetailViewModel
from dip.experience.marketplace_activity import MarketplaceActivityDetailViewModel
from dip.experience.listing_lifecycle import ListingLifecycleDetailViewModel
from dip.experience.marketplace_momentum import MarketplaceMomentumDetailViewModel
from dip.experience.marketplace_stability import MarketplaceStabilityDetailViewModel
from dip.experience.weekend_listings import WeekendListingsDetailViewModel
from dip.intelligence import IntelligenceStatus


class CollectionExplorerConsistencyError(ValueError):
    """Raised when unified Collection Explorer values contradict one another."""


class CollectionExplorerDestination(str, Enum):
    """Stable destination identifiers in their documented order."""

    OVERVIEW = "overview"
    COLLECTION_HEALTH = "collection_health"
    HIDDEN_GEMS = "hidden_gems"
    COLLECTION_TRENDS = "collection_trends"
    WEEKEND_LISTINGS = "weekend_listings"
    PRICE_CHANGES = "price_changes"
    SUPPLY_CHANGES = "supply_changes"
    RARE_APPEARANCES = "rare_appearances"
    MARKETPLACE_ACTIVITY = "marketplace_activity"
    LISTING_LIFECYCLE = "listing_lifecycle"
    MARKETPLACE_MOMENTUM = "marketplace_momentum"
    MARKETPLACE_STABILITY = "marketplace_stability"


class CollectionExplorerState(str, Enum):
    """Explicit aggregate and destination availability states."""

    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class CollectionExplorerOverviewViewModel:
    """Concise orientation copied from the current Dashboard homepage."""

    state: CollectionExplorerState
    summary: str
    comparison_state: DashboardSectionState
    comparison_summary: str
    collection_size: int | None = None
    executed_at: datetime | None = None
    execution_status: IntelligenceStatus | None = None
    completed_module_count: int = 0
    total_module_count: int = 0
    run_id: int | None = None
    engine_version: str | None = None
    collection_health_score: float | None = None
    hidden_gems_count: int | None = None

    def __post_init__(self) -> None:
        _validate_state(self.state)
        _validate_text(self.summary, "summary")
        if type(self.comparison_state) is not DashboardSectionState:
            raise TypeError("comparison_state must be a DashboardSectionState.")
        _validate_text(self.comparison_summary, "comparison_summary")
        _optional_count(self.collection_size, "collection_size")
        _count(self.completed_module_count, "completed_module_count")
        _count(self.total_module_count, "total_module_count")
        if self.completed_module_count > self.total_module_count:
            raise CollectionExplorerConsistencyError(
                "completed_module_count cannot exceed total_module_count."
            )
        _optional_count(self.hidden_gems_count, "hidden_gems_count")
        _optional_score(self.collection_health_score)
        if self.engine_version is not None:
            _validate_text(self.engine_version, "engine_version")

        if self.state is CollectionExplorerState.AVAILABLE:
            if type(self.executed_at) is not datetime:
                raise CollectionExplorerConsistencyError(
                    "An available Explorer overview requires executed_at."
                )
            if type(self.execution_status) is not IntelligenceStatus:
                raise CollectionExplorerConsistencyError(
                    "An available Explorer overview requires execution_status."
                )
            _positive_count(self.run_id, "run_id")
        elif (
            self.collection_size is not None
            or self.executed_at is not None
            or self.execution_status is not None
            or self.completed_module_count
            or self.total_module_count
            or self.run_id is not None
            or self.engine_version is not None
            or self.collection_health_score is not None
            or self.hidden_gems_count is not None
        ):
            raise CollectionExplorerConsistencyError(
                "A non-available Explorer overview cannot contain execution values."
            )


@dataclass(frozen=True)
class CollectionExplorerDestinationViewModel:
    """One deterministic navigation destination and its availability."""

    destination: CollectionExplorerDestination
    label: str
    state: CollectionExplorerState

    def __post_init__(self) -> None:
        if type(self.destination) is not CollectionExplorerDestination:
            raise TypeError("destination must be a CollectionExplorerDestination.")
        _validate_text(self.label, "label")
        _validate_state(self.state)


_DESTINATION_ORDER = tuple(CollectionExplorerDestination)
_DESTINATION_LABELS = {
    CollectionExplorerDestination.OVERVIEW: "Overview",
    CollectionExplorerDestination.COLLECTION_HEALTH: "Collection Health",
    CollectionExplorerDestination.HIDDEN_GEMS: "Hidden Gems",
    CollectionExplorerDestination.COLLECTION_TRENDS: "Collection Trends",
    CollectionExplorerDestination.WEEKEND_LISTINGS: "Weekend Listings",
    CollectionExplorerDestination.PRICE_CHANGES: "Price Changes",
    CollectionExplorerDestination.SUPPLY_CHANGES: "Supply Changes",
    CollectionExplorerDestination.RARE_APPEARANCES: "Rare Appearances",
    CollectionExplorerDestination.MARKETPLACE_ACTIVITY: "Marketplace Activity",
    CollectionExplorerDestination.LISTING_LIFECYCLE: "Listing Lifecycle",
    CollectionExplorerDestination.MARKETPLACE_MOMENTUM: "Marketplace Momentum",
    CollectionExplorerDestination.MARKETPLACE_STABILITY: "Marketplace Stability",
}


@dataclass(frozen=True)
class CollectionExplorerViewModel:
    """One immutable Explorer workspace built from a single homepage model."""

    state: CollectionExplorerState
    destinations: tuple[CollectionExplorerDestinationViewModel, ...]
    selected_destination: CollectionExplorerDestination
    overview: CollectionExplorerOverviewViewModel
    collection_health: CollectionHealthDetailViewModel
    hidden_gems: HiddenGemsDetailViewModel
    collection_trends: CollectionTrendsViewModel
    weekend_listings: WeekendListingsDetailViewModel
    price_changes: PriceChangesDetailViewModel
    supply_changes: SupplyChangesDetailViewModel
    rare_appearances: RareAppearancesDetailViewModel
    marketplace_activity: MarketplaceActivityDetailViewModel
    listing_lifecycle: ListingLifecycleDetailViewModel
    marketplace_momentum: MarketplaceMomentumDetailViewModel
    marketplace_stability: MarketplaceStabilityDetailViewModel
    title: str = field(init=False, default="Collection Explorer")

    def __post_init__(self) -> None:
        _validate_state(self.state)
        destinations = _freeze_destinations(self.destinations)
        if type(self.selected_destination) is not CollectionExplorerDestination:
            raise TypeError(
                "selected_destination must be a CollectionExplorerDestination."
            )
        if type(self.overview) is not CollectionExplorerOverviewViewModel:
            raise TypeError("overview must be a CollectionExplorerOverviewViewModel.")
        if type(self.collection_health) is not CollectionHealthDetailViewModel:
            raise TypeError(
                "collection_health must be a CollectionHealthDetailViewModel."
            )
        if type(self.hidden_gems) is not HiddenGemsDetailViewModel:
            raise TypeError("hidden_gems must be a HiddenGemsDetailViewModel.")
        if type(self.collection_trends) is not CollectionTrendsViewModel:
            raise TypeError("collection_trends must be a CollectionTrendsViewModel.")
        if type(self.weekend_listings) is not WeekendListingsDetailViewModel:
            raise TypeError("weekend_listings must be a WeekendListingsDetailViewModel.")
        if type(self.price_changes) is not PriceChangesDetailViewModel:
            raise TypeError("price_changes must be a PriceChangesDetailViewModel.")
        if type(self.supply_changes) is not SupplyChangesDetailViewModel:
            raise TypeError("supply_changes must be a SupplyChangesDetailViewModel.")
        if type(self.rare_appearances) is not RareAppearancesDetailViewModel:
            raise TypeError("rare_appearances must be a RareAppearancesDetailViewModel.")
        if type(self.marketplace_activity) is not MarketplaceActivityDetailViewModel:
            raise TypeError("marketplace_activity must be a MarketplaceActivityDetailViewModel.")
        if type(self.listing_lifecycle) is not ListingLifecycleDetailViewModel:
            raise TypeError("listing_lifecycle must be a ListingLifecycleDetailViewModel.")
        if type(self.marketplace_momentum) is not MarketplaceMomentumDetailViewModel:
            raise TypeError(
                "marketplace_momentum must be a MarketplaceMomentumDetailViewModel."
            )
        if type(self.marketplace_stability) is not MarketplaceStabilityDetailViewModel:
            raise TypeError("marketplace_stability must be a MarketplaceStabilityDetailViewModel.")

        expected_states = (
            self.overview.state,
            _collection_health_state(self.collection_health),
            _hidden_gems_state(self.hidden_gems),
            _collection_trends_state(self.collection_trends),
            _weekend_listings_state(self.weekend_listings),
            _price_changes_state(self.price_changes),
            _supply_changes_state(self.supply_changes),
            _rare_appearances_state(self.rare_appearances),
            _marketplace_activity_state(self.marketplace_activity),
            _listing_lifecycle_state(self.listing_lifecycle),
            _marketplace_momentum_state(self.marketplace_momentum),
            _marketplace_stability_state(self.marketplace_stability),
        )
        if tuple(item.state for item in destinations) != expected_states:
            raise CollectionExplorerConsistencyError(
                "Destination states must match their composed detail models."
            )
        if self.selected_destination not in tuple(
            item.destination for item in destinations
        ):
            raise CollectionExplorerConsistencyError(
                "The selected destination must be present in the Explorer."
            )
        expected_state = _aggregate_state(expected_states)
        if self.state is not expected_state:
            raise CollectionExplorerConsistencyError(
                "Explorer state contradicts its destination states."
            )
        object.__setattr__(self, "destinations", destinations)

    def destination_for(
        self,
        destination: CollectionExplorerDestination | str,
    ) -> CollectionExplorerDestinationViewModel | None:
        """Return one navigation destination by stable identifier."""

        try:
            identifier = CollectionExplorerDestination(destination)
        except (TypeError, ValueError):
            return None
        return next(
            (item for item in self.destinations if item.destination is identifier),
            None,
        )


def destination_view_models(
    overview: CollectionExplorerOverviewViewModel,
    collection_health: CollectionHealthDetailViewModel,
    hidden_gems: HiddenGemsDetailViewModel,
    collection_trends: CollectionTrendsViewModel,
    weekend_listings: WeekendListingsDetailViewModel,
    price_changes: PriceChangesDetailViewModel,
    supply_changes: SupplyChangesDetailViewModel,
    rare_appearances: RareAppearancesDetailViewModel,
    marketplace_activity: MarketplaceActivityDetailViewModel,
    listing_lifecycle: ListingLifecycleDetailViewModel,
    marketplace_momentum: MarketplaceMomentumDetailViewModel,
    marketplace_stability: MarketplaceStabilityDetailViewModel,
) -> tuple[CollectionExplorerDestinationViewModel, ...]:
    """Create the fixed navigation sequence for all composed destinations."""

    states = (
        overview.state,
        _collection_health_state(collection_health),
        _hidden_gems_state(hidden_gems),
        _collection_trends_state(collection_trends),
        _weekend_listings_state(weekend_listings),
        _price_changes_state(price_changes),
        _supply_changes_state(supply_changes),
        _rare_appearances_state(rare_appearances),
        _marketplace_activity_state(marketplace_activity),
        _listing_lifecycle_state(listing_lifecycle),
        _marketplace_momentum_state(marketplace_momentum),
        _marketplace_stability_state(marketplace_stability),
    )
    return tuple(
        CollectionExplorerDestinationViewModel(
            destination=destination,
            label=_DESTINATION_LABELS[destination],
            state=state,
        )
        for destination, state in zip(_DESTINATION_ORDER, states, strict=True)
    )


def explorer_state(
    destinations: tuple[CollectionExplorerDestinationViewModel, ...],
) -> CollectionExplorerState:
    """Derive the aggregate state from already validated destinations."""

    return _aggregate_state(tuple(destination.state for destination in destinations))


def _freeze_destinations(
    values: Any,
) -> tuple[CollectionExplorerDestinationViewModel, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("destinations must be a collection.")
    try:
        destinations = tuple(values)
    except TypeError as exc:
        raise TypeError("destinations must be a collection.") from exc
    if any(
        type(value) is not CollectionExplorerDestinationViewModel
        for value in destinations
    ):
        raise TypeError(
            "destinations must contain CollectionExplorerDestinationViewModel values."
        )
    identifiers = tuple(item.destination for item in destinations)
    if len(set(identifiers)) != len(identifiers):
        raise CollectionExplorerConsistencyError(
            "Explorer destination identifiers must be unique."
        )
    if identifiers != _DESTINATION_ORDER:
        raise CollectionExplorerConsistencyError(
            "Explorer destinations must use the documented order."
        )
    labels = tuple(item.label for item in destinations)
    if len(set(labels)) != len(labels):
        raise CollectionExplorerConsistencyError(
            "Explorer destination labels must be unique."
        )
    if labels != tuple(_DESTINATION_LABELS[item] for item in _DESTINATION_ORDER):
        raise CollectionExplorerConsistencyError(
            "Explorer destinations must use their stable display labels."
        )
    return destinations


def _collection_health_state(
    detail: CollectionHealthDetailViewModel,
) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _hidden_gems_state(detail: HiddenGemsDetailViewModel) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _collection_trends_state(detail: CollectionTrendsViewModel) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _weekend_listings_state(
    detail: WeekendListingsDetailViewModel,
) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _price_changes_state(
    detail: PriceChangesDetailViewModel,
) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _supply_changes_state(detail: SupplyChangesDetailViewModel) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _rare_appearances_state(detail: RareAppearancesDetailViewModel) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _marketplace_activity_state(detail: MarketplaceActivityDetailViewModel) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _listing_lifecycle_state(detail: ListingLifecycleDetailViewModel) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _marketplace_momentum_state(
    detail: MarketplaceMomentumDetailViewModel,
) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _marketplace_stability_state(
    detail: MarketplaceStabilityDetailViewModel,
) -> CollectionExplorerState:
    return CollectionExplorerState(detail.state.value)


def _aggregate_state(
    states: tuple[CollectionExplorerState, ...],
) -> CollectionExplorerState:
    if states and all(state is CollectionExplorerState.LOADING for state in states):
        return CollectionExplorerState.LOADING
    if states and states[0] is CollectionExplorerState.EMPTY and all(
        state is CollectionExplorerState.UNAVAILABLE for state in states[1:]
    ):
        return CollectionExplorerState.EMPTY
    if all(state is CollectionExplorerState.UNAVAILABLE for state in states):
        return CollectionExplorerState.UNAVAILABLE
    if all(state is CollectionExplorerState.ERROR for state in states):
        return CollectionExplorerState.ERROR

    core_states = states[:3]
    trends_state = states[3]
    weekend_state = states[4]
    price_changes_state = states[5]
    supply_changes_state = states[6]
    rare_appearances_state = states[7]
    marketplace_activity_state = states[8]
    listing_lifecycle_state = states[9]
    marketplace_momentum_state = states[10]
    marketplace_stability_state = states[11]
    usable = {
        CollectionExplorerState.AVAILABLE,
        CollectionExplorerState.EMPTY,
    }
    if (
        all(state in usable for state in core_states)
        and trends_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_HISTORY,
        }
        and weekend_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_DATA,
        }
        and price_changes_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_HISTORY,
            CollectionExplorerState.INSUFFICIENT_DATA,
        }
        and supply_changes_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_HISTORY,
            CollectionExplorerState.INSUFFICIENT_DATA,
        }
        and rare_appearances_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_HISTORY,
        }
        and marketplace_activity_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_DATA,
        }
        and listing_lifecycle_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_HISTORY,
        }
        and marketplace_momentum_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_DATA,
        }
        and marketplace_stability_state
        in {
            *usable,
            CollectionExplorerState.UNAVAILABLE,
            CollectionExplorerState.INSUFFICIENT_DATA,
        }
    ):
        return CollectionExplorerState.AVAILABLE
    if any(state in usable or state is CollectionExplorerState.PARTIAL for state in core_states):
        return CollectionExplorerState.PARTIAL
    if any(state is CollectionExplorerState.ERROR for state in states):
        return CollectionExplorerState.ERROR
    return CollectionExplorerState.UNAVAILABLE


def _validate_state(value: Any) -> None:
    if type(value) is not CollectionExplorerState:
        raise TypeError("state must be a CollectionExplorerState.")


def _validate_text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string.")


def _count(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must be non-negative.")


def _optional_count(value: Any, name: str) -> None:
    if value is not None:
        _count(value, name)


def _positive_count(value: Any, name: str) -> None:
    _count(value, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _optional_score(value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("collection_health_score must be a number or None.")
    score = float(value)
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError(
            "collection_health_score must be finite and between 0 and 100."
        )


# Compatibility models for clients of the original current-engine Explorer.
@dataclass(frozen=True)
class CollectionHealthExplorerViewModel:
    module_id: str
    title: str
    state: DashboardCardState
    overall_health: float | None
    summary: str
    component_scores: tuple[DashboardComponentScore, ...] = ()
    evidence: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class HiddenGemsExplorerViewModel:
    module_id: str
    title: str
    state: DashboardCardState
    total_hidden_gems: int | None
    summary: str
    ranked_releases: tuple[DashboardHiddenGemViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalIntelligenceExplorerViewModel:
    module_id: str
    title: str
    state: DashboardCardState
    summary: str
    latest_snapshot: str | None = None
    previous_snapshot: str | None = None
    collection_size_change: int | None = None
    collection_value_change: str | None = None
    average_value_change: str | None = None
    median_value_change: str | None = None
    releases_added: int | None = None
    releases_removed: int | None = None
    added_releases: tuple[DashboardReleaseViewModel, ...] = ()
    removed_releases: tuple[DashboardReleaseViewModel, ...] = ()
    top_gainers: tuple[DashboardReleaseViewModel, ...] = ()
    top_decliners: tuple[DashboardReleaseViewModel, ...] = ()
    evidence_coverage: str = ""
    diagnostics: tuple[str, ...] = ()


ExplorerSection = (
    CollectionHealthExplorerViewModel
    | HiddenGemsExplorerViewModel
    | HistoricalIntelligenceExplorerViewModel
)


@dataclass(frozen=True)
class CollectionIntelligenceExplorerViewModel:
    sections: tuple[ExplorerSection, ...] = ()

    def section_for(self, module_id: str) -> ExplorerSection | None:
        return next(
            (
                section
                for section in self.sections
                if section.module_id == module_id
            ),
            None,
        )
