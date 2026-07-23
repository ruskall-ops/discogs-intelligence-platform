from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    CollectionHealthPresentationService,
    HiddenGemsPresentationService,
)
from dip.experience.collection_health import CollectionHealthDetailViewModelBuilder
from dip.experience.dashboard import (
    DashboardHomepageViewModel,
    DashboardHomepageViewModelBuilder,
    DashboardSectionState,
)
from dip.experience.desktop import (
    DesktopCollectionExplorerController,
    DesktopCollectionExplorerRenderer,
)
from dip.experience.desktop.collection_health_renderer import (
    DesktopCollectionHealthRenderer,
)
from dip.experience.desktop.hidden_gems_renderer import DesktopHiddenGemsRenderer
from dip.experience.explorer import (
    CollectionExplorerConsistencyError,
    CollectionExplorerDestination,
    CollectionExplorerState,
    CollectionExplorerViewModelBuilder,
)
from dip.experience.hidden_gems import HiddenGemsDetailViewModelBuilder
from dip.intelligence import IntelligenceStatus

from tests.test_dashboard_homepage import (
    comparison_view_model,
    execution,
    generic_record,
    health_record,
    hidden_record,
    record,
)
from tests.test_hidden_gems_experience import candidate


class CollectionExplorerModelTestCase(unittest.TestCase):
    def test_models_are_frozen_and_defensively_freeze_destinations(self) -> None:
        explorer = build_explorer(available_homepage())
        copied = replace(explorer, destinations=list(explorer.destinations))

        self.assertIsInstance(copied.destinations, tuple)
        with self.assertRaises(FrozenInstanceError):
            copied.state = CollectionExplorerState.ERROR  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            copied.overview.summary = "Changed"  # type: ignore[misc]

    def test_destination_identifiers_and_order_are_stable(self) -> None:
        explorer = build_explorer(available_homepage())

        self.assertEqual(
            tuple(item.destination for item in explorer.destinations),
            tuple(CollectionExplorerDestination),
        )
        self.assertEqual(
            tuple(item.label for item in explorer.destinations),
            (
                "Overview",
                "Collection Health",
                "Hidden Gems",
                "Collection Trends",
                "Weekend Listings",
                "Price Changes",
                "Supply Changes",
                "Rare Appearances",
                "Marketplace Activity",
                "Listing Lifecycle",
                "Marketplace Momentum",
                "Marketplace Stability",
            ),
        )

    def test_duplicate_and_reordered_destinations_are_rejected(self) -> None:
        explorer = build_explorer(available_homepage())
        duplicate = (
            explorer.destinations[0],
            explorer.destinations[1],
            explorer.destinations[1],
        )

        with self.assertRaisesRegex(CollectionExplorerConsistencyError, "unique"):
            replace(explorer, destinations=duplicate)
        with self.assertRaisesRegex(
            CollectionExplorerConsistencyError,
            "documented order",
        ):
            replace(explorer, destinations=tuple(reversed(explorer.destinations)))

    def test_selected_destination_and_top_level_state_are_validated(self) -> None:
        explorer = build_explorer(available_homepage())

        with self.assertRaises(TypeError):
            replace(explorer, selected_destination="overview")
        with self.assertRaisesRegex(CollectionExplorerConsistencyError, "contradicts"):
            replace(explorer, state=CollectionExplorerState.ERROR)

    def test_partial_state_is_derived_when_one_detail_is_unavailable(self) -> None:
        explorer = build_explorer(
            DashboardHomepageViewModelBuilder().build(
                execution(1, health_record(1))
            )
        )

        self.assertIs(explorer.state, CollectionExplorerState.PARTIAL)
        self.assertIs(
            explorer.destination_for("hidden_gems").state,
            CollectionExplorerState.UNAVAILABLE,
        )


