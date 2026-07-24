from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import unittest

from dip.historical_intelligence import (
    IntelligenceChangeAnalysis,
    IntelligenceTrendAnalysis,
    IntelligenceTrendClassification,
    IntelligenceTrendDiagnosticCode,
    IntelligenceTrendEvidenceCoverage,
    IntelligenceTrendOverallPattern,
)
from dip.intelligence import IntelligenceExecution, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from dip.app import IntelligenceTrendAnalysisExecutionService, IntelligenceTrendAnalysisPresentationService
from dip.experience.intelligence_trend_analysis import IntelligenceTrendAnalysisViewModelBuilder
from dip.experience.desktop.intelligence_trend_analysis_renderer import DesktopIntelligenceTrendAnalysisController
from dip.portfolio_decision_intelligence import PortfolioOpportunityMappingCategory
from tests.test_portfolio_opportunity_alignment import alignment


def observation(snapshot, supportive_share):
    result, output = alignment()
    entries = tuple(
        replace(value, release_share=Decimal(supportive_share))
        if value.category is PortfolioOpportunityMappingCategory.SUPPORTIVE else value
        for value in output.breadth.mapping_entries
    )
    output = replace(
        output,
        breadth=replace(output.breadth, mapping_entries=entries),
        provenance=replace(output.provenance, collection_snapshot_id=snapshot),
    )
    return replace(result, metrics={"output": output})


def change(previous_snapshot, current_snapshot, previous_value, current_value):
    return IntelligenceChangeAnalysis().compare(
        observation(previous_snapshot, previous_value),
        observation(current_snapshot, current_value),
    )


def trend(values):
    changes = tuple(
        change(index + 1, index + 2, values[index], values[index + 1])
        for index in range(len(values) - 1)
    )
    result = IntelligenceTrendAnalysis().analyse(changes)
    return result, result.metrics["output"]


class IntelligenceTrendAnalysisTestCase(unittest.TestCase):
    def test_minimum_linked_history_and_exact_numeric_trends(self):
        result, output = trend(("0.1", "0.2", "0.3"))
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        supportive = output.numeric_metric_trends[0]
        self.assertEqual(supportive.metric_id, "supportive_share")
        self.assertEqual(supportive.first_value, Decimal("0.1"))
        self.assertEqual(supportive.latest_value, Decimal("0.3"))
        self.assertEqual(supportive.net_delta, Decimal("0.2"))
        self.assertIs(supportive.classification, IntelligenceTrendClassification.CONSISTENTLY_INCREASING)
        self.assertEqual(output.summary.comparison_count, 2)
        self.assertEqual(output.summary.observation_count, 3)
        self.assertEqual(output.provenance.ordered_snapshot_chain, (1, 2, 3))

    def test_stable_plateau_net_reversal_and_oscillation_classification(self):
        cases = (
            (("0.1", "0.1", "0.1"), IntelligenceTrendClassification.STABLE),
            (("0.1", "0.2", "0.2"), IntelligenceTrendClassification.NET_INCREASING),
            (("0.3", "0.2", "0.2"), IntelligenceTrendClassification.NET_DECREASING),
            (("0.1", "0.2", "0.3", "0.2"), IntelligenceTrendClassification.REVERSING),
            (("0.1", "0.2", "0.1", "0.2"), IntelligenceTrendClassification.OSCILLATING),
        )
        for values, expected in cases:
            with self.subTest(expected=expected):
                _, output = trend(values)
                self.assertIs(output.numeric_metric_trends[0].classification, expected)

    def test_insufficient_and_discontinuous_sequences_are_not_reordered(self):
        one = change(1, 2, "0.1", "0.2")
        insufficient = IntelligenceTrendAnalysis().analyse((one,)).metrics["output"]
        self.assertIs(insufficient.summary.evidence_coverage, IntelligenceTrendEvidenceCoverage.INSUFFICIENT)
        discontinuous = IntelligenceTrendAnalysis().analyse((
            one,
            change(3, 4, "0.2", "0.3"),
        )).metrics["output"]
        self.assertIs(discontinuous.summary.overall_pattern, IntelligenceTrendOverallPattern.INSUFFICIENT)
        self.assertIn(
            IntelligenceTrendDiagnosticCode.DISCONTINUOUS_SNAPSHOT_CHAIN,
            tuple(value.code for value in discontinuous.diagnostics),
        )
        duplicate = IntelligenceTrendAnalysis().analyse((one, one)).metrics["output"]
        self.assertIn(
            IntelligenceTrendDiagnosticCode.DUPLICATE_TRANSITION,
            tuple(value.code for value in duplicate.diagnostics),
        )

    def test_categorical_history_serialization_and_immutability(self):
        result, output = trend(("0.1", "0.2", "0.3"))
        self.assertTrue(output.assessment_trend.stable)
        self.assertEqual(output.assessment_trend.observation_count if hasattr(output.assessment_trend, "observation_count") else len(output.assessment_trend.observed_values), 3)
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        with self.assertRaises(FrozenInstanceError):
            output.summary.comparison_count = 4
        controller = DesktopIntelligenceTrendAnalysisController(
            IntelligenceTrendAnalysisPresentationService(IntelligenceTrendAnalysisViewModelBuilder())
        )
        rendered = controller.open(result)
        body = "\n".join(value.body for value in rendered.sections)
        self.assertIn("Snapshot chain", body)
        self.assertIn("Supportive Share", body)
        self.assertNotIn("forecast", body.lower())
        self.assertEqual(controller.open(None).sections, ())

    def test_execution_service_calls_explicit_engine_once(self):
        changes = (
            change(1, 2, "0.1", "0.2"),
            change(2, 3, "0.2", "0.3"),
        )

        class Engine:
            def __init__(self):
                self.calls = []

            def execute(self, supplied):
                self.calls.append(supplied)
                return IntelligenceExecution((IntelligenceTrendAnalysis().analyse(supplied),))

        engine = Engine()
        result = IntelligenceTrendAnalysisExecutionService(engine).execute(changes)
        self.assertEqual(engine.calls, [changes])
        self.assertEqual(result.module_id, "intelligence_trend_analysis")

    def test_non_material_input_diagnostic_reduces_evidence_to_partial(self):
        changes = (
            replace(change(1, 2, "0.1", "0.2"), diagnostics=("Preserved source caveat.",)),
            change(2, 3, "0.2", "0.3"),
        )
        output = IntelligenceTrendAnalysis().analyse(changes).metrics["output"]
        self.assertIs(output.summary.evidence_coverage, IntelligenceTrendEvidenceCoverage.PARTIAL)


if __name__ == "__main__":
    unittest.main()
