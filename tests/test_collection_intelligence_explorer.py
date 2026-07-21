from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from dip.experience.dashboard import (
    DashboardCardState,
    HiddenGemsCardViewModel,
    IntelligenceDashboardPresenter,
    IntelligenceDashboardViewModel,
)
from dip.experience.desktop.explorer_renderer import (
    DesktopExplorerController,
    DesktopExplorerRenderer,
)
from dip.experience.explorer import (
    CollectionHealthExplorerViewModel,
    CollectionIntelligenceExplorerPresenter,
    HiddenGemsExplorerViewModel,
    HistoricalIntelligenceExplorerViewModel,
)
from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus
from dip.intelligence.modules import (
    CollectionHealthModule,
    HiddenGemsModule,
    HistoricalIntelligenceModule,
)


def release(release_id: int, *, artist: str = "Artist", title: str = "Title"):
    return {
        "release_id": release_id,
        "artist": artist,
        "title": title,
        "label": "Label",
        "quantity": 1,
    }


def market(price: int = 10):
    return {
        "wants": 200,
        "copies_for_sale": 2,
        "community_rating": 4.5,
        "lowest_price": price,
    }


def snapshot(release_id: int, value: int, captured_at: str, *, artist="Artist", title="Title"):
    return {
        "release_id": release_id,
        "artist": artist,
        "title": title,
        "lowest_price": value,
        "captured_at": captured_at,
    }


def completed_dashboard() -> IntelligenceDashboardViewModel:
    collection = tuple(
        release(index, artist=f"Artist {index}", title=f"Title {index}")
        for index in range(1, 7)
    )
    marketplace = {index: market(index + 5) for index in range(1, 7)}
    context = IntelligenceContext(collection=collection, marketplace=marketplace)
    health = CollectionHealthModule().analyse(context)
    hidden = HiddenGemsModule().analyse(context)
    historical = HistoricalIntelligenceModule().analyse(
        IntelligenceContext(
            history={
                1: (
                    snapshot(1, 10, "2026-07-01T10:00:00Z", artist="A", title="One"),
                    snapshot(2, 20, "2026-07-01T10:00:00Z", artist="B", title="Two"),
                    snapshot(4, 40, "2026-07-01T10:00:00Z", artist="D", title="Four"),
                ),
                2: (
                    snapshot(1, 25, "2026-07-08T10:00:00Z", artist="A", title="One"),
                    snapshot(2, 15, "2026-07-08T10:00:00Z", artist="B", title="Two"),
                    snapshot(3, 30, "2026-07-08T10:00:00Z", artist="C", title="Three"),
                ),
            }
        )
    )
    return IntelligenceDashboardPresenter().present((health, hidden, historical))


class ExplorerPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.explorer = CollectionIntelligenceExplorerPresenter().present(
            completed_dashboard()
        )

    def test_collection_health_explorer_maps_existing_presentation_values(self) -> None:
        section = self.explorer.section_for("collection_health")
        self.assertIsInstance(section, CollectionHealthExplorerViewModel)
        self.assertEqual(section.state, DashboardCardState.READY)
        self.assertIsNotNone(section.overall_health)
        self.assertEqual(len(section.component_scores), 4)
        self.assertTrue(section.evidence)
        self.assertTrue(section.diagnostics)

    def test_hidden_gems_explorer_contains_all_ranked_explainable_releases(self) -> None:
        section = self.explorer.section_for("hidden_gems")
        self.assertIsInstance(section, HiddenGemsExplorerViewModel)
        self.assertEqual(section.total_hidden_gems, 6)
        self.assertEqual(len(section.ranked_releases), 6)
        self.assertTrue(section.ranked_releases[0].explanation)
        self.assertTrue(section.ranked_releases[0].evidence)
        self.assertFalse(hasattr(section.ranked_releases[0], "hidden_gem_score"))

    def test_historical_explorer_maps_full_drill_down(self) -> None:
        section = self.explorer.section_for("historical_intelligence")
        self.assertIsInstance(section, HistoricalIntelligenceExplorerViewModel)
        self.assertEqual(section.latest_snapshot, "08 Jul 2026 10:00")
        self.assertEqual(section.previous_snapshot, "01 Jul 2026 10:00")
        self.assertEqual(section.collection_size_change, 0)
        self.assertEqual(section.releases_added, 1)
        self.assertEqual(section.releases_removed, 1)
        self.assertEqual(section.added_releases[0].release_id, 3)
        self.assertEqual(section.removed_releases[0].release_id, 4)
        self.assertEqual(section.top_gainers[0].release_id, 1)
        self.assertEqual(section.top_decliners[0].release_id, 2)
        self.assertIn("previous 3/3", section.evidence_coverage)

    def test_explorer_models_are_immutable(self) -> None:
        section = self.explorer.section_for("collection_health")
        with self.assertRaises(FrozenInstanceError):
            section.summary = "Changed"  # type: ignore[misc]


