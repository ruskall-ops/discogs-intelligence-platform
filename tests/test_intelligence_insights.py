from dataclasses import FrozenInstanceError
import unittest

from dip.app import IntelligenceInsightsPresentationService
from dip.experience.desktop.intelligence_insights_renderer import (
    DesktopIntelligenceInsightsController,
)
from dip.experience.intelligence_insights import (
    ChangeInsightGenerator,
    IntelligenceInsightCategory,
    IntelligenceInsightCollectionState,
    IntelligenceInsightPriority,
    IntelligenceInsightType,
    SnapshotInsightGenerator,
    TrendInsightGenerator,
)
from tests.test_history_explorer import supplied_view_models


class IntelligenceInsightsTestCase(unittest.TestCase):
    def setUp(self):
        self.snapshots, self.changes, self.trends = supplied_view_models()
        self.service = IntelligenceInsightsPresentationService(
            SnapshotInsightGenerator(), ChangeInsightGenerator(), TrendInsightGenerator()
        )

    def test_snapshot_insights_are_deterministic_evidence_first_and_ordered(self):
        first = self.service.snapshot_insights(self.snapshots[0])
        second = self.service.snapshot_insights(self.snapshots[0])
        self.assertEqual(first, second)
        self.assertIs(first.category, IntelligenceInsightCategory.SNAPSHOT)
        self.assertEqual(
            tuple(value.insight_type for value in first.insights),
            (
                IntelligenceInsightType.ASSESSMENT,
                IntelligenceInsightType.EVIDENCE,
                IntelligenceInsightType.NUMERIC_METRIC,
                IntelligenceInsightType.REASON,
                IntelligenceInsightType.CONFIGURATION,
                IntelligenceInsightType.PROVENANCE,
            ),
        )
        self.assertTrue(all(value.evidence for value in first.insights))
        priority_order = tuple(IntelligenceInsightPriority).index
        self.assertEqual(
            tuple(value.priority for value in first.insights),
            tuple(sorted((value.priority for value in first.insights), key=priority_order)),
        )
        self.assertTrue(all(value.reason_codes == self.snapshots[0].reasons for value in first.insights))
        self.assertTrue(all(value.provenance == self.snapshots[0].provenance for value in first.insights))

    def test_change_insights_preserve_transitions_reasons_diagnostics_and_source(self):
        collection = self.service.change_insights(self.changes[0])
        self.assertIs(collection.category, IntelligenceInsightCategory.CHANGE)
        assessment = next(value for value in collection.insights if value.insight_type is IntelligenceInsightType.ASSESSMENT)
        self.assertIn("Assessment", assessment.title)
        self.assertEqual(assessment.reason_codes, self.changes[0].output.reason_codes)
        self.assertEqual(assessment.diagnostics, self.changes[0].output.output_diagnostics)
        metrics = tuple(value for value in collection.insights if value.insight_type is IntelligenceInsightType.NUMERIC_METRIC)
        self.assertEqual(len(metrics), len(self.changes[0].output.metrics))

    def test_trend_insights_consume_classifications_without_regeneration(self):
        collection = self.service.trend_insights(self.trends[0])
        self.assertIs(collection.category, IntelligenceInsightCategory.TREND)
        metric_insights = tuple(value for value in collection.insights if value.insight_type is IntelligenceInsightType.NUMERIC_METRIC)
        self.assertEqual(len(metric_insights), len(self.trends[0].output.numeric_metric_trends))
        for insight, source in zip(metric_insights, self.trends[0].output.numeric_metric_trends, strict=True):
            self.assertIn(source.classification.value.replace("_", " "), insight.title.lower())
            self.assertEqual(insight.reason_codes, self.trends[0].output.reason_codes)
            self.assertEqual(insight.provenance, self.trends[0].output.provenance)

    def test_renderer_receives_collections_and_outputs_all_evidence(self):
        collections = (
            self.service.snapshot_insights(self.snapshots[0]),
            self.service.change_insights(self.changes[0]),
            self.service.trend_insights(self.trends[0]),
        )
        rendered = DesktopIntelligenceInsightsController().open(collections)
        self.assertEqual(tuple(value.title for value in rendered.sections), ("Snapshot", "Change", "Trend"))
        body = "\n".join(value.body for value in rendered.sections)
        for label in ("Evidence:", "Reasons:", "Diagnostics:", "Source:", "Provenance:", "Priority:", "Category:", "Type:"):
            self.assertIn(label, body)
        for forbidden in ("should buy", "should sell", "forecast", "recommended"):
            self.assertNotIn(forbidden, body.lower())
        self.assertEqual(DesktopIntelligenceInsightsController().open().sections[0].body, "No insights.")

    def test_empty_unavailable_and_immutability(self):
        self.assertIs(
            self.service.snapshot_insights(None).state,
            IntelligenceInsightCollectionState.NO_SNAPSHOT,
        )
        self.assertIs(
            self.service.change_insights(None).state,
            IntelligenceInsightCollectionState.NO_CHANGE,
        )
        self.assertIs(
            self.service.trend_insights(None).state,
            IntelligenceInsightCollectionState.NO_TREND,
        )
        collection = self.service.snapshot_insights(self.snapshots[0])
        with self.assertRaises(FrozenInstanceError):
            collection.insights = ()
        with self.assertRaises(FrozenInstanceError):
            collection.insights[0].title = "Changed"


if __name__ == "__main__":
    unittest.main()
