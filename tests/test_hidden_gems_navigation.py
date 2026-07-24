from __future__ import annotations

from pathlib import Path
import unittest

from dip.app import HiddenGemsPresentationService
from dip.experience.dashboard import (
    DashboardHomepageViewModel,
    DashboardHomepageViewModelBuilder,
)
from dip.experience.desktop import (
    DesktopHiddenGemsController,
    DesktopHiddenGemsRenderer,
)
from dip.experience.hidden_gems import (
    HiddenGemsDetailState,
    HiddenGemsDetailViewModelBuilder,
)

from tests.test_dashboard_homepage import execution, hidden_record
from tests.test_hidden_gems_experience import (
    available_section,
    candidate,
    source_candidate,
)


class HiddenGemsDesktopRenderingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = HiddenGemsDetailViewModelBuilder()
        self.renderer = DesktopHiddenGemsRenderer()

    def test_available_detail_renders_all_values_in_candidate_order(self) -> None:
        detail = self.builder.build(
            available_section(source_candidate(1), source_candidate(2))
        )

        rendered = self.renderer.render(detail)

        self.assertEqual(tuple(item.rank for item in rendered.candidates), (1, 2))
        self.assertIn("Artist 1", rendered.candidates[0].heading)
        self.assertIn("89.0/100", rendered.candidates[0].body)
        self.assertLess(
            rendered.candidates[0].body.index("Demand:"),
            rendered.candidates[0].body.index("Scarcity:"),
        )
        self.assertIn("Wants: 200", rendered.candidates[0].body)
        self.assertIn("Evidence 1.", rendered.candidates[0].body)

    def test_partial_candidate_renders_each_missing_value_as_unavailable(self) -> None:
        detail = self.builder.build(
            available_section(
                source_candidate(
                    1,
                    supporting_overrides={"community_rating": None},
                    factor_overrides={"community_rating": None},
                )
            )
        )

        rendered = self.renderer.render(detail)

        self.assertIs(rendered.state, HiddenGemsDetailState.PARTIAL)
        self.assertGreaterEqual(rendered.candidates[0].body.count("Unavailable"), 2)

    def test_loading_empty_and_unavailable_render_without_candidates(self) -> None:
        loading_homepage = DashboardHomepageViewModel.loading()
        empty_homepage = DashboardHomepageViewModelBuilder().build(
            execution(1, hidden_record(1, candidates=()))
        )
        unavailable_homepage = DashboardHomepageViewModelBuilder().build(None)
        controller = DesktopHiddenGemsController(
            HiddenGemsPresentationService(self.builder)
        )

        loading = controller.open(loading_homepage)
        empty = controller.open(empty_homepage)
        unavailable = controller.open(unavailable_homepage)

        self.assertEqual(loading.candidates, ())
        self.assertEqual(empty.headline, "No Hidden Gems found")
        self.assertEqual(empty.candidates, ())
        self.assertEqual(unavailable.headline, "Unavailable")
        self.assertEqual(unavailable.candidates, ())


class HiddenGemsNavigationTestCase(unittest.TestCase):
    def test_controller_uses_current_homepage_without_another_query(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(1, hidden_record(1, candidates=(candidate(1),)))
        )

        class RecordingPresentation:
            def __init__(self) -> None:
                self.homepages = []

            def detail_for_homepage(self, received):
                self.homepages.append(received)
                return HiddenGemsDetailViewModelBuilder().build(
                    received.section_for("hidden_gems")
                )

        presentation = RecordingPresentation()
        controller = DesktopHiddenGemsController(presentation)

        controller.open(homepage)

        self.assertEqual(presentation.homepages, [homepage])

    def test_navigation_is_hidden_for_loading_and_unavailable_states(self) -> None:
        controller = DesktopHiddenGemsController(
            HiddenGemsPresentationService(HiddenGemsDetailViewModelBuilder())
        )
        available = DashboardHomepageViewModelBuilder().build(
            execution(1, hidden_record(1, candidates=(candidate(1),)))
        )

        self.assertTrue(controller.can_open(available))
        self.assertFalse(controller.can_open(DashboardHomepageViewModelBuilder().build(None)))
        self.assertFalse(controller.can_open(DashboardHomepageViewModel.loading()))

    def test_dashboard_has_conditional_live_hidden_gems_navigation(self) -> None:
        root = Path(__file__).resolve().parents[1]
        app_source = (root / "src/dip/experience/desktop/app.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('text="Open Hidden Gems"', app_source)
        self.assertIn("command=self.open_hidden_gems", app_source)
        self.assertIn("self.hidden_gems_controller.can_open", app_source)
        self.assertIn("self.hidden_gems_button.pack_forget()", app_source)
        self.assertIn("self.hidden_gems_controller.open", app_source)
        self.assertIn("scrollbar.set", app_source)

    def test_experience_has_no_engine_module_or_persistence_coupling(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = (
            root / "src/dip/experience/hidden_gems/models.py",
            root / "src/dip/experience/hidden_gems/builder.py",
            root / "src/dip/app/hidden_gems_presentation.py",
            root / "src/dip/experience/desktop/hidden_gems_renderer.py",
        )

        for path in files:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("dip.persistence", source)
            self.assertNotIn("sqlite3", source)
            self.assertNotIn("HiddenGemsModule", source)
            self.assertNotIn("IntelligenceEngine", source)
            self.assertNotIn("hidden_gem_score", source)


if __name__ == "__main__":
    unittest.main()
