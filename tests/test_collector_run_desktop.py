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
    app.collector_run_service = None
    app.db = SimpleNamespace(release_ids=Mock(return_value=[3, 4]))
    app.refresh_discogs_button = Mock()
    app.progress = Mock()
    app.status_var = Mock()
    app.refresh_dashboard = Mock()
    app.load_table = Mock()
    return app


class CollectorRunDesktopTestCase(unittest.TestCase):
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
        thread_type.assert_called_once_with(
            target=app.refresh_market_data,
            args=("temporary-token",),
            daemon=True,
        )
        worker.start.assert_called_once_with()

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
        message.assert_called_once()

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
        self.assertNotIn("temporary-token", scheduled[0][1][0])
        self.assertIn("RuntimeError", scheduled[0][1][0])

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
                [(app.show_refresh_unavailable, ("No stored collection.",))],
            )
            app.refresh_discogs_button.configure.assert_not_called()
            app.status_var.set.assert_not_called()
            warning.assert_not_called()
            error.assert_not_called()

            callback, args = scheduled.pop()
            callback(*args)

            self.assertFalse(app._collector_run_active)
            app.refresh_discogs_button.configure.assert_called_with(
                state="normal"
            )
            app.refresh_dashboard.assert_not_called()
            app.load_table.assert_not_called()
            warning.assert_called_once()
            error.assert_not_called()

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
                [(app.show_refresh_error, (str(application_error),))],
            )
            app.refresh_discogs_button.configure.assert_not_called()
            app.status_var.set.assert_not_called()
            warning.assert_not_called()
            error.assert_not_called()

            callback, args = scheduled.pop()
            callback(*args)

            self.assertFalse(app._collector_run_active)
            app.refresh_discogs_button.configure.assert_called_with(
                state="normal"
            )
            app.refresh_dashboard.assert_not_called()
            app.load_table.assert_not_called()
            error.assert_called_once()
            warning.assert_not_called()

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
                app.refresh_dashboard.assert_called_once_with()
                app.load_table.assert_called_once_with()
                message.assert_called_once()

    def test_failed_and_unexpected_outcomes_restore_controls(self):
        app = _app()
        app._collector_run_active = True
        with patch(
            "dip.experience.desktop.app.messagebox.showerror"
        ) as message:
            app.finish_refresh(_result(CollectorRunStatus.FAILED))

        self.assertFalse(app._collector_run_active)
        app.refresh_dashboard.assert_not_called()
        app.load_table.assert_not_called()
        message.assert_called_once()

        app._collector_run_active = True
        with patch("dip.experience.desktop.app.messagebox.showerror"):
            app.show_refresh_error("safe error")
        self.assertFalse(app._collector_run_active)


if __name__ == "__main__":
    unittest.main()
