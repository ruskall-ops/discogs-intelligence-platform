from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from dip.collection.services import ImportService, ImportSummary
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
from dip.persistence.sqlite import Database


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
    app.refresh_dashboard = Mock(return_value=True)
    app.load_table = Mock(return_value=True)
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


class _Variable:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value


class _Tree:
    def get_children(self):
        return ()

    def delete(self, item):
        raise AssertionError("an empty tree must not delete rows")

    def insert(self, *args, **kwargs):
        raise AssertionError("the test display database returns no rows")


class _DisplayDatabase:
    def __init__(self, *, dashboard_fails=False, table_fails=False):
        self.dashboard_fails = dashboard_fails
        self.table_fails = table_fails
        self.dashboard_calls = 0
        self.table_calls = 0

    def dashboard(self):
        self.dashboard_calls += 1
        if self.dashboard_fails:
            raise RuntimeError("HOSTILE DASHBOARD")
        return {}

    def review_rows(self, **kwargs):
        self.table_calls += 1
        if self.table_fails:
            raise RuntimeError("HOSTILE TABLE")
        return []


class CollectorRunDesktopTestCase(unittest.TestCase):
    def test_every_terminal_outcome_retains_cache_and_marks_only_live_windows_stale(self):
        stale_copy = "Newer history is available\nThese cached results predate the latest completed Collector Run."
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
                    self.assertIs(controller.marketplace_cache, old_cache)
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
                            self.assertEqual(buttons[window].states[-1], ["!disabled"])
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


