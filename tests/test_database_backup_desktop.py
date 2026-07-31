from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from dip.app.database_backup import DatabaseBackupResult
from dip.experience.desktop.app import App


def app() -> App:
    value = App.__new__(App)
    value._collector_run_active = False
    value._database_backup_active = False
    value._queue_note_dirty = False
    value._confirm_unsaved_queue_note = Mock(return_value=True)
    value.database_backup_service = Mock()
    value.database_backup_service.backup.return_value = DatabaseBackupResult(
        "backup.sqlite3"
    )
    value.database_backup_button = Mock()
    value.refresh_discogs_button = Mock()
    value.status_var = Mock()
    value.status_var.get.return_value = "Ready"
    value.configure = Mock()
    value.update_idletasks = Mock()
    return value


class DatabaseBackupDesktopTestCase(unittest.TestCase):
    def test_active_run_and_active_backup_stop_before_note_or_dialog(self) -> None:
        for attribute, title in (
            ("_collector_run_active", "Backup unavailable"),
            ("_database_backup_active", "Backup already active"),
        ):
            with self.subTest(attribute=attribute):
                value = app()
                setattr(value, attribute, True)
                with (
                    patch(
                        "dip.experience.desktop.app.messagebox.showinfo"
                    ) as message,
                    patch(
                        "dip.experience.desktop.app.filedialog.asksaveasfilename"
                    ) as chooser,
                ):
                    value.back_up_database()
                self.assertEqual(message.call_args.args[0], title)
                value._confirm_unsaved_queue_note.assert_not_called()
                chooser.assert_not_called()

    def test_note_cancel_or_save_failure_stops_before_save_as(self) -> None:
        value = app()
        value._confirm_unsaved_queue_note.return_value = False
        with patch(
            "dip.experience.desktop.app.filedialog.asksaveasfilename"
        ) as chooser:
            value.back_up_database()
        chooser.assert_not_called()
        value.database_backup_service.backup.assert_not_called()

    def test_save_as_cancel_is_a_no_op(self) -> None:
        value = app()
        with patch(
            "dip.experience.desktop.app.filedialog.asksaveasfilename",
            return_value="",
        ):
            value.back_up_database()
        value.database_backup_service.backup.assert_not_called()
        self.assertFalse(value._database_backup_active)

    def test_backup_is_synchronous_and_restores_ui_state(self) -> None:
        value = app()
        with (
            patch(
                "dip.experience.desktop.app.filedialog.asksaveasfilename",
                return_value="/tmp/backup.sqlite3",
            ),
            patch(
                "dip.experience.desktop.app.messagebox.showinfo"
            ) as success,
        ):
            value.back_up_database()

        value.database_backup_service.backup.assert_called_once_with(
            Path("/tmp/backup.sqlite3"),
            overwrite=False,
        )
        value.update_idletasks.assert_called_once_with()
        self.assertEqual(
            value.configure.call_args_list,
            [call(cursor="watch"), call(cursor="")],
        )
        value.database_backup_button.state.assert_has_calls(
            [call(["disabled"]), call(["!disabled"])]
        )
        self.assertFalse(value._database_backup_active)
        self.assertIn("backup.sqlite3", success.call_args.args[1])
        self.assertNotIn("/tmp/", success.call_args.args[1])

    def test_overwrite_confirmation_and_safe_failure(self) -> None:
        value = app()
        value.database_backup_service.backup.side_effect = RuntimeError(
            "token SQL /private/database.db personal note"
        )
        with (
            patch(
                "dip.experience.desktop.app.filedialog.asksaveasfilename",
                return_value="/tmp/backup.sqlite3",
            ),
            patch.object(Path, "exists", return_value=True),
            patch(
                "dip.experience.desktop.app.messagebox.askyesno",
                return_value=True,
            ),
            patch(
                "dip.experience.desktop.app.messagebox.showerror"
            ) as failure,
        ):
            value.back_up_database()

        value.database_backup_service.backup.assert_called_once_with(
            Path("/tmp/backup.sqlite3"),
            overwrite=True,
        )
        visible = " ".join(str(item) for item in failure.call_args.args)
        for sentinel in ("token", "SQL", "/private/", "personal note"):
            self.assertNotIn(sentinel, visible)
        self.assertFalse(value._database_backup_active)

    def test_backup_does_not_save_session_or_mutate_domain_state(self) -> None:
        value = app()
        value.session_restoration_service = Mock()
        value.collector_review_service = Mock()
        with (
            patch(
                "dip.experience.desktop.app.filedialog.asksaveasfilename",
                return_value="/tmp/backup.sqlite3",
            ),
            patch("dip.experience.desktop.app.messagebox.showinfo"),
        ):
            value.back_up_database()
        value.session_restoration_service.save.assert_not_called()
        value.collector_review_service.assert_not_called()

    def test_activation_failures_restore_state_independently(self) -> None:
        cases = (
            ("backup_button", lambda value: setattr(
                value.database_backup_button.state,
                "side_effect",
                [RuntimeError("widget"), None],
            )),
            ("refresh_button", lambda value: setattr(
                value.refresh_discogs_button.configure,
                "side_effect",
                [RuntimeError("widget"), None],
            )),
            ("status", lambda value: setattr(
                value.status_var.set,
                "side_effect",
                [RuntimeError("widget"), None],
            )),
            ("cursor", lambda value: setattr(
                value.configure,
                "side_effect",
                [RuntimeError("widget"), None],
            )),
            ("idletasks", lambda value: setattr(
                value.update_idletasks,
                "side_effect",
                RuntimeError("widget"),
            )),
            ("service", lambda value: setattr(
                value.database_backup_service.backup,
                "side_effect",
                RuntimeError("token SQL /private/path"),
            )),
        )
        for name, configure_failure in cases:
            with self.subTest(name=name):
                value = app()
                configure_failure(value)
                with (
                    patch(
                        "dip.experience.desktop.app.filedialog.asksaveasfilename",
                        return_value="/tmp/backup.sqlite3",
                    ),
                    patch(
                        "dip.experience.desktop.app.messagebox.showerror"
                    ) as error,
                ):
                    value.back_up_database()
                self.assertFalse(value._database_backup_active)
                value.database_backup_button.state.assert_called()
                value.refresh_discogs_button.configure.assert_called()
                visible = " ".join(
                    str(item)
                    for call_value in error.call_args_list
                    for item in call_value.args
                )
                for sentinel in ("token", "SQL", "/private/"):
                    self.assertNotIn(sentinel, visible)

    def test_cleanup_failures_do_not_prevent_remaining_cleanup(self) -> None:
        value = app()
        value.configure.side_effect = [None, RuntimeError("clear cursor")]
        value.status_var.set.side_effect = [None, RuntimeError("status")]
        value.database_backup_button.state.side_effect = [
            None,
            RuntimeError("button"),
        ]
        value.refresh_discogs_button.configure.side_effect = [
            None,
            RuntimeError("refresh"),
        ]
        with (
            patch(
                "dip.experience.desktop.app.filedialog.asksaveasfilename",
                return_value="/tmp/backup.sqlite3",
            ),
            patch("dip.experience.desktop.app.messagebox.showinfo"),
        ):
            value.back_up_database()
        self.assertFalse(value._database_backup_active)
        self.assertEqual(value.configure.call_count, 2)
        self.assertEqual(value.status_var.set.call_count, 2)
        self.assertEqual(value.database_backup_button.state.call_count, 2)
        self.assertEqual(value.refresh_discogs_button.configure.call_count, 2)

    def test_dirty_note_save_discard_cancel_and_failure_ordering(self) -> None:
        for response, save_result, should_continue in (
            (True, True, True),
            (False, True, True),
            (None, True, False),
            (True, False, False),
        ):
            with self.subTest(
                response=response,
                save_result=save_result,
            ):
                value = app()
                value._queue_note_dirty = True
                value.current_queue_item = SimpleNamespace(
                    review_note="durable note"
                )
                value._save_queue_note = Mock(return_value=save_result)
                value._load_queue_item = Mock()
                value._confirm_unsaved_queue_note = (
                    App._confirm_unsaved_queue_note.__get__(value, App)
                )
                with (
                    patch(
                        "dip.experience.desktop.app.messagebox.askyesnocancel",
                        return_value=response,
                    ),
                    patch(
                        "dip.experience.desktop.app.filedialog.asksaveasfilename",
                        return_value="/tmp/backup.sqlite3",
                    ) as chooser,
                    patch(
                        "dip.experience.desktop.app.messagebox.showinfo"
                    ),
                ):
                    value.back_up_database()
                if should_continue:
                    chooser.assert_called_once()
                    value.database_backup_service.backup.assert_called_once()
                else:
                    chooser.assert_not_called()
                    value.database_backup_service.backup.assert_not_called()
                if response is True:
                    value._save_queue_note.assert_called_once()
                elif response is False:
                    value._save_queue_note.assert_not_called()
                    value._load_queue_item.assert_called_once_with(
                        value.current_queue_item
                    )


if __name__ == "__main__":
    unittest.main()
