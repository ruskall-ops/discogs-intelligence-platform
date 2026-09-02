from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
from time import perf_counter
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
from zipfile import ZipFile

from dip.experience.collector_review_presentation import (
    decision_row_values,
    observation_detail_sections,
)
from dip.experience.desktop.hidden_gems_renderer import DesktopHiddenGemsRenderer
from dip.experience.desktop.price_changes_renderer import DesktopPriceChangesRenderer
from dip.experience.desktop.supply_changes_renderer import DesktopSupplyChangesRenderer
from dip.experience.hidden_gems import HiddenGemsDetailViewModelBuilder
from dip.experience.price_changes import PriceChangesDetailViewModelBuilder
from dip.experience.reporting import render_markdown
from dip.experience.reporting.models import (
    AnalysisRunSummary,
    CollectionSummary,
    HistoricalSummary,
    IntelligenceReport,
    ReportMover,
)
from dip.experience.results_presentation import (
    FixedPresentationVocabulary,
    PresentationSurface,
    PresentationTerm,
    presentation_label,
    presentation_vocabulary,
)
from dip.experience.supply_changes import SupplyChangesDetailViewModelBuilder
from dip.exports import export_excel
from dip.intelligence import IntelligenceContext
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    PriceChangesModule,
    SupplyChangesModule,
)

from tests.test_collector_review_desktop import _workspace
from tests.test_hidden_gems_experience import available_section, source_candidate


UTC = timezone.utc
PREVIOUS = datetime(2026, 8, 1, tzinfo=UTC)
LATEST = datetime(2026, 8, 2, tzinfo=UTC)


class PresentationTerminologyTestCase(unittest.TestCase):
    def test_glossary_is_closed_frozen_exhaustive_and_surface_specific(self):
        values = tuple(presentation_vocabulary(term) for term in PresentationTerm)
        self.assertEqual(tuple(value.term for value in values), tuple(PresentationTerm))
        self.assertTrue(all(type(value) is FixedPresentationVocabulary for value in values))
        self.assertTrue(all(
            tuple(surface for surface, _label in value.labels)
            == tuple(PresentationSurface)
            for value in values
        ))
        self.assertEqual(
            presentation_label(PresentationTerm.PRICE_CHANGES),
            "Price Changes",
        )
        self.assertEqual(
            presentation_label(
                PresentationTerm.PRICE_CHANGES,
                PresentationSurface.LEGACY_MARKDOWN,
            ),
            "Price Changes 2.0",
        )
        self.assertEqual(
            presentation_label(PresentationTerm.PREVIOUS_SNAPSHOT),
            "Previous snapshot",
        )
        self.assertEqual(
            presentation_label(PresentationTerm.LATEST_SNAPSHOT),
            "Latest snapshot",
        )
        with self.assertRaises(FrozenInstanceError):
            values[0].term = PresentationTerm.LATEST_SNAPSHOT  # type: ignore[misc]
        with self.assertRaises(TypeError):
            presentation_label("TOKEN /private SQL personal-note")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            FixedPresentationVocabulary(
                PresentationTerm.COLLECTOR_RUN,
                ((PresentationSurface.SCREEN, " Collector Run"),),
            )

    def test_markdown_labels_legacy_analysis_without_changing_payload_values(self):
        mover = ReportMover(7, "Artist|Seven", "Title", 0, -2, Decimal("1.25"), Decimal("12.50"))
        report = IntelligenceReport(
            presentation_label(
                PresentationTerm.LEGACY_COLLECTOR_RUN_ANALYSIS,
                PresentationSurface.LEGACY_MARKDOWN,
            ),
            datetime(2026, 8, 3, 12, 30),
            CollectionSummary(10, 11, 1, 2, 3, 4),
            AnalysisRunSummary(9, "completed", "start", "complete", 10, 9, 1),
            HistoricalSummary(9, 8, 10, 4, 3, 2, 1, 40.0),
            [mover],
            [mover],
            [mover],
        )
        before = (
            report.collection,
            report.latest_run,
            report.historical,
            tuple(report.top_price_movers),
            tuple(report.top_demand_movers),
            tuple(report.top_scarcity_movers),
        )
        rendered = render_markdown(report)
        after = (
            report.collection,
            report.latest_run,
            report.historical,
            tuple(report.top_price_movers),
            tuple(report.top_demand_movers),
            tuple(report.top_scarcity_movers),
        )
        self.assertEqual(before, after)
        self.assertIn("# Legacy Collector Run analysis", rendered)
        self.assertIn("## Latest Collector Run", rendered)
        self.assertIn("## Legacy Collector Run analysis comparison", rendered)
        self.assertIn("## Legacy price movers", rendered)
        self.assertIn("7 | Artist\\|Seven | Title | +0 | -2 | +1.25 | +12.50%", rendered)
        self.assertIn("not Price Changes 2.0 or Supply Changes 2.0", rendered)

    def test_excel_changes_only_fixed_explanatory_copy_and_preserves_row_values(self):
        rows = (
            _Row(
                release_id=1,
                decision="Research further",
                priority="Monitor",
                opportunity_score=Decimal("0"),
                lowest_price=Decimal("0"),
                wants=0,
                copies_for_sale=0,
            ),
            _Row(
                release_id=2,
                decision="Consider selling",
                priority="Worth reviewing",
                opportunity_score=Decimal("-12.5"),
                lowest_price=Decimal("12.345"),
                wants=11,
                copies_for_sale=3,
            ),
        )
        before = tuple(dict(row) for row in rows)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.xlsx"
            export_excel(path, rows)
            with ZipFile(path) as workbook:
                strings = _shared_strings(workbook)
                sheet = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
                workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")
        self.assertEqual(tuple(dict(row) for row in rows), before)
        self.assertIn("Discogs Intelligence Platform — Legacy Collector Run review analysis", strings)
        self.assertIn("Research further", strings)
        self.assertIn("Consider selling", strings)
        self.assertIn("Monitor", strings)
        self.assertIn('name="Review"', workbook_xml)
        for exact_numeric in ("<v>0</v>", "<v>-12.5</v>", "<v>12.345</v>"):
            self.assertIn(exact_numeric, sheet)

    def test_documentation_preserves_screen_export_and_release_boundaries(self):
        documents = {
            path: Path(path).read_text(encoding="utf-8")
            for path in (
                "README.md",
                "PROJECT_BOOTSTRAP.md",
                "docs/Architecture.md",
                "docs/CollectorReview.md",
                "docs/CurrentProductState.md",
                "docs/Dashboard.md",
                "docs/Explorer.md",
                "docs/MarketplaceArchitecture.md",
                "docs/ReportingEngine.md",
                "docs/Roadmap.md",
            )
        }
        combined = "\n".join(documents.values())
        for label in (
            "Previous snapshot",
            "Latest snapshot",
            "Current catalogue metadata",
            "Collector Run",
            "Marketplace Changes",
            "Legacy Collector Run analysis",
        ):
            self.assertIn(label, combined)
        self.assertIn("unchanged", documents["docs/ReportingEngine.md"])
        self.assertIn("extend the previous v0.5.1 scope", documents["docs/Roadmap.md"])
        self.assertIn("current public personal-use release", documents["README.md"])
        self.assertNotIn("unreleased", documents["README.md"].lower())
        self.assertNotIn("VoiceOver certified", combined)