class ExplorerStateTests(unittest.TestCase):
    def test_unavailable_dashboard_maps_three_unavailable_sections(self) -> None:
        dashboard = IntelligenceDashboardPresenter().present(())
        explorer = CollectionIntelligenceExplorerPresenter().present(dashboard)
        self.assertEqual(len(explorer.sections), 3)
        self.assertTrue(
            all(section.state == DashboardCardState.UNAVAILABLE for section in explorer.sections)
        )

    def test_insufficient_history_remains_informational(self) -> None:
        historical = HistoricalIntelligenceModule().analyse(IntelligenceContext())
        dashboard = IntelligenceDashboardPresenter().present((historical,))
        section = CollectionIntelligenceExplorerPresenter().present(
            dashboard
        ).section_for("historical_intelligence")
        self.assertEqual(section.state, DashboardCardState.INSUFFICIENT_HISTORY)
        self.assertIn("fewer than two", section.summary)

    def test_skipped_and_incomplete_states_are_preserved(self) -> None:
        skipped_hidden = HiddenGemsModule().analyse(IntelligenceContext())
        incomplete_health = IntelligenceResult(
            module_id="collection_health",
            status=IntelligenceStatus.COMPLETED,
            summary="Partial Collection Health evidence.",
            metrics={"component_scores": {}},
        )
        explorer = CollectionIntelligenceExplorerPresenter().present(
            IntelligenceDashboardPresenter().present(
                (incomplete_health, skipped_hidden)
            )
        )
        self.assertEqual(
            explorer.section_for("collection_health").state,
            DashboardCardState.INCOMPLETE,
        )
        self.assertEqual(
            explorer.section_for("hidden_gems").state,
            DashboardCardState.SKIPPED,
        )

    def test_failed_modules_remain_independent(self) -> None:
        failed = IntelligenceResult(
            module_id="hidden_gems",
            status=IntelligenceStatus.FAILED,
            summary="Hidden Gems failed.",
            diagnostics=("controlled",),
        )
        historical = HistoricalIntelligenceModule().analyse(IntelligenceContext())
        explorer = CollectionIntelligenceExplorerPresenter().present(
            IntelligenceDashboardPresenter().present((failed, historical))
        )
        self.assertEqual(explorer.section_for("hidden_gems").state, DashboardCardState.FAILED)
        self.assertEqual(
            explorer.section_for("historical_intelligence").state,
            DashboardCardState.INSUFFICIENT_HISTORY,
        )
        self.assertEqual(
            explorer.section_for("collection_health").state,
            DashboardCardState.UNAVAILABLE,
        )

    def test_invalid_section_mapping_is_isolated(self) -> None:
        wrong_card = HiddenGemsCardViewModel(
            module_id="collection_health",
            title="Wrong type",
            state=DashboardCardState.READY,
            total_hidden_gems=0,
            summary="Malformed dashboard input.",
        )
        explorer = CollectionIntelligenceExplorerPresenter().present(
            IntelligenceDashboardViewModel(cards=(wrong_card,))
        )
        self.assertEqual(
            explorer.section_for("collection_health").state,
            DashboardCardState.FAILED,
        )
        self.assertEqual(
            explorer.section_for("hidden_gems").state,
            DashboardCardState.UNAVAILABLE,
        )


class ExplorerRenderingAndNavigationTests(unittest.TestCase):
    def test_renderer_displays_all_three_sections_and_required_details(self) -> None:
        explorer = CollectionIntelligenceExplorerPresenter().present(
            completed_dashboard()
        )
        rendered = DesktopExplorerRenderer().render(explorer)
        self.assertEqual(len(rendered.sections), 3)
        self.assertIn("Component scores", rendered.sections[0].body)
        self.assertIn("Ranked releases", rendered.sections[1].body)
        self.assertIn("Evidence coverage", rendered.sections[2].body)
        self.assertIn("Added releases", rendered.sections[2].body)
        self.assertIn("Top decliners", rendered.sections[2].body)

    def test_navigation_controller_opens_explorer_from_dashboard_model(self) -> None:
        view = DesktopExplorerController().open(completed_dashboard())
        self.assertEqual(view.title, "Collection Intelligence Explorer")
        self.assertEqual(
            tuple(section.module_id for section in view.sections),
            ("collection_health", "hidden_gems", "historical_intelligence"),
        )


if __name__ == "__main__":
    unittest.main()
