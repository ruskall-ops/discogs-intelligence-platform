from __future__ import annotations

from pathlib import Path
import unittest

from dip.app import CollectionHealthPresentationService
from dip.experience.collection_health import (
    CollectionHealthDetailState,
    CollectionHealthDetailViewModel,
    CollectionHealthDetailViewModelBuilder,
)
from dip.experience.dashboard import (
    DashboardCollectionHealthViewModel,
    DashboardHomepageViewModelBuilder,
    DashboardSectionState,
)
from dip.experience.desktop import (
    DesktopCollectionHealthController,
    DesktopCollectionHealthRenderer,
    DesktopCollectionHealthSectionId,
)
from dip.intelligence import IntelligenceStatus

from tests.test_collection_health_experience import available_section
from tests.test_dashboard_homepage import execution, health_record


class CollectionHealthDesktopRenderingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = CollectionHealthDetailViewModelBuilder()
        self.renderer = DesktopCollectionHealthRenderer()

    def test_available_detail_renders_all_sections_in_explicit_order(self) -> None:
        rendered = self.renderer.render(self.builder.build(available_section()))

        self.assertEqual(rendered.title, "Collection Health")
        self.assertEqual(rendered.headline, "Overall health: 47.8/100")
        self.assertEqual(
            tuple(section.section_id for section in rendered.sections),
            tuple(DesktopCollectionHealthSectionId),
        )
        self.assertIn("Metadata completeness: 11.1/100", rendered.sections[0].body)
        self.assertIn("Core metadata", rendered.sections[1].body)
        self.assertIn("Refresh marketplace", rendered.sections[2].body)
        self.assertIn("10 collection releases", rendered.sections[3].body)
        self.assertIn("Prepared context", rendered.sections[4].body)

    def test_loading_and_unavailable_states_render_without_detail_sections(self) -> None:
        loading = self.renderer.render(
            self.builder.build(
                DashboardCollectionHealthViewModel(
                    state=DashboardSectionState.LOADING,
                    card=None,
                )
            )
        )
        unavailable_detail = CollectionHealthPresentationService(
            self.builder
        ).detail_for_homepage(DashboardHomepageViewModelBuilder().build(None))
        unavailable = self.renderer.render(unavailable_detail)

        self.assertIs(unavailable.state, CollectionHealthDetailState.UNAVAILABLE)
        self.assertEqual(unavailable.headline, "Unavailable")
        self.assertEqual(unavailable.sections, ())
        self.assertIs(loading.state, CollectionHealthDetailState.LOADING)
        self.assertEqual(loading.headline, "Loading")
        self.assertEqual(loading.sections, ())

    def test_empty_state_renders_existing_module_guidance(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(
                1,
                health_record(
                    1,
                    score=0.0,
                    collection_size=0,
                    status=IntelligenceStatus.SKIPPED,
                ),
            )
        )
        rendered = DesktopCollectionHealthController(
            CollectionHealthPresentationService(self.builder)
        ).open(homepage)

        self.assertIs(rendered.state, CollectionHealthDetailState.EMPTY)
        self.assertIn("0.0/100", rendered.headline)

    def test_error_state_renders_diagnostics_without_inventing_values(self) -> None:
        rendered = self.renderer.render(
            CollectionHealthDetailViewModel(
                state=CollectionHealthDetailState.ERROR,
                summary="Collection Health could not be completed.",
                diagnostics=("Controlled module failure.",),
            )
        )

        self.assertIn("Unable to display", rendered.headline)
        self.assertIn("No component scores", rendered.sections[0].body)
        self.assertIn("Controlled module failure", rendered.sections[-1].body)


class CollectionHealthNavigationTestCase(unittest.TestCase):
    def test_controller_opens_detail_from_current_homepage(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(1, health_record(1, score=72.5))
        )
        controller = DesktopCollectionHealthController(
            CollectionHealthPresentationService(
                CollectionHealthDetailViewModelBuilder()
            )
        )

        rendered = controller.open(homepage)

        self.assertEqual(rendered.title, "Collection Health")
        self.assertIn("72.5/100", rendered.headline)

    def test_dashboard_has_a_live_collection_health_navigation_action(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app_source = (
            root / "src/dip/experience/desktop/app.py"
        ).read_text(encoding="utf-8")

        self.assertIn('text="Open Collection Health"', app_source)
        self.assertIn("command=self.open_collection_health", app_source)
        self.assertIn("self.collection_health_controller.open", app_source)

    def test_experience_and_renderer_have_no_intelligence_or_persistence_coupling(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = (
            root / "src/dip/experience/collection_health/models.py",
            root / "src/dip/experience/collection_health/builder.py",
            root / "src/dip/experience/desktop/collection_health_renderer.py",
        )

        for path in files:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("dip.persistence", source)
            self.assertNotIn("sqlite3", source)
            self.assertNotIn("CollectionHealthModule", source)
            self.assertNotIn("component_weights", source)


if __name__ == "__main__":
    unittest.main()
