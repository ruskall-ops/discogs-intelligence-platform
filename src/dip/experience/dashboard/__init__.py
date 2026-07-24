"""Presentation-neutral intelligence dashboard boundary."""

from .homepage import DashboardHomepageViewModelBuilder
from .homepage_models import (
    DashboardChangeSummaryViewModel,
    DashboardChangedModuleViewModel,
    DashboardCollectionHealthViewModel,
    DashboardCollectionOverviewViewModel,
    DashboardExecutionViewModel,
    DashboardHiddenGemsViewModel,
    DashboardHomepageConsistencyError,
    DashboardHomepageSection,
    DashboardHomepageViewModel,
    DashboardSectionId,
    DashboardSectionState,
)
from .models import (
    DashboardCardState,
    DashboardCardViewModel,
    DashboardComponentScore,
    DashboardHiddenGemViewModel,
    DashboardMetricValueViewModel,
    DashboardReleaseViewModel,
    HiddenGemsCardViewModel,
    HistoricalIntelligenceCardViewModel,
    IntelligenceDashboardViewModel,
)
from .presenter import (
    CollectionHealthCardPresenter,
    HiddenGemsCardPresenter,
    HistoricalIntelligenceCardPresenter,
    IntelligenceDashboardPresenter,
)

__all__ = [
    "CollectionHealthCardPresenter",
    "DashboardChangeSummaryViewModel",
    "DashboardChangedModuleViewModel",
    "DashboardCardState",
    "DashboardCardViewModel",
    "DashboardCollectionHealthViewModel",
    "DashboardCollectionOverviewViewModel",
    "DashboardComponentScore",
    "DashboardExecutionViewModel",
    "DashboardHiddenGemsViewModel",
    "DashboardHiddenGemViewModel",
    "DashboardHomepageConsistencyError",
    "DashboardHomepageSection",
    "DashboardHomepageViewModel",
    "DashboardHomepageViewModelBuilder",
    "DashboardReleaseViewModel",
    "DashboardMetricValueViewModel",
    "DashboardSectionId",
    "DashboardSectionState",
    "HiddenGemsCardPresenter",
    "HiddenGemsCardViewModel",
    "HistoricalIntelligenceCardPresenter",
    "HistoricalIntelligenceCardViewModel",
    "IntelligenceDashboardPresenter",
    "IntelligenceDashboardViewModel",
]
