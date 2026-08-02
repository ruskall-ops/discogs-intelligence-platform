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
from dip.app.marketplace_change_workspace import MarketplaceSnapshotWindowSelector


class _MarketplaceHistoryQueries(Protocol):
    def all_snapshots(self) -> tuple[MarketplaceSnapshot, ...]: ...


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
        selector: MarketplaceSnapshotWindowSelector | None = None,
    ) -> None:
        self._history_queries = history_queries
        self._engine = engine
        self._selector = selector or MarketplaceSnapshotWindowSelector()

    def execute(self) -> IntelligenceResult:
        """Return the single Price Changes result for bounded recent history."""

        selected = self._selector._select(self._history_queries.all_snapshots())
        comparison = MarketplaceSnapshotComparisonInput(
            previous_snapshot=selected.baseline,
            latest_snapshot=selected.current,
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
    if result.module_id != "price_changes" or result.module_version != "2.0":
        raise PriceChangesExecutionConsistencyError(
            "Price Changes engine returned an incompatible module identity."
        )
    return result


__all__ = [
    "PriceChangesExecutionConsistencyError",
    "PriceChangesExecutionService",
]
