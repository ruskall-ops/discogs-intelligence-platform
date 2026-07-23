"""Application bootstrap and use-case orchestration."""

from .collection_health_presentation import CollectionHealthPresentationService
from .collection_explorer_presentation import CollectionExplorerPresentationService
from .collection_trends_presentation import CollectionTrendsPresentationService
from .comparison_presentation import ComparisonPresentationService
from .dashboard import (
    CollectionIntelligencePresentationService,
    DashboardHomepageService,
)
from .hidden_gems_presentation import HiddenGemsPresentationService
from .intelligence_comparison import (
    ComparisonHistoryUnavailableError,
    HistoricalExecutionNotFoundError,
    IntelligenceComparisonService,
)
from .intelligence_history import (
    HistoricalIntelligenceExecution,
    HistoricalModuleResult,
    IntelligenceHistoryConsistencyError,
    IntelligenceHistoryQueryService,
)
from .marketplace_history import (
    MarketplaceHistoryCommandService,
    MarketplaceHistoryConsistencyError,
    MarketplaceHistoryQueryService,
)
from .price_changes import (
    PriceChangesExecutionConsistencyError,
    PriceChangesExecutionService,
)
from .price_changes_presentation import PriceChangesPresentationService
from .supply_changes import SupplyChangesExecutionConsistencyError, SupplyChangesExecutionService
from .supply_changes_presentation import SupplyChangesPresentationService
from .rare_appearances import RareAppearancesExecutionConsistencyError, RareAppearancesExecutionService
from .rare_appearances_presentation import RareAppearancesPresentationService
from .weekend_listings_presentation import WeekendListingsPresentationService


def main() -> None:
    """Start the desktop application."""

    from dip.experience.desktop.app import App

    App().mainloop()


__all__ = [
    "CollectionHealthPresentationService",
    "CollectionExplorerPresentationService",
    "CollectionTrendsPresentationService",
    "ComparisonHistoryUnavailableError",
    "ComparisonPresentationService",
    "CollectionIntelligencePresentationService",
    "DashboardHomepageService",
    "HistoricalIntelligenceExecution",
    "HistoricalModuleResult",
    "HistoricalExecutionNotFoundError",
    "HiddenGemsPresentationService",
    "IntelligenceComparisonService",
    "IntelligenceHistoryConsistencyError",
    "IntelligenceHistoryQueryService",
    "MarketplaceHistoryCommandService",
    "MarketplaceHistoryConsistencyError",
    "MarketplaceHistoryQueryService",
    "PriceChangesExecutionConsistencyError",
    "PriceChangesExecutionService",
    "PriceChangesPresentationService",
    "SupplyChangesExecutionConsistencyError",
    "SupplyChangesExecutionService",
    "SupplyChangesPresentationService",
    "RareAppearancesExecutionConsistencyError",
    "RareAppearancesExecutionService",
    "RareAppearancesPresentationService",
    "WeekendListingsPresentationService",
    "main",
]
