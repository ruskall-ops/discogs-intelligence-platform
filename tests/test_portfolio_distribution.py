from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest

from dip.app import (
    PortfolioDistributionExecutionService,
    PortfolioDistributionPresentationService,
    build_portfolio_distribution_input,
)
from dip.experience.desktop.portfolio_distribution_renderer import (
    DesktopPortfolioDistributionController,
    DesktopPortfolioDistributionRenderer,
)
from dip.experience.desktop.portfolio_renderer import (
    DesktopPortfolioController,
    DesktopPortfolioDestination,
)
from dip.experience.portfolio_distribution import PortfolioDistributionViewModelBuilder
from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from dip.portfolio_intelligence import (
    PortfolioDistributionDiagnosticCode,
    PortfolioDistributionDimension,
    PortfolioDistributionEvidenceCoverage,
    PortfolioDistributionModule,
    PortfolioDistributionRuleConfiguration,
    PortfolioReleaseMetadataFact,
    PortfolioDistributionInput,
)


def row(release_id, quantity=1, artist="Artist", label="Label", format="Vinyl", released="1970"):
    return {
        "release_id": release_id,
        "quantity": quantity,
        "artist": artist,
        "label": label,
        "format": format,
        "released": released,
    }


def analyse(rows):
    supplied = build_portfolio_distribution_input(rows, collection_snapshot_id=41)
    result = PortfolioDistributionModule().analyse(
        IntelligenceContext(portfolio_distribution_input=supplied)
    )
    return result, result.metrics["output"]


