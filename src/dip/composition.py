"""Concrete desktop dependency composition kept outside presentation code."""

from __future__ import annotations

from dataclasses import dataclass

from dip.app.comparison_presentation import ComparisonPresentationService
from dip.app.dashboard import (
    CollectionIntelligencePresentationService,
    DashboardHomepageService,
)
from dip.app.intelligence_comparison import IntelligenceComparisonService
from dip.app.intelligence_context import IntelligenceContextFactory
from dip.app.intelligence_history import IntelligenceHistoryQueryService
from dip.comparison import ComparisonEngine
from dip.config import SETTINGS
from dip.experience.comparison import ComparisonViewModelBuilder
from dip.experience.dashboard import (
    DashboardHomepageViewModelBuilder,
    IntelligenceDashboardPresenter,
)
from dip.intelligence import IntelligenceEngine, build_v02_intelligence_registry
from dip.persistence.sqlite import Database, SQLiteIntelligenceHistoryRepository


@dataclass(frozen=True)
class DesktopApplicationDependencies:
    """Concrete dependencies required by the legacy Tkinter application shell."""

    database: Database
    dashboard_homepage: DashboardHomepageService
    collection_intelligence_presentation: CollectionIntelligencePresentationService
    intelligence_dashboard_presenter: IntelligenceDashboardPresenter


def build_desktop_application_dependencies() -> DesktopApplicationDependencies:
    """Construct concrete adapters at the application's composition boundary."""

    database = Database(SETTINGS.database_path)
    history_repository = SQLiteIntelligenceHistoryRepository(database)
    history_queries = IntelligenceHistoryQueryService(history_repository)
    comparison_presentation = ComparisonPresentationService(
        IntelligenceComparisonService(history_queries, ComparisonEngine()),
        ComparisonViewModelBuilder(),
    )
    intelligence_dashboard_presenter = IntelligenceDashboardPresenter()
    context_factory = IntelligenceContextFactory(database)
    engine = IntelligenceEngine(build_v02_intelligence_registry())

    return DesktopApplicationDependencies(
        database=database,
        dashboard_homepage=DashboardHomepageService(
            history_queries,
            comparison_presentation,
            DashboardHomepageViewModelBuilder(),
        ),
        collection_intelligence_presentation=(
            CollectionIntelligencePresentationService(
                context_factory,
                engine,
                intelligence_dashboard_presenter,
            )
        ),
        intelligence_dashboard_presenter=intelligence_dashboard_presenter,
    )


__all__ = [
    "DesktopApplicationDependencies",
    "build_desktop_application_dependencies",
]
