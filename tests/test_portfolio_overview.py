from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest

from dip.app import (
    PortfolioOverviewExecutionService,
    PortfolioOverviewPresentationService,
    build_portfolio_overview_input,
)
from dip.decision_intelligence import MarketplaceOpportunityModule
from dip.experience.desktop.portfolio_overview_renderer import (
    DesktopPortfolioOverviewController,
    DesktopPortfolioOverviewRenderer,
)
from dip.experience.portfolio_overview import PortfolioOverviewViewModelBuilder
from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from dip.portfolio_intelligence import (
    PortfolioEvidenceCoverage,
    PortfolioOverviewDiagnosticCode,
    PortfolioOverviewModule,
    PortfolioOverviewRuleConfiguration,
    PortfolioReleaseMatchState,
)
from tests.test_marketplace_opportunity import analyse, supplied


def opportunity_result():
    return analyse(supplied((
        (1, "positive", "stable", "scarce"),
        (2, "positive", "volatile", "scarce"),
        (3, "negative", "mixed", "common"),
        (4, "positive", "stable", "scarce"),
    )))[0]


def overview(rows, result=None, rules=None):
    prepared = build_portfolio_overview_input(
        rows,
        opportunity_result() if result is None else result,
        collection_snapshot_id=17,
    )
    module = PortfolioOverviewModule(rules or PortfolioOverviewRuleConfiguration())
    produced = module.analyse(IntelligenceContext(portfolio_overview_input=prepared))
    return produced, produced.metrics["output"]


