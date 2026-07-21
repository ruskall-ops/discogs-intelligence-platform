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
from dip.persistence.sqlite import Database, SQLiteIntelligenceHistoryRepository


@dataclass(frozen=True)
class DesktopApplicationDependencies:
    """Concrete dependencies required by the legacy Tkinter application shell."""

    database: Database
    dashboard_homepage: DashboardHomepageService
    collection_health_controller: DesktopCollectionHealthController
    collection_explorer_controller: DesktopCollectionExplorerController
    hidden_gems_controller: DesktopHiddenGemsController


def build_desktop_application_dependencies() -> DesktopApplicationDependencies:
    """Construct concrete adapters at the application's composition boundary."""

    database = Database(SETTINGS.database_path)
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

    return DesktopApplicationDependencies(
        database=database,
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
            ),
            DesktopCollectionExplorerRenderer(
                collection_health_renderer,
                hidden_gems_renderer,
                collection_trends_renderer,
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