class CSVImportDesktopLifecycleTestCase(unittest.TestCase):
    @staticmethod
    def _import_app(*, import_effect=None):
        app = _app()
        summary = ImportSummary(3, 3, 3, 0)
        app.import_service = SimpleNamespace(
            import_collection=Mock(
                side_effect=import_effect,
                return_value=summary,
            )
        )
        return app

    @staticmethod
    def _real_display_app(display_database):
        app = _app()
        app.db = display_database
        app.refresh_dashboard = App.refresh_dashboard.__get__(app, App)
        app.load_table = App.load_table.__get__(app, App)
        app.tree = _Tree()
        app.search_var = _Variable()
        app.priority_var = _Variable("All")
        app.decision_filter_var = _Variable("All")
        app.kpis = {}
        app.collector_review_observations = None
        app._apply_hot_now_dashboard_state = Mock()
        app._render_observations = Mock()
        app.refresh_intelligence_dashboard = Mock()
        return app

    def test_success_runs_each_phase_once_and_notifies_completion(self):
        app = self._import_app()

        with (
            patch(
                "dip.experience.desktop.app.filedialog.askopenfilename",
                return_value="collection.csv",
            ),
            patch("dip.experience.desktop.app.messagebox.showinfo") as info,
            patch("dip.experience.desktop.app.messagebox.showerror") as error,
        ):
            app.import_csv()

        app.import_service.import_collection.assert_called_once_with(
            Path("collection.csv")
        )
        app.status_var.set.assert_called_once_with(
            "Imported 3 collection rows (0 invalid rows skipped)"
        )
        app.refresh_dashboard.assert_called_once_with()
        app.load_table.assert_called_once_with(report_failure=False)
        info.assert_called_once()
        error.assert_not_called()

    def test_import_failure_shows_only_fixed_import_failure_copy(self):
        hostile = "HOSTILE ROW PATH SQL TOKEN"
        app = self._import_app(import_effect=RuntimeError(hostile))

        with (
            patch(
                "dip.experience.desktop.app.filedialog.askopenfilename",
                return_value="collection.csv",
            ),
            patch("dip.experience.desktop.app.messagebox.showinfo") as info,
            patch("dip.experience.desktop.app.messagebox.showerror") as error,
        ):
            app.import_csv()

        error.assert_called_once_with(
            "Import failed",
            "The selected collection file could not be imported.",
        )
        info.assert_not_called()
        app.status_var.set.assert_not_called()
        app.refresh_dashboard.assert_not_called()
        app.load_table.assert_not_called()
        self.assertNotIn(hostile, repr(error.call_args))

    def test_post_commit_display_failures_are_truthful_and_do_not_retry(self):
        refresh_copy = (
            "The collection was imported, but the displayed data could not be "
            "refreshed. Reopen the view or application; do not import the file "
            "again."
        )
        for phase in ("dashboard", "table"):
            with self.subTest(phase=phase):
                app = self._import_app()
                if phase == "dashboard":
                    app.refresh_dashboard.side_effect = RuntimeError("HOSTILE")
                else:
                    app.load_table.side_effect = RuntimeError("HOSTILE")

                with (
                    patch(
                        "dip.experience.desktop.app.filedialog.askopenfilename",
                        return_value="collection.csv",
                    ),
                    patch("dip.experience.desktop.app.messagebox.showinfo") as info,
                    patch("dip.experience.desktop.app.messagebox.showerror") as error,
                ):
                    app.import_csv()

                app.import_service.import_collection.assert_called_once()
                error.assert_called_once_with("Collection imported", refresh_copy)
                info.assert_not_called()
                app.refresh_dashboard.assert_called_once_with()
                app.load_table.assert_called_once_with(report_failure=False)
                self.assertEqual(
                    app.status_var.set.call_args.args[0],
                    "Collection imported; displayed data could not be refreshed.",
                )

    def test_only_literal_true_refresh_results_allow_completion(self):
        warning = (
            "The collection was imported, but the displayed data could not be "
            "refreshed. Reopen the view or application; do not import the file "
            "again."
        )
        unexpected_results = (
            None,
            Mock(),
            object(),
            1,
            "success",
            ("success",),
            ["success"],
        )
        for boundary in ("dashboard", "table"):
            for result in unexpected_results:
                with self.subTest(boundary=boundary, result_type=type(result).__name__):
                    app = self._import_app()
                    if boundary == "dashboard":
                        app.refresh_dashboard.return_value = result
                    else:
                        app.load_table.return_value = result

                    with (
                        patch(
                            "dip.experience.desktop.app.filedialog.askopenfilename",
                            return_value="collection.csv",
                        ),
                        patch("dip.experience.desktop.app.messagebox.showinfo") as info,
                        patch("dip.experience.desktop.app.messagebox.showerror") as error,
                    ):
                        app.import_csv()

                    app.import_service.import_collection.assert_called_once_with(
                        Path("collection.csv")
                    )
                    app.refresh_dashboard.assert_called_once_with()
                    app.load_table.assert_called_once_with(report_failure=False)
                    error.assert_called_once_with("Collection imported", warning)
                    info.assert_not_called()
                    self.assertEqual(
                        app.status_var.set.call_args_list[-1].args,
                        (
                            "Collection imported; displayed data could not be "
                            "refreshed.",
                        ),
                    )
                    self.assertNotIn(repr(result), repr(error.call_args))

    def test_literal_boolean_refresh_result_combinations(self):
        warning = (
            "The collection was imported, but the displayed data could not be "
            "refreshed. Reopen the view or application; do not import the file "
            "again."
        )
        for dashboard_result, table_result in (
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ):
            with self.subTest(
                dashboard_result=dashboard_result,
                table_result=table_result,
            ):
                app = self._import_app()
                app.refresh_dashboard.return_value = dashboard_result
                app.load_table.return_value = table_result

                with (
                    patch(
                        "dip.experience.desktop.app.filedialog.askopenfilename",
                        return_value="collection.csv",
                    ),
                    patch("dip.experience.desktop.app.messagebox.showinfo") as info,
                    patch("dip.experience.desktop.app.messagebox.showerror") as error,
                ):
                    app.import_csv()

                app.import_service.import_collection.assert_called_once_with(
                    Path("collection.csv")
                )
                app.refresh_dashboard.assert_called_once_with()
                app.load_table.assert_called_once_with(report_failure=False)
                if dashboard_result is True and table_result is True:
                    info.assert_called_once()
                    error.assert_not_called()
                else:
                    info.assert_not_called()
                    error.assert_called_once_with("Collection imported", warning)

    def test_completion_dialog_failure_does_not_reclassify_committed_import(self):
        app = self._import_app()

        with (
            patch(
                "dip.experience.desktop.app.filedialog.askopenfilename",
                return_value="collection.csv",
            ),
            patch(
                "dip.experience.desktop.app.messagebox.showinfo",
                side_effect=RuntimeError("HOSTILE"),
            ),
            patch("dip.experience.desktop.app.messagebox.showerror") as error,
        ):
            app.import_csv()

        app.import_service.import_collection.assert_called_once()
        app.refresh_dashboard.assert_called_once_with()
        app.load_table.assert_called_once_with(report_failure=False)
        error.assert_not_called()

    def test_status_failure_does_not_retry_or_prevent_display_refresh(self):
        app = self._import_app()
        app.status_var.set.side_effect = RuntimeError("HOSTILE")

        with (
            patch(
                "dip.experience.desktop.app.filedialog.askopenfilename",
                return_value="collection.csv",
            ),
            patch("dip.experience.desktop.app.messagebox.showinfo"),
            patch("dip.experience.desktop.app.messagebox.showerror") as error,
        ):
            app.import_csv()

        app.import_service.import_collection.assert_called_once()
        app.refresh_dashboard.assert_called_once_with()
        app.load_table.assert_called_once_with(report_failure=False)
        error.assert_not_called()

    def test_selector_failure_is_fixed_and_cancellation_is_a_no_op(self):
        app = self._import_app()
        with (
            patch(
                "dip.experience.desktop.app.filedialog.askopenfilename",
                side_effect=RuntimeError("HOSTILE PATH"),
            ),
            patch("dip.experience.desktop.app.messagebox.showerror") as error,
            patch("dip.experience.desktop.app.messagebox.showinfo") as info,
        ):
            app.import_csv()
        error.assert_called_once_with(
            "Import unavailable",
            "The collection file selector could not be opened.",
        )
        info.assert_not_called()
        app.import_service.import_collection.assert_not_called()
        app.status_var.set.assert_not_called()

        app = self._import_app()
        with (
            patch(
                "dip.experience.desktop.app.filedialog.askopenfilename",
                return_value="",
            ),
            patch("dip.experience.desktop.app.messagebox.showerror") as error,
            patch("dip.experience.desktop.app.messagebox.showinfo") as info,
        ):
            app.import_csv()
        error.assert_not_called()
        info.assert_not_called()
        app.import_service.import_collection.assert_not_called()
        app.status_var.set.assert_not_called()

    def test_refresh_boundaries_report_real_internal_failure_and_success(self):
        dashboard_failure = self._real_display_app(
            _DisplayDatabase(dashboard_fails=True)
        )
        self.assertFalse(dashboard_failure.refresh_dashboard())

        table_failure = self._real_display_app(
            _DisplayDatabase(table_fails=True)
        )
        with patch("dip.experience.desktop.app.messagebox.showerror") as error:
            self.assertFalse(table_failure.load_table())
        error.assert_called_once_with(
            "Collection Decisions unavailable",
            "Collection Decisions could not be loaded.",
        )

        success = self._real_display_app(_DisplayDatabase())
        self.assertTrue(success.refresh_dashboard())
        self.assertTrue(success.load_table())

    def test_real_post_commit_display_failures_preserve_durable_import(self):
        warning = (
            "The collection was imported, but the displayed data could not be "
            "refreshed. Reopen the view or application; do not import the file "
            "again."
        )
        cases = (
            ("dashboard", True, False),
            ("table", False, True),
            ("both", True, True),
        )
        for name, dashboard_fails, table_fails in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                csv_path = root / "collection.csv"
                csv_path.write_text(
                    "Release ID,Artist,Title\n"
                    "1101,Fixture Artist,Fixture Title\n"
                    "1101,Fixture Artist,Fixture Title\n",
                    encoding="utf-8",
                )
                database_path = root / "collection.sqlite3"
                database = Database(database_path)
                service = ImportService(database)
                display = _DisplayDatabase(
                    dashboard_fails=dashboard_fails,
                    table_fails=table_fails,
                )
                app = self._real_display_app(display)
                app.import_service = SimpleNamespace(
                    import_collection=Mock(wraps=service.import_collection)
                )

                with (
                    patch(
                        "dip.experience.desktop.app.filedialog.askopenfilename",
                        return_value=str(csv_path),
                    ),
                    patch("dip.experience.desktop.app.messagebox.showinfo") as info,
                    patch("dip.experience.desktop.app.messagebox.showerror") as error,
                ):
                    app.import_csv()

                app.import_service.import_collection.assert_called_once_with(csv_path)
                self.assertEqual(display.dashboard_calls, 1)
                self.assertEqual(display.table_calls, 1)
                error.assert_called_once_with("Collection imported", warning)
                info.assert_not_called()
                self.assertEqual(
                    app.status_var.set.call_args.args[0],
                    "Collection imported; displayed data could not be refreshed.",
                )
                database.close()

                reopened = Database(database_path)
                try:
                    counts = tuple(
                        reopened.conn.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                        for table in (
                            "releases",
                            "collection_ownership",
                            "decisions",
                            "analysis_runs",
                            "marketplace_snapshots",
                            "desktop_session",
                        )
                    )
                    quantity = reopened.conn.execute(
                        "SELECT quantity FROM collection_ownership"
                    ).fetchone()[0]
                finally:
                    reopened.close()
                self.assertEqual(counts, (1, 1, 1, 0, 0, 0))
                self.assertEqual(quantity, 2)

    def test_keyboard_interrupt_and_system_exit_propagate_from_every_phase(self):
        for exception_type in (KeyboardInterrupt, SystemExit):
            for phase in (
                "selection",
                "import",
                "status",
                "dashboard",
                "table",
                "completion",
            ):
                with self.subTest(exception=exception_type.__name__, phase=phase):
                    app = self._import_app()
                    chooser_effect = None
                    info_effect = None
                    if phase == "selection":
                        chooser_effect = exception_type()
                    elif phase == "import":
                        app.import_service.import_collection.side_effect = exception_type()
                    elif phase == "status":
                        app.status_var.set.side_effect = exception_type()
                    elif phase == "dashboard":
                        app.refresh_dashboard.side_effect = exception_type()
                    elif phase == "table":
                        app.load_table.side_effect = exception_type()
                    else:
                        info_effect = exception_type()

                    with (
                        patch(
                            "dip.experience.desktop.app.filedialog.askopenfilename",
                            return_value="collection.csv",
                            side_effect=chooser_effect,
                        ),
                        patch(
                            "dip.experience.desktop.app.messagebox.showinfo",
                            side_effect=info_effect,
                        ),
                        patch("dip.experience.desktop.app.messagebox.showerror"),
                    ):
                        with self.assertRaises(exception_type):
                            app.import_csv()


if __name__ == "__main__":
    unittest.main()
