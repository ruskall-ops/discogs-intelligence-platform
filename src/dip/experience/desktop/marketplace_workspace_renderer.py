"""Dedicated rendering for immutable Marketplace Workspace state."""

from dataclasses import dataclass

from dip.experience.marketplace_workspace import (
    MarketplaceWorkspaceAvailability,
    MarketplaceWorkspaceState,
)

from .history_explorer_renderer import DesktopHistoryExplorerRenderer
from .intelligence_insights_renderer import DesktopIntelligenceInsightsRenderer
from .marketplace_opportunity_renderer import DesktopMarketplaceOpportunityRenderer


@dataclass(frozen=True)
class DesktopMarketplaceWorkspaceSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopMarketplaceWorkspaceView:
    title: str
    availability: MarketplaceWorkspaceAvailability
    sections: tuple[DesktopMarketplaceWorkspaceSection, ...]


class DesktopMarketplaceWorkspaceRenderer:
    def __init__(self, detail_renderer=None, history_renderer=None, insights_renderer=None):
        self._detail = detail_renderer or DesktopMarketplaceOpportunityRenderer()
        self._history = history_renderer or DesktopHistoryExplorerRenderer()
        self._insights = insights_renderer or DesktopIntelligenceInsightsRenderer()

    def render(self, state):
        if type(state) is not MarketplaceWorkspaceState:
            raise TypeError("state must be MarketplaceWorkspaceState.")
        if state.availability is MarketplaceWorkspaceAvailability.UNAVAILABLE:
            return DesktopMarketplaceWorkspaceView(
                state.title, state.availability,
                (DesktopMarketplaceWorkspaceSection("Attention Queue", "Workspace unavailable."),),
            )
        selected = next((value for value in state.filtered_queue if value.release_id == state.selected_release_id), None)
        queue = (
            "\n\n".join(_queue_item(value) for value in state.filtered_queue)
            if state.filtered_queue else "No opportunities supplied."
        )
        detail = (
            _detail(
                self._detail.render(state.selected_detail), selected,
                self._insights.render(selected.insights) if selected.insights else None,
            )
            if state.selected_detail is not None else "No opportunity detail."
        )
        evidence = (
            "\n\n".join(f"{value.title}\n{_values(value.items)}" for value in state.selected_evidence_sections)
            if state.selected_evidence_sections else "No evidence."
        )
        history = (
            _sections(self._history.render(state.selected_history).sections)
            if state.selected_history is not None else "No history."
        )
        if selected is not None and selected.trend_available:
            history = "\n\n".join((history, "Trend availability: supplied."))
        portfolio = _portfolio(state.selected_portfolio_context)
        research = (
            f"Release {selected.release_id}\nResearch status: {_label(selected.research_status.value)}"
            if selected is not None else "No research status."
        )
        return DesktopMarketplaceWorkspaceView(
            state.title, state.availability,
            (
                DesktopMarketplaceWorkspaceSection("Attention Queue", queue),
                DesktopMarketplaceWorkspaceSection("Opportunity Detail", detail),
                DesktopMarketplaceWorkspaceSection("Evidence", evidence),
                DesktopMarketplaceWorkspaceSection("Marketplace History", history),
                DesktopMarketplaceWorkspaceSection("Portfolio Context", portfolio),
                DesktopMarketplaceWorkspaceSection("Research Status", research),
            ),
        )


class DesktopMarketplaceWorkspaceController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopMarketplaceWorkspaceRenderer()

    def open(self, queue=(), **state):
        return self._renderer.render(self._presentation.workspace(queue, **state))

    def render_state(self, state):
        return self._renderer.render(state)


def _queue_item(value):
    return "\n".join((
        f"Release {value.release_id}: {value.artist} — {value.title}",
        f"Marketplace assessment: {_value(value.marketplace_assessment)}",
        f"Evidence: {_value(value.evidence_state)}",
        f"Classification: {_value(value.opportunity_classification)}",
        f"Insight: {value.insight_summary}",
        f"Reasons: {_values(value.reason_codes)}",
        f"Diagnostics: {_values(value.diagnostics)}",
        f"History available: {'yes' if value.history_available else 'no'}",
        f"Trend available: {'yes' if value.trend_available else 'no'}",
        f"Research status: {_label(value.research_status.value)}",
    ))


def _detail(rendered, selected, insights):
    return "\n\n".join((
        rendered.headline, rendered.summary, rendered.context,
        *(f"{value.heading}\n{value.body}" for value in rendered.releases),
        f"Reasons: {_values(selected.reason_codes)}",
        f"Diagnostics: {_values(selected.diagnostics)}",
        f"Provenance: {_value(selected.provenance)}",
        f"Configuration: {_value(selected.configuration)}",
        "Insights:\n" + (_sections(insights.sections) if insights is not None else "No insights."),
    ))


def _portfolio(value):
    if value is None:
        return "No portfolio context."
    return "\n".join((
        f"Owned: {'yes' if value.owned else 'no'}",
        f"Owned copies: {value.owned_copies}",
        f"Portfolio alignment: {_value(value.portfolio_alignment)}",
        f"Collection gap: {_value(value.collection_gap)}",
        f"Duplication: {_value(value.duplication)}",
        f"Concentration context: {_value(value.concentration_context)}",
        f"Coverage: {_value(value.coverage)}",
        f"Provenance: {_value(value.provenance)}",
    ))


def _sections(sections):
    return "\n\n".join(f"{value.title}\n{value.body}" for value in sections)


def _values(values):
    return ", ".join(_value(value) for value in values) or "none"


def _value(value):
    return "Not supplied" if value is None else str(value.value) if hasattr(value, "value") else str(value)


def _label(value):
    return value.replace("_", " ").title()


__all__ = [
    "DesktopMarketplaceWorkspaceController", "DesktopMarketplaceWorkspaceRenderer",
    "DesktopMarketplaceWorkspaceSection", "DesktopMarketplaceWorkspaceView",
]