class RealisticPresentationVolumeTestCase(unittest.TestCase):
    def test_price_supply_hidden_gems_and_review_rendering_is_deterministic_and_bounded(self):
        previous, latest = _volume_snapshots(500)
        price_result = PriceChangesModule().analyse(
            IntelligenceContext(
                marketplace_comparison=MarketplaceSnapshotComparisonInput(previous, latest)
            )
        )
        supply_result = SupplyChangesModule().analyse(
            IntelligenceContext(
                marketplace_comparison=MarketplaceSnapshotComparisonInput(previous, latest)
            )
        )
        price_detail = PriceChangesDetailViewModelBuilder().build(price_result)
        supply_detail = SupplyChangesDetailViewModelBuilder().build(supply_result)
        price_tuple = price_detail.release_changes
        supply_tuple = supply_detail.changes
        hidden_detail = HiddenGemsDetailViewModelBuilder().build(
            available_section(*(source_candidate(value) for value in range(1, 76)))
        )
        hidden_tuple = hidden_detail.candidates

        started = perf_counter()
        with (
            patch.object(
                PriceChangesModule,
                "analyse",
                side_effect=AssertionError("rendering recalculated Price Changes"),
            ),
            patch.object(
                SupplyChangesModule,
                "analyse",
                side_effect=AssertionError("rendering recalculated Supply Changes"),
            ),
        ):
            price_first = DesktopPriceChangesRenderer().render(price_detail)
            price_second = DesktopPriceChangesRenderer().render(price_detail)
            supply_first = DesktopSupplyChangesRenderer().render(supply_detail)
            supply_second = DesktopSupplyChangesRenderer().render(supply_detail)
            hidden_first = DesktopHiddenGemsRenderer().render(hidden_detail)
            hidden_second = DesktopHiddenGemsRenderer().render(hidden_detail)

        self.assertEqual(price_first, price_second)
        self.assertEqual(supply_first, supply_second)
        self.assertEqual(hidden_first, hidden_second)
        self.assertIs(price_detail.release_changes, price_tuple)
        self.assertIs(supply_detail.changes, supply_tuple)
        self.assertIs(hidden_detail.candidates, hidden_tuple)
        self.assertEqual(
            tuple(candidate.rank for candidate in hidden_first.candidates),
            tuple(range(1, 76)),
        )
        self.assertEqual(
            tuple(row.release_id for row in price_first.release_changes),
            tuple(range(1, 501)),
        )
        self.assertEqual(
            tuple(row.release_id for row in supply_first.changes),
            tuple(range(1, 501)),
        )
        self.assertIn("Previous value: GBP 0", price_first.release_changes[0].body)
        self.assertIn("Latest value: GBP 0.25", price_first.release_changes[0].body)
        self.assertIn("Previous supply: 0", supply_first.changes[0].body)
        self.assertIn("Latest supply: 1", supply_first.changes[0].body)
        self.assertIn("Wants: 200", hidden_first.candidates[0].body)

        decision_rows = tuple(
            _Row(
                artist=f"Artist {value}",
                title=f"Title {value}",
                lowest_price=None if value % 2 else Decimal("0"),
                wants=None if value % 3 else 0,
                copies_for_sale=value % 5,
                opportunity_score=Decimal("-1.25") if value % 7 == 0 else Decimal("2.5"),
                sell_window="Stable",
                priority="Monitor" if value % 11 == 0 else "Worth reviewing",
                decision="Research further" if value % 13 == 0 else "Review",
            )
            for value in range(1, 1001)
        )
        decision_before = tuple(dict(row) for row in decision_rows)
        formatted = tuple(decision_row_values(row) for row in decision_rows)
        self.assertEqual(tuple(dict(row) for row in decision_rows), decision_before)
        self.assertEqual(len(formatted), 1000)
        self.assertEqual(formatted[0][2], "—")
        self.assertEqual(formatted[1][2], "0.00")
        self.assertIn("Research further", {row[-1] for row in formatted})
        self.assertIn("Monitor", {row[-2] for row in formatted})

        observations = _workspace(300).hot_now
        observation_before = tuple(observations)
        sections = tuple(observation_detail_sections(value) for value in observations)
        self.assertEqual(observations, observation_before)
        self.assertEqual(len(sections), 300)
        self.assertTrue(all(value[0].title == "Calculated observation" for value in sections))
        self.assertLess(perf_counter() - started, 10.0)

        hostile = "TOKEN provider SQL /private/personal.sqlite PERSONAL-NOTE"
        fixed_copy = repr(tuple(presentation_vocabulary(term) for term in PresentationTerm))
        self.assertNotIn(hostile, fixed_copy)
        for path in (
            "src/dip/experience/desktop/price_changes_renderer.py",
            "src/dip/experience/desktop/supply_changes_renderer.py",
            "src/dip/experience/desktop/hidden_gems_renderer.py",
            "src/dip/experience/collector_review_presentation.py",
        ):
            source = Path(path).read_text(encoding="utf-8")
            for forbidden in (
                "sqlite3",
                "requests",
                "all_snapshots(",
                "review_rows(",
                "save_",
                ".analyse(",
            ):
                self.assertNotIn(forbidden, source)


