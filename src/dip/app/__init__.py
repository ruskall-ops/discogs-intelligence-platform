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
    "WeekendListingsPresentationService",
    "main",
]
