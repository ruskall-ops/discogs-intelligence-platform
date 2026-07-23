"""Concrete desktop dependency composition kept outside presentation code."""

from __future__ import annotations

from dataclasses import dataclass

from dip.app.collection_health_presentation import CollectionHealthPresentationService
from dip.app.collection_explorer_presentation import CollectionExplorerPresentationService
from dip.app.collection_trends_presentation import CollectionTrendsPresentationService
from dip.app.comparison_presentation import ComparisonPresentationService
from dip.app.dashboard import DashboardHomepageService
from dip.app.hidden_gems_presentation import HiddenGemsPresentationService
from dip.app.intelligence_comparison import IntelligenceComparisonService
from dip.app.intelligence_history import IntelligenceHistoryQueryService
from dip.app.marketplace_history import (
    MarketplaceHistoryCommandService,
    MarketplaceHistoryQueryService,
)
from dip.app.price_changes import PriceChangesExecutionService
from dip.app.price_changes_presentation import PriceChangesPresentationService
from dip.app.supply_changes import SupplyChangesExecutionService
from dip.app.supply_changes_presentation import SupplyChangesPresentationService
from dip.app.rare_appearances import RareAppearancesExecutionService
from dip.app.rare_appearances_presentation import RareAppearancesPresentationService
from dip.app.marketplace_activity import MarketplaceActivityExecutionService
from dip.app.marketplace_activity_presentation import MarketplaceActivityPresentationService
from dip.app.listing_lifecycle import ListingLifecycleExecutionService
from dip.app.listing_lifecycle_presentation import ListingLifecyclePresentationService
from dip.app.weekend_listings_presentation import WeekendListingsPresentationService
from dip.comparison import ComparisonEngine
from dip.config import SETTINGS
from dip.experience.collection_health import CollectionHealthDetailViewModelBuilder
from dip.experience.comparison import ComparisonViewModelBuilder
from dip.experience.collection_trends import CollectionTrendsViewModelBuilder
from dip.experience.dashboard import DashboardHomepageViewModelBuilder
from dip.experience.explorer import CollectionExplorerViewModelBuilder
from dip.experience.desktop.collection_health_renderer import (
    DesktopCollectionHealthController,
    DesktopCollectionHealthRenderer,
)
from dip.experience.desktop.collection_explorer_renderer import (
    DesktopCollectionExplorerController,
    DesktopCollectionExplorerRenderer,
)
from dip.experience.desktop.collection_trends_renderer import (
    DesktopCollectionTrendsRenderer,
)
from dip.experience.desktop.hidden_gems_renderer import (
    DesktopHiddenGemsController,
    DesktopHiddenGemsRenderer,
)
from dip.experience.hidden_gems import HiddenGemsDetailViewModelBuilder
from dip.experience.price_changes import PriceChangesDetailViewModelBuilder
from dip.experience.supply_changes import SupplyChangesDetailViewModelBuilder
from dip.experience.rare_appearances import RareAppearancesDetailViewModelBuilder
from dip.experience.marketplace_activity import MarketplaceActivityDetailViewModelBuilder
from dip.experience.listing_lifecycle import ListingLifecycleDetailViewModelBuilder
from dip.experience.desktop.price_changes_renderer import (
    DesktopPriceChangesRenderer,
)
from dip.experience.desktop.supply_changes_renderer import DesktopSupplyChangesRenderer
from dip.experience.desktop.rare_appearances_renderer import DesktopRareAppearancesRenderer
from dip.experience.desktop.marketplace_activity_renderer import DesktopMarketplaceActivityRenderer
from dip.experience.desktop.listing_lifecycle_renderer import DesktopListingLifecycleRenderer
from dip.experience.weekend_listings import WeekendListingsDetailViewModelBuilder
from dip.experience.desktop.weekend_listings_renderer import (
    DesktopWeekendListingsRenderer,
)
from dip.intelligence import IntelligenceEngine
from dip.marketplace_intelligence import ListingLifecycleModule, MarketplaceActivityModule, PriceChangesModule, RareAppearancesModule, SupplyChangesModule
from dip.persistence.sqlite import (
    Database,
    SQLiteIntelligenceHistoryRepository,
    SQLiteMarketplaceHistoryRepository,
)


@dataclass(frozen=True)
class DesktopApplicationDependencies:
    """Concrete dependencies required by the legacy Tkinter application shell."""

    database: Database
    dashboard_homepage: DashboardHomepageService
    collection_health_controller: DesktopCollectionHealthController
    collection_explorer_controller: DesktopCollectionExplorerController
    hidden_gems_controller: DesktopHiddenGemsController
    marketplace_history_commands: MarketplaceHistoryCommandService | None = None
    marketplace_history_queries: MarketplaceHistoryQueryService | None = None
    price_changes_execution: PriceChangesExecutionService | None = None
    supply_changes_execution: SupplyChangesExecutionService | None = None
    rare_appearances_execution: RareAppearancesExecutionService | None = None
    marketplace_activity_execution: MarketplaceActivityExecutionService | None = None
    listing_lifecycle_execution: ListingLifecycleExecutionService | None = None