class CollectionExplorerBuilderAndOverviewTestCase(unittest.TestCase):
    def test_no_history_is_an_explicit_empty_workspace(self) -> None:
        explorer = build_explorer(DashboardHomepageViewModelBuilder().build(None))

        self.assertIs(explorer.state, CollectionExplorerState.EMPTY)
        self.assertIs(explorer.overview.state, CollectionExplorerState.EMPTY)
        self.assertIn("No completed", explorer.overview.summary)
        self.assertIs(
            explorer.destination_for("collection_health").state,
            CollectionExplorerState.UNAVAILABLE,
        )

    def test_loading_source_builds_all_loading_destinations(self) -> None:
        explorer = build_explorer(DashboardHomepageViewModel.loading())

        self.assertIs(explorer.state, CollectionExplorerState.LOADING)
        self.assertTrue(
            all(
                destination.state is CollectionExplorerState.LOADING
                for destination in explorer.destinations
            )
        )

    def test_one_execution_preserves_typed_overview_values(self) -> None:
        explorer = build_explorer(available_homepage(health_score=12.3))
        overview = explorer.overview

        self.assertIs(overview.state, CollectionExplorerState.AVAILABLE)
        self.assertEqual(overview.collection_size, 10)
        self.assertIs(overview.execution_status, IntelligenceStatus.COMPLETED)
        self.assertEqual(overview.completed_module_count, 2)
        self.assertEqual(overview.total_module_count, 2)
        self.assertEqual(overview.run_id, 1)
        self.assertEqual(overview.engine_version, "engine-1")
        self.assertEqual(overview.collection_health_score, 12.3)
        self.assertNotEqual(overview.collection_health_score, 82.5)
        self.assertEqual(overview.hidden_gems_count, 2)

    def test_collection_size_can_remain_unavailable(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(1, generic_record(1, "another_module"))
        )

        explorer = build_explorer(homepage)

        self.assertIsNone(explorer.overview.collection_size)
        self.assertIs(explorer.state, CollectionExplorerState.PARTIAL)

    def test_hidden_gems_empty_is_usable_and_preserves_zero_count(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(
                1,
                health_record(1),
                hidden_record(1, candidates=()),
            )
        )

        explorer = build_explorer(homepage)

        self.assertEqual(explorer.overview.hidden_gems_count, 0)
        self.assertIs(
            explorer.destination_for("hidden_gems").state,
            CollectionExplorerState.EMPTY,
        )
        self.assertIs(explorer.state, CollectionExplorerState.AVAILABLE)

    def test_comparison_changed_unchanged_and_insufficient_history_are_copied(self) -> None:
        previous = execution(1, health_record(1, score=80.0))
        changed_current = execution(2, health_record(2, score=82.0))
        unchanged_current = execution(3, health_record(3, score=80.0))
        builder = DashboardHomepageViewModelBuilder()
        cases = (
            (
                builder.build(
                    changed_current,
                    comparison_view_model(changed_current, previous),
                ),
                "differs",
                DashboardSectionState.AVAILABLE,
            ),
            (
                builder.build(
                    unchanged_current,
                    comparison_view_model(unchanged_current, previous),
                ),
                "matches",
                DashboardSectionState.AVAILABLE,
            ),
            (
                builder.build(previous),
                "At least two",
                DashboardSectionState.INSUFFICIENT_HISTORY,
            ),
        )

        for homepage, expected, state in cases:
            with self.subTest(expected=expected):
                overview = build_explorer(homepage).overview
                self.assertIn(expected, overview.comparison_summary)
                self.assertIs(overview.comparison_state, state)

    def test_error_detail_degrades_only_its_destination(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(
                1,
                health_record(1),
                record(
                    1,
                    "hidden_gems",
                    status=IntelligenceStatus.FAILED,
                    metrics={},
                ),
            )
        )

        explorer = build_explorer(homepage)

        self.assertIs(explorer.state, CollectionExplorerState.PARTIAL)
        self.assertIs(
            explorer.destination_for("collection_health").state,
            CollectionExplorerState.AVAILABLE,
        )
        self.assertIs(
            explorer.destination_for("hidden_gems").state,
            CollectionExplorerState.ERROR,
        )


