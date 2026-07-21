"""Application coordination for the latest Collection Trends comparison."""

from __future__ import annotations

from typing import Protocol

from dip.app.intelligence_history import HistoricalIntelligenceExecution
from dip.comparison import ExecutionComparison
from dip.experience.collection_trends import CollectionTrendsViewModel
from dip.intelligence import IntelligenceStatus


class _HistoryQueries(Protocol):
    def recent_executions(
        self,
        limit: int,
    ) -> tuple[HistoricalIntelligenceExecution, ...]: ...


class _ComparisonService(Protocol):
    def compare(
        self,
        current: HistoricalIntelligenceExecution,
        previous: HistoricalIntelligenceExecution,
    ) -> ExecutionComparison: ...


class _TrendsBuilder(Protocol):
    def build(
        self,
        executions: tuple[HistoricalIntelligenceExecution, ...],
        comparison: ExecutionComparison | None,
        *,
        history_exists: bool,
    ) -> CollectionTrendsViewModel: ...


class CollectionTrendsPresentationService:
    """Query once and compare the newest two comparable recent executions."""

    candidate_window = 5

    def __init__(
        self,
        history_queries: _HistoryQueries,
        comparison_service: _ComparisonService,
        builder: _TrendsBuilder,
    ) -> None:
        self._history_queries = history_queries
        self._comparison_service = comparison_service
        self._builder = builder

    def latest_trends(self) -> CollectionTrendsViewModel:
        """Build Trends from at most two executions selected from one query."""

        recent = self._history_queries.recent_executions(self.candidate_window)
        if type(recent) is not tuple:
            raise TypeError("recent_executions must return an immutable tuple.")
        comparable = tuple(
            execution for execution in recent if _is_comparable(execution)
        )[:2]
        comparison = (
            self._comparison_service.compare(comparable[0], comparable[1])
            if len(comparable) == 2
            else None
        )
        return self._builder.build(
            comparable,
            comparison,
            history_exists=bool(recent),
        )


def _is_comparable(execution: HistoricalIntelligenceExecution) -> bool:
    if type(execution) is not HistoricalIntelligenceExecution:
        raise TypeError("History contains an unsupported execution value.")
    return any(
        record.status in {IntelligenceStatus.COMPLETED, IntelligenceStatus.SKIPPED}
        for record in execution.records
    )


__all__ = ["CollectionTrendsPresentationService"]