def build_desktop_application_dependencies() -> DesktopApplicationDependencies:
    """Construct concrete adapters at the application's composition boundary."""

    database = Database(SETTINGS.database_path)
    marketplace_history_repository = SQLiteMarketplaceHistoryRepository(database)
    marketplace_history_commands = MarketplaceHistoryCommandService(
        marketplace_history_repository
    )
    marketplace_history_queries = MarketplaceHistoryQueryService(
        marketplace_history_repository
    )
    price_changes_execution = PriceChangesExecutionService(
        marketplace_history_queries,
        IntelligenceEngine((PriceChangesModule(),)),
    )
    supply_changes_execution = SupplyChangesExecutionService(
        marketplace_history_queries,
        IntelligenceEngine((SupplyChangesModule(),)),
    )
    rare_appearances_execution = RareAppearancesExecutionService(
        marketplace_history_queries,
        IntelligenceEngine((RareAppearancesModule(),)),
    )
    marketplace_activity_execution = MarketplaceActivityExecutionService(
        price_changes_execution,
        supply_changes_execution,
        rare_appearances_execution,
        IntelligenceEngine((MarketplaceActivityModule(),)),
    )
    listing_lifecycle_execution = ListingLifecycleExecutionService(
        marketplace_history_queries,
        IntelligenceEngine((ListingLifecycleModule(),)),
    )
    history_repository = SQLiteIntelligenceHistoryRepository(database)
    history_queries = IntelligenceHistoryQueryService(history_repository)
    comparison_service = IntelligenceComparisonService(
        history_queries,
        ComparisonEngine(),
    )
    comparison_presentation = ComparisonPresentationService(
        comparison_service,
        ComparisonViewModelBuilder(),
    )
    collection_health_presentation = CollectionHealthPresentationService(
        CollectionHealthDetailViewModelBuilder()
    )
    hidden_gems_presentation = HiddenGemsPresentationService(
        HiddenGemsDetailViewModelBuilder()
    )
    collection_health_renderer = DesktopCollectionHealthRenderer()
    hidden_gems_renderer = DesktopHiddenGemsRenderer()
    collection_trends_renderer = DesktopCollectionTrendsRenderer()
    collection_trends_presentation = CollectionTrendsPresentationService(
        history_queries,
        comparison_service,
        CollectionTrendsViewModelBuilder(),
    )
    weekend_listings_presentation = WeekendListingsPresentationService(
        WeekendListingsDetailViewModelBuilder()
    )
    weekend_listings_renderer = DesktopWeekendListingsRenderer()
    price_changes_presentation = PriceChangesPresentationService(
        PriceChangesDetailViewModelBuilder()
    )
    price_changes_renderer = DesktopPriceChangesRenderer()
    supply_changes_presentation = SupplyChangesPresentationService(
        SupplyChangesDetailViewModelBuilder()
    )
    supply_changes_renderer = DesktopSupplyChangesRenderer()
    rare_appearances_presentation = RareAppearancesPresentationService(
        RareAppearancesDetailViewModelBuilder()
    )
    rare_appearances_renderer = DesktopRareAppearancesRenderer()
    marketplace_activity_presentation = MarketplaceActivityPresentationService(
        MarketplaceActivityDetailViewModelBuilder()
    )
    marketplace_activity_renderer = DesktopMarketplaceActivityRenderer()
    listing_lifecycle_presentation = ListingLifecyclePresentationService(
        ListingLifecycleDetailViewModelBuilder()
    )
    listing_lifecycle_renderer = DesktopListingLifecycleRenderer()

    return DesktopApplicationDependencies(
        database=database,
        marketplace_history_commands=marketplace_history_commands,
        marketplace_history_queries=marketplace_history_queries,
        price_changes_execution=price_changes_execution,
        supply_changes_execution=supply_changes_execution,
        rare_appearances_execution=rare_appearances_execution,
        marketplace_activity_execution=marketplace_activity_execution,
        listing_lifecycle_execution=listing_lifecycle_execution,
        dashboard_homepage=DashboardHomepageService(
            history_queries,
            comparison_presentation,
            DashboardHomepageViewModelBuilder(),
        ),
        collection_health_controller=DesktopCollectionHealthController(
            collection_health_presentation,
            collection_health_renderer,
        ),
        collection_explorer_controller=DesktopCollectionExplorerController(
            CollectionExplorerPresentationService(
                collection_health_presentation,
                hidden_gems_presentation,
                CollectionExplorerViewModelBuilder(),
                collection_trends=collection_trends_presentation,
                weekend_listings=weekend_listings_presentation,
                price_changes=price_changes_presentation,
                supply_changes=supply_changes_presentation,
                rare_appearances=rare_appearances_presentation,
                marketplace_activity=marketplace_activity_presentation,
                listing_lifecycle=listing_lifecycle_presentation,
            ),
            DesktopCollectionExplorerRenderer(
                collection_health_renderer,
                hidden_gems_renderer,
                collection_trends_renderer,
                weekend_listings_renderer,
                price_changes_renderer,
                supply_changes_renderer,
                rare_appearances_renderer,
                marketplace_activity_renderer,
                listing_lifecycle_renderer,
            ),
        ),
        hidden_gems_controller=DesktopHiddenGemsController(
            hidden_gems_presentation,
            hidden_gems_renderer,
        ),
    )


__all__ = [
    "DesktopApplicationDependencies",
    "build_desktop_application_dependencies",
]
