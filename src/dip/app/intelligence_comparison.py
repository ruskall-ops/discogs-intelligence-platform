"""Application orchestration for comparing historical Intelligence executions."""

from __future__ import annotations

from typing import Protocol

from dip.comparison import ExecutionComparison

from .intelligence_history import HistoricalIntelligenceExecution


class _HistoricalIntelligenceQueries(Protocol):
    def recent_executions(
        self,
        limit: int,
    ) -> tuple[HistoricalIntelligenceExecution, ...]: ...

    def execution(
        self,
        run_id: int,
    ) -> HistoricalIntelligenceExecution | None: ...


class _ComparisonEngine(Protocol):
    def compare(
        self,
        current: HistoricalIntelligenceExecution,
        previous: HistoricalIntelligenceExecution,
    ) -> ExecutionComparison: ...


class ComparisonHistoryUnavailableError(RuntimeError):
    """Raised when history cannot supply both sides of a comparison."""


class HistoricalExecutionNotFoundError(LookupError):
    """Raised when a requested persisted execution does not exist."""

    def __init__(self, run_id: int) -> None:
        self.run_id = run_id
        super().__init__(f"Intelligence History run {run_id} does not exist.")


class IntelligenceComparisonService:
    """Load historical executions and delegate deterministic comparison."""

    def __init__(
        self,
        history_queries: _HistoricalIntelligenceQueries,
        comparison_engine: _ComparisonEngine,
    ) -> None:
        self._history_queries = history_queries
        self._comparison_engine = comparison_engine

    def compare_latest(self) -> ExecutionComparison:
        """Compare the latest execution with its immediate predecessor."""

        recent = self._history_queries.recent_executions(2)
        if not recent:
            raise ComparisonHistoryUnavailableError(
                "At least two historical executions are required; history is empty."
            )
        if len(recent) < 2:
            raise ComparisonHistoryUnavailableError(
                "At least two historical executions are required."
            )
        current, previous = recent
        return self.compare(current, previous)

    def compare(
        self,
        current: HistoricalIntelligenceExecution,
        previous: HistoricalIntelligenceExecution,
    ) -> ExecutionComparison:
        """Compare two supplied executions, treating the first as current."""

        return self._comparison_engine.compare(current, previous)

    def compare_by_run_ids(
        self,
        current_run_id: int,
        previous_run_id: int,
    ) -> ExecutionComparison:
        """Load and compare two distinct persisted execution identifiers."""

        _validate_run_id(current_run_id, "current_run_id")
        _validate_run_id(previous_run_id, "previous_run_id")
        if current_run_id == previous_run_id:
            raise ValueError("Cannot compare an Intelligence History run with itself.")

        current = self._history_queries.execution(current_run_id)
        if current is None:
            raise HistoricalExecutionNotFoundError(current_run_id)
        previous = self._history_queries.execution(previous_run_id)
        if previous is None:
            raise HistoricalExecutionNotFoundError(previous_run_id)
        return self.compare(current, previous)


def _validate_run_id(run_id: object, name: str) -> None:
    if type(run_id) is not int:
        raise TypeError(f"{name} must be an integer.")
    if run_id <= 0:
        raise ValueError(f"{name} must be a positive integer.")


__all__ = [
    "ComparisonHistoryUnavailableError",
    "HistoricalExecutionNotFoundError",
    "IntelligenceComparisonService",
]
