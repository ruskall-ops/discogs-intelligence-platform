from dataclasses import FrozenInstanceError
import unittest

from dip.app import HistoryExplorerPresentationService
from dip.experience.desktop.history_explorer_renderer import DesktopHistoryExplorerController
from dip.experience.history_explorer import (
    HistoricalSnapshotViewModel,
    HistoryExplorerAvailability,
    HistoryExplorerFilters,
    HistoryExplorerPane,
    HistoryExplorerStateBuilder,
)
from dip.experience.intelligence_change_analysis import IntelligenceChangeAnalysisViewModelBuilder
from dip.experience.intelligence_trend_analysis import IntelligenceTrendAnalysisViewModelBuilder
from dip.historical_intelligence import IntelligenceChangeAnalysis, IntelligenceTrendAnalysis
from tests.test_intelligence_trend_analysis import observation


def supplied_view_models():
    snapshots = tuple(
        HistoricalSnapshotViewModel(
            position, "portfolio_opportunity_alignment", "1.0", "1.0",
            position, "portfolio-a", assessment, evidence,
            metrics=(f"metric-{position}",), reasons=(f"reason-{position}",),
            diagnostics=(), provenance=f"provenance-{position}",
            configuration="rules-1.0", history_identity=f"history-{position}",
        )
        for position, assessment, evidence in (
            (1, "mixed", "complete"),
            (2, "selectively_aligned", "partial"),
            (3, "broadly_aligned", "complete"),
        )
    )
    changes = (
        IntelligenceChangeAnalysis().compare(observation(1, "0.1"), observation(2, "0.2")),
        IntelligenceChangeAnalysis().compare(observation(2, "0.2"), observation(3, "0.3")),
    )
    change_models = tuple(IntelligenceChangeAnalysisViewModelBuilder().build(value) for value in changes)
    trend_result = IntelligenceTrendAnalysis().analyse(changes)
    trend_models = (IntelligenceTrendAnalysisViewModelBuilder().build(trend_result),)
    return snapshots, change_models, trend_models


class HistoryExplorerTestCase(unittest.TestCase):
    def test_timeline_preserves_supplied_order_and_renders_all_panes(self):
        snapshots, changes, trends = supplied_view_models()
        controller = DesktopHistoryExplorerController(
            HistoryExplorerPresentationService(HistoryExplorerStateBuilder())
        )
        rendered = controller.open(snapshots, changes, trends)
        self.assertEqual(
            tuple(value.title for value in rendered.sections),
            ("Timeline", "Snapshot", "Change", "Trend", "Details"),
        )
        timeline = rendered.sections[0].body
        self.assertLess(timeline.index("Observation 1"), timeline.index("Observation 2"))
        self.assertLess(timeline.index("Observation 2"), timeline.index("Observation 3"))
        self.assertIn("Assessment: mixed", rendered.sections[1].body)
        self.assertIn("Supportive Share", rendered.sections[2].body)
        self.assertIn("Historical pattern", rendered.sections[3].body)
        self.assertIn("History identity: history-1", rendered.sections[4].body)

    def test_filters_are_identity_only_and_preserve_relative_order(self):
        snapshots, changes, trends = supplied_view_models()
        builder = HistoryExplorerStateBuilder()
        state = builder.build(
            snapshots, changes, trends,
            filters=HistoryExplorerFilters(module_version="1.0", snapshot_identity=2),
        )
        self.assertEqual(tuple(value.observation_number for value in state.observations), (2,))
        selected = builder.select(state, pane=HistoryExplorerPane.DETAILS)
        self.assertIs(selected.current_pane, HistoryExplorerPane.DETAILS)
        self.assertIs(state.current_pane, HistoryExplorerPane.TIMELINE)
        with self.assertRaises(FrozenInstanceError):
            selected.current_pane = HistoryExplorerPane.TIMELINE

    def test_deterministic_empty_and_unavailable_states(self):
        controller = DesktopHistoryExplorerController(
            HistoryExplorerPresentationService(HistoryExplorerStateBuilder())
        )
        empty = controller.open()
        self.assertIs(empty.availability, HistoryExplorerAvailability.EMPTY)
        self.assertEqual(empty.sections[0].body, "No snapshots.")
        self.assertEqual(empty.sections[2].body, "No change analyses.")
        self.assertEqual(empty.sections[3].body, "No trend analyses.")
        unavailable = controller.open(history_available=False)
        self.assertIs(unavailable.availability, HistoryExplorerAvailability.UNAVAILABLE)
        self.assertEqual(unavailable.sections[0].body, "History unavailable.")

    def test_selection_and_navigation_do_not_call_supplied_view_models(self):
        snapshots, changes, trends = supplied_view_models()
        presentation = HistoryExplorerPresentationService(HistoryExplorerStateBuilder())
        state = presentation.explorer(snapshots, changes, trends)
        selected = presentation.select(
            state, pane=HistoryExplorerPane.SNAPSHOT, observation=2,
            transition=1, trend=0,
        )
        self.assertEqual(selected.selected_observation, 2)
        self.assertEqual(selected.selected_transition, 1)
        self.assertEqual(selected.selected_trend, 0)
        self.assertEqual(selected.observations, snapshots)


if __name__ == "__main__":
    unittest.main()
