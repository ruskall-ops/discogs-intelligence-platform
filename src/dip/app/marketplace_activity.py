"""Application orchestration for composite Marketplace Activity."""

from typing import Protocol

from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult


class _ResultExecution(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _ActivityEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class MarketplaceActivityExecutionConsistencyError(RuntimeError):
    """Raised when a coordinated source or dedicated engine violates its contract."""


_REQUIRED_SOURCE_IDENTITIES = (
    ("price_changes", "2.0"),
    ("supply_changes", "2.0"),
    ("rare_appearances", "1.0"),
)


class MarketplaceActivityExecutionService:
    """Coordinate existing source intelligence and execute the composite once."""

    def __init__(self, price_changes: _ResultExecution, supply_changes: _ResultExecution, rare_appearances: _ResultExecution, engine: _ActivityEngine, weekend_listings: _ResultExecution | None = None) -> None:
        self._price_changes = price_changes
        self._supply_changes = supply_changes
        self._rare_appearances = rare_appearances
        self._weekend_listings = weekend_listings
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        results = [self._price_changes.execute(), self._supply_changes.execute(), self._rare_appearances.execute()]
        if self._weekend_listings is not None:
            results.append(self._weekend_listings.execute())
        if any(type(value) is not IntelligenceResult for value in results):
            raise MarketplaceActivityExecutionConsistencyError("Marketplace Activity sources must return IntelligenceResult values.")
        if tuple(
            (value.module_id, value.module_version) for value in results[:3]
        ) != _REQUIRED_SOURCE_IDENTITIES:
            raise MarketplaceActivityExecutionConsistencyError(
                "Marketplace Activity received an incompatible required source result."
            )
        if len({value.module_id for value in results}) != len(results):
            raise MarketplaceActivityExecutionConsistencyError("Marketplace Activity received duplicate source outputs.")
        if len(results) == 4 and (
            results[3].module_id,
            results[3].module_version,
        ) != ("weekend_listings", "1.0"):
            raise MarketplaceActivityExecutionConsistencyError("Optional Marketplace Activity source must be Weekend Listings.")
        execution = self._engine.execute(IntelligenceContext(marketplace_activity_sources=tuple(results)))
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise MarketplaceActivityExecutionConsistencyError("Marketplace Activity engine must return exactly one result.")
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "marketplace_activity":
            raise MarketplaceActivityExecutionConsistencyError("Marketplace Activity engine returned an unexpected result.")
        return result


__all__ = ["MarketplaceActivityExecutionConsistencyError", "MarketplaceActivityExecutionService"]
