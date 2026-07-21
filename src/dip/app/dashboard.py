"""Application coordination for the read-only Dashboard homepage."""

from __future__ import annotations

from typing import Protocol

from dip.experience.comparison import ExecutionComparisonViewModel
from dip.experience.dashboard.homepage_models import (
    DashboardHomepageViewModel,
    DashboardSectionState,
)
from dip.experience.dashboard.models import IntelligenceDashboardViewModel
from dip.intelligence import IntelligenceContext, IntelligenceExecution

from .intelligence_comparison import ComparisonHistoryUnavailableError
from .intelligence_history import HistoricalIntelligenceExecution


class _HistoryQueries(Protocol):
    def latest_execution(self) -> HistoricalIntelligenceExecution | None: ...


class _ComparisonPresentation(Protocol):
    def latest_view_model(self) -> ExecutionComparisonViewModel: ...


class _DashboardHomepageBuilder(Protocol):
    def build(
        self,
        latest_execution: HistoricalIntelligenceExecution | None,
        comparison: ExecutionComparisonViewModel | None = None,
        *,
        comparison_state: DashboardSectionState = (
            DashboardSectionState.INSUFFICIENT_HISTORY
        ),
    ) -> DashboardHomepageViewModel: ...


class _IntelligenceContextFactory(Protocol):
    def build(self) -> IntelligenceContext: ...


class _IntelligenceEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class _IntelligenceDashboardPresenter(Protocol):
    def present(
        self,
        intelligence: IntelligenceExecution,
    ) -> IntelligenceDashboardViewModel: ...


class CollectionIntelligencePresentationService:
    """Request current Collection Intelligence for existing presentation clients."""

    def __init__(
        self,
        context_factory: _IntelligenceContextFactory,
        engine: _IntelligenceEngine,
        presenter: _IntelligenceDashboardPresenter,
    ) -> None:
        self._context_factory = context_factory
        self._engine = engine
        self._presenter = presenter

    def dashboard(self) -> IntelligenceDashboardViewModel:
        """Return the established current-intelligence Dashboard model."""

        context = self._context_factory.build()
        execution = self._engine.execute(context)
        return self._presenter.present(execution)


class DashboardHomepageService:
    """Coordinate existing history and comparison presentation abstractions."""

    def __init__(
        self,
        history_queries: _HistoryQueries,
        comparison_presentation: _ComparisonPresentation,
        view_model_builder: _DashboardHomepageBuilder,
    ) -> None:
        self._history_queries = history_queries
        self._comparison_presentation = comparison_presentation
        self._view_model_builder = view_model_builder

    def homepage(self) -> DashboardHomepageViewModel:
        """Return the latest homepage without accessing persistence directly."""

        latest = self._history_queries.latest_execution()
        if latest is None:
            return self._view_model_builder.build(
                None,
                comparison_state=DashboardSectionState.INSUFFICIENT_HISTORY,
            )

        try:
            comparison = self._comparison_presentation.latest_view_model()
        except ComparisonHistoryUnavailableError:
            return self._view_model_builder.build(
                latest,
                comparison_state=DashboardSectionState.INSUFFICIENT_HISTORY,
            )

        return self._view_model_builder.build(latest, comparison)


__all__ = [
    "CollectionIntelligencePresentationService",
    "DashboardHomepageService",
]
