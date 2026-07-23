"""Application coordination for the unified Collection Explorer."""

from __future__ import annotations

from typing import Protocol

from dip.experience.collection_health import CollectionHealthDetailViewModel
from dip.experience.collection_trends import CollectionTrendsViewModel
from dip.experience.dashboard import (
    DashboardHomepageViewModel,
    DashboardSectionId,
    DashboardSectionState,
)
from dip.experience.explorer import (
    CollectionExplorerDestination,
    CollectionExplorerViewModel,
)
from dip.experience.hidden_gems import HiddenGemsDetailViewModel
from dip.experience.price_changes import PriceChangesDetailViewModel
from dip.experience.supply_changes import SupplyChangesDetailViewModel
from dip.experience.rare_appearances import RareAppearancesDetailViewModel
from dip.experience.marketplace_activity import MarketplaceActivityDetailViewModel
from dip.experience.listing_lifecycle import ListingLifecycleDetailViewModel
from dip.experience.weekend_listings import WeekendListingsDetailViewModel
from dip.intelligence import IntelligenceResult


class _CollectionHealthPresentation(Protocol):
    def detail_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> CollectionHealthDetailViewModel: ...


class _HiddenGemsPresentation(Protocol):
    def detail_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> HiddenGemsDetailViewModel: ...


class _CollectionExplorerBuilder(Protocol):
    def build(
        self,
        homepage: DashboardHomepageViewModel,
        collection_health: CollectionHealthDetailViewModel,
        hidden_gems: HiddenGemsDetailViewModel,
        collection_trends: CollectionTrendsViewModel,
        weekend_listings: WeekendListingsDetailViewModel,
        price_changes: PriceChangesDetailViewModel,
        supply_changes: SupplyChangesDetailViewModel,
        rare_appearances: RareAppearancesDetailViewModel,
        marketplace_activity: MarketplaceActivityDetailViewModel,
        listing_lifecycle: ListingLifecycleDetailViewModel,
        *,
        selected_destination: CollectionExplorerDestination,
    ) -> CollectionExplorerViewModel: ...


