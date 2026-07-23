"""Build the unified Collection Explorer from established presentation models."""

from __future__ import annotations

from dip.experience.collection_health import CollectionHealthDetailViewModel
from dip.experience.collection_trends import CollectionTrendsViewModel
from dip.experience.dashboard import (
    DashboardChangeSummaryViewModel,
    DashboardCollectionOverviewViewModel,
    DashboardExecutionViewModel,
    DashboardHomepageConsistencyError,
    DashboardHomepageViewModel,
    DashboardSectionId,
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

from .models import (
    CollectionExplorerDestination,
    CollectionExplorerOverviewViewModel,
    CollectionExplorerState,
    CollectionExplorerViewModel,
    destination_view_models,
    explorer_state,
)


class CollectionExplorerViewModelBuilder:
    """Compose one Explorer without duplicating established detail models."""

    def build(
        self,
        homepage: DashboardHomepageViewModel,
        collection_health: CollectionHealthDetailViewModel,
        hidden_gems: HiddenGemsDetailViewModel,
        collection_trends: CollectionTrendsViewModel | None = None,
        weekend_listings: WeekendListingsDetailViewModel | None = None,
        price_changes: PriceChangesDetailViewModel | None = None,
        supply_changes: SupplyChangesDetailViewModel | None = None,
        rare_appearances: RareAppearancesDetailViewModel | None = None,
        marketplace_activity: MarketplaceActivityDetailViewModel | None = None,
        listing_lifecycle: ListingLifecycleDetailViewModel | None = None,
        marketplace_momentum: MarketplaceMomentumDetailViewModel | None = None,
        marketplace_stability: MarketplaceStabilityDetailViewModel | None = None,
        *,
        selected_destination: CollectionExplorerDestination = (
            CollectionExplorerDestination.OVERVIEW
        ),
    ) -> CollectionExplorerViewModel:
        """Build all destinations from one already selected homepage result."""

        if type(homepage) is not DashboardHomepageViewModel:
            raise TypeError("homepage must be a DashboardHomepageViewModel.")
        if type(collection_health) is not CollectionHealthDetailViewModel:
            raise TypeError(
                "collection_health must be a CollectionHealthDetailViewModel."
            )
        if type(hidden_gems) is not HiddenGemsDetailViewModel:
            raise TypeError("hidden_gems must be a HiddenGemsDetailViewModel.")
        if type(selected_destination) is not CollectionExplorerDestination:
            raise TypeError(
                "selected_destination must be a CollectionExplorerDestination."
            )

        overview_source = homepage.section_for(DashboardSectionId.COLLECTION_OVERVIEW)
        changes = homepage.section_for(DashboardSectionId.WHAT_CHANGED)
        execution = homepage.section_for(DashboardSectionId.LATEST_EXECUTION)
        if type(overview_source) is not DashboardCollectionOverviewViewModel:
            raise DashboardHomepageConsistencyError(
                "The homepage does not contain a Collection overview section."
            )
        if type(changes) is not DashboardChangeSummaryViewModel:
            raise DashboardHomepageConsistencyError(
                "The homepage does not contain a What Changed section."
            )
        if type(execution) is not DashboardExecutionViewModel:
            raise DashboardHomepageConsistencyError(
                "The homepage does not contain a Latest execution section."
            )

        overview = self._overview(
            overview_source,
            changes,
            execution,
            collection_health,
            hidden_gems,
        )
        if collection_trends is None:
            collection_trends = (
                CollectionTrendsViewModel.loading()
                if overview.state is CollectionExplorerState.LOADING
                else CollectionTrendsViewModel.unavailable()
            )
        if type(collection_trends) is not CollectionTrendsViewModel:
            raise TypeError("collection_trends must be a CollectionTrendsViewModel.")
        if weekend_listings is None:
            weekend_listings = (
                WeekendListingsDetailViewModel.loading()
                if overview.state is CollectionExplorerState.LOADING
                else WeekendListingsDetailViewModel.unavailable()
            )
        if type(weekend_listings) is not WeekendListingsDetailViewModel:
            raise TypeError("weekend_listings must be a WeekendListingsDetailViewModel.")
        if price_changes is None:
            price_changes = (
                PriceChangesDetailViewModel.loading()
                if overview.state is CollectionExplorerState.LOADING
                else PriceChangesDetailViewModel.unavailable()
            )
        if type(price_changes) is not PriceChangesDetailViewModel:
            raise TypeError("price_changes must be a PriceChangesDetailViewModel.")
        if supply_changes is None:
            supply_changes = SupplyChangesDetailViewModel.loading() if overview.state is CollectionExplorerState.LOADING else SupplyChangesDetailViewModel.unavailable()
        if type(supply_changes) is not SupplyChangesDetailViewModel:
            raise TypeError("supply_changes must be a SupplyChangesDetailViewModel.")
        if rare_appearances is None:
            rare_appearances = RareAppearancesDetailViewModel.loading() if overview.state is CollectionExplorerState.LOADING else RareAppearancesDetailViewModel.unavailable()
        if type(rare_appearances) is not RareAppearancesDetailViewModel:
            raise TypeError("rare_appearances must be a RareAppearancesDetailViewModel.")
        if marketplace_activity is None:
            marketplace_activity = MarketplaceActivityDetailViewModel.loading() if overview.state is CollectionExplorerState.LOADING else MarketplaceActivityDetailViewModel.unavailable()
        if type(marketplace_activity) is not MarketplaceActivityDetailViewModel:
            raise TypeError("marketplace_activity must be a MarketplaceActivityDetailViewModel.")
        if listing_lifecycle is None:
            listing_lifecycle = ListingLifecycleDetailViewModel.loading() if overview.state is CollectionExplorerState.LOADING else ListingLifecycleDetailViewModel.unavailable()
        if type(listing_lifecycle) is not ListingLifecycleDetailViewModel:
            raise TypeError("listing_lifecycle must be a ListingLifecycleDetailViewModel.")
        if marketplace_momentum is None:
            marketplace_momentum = (
                MarketplaceMomentumDetailViewModel.loading()
                if overview.state is CollectionExplorerState.LOADING
                else MarketplaceMomentumDetailViewModel.unavailable()
            )
        if type(marketplace_momentum) is not MarketplaceMomentumDetailViewModel:
            raise TypeError(
                "marketplace_momentum must be a MarketplaceMomentumDetailViewModel."
            )
        if marketplace_stability is None:
            marketplace_stability = (
                MarketplaceStabilityDetailViewModel.loading()
                if overview.state is CollectionExplorerState.LOADING
                else MarketplaceStabilityDetailViewModel.unavailable()
            )
        if type(marketplace_stability) is not MarketplaceStabilityDetailViewModel:
            raise TypeError("marketplace_stability must be a MarketplaceStabilityDetailViewModel.")
        destinations = destination_view_models(
            overview,
            collection_health,
            hidden_gems,
            collection_trends,
            weekend_listings,
            price_changes,
            supply_changes,
            rare_appearances,
            marketplace_activity,
            listing_lifecycle,
            marketplace_momentum,
            marketplace_stability,
        )
        return CollectionExplorerViewModel(
            state=explorer_state(destinations),
            destinations=destinations,
            selected_destination=selected_destination,
            overview=overview,
            collection_health=collection_health,
            hidden_gems=hidden_gems,
            collection_trends=collection_trends,
            weekend_listings=weekend_listings,
            price_changes=price_changes,
            supply_changes=supply_changes,
            rare_appearances=rare_appearances,
            marketplace_activity=marketplace_activity,
            listing_lifecycle=listing_lifecycle,
            marketplace_momentum=marketplace_momentum,
            marketplace_stability=marketplace_stability,
        )

    @staticmethod
    def _overview(
        source: DashboardCollectionOverviewViewModel,
        changes: DashboardChangeSummaryViewModel,
        execution: DashboardExecutionViewModel,
        collection_health: CollectionHealthDetailViewModel,
        hidden_gems: HiddenGemsDetailViewModel,
    ) -> CollectionExplorerOverviewViewModel:
        state = _overview_state(source.state)
        available = state is CollectionExplorerState.AVAILABLE
        return CollectionExplorerOverviewViewModel(
            state=state,
            summary=source.summary,
            comparison_state=changes.state,
            comparison_summary=changes.summary,
            collection_size=source.collection_size if available else None,
            executed_at=source.latest_executed_at if available else None,
            execution_status=source.current_status if available else None,
            completed_module_count=(source.completed_module_count if available else 0),
            total_module_count=source.total_module_count if available else 0,
            run_id=execution.run_id if available else None,
            engine_version=execution.engine_version if available else None,
            collection_health_score=(
                collection_health.overall_score if available else None
            ),
            hidden_gems_count=(hidden_gems.candidate_count if available else None),
        )


def _overview_state(state: DashboardSectionState) -> CollectionExplorerState:
    states = {
        DashboardSectionState.LOADING: CollectionExplorerState.LOADING,
        DashboardSectionState.AVAILABLE: CollectionExplorerState.AVAILABLE,
        DashboardSectionState.EMPTY: CollectionExplorerState.EMPTY,
        DashboardSectionState.UNAVAILABLE: CollectionExplorerState.UNAVAILABLE,
        DashboardSectionState.ERROR: CollectionExplorerState.ERROR,
    }
    try:
        return states[state]
    except KeyError as exc:
        raise DashboardHomepageConsistencyError(
            "Collection overview has an unsupported state."
        ) from exc


__all__ = ["CollectionExplorerViewModelBuilder"]
