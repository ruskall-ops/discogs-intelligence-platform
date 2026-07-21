"""Application bootstrap and use-case orchestration."""

from .collection_health_presentation import CollectionHealthPresentationService
from .comparison_presentation import ComparisonPresentationService
from .dashboard import (
    CollectionIntelligencePresentationService,
    DashboardHomepageService,
)
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


def main() -> None:
    """Start the desktop application."""

    from dip.experience.desktop.app import App

    App().mainloop()


__all__ = [
    "CollectionHealthPresentationService",
    "ComparisonHistoryUnavailableError",
    "ComparisonPresentationService",
    "CollectionIntelligencePresentationService",
    "DashboardHomepageService",
    "HistoricalIntelligenceExecution",
    "HistoricalModuleResult",
    "HistoricalExecutionNotFoundError",
    "IntelligenceComparisonService",
    "IntelligenceHistoryConsistencyError",
    "IntelligenceHistoryQueryService",
    "main",
]
