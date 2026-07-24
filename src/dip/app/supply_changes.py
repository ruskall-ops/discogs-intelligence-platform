"""Application orchestration for Supply Changes Intelligence."""

from __future__ import annotations

from typing import Protocol

from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult
from dip.marketplace_intelligence import MarketplaceSnapshot, MarketplaceSnapshotComparisonInput


class _MarketplaceHistoryQueries(Protocol):
    def recent_snapshots(self, limit: int) -> tuple[MarketplaceSnapshot, ...]: ...


class _IntelligenceEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class SupplyChangesExecutionConsistencyError(RuntimeError):
    """Raised when the dedicated engine violates the execution contract."""


class SupplyChangesExecutionService:
    """Load the newest snapshot pair and execute Supply Changes once."""

    def __init__(self, history_queries: _MarketplaceHistoryQueries, engine: _IntelligenceEngine) -> None:
        self._history_queries = history_queries
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        snapshots = self._history_queries.recent_snapshots(2)
        comparison = MarketplaceSnapshotComparisonInput(
            previous_snapshot=snapshots[1] if len(snapshots) > 1 else None,
            latest_snapshot=snapshots[0] if snapshots else None,
        )
        execution = self._engine.execute(IntelligenceContext(marketplace_comparison=comparison))
        if type(execution) is not IntelligenceExecution:
            raise SupplyChangesExecutionConsistencyError("Supply Changes engine must return an IntelligenceExecution.")
        if len(execution.results) != 1:
            raise SupplyChangesExecutionConsistencyError("Supply Changes engine must return exactly one result.")
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "supply_changes":
            raise SupplyChangesExecutionConsistencyError("Supply Changes engine returned an unexpected result.")
        return result


__all__ = ["SupplyChangesExecutionConsistencyError", "SupplyChangesExecutionService"]
