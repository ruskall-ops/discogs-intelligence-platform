"""Application orchestration for Price Changes Intelligence."""

from __future__ import annotations

from typing import Protocol

from dip.intelligence import (
    IntelligenceContext,
    IntelligenceExecution,
    IntelligenceResult,
)
from dip.marketplace_intelligence import (
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
)


class _MarketplaceHistoryQueries(Protocol):
    def recent_snapshots(
        self,
        limit: int,
    ) -> tuple[MarketplaceSnapshot, ...]: ...


class _IntelligenceEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class PriceChangesExecutionConsistencyError(RuntimeError):
    """Raised when the dedicated engine violates the execution contract."""


class PriceChangesExecutionService:
    """Load the newest snapshot pair and execute Price Changes once."""

    def __init__(
        self,
        history_queries: _MarketplaceHistoryQueries,
        engine: _IntelligenceEngine,
    ) -> None:
        self._history_queries = history_queries
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        """Return the single Price Changes result for bounded recent history."""

        snapshots = self._history_queries.recent_snapshots(2)
        comparison = MarketplaceSnapshotComparisonInput(
            previous_snapshot=snapshots[1] if len(snapshots) > 1 else None,
            latest_snapshot=snapshots[0] if snapshots else None,
        )
        execution = self._engine.execute(
            IntelligenceContext(marketplace_comparison=comparison)
        )
        return _price_changes_result(execution)


def _price_changes_result(execution: object) -> IntelligenceResult:
    if type(execution) is not IntelligenceExecution:
        raise PriceChangesExecutionConsistencyError(
            "Price Changes engine must return an IntelligenceExecution."
        )
    if len(execution.results) != 1:
        raise PriceChangesExecutionConsistencyError(
            "Price Changes engine must return exactly one result."
        )

    result = execution.results[0]
    if type(result) is not IntelligenceResult:
        raise PriceChangesExecutionConsistencyError(
            "Price Changes engine returned a value that is not an IntelligenceResult."
        )
    if result.module_id != "price_changes":
        raise PriceChangesExecutionConsistencyError(
            f"Price Changes engine returned module {result.module_id!r}."
        )
    return result


__all__ = [
    "PriceChangesExecutionConsistencyError",
    "PriceChangesExecutionService",
]
