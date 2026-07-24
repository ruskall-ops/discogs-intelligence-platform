"""Dedicated renderer for immutable History Explorer presentation state."""

from dataclasses import dataclass

from dip.experience.history_explorer import (
    HistoryExplorerAvailability,
    HistoryExplorerState,
)

from .intelligence_change_analysis_renderer import DesktopIntelligenceChangeAnalysisRenderer
from .intelligence_trend_analysis_renderer import DesktopIntelligenceTrendAnalysisRenderer


@dataclass(frozen=True)
class DesktopHistoryExplorerSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopHistoryExplorerView:
    title: str
    availability: HistoryExplorerAvailability
    sections: tuple[DesktopHistoryExplorerSection, ...]


class DesktopHistoryExplorerRenderer:
    def __init__(self, change_renderer=None, trend_renderer=None):
        self._change = change_renderer or DesktopIntelligenceChangeAnalysisRenderer()
        self._trend = trend_renderer or DesktopIntelligenceTrendAnalysisRenderer()

    def render(self, state):
        if type(state) is not HistoryExplorerState:
            raise TypeError("state must be HistoryExplorerState.")
        if state.availability is HistoryExplorerAvailability.UNAVAILABLE:
            return DesktopHistoryExplorerView(
                state.title, state.availability,
                (DesktopHistoryExplorerSection("Timeline", "History unavailable."),),
            )
        timeline = (
            "\n\n".join(_observation(value) for value in state.observations)
            if state.observations else "No snapshots."
        )
        snapshot = (
            _snapshot(state.observations[state.selected_observation])
            if state.selected_observation is not None else "No snapshot selected."
        )
        change = (
            _rendered(self._change.render(state.changes[state.selected_transition]))
            if state.selected_transition is not None else "No change analyses."
        )
        trend = (
            _rendered(self._trend.render(state.trends[state.selected_trend]))
            if state.selected_trend is not None else "No trend analyses."
        )
        details = _details(state)
        return DesktopHistoryExplorerView(
            state.title, state.availability,
            (
                DesktopHistoryExplorerSection("Timeline", timeline),
                DesktopHistoryExplorerSection("Snapshot", snapshot),
                DesktopHistoryExplorerSection("Change", change),
                DesktopHistoryExplorerSection("Trend", trend),
                DesktopHistoryExplorerSection("Details", details),
            ),
        )


class DesktopHistoryExplorerController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopHistoryExplorerRenderer()

    def open(self, observations=(), changes=(), trends=(), **selection):
        state = self._presentation.explorer(observations, changes, trends, **selection)
        return self._renderer.render(state)

    def render_state(self, state):
        return self._renderer.render(state)


def _observation(value):
    return "\n".join((
        f"Observation {value.observation_number}",
        f"Module: {value.module_id}",
        f"Module version: {value.module_version}",
        f"Rule set: {value.rule_set_version}",
        f"Snapshot identity: {_value(value.snapshot_identity)}",
        f"Portfolio identity: {_value(value.portfolio_identity)}",
        f"Assessment: {_value(value.assessment)}",
        f"Evidence: {_value(value.evidence)}",
    ))


def _snapshot(value):
    return "\n".join((
        f"Assessment: {_value(value.assessment)}",
        f"Evidence: {_value(value.evidence)}",
        f"Metrics: {_values(value.metrics)}",
        f"Reasons: {_values(value.reasons)}",
        f"Diagnostics: {_values(value.diagnostics)}",
        f"Provenance: {_value(value.provenance)}",
        f"Configuration: {_value(value.configuration)}",
    ))


def _details(state):
    if state.selected_observation is None:
        return "\n".join((
            "No snapshot selected.",
            f"Observation count: {len(state.observations)}",
            f"Comparison count: {len(state.changes)}",
            f"Trend count: {len(state.trends)}",
        ))
    value = state.observations[state.selected_observation]
    return "\n".join((
        f"Module identity: {value.module_id}",
        f"Module version: {value.module_version}",
        f"Rule-set version: {value.rule_set_version}",
        f"History identity: {_value(value.history_identity)}",
        f"Portfolio identity: {_value(value.portfolio_identity)}",
        f"Snapshot identity: {_value(value.snapshot_identity)}",
        f"Observation count: {len(state.observations)}",
        f"Comparison count: {len(state.changes)}",
        f"Reasons: {_values(value.reasons)}",
        f"Diagnostics: {_values(value.diagnostics)}",
        f"Configuration: {_value(value.configuration)}",
        f"Provenance: {_value(value.provenance)}",
    ))


def _rendered(value):
    return "\n\n".join((
        value.headline,
        value.summary,
        *(f"{section.title}\n{section.body}" for section in value.sections),
    ))


def _values(values):
    return ", ".join(_value(value) for value in values) or "none"


def _value(value):
    return "Not supplied" if value is None else str(value.value) if hasattr(value, "value") else str(value)


__all__ = [
    "DesktopHistoryExplorerController", "DesktopHistoryExplorerRenderer",
    "DesktopHistoryExplorerSection", "DesktopHistoryExplorerView",
]
