from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class ReportMover:
    """One release highlighted within a report."""

    release_id: int
    artist: str
    title: str

    wants_change: int | None
    copies_for_sale_change: int | None
    lowest_price_change: Decimal | None
    lowest_price_percent_change: Decimal | None


@dataclass(frozen=True)
class CollectionSummary:
    """High-level collection statistics."""

    unique_releases: int
    owned_copies: int
    high_priority: int
    worth_reviewing: int
    hot_now: int
    protected: int


@dataclass(frozen=True)
class AnalysisRunSummary:
    """Summary of the latest marketplace analysis run."""

    run_id: int
    status: str
    started_at: str
    completed_at: str | None
    releases_attempted: int
    releases_succeeded: int
    releases_failed: int


@dataclass(frozen=True)
class HistoricalSummary:
    """Summary of changes between two completed analysis runs."""

    latest_run_id: int
    previous_run_id: int
    total_comparisons: int
    changed: int
    unchanged: int
    new: int
    missing: int
    percent_changed: float


@dataclass(frozen=True)
class IntelligenceReport:
    """Structured report data independent of output format."""

    title: str
    generated_at: datetime
    collection: CollectionSummary
    latest_run: AnalysisRunSummary | None
    historical: HistoricalSummary | None
    top_price_movers: list[ReportMover]
    top_demand_movers: list[ReportMover]
    top_scarcity_movers: list[ReportMover]