"""Build recent Collection Trends from an established execution comparison."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dip.app.intelligence_history import HistoricalIntelligenceExecution
from dip.comparison import ExecutionComparison, ModuleComparison
from dip.intelligence import IntelligenceStatus

from .models import (
    CollectionTrendDirection,
    CollectionTrendExecutionViewModel,
    CollectionTrendMetricViewModel,
    CollectionTrendValueKind,
    CollectionTrendsConsistencyError,
    CollectionTrendsState,
    CollectionTrendsViewModel,
)


_MISSING = object()
_INVALID = object()
_COMPONENTS = (
    ("metadata_completeness", "Metadata completeness"),
    ("marketplace_coverage", "Marketplace coverage"),
    ("demand_strength", "Demand strength"),
    ("valuation_coverage", "Valuation coverage"),
)


class CollectionTrendsViewModelBuilder:
    """Project aligned historical metrics into neutral typed changes."""

    def build(
        self,
        executions: tuple[HistoricalIntelligenceExecution, ...],
        comparison: ExecutionComparison | None,
        *,
        history_exists: bool,
    ) -> CollectionTrendsViewModel:
        if type(executions) is not tuple or any(
            type(item) is not HistoricalIntelligenceExecution for item in executions
        ):
            raise TypeError("executions must be an immutable tuple of executions.")
        if len(executions) > 2:
            raise CollectionTrendsConsistencyError(
                "Collection Trends compares at most two executions."
            )
        if not executions:
            return (
                CollectionTrendsViewModel(
                    CollectionTrendsState.EMPTY,
                    "History exists but contains no comparable collection metrics.",
                )
                if history_exists
                else CollectionTrendsViewModel.unavailable()
            )
        latest = self._execution(executions[0])
        if len(executions) == 1:
            return CollectionTrendsViewModel(
                CollectionTrendsState.INSUFFICIENT_HISTORY,
                "At least two comparable executions are required for Collection Trends.",
                latest_execution=latest,
            )
        if type(comparison) is not ExecutionComparison:
            raise TypeError("Two Trends executions require an ExecutionComparison.")
        current, previous = executions
        if (
            comparison.current_run != current.run
            or comparison.previous_run != previous.run
        ):
            raise CollectionTrendsConsistencyError(
                "The comparison does not match the selected Trends executions."
            )

        by_module = {module.module_id: module for module in comparison.modules}
        metrics: list[CollectionTrendMetricViewModel] = []
        self._append(
            metrics,
            "collection_size",
            "Collection size",
            CollectionTrendValueKind.COUNT,
            self._collection_size(by_module, "previous"),
            self._collection_size(by_module, "current"),
        )
        health = by_module.get("collection_health")
        self._append(
            metrics,
            "collection_health.overall_score",
            "Collection Health",
            CollectionTrendValueKind.SCORE,
            self._value(health, "previous", ("overall_health_score",)),
            self._value(health, "current", ("overall_health_score",)),
        )
        for component_id, label in _COMPONENTS:
            self._append(
                metrics,
                f"collection_health.{component_id}",
                label,
                CollectionTrendValueKind.SCORE,
                self._value(
                    health,
                    "previous",
                    ("component_scores", component_id),
                ),
                self._value(
                    health,
                    "current",
                    ("component_scores", component_id),
                ),
            )
        gems = by_module.get("hidden_gems")
        self._append(
            metrics,
            "hidden_gems.candidate_count",
            "Hidden Gems",
            CollectionTrendValueKind.COUNT,
            self._value(gems, "previous", ("candidate_count",)),
            self._value(gems, "current", ("candidate_count",)),
        )
        self._append(
            metrics,
            "completed_module_count",
            "Completed modules",
            CollectionTrendValueKind.COUNT,
            self._completed(previous),
            self._completed(current),
        )

        if not metrics:
            return CollectionTrendsViewModel(
                CollectionTrendsState.EMPTY,
                "The selected executions contain no trendable collection metrics.",
                previous_execution=self._execution(previous),
                latest_execution=latest,
            )
        partial = any(
            metric.direction in {
                CollectionTrendDirection.NEWLY_AVAILABLE,
                CollectionTrendDirection.NO_LONGER_AVAILABLE,
                CollectionTrendDirection.INCOMPARABLE,
            }
            for metric in metrics
        )
        return CollectionTrendsViewModel(
            CollectionTrendsState.PARTIAL if partial else CollectionTrendsState.AVAILABLE,
            "Neutral changes between the two latest comparable intelligence executions.",
            previous_execution=self._execution(previous),
            latest_execution=latest,
            metrics=tuple(metrics),
        )

    @staticmethod
    def _execution(execution):
        return CollectionTrendExecutionViewModel(
            execution.run.run_id,
            execution.run.executed_at,
            execution.run.engine_version,
        )

    @staticmethod
    def _completed(execution):
        return sum(record.status is IntelligenceStatus.COMPLETED for record in execution.records)

    def _collection_size(self, modules, side):
        for module_id in ("collection_health", "hidden_gems"):
            value = self._value(modules.get(module_id), side, ("collection_release_count",))
            if value is not _MISSING and value is not None:
                return value
        return _MISSING

    @staticmethod
    def _value(module: ModuleComparison | None, side: str, path: tuple[str, ...]):
        if module is None:
            return _MISSING
        value = getattr(module.metrics, side)
        if value is None:
            return _MISSING
        if not isinstance(value, Mapping):
            return _INVALID
        current: Any = value
        for key in path:
            if not isinstance(current, Mapping):
                return _INVALID
            if key not in current:
                return _MISSING
            current = current[key]
        return current

    @staticmethod
    def _append(metrics, metric_id, label, kind, previous, latest):
        if (previous is _MISSING or previous is None) and (
            latest is _MISSING or latest is None
        ):
            return
        previous_value = _typed(previous, kind)
        latest_value = _typed(latest, kind)
        if (
            previous is _INVALID
            or latest is _INVALID
            or (
                previous is not _MISSING
                and previous is not None
                and previous_value is None
            )
            or (
                latest is not _MISSING
                and latest is not None
                and latest_value is None
            )
        ):
            direction = CollectionTrendDirection.INCOMPARABLE
            delta = None
        elif previous_value is None:
            direction = CollectionTrendDirection.NEWLY_AVAILABLE
            delta = None
        elif latest_value is None:
            direction = CollectionTrendDirection.NO_LONGER_AVAILABLE
            delta = None
        else:
            delta = latest_value - previous_value
            direction = (
                CollectionTrendDirection.INCREASED
                if delta > 0
                else CollectionTrendDirection.DECREASED
                if delta < 0
                else CollectionTrendDirection.UNCHANGED
            )
        metrics.append(
            CollectionTrendMetricViewModel(
                metric_id,
                label,
                kind,
                previous_value,
                latest_value,
                delta,
                direction,
            )
        )


def _typed(value, kind):
    if value is _MISSING or value is _INVALID or isinstance(value, bool):
        return None
    if kind is CollectionTrendValueKind.COUNT:
        return value if type(value) is int and value >= 0 else None
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if 0 <= number <= 100 else None


__all__ = ["CollectionTrendsViewModelBuilder"]
