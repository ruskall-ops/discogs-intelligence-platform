from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import unittest

from dip.app import IntelligenceChangeAnalysisPresentationService
from dip.experience.desktop.intelligence_change_analysis_renderer import (
    DesktopIntelligenceChangeAnalysisController,
)
from dip.experience.intelligence_change_analysis import IntelligenceChangeAnalysisViewModelBuilder
from dip.historical_intelligence import (
    IntelligenceChangeAnalysis,
    IntelligenceChangeAnalysisDiagnosticCode,
    IntelligenceChangeAnalysisReasonCode,
    IntelligenceComparisonState,
)
from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from dip.portfolio_decision_intelligence import (
    PortfolioOpportunityAlignmentAssessment,
    PortfolioOpportunityAlignmentEvidenceCoverage,
    PortfolioOpportunityMappingCategory,
)
from tests.test_portfolio_opportunity_alignment import alignment


def changed_result():
    previous, previous_output = alignment()
    entries = []
    for value in previous_output.breadth.mapping_entries:
        if value.category is PortfolioOpportunityMappingCategory.SUPPORTIVE:
            value = replace(value, release_count=value.release_count + 1, release_share=value.release_share + Decimal("0.1"))
        elif value.category is PortfolioOpportunityMappingCategory.ADVERSE:
            value = replace(value, release_count=max(0, value.release_count - 1), release_share=max(Decimal("0"), value.release_share - Decimal("0.1")))
        entries.append(value)
    current_output = replace(
        previous_output,
        summary=replace(
            previous_output.summary,
            assessment=PortfolioOpportunityAlignmentAssessment.SELECTIVELY_ALIGNED,
            evidence_coverage=PortfolioOpportunityAlignmentEvidenceCoverage.LIMITED,
        ),
        breadth=replace(
            previous_output.breadth,
            matched_releases=previous_output.breadth.matched_releases + 1,
            unmatched_releases=max(0, previous_output.breadth.unmatched_releases - 1),
            mapping_entries=tuple(entries),
        ),
    )
    return previous, replace(previous, metrics={"output": current_output})