class CollectionExplorerPresentationServiceTestCase(unittest.TestCase):
    def test_same_homepage_instance_is_used_for_every_destination(self) -> None:
        homepage = available_homepage()
        real_health = health_service()
        real_hidden = hidden_service()

        class RecordingHealth:
            def __init__(self) -> None:
                self.received = []

            def detail_for_homepage(self, source):
                self.received.append(source)
                return real_health.detail_for_homepage(source)

        class RecordingHidden:
            def __init__(self) -> None:
                self.received = []

            def detail_for_homepage(self, source):
                self.received.append(source)
                return real_hidden.detail_for_homepage(source)

        health = RecordingHealth()
        hidden = RecordingHidden()
        service = CollectionExplorerPresentationService(
            health,
            hidden,
            CollectionExplorerViewModelBuilder(),
        )

        explorer = service.explorer_for_homepage(
            homepage,
            selected_destination=CollectionExplorerDestination.HIDDEN_GEMS,
        )

        self.assertEqual(health.received, [homepage])
        self.assertEqual(hidden.received, [homepage])
        self.assertIs(
            explorer.selected_destination,
            CollectionExplorerDestination.HIDDEN_GEMS,
        )

    def test_existing_detail_models_are_composed_without_copying(self) -> None:
        homepage = available_homepage()
        health = health_service().detail_for_homepage(homepage)
        hidden = hidden_service().detail_for_homepage(homepage)
        explorer = CollectionExplorerViewModelBuilder().build(
            homepage,
            health,
            hidden,
        )

        self.assertIs(explorer.collection_health, health)
        self.assertIs(explorer.hidden_gems, hidden)

    def test_unexpected_detail_failure_propagates(self) -> None:
        failure = RuntimeError("controlled detail failure")

        class BrokenHealth:
            def detail_for_homepage(self, homepage):
                raise failure

        service = CollectionExplorerPresentationService(
            BrokenHealth(),
            hidden_service(),
            CollectionExplorerViewModelBuilder(),
        )

        with self.assertRaises(RuntimeError) as raised:
            service.explorer_for_homepage(available_homepage())

        self.assertIs(raised.exception, failure)