class PortfolioDistributionTestCase(unittest.TestCase):
    def test_supported_repository_dimensions_and_complete_distribution(self):
        result, output = analyse((
            row(1, 2, "Shared", "Alpha", "Vinyl", "1969"),
            row(2, 1, "Shared", "Beta", "CD", "1970"),
            row(3, 3, "Other", "Alpha", "Vinyl", "2004"),
        ))
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(output.rule_set_version, "1.0")
        self.assertEqual(output.summary.supported_dimensions, tuple(PortfolioDistributionDimension))
        self.assertEqual(output.summary.unavailable_dimensions, ("country", "genre", "style"))
        self.assertIs(output.summary.evidence_coverage, PortfolioDistributionEvidenceCoverage.COMPLETE)
        self.assertEqual(output.summary.ownership.unique_owned_releases, 3)
        self.assertEqual(output.summary.ownership.total_owned_copies, 6)
        self.assertEqual(output.summary.ownership.duplicate_copy_count, 3)
        artist = output.dimensions[0]
        self.assertEqual(artist.entries[0].category_id, "Shared")
        self.assertEqual(artist.entries[0].release_ids, (1, 2))
        self.assertEqual(artist.entries[0].release_ratio, Decimal(2) / Decimal(3))
        self.assertEqual(artist.entries[0].copy_ratio, Decimal("0.5"))
        decades = output.dimensions[4]
        self.assertEqual(tuple(value.display_name for value in decades.entries), ("1960s", "1970s", "2000s"))

    def test_duplicate_rows_are_summed_and_conflicting_metadata_is_excluded(self):
        supplied = build_portfolio_distribution_input((
            row(1, 2),
            row(1, 3),
            row(2, 1, artist="First"),
            row(2, 1, artist="Second"),
            row("bad"),
            row(3, quantity=0),
        ))
        self.assertEqual(tuple((value.release_id, value.quantity) for value in supplied.releases), ((1, 5),))
        self.assertEqual(supplied.malformed_owned_release_count, 3)
        codes = tuple(value.code for value in supplied.diagnostics)
        self.assertIn(PortfolioDistributionDiagnosticCode.DUPLICATE_OWNERSHIP_ROW_NORMALIZED, codes)
        self.assertIn(PortfolioDistributionDiagnosticCode.CONFLICTING_DUPLICATE_METADATA, codes)
        self.assertIn(PortfolioDistributionDiagnosticCode.MALFORMED_RELEASE_IDENTITY, codes)
        self.assertIn(PortfolioDistributionDiagnosticCode.INVALID_OWNERSHIP_QUANTITY, codes)

    def test_missing_metadata_and_invalid_year_are_visible_without_unknown_categories(self):
        _, output = analyse((
            row(1, 2, artist=" ", label=None, format="", released="0"),
            row(2, 1, artist="Artist", label="Label", format="Vinyl", released="2000"),
        ))
        self.assertIs(output.summary.evidence_coverage, PortfolioDistributionEvidenceCoverage.PARTIAL)
        for dimension in output.dimensions:
            self.assertEqual(dimension.missing_release_ids, (1,))
            self.assertEqual(dimension.releases_with_metadata, 1)
            self.assertEqual(dimension.releases_missing_metadata, 1)
            self.assertEqual(dimension.copies_with_metadata, 1)
            self.assertEqual(dimension.copies_missing_metadata, 2)
            self.assertEqual(dimension.release_metadata_coverage_ratio, Decimal("0.5"))
            self.assertEqual(dimension.copy_metadata_coverage_ratio, Decimal(1) / Decimal(3))
            self.assertNotIn("Unknown", tuple(value.display_name for value in dimension.entries))
        self.assertIn(
            PortfolioDistributionDiagnosticCode.INVALID_RELEASE_YEAR,
            tuple(value.code for value in output.diagnostics),
        )

    def test_limited_and_insufficient_metadata_coverage(self):
        _, limited = analyse((
            row(1, artist="Artist", label=None, format=None, released=None),
        ))
        self.assertIs(limited.summary.evidence_coverage, PortfolioDistributionEvidenceCoverage.LIMITED)
        empty_result, empty = analyse(())
        self.assertIs(empty_result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(empty.summary.evidence_coverage, PortfolioDistributionEvidenceCoverage.INSUFFICIENT)
        no_metadata_result, no_metadata = analyse((row(1, artist=None, label=None, format=None, released=None),))
        self.assertIs(no_metadata_result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(no_metadata.summary.evidence_coverage, PortfolioDistributionEvidenceCoverage.INSUFFICIENT)

    def test_concentration_ties_are_canonical_and_non_interpretive(self):
        _, output = analyse((
            row(1, 2, artist="Beta"),
            row(2, 2, artist="Alpha"),
        ))
        artist = output.dimensions[0]
        self.assertEqual(tuple(value.display_name for value in artist.entries), ("Alpha", "Beta"))
        self.assertEqual(artist.concentration.largest_category_display_name, "Alpha")
        self.assertEqual(artist.concentration.tied_largest_category_count, 2)
        self.assertNotIn("risk", repr(artist.concentration).lower())
        with self.assertRaises(FrozenInstanceError):
            artist.represented_category_count = 3

    def test_rule_configuration_and_normalized_year_range_are_validated(self):
        with self.assertRaises(ValueError):
            PortfolioDistributionRuleConfiguration(2000, 1900)
        rules = PortfolioDistributionRuleConfiguration(1900, 2000)
        module = PortfolioDistributionModule(rules)
        supplied = PortfolioDistributionInput((
            PortfolioReleaseMetadataFact(1, 1, release_year=2001),
        ))
        with self.assertRaisesRegex(ValueError, "configured range"):
            module.analyse(IntelligenceContext(portfolio_distribution_input=supplied))

    def test_history_presentation_and_renderer_preserve_domain_order(self):
        result, output = analyse((
            row(2, artist="Beta", released="2000"),
            row(1, 2, artist="Alpha", released="1999"),
        ))
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        controller = DesktopPortfolioDistributionController(
            PortfolioDistributionPresentationService(PortfolioDistributionViewModelBuilder()),
            DesktopPortfolioDistributionRenderer(),
        )
        rendered = controller.open(result)
        self.assertEqual(rendered.title, "Portfolio Distribution")
        self.assertEqual(rendered.sections[1].title, "Artist distribution")
        body = "\n".join(value.body for value in rendered.sections)
        self.assertIn("Owned copies: 3", body)
        self.assertIn("Largest represented category", body)
        self.assertEqual(controller.open(None).sections, ())

    def test_execution_and_portfolio_navigation_call_each_boundary_once(self):
        class Collection:
            def __init__(self):
                self.calls = 0

            def owned_portfolio_metadata_rows(self):
                self.calls += 1
                return [row(1)]

        class Engine:
            def __init__(self):
                self.calls = []
                self.real = IntelligenceEngine((PortfolioDistributionModule(),))

            def execute(self, context):
                self.calls.append(context)
                return self.real.execute(context)

        collection, engine = Collection(), Engine()
        result = PortfolioDistributionExecutionService(collection, engine).execute()
        self.assertEqual(collection.calls, 1)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(result.module_id, "portfolio_distribution")

        class ExistingController:
            def __init__(self, value):
                self.value = value
                self.calls = []

            def open(self, supplied):
                self.calls.append(supplied)
                return self.value

        distribution = DesktopPortfolioDistributionController(
            PortfolioDistributionPresentationService(PortfolioDistributionViewModelBuilder())
        ).open(result)
        overview = type("Overview", (), {
            "headline": "Overview", "summary": "Supplied overview", "sections": ()
        })()
        overview_controller = ExistingController(overview)
        distribution_controller = ExistingController(distribution)
        concentration_controller = ExistingController(distribution)
        workspace = DesktopPortfolioController(
            overview_controller, distribution_controller, concentration_controller
        )
        rendered = workspace.open("overview-result", result, "concentration-result")
        self.assertEqual(overview_controller.calls, ["overview-result"])
        self.assertEqual(distribution_controller.calls, [result])
        self.assertEqual(
            tuple(value.destination for value in rendered.sections),
            (
                DesktopPortfolioDestination.OVERVIEW,
                DesktopPortfolioDestination.DISTRIBUTION,
                DesktopPortfolioDestination.CONCENTRATION,
            ),
        )


if __name__ == "__main__":
    unittest.main()
