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
from .marketplace_activity import MarketplaceActivityExecutionConsistencyError, MarketplaceActivityExecutionService
from .marketplace_activity_presentation import MarketplaceActivityPresentationService
from .listing_lifecycle import ListingLifecycleExecutionConsistencyError, ListingLifecycleExecutionService
from .listing_lifecycle_presentation import ListingLifecyclePresentationService
from .marketplace_momentum import (
    MarketplaceMomentumExecutionConsistencyError,
    MarketplaceMomentumExecutionService,
    build_marketplace_momentum_input,
)
from .marketplace_momentum_presentation import MarketplaceMomentumPresentationService
from .marketplace_stability import (
    MarketplaceStabilityExecutionConsistencyError,
    MarketplaceStabilityExecutionService,
    build_marketplace_stability_input,
)
from .marketplace_stability_presentation import MarketplaceStabilityPresentationService
from .marketplace_scarcity import (
    MarketplaceScarcityExecutionConsistencyError,
    MarketplaceScarcityExecutionService,
    build_marketplace_scarcity_input,
)
from .marketplace_scarcity_presentation import MarketplaceScarcityPresentationService
from .marketplace_opportunity import (
    MarketplaceOpportunityExecutionConsistencyError,
    MarketplaceOpportunityExecutionService,
    build_marketplace_opportunity_input,
)
from .marketplace_opportunity_presentation import MarketplaceOpportunityPresentationService
from .portfolio_overview import (
    PortfolioOverviewExecutionConsistencyError,
    PortfolioOverviewExecutionService,
    build_portfolio_overview_input,
)
from .portfolio_overview_presentation import PortfolioOverviewPresentationService
from .portfolio_distribution import (
    PortfolioDistributionExecutionConsistencyError,
    PortfolioDistributionExecutionService,
    build_portfolio_distribution_input,
)
from .portfolio_distribution_presentation import PortfolioDistributionPresentationService
from .portfolio_concentration import (
    PortfolioConcentrationExecutionConsistencyError,
    PortfolioConcentrationExecutionService,
    build_portfolio_concentration_input,
)
from .portfolio_concentration_presentation import PortfolioConcentrationPresentationService
from .portfolio_opportunity_alignment import (
    PortfolioOpportunityAlignmentExecutionConsistencyError,
    PortfolioOpportunityAlignmentExecutionService,
    build_portfolio_opportunity_alignment_input,
)
from .portfolio_opportunity_alignment_presentation import PortfolioOpportunityAlignmentPresentationService
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
    "MarketplaceActivityExecutionConsistencyError",
    "MarketplaceActivityExecutionService",
    "MarketplaceActivityPresentationService",
    "ListingLifecycleExecutionConsistencyError",
    "ListingLifecycleExecutionService",
    "ListingLifecyclePresentationService",
    "MarketplaceMomentumExecutionConsistencyError",
    "MarketplaceMomentumExecutionService",
    "MarketplaceMomentumPresentationService",
    "MarketplaceStabilityExecutionConsistencyError",
    "MarketplaceStabilityExecutionService",
    "MarketplaceStabilityPresentationService",
    "MarketplaceScarcityExecutionConsistencyError",
    "MarketplaceScarcityExecutionService",
    "MarketplaceScarcityPresentationService",
    "MarketplaceOpportunityExecutionConsistencyError",
    "MarketplaceOpportunityExecutionService",
    "MarketplaceOpportunityPresentationService",
    "PortfolioOverviewExecutionConsistencyError",
    "PortfolioOverviewExecutionService",
    "PortfolioOverviewPresentationService",
    "PortfolioDistributionExecutionConsistencyError",
    "PortfolioDistributionExecutionService",
    "PortfolioDistributionPresentationService",
    "PortfolioConcentrationExecutionConsistencyError",
    "PortfolioConcentrationExecutionService",
    "PortfolioConcentrationPresentationService",
    "PortfolioOpportunityAlignmentExecutionConsistencyError",
    "PortfolioOpportunityAlignmentExecutionService",
    "PortfolioOpportunityAlignmentPresentationService",
    "WeekendListingsPresentationService",
    "build_marketplace_momentum_input",
    "build_marketplace_stability_input",
    "build_marketplace_scarcity_input",
    "build_marketplace_opportunity_input",
    "build_portfolio_overview_input",
    "build_portfolio_distribution_input",
    "build_portfolio_concentration_input",
    "build_portfolio_opportunity_alignment_input",
    "main",
]
