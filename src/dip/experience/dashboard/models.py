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
class IntelligenceDashboardViewModel:
    """Read-only collection of intelligence cards for a dashboard."""

    cards: tuple[DashboardCardViewModel, ...] = ()

    def card_for(self, module_id: str) -> DashboardCardViewModel | None:
        return next(
            (
                card
                for card in self.cards
                if card.module_id == module_id
            ),
            None,
        )