class IntelligenceChangeAnalysisTestCase(unittest.TestCase):
    def test_unchanged_supported_alignment_is_descriptive(self):
        previous, _ = alignment()
        result = IntelligenceChangeAnalysis().compare(previous, previous)
        output = result.metrics["output"]
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(output.summary.comparison_state, IntelligenceComparisonState.UNCHANGED)
        self.assertFalse(output.summary.overall_changed)
        self.assertIn(IntelligenceChangeAnalysisReasonCode.NO_CHANGE, output.reason_codes)
        self.assertTrue(all(value.delta == 0 for value in output.metrics))

    def test_assessment_evidence_and_numeric_transitions_preserve_decimal(self):
        previous, current = changed_result()
        result = IntelligenceChangeAnalysis().compare(previous, current)
        output = result.metrics["output"]
        self.assertIs(output.assessment.comparison_state, IntelligenceComparisonState.MODIFIED)
        self.assertIs(output.evidence.comparison_state, IntelligenceComparisonState.MODIFIED)
        metrics = {value.metric_id: value for value in output.metrics}
        self.assertIs(metrics["supportive_share"].comparison_state, IntelligenceComparisonState.INCREASED)
        self.assertEqual(metrics["supportive_share"].delta, Decimal("0.1"))
        self.assertIs(type(metrics["supportive_share"].delta), Decimal)
        self.assertIs(metrics["adverse_share"].comparison_state, IntelligenceComparisonState.DECREASED)
        self.assertIs(metrics["matched_releases"].comparison_state, IntelligenceComparisonState.INCREASED)

    def test_missing_unsupported_mismatch_and_version_fail_deterministically(self):
        valid, _ = alignment()
        cases = (
            (None, valid, IntelligenceChangeAnalysisDiagnosticCode.MISSING_PREVIOUS_RESULT),
            (valid, None, IntelligenceChangeAnalysisDiagnosticCode.MISSING_CURRENT_RESULT),
            (replace(valid, module_id="other"), valid, IntelligenceChangeAnalysisDiagnosticCode.UNSUPPORTED_MODULE),
            (replace(valid, module_version="2.0"), valid, IntelligenceChangeAnalysisDiagnosticCode.VERSION_MISMATCH),
            (valid, replace(valid, metrics={"output": object()}), IntelligenceChangeAnalysisDiagnosticCode.TYPED_OUTPUT_MISMATCH),
        )
        for previous, current, code in cases:
            with self.subTest(code=code):
                result = IntelligenceChangeAnalysis().compare(previous, current)
                output = result.metrics["output"]
                self.assertIs(result.status, IntelligenceStatus.SKIPPED)
                self.assertIs(output.summary.comparison_state, IntelligenceComparisonState.INSUFFICIENT)
                self.assertIn(code, tuple(value.code for value in output.output_diagnostics))

    def test_rule_set_status_snapshot_and_module_mismatch_validation(self):
        valid, valid_output = alignment()

        wrong_rules = replace(valid_output)
        object.__setattr__(wrong_rules, "rule_set_version", "2.0")
        malformed_snapshot = replace(
            valid_output,
            provenance=replace(valid_output.provenance, collection_snapshot_id=True),
        )
        cases = (
            (
                valid,
                replace(valid, metrics={"output": wrong_rules}),
                IntelligenceChangeAnalysisDiagnosticCode.RULE_SET_MISMATCH,
            ),
            (
                valid,
                replace(valid, status=IntelligenceStatus.SKIPPED),
                IntelligenceChangeAnalysisDiagnosticCode.SOURCE_STATUS_INCOMPATIBLE,
            ),
            (
                valid,
                replace(valid, metrics={"output": malformed_snapshot}),
                IntelligenceChangeAnalysisDiagnosticCode.SNAPSHOT_MISMATCH,
            ),
            (
                replace(valid, module_id="other"),
                valid,
                IntelligenceChangeAnalysisDiagnosticCode.MODULE_MISMATCH,
            ),
        )
        for previous, current, expected in cases:
            with self.subTest(expected=expected):
                output = IntelligenceChangeAnalysis().compare(previous, current).metrics["output"]
                self.assertIs(output.summary.comparison_state, IntelligenceComparisonState.INSUFFICIENT)
                self.assertIn(expected, tuple(value.code for value in output.output_diagnostics))

    def test_reason_and_diagnostic_order_is_canonical(self):
        valid, _ = alignment()
        output = IntelligenceChangeAnalysis().compare(None, valid).metrics["output"]
        reason_order = tuple(IntelligenceChangeAnalysisReasonCode).index
        diagnostic_order = tuple(IntelligenceChangeAnalysisDiagnosticCode).index
        self.assertEqual(
            output.reason_codes,
            tuple(sorted(output.reason_codes, key=reason_order)),
        )
        self.assertEqual(
            output.output_diagnostics,
            tuple(sorted(output.output_diagnostics, key=lambda value: (diagnostic_order(value.code), value.message))),
        )

    def test_history_presentation_renderer_and_immutability(self):
        previous, current = changed_result()
        result = IntelligenceChangeAnalysis().compare(previous, current)
        output = result.metrics["output"]
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        with self.assertRaises(FrozenInstanceError):
            output.summary.overall_changed = False
        controller = DesktopIntelligenceChangeAnalysisController(
            IntelligenceChangeAnalysisPresentationService(IntelligenceChangeAnalysisViewModelBuilder())
        )
        rendered = controller.open(result)
        body = "\n".join(value.body for value in rendered.sections)
        self.assertIn("Supportive Share", body)
        self.assertIn("Previous snapshot", body)
        self.assertNotIn("improved", body.lower())
        self.assertEqual(controller.open(None).sections, ())


if __name__ == "__main__":
    unittest.main()
