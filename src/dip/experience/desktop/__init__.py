"""Tkinter desktop experience with import-safe presentation models."""

from .collection_health_renderer import (
    DesktopCollectionHealthController,
    DesktopCollectionHealthRenderer,
    DesktopCollectionHealthSection,
    DesktopCollectionHealthSectionId,
    DesktopCollectionHealthView,
)
from .collection_explorer_renderer import (
    DesktopCollectionExplorerController,
    DesktopCollectionExplorerNavigationItem,
    DesktopCollectionExplorerRenderer,
    DesktopCollectionExplorerSection,
    DesktopCollectionExplorerView,
)
from .collection_trends_renderer import (
    DesktopCollectionTrendMetric,
    DesktopCollectionTrendsRenderer,
    DesktopCollectionTrendsView,
)
from .dashboard_renderer import DesktopDashboardCard, DesktopDashboardRenderer
from .homepage_renderer import (
    DesktopDashboardHomepageRenderer,
    DesktopDashboardHomepageSection,
)
from .hidden_gems_renderer import (
    DesktopHiddenGemCandidate,
    DesktopHiddenGemsController,
    DesktopHiddenGemsRenderer,
    DesktopHiddenGemsView,
)
from .weekend_listings_renderer import (
    DesktopWeekendListing,
    DesktopWeekendListingsRenderer,
    DesktopWeekendListingsView,
)
from .explorer_renderer import (
    DesktopExplorerController,
    DesktopExplorerRenderer,
    DesktopExplorerSection,
    DesktopExplorerView,
)

__all__ = [
    "App",
    "DesktopCollectionHealthController",
    "DesktopCollectionHealthRenderer",
    "DesktopCollectionHealthSection",
    "DesktopCollectionHealthSectionId",
    "DesktopCollectionHealthView",
    "DesktopCollectionExplorerController",
    "DesktopCollectionExplorerNavigationItem",
    "DesktopCollectionExplorerRenderer",
    "DesktopCollectionExplorerSection",
    "DesktopCollectionExplorerView",
    "DesktopCollectionTrendMetric",
    "DesktopCollectionTrendsRenderer",
    "DesktopCollectionTrendsView",
    "DesktopDashboardCard",
    "DesktopDashboardRenderer",
    "DesktopDashboardHomepageRenderer",
    "DesktopDashboardHomepageSection",
    "DesktopExplorerRenderer",
    "DesktopExplorerController",
    "DesktopExplorerSection",
    "DesktopExplorerView",
    "DesktopHiddenGemCandidate",
    "DesktopHiddenGemsController",
    "DesktopHiddenGemsRenderer",
    "DesktopHiddenGemsView",
    "DesktopWeekendListing",
    "DesktopWeekendListingsRenderer",
    "DesktopWeekendListingsView",
]


def __getattr__(name: str):
    if name == "App":
        from .app import App

        return App
    raise AttributeError(name)