class CollectionExplorerPresentationService:
    """Compose existing detail presentations for one current homepage."""

    def __init__(
        self,
        collection_health: _CollectionHealthPresentation,
        hidden_gems: _HiddenGemsPresentation,
        builder: _CollectionExplorerBuilder,
        *,
        collection_trends: "_CollectionTrendsPresentation | None" = None,
        weekend_listings: "_WeekendListingsPresentation | None" = None,
        price_changes: "_PriceChangesPresentation | None" = None,
        supply_changes: "_SupplyChangesPresentation | None" = None,
        rare_appearances: "_RareAppearancesPresentation | None" = None,
        marketplace_activity: "_MarketplaceActivityPresentation | None" = None,
        listing_lifecycle: "_ListingLifecyclePresentation | None" = None,
    ) -> None:
        self._collection_health = collection_health
        self._hidden_gems = hidden_gems
        self._builder = builder
        self._collection_trends = collection_trends
        self._weekend_listings = weekend_listings
        self._price_changes = price_changes
        self._supply_changes = supply_changes
        self._rare_appearances = rare_appearances
        self._marketplace_activity = marketplace_activity
        self._listing_lifecycle = listing_lifecycle

    def explorer_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
        *,
        selected_destination: CollectionExplorerDestination = (
            CollectionExplorerDestination.OVERVIEW
        ),
        weekend_listings_result: IntelligenceResult | None = None,
        price_changes_result: IntelligenceResult | None = None,
        supply_changes_result: IntelligenceResult | None = None,
        rare_appearances_result: IntelligenceResult | None = None,
        marketplace_activity_result: IntelligenceResult | None = None,
        listing_lifecycle_result: IntelligenceResult | None = None,
    ) -> CollectionExplorerViewModel:
        """Build every destination once from the exact same homepage model."""

        if type(homepage) is not DashboardHomepageViewModel:
            raise TypeError("homepage must be a DashboardHomepageViewModel.")
        if type(selected_destination) is not CollectionExplorerDestination:
            raise TypeError(
                "selected_destination must be a CollectionExplorerDestination."
            )
        collection_health = self._collection_health.detail_for_homepage(homepage)
        hidden_gems = self._hidden_gems.detail_for_homepage(homepage)
        collection_trends = (
            self._collection_trends.latest_trends()
            if self._collection_trends is not None
            else (
                CollectionTrendsViewModel.loading()
                if homepage.section_for(
                    DashboardSectionId.COLLECTION_OVERVIEW
                ).state is DashboardSectionState.LOADING
                else CollectionTrendsViewModel.unavailable()
            )
        )
        overview_loading = homepage.section_for(
            DashboardSectionId.COLLECTION_OVERVIEW
        ).state is DashboardSectionState.LOADING
        weekend_listings = (
            WeekendListingsDetailViewModel.loading()
            if overview_loading
            else (
                self._weekend_listings.detail_for_result(weekend_listings_result)
                if self._weekend_listings is not None
                else WeekendListingsDetailViewModel.unavailable()
            )
        )
        price_changes = (
            PriceChangesDetailViewModel.loading()
            if overview_loading
            else (
                self._price_changes.detail_for_result(price_changes_result)
                if self._price_changes is not None
                else PriceChangesDetailViewModel.unavailable()
            )
        )
        supply_changes = (
            SupplyChangesDetailViewModel.loading()
            if overview_loading
            else (self._supply_changes.detail_for_result(supply_changes_result) if self._supply_changes is not None else SupplyChangesDetailViewModel.unavailable())
        )
        rare_appearances = RareAppearancesDetailViewModel.loading() if overview_loading else (self._rare_appearances.detail_for_result(rare_appearances_result) if self._rare_appearances is not None else RareAppearancesDetailViewModel.unavailable())
        marketplace_activity = MarketplaceActivityDetailViewModel.loading() if overview_loading else (self._marketplace_activity.detail_for_result(marketplace_activity_result) if self._marketplace_activity is not None else MarketplaceActivityDetailViewModel.unavailable())
        listing_lifecycle = ListingLifecycleDetailViewModel.loading() if overview_loading else (self._listing_lifecycle.detail_for_result(listing_lifecycle_result) if self._listing_lifecycle is not None else ListingLifecycleDetailViewModel.unavailable())
        return self._builder.build(
            homepage,
            collection_health,
            hidden_gems,
            collection_trends,
            weekend_listings,
            price_changes,
            supply_changes,
            rare_appearances,
            marketplace_activity,
            listing_lifecycle,
            selected_destination=selected_destination,
        )


class _CollectionTrendsPresentation(Protocol):
    def latest_trends(self) -> CollectionTrendsViewModel: ...


class _WeekendListingsPresentation(Protocol):
    def detail_for_result(
        self,
        result: IntelligenceResult | None,
    ) -> WeekendListingsDetailViewModel: ...


class _PriceChangesPresentation(Protocol):
    def detail_for_result(
        self,
        result: IntelligenceResult | None,
    ) -> PriceChangesDetailViewModel: ...


class _SupplyChangesPresentation(Protocol):
    def detail_for_result(self, result: IntelligenceResult | None) -> SupplyChangesDetailViewModel: ...


class _RareAppearancesPresentation(Protocol):
    def detail_for_result(self, result: IntelligenceResult | None) -> RareAppearancesDetailViewModel: ...


class _MarketplaceActivityPresentation(Protocol):
    def detail_for_result(self, result: IntelligenceResult | None) -> MarketplaceActivityDetailViewModel: ...


class _ListingLifecyclePresentation(Protocol):
    def detail_for_result(self, result: IntelligenceResult | None) -> ListingLifecycleDetailViewModel: ...


__all__ = ["CollectionExplorerPresentationService"]
