from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import unittest

from dip.app import (
    PortfolioConcentrationExecutionService,
    PortfolioConcentrationPresentationService,
    build_portfolio_concentration_input,
)
from dip.experience.desktop.portfolio_concentration_renderer import (
    DesktopPortfolioConcentrationController,
    DesktopPortfolioConcentrationRenderer,
)
from dip.experience.desktop.portfolio_renderer import (
    DesktopPortfolioController,
    DesktopPortfolioDestination,
)
from dip.experience.portfolio_concentration import PortfolioConcentrationViewModelBuilder
from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceResult, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from dip.portfolio_intelligence import (
    PortfolioConcentrationEvidenceCoverage,
    PortfolioConcentrationModule,
    PortfolioConcentrationRuleConfiguration,
    PortfolioConcentrationState,
)
from tests.test_portfolio_distribution import analyse as distribution_analyse, row


def concentration(rows):
    distribution_result, _ = distribution_analyse(rows)
    supplied = build_portfolio_concentration_input(distribution_result)
    result = PortfolioConcentrationModule().analyse(
        IntelligenceContext(portfolio_concentration_input=supplied)
    )
    return result, result.metrics["output"]


class PortfolioConcentrationTestCase(unittest.TestCase):
    def test_one_category_metrics_are_explicit(self):
        result, output = concentration((
            row(1, 2, artist="One"),
            row(2, 1, artist="One"),
        ))
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        artist = output.dimensions[0]
        for metrics in (artist.release_concentration, artist.copy_concentration):
            self.assertEqual(metrics.largest_category_share, Decimal("1"))
            self.assertEqual(metrics.top_three.share, Decimal("1"))
            self.assertEqual(metrics.top_three.included_category_count, 1)
            self.assertEqual(metrics.top_five.share, Decimal("1"))
            self.assertEqual(metrics.hhi, Decimal("1"))
            self.assertEqual(metrics.normalized_hhi, Decimal("1"))
            self.assertEqual(metrics.effective_category_count, Decimal("1"))
            self.assertIs(metrics.state, PortfolioConcentrationState.HIGHLY_CONCENTRATED)

    def test_equal_categories_hhi_effective_count_and_ties(self):
        _, output = concentration((
            row(1, artist="Alpha"),
            row(2, artist="Beta"),
        ))
        artist = output.dimensions[0]
        metrics = artist.release_concentration
        self.assertEqual(metrics.membership_total, 2)
        self.assertEqual(metrics.largest_category_share, Decimal("0.5"))
        self.assertEqual(len(metrics.largest_categories), 2)
        self.assertEqual(metrics.hhi, Decimal("0.50"))
        self.assertEqual(metrics.normalized_hhi, Decimal("0"))
        self.assertEqual(metrics.effective_category_count, Decimal("2"))
        self.assertIs(metrics.state, PortfolioConcentrationState.DISPERSED)

    def test_top_n_uses_source_order_and_visible_membership_denominator(self):
        _, output = concentration(tuple(
            row(index, artist=name)
            for index, name in enumerate(("A", "A", "A", "B", "B", "C", "D", "E", "F"), 1)
        ))
        metrics = output.dimensions[0].release_concentration
        self.assertEqual(metrics.membership_total, 9)
        self.assertEqual(
            tuple(value.category_id for value in metrics.top_three.contributions),
            ("A", "B", "C"),
        )
        self.assertEqual(metrics.top_three.membership_numerator, 6)
        self.assertEqual(metrics.top_three.membership_denominator, 9)
        self.assertEqual(metrics.top_three.share, Decimal(6) / Decimal(9))
        self.assertEqual(metrics.top_five.included_category_count, 5)
        self.assertEqual(metrics.top_five.membership_numerator, 8)

    def test_copy_ownership_changes_copy_concentration_with_exact_deltas(self):
        _, output = concentration((
            row(1, 5, artist="Alpha"),
            row(2, 1, artist="Beta"),
        ))
        artist = output.dimensions[0]
        release = artist.release_concentration
        copies = artist.copy_concentration
        self.assertEqual(release.hhi, Decimal("0.50"))
        self.assertEqual(copies.largest_category_share, Decimal(5) / Decimal(6))
        self.assertEqual(copies.hhi, (Decimal(5) / Decimal(6)) ** 2 + (Decimal(1) / Decimal(6)) ** 2)
        self.assertEqual(artist.difference.hhi_delta, copies.hhi - release.hhi)
        self.assertGreater(artist.difference.largest_category_share_delta, 0)

    def test_default_state_bands_use_normalized_hhi(self):
        cases = (
            ((3, 1), PortfolioConcentrationState.MODERATE),
            ((5, 1), PortfolioConcentrationState.CONCENTRATED),
            ((10, 1), PortfolioConcentrationState.HIGHLY_CONCENTRATED),
        )
        for counts, expected in cases:
            rows = []
            release_id = 1
            for category, count in zip(("Alpha", "Beta"), counts, strict=True):
                for _ in range(count):
                    rows.append(row(release_id, artist=category))
                    release_id += 1
            with self.subTest(counts=counts):
                _, output = concentration(tuple(rows))
                self.assertIs(output.dimensions[0].release_concentration.state, expected)

    def test_metadata_coverage_and_empty_source_states_are_preserved(self):
        _, partial = concentration((
            row(1, artist="Artist", label=None),
            row(2, artist="Other", label="Label"),
        ))
        self.assertIs(partial.summary.evidence_coverage, PortfolioConcentrationEvidenceCoverage.PARTIAL)
        label = partial.dimensions[1]
        self.assertEqual(label.releases_missing_metadata, 1)
        self.assertEqual(label.missing_release_ids, (1,))
        empty_result, empty = concentration(())
        self.assertIs(empty_result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(empty.summary.evidence_coverage, PortfolioConcentrationEvidenceCoverage.INSUFFICIENT)

    def test_source_validation_missing_wrong_version_and_malformed_output(self):
        missing = build_portfolio_concentration_input(None)
        self.assertFalse(missing.source_compatible)
        wrong = build_portfolio_concentration_input(IntelligenceResult(
            "other", IntelligenceStatus.COMPLETED, "wrong", module_version="1.0"
        ))
        self.assertFalse(wrong.source_compatible)
        distribution_result, _ = distribution_analyse((row(1),))
        unsupported = build_portfolio_concentration_input(
            replace(distribution_result, module_version="2.0")
        )
        self.assertFalse(unsupported.source_compatible)
        malformed = build_portfolio_concentration_input(
            replace(distribution_result, metrics={"output": object()})
        )
        self.assertFalse(malformed.source_compatible)
        result = PortfolioConcentrationModule().analyse(
            IntelligenceContext(portfolio_concentration_input=unsupported)
        )
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)

    def test_rules_history_presentation_renderer_and_navigation(self):
        with self.assertRaises(ValueError):
            PortfolioConcentrationRuleConfiguration(
                Decimal("0.4"), Decimal("0.3"), Decimal("0.6")
            )
        result, output = concentration((
            row(1, 3, artist="Alpha"),
            row(2, 1, artist="Beta"),
        ))
        self.assertEqual(output.rule_set_version, "1.0")
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        with self.assertRaises(FrozenInstanceError):
            output.summary.total_owned_copies = 5
        concentration_controller = DesktopPortfolioConcentrationController(
            PortfolioConcentrationPresentationService(PortfolioConcentrationViewModelBuilder()),
            DesktopPortfolioConcentrationRenderer(),
        )
        rendered = concentration_controller.open(result)
        body = "\n".join(value.body for value in rendered.sections)
        self.assertIn("Normalized HHI", body)
        self.assertIn("Effective category count", body)
        self.assertEqual(concentration_controller.open(None).sections, ())

        class Existing:
            def __init__(self, value):
                self.value = value
                self.calls = []

            def open(self, supplied):
                self.calls.append(supplied)
                return self.value

        simple = type("Rendered", (), {"headline": "State", "summary": "Summary", "sections": ()})()
        controllers = (Existing(simple), Existing(simple), Existing(rendered))
        workspace = DesktopPortfolioController(*controllers)
        portfolio = workspace.open("overview", "distribution", result)
        self.assertEqual(tuple(value.destination for value in portfolio.sections), (
            DesktopPortfolioDestination.OVERVIEW,
            DesktopPortfolioDestination.DISTRIBUTION,
            DesktopPortfolioDestination.CONCENTRATION,
        ))
        self.assertEqual(controllers[2].calls, [result])

    def test_execution_calls_provider_and_engine_once(self):
        source, _ = distribution_analyse((row(1),))

        class Provider:
            def __init__(self):
                self.calls = 0

            def execute(self):
                self.calls += 1
                return source

        class Engine:
            def __init__(self):
                self.calls = []
                self.real = IntelligenceEngine((PortfolioConcentrationModule(),))

            def execute(self, context):
                self.calls.append(context)
                return self.real.execute(context)

        provider, engine = Provider(), Engine()
        result = PortfolioConcentrationExecutionService(provider, engine).execute()
        self.assertEqual(provider.calls, 1)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(result.module_id, "portfolio_concentration")


if __name__ == "__main__":
    unittest.main()
