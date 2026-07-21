"""Tkinter-neutral text rendering for desktop intelligence cards."""

from __future__ import annotations

from dataclasses import dataclass

from dip.experience.dashboard import (
    DashboardCardState,
    DashboardCardViewModel,
    HiddenGemsCardViewModel,
    HistoricalIntelligenceCardViewModel,
    IntelligenceDashboardViewModel,
)


@dataclass(frozen=True)
class DesktopDashboardCard:
    module_id: str
    title: str
    body: str


class DesktopDashboardRenderer:
    """Format dashboard view models without reading domain models or storage."""

    def render(
        self,
        dashboard: IntelligenceDashboardViewModel,
    ) -> tuple[DesktopDashboardCard, ...]:
        return tuple(self._render_card(card) for card in dashboard.cards)

    def _render_card(self, card) -> DesktopDashboardCard:
        if isinstance(card, DashboardCardViewModel):
            body = self._health(card)
        elif isinstance(card, HiddenGemsCardViewModel):
            body = self._hidden_gems(card)
        elif isinstance(card, HistoricalIntelligenceCardViewModel):
            body = self._historical(card)
        else:
            body = "Intelligence is unavailable."
        return DesktopDashboardCard(card.module_id, card.title, body)

    def _health(self, card: DashboardCardViewModel) -> str:
        unavailable = self._state_message(card.state, card.summary)
        if unavailable is not None:
            return unavailable
        score = f"{card.headline_score:.1f}/100" if card.headline_score is not None else "Unavailable"
        lines = [score, card.summary]
        lines.extend(self._section("Top positive findings", card.strengths[:3]))
        lines.extend(self._section("Top concerns", card.improvement_opportunities[:3]))
        return "\n".join(lines)

    def _hidden_gems(self, card: HiddenGemsCardViewModel) -> str:
        unavailable = self._state_message(card.state, card.summary)
        if unavailable is not None:
            return unavailable
        lines = [f"Total hidden gems: {card.total_hidden_gems or 0}", card.summary]
        if card.top_gems:
            lines.append("Top hidden gems")
            lines.extend(
                f"• {item.artist} — {item.title}: {item.explanation}"
                for item in card.top_gems
            )
        lines.append(card.explainability_summary)
        return "\n".join(lines)

    def _historical(self, card: HistoricalIntelligenceCardViewModel) -> str:
        unavailable = self._state_message(card.state, card.summary)
        if unavailable is not None:
            return unavailable
        lines = [
            f"Latest: {card.latest_snapshot_date or 'Unavailable'}",
            f"Previous: {card.previous_snapshot_date or 'Unavailable'}",
            f"Added {card.releases_added or 0} • Removed {card.releases_removed or 0} • Size {self._signed(card.collection_size_change)}",
            f"Collection value: {card.collection_value_change or 'Unavailable'}",
            f"Average value: {card.average_value_change or 'Unavailable'}",
            f"Median value: {card.median_value_change or 'Unavailable'}",
        ]
        lines.extend(self._release_section("Top gainers", card.top_gainers))
        lines.extend(self._release_section("Top decliners", card.top_decliners))
        if card.evidence_coverage_summary:
            lines.append(card.evidence_coverage_summary)
        return "\n".join(lines)

    @staticmethod
    def _state_message(state: DashboardCardState, summary: str) -> str | None:
        if state == DashboardCardState.INSUFFICIENT_HISTORY:
            return f"Insufficient history\n{summary}"
        if state in {
            DashboardCardState.FAILED,
            DashboardCardState.UNAVAILABLE,
            DashboardCardState.INCOMPLETE,
            DashboardCardState.SKIPPED,
        }:
            return summary
        return None

    @staticmethod
    def _section(title: str, items: tuple[str, ...]) -> list[str]:
        return [title, *(f"• {item}" for item in items)] if items else []

    @staticmethod
    def _release_section(title: str, items) -> list[str]:
        return [title, *(f"• {item.artist} — {item.title}: {item.change}" for item in items)] if items else []

    @staticmethod
    def _signed(value: int | None) -> str:
        return "Unavailable" if value is None else f"{value:+d}"
