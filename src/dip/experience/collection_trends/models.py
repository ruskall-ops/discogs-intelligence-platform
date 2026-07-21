"""Immutable presentation models for recent Collection Trends."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any


class CollectionTrendsConsistencyError(ValueError):
    """Raised when Collection Trends presentation values are contradictory."""


class CollectionTrendsState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INSUFFICIENT_HISTORY = "insufficient_history"


class CollectionTrendDirection(str, Enum):
    INCREASED = "increased"
    DECREASED = "decreased"
    UNCHANGED = "unchanged"
    NEWLY_AVAILABLE = "newly_available"
    NO_LONGER_AVAILABLE = "no_longer_available"
    INCOMPARABLE = "incomparable"


class CollectionTrendValueKind(str, Enum):
    COUNT = "count"
    SCORE = "score"


TrendNumber = int | float


@dataclass(frozen=True)
class CollectionTrendExecutionViewModel:
    run_id: int
    executed_at: datetime
    engine_version: str | None

    def __post_init__(self) -> None:
        _positive_integer(self.run_id, "run_id")
        if type(self.executed_at) is not datetime:
            raise TypeError("executed_at must be a datetime.")
        if self.engine_version is not None:
            _text(self.engine_version, "engine_version")


@dataclass(frozen=True)
class CollectionTrendMetricViewModel:
    metric_id: str
    label: str
    value_kind: CollectionTrendValueKind
    previous_value: TrendNumber | None
    latest_value: TrendNumber | None
    delta: TrendNumber | None
    direction: CollectionTrendDirection

    def __post_init__(self) -> None:
        _text(self.metric_id, "metric_id")
        _text(self.label, "label")
        if type(self.value_kind) is not CollectionTrendValueKind:
            raise TypeError("value_kind must be a CollectionTrendValueKind.")
        if type(self.direction) is not CollectionTrendDirection:
            raise TypeError("direction must be a CollectionTrendDirection.")
        previous = _number(self.previous_value, self.value_kind, "previous_value")
        latest = _number(self.latest_value, self.value_kind, "latest_value")
        delta = _delta(self.delta, self.value_kind)
        expected = _expected_direction(previous, latest, delta, self.direction)
        if self.direction is not expected:
            raise CollectionTrendsConsistencyError(
                "Metric direction is inconsistent with its typed values."
            )
        object.__setattr__(self, "previous_value", previous)
        object.__setattr__(self, "latest_value", latest)
        object.__setattr__(self, "delta", delta)


@dataclass(frozen=True)
class CollectionTrendsViewModel:
    state: CollectionTrendsState
    summary: str
    previous_execution: CollectionTrendExecutionViewModel | None = None
    latest_execution: CollectionTrendExecutionViewModel | None = None
    metrics: tuple[CollectionTrendMetricViewModel, ...] = ()
    messages: tuple[str, ...] = ()
    title: str = field(init=False, default="Collection Trends")

    def __post_init__(self) -> None:
        if type(self.state) is not CollectionTrendsState:
            raise TypeError("state must be a CollectionTrendsState.")
        _text(self.summary, "summary")
        metrics = _freeze_metrics(self.metrics)
        messages = _freeze_text(self.messages, "messages")
        previous = self.previous_execution
        latest = self.latest_execution
        if previous is not None and type(previous) is not CollectionTrendExecutionViewModel:
            raise TypeError("previous_execution has an unsupported type.")
        if latest is not None and type(latest) is not CollectionTrendExecutionViewModel:
            raise TypeError("latest_execution has an unsupported type.")
        if previous is not None and latest is not None:
            if previous.run_id == latest.run_id:
                raise CollectionTrendsConsistencyError(
                    "Compared Trends executions must have distinct run IDs."
                )
            if _execution_key(latest) <= _execution_key(previous):
                raise CollectionTrendsConsistencyError(
                    "The latest Trends execution must follow the previous execution."
                )

        if self.state in {CollectionTrendsState.AVAILABLE, CollectionTrendsState.PARTIAL}:
            if previous is None or latest is None or not metrics:
                raise CollectionTrendsConsistencyError(
                    "Comparable Trends require two executions and metrics."
                )
            partial = any(
                metric.direction in {
                    CollectionTrendDirection.NEWLY_AVAILABLE,
                    CollectionTrendDirection.NO_LONGER_AVAILABLE,
                    CollectionTrendDirection.INCOMPARABLE,
                }
                for metric in metrics
            )
            if partial != (self.state is CollectionTrendsState.PARTIAL):
                raise CollectionTrendsConsistencyError(
                    "Partial Trends state does not match metric availability."
                )
        elif self.state is CollectionTrendsState.INSUFFICIENT_HISTORY:
            if previous is not None or latest is None or metrics:
                raise CollectionTrendsConsistencyError(
                    "Insufficient history requires exactly one execution."
                )
        elif self.state is CollectionTrendsState.EMPTY:
            if metrics:
                raise CollectionTrendsConsistencyError(
                    "Empty Trends cannot contain metrics."
                )
        elif previous is not None or latest is not None or metrics:
            raise CollectionTrendsConsistencyError(
                "This Trends state cannot contain execution values."
            )
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "messages", messages)

    @classmethod
    def loading(cls) -> "CollectionTrendsViewModel":
        return cls(CollectionTrendsState.LOADING, "Collection Trends are loading.")

    @classmethod
    def unavailable(cls) -> "CollectionTrendsViewModel":
        return cls(
            CollectionTrendsState.UNAVAILABLE,
            "No Intelligence History is available for Collection Trends.",
        )


def _freeze_metrics(values: Any) -> tuple[CollectionTrendMetricViewModel, ...]:
    try:
        metrics = tuple(values)
    except TypeError as exc:
        raise TypeError("metrics must be a collection.") from exc
    if any(type(value) is not CollectionTrendMetricViewModel for value in metrics):
        raise TypeError("metrics contain an unsupported value.")
    identifiers = tuple(metric.metric_id for metric in metrics)
    if len(set(identifiers)) != len(identifiers):
        raise CollectionTrendsConsistencyError("Trend metric IDs must be unique.")
    canonical = tuple(metric_id for metric_id in _METRIC_ORDER if metric_id in identifiers)
    if identifiers != canonical:
        raise CollectionTrendsConsistencyError("Trend metrics must use canonical order.")
    return metrics


_METRIC_ORDER = (
    "collection_size",
    "collection_health.overall_score",
    "collection_health.metadata_completeness",
    "collection_health.marketplace_coverage",
    "collection_health.demand_strength",
    "collection_health.valuation_coverage",
    "hidden_gems.candidate_count",
    "completed_module_count",
)


def _expected_direction(previous, latest, delta, supplied):
    if supplied is CollectionTrendDirection.INCOMPARABLE:
        if delta is not None:
            raise CollectionTrendsConsistencyError("Incomparable metrics cannot have a delta.")
        return supplied
    if previous is None and latest is None:
        if delta is not None:
            raise CollectionTrendsConsistencyError("Unavailable metrics cannot have a delta.")
        expected = CollectionTrendDirection.INCOMPARABLE
    elif previous is None:
        expected = CollectionTrendDirection.NEWLY_AVAILABLE
    elif latest is None:
        expected = CollectionTrendDirection.NO_LONGER_AVAILABLE
    else:
        expected_delta = latest - previous
        if delta != expected_delta:
            raise CollectionTrendsConsistencyError("Metric delta is inconsistent.")
        expected = (
            CollectionTrendDirection.INCREASED
            if delta > 0
            else CollectionTrendDirection.DECREASED
            if delta < 0
            else CollectionTrendDirection.UNCHANGED
        )
    if expected in {
        CollectionTrendDirection.NEWLY_AVAILABLE,
        CollectionTrendDirection.NO_LONGER_AVAILABLE,
    } and delta is not None:
        raise CollectionTrendsConsistencyError("Unavailable metric sides cannot have a delta.")
    return expected


def _number(value, kind, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or None.")
    if kind is CollectionTrendValueKind.COUNT:
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer count.")
        return value
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 100:
        raise ValueError(f"{name} must be a score from 0 to 100.")
    return number


def _delta(value, kind):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("delta must be numeric or None.")
    if kind is CollectionTrendValueKind.COUNT and type(value) is not int:
        raise TypeError("A count delta must be an integer.")
    number = value if kind is CollectionTrendValueKind.COUNT else float(value)
    if isinstance(number, float) and not math.isfinite(number):
        raise ValueError("delta must be finite.")
    return number


def _execution_key(value):
    timestamp = value.executed_at
    normalized = (
        timestamp.replace(tzinfo=timezone.utc)
        if timestamp.tzinfo is None
        else timestamp.astimezone(timezone.utc)
    )
    return normalized, value.run_id


def _freeze_text(values, name):
    if isinstance(values, str):
        raise TypeError(f"{name} must be a collection of strings.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    for value in result:
        _text(value, f"{name} item")
    return result


def _positive_integer(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _text(value, name):
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed.")


__all__ = [
    "CollectionTrendDirection",
    "CollectionTrendExecutionViewModel",
    "CollectionTrendMetricViewModel",
    "CollectionTrendValueKind",
    "CollectionTrendsConsistencyError",
    "CollectionTrendsState",
    "CollectionTrendsViewModel",
]
