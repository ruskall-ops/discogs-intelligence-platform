"""Build Explorer selection state from already-produced immutable ViewModels."""

from .models import (
    HistoricalSnapshotViewModel,
    HistoryExplorerAvailability,
    HistoryExplorerFilters,
    HistoryExplorerPane,
    HistoryExplorerState,
)
from dip.experience.intelligence_change_analysis import IntelligenceChangeAnalysisViewModel
from dip.experience.intelligence_trend_analysis import IntelligenceTrendAnalysisViewModel


class HistoryExplorerStateBuilder:
    def build(
        self,
        observations=(),
        changes=(),
        trends=(),
        *,
        filters=HistoryExplorerFilters(),
        current_pane=HistoryExplorerPane.TIMELINE,
        selected_observation=None,
        selected_transition=None,
        selected_trend=None,
        history_available=True,
    ):
        observations, changes, trends = tuple(observations), tuple(changes), tuple(trends)
        if any(type(value) is not HistoricalSnapshotViewModel for value in observations):
            raise TypeError("observations must contain HistoricalSnapshotViewModel values.")
        if any(type(value) is not IntelligenceChangeAnalysisViewModel for value in changes):
            raise TypeError("changes must contain IntelligenceChangeAnalysisViewModel values.")
        if any(type(value) is not IntelligenceTrendAnalysisViewModel for value in trends):
            raise TypeError("trends must contain IntelligenceTrendAnalysisViewModel values.")
        if type(filters) is not HistoryExplorerFilters:
            raise TypeError("filters must be HistoryExplorerFilters.")
        filtered = tuple(value for value in observations if _matches(value, filters))
        availability = (
            HistoryExplorerAvailability.UNAVAILABLE if not history_available
            else HistoryExplorerAvailability.AVAILABLE
            if observations or changes or trends
            else HistoryExplorerAvailability.EMPTY
        )
        if selected_observation is None and filtered:
            selected_observation = 0
        if selected_transition is None and changes:
            selected_transition = 0
        if selected_trend is None and trends:
            selected_trend = 0
        return HistoryExplorerState(
            availability, current_pane, filtered, changes, trends, filters,
            selected_observation, selected_transition, selected_trend,
            history_available,
        )

    def select(self, state, *, pane=None, observation=None, transition=None, trend=None):
        if type(state) is not HistoryExplorerState:
            raise TypeError("state must be HistoryExplorerState.")
        return HistoryExplorerState(
            state.availability, pane or state.current_pane,
            state.observations, state.changes, state.trends, state.filters,
            state.selected_observation if observation is None else observation,
            state.selected_transition if transition is None else transition,
            state.selected_trend if trend is None else trend,
            state.history_available,
        )


def _matches(value, filters):
    return all((
        filters.observation_number is None or value.observation_number == filters.observation_number,
        filters.module_id is None or value.module_id == filters.module_id,
        filters.module_version is None or value.module_version == filters.module_version,
        filters.rule_set_version is None or value.rule_set_version == filters.rule_set_version,
        filters.portfolio_identity is None or value.portfolio_identity == filters.portfolio_identity,
        filters.snapshot_identity is None or value.snapshot_identity == filters.snapshot_identity,
    ))


__all__ = ["HistoryExplorerStateBuilder"]