class PortfolioOverviewTestCase(unittest.TestCase):
    def test_ownership_normalization_matching_and_copy_counts(self):
        result, output = overview((
            {"release_id": 1, "quantity": 2},
            {"release_id": 1, "quantity": 1},
            {"release_id": 2, "quantity": 1},
            {"release_id": 9, "quantity": 2},
            {"release_id": "bad", "quantity": 1},
        ))
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(output.summary.ownership.unique_owned_release_count, 3)
        self.assertEqual(output.summary.ownership.total_owned_entry_count, 6)
        self.assertEqual(output.summary.ownership.duplicate_copy_count, 3)
        self.assertEqual(output.summary.ownership.malformed_owned_entry_count, 1)
        self.assertEqual(output.summary.matched_owned_release_count, 2)
        self.assertEqual(output.summary.unmatched_owned_release_count, 1)
        self.assertEqual(
            tuple((value.release_id, value.quantity, value.match_state) for value in output.releases),
            (
                (1, 3, PortfolioReleaseMatchState.MATCHED_USABLE),
                (2, 1, PortfolioReleaseMatchState.MATCHED_USABLE),
                (9, 2, PortfolioReleaseMatchState.UNMATCHED),
            ),
        )
        codes = tuple(value.code for value in output.diagnostics)
        self.assertIn(PortfolioOverviewDiagnosticCode.DUPLICATE_OWNED_RELEASE_IDENTITY, codes)
        self.assertIn(PortfolioOverviewDiagnosticCode.OWNED_RELEASE_MISSING_FROM_OPPORTUNITY, codes)

    def test_distributions_include_zero_states_exact_ratios_and_release_ids(self):
        _, output = overview((
            {"release_id": 1, "quantity": 1},
            {"release_id": 2, "quantity": 1},
            {"release_id": 3, "quantity": 1},
        ))
        distribution = output.opportunity_distribution
        self.assertEqual(tuple(value.state for value in distribution.entries), (
            "strong", "developing", "balanced", "constrained", "weak", "insufficient",
        ))
        by_state = {value.state: value for value in distribution.entries}
        self.assertEqual(by_state["strong"].release_ids, (1,))
        self.assertEqual(by_state["constrained"].release_ids, (2,))
        self.assertEqual(by_state["weak"].release_ids, (3,))
        self.assertEqual(by_state["developing"].count, 0)
        self.assertEqual(by_state["strong"].all_owned_ratio, Decimal(1) / Decimal(3))
        self.assertEqual(distribution.all_owned_denominator, 3)
        self.assertEqual(distribution.matched_denominator, 3)
        self.assertEqual(distribution.usable_denominator, 3)
        self.assertEqual(tuple(value.state for value in output.momentum_distribution.entries), (
            "positive", "mixed", "neutral", "negative", "insufficient",
        ))
        self.assertEqual(tuple(value.state for value in output.stability_distribution.entries), (
            "stable", "mixed", "volatile", "insufficient",
        ))
        self.assertEqual(tuple(value.state for value in output.scarcity_distribution.entries), (
            "abundant", "common", "limited", "scarce", "very_scarce", "insufficient",
        ))

    def test_coverage_boundaries_empty_and_incompatible_source(self):
        _, complete = overview(tuple({"release_id": value, "quantity": 1} for value in (1, 2, 3, 4)))
        self.assertIs(complete.summary.evidence_coverage, PortfolioEvidenceCoverage.COMPLETE)
        _, partial = overview(tuple({"release_id": value, "quantity": 1} for value in (1, 2, 3, 9)))
        self.assertIs(partial.summary.evidence_coverage, PortfolioEvidenceCoverage.PARTIAL)
        _, limited = overview(tuple({"release_id": value, "quantity": 1} for value in (1, 2, 9, 10)))
        self.assertIs(limited.summary.evidence_coverage, PortfolioEvidenceCoverage.LIMITED)
        empty_result, empty = overview(())
        self.assertIs(empty_result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(empty.summary.evidence_coverage, PortfolioEvidenceCoverage.INSUFFICIENT)
        incompatible = MarketplaceOpportunityModule().analyse(IntelligenceContext())
        incompatible_result, incompatible_output = overview(({"release_id": 1},), incompatible)
        self.assertIs(incompatible_result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(incompatible_output.summary.evidence_coverage, PortfolioEvidenceCoverage.INSUFFICIENT)

    def test_custom_threshold_validation_concentration_tie_and_immutability(self):
        rules = PortfolioOverviewRuleConfiguration(Decimal("0.5"))
        _, output = overview(
            tuple({"release_id": value} for value in (1, 2, 9, 10)),
            rules=rules,
        )
        self.assertIs(output.summary.evidence_coverage, PortfolioEvidenceCoverage.PARTIAL)
        opportunity = output.concentration_facts[0]
        self.assertEqual(opportunity.largest_category, "strong")
        self.assertEqual(opportunity.largest_category_count, 1)
        with self.assertRaises(ValueError):
            PortfolioOverviewRuleConfiguration(Decimal("1"))
        with self.assertRaises(TypeError):
            PortfolioOverviewRuleConfiguration(0.75)
        with self.assertRaises(FrozenInstanceError):
            output.summary.coverage_numerator = 4

    def test_history_presentation_and_renderer_preserve_typed_output(self):
        result, output = overview((
            {"release_id": 1, "quantity": 2},
            {"release_id": 9, "quantity": 1},
        ))
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        presentation = PortfolioOverviewPresentationService(PortfolioOverviewViewModelBuilder())
        controller = DesktopPortfolioOverviewController(
            presentation, DesktopPortfolioOverviewRenderer()
        )
        rendered = controller.open(result)
        self.assertEqual(rendered.title, "Portfolio Overview")
        body = "\n".join(value.body for value in rendered.sections)
        self.assertIn(
            "Observed Marketplace Scarcity distribution",
            tuple(value.title for value in rendered.sections),
        )
        self.assertIn("Coverage: 1/2 (0.5)", body)
        self.assertIn("Unmatched", body)
        unavailable = controller.open(None)
        self.assertEqual(unavailable.sections, ())

    def test_execution_calls_collection_opportunity_and_engine_once(self):
        class Collection:
            def __init__(self):
                self.calls = 0

            def owned_portfolio_rows(self):
                self.calls += 1
                return [{"release_id": 1, "quantity": 2}]

        class Opportunity:
            def __init__(self):
                self.calls = 0

            def execute(self):
                self.calls += 1
                return opportunity_result()

        class Engine:
            def __init__(self):
                self.calls = []
                self.real = IntelligenceEngine((PortfolioOverviewModule(),))

            def execute(self, context):
                self.calls.append(context)
                return self.real.execute(context)

        collection, opportunity, engine = Collection(), Opportunity(), Engine()
        result = PortfolioOverviewExecutionService(collection, opportunity, engine).execute()
        self.assertEqual(collection.calls, 1)
        self.assertEqual(opportunity.calls, 1)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(result.module_id, "portfolio_overview")


if __name__ == "__main__":
    unittest.main()