class CollectionExplorerRenderingAndNavigationTestCase(unittest.TestCase):
    def test_renderer_preserves_destination_and_hidden_gems_order(self) -> None:
        first = replace(candidate(1), hidden_gem_score=12.3)
        second = replace(candidate(2), hidden_gem_score=99.9)
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(
                1,
                health_record(1),
                hidden_record(1, candidates=(first, second)),
            )
        )

        rendered = DesktopCollectionExplorerRenderer().render(
            build_explorer(homepage)
        )

        self.assertEqual(
            tuple(section.destination for section in rendered.sections),
            tuple(CollectionExplorerDestination),
        )
        hidden_body = rendered.sections[2].body
        self.assertLess(hidden_body.index("Artist 1"), hidden_body.index("Artist 2"))
        self.assertIn("12.3/100", hidden_body)

    def test_existing_detail_renderers_are_reused(self) -> None:
        class RecordingHealthRenderer:
            def __init__(self) -> None:
                self.received = []

            def render(self, detail):
                self.received.append(detail)
                return DesktopCollectionHealthRenderer().render(detail)

        class RecordingHiddenRenderer:
            def __init__(self) -> None:
                self.received = []

            def render(self, detail):
                self.received.append(detail)
                return DesktopHiddenGemsRenderer().render(detail)

        explorer = build_explorer(available_homepage())
        health = RecordingHealthRenderer()
        hidden = RecordingHiddenRenderer()

        DesktopCollectionExplorerRenderer(health, hidden).render(explorer)

        self.assertEqual(health.received, [explorer.collection_health])
        self.assertEqual(hidden.received, [explorer.hidden_gems])

    def test_controller_calls_presentation_once_and_selects_destination(self) -> None:
        homepage = available_homepage()
        real_service = explorer_service()

        class RecordingPresentation:
            def __init__(self) -> None:
                self.calls = []

            def explorer_for_homepage(self, source, *, selected_destination):
                self.calls.append((source, selected_destination))
                return real_service.explorer_for_homepage(
                    source,
                    selected_destination=selected_destination,
                )

        presentation = RecordingPresentation()
        controller = DesktopCollectionExplorerController(presentation)

        rendered = controller.open(
            homepage,
            selected_destination=CollectionExplorerDestination.COLLECTION_HEALTH,
        )

        self.assertEqual(
            presentation.calls,
            [(homepage, CollectionExplorerDestination.COLLECTION_HEALTH)],
        )
        self.assertIs(
            rendered.selected_destination,
            CollectionExplorerDestination.COLLECTION_HEALTH,
        )
        self.assertEqual(sum(item.selected for item in rendered.navigation), 1)

    def test_empty_and_unavailable_destinations_render_clear_text(self) -> None:
        rendered = DesktopCollectionExplorerRenderer().render(
            build_explorer(DashboardHomepageViewModelBuilder().build(None))
        )

        self.assertIn("No intelligence history", rendered.sections[0].body)
        self.assertIn("Unavailable", rendered.sections[1].body)
        self.assertIn("Unavailable", rendered.sections[2].body)

    def test_loading_homepage_is_stale_and_not_openable(self) -> None:
        self.assertFalse(
            DesktopCollectionExplorerController.can_open(
                DashboardHomepageViewModel.loading()
            )
        )
        self.assertTrue(
            DesktopCollectionExplorerController.can_open(
                DashboardHomepageViewModelBuilder().build(None)
            )
        )

    def test_explorer_code_has_no_engine_repository_or_sqlite_dependency(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = (
            root / "src/dip/experience/explorer/models.py",
            root / "src/dip/experience/explorer/builder.py",
            root / "src/dip/app/collection_explorer_presentation.py",
            root / "src/dip/experience/desktop/collection_explorer_renderer.py",
        )
        forbidden = (
            "dip.persistence",
            "sqlite3",
            "IntelligenceEngine",
            "IntelligenceHistoryQueryService",
            "HiddenGemsModule",
            "CollectionHealthModule",
        )

        for path in files:
            source = path.read_text(encoding="utf-8")
            for value in forbidden:
                self.assertNotIn(value, source)


class CollectionExplorerDesktopShellTestCase(unittest.TestCase):
    def test_dashboard_action_uses_current_homepage_and_scrollable_notebook(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "src/dip/experience/desktop/app.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('text="Open Collection Explorer"', source)
        self.assertIn("self.collection_explorer_controller.open", source)
        self.assertIn("self.current_dashboard_homepage", source)
        self.assertIn("ttk.Notebook", source)
        self.assertIn("notebook.select(selected_index)", source)
        self.assertIn("yscrollcommand=scrollbar.set", source)
        self.assertIn('text="Close"', source)

    def test_stale_protection_and_existing_navigation_remain(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "src/dip/experience/desktop/app.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("self.collection_explorer_controller.can_open", source)
        self.assertIn('state(["disabled"])', source)
        self.assertIn('text="Open Collection Health"', source)
        self.assertIn('text="Open Hidden Gems"', source)
        self.assertIn('text="Collection Review"', source)
        self.assertNotIn("current_intelligence_dashboard", source)
        self.assertNotIn("collection_intelligence_presentation.dashboard()", source)


def health_service() -> CollectionHealthPresentationService:
    return CollectionHealthPresentationService(CollectionHealthDetailViewModelBuilder())


def hidden_service() -> HiddenGemsPresentationService:
    return HiddenGemsPresentationService(HiddenGemsDetailViewModelBuilder())


def explorer_service() -> CollectionExplorerPresentationService:
    return CollectionExplorerPresentationService(
        health_service(),
        hidden_service(),
        CollectionExplorerViewModelBuilder(),
    )


def build_explorer(homepage: DashboardHomepageViewModel):
    return explorer_service().explorer_for_homepage(homepage)


def available_homepage(*, health_score: float = 80.0) -> DashboardHomepageViewModel:
    return DashboardHomepageViewModelBuilder().build(
        execution(
            1,
            health_record(1, score=health_score),
            hidden_record(1, candidates=(candidate(1), candidate(2))),
        )
    )


if __name__ == "__main__":
    unittest.main()
