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
]


def __getattr__(name: str):
    if name == "App":
        from .app import App

        return App
    raise AttributeError(name)
