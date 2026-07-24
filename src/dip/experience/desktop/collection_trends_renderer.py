"""Desktop-neutral rendering for recent Collection Trends."""

from __future__ import annotations

from dataclasses import dataclass

from dip.experience.collection_trends import (
    CollectionTrendDirection,
    CollectionTrendMetricViewModel,
    CollectionTrendValueKind,
    CollectionTrendsState,
    CollectionTrendsViewModel,
)


@dataclass(frozen=True)
class DesktopCollectionTrendMetric:
    metric_id: str
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopCollectionTrendsView:
    title: str
    state: CollectionTrendsState
    headline: str
    comparison: str
    metrics: tuple[DesktopCollectionTrendMetric, ...] = ()
    messages: str = ""


class DesktopCollectionTrendsRenderer:
    """Format typed Trends without querying or comparing values."""

    def render(self, trends: CollectionTrendsViewModel) -> DesktopCollectionTrendsView:
        if type(trends) is not CollectionTrendsViewModel:
            raise TypeError("trends must be a CollectionTrendsViewModel.")
        comparison = ""
        if trends.latest_execution is not None:
            comparison = (
                _date(trends.latest_execution.executed_at)
                if trends.previous_execution is None
                else (
                    f"{_date(trends.previous_execution.executed_at)} → "
                    f"{_date(trends.latest_execution.executed_at)}"
                )
            )
        return DesktopCollectionTrendsView(
            title=trends.title,
            state=trends.state,
            headline=_headline(trends),
            comparison=comparison,
            metrics=tuple(_metric(metric) for metric in trends.metrics),
            messages="\n".join(f"• {message}" for message in trends.messages),
        )


def _metric(metric: CollectionTrendMetricViewModel) -> DesktopCollectionTrendMetric:
    previous = _value(metric.previous_value, metric.value_kind)
    latest = _value(metric.latest_value, metric.value_kind)
    change = (
        "Unavailable"
        if metric.delta is None
        else _signed(metric.delta, metric.value_kind)
    )
    direction = metric.direction.value.replace("_", " ").title()
    return DesktopCollectionTrendMetric(
        metric.metric_id,
        metric.label,
        f"{previous} → {latest}\nChange: {change}\nDirection: {direction}",
    )


def _headline(trends: CollectionTrendsViewModel) -> str:
    labels = {
        CollectionTrendsState.LOADING: "Loading",
        CollectionTrendsState.AVAILABLE: "Latest comparison available",
        CollectionTrendsState.PARTIAL: "Latest comparison partially available",
        CollectionTrendsState.EMPTY: "No trendable metrics",
        CollectionTrendsState.UNAVAILABLE: "No intelligence history",
        CollectionTrendsState.ERROR: "Unable to display Collection Trends",
        CollectionTrendsState.INSUFFICIENT_HISTORY: "Insufficient history",
    }
    return f"{labels[trends.state]}\n{trends.summary}"


def _value(value, kind):
    if value is None:
        return "Unavailable"
    return f"{value:,}" if kind is CollectionTrendValueKind.COUNT else f"{value:.1f}/100"


def _signed(value, kind):
    return f"{value:+,}" if kind is CollectionTrendValueKind.COUNT else f"{value:+.1f}"


def _date(value):
    return value.strftime("%d %b %Y %H:%M")


__all__ = [
    "DesktopCollectionTrendMetric",
    "DesktopCollectionTrendsRenderer",
    "DesktopCollectionTrendsView",
]
