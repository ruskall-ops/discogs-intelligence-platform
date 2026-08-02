from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dip.app.collector_run import (
    CollectorRunExecutionError,
    CollectorRunProgress,
    CollectorRunResult,
    CollectorRunStatus,
    CollectorRunUnavailableError,
)
from dip.experience.desktop.app import App
from dip.experience.desktop.collection_explorer_renderer import (
    DesktopCollectionExplorerController,
)


class _Service:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def run(self, token, callback):
        self.calls.append(token)
        if self.error is not None:
            raise self.error
        callback(CollectorRunProgress(2, 0, 0, 0))
        callback(CollectorRunProgress(2, 1, 1, 0, 3))
        return self.result


def _result(status):
    counts = {
        CollectorRunStatus.COMPLETED: (2, 0, ()),
        CollectorRunStatus.PARTIAL: (1, 1, (4,)),
        CollectorRunStatus.FAILED: (0, 2, (3, 4)),
    }
    succeeded, failed, failed_ids = counts[status]
    return CollectorRunResult(
        7,
        datetime(2026, 7, 25, tzinfo=timezone.utc),
        status,
        2,
        2,
        succeeded,
        failed,
        failed_ids,
    )


def _app():
    app = App.__new__(App)
    app._collector_run_active = False
    app._database_backup_active = False
    app.collector_run_service = None
    app.db = SimpleNamespace(release_ids=Mock(return_value=[3, 4]))
    app.refresh_discogs_button = Mock()
    app.import_csv_button = Mock()
    app.database_backup_button = Mock()
    app.progress = Mock()
    app.status_var = Mock()
    app.refresh_dashboard = Mock()
    app.load_table = Mock()
    return app


def _assert_import_available(app):
    with (
        patch(
            "dip.experience.desktop.app.filedialog.askopenfilename",
            return_value="",
        ) as chooser,
        patch(
            "dip.experience.desktop.app.messagebox.showwarning"
        ) as warning,
    ):
        app.import_csv()
    chooser.assert_called_once()
    warning.assert_not_called()


