from __future__ import annotations

import importlib.metadata
import importlib.resources
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import dip
from dip.app import main
from dip.experience.dashboard import (
    DashboardCommandCardId,
    DashboardCommandCenterBuilder,
    DashboardHomepageViewModelBuilder,
)
from dip.experience.history_explorer import HistoryExplorerStateBuilder
from dip.experience.dashboard import DashboardNavigationTarget
from dip.experience.desktop.app import App
from dip.experience.desktop.app import _UNAVAILABLE_EXPLORER_DESTINATIONS
from dip.experience.explorer import CollectionExplorerDestination
from dip.experience.marketplace_workspace import MarketplaceWorkspaceStateBuilder
from dip.experience.project_workspace import ProjectWorkspaceNavigationTarget
from dip.persistence.sqlite import Database
from tests.test_portfolio_workspace import presentation as portfolio_presentation


class ReleaseHardeningTestCase(unittest.TestCase):
    def test_current_documents_describe_the_prepared_release_candidate(self) -> None:
        root = Path(__file__).resolve().parents[1]
        names = (
            "README.md",
            "PROJECT_BOOTSTRAP.md",
            "docs/Roadmap.md",
            "docs/SessionRestoration.md",
            "docs/CollectorReview.md",
            "docs/Architecture.md",
            "docs/BackupAndRecovery.md",
            "docs/CurrentProductState.md",
            "docs/Configuration.md",
            "docs/Database.md",
        )
        documents = tuple(
            (name, (root / name).read_text(encoding="utf-8"))
            for name in names
        )
        current_state_names = {
            "README.md",
            "PROJECT_BOOTSTRAP.md",
            "docs/Roadmap.md",
            "docs/Architecture.md",
            "docs/BackupAndRecovery.md",
            "docs/CurrentProductState.md",
            "docs/Configuration.md",
        }
        for name, document in documents:
            with self.subTest(document=name):
                normalized = " ".join(document.lower().split())
                self.assertNotIn("v0.5.1 was released", normalized)
                self.assertNotIn("v0.5.1 is the current public", normalized)
                self.assertNotIn("v0.5.1 is tagged", normalized)
                self.assertNotIn("v0.5.1 is published", normalized)
                self.assertNotIn("released dip v0.5.1", normalized)
                self.assertNotIn("status: released 2 august 2026", normalized)
                if name in current_state_names:
                    self.assertIn("prepared release candidate", normalized)
                    self.assertIn("implemented and validated", normalized)
                    self.assertIn("awaiting release completion", normalized)
        combined = "\n".join(document for _, document in documents).lower()
        self.assertIn("0.5.1", combined)
        self.assertIn("v0.5.0 remains the latest completed", combined)

        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(
            "Version 0.5.1 — Marketplace Change Explorer",
            changelog,
        )
        self.assertIn("Released 2 August 2026.", changelog)

    def test_release_checklist_targets_v0_5_1_in_required_order(self) -> None:
        root = Path(__file__).resolve().parents[1]
        checklist = (root / "docs/ReleaseChecklist.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("| `RELEASE_VERSION` | `0.5.1` |", checklist)
        self.assertIn("| `RELEASE_TAG` | `v0.5.1` |", checklist)
        self.assertIn("| `RELEASE_BRANCH` | `release/v0.5.1` |", checklist)
        self.assertIn(
            "| `RELEASE_TITLE` | `DIP v0.5.1 — Marketplace Change Explorer` |",
            checklist,
        )
        self.assertIn("| `PREVIOUS_TAG` | `v0.5.0` |", checklist)

        self.assertNotIn("git tag -a v0.5.0", checklist)
        self.assertNotIn("git push origin v0.5.0", checklist)
        self.assertNotIn("gh release create v0.5.0", checklist)
        self.assertIn("git tag -a v0.5.1", checklist)
        self.assertIn("git push origin v0.5.1", checklist)
        self.assertIn("gh release create v0.5.1", checklist)

        ordered_gates = (
            "1. Prepare release changes",
            "2. Validate the complete candidate",
            "3. Obtain independent read-only approval",
            "4. Commit the approved release preparation",
            "5. Push only the `release/v0.5.1` branch",
            "6. Open a pull request",
            "7. Require Linux and macOS CI to pass",
            "8. Review and merge the pull request",
            "9. Fetch/prune and synchronize local `main`",
            "10. Verify that local `main` equals `origin/main`",
            "11. Rebuild and install the wheel and source distribution",
            "12. Perform the final installed macOS verification",
            "13. Create the annotated `v0.5.1` tag",
            "14. Verify locally that `v0.5.1^{commit}`",
            "15. Push only the `v0.5.1` tag",
            "16. Create the GitHub release titled",
            "17. Verify the GitHub release title",
            "18. Complete post-release documentation housekeeping",
        )
        positions = tuple(checklist.index(gate) for gate in ordered_gates)
        self.assertEqual(positions, tuple(sorted(positions)))

        self.assertIn("## Manual GitHub website path", checklist)
        self.assertIn("Draft a new release", checklist)
        self.assertIn("Select the existing verified tag `v0.5.1`", checklist)
        self.assertIn("## Optional GitHub CLI path", checklist)

    def test_runtime_packaging_entry_point_and_schema_contract(self) -> None:
        self.assertEqual(dip.__version__, "0.5.1")
        distribution = importlib.metadata.distribution(
            "discogs-intelligence-platform"
        )
        entry_points = {
            value.name: value.value for value in distribution.entry_points
        }
        self.assertEqual(entry_points["dip"], "dip.app:main")
        schema = importlib.resources.files("dip.persistence.sqlite").joinpath(
            "schema.sql"
        )
        self.assertTrue(schema.is_file())

    def test_fresh_database_has_current_migrations_and_no_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "fresh.db")
            try:
                versions = tuple(
                    row[0]
                    for row in database.conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                )
                self.assertEqual(versions, tuple(range(1, 8)))
                migration_directory = (
                    Path(__file__).resolve().parents[1]
                    / "src/dip/persistence/sqlite/migrations/versions"
                )
                self.assertEqual(tuple(migration_directory.glob("v008_*.py")), ())
                self.assertEqual(
                    database.conn.execute(
                        "SELECT COUNT(*) FROM desktop_session"
                    ).fetchone()[0],
                    0,
                )
            finally:
                database.close()

    def test_application_entry_point_reports_fixed_safe_startup_failure(self) -> None:
        sentinel = "token SQL /private/database.db personal note"
        with (
            patch(
                "dip.experience.desktop.app.App",
                side_effect=RuntimeError(sentinel),
            ),
            patch("tkinter.messagebox.showerror") as error,
        ):
            main()
        visible = " ".join(str(value) for value in error.call_args.args)
        self.assertEqual(
            error.call_args.args[1],
            "DIP could not start. The application database or configuration "
            "could not be opened.",
        )
        self.assertNotIn(sentinel, visible)

    def test_dashboard_foundation_actions_are_disabled_but_collection_is_enabled(
        self,
    ) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(None)
        portfolio = portfolio_presentation().workspace()
        marketplace = MarketplaceWorkspaceStateBuilder().build(())
        history = HistoryExplorerStateBuilder().build()
        dashboard = DashboardCommandCenterBuilder().build(
            homepage, portfolio, marketplace, history
        )
        cards = {card.card_id: card for card in dashboard.cards}
        self.assertTrue(
            cards[DashboardCommandCardId.PORTFOLIO_HEALTH].actions[0].enabled
        )
        for card_id in (
            DashboardCommandCardId.PORTFOLIO_SUMMARY,
            DashboardCommandCardId.OPPORTUNITY_HIGHLIGHTS,
            DashboardCommandCardId.HISTORICAL_CHANGES,
            DashboardCommandCardId.MARKETPLACE_HIGHLIGHTS,
            DashboardCommandCardId.RESEARCH_SUMMARY,
        ):
            self.assertFalse(cards[card_id].actions[0].enabled)
            self.assertEqual(cards[card_id].summary, "Not available in this release")

    def test_navigation_dispatchers_fail_closed_for_unavailable_targets(
        self,
    ) -> None:
        application = App.__new__(App)
        application.open_intelligence_explorer = Mock()
        application.open_portfolio_overview = Mock()
        application.open_intelligence_change_analysis = Mock()
        application.open_marketplace_workspace = Mock()
        for target in DashboardNavigationTarget:
            application._open_dashboard_target(target)
        application.open_intelligence_explorer.assert_called_once_with()
        application.open_portfolio_overview.assert_not_called()
        application.open_intelligence_change_analysis.assert_not_called()
        application.open_marketplace_workspace.assert_not_called()
        application._open_dashboard_target(object())

        application.tabs = Mock()
        application.dashboard_tab = object()
        for target in ProjectWorkspaceNavigationTarget:
            application._open_project_target(target)
        application.tabs.select.assert_called_once_with(
            application.dashboard_tab
        )
        application.open_portfolio_overview.assert_not_called()
        application._open_project_target(object())

    def test_direct_workspace_handlers_do_not_open_unavailable_foundations(
        self,
    ) -> None:
        application = App.__new__(App)
        application.portfolio_workspace_controller = Mock()
        application.intelligence_change_analysis_controller = Mock()
        application.marketplace_workspace_controller = Mock()
        with patch("dip.experience.desktop.app.tk.Toplevel") as window:
            application.open_portfolio_overview()
            application.open_intelligence_change_analysis()
            application.open_marketplace_workspace()
        application.portfolio_workspace_controller.assert_not_called()
        application.intelligence_change_analysis_controller.assert_not_called()
        application.marketplace_workspace_controller.assert_not_called()
        window.assert_not_called()

    def test_export_failures_use_fixed_safe_messages(self) -> None:
        sentinel = (
            "token provider-body SQL /private/database.db "
            "/tmp/export personal-note serialized-payload row-value"
        )
        application = App.__new__(App)
        application.db = Mock()
        application.db.review_rows.side_effect = RuntimeError(sentinel)
        with (
            patch(
                "dip.experience.desktop.app.filedialog.asksaveasfilename",
                return_value="/tmp/private-report.xlsx",
            ),
            patch(
                "dip.experience.desktop.app.messagebox.showerror"
            ) as error,
        ):
            application.export_report()
        self.assertEqual(
            error.call_args.args[1],
            "The Excel report could not be exported.",
        )
        self.assertNotIn(sentinel, " ".join(map(str, error.call_args.args)))

        with (
            patch(
                "dip.experience.desktop.app.filedialog.asksaveasfilename",
                return_value="/tmp/private-report.md",
            ),
            patch(
                "dip.experience.desktop.app.ReportingService",
                side_effect=RuntimeError(sentinel),
            ),
            patch(
                "dip.experience.desktop.app.messagebox.showerror"
            ) as error,
        ):
            application.export_intelligence_report()
        self.assertEqual(
            error.call_args.args[1],
            "The Intelligence report could not be exported.",
        )
        self.assertNotIn(sentinel, " ".join(map(str, error.call_args.args)))

    def test_export_success_shows_filename_only(self) -> None:
        application = App.__new__(App)
        application.db = Mock()
        application.db.review_rows.return_value = ()
        with (
            patch(
                "dip.experience.desktop.app.filedialog.asksaveasfilename",
                return_value="/private/collector/export.xlsx",
            ),
            patch("dip.experience.desktop.app.export_excel"),
            patch(
                "dip.experience.desktop.app.messagebox.showinfo"
            ) as success,
        ):
            application.export_report()
        visible = " ".join(map(str, success.call_args.args))
        self.assertIn("export.xlsx", visible)
        self.assertNotIn("/private/collector", visible)

    def test_changed_architecture_documents_match_disabled_production(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dashboard = (root / "docs/Dashboard.md").read_text(
            encoding="utf-8"
        )
        architecture = (root / "docs/Architecture.md").read_text(
            encoding="utf-8"
        )
        current = (root / "docs/CurrentProductState.md").read_text(
            encoding="utf-8"
        )
        combined = "\n".join((dashboard, architecture, current))
        self.assertIn("Not available in this release", combined)
        self.assertIn("do not invoke", combined)
        self.assertNotIn(
            "currently navigate to visible placeholder",
            combined,
        )
        self.assertNotIn(
            "Its actions open existing workspace controllers",
            combined,
        )

    def test_explorer_marketplace_availability_matrix_is_exact(self) -> None:
        self.assertEqual(
            _UNAVAILABLE_EXPLORER_DESTINATIONS,
            frozenset(
                (
                    CollectionExplorerDestination.WEEKEND_LISTINGS,
                    CollectionExplorerDestination.RARE_APPEARANCES,
                    CollectionExplorerDestination.MARKETPLACE_ACTIVITY,
                    CollectionExplorerDestination.LISTING_LIFECYCLE,
                    CollectionExplorerDestination.MARKETPLACE_MOMENTUM,
                    CollectionExplorerDestination.MARKETPLACE_STABILITY,
                    CollectionExplorerDestination.MARKETPLACE_SCARCITY,
                    CollectionExplorerDestination.MARKETPLACE_OPPORTUNITY,
                )
            ),
        )
        for enabled in (
            CollectionExplorerDestination.OVERVIEW,
            CollectionExplorerDestination.COLLECTION_HEALTH,
            CollectionExplorerDestination.HIDDEN_GEMS,
            CollectionExplorerDestination.COLLECTION_TRENDS,
        ):
            self.assertNotIn(
                enabled,
                _UNAVAILABLE_EXPLORER_DESTINATIONS,
            )


if __name__ == "__main__":
    unittest.main()
