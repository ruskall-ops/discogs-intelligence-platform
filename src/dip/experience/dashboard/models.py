"""Presentation-neutral, read-only dashboard view models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DashboardCardState(str, Enum):
    """States a presentation layer can render without domain knowledge."""

    READY = "ready"
    SKIPPED = "skipped"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_HISTORY = "insufficient_history"


@dataclass(frozen=True)
class DashboardComponentScore:
    """One named score already calculated by an intelligence module."""

    key: str
    label: str
    score: float


@dataclass(frozen=True)
class DashboardCardViewModel:
    """Generic intelligence card data for desktop or future interfaces."""

    module_id: str
    title: str
    state: DashboardCardState
    headline_label: str
    headline_score: float | None
    summary: str
    components: tuple[DashboardComponentScore, ...] = ()
    strengths: tuple[str, ...] = ()
    improvement_opportunities: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class DashboardReleaseViewModel:
    """A release prepared for display without internal scoring models."""

    release_id: int
    artist: str
    title: str
    explanation: str = ""
    change: str = ""


@dataclass(frozen=True)
class HiddenGemsCardViewModel:
    """Presentation-only Hidden Gems card."""

    module_id: str
    title: str
    state: DashboardCardState
    total_hidden_gems: int | None
    summary: str
    top_gems: tuple[DashboardReleaseViewModel, ...] = ()
    explainability_summary: str = ""
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalIntelligenceCardViewModel:
    """Presentation-only latest-versus-previous history card."""

    module_id: str
    title: str
    state: DashboardCardState
    summary: str
    latest_snapshot_date: str | None = None
    previous_snapshot_date: str | None = None
    releases_added: int | None = None
    releases_removed: int | None = None
    collection_size_change: int | None = None
    collection_value_change: str | None = None
    average_value_change: str | None = None
    median_value_change: str | None = None
    top_gainers: tuple[DashboardReleaseViewModel, ...] = ()
    top_decliners: tuple[DashboardReleaseViewModel, ...] = ()
    evidence_coverage_summary: str = ""
    diagnostics: tuple[str, ...] = ()


DashboardIntelligenceCard = (
    DashboardCardViewModel
    | HiddenGemsCardViewModel
    | HistoricalIntelligenceCardViewModel
)


@dataclass(frozen=True)
class IntelligenceDashboardViewModel:
    """Read-only collection of intelligence cards for a dashboard."""

    cards: tuple[DashboardIntelligenceCard, ...] = ()

    def card_for(self, module_id: str) -> DashboardIntelligenceCard | None:
        return next(
            (
                card
                for card in self.cards
                if card.module_id == module_id
            ),
            None,
        )