class CollectorRunDesktopTestCase(unittest.TestCase):
    def test_every_terminal_outcome_invalidates_cache_and_marks_only_live_windows_stale(self):
        stale_copy = "Marketplace history has changed. Refresh Marketplace Changes to update these results."
        class History:
            def __init__(self, operations): self.operations = operations
            def all_snapshots(self):
                self.operations["history"] += 1
                return ()
        class Metadata:
            def __init__(self, operations): self.operations = operations
            def metadata_for_release_ids(self, release_ids):
                self.operations["metadata"] += 1
                return ()
        class WorkspaceService:
            def __init__(self, operations):
                self.operations = operations
                self.history = History(operations)
                self.metadata = Metadata(operations)
            def build(self):
                self.operations["workspace"] += 1
                self.history.all_snapshots()
                self.metadata.metadata_for_release_ids(())
                return object()
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs): return kwargs
        class Renderer:
            def render(self, value): return value
        class Window:
            def __init__(self, live): self.live = live
            def winfo_exists(self): return self.live
        class Label:
            def __init__(self): self.text = "old"
            def configure(self, *, text): self.text = text
        class Button:
            def __init__(self): self.states = []
            def state(self, value): self.states.append(value)
        cases = {
            "zero": (),
            "one": (True,),
            "multiple": (True, True),
            "destroyed": (False,),
            "closed": (False,),
            "mixed": (True, False, True),
        }
        for status in CollectorRunStatus:
            for name, live_states in cases.items():
                with self.subTest(status=status, windows=name):
                    app = _app()
                    operations = {
                        "history": 0,
                        "metadata": 0,
                        "workspace": 0,
                        "replacement": 0,
                        "provider": 0,
                        "persistence": 0,
                    }
                    app._collector_run_active = True
                    app.collector_run_service = Mock()
                    app.db = Mock()
                    app._create_marketplace_replacement_toplevel = Mock(
                        side_effect=lambda: operations.__setitem__(
                            "replacement", operations["replacement"] + 1
                        )
                    )
                    workspace = WorkspaceService(operations)
                    controller = DesktopCollectionExplorerController(
                        Presentation(), Renderer(), workspace,
                        lambda: not app._collector_run_active,
                    )
                    old_cache = object()
                    controller._marketplace_cache = old_cache
                    controller._validate_marketplace_candidate = lambda value: value
                    app.collection_explorer_controller = controller
                    windows = tuple(Window(live) for live in live_states)
                    labels = {window: Label() for window in windows}
                    buttons = {window: Button() for window in windows}
                    app._marketplace_explorer_handles = {
                        window: (labels[window], buttons[window]) for window in windows
                    }
                    app.open_intelligence_explorer = Mock(
                        side_effect=lambda: operations.__setitem__(
                            "replacement", operations["replacement"] + 1
                        )
                    )
                    with patch("dip.experience.desktop.app.messagebox.showinfo"), patch("dip.experience.desktop.app.messagebox.showwarning"), patch("dip.experience.desktop.app.messagebox.showerror"):
                        app.finish_refresh(_result(status))
                    self.assertFalse(app._collector_run_active)
                    self.assertIsNone(controller.marketplace_cache)
                    app.open_intelligence_explorer.assert_not_called()
                    app._create_marketplace_replacement_toplevel.assert_not_called()
                    self.assertEqual(app.collector_run_service.mock_calls, [])
                    self.assertEqual(app.db.mock_calls, [])
                    self.assertEqual(
                        operations,
                        {
                            "history": 0,
                            "metadata": 0,
                            "workspace": 0,
                            "replacement": 0,
                            "provider": 0,
                            "persistence": 0,
                        },
                    )
                    for window in windows:
                        if window.live:
                            self.assertIn(window, app._marketplace_explorer_handles)
                            self.assertEqual(labels[window].text, stale_copy)
                            self.assertEqual(buttons[window].states, [["!disabled"]])
                        else:
                            self.assertNotIn(window, app._marketplace_explorer_handles)
                    app.refresh_discogs_button.configure.assert_called_with(state="normal")
                    app.import_csv_button.configure.assert_called_with(state="normal")
                    candidate = controller.refresh_marketplace_changes()
                    self.assertIsNotNone(candidate)
                    self.assertEqual(
                        operations,
                        {
                            "history": 1,
                            "metadata": 1,
                            "workspace": 1,
                            "replacement": 0,
                            "provider": 0,
                            "persistence": 0,
                        },
                    )
    def test_duplicate_start_is_prevented(self):
        app = _app()
        app._collector_run_active = True
        app.collector_run_service = Mock()

        app.start_refresh()

        app.db.release_ids.assert_not_called()
        app.collector_run_service.run.assert_not_called()

    def test_start_uses_daemon_worker_and_disables_controls(self):
        app = _app()
        app.collector_run_service = Mock()
        worker = Mock()
        with (
            patch(
                "dip.experience.desktop.app.simpledialog.askstring",
                return_value="temporary-token",
            ),
            patch(
                "dip.experience.desktop.app.threading.Thread",
                return_value=worker,
            ) as thread_type,
        ):
            app.start_refresh()

        self.assertTrue(app._collector_run_active)
        app.refresh_discogs_button.configure.assert_called_once_with(
            state="disabled"
        )
        app.import_csv_button.configure.assert_called_once_with(state="disabled")
        thread_type.assert_called_once_with(
            target=app.refresh_market_data,
            args=("temporary-token",),
            daemon=True,
        )
        worker.start.assert_called_once_with()

    def test_import_is_guarded_while_collector_run_is_active(self):
        app = _app()
        app._collector_run_active = True
        with (
            patch(
                "dip.experience.desktop.app.messagebox.showwarning"
            ) as warning,
            patch(
                "dip.experience.desktop.app.filedialog.askopenfilename"
            ) as chooser,
        ):
            app.import_csv()

        warning.assert_called_once()
        chooser.assert_not_called()

    def test_worker_schedules_progress_and_terminal_result(self):
        app = _app()
        result = _result(CollectorRunStatus.PARTIAL)
        app.collector_run_service = _Service(result)
        scheduled = []
        app.after = lambda delay, callback, *args: scheduled.append(
            (delay, callback, args)
        )

        app.refresh_market_data("temporary-token")

        self.assertEqual(app.collector_run_service.calls, ["temporary-token"])
        self.assertEqual(
            [item[1] for item in scheduled],
            [
                app.update_refresh_progress,
                app.update_refresh_progress,
                app.finish_refresh,
            ],
        )
        self.assertEqual(scheduled[-1][2], (result,))
        app.import_csv_button.configure.assert_not_called()

    def test_worker_start_failure_restores_controls(self):
        app = _app()
        app.collector_run_service = Mock()
        worker = Mock()
        worker.start.side_effect = RuntimeError("thread unavailable")
        with (
            patch(
                "dip.experience.desktop.app.simpledialog.askstring",
                return_value="temporary-token",
            ),
            patch(
                "dip.experience.desktop.app.threading.Thread",
                return_value=worker,
            ),
            patch(
                "dip.experience.desktop.app.messagebox.showerror"
            ) as message,
        ):
            app.start_refresh()

        self.assertFalse(app._collector_run_active)
        app.refresh_discogs_button.configure.assert_called_with(state="normal")
        app.import_csv_button.configure.assert_called_with(state="normal")
        message.assert_called_once()
        _assert_import_available(app)

    def test_worker_schedules_unexpected_error_without_token(self):
        app = _app()
        app.collector_run_service = _Service(
            error=RuntimeError("temporary-token")
        )
        scheduled = []
        app.after = lambda delay, callback, *args: scheduled.append(
            (callback, args)
        )

        app.refresh_market_data("temporary-token")

        self.assertEqual(scheduled[0][0], app.show_refresh_error)
        self.assertEqual(scheduled[0][1], ())
        app.import_csv_button.configure.assert_not_called()
        callback, args = scheduled[0]
        with patch("dip.experience.desktop.app.messagebox.showerror"):
            callback(*args)
        app.import_csv_button.configure.assert_called_with(state="normal")
        _assert_import_available(app)

    def test_unavailable_error_is_scheduled_and_restores_for_another_run(self):
        app = _app()
        app._collector_run_active = True
        app.collector_run_service = _Service(
            error=CollectorRunUnavailableError("No stored collection.")
        )
        scheduled = []
        app.after = lambda delay, callback, *args: scheduled.append(
            (callback, args)
        )
        worker = Mock()

        with (
            patch(
                "dip.experience.desktop.app.messagebox.showwarning"
            ) as warning,
            patch(
                "dip.experience.desktop.app.messagebox.showerror"
            ) as error,
        ):
            app.refresh_market_data("temporary-token")

            self.assertEqual(
                scheduled,
            [(app.show_refresh_unavailable, ())],
            )
            app.refresh_discogs_button.configure.assert_not_called()
            app.import_csv_button.configure.assert_not_called()
            app.status_var.set.assert_not_called()
            warning.assert_not_called()
            error.assert_not_called()

            callback, args = scheduled.pop()
            callback(*args)

            self.assertFalse(app._collector_run_active)
            app.refresh_discogs_button.configure.assert_called_with(
                state="normal"
            )
            app.import_csv_button.configure.assert_called_with(state="normal")
            app.refresh_dashboard.assert_not_called()
            app.load_table.assert_not_called()
            warning.assert_called_once()
            error.assert_not_called()
            _assert_import_available(app)

        with (
            patch(
                "dip.experience.desktop.app.simpledialog.askstring",
                return_value="another-token",
            ),
            patch(
                "dip.experience.desktop.app.threading.Thread",
                return_value=worker,
            ),
        ):
            app.start_refresh()
        self.assertTrue(app._collector_run_active)
        worker.start.assert_called_once_with()

    def test_execution_error_is_scheduled_and_restores_for_another_run(self):
        app = _app()
        app._collector_run_active = True
        application_error = CollectorRunExecutionError(None, 0, 0, 0)
        app.collector_run_service = _Service(error=application_error)
        scheduled = []
        app.after = lambda delay, callback, *args: scheduled.append(
            (callback, args)
        )
        worker = Mock()

        with (
            patch(
                "dip.experience.desktop.app.messagebox.showwarning"
            ) as warning,
            patch(
                "dip.experience.desktop.app.messagebox.showerror"
            ) as error,
        ):
            app.refresh_market_data("temporary-token")

            self.assertEqual(
                scheduled,
            [(app.show_refresh_error, ())],
            )
            app.refresh_discogs_button.configure.assert_not_called()
            app.import_csv_button.configure.assert_not_called()
            app.status_var.set.assert_not_called()
            warning.assert_not_called()
            error.assert_not_called()

            callback, args = scheduled.pop()
            callback(*args)

            self.assertFalse(app._collector_run_active)
            app.refresh_discogs_button.configure.assert_called_with(
                state="normal"
            )
            app.import_csv_button.configure.assert_called_with(state="normal")
            app.refresh_dashboard.assert_not_called()
            app.load_table.assert_not_called()
            error.assert_called_once()
            warning.assert_not_called()
            _assert_import_available(app)

        with (
            patch(
                "dip.experience.desktop.app.simpledialog.askstring",
                return_value="another-token",
            ),
            patch(
                "dip.experience.desktop.app.threading.Thread",
                return_value=worker,
            ),
        ):
            app.start_refresh()
        self.assertTrue(app._collector_run_active)
        worker.start.assert_called_once_with()

    def test_complete_and_partial_results_refresh_views_and_restore_controls(self):
        for status, message_method in (
            (CollectorRunStatus.COMPLETED, "showinfo"),
            (CollectorRunStatus.PARTIAL, "showwarning"),
        ):
            with self.subTest(status=status):
                app = _app()
                app._collector_run_active = True
                with patch(
                    f"dip.experience.desktop.app.messagebox.{message_method}"
                ) as message:
                    app.finish_refresh(_result(status))

                self.assertFalse(app._collector_run_active)
                app.refresh_discogs_button.configure.assert_called_with(
                    state="normal"
                )
                app.import_csv_button.configure.assert_called_with(
                    state="normal"
                )
                app.refresh_dashboard.assert_called_once_with()
                app.load_table.assert_called_once_with()
                message.assert_called_once()
                _assert_import_available(app)

    def test_terminal_status_survives_normal_table_refresh(self):
        app = _app()
        app._collector_run_active = True
        visible_status = {"value": ""}
        app.status_var.set.side_effect = (
            lambda value: visible_status.__setitem__("value", value)
        )
        app.status_var.get.side_effect = lambda: visible_status["value"]
        app.load_table.side_effect = (
            lambda: app.status_var.set("Showing 6 records")
        )

        with patch(
            "dip.experience.desktop.app.messagebox.showinfo"
        ) as message:
            app.finish_refresh(_result(CollectorRunStatus.COMPLETED))

        self.assertEqual(
            visible_status["value"],
            "Refresh complete — 2 successful, 0 errors",
        )
        message.assert_called_once_with(
            "Refresh complete",
            "Refresh complete — 2 successful, 0 errors",
        )

    def test_failed_and_unexpected_outcomes_restore_controls(self):
        app = _app()
        app._collector_run_active = True
        with patch(
            "dip.experience.desktop.app.messagebox.showerror"
        ) as message:
            app.finish_refresh(_result(CollectorRunStatus.FAILED))

        self.assertFalse(app._collector_run_active)
        app.import_csv_button.configure.assert_called_with(state="normal")
        app.refresh_dashboard.assert_not_called()
        app.load_table.assert_not_called()
        message.assert_called_once()
        _assert_import_available(app)

        app._collector_run_active = True
        with patch("dip.experience.desktop.app.messagebox.showerror"):
            app.show_refresh_error("safe error")
        self.assertFalse(app._collector_run_active)
        app.import_csv_button.configure.assert_called_with(state="normal")
        _assert_import_available(app)


if __name__ == "__main__":
    unittest.main()
