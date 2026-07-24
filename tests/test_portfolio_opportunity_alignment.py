from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import unittest

from dip.app import (
    PortfolioOpportunityAlignmentExecutionService,
    PortfolioOpportunityAlignmentPresentationService,
    build_portfolio_concentration_input,
    build_portfolio_opportunity_alignment_input,
)
from dip.experience.desktop.portfolio_opportunity_alignment_renderer import (
    DesktopPortfolioOpportunityAlignmentController,
)
from dip.experience.desktop.portfolio_renderer import DesktopPortfolioController, DesktopPortfolioDestination
from dip.experience.portfolio_opportunity_alignment import PortfolioOpportunityAlignmentViewModelBuilder
from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from dip.portfolio_decision_intelligence import (
    PortfolioConcentrationContextCategory,
    PortfolioOpportunityAlignmentAssessment,
    PortfolioOpportunityAlignmentModule,
    PortfolioOpportunityMappingCategory,
)
from dip.portfolio_intelligence import PortfolioConcentrationModule
from tests.test_portfolio_distribution import analyse as distribution_analyse, row
from tests.test_portfolio_overview import overview


def sources():
    rows = (
        row(1, 2, artist="Alpha"),
        row(2, 1, artist="Beta"),
        row(3, 1, artist="Gamma"),
    )
    overview_result, _ = overview(tuple({"release_id": value["release_id"], "quantity": value["quantity"]} for value in rows))
    distribution_result, distribution = distribution_analyse(rows)
    distribution = replace(
        distribution,
        provenance=replace(distribution.provenance, collection_snapshot_id=17),
    )
    distribution_result = replace(distribution_result, metrics={"output": distribution})
    concentration_input = build_portfolio_concentration_input(distribution_result)
    concentration_result = PortfolioConcentrationModule().analyse(
        IntelligenceContext(portfolio_concentration_input=concentration_input)
    )
    return overview_result, distribution_result, concentration_result


def alignment():
    prepared = build_portfolio_opportunity_alignment_input(*sources())
    result = PortfolioOpportunityAlignmentModule().analyse(
        IntelligenceContext(portfolio_opportunity_alignment_input=prepared)
    )
    return result, result.metrics["output"]


class PortfolioOpportunityAlignmentTestCase(unittest.TestCase):
    def test_mapping_breadth_category_copy_semantics_and_concentration_context(self):
        result, output = alignment()
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(
            tuple(value.category for value in output.breadth.mapping_entries),
            tuple(PortfolioOpportunityMappingCategory),
        )
        mapped = {value.category: value for value in output.breadth.mapping_entries}
        self.assertEqual(mapped[PortfolioOpportunityMappingCategory.SUPPORTIVE].release_ids, (1,))
        self.assertEqual(mapped[PortfolioOpportunityMappingCategory.SUPPORTIVE].copy_count, 2)
        self.assertEqual(mapped[PortfolioOpportunityMappingCategory.SUPPORTIVE].copy_share, Decimal("0.5"))
        self.assertEqual(mapped[PortfolioOpportunityMappingCategory.LIMITING].release_ids, (2,))
        self.assertEqual(mapped[PortfolioOpportunityMappingCategory.ADVERSE].release_ids, (3,))
        artist = output.dimensions[0]
        self.assertEqual(tuple(value.category_id for value in artist.categories), ("Alpha", "Beta", "Gamma"))
        self.assertEqual(artist.categories[0].mapping_entries[0].copy_count, 2)
        self.assertIs(artist.release_concentration_context, PortfolioConcentrationContextCategory.BROAD)

    def test_missing_and_incompatible_sources_are_deterministically_insufficient(self):
        overview_result, distribution_result, concentration_result = sources()
        for supplied in (
            (None, distribution_result, concentration_result),
            (overview_result, None, concentration_result),
            (overview_result, distribution_result, None),
            (overview_result, replace(distribution_result, module_version="2.0"), concentration_result),
        ):
            with self.subTest(supplied=supplied):
                result = PortfolioOpportunityAlignmentModule().analyse(
                    IntelligenceContext(
                        portfolio_opportunity_alignment_input=build_portfolio_opportunity_alignment_input(*supplied)
                    )
                )
                self.assertIs(result.status, IntelligenceStatus.SKIPPED)
                self.assertIs(result.metrics["output"].summary.assessment, PortfolioOpportunityAlignmentAssessment.INSUFFICIENT)

    def test_execution_history_presentation_and_fourth_portfolio_destination(self):
        source_results = sources()

        class Provider:
            def __init__(self, value):
                self.value, self.calls = value, 0
            def execute(self):
                self.calls += 1
                return self.value

        providers = tuple(Provider(value) for value in source_results)
        service = PortfolioOpportunityAlignmentExecutionService(
            *providers, IntelligenceEngine((PortfolioOpportunityAlignmentModule(),))
        )
        result = service.execute()
        self.assertEqual(tuple(value.calls for value in providers), (1, 1, 1))
        output = result.metrics["output"]
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        with self.assertRaises(FrozenInstanceError):
            output.summary.assessment = PortfolioOpportunityAlignmentAssessment.MIXED
        controller = DesktopPortfolioOpportunityAlignmentController(
            PortfolioOpportunityAlignmentPresentationService(PortfolioOpportunityAlignmentViewModelBuilder())
        )
        rendered = controller.open(result)
        self.assertIn("Observed alignment", rendered.headline)
        self.assertIn("Thresholds", "\n".join(value.body for value in rendered.sections))

        class Existing:
            def open(self, supplied):
                return rendered

        portfolio = DesktopPortfolioController(Existing(), Existing(), Existing(), Existing()).open(
            None, None, None, result
        )
        self.assertEqual(
            tuple(value.destination for value in portfolio.sections),
            (
                DesktopPortfolioDestination.OVERVIEW,
                DesktopPortfolioDestination.DISTRIBUTION,
                DesktopPortfolioDestination.CONCENTRATION,
                DesktopPortfolioDestination.OPPORTUNITY_ALIGNMENT,
            ),
        )


if __name__ == "__main__":
    unittest.main()
