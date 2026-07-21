"""Tkinter desktop experience with import-safe presentation models."""

from .collection_health_renderer import (
    DesktopCollectionHealthController,
    DesktopCollectionHealthRenderer,
    DesktopCollectionHealthSection,
    DesktopCollectionHealthSectionId,
    DesktopCollectionHealthView,
)
from .dashboard_renderer import DesktopDashboardCard, DesktopDashboardRenderer
from .homepage_renderer import (
    DesktopDashboardHomepageRenderer,
    DesktopDashboardHomepageSection,
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
    "DesktopDashboardCard",
    "DesktopDashboardRenderer",
    "DesktopDashboardHomepageRenderer",
    "DesktopDashboardHomepageSection",
    "DesktopExplorerRenderer",
    "DesktopExplorerController",
    "DesktopExplorerSection",
    "DesktopExplorerView",
]


def __getattr__(name: str):
    if name == "App":
        from .app import App

        return App
    raise AttributeError(name)
