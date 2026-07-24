"""Explicit application execution boundary for Trend Analysis."""

from dip.intelligence import IntelligenceExecution, IntelligenceResult


class IntelligenceTrendAnalysisExecutionService:
    def __init__(self, engine):
        self._engine = engine

    def execute(self, ordered_change_results):
        supplied = tuple(ordered_change_results)
        execution = self._engine.execute(supplied)
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise RuntimeError("Trend Analysis engine must return exactly one result.")
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "intelligence_trend_analysis":
            raise RuntimeError("Trend Analysis engine returned an unexpected result.")
        return result


__all__ = ["IntelligenceTrendAnalysisExecutionService"]
