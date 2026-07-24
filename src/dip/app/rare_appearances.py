"""Application orchestration for Rare Appearances Intelligence."""

from typing import Protocol

from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult
from dip.marketplace_intelligence import MarketplaceSnapshot


class _MarketplaceHistoryQueries(Protocol):
    def all_snapshots(self) -> tuple[MarketplaceSnapshot, ...]: ...


class _IntelligenceEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class RareAppearancesExecutionConsistencyError(RuntimeError):
    """Raised when the dedicated engine violates the execution contract."""


class RareAppearancesExecutionService:
    """Load complete chronological history and execute the module once."""

    def __init__(self, history_queries: _MarketplaceHistoryQueries, engine: _IntelligenceEngine) -> None:
        self._history_queries = history_queries
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        history = self._history_queries.all_snapshots()
        if type(history) is not tuple or any(type(value) is not MarketplaceSnapshot for value in history):
            raise RareAppearancesExecutionConsistencyError("Marketplace History must return a tuple of snapshots.")
        execution = self._engine.execute(IntelligenceContext(marketplace_history=history))
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise RareAppearancesExecutionConsistencyError("Rare Appearances engine must return exactly one result.")
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "rare_appearances":
            raise RareAppearancesExecutionConsistencyError("Rare Appearances engine returned an unexpected result.")
        return result


__all__ = ["RareAppearancesExecutionConsistencyError", "RareAppearancesExecutionService"]