class _Row(dict):
    def __init__(self, **values):
        defaults = {
            "release_id": 0,
            "decision": "Review",
            "miss_rating": "",
            "protected": 0,
            "priority": "Not scored",
            "sell_window": "",
            "opportunity_score": None,
            "value_score": None,
            "demand_score": None,
            "liquidity_score": None,
            "momentum_score": None,
            "artist": "Artist",
            "title": "Title",
            "label": "Label",
            "catalog_no": "CAT",
            "wants": None,
            "haves": None,
            "copies_for_sale": None,
            "lowest_price": None,
            "explanation": "Explanation",
            "personal_notes": "",
            "discogs_uri": "",
        }
        defaults.update(values)
        super().__init__(defaults)


def _shared_strings(workbook: ZipFile) -> str:
    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    return "\n".join(
        "".join(node.itertext()) for node in root.findall("x:si", namespace)
    )


def _volume_snapshots(count: int) -> tuple[MarketplaceSnapshot, MarketplaceSnapshot]:
    previous = tuple(
        MarketplaceReleaseObservation(
            release_id,
            PREVIOUS,
            MarketplaceDataStatus.COMPLETE,
            lowest_price=MarketplaceMoney(Decimal(release_id - 1), "GBP"),
            num_for_sale=release_id - 1,
            num_wanted=release_id * 2,
        )
        for release_id in range(1, count + 1)
    )
    latest = tuple(
        MarketplaceReleaseObservation(
            release_id,
            LATEST,
            MarketplaceDataStatus.COMPLETE,
            lowest_price=MarketplaceMoney(Decimal(release_id - 1) + Decimal("0.25"), "GBP"),
            num_for_sale=release_id,
            num_wanted=release_id * 2,
        )
        for release_id in range(1, count + 1)
    )
    return (
        MarketplaceSnapshot("previous", PREVIOUS, "discogs", MarketplaceDataStatus.COMPLETE, previous, source_version="v2"),
        MarketplaceSnapshot("latest", LATEST, "discogs", MarketplaceDataStatus.COMPLETE, latest, source_version="v2"),
    )


if __name__ == "__main__":
    unittest.main()
