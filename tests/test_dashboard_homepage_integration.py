from __future__ import annotations

from pathlib import Path
import unittest

from dip.experience.dashboard import (
    DashboardHomepageViewModelBuilder,
    DashboardSectionId,
)
from dip.experience.desktop import DesktopDashboardHomepageRenderer

from tests.test_dashboard_homepage import (
    candidate,
    comparison_view_model,
    execution,
    health_record,
    hidden_record,
)


class DashboardHomepageRendererTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = DesktopDashboardHomepageRenderer()

    def test_homepage_renders_expected_section_headings_in_order(self) -> None:
        rendered = self.renderer.render(DashboardHomepageViewModelBuilder().build(None))

        self.assertEqual(
            tuple(section.section_id for section in rendered),
            tuple(DashboardSectionId),
        )
        self.assertEqual(
            tuple(section.title for section in rendered),
            (
                "Collection overview",
                "Collection Health",
                "Hidden Gems",
                "What Changed",
                "Latest execution",
            ),
        )

    def test_empty_and_first_run_states_render_safely(self) -> None:
        empty = self.renderer.render(DashboardHomepageViewModelBuilder().build(None))
        first_run = self.renderer.render(
            DashboardHomepageViewModelBuilder().build(
                execution(1, health_record(1))
            )
        )

        self.assertIn("No intelligence history", empty[0].body)
        self.assertIn("Insufficient history", first_run[3].body)
        self.assertIn("80.0/100", first_run[1].body)

    def test_available_data_renders_without_reordering_or_run_id(self) -> None:
        previous = execution(1, health_record(1, score=80.0))
        current = execution(
            2,
            health_record(2, score=82.0),
            hidden_record(2, candidates=(candidate(4), candidate(9))),
            engine_version="engine-2",
        )
        homepage = DashboardHomepageViewModelBuilder().build(
            current,
            comparison_view_model(current, previous),
        )

        rendered = self.renderer.render(homepage)

        self.assertIn("Collection size: 10", rendered[0].body)
        self.assertLess(rendered[2].body.index("Artist 4"), rendered[2].body.index("Artist 9"))
        self.assertIn("Collection Health — Changed", rendered[3].body)
        self.assertIn("Hidden Gems — Added", rendered[3].body)
        self.assertIn("Engine version: engine-2", rendered[4].body)
        self.assertNotIn("Run 2", rendered[4].body)

    def test_dashboard_presentation_code_has_no_persistence_dependency(self) -> None:
        root = Path(__file__).resolve().parents[1]
        presentation_files = (
            root / "src/dip/experience/dashboard/homepage.py",
            root / "src/dip/experience/dashboard/homepage_models.py",
            root / "src/dip/experience/desktop/homepage_renderer.py",
            root / "src/dip/experience/desktop/app.py",
        )

        for path in presentation_files:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("dip.persistence", source)
            self.assertNotIn("sqlite3", source)
            self.assertNotIn("IntelligenceHistoryRepository", source)


if __name__ == "__main__":
    unittest.main()
