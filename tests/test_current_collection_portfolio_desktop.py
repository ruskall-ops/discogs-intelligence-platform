"""Desktop Portfolio lifecycle and factual rendering, without a live provider."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dip.experience.current_collection_portfolio import (
    CurrentCollectionPortfolioPresentationBuilder,
    PortfolioDestination,
)
from dip.experience.desktop.app import App
from dip.experience.desktop.current_collection_portfolio_window import CurrentCollectionPortfolioWindow, portfolio_lines
from tests.test_current_collection_portfolio_presentation import _outcome, _row


class _Window:
    def __init__(self, *_args):
        self._workspace = None
        self.freshness = SimpleNamespace(get=lambda: self.fresh, set=self._set_fresh)
        self.fresh = "Loading…"
        self.focus_count = 0
        self.render_count = 0
        self.active = False
        self.window = SimpleNamespace(focus_get=lambda: None)

    def _set_fresh(self, value):
        self.fresh = value

    def alive(self):
        return True

    def focus(self):
        self.focus_count += 1

    def show(self, workspace, *, freshness, error=""):
        self._workspace = workspace
        self.fresh = freshness
        self.error = error
        self.render_count += 1

    def set_run_active(self, active):
        self.active = active


class CurrentCollectionPortfolioDesktopTestCase(unittest.TestCase):
    def test_disabled_refresh_keyboard_traversal_in_both_directions(self):
        focused = []
        def control(name, *, disabled=False):
            return SimpleNamespace(
                state=lambda: ("disabled",) if disabled else (),
                focus_set=lambda: focused.append(name),
            )

        navigation = control("navigation")
        refresh = control("refresh", disabled=True)
        text = control("text")
        close = control("close")
        window = CurrentCollectionPortfolioWindow.__new__(CurrentCollectionPortfolioWindow)
        window._focus_order = (navigation, refresh, text, close)
        window.alive = lambda: True

        self.assertEqual(window._traverse(refresh, 1), "break")
        self.assertEqual(window._traverse(refresh, -1), "break")
        self.assertEqual(focused, ["text", "navigation"])

    def setUp(self):
        self.app = App.__new__(App)
        self.app._collector_run_active = False
        self.app._current_collection_portfolio_window = None
        self.app.current_collection_portfolio_builder = CurrentCollectionPortfolioPresentationBuilder()
        self.app.current_collection_portfolio_execution = Mock()
        self.success, self.repository = _outcome((_row(1, quantity=2), _row(2, artist=None)))
        self.app.current_collection_portfolio_execution.execute.return_value = self.success

    def test_one_window_and_explicit_refresh_preserve_destination(self):
        with patch("dip.experience.desktop.app.CurrentCollectionPortfolioWindow", _Window):
            self.app.open_portfolio_overview()
            window = self.app._current_collection_portfolio_window
            self.assertEqual(window.fresh, "Current")
            self.assertIs(window._workspace.selected_destination, PortfolioDestination.DISTRIBUTION)
            self.assertEqual(self.app.current_collection_portfolio_execution.execute.call_count, 1)
            self.app.open_portfolio_overview()
            self.assertIs(self.app._current_collection_portfolio_window, window)
            self.assertEqual(window.focus_count, 2)
            self.assertEqual(self.app.current_collection_portfolio_execution.execute.call_count, 1)
            window._workspace = self.app.current_collection_portfolio_builder.select(
                window._workspace, PortfolioDestination.CONCENTRATION
            )
            self.app.refresh_current_collection_portfolio()
            self.assertEqual(self.app.current_collection_portfolio_execution.execute.call_count, 2)
            self.assertIs(window._workspace.selected_destination, PortfolioDestination.CONCENTRATION)

    def test_failure_preserves_prior_pair_and_outdated_state(self):
        with patch("dip.experience.desktop.app.CurrentCollectionPortfolioWindow", _Window):
            self.app.open_portfolio_overview()
        window = self.app._current_collection_portfolio_window
        previous = window._workspace
        self.app._mark_current_collection_portfolio_outdated()
        self.app.current_collection_portfolio_execution.execute.side_effect = RuntimeError("token SQL /private/path")
        self.app.refresh_current_collection_portfolio()
        self.assertIs(window._workspace, previous)
        self.assertEqual(window.fresh, "Out of date — collection data changed")
        self.assertNotIn("token", window.error)
        self.assertIn("could not be calculated", window.error)

    def test_first_failure_is_unavailable_and_active_run_blocks_both_operations(self):
        self.app.current_collection_portfolio_execution.execute.side_effect = RuntimeError("private")
        with patch("dip.experience.desktop.app.CurrentCollectionPortfolioWindow", _Window):
            self.app.open_portfolio_overview()
        window = self.app._current_collection_portfolio_window
        self.assertIsNone(window._workspace.distribution)
        self.assertEqual(window.fresh, "Unavailable")
        self.app._collector_run_active = True
        self.app._update_current_collection_portfolio_run_state()
        self.assertTrue(window.active)
        self.app.open_portfolio_overview()
        self.app.refresh_current_collection_portfolio()
        self.assertEqual(self.app.current_collection_portfolio_execution.execute.call_count, 1)

    def test_import_invalidates_after_commit_before_failed_display_refresh(self):
        window = _Window()
        window._workspace = CurrentCollectionPortfolioPresentationBuilder().build(self.success)
        window.fresh = "Current"
        self.app._current_collection_portfolio_window = window
        self.app.import_service = Mock()
        self.app.import_service.import_collection.return_value = SimpleNamespace(imported_records=2, invalid_release_ids=0)
        self.app.status_var = Mock()
        self.app.refresh_dashboard = Mock(side_effect=RuntimeError("display"))
        self.app.load_table = Mock(return_value=False)
        def display_refresh():
            self.assertEqual(window.fresh, "Out of date — collection data changed")
            raise RuntimeError("display")
        self.app.refresh_dashboard.side_effect = display_refresh
        with patch("dip.experience.desktop.app.filedialog.askopenfilename", return_value="synthetic.csv"), patch("dip.experience.desktop.app.messagebox.showerror"):
            self.app.import_csv()
        self.assertEqual(window.fresh, "Out of date — collection data changed")
        self.assertIsNotNone(window._workspace.distribution)

    def test_cancelled_and_rolled_back_import_leave_snapshot_current(self):
        window = _Window()
        window._workspace = CurrentCollectionPortfolioPresentationBuilder().build(self.success)
        window.fresh = "Current"
        self.app._current_collection_portfolio_window = window
        self.app.import_service = Mock()
        with patch("dip.experience.desktop.app.filedialog.askopenfilename", return_value=""):
            self.app.import_csv()
        self.app.import_service.import_collection.assert_not_called()
        self.assertEqual(window.fresh, "Current")
        self.app.import_service.import_collection.side_effect = RuntimeError("rollback")
        with patch("dip.experience.desktop.app.filedialog.askopenfilename", return_value="synthetic.csv"), patch("dip.experience.desktop.app.messagebox.showerror"):
            self.app.import_csv()
        self.assertEqual(window.fresh, "Current")

    def test_renderer_preserves_denominator_copy_and_both_bases(self):
        builder = CurrentCollectionPortfolioPresentationBuilder()
        workspace = builder.build(self.success)
        distribution = "\n".join(portfolio_lines(workspace))
        self.assertIn("Owned releases: 2", distribution)
        self.assertIn("Metadata: 1/2 (50.00%) releases", distribution)
        self.assertIn("Missing metadata", distribution)
        concentration = "\n".join(portfolio_lines(builder.select(workspace, PortfolioDestination.CONCENTRATION)))
        self.assertIn("Release membership", concentration)
        self.assertIn("Copy membership", concentration)
        self.assertIn("represented memberships only", concentration)
        self.assertIn("First 3 categories in Distribution order", concentration)
        self.assertNotIn("Opportunity Alignment", concentration)


if __name__ == "__main__":
    unittest.main()
