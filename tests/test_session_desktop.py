from __future__ import annotations

import unittest
import tkinter as tk
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dip.app.session_restoration import SessionRestorationService
from dip.app.collector_run import CollectorRunStatus
from dip.collector_review import (
    ObservationIdentity,
    ObservationSectionStatus,
    WeekendObservationSource,
)
from dip.experience.desktop.app import (
    App,
    _DECISION_FILTER_LABELS,
    _PRIORITY_FILTER_LABELS,
    _QUEUE_FILTER_LABELS,
    _SOURCE_LABELS,
    _enum_for_label,
    _sanitize_geometry,
    _valid_normal_geometry,
)
from dip.persistence.sqlite import Database
from dip.persistence.sqlite.session import SQLiteSessionRepository
from dip.session import (
    CollectionReviewDestination,
    DecisionPriorityFilter,
    DecisionStateFilter,
    DesktopSession,
    QueueStatusFilter,
    SessionValidationError,
    TopLevelDestination,
)


def session(**changes):
    values = {
        "format_version": 1,
        "saved_at": datetime(2026, 7, 27, tzinfo=timezone.utc),
        "active_project_id": "current_collection",
        "window_width": 1380,
        "window_height": 820,
        "window_x": -1200,
        "window_y": 30,
        "top_level_destination": TopLevelDestination.COLLECTION_REVIEW,
        "collection_review_destination":
            CollectionReviewDestination.WEEKEND_REVIEW_QUEUE,
        "observation_source": WeekendObservationSource.HIDDEN_GEM,
        "queue_filter": QueueStatusFilter.RESOLVED,
        "decision_priority_filter":
            DecisionPriorityFilter.WORTH_REVIEWING,
        "decision_state_filter": DecisionStateFilter.KEEP,
        "selected_observation": ObservationIdentity(
            WeekendObservationSource.HIDDEN_GEM,
            7,
        ),
        "selected_queue_item_id": 8,
        "selected_decision_release_id": 9,
    }
    values.update(changes)
    return DesktopSession(**values)


class _Notebook:
    def __init__(self, widgets, selected):
        self._tokens = {
            widget: f"tab-{index}"
            for index, widget in enumerate(widgets)
        }
        self._widgets = {
            token: widget for widget, token in self._tokens.items()
        }
        self._selected = self._tokens[selected]

    def select(self, widget=None):
        if widget is not None:
            self._selected = self._tokens[widget]
        return self._selected

    def nametowidget(self, token):
        return self._widgets[token]


class SessionGeometryTestCase(unittest.TestCase):
    def test_valid_negative_multimonitor_position_is_retained(self):
        self.assertEqual(
            _sanitize_geometry(
                1380,
                820,
                -1500,
                20,
                (-1920, 0, 3840, 1080),
            ),
            (1380, 820, -1500, 20),
        )

    def test_offscreen_position_is_centered(self):
        self.assertEqual(
            _sanitize_geometry(1200, 700, 4000, 3000, (0, 0, 1920, 1080)),
            (1200, 700, 360, 190),
        )

    def test_partial_visibility_threshold_and_size_clamping(self):
        self.assertEqual(
            _sanitize_geometry(
                4000,
                2000,
                1761,
                1017,
                (0, 0, 1920, 1080),
            ),
            (1920, 1080, 0, 0),
        )
        self.assertEqual(
            _sanitize_geometry(1050, 650, 1760, 1016, (0, 0, 1920, 1080)),
            (1050, 650, 1760, 1016),
        )

    def test_invalid_virtual_bounds_restore_dimensions_only(self):
        self.assertEqual(
            _sanitize_geometry(1380, 820, 10, 20, None),
            (1380, 820, None, None),
        )
        self.assertEqual(
            _sanitize_geometry(1380, 820, 10, 20, (0, 0, 0, 0)),
            (1380, 820, None, None),
        )

    def test_normal_geometry_validation_rejects_state_artifacts(self):
        self.assertTrue(_valid_normal_geometry((1050, 650, -1, 0)))
        self.assertFalse(_valid_normal_geometry((800, 600, 0, 0)))
        self.assertFalse(_valid_normal_geometry((True, 650, 0, 0)))

    def test_capture_retains_last_normal_geometry_through_non_normal_states(self):
        app = App.__new__(App)
        app._last_normal_geometry = (1200, 700, 10, 20)
        app.state = Mock(return_value="zoomed")
        app.attributes = Mock(return_value=False)
        app.update_idletasks = Mock()
        app.winfo_width = Mock(return_value=1500)
        app.winfo_height = Mock(return_value=900)
        app.winfo_x = Mock(return_value=30)
        app.winfo_y = Mock(return_value=40)
        app._record_normal_geometry()
        self.assertEqual(app._last_normal_geometry, (1200, 700, 10, 20))

        app.state.return_value = "normal"
        app.attributes.return_value = True
        app._record_normal_geometry()
        self.assertEqual(app._last_normal_geometry, (1200, 700, 10, 20))

        app.attributes.return_value = False
        app._record_normal_geometry()
        self.assertEqual(app._last_normal_geometry, (1500, 900, 30, 40))


class SessionDesktopLifecycleTestCase(unittest.TestCase):
    def _restore_app(self, stored, active_project_id="current_collection"):
        app = App.__new__(App)
        app.session_restoration_service = Mock()
        app.session_restoration_service.load.return_value = stored
        app.project_management = Mock()
        app.project_management.active_project.return_value = SimpleNamespace(
            project_id=active_project_id
        )
        app.observation_source_var = Mock()
        app.queue_filter_var = Mock()
        app.priority_var = Mock()
        app.decision_filter_var = Mock()
        app.search_var = Mock()
        app.status_var = Mock()
        app._apply_session_geometry = Mock()
        app.refresh_dashboard = Mock()
        app.refresh_weekend_review_queue = Mock()
        app.load_table = Mock()
        app._restore_session_selections = Mock()
        app._restore_session_navigation = Mock()
        app._record_normal_geometry = Mock()
        app._last_queue_filter = "Active"
        return app

    def test_startup_applies_preferences_before_queries_then_restores_selection(self):
        stored = session()
        app = self._restore_app(stored)
        events = []
        app.observation_source_var.set.side_effect = (
            lambda value: events.append(("source", value))
        )
        app.queue_filter_var.set.side_effect = (
            lambda value: events.append(("queue", value))
        )
        app.queue_filter_var.get.return_value = "Resolved"
        app.refresh_dashboard.side_effect = lambda: events.append(("dashboard",))
        app.refresh_weekend_review_queue.side_effect = (
            lambda value: events.append(("queue_query", value))
        )
        app.load_table.side_effect = lambda: events.append(("decisions",))
        app._restore_session_selections.side_effect = (
            lambda value: events.append(("selections", value))
        )
        app._restore_session_navigation.side_effect = (
            lambda value: events.append(("navigation", value))
        )

        app._restore_session_and_load()

        self.assertLess(events.index(("source", "Hidden Gems")),
                        events.index(("dashboard",)))
        self.assertLess(events.index(("queue", "Resolved")),
                        events.index(("queue_query", 8)))
        self.assertLess(events.index(("decisions",)),
                        events.index(("navigation", stored)))
        self.assertLess(events.index(("navigation", stored)),
                        events.index(("selections", stored)))
        self.assertFalse(app._session_restoring)
        app.search_var.set.assert_called_once_with("")
        app.status_var.set.assert_not_called()

    def test_project_mismatch_restores_geometry_only(self):
        stored = session()
        app = self._restore_app(stored, active_project_id="other")
        app.queue_filter_var.get.return_value = "Active"
        app._restore_session_and_load()
        app._apply_session_geometry.assert_called_once_with(stored)
        app.observation_source_var.set.assert_not_called()
        app._restore_session_selections.assert_not_called()
        app._restore_session_navigation.assert_not_called()
        app.refresh_weekend_review_queue.assert_called_once_with(None)

    def test_load_failure_uses_defaults_and_neutral_status(self):
        app = self._restore_app(None)
        app.session_restoration_service.load.side_effect = RuntimeError("unsafe")
        app.queue_filter_var.get.return_value = "Active"
        app._restore_session_and_load()
        app._apply_session_geometry.assert_not_called()
        app.status_var.set.assert_called_once_with(
            "Previous session settings could not be restored."
        )
        self.assertFalse(app._session_restoring)
        app.session_restoration_service.save.assert_not_called()
        app.refresh_dashboard.assert_called_once_with()
        app.refresh_weekend_review_queue.assert_called_once_with(None)
        app.load_table.assert_called_once_with()

    def test_guard_is_cleared_after_each_restoration_stage_failure(self):
        stages = (
            "_apply_session_geometry",
            "refresh_dashboard",
            "refresh_weekend_review_queue",
            "load_table",
            "_restore_session_navigation",
            "_restore_session_selections",
        )
        for stage in stages:
            with self.subTest(stage=stage):
                app = self._restore_app(session())
                app.queue_filter_var.get.return_value = "Resolved"
                getattr(app, stage).side_effect = RuntimeError("unsafe detail")
                with self.assertRaises(RuntimeError):
                    app._restore_session_and_load()
                self.assertFalse(app._session_restoring)
                app.session_restoration_service.save.assert_not_called()

    def test_geometry_application_falls_back_then_silently_keeps_default(self):
        for failures, expected in ((1, 2), (2, 2)):
            with self.subTest(failures=failures):
                app = App.__new__(App)
                app.update_idletasks = Mock()
                app.winfo_vrootx = Mock(return_value=0)
                app.winfo_vrooty = Mock(return_value=0)
                app.winfo_vrootwidth = Mock(return_value=1920)
                app.winfo_vrootheight = Mock(return_value=1080)
                app._last_normal_geometry = (1050, 650, 0, 0)
                app.geometry = Mock(
                    side_effect=[tk.TclError(), None]
                    if failures == 1
                    else [tk.TclError(), tk.TclError()]
                )
                app._apply_session_geometry(session())
                self.assertEqual(app.geometry.call_count, expected)
                if failures == 1:
                    self.assertEqual(
                        app.geometry.call_args_list[-1].args,
                        ("1380x820",),
                    )
                else:
                    self.assertEqual(
                        app._last_normal_geometry,
                        (1050, 650, 0, 0),
                    )

    def test_selection_restoration_uses_only_exact_visible_rows(self):
        stored = session()
        app = App.__new__(App)
        app._observation_section = Mock(
            return_value=SimpleNamespace(
                status=ObservationSectionStatus.AVAILABLE
            )
        )
        app._render_observations = Mock()
        app.observation_tree = Mock()
        app.queue_tree = Mock()
        app.queue_tree.exists.return_value = True
        app.queue_tree.selection.return_value = ()
        app.tree = Mock()
        app.tree.exists.return_value = True
        app.tree.selection.return_value = ()
        app.collector_review_service = Mock()
        queue_item = SimpleNamespace(queue_item_id=8)
        app.collector_review_service.get.return_value = queue_item
        app._load_queue_item = Mock()

        app._restore_session_selections(stored)

        app._render_observations.assert_called_once_with(
            stored.selected_observation
        )
        app.queue_tree.selection_set.assert_called_once_with("8")
        app.queue_tree.see.assert_called_once_with("8")
        app._load_queue_item.assert_called_once_with(queue_item)
        app.tree.selection_set.assert_called_once_with("9")
        app.tree.see.assert_called_once_with("9")

    def test_missing_selection_does_not_substitute_or_mutate(self):
        stored = session()
        app = App.__new__(App)
        app._observation_section = Mock(
            return_value=SimpleNamespace(
                status=ObservationSectionStatus.UNAVAILABLE
            )
        )
        app._render_observations = Mock()
        app.observation_tree = Mock()
        app.observation_tree.selection.return_value = ()
        app._show_observation_detail = Mock()
        app.queue_tree = Mock()
        app.queue_tree.exists.return_value = False
        app.queue_tree.selection.return_value = ()
        app.tree = Mock()
        app.tree.exists.return_value = False
        app.tree.selection.return_value = ()
        app.collector_review_service = Mock()
        app._load_queue_item = Mock()

        app._restore_session_selections(stored)

        app._render_observations.assert_not_called()
        app.collector_review_service.get.assert_not_called()
        app.queue_tree.selection_set.assert_not_called()
        app.tree.selection_set.assert_not_called()

    def test_active_run_blocks_every_close_action(self):
        app = App.__new__(App)
        app._collector_run_active = True
        app._confirm_unsaved_queue_note = Mock()
        app.session_restoration_service = Mock()
        app.db = Mock()
        app.destroy = Mock()
        with patch(
            "dip.experience.desktop.app.messagebox.showinfo"
        ) as message:
            app.on_close()
        message.assert_called_once()
        app._confirm_unsaved_queue_note.assert_not_called()
        app.session_restoration_service.save.assert_not_called()
        app.db.close.assert_not_called()
        app.destroy.assert_not_called()

    def test_close_orders_draft_session_database_and_destroy(self):
        app = App.__new__(App)
        app._collector_run_active = False
        events = []
        app._confirm_unsaved_queue_note = Mock(
            side_effect=lambda: events.append("draft") or True
        )
        capture = object()
        app._capture_session = Mock(
            side_effect=lambda: events.append("capture") or capture
        )
        app.session_restoration_service = Mock()
        app.session_restoration_service.save.side_effect = (
            lambda value: events.append(("save", value))
        )
        app.db = Mock()
        app.db.close.side_effect = lambda: events.append("database")
        app.destroy = Mock(side_effect=lambda: events.append("destroy"))

        app.on_close()

        self.assertEqual(
            events,
            ["draft", "capture", ("save", capture), "database", "destroy"],
        )

    def test_failed_session_save_honours_both_choices(self):
        for close_without_saving in (False, True):
            with self.subTest(close=close_without_saving):
                app = App.__new__(App)
                app._collector_run_active = False
                app._confirm_unsaved_queue_note = Mock(return_value=True)
                app._capture_session = Mock(return_value=object())
                app.session_restoration_service = Mock()
                app.session_restoration_service.save.side_effect = RuntimeError()
                app._confirm_close_without_session = Mock(
                    return_value=close_without_saving
                )
                app.db = Mock()
                app.destroy = Mock()
                app.on_close()
                self.assertEqual(
                    app.db.close.call_count,
                    1 if close_without_saving else 0,
                )
                self.assertEqual(
                    app.destroy.call_count,
                    1 if close_without_saving else 0,
                )

    def test_database_close_failure_keeps_root_open(self):
        app = App.__new__(App)
        app.db = Mock()
        app.db.close.side_effect = RuntimeError("unsafe")
        app.destroy = Mock()
        with patch(
            "dip.experience.desktop.app.messagebox.showerror"
        ) as message:
            self.assertFalse(app._close_database_and_root())
        message.assert_called_once()
        app.destroy.assert_not_called()

    def test_macos_application_quit_uses_graceful_close_boundary(self):
        app = App.__new__(App)
        app.protocol = Mock()
        app.tk = Mock()
        app.tk.call.return_value = "aqua"
        app.createcommand = Mock()
        app.on_close = Mock()

        app._register_close_handlers()

        app.protocol.assert_called_once_with(
            "WM_DELETE_WINDOW",
            app.on_close,
        )
        app.createcommand.assert_called_once_with(
            "::tk::mac::Quit",
            app.on_close,
        )
        app.createcommand.call_args.args[1]()
        app.on_close.assert_called_once_with()

    def test_non_aqua_close_registration_does_not_add_application_quit(self):
        app = App.__new__(App)
        app.protocol = Mock()
        app.tk = Mock()
        app.tk.call.return_value = "x11"
        app.createcommand = Mock()
        app.on_close = Mock()

        app._register_close_handlers()

        app.protocol.assert_called_once()
        app.createcommand.assert_not_called()

    def test_dirty_note_cancel_blocks_capture_and_close(self):
        app = App.__new__(App)
        app._collector_run_active = False
        app._confirm_unsaved_queue_note = Mock(return_value=False)
        app._capture_session = Mock()
        app.session_restoration_service = Mock()
        app.db = Mock()
        app.destroy = Mock()
        app.on_close()
        app._capture_session.assert_not_called()
        app.session_restoration_service.save.assert_not_called()
        app.db.close.assert_not_called()
        app.destroy.assert_not_called()

    def test_capture_failure_uses_close_choice_without_calling_service(self):
        for close_without_saving in (False, True):
            with self.subTest(close=close_without_saving):
                app = App.__new__(App)
                app._collector_run_active = False
                app._confirm_unsaved_queue_note = Mock(return_value=True)
                app._capture_session = Mock(
                    side_effect=SessionValidationError(
                        "Desktop session selection cannot be captured."
                    )
                )
                app.session_restoration_service = Mock()
                app._confirm_close_without_session = Mock(
                    return_value=close_without_saving
                )
                app.db = Mock()
                app.destroy = Mock()
                app.on_close()
                app.session_restoration_service.save.assert_not_called()
                self.assertEqual(
                    app.db.close.call_count,
                    1 if close_without_saving else 0,
                )
                self.assertEqual(
                    app.destroy.call_count,
                    1 if close_without_saving else 0,
                )

    def test_repeated_save_and_database_close_failures_can_recover(self):
        app = App.__new__(App)
        app._collector_run_active = False
        app._confirm_unsaved_queue_note = Mock(return_value=True)
        app._capture_session = Mock(return_value=object())
        app.session_restoration_service = Mock()
        app.session_restoration_service.save.side_effect = [
            RuntimeError("unsafe"),
            None,
            None,
        ]
        app._confirm_close_without_session = Mock(return_value=False)
        app.db = Mock()
        app.db.close.side_effect = [RuntimeError("unsafe path"), None]
        app.destroy = Mock()
        with patch(
            "dip.experience.desktop.app.messagebox.showerror"
        ) as message:
            app.on_close()
            app.on_close()
            app.on_close()
        self.assertEqual(app._capture_session.call_count, 3)
        self.assertEqual(app.session_restoration_service.save.call_count, 3)
        self.assertEqual(app.db.close.call_count, 2)
        app.destroy.assert_called_once_with()
        self.assertNotIn("unsafe", str(message.call_args))


class SessionMappingAndCaptureTestCase(unittest.TestCase):
    def _capture_app(self):
        app = App.__new__(App)
        app._record_normal_geometry = Mock()
        app._last_normal_geometry = (1380, 820, -10, 20)
        app.project_management = Mock()
        app.project_management.active_project.return_value = SimpleNamespace(
            project_id="current_collection"
        )
        app.project_tab = object()
        app.dashboard_tab = object()
        app.review_tab = object()
        app.observations_tab = object()
        app.queue_tab = object()
        app.decisions_tab = object()
        app.tabs = Mock()
        app.tabs.select.return_value = "top"
        app.tabs.nametowidget.return_value = app.project_tab
        app.collection_review_tabs = Mock()
        app.collection_review_tabs.select.return_value = "review"
        app.collection_review_tabs.nametowidget.return_value = (
            app.observations_tab
        )
        app.observation_source_var = Mock()
        app.observation_source_var.get.return_value = "Hot now"
        app.queue_filter_var = Mock()
        app.queue_filter_var.get.return_value = "Active"
        app.priority_var = Mock()
        app.priority_var.get.return_value = "All"
        app.decision_filter_var = Mock()
        app.decision_filter_var.get.return_value = "All"
        app.observation_tree = Mock()
        app.observation_tree.selection.return_value = ()
        app.queue_tree = Mock()
        app.queue_tree.selection.return_value = ()
        app.tree = Mock()
        app.tree.selection.return_value = ()
        return app

    def _use_real_notebooks(
        self,
        app,
        top_level,
        collection_review,
    ):
        app.tabs = _Notebook(
            (app.project_tab, app.dashboard_tab, app.review_tab),
            top_level,
        )
        app.collection_review_tabs = _Notebook(
            (app.observations_tab, app.queue_tab, app.decisions_tab),
            collection_review,
        )

    def test_all_label_mappings_are_complete_and_reversible(self):
        for mapping in (
            _SOURCE_LABELS,
            _QUEUE_FILTER_LABELS,
            _PRIORITY_FILTER_LABELS,
            _DECISION_FILTER_LABELS,
        ):
            self.assertEqual(len(mapping), len(set(mapping.values())))
            for enum_value, label in mapping.items():
                self.assertIs(_enum_for_label(label, mapping), enum_value)
        for malformed in ("unknown-secret", "", None):
            with self.subTest(malformed=malformed):
                with self.assertRaises(SessionValidationError) as raised:
                    _enum_for_label(malformed, _QUEUE_FILTER_LABELS)
                if malformed:
                    self.assertNotIn(str(malformed), str(raised.exception))

    def test_capture_reads_each_current_widget_selection(self):
        app = self._capture_app()
        for widget, expected in (
            (app.project_tab, TopLevelDestination.PROJECT),
            (app.dashboard_tab, TopLevelDestination.DASHBOARD),
            (app.review_tab, TopLevelDestination.COLLECTION_REVIEW),
        ):
            app.tabs.nametowidget.return_value = widget
            self.assertIs(app._top_level_destination(), expected)
        for widget, expected in (
            (
                app.observations_tab,
                CollectionReviewDestination.OBSERVATIONS,
            ),
            (
                app.queue_tab,
                CollectionReviewDestination.WEEKEND_REVIEW_QUEUE,
            ),
            (
                app.decisions_tab,
                CollectionReviewDestination.COLLECTION_DECISIONS,
            ),
        ):
            app.collection_review_tabs.nametowidget.return_value = widget
            self.assertIs(app._collection_review_destination(), expected)

        app.tabs.nametowidget.return_value = app.review_tab
        app.collection_review_tabs.nametowidget.return_value = app.queue_tab
        app.observation_source_var.get.return_value = "Hidden Gems"
        app.queue_filter_var.get.return_value = "Resolved"
        app.priority_var.get.return_value = "Worth reviewing"
        app.decision_filter_var.get.return_value = "Keep"
        app.observation_tree.selection.return_value = ("hidden_gem:7",)
        app.queue_tree.selection.return_value = ("8",)
        app.tree.selection.return_value = ("9",)
        captured = app._capture_session()
        self.assertEqual(
            captured.selected_observation,
            ObservationIdentity(WeekendObservationSource.HIDDEN_GEM, 7),
        )
        self.assertEqual(captured.selected_queue_item_id, 8)
        self.assertEqual(captured.selected_decision_release_id, 9)

    def test_graceful_capture_reads_nondefault_and_every_review_destination(self):
        app = self._capture_app()
        for review_widget, expected in (
            (
                app.observations_tab,
                CollectionReviewDestination.OBSERVATIONS,
            ),
            (
                app.queue_tab,
                CollectionReviewDestination.WEEKEND_REVIEW_QUEUE,
            ),
            (
                app.decisions_tab,
                CollectionReviewDestination.COLLECTION_DECISIONS,
            ),
        ):
            with self.subTest(destination=expected):
                self._use_real_notebooks(
                    app,
                    app.review_tab,
                    review_widget,
                )
                captured = app._capture_session()
                self.assertIs(
                    captured.top_level_destination,
                    TopLevelDestination.COLLECTION_REVIEW,
                )
                self.assertIs(
                    captured.collection_review_destination,
                    expected,
                )

    def test_real_sqlite_restart_applies_navigation_after_query_callbacks(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "session.sqlite3"
            first_database = Database(database_path)
            first_app = self._capture_app()
            self._use_real_notebooks(
                first_app,
                first_app.review_tab,
                first_app.decisions_tab,
            )
            first_app.session_restoration_service = (
                SessionRestorationService(
                    SQLiteSessionRepository(first_database)
                )
            )
            first_app.db = first_database
            first_app._collector_run_active = False
            first_app._confirm_unsaved_queue_note = Mock(return_value=True)
            first_app.destroy = Mock()

            first_app.on_close()

            first_app.destroy.assert_called_once_with()
            second_database = Database(database_path)
            try:
                restored = SessionRestorationService(
                    SQLiteSessionRepository(second_database)
                ).load()
                self.assertIsNotNone(restored)
                self.assertIs(
                    restored.top_level_destination,
                    TopLevelDestination.COLLECTION_REVIEW,
                )
                self.assertIs(
                    restored.collection_review_destination,
                    CollectionReviewDestination.COLLECTION_DECISIONS,
                )

                second_app = self._capture_app()
                self._use_real_notebooks(
                    second_app,
                    second_app.project_tab,
                    second_app.observations_tab,
                )
                second_app.session_restoration_service = (
                    SessionRestorationService(
                        SQLiteSessionRepository(second_database)
                    )
                )
                second_app._apply_session_geometry = Mock()
                second_app._record_normal_geometry = Mock()
                second_app.status_var = Mock()
                second_app.search_var = Mock()
                second_app._last_queue_filter = "Active"
                second_app.refresh_dashboard = Mock(
                    side_effect=lambda: second_app.tabs.select(
                        second_app.project_tab
                    )
                )
                second_app.refresh_weekend_review_queue = Mock(
                    side_effect=lambda _identity: (
                        second_app.collection_review_tabs.select(
                            second_app.observations_tab
                        )
                    )
                )
                second_app.load_table = Mock()
                second_app._restore_session_selections = Mock()
                second_app.start_refresh = Mock()
                second_app.edit_selected = Mock()

                second_app._restore_session_and_load()

                self.assertIs(
                    second_app._top_level_destination(),
                    TopLevelDestination.COLLECTION_REVIEW,
                )
                self.assertIs(
                    second_app._collection_review_destination(),
                    CollectionReviewDestination.COLLECTION_DECISIONS,
                )
                self.assertEqual(
                    second_app.queue_filter_var.get(),
                    "Active",
                )
                second_app.start_refresh.assert_not_called()
                second_app.edit_selected.assert_not_called()
            finally:
                second_database.close()

    def test_stale_cached_state_without_tree_selection_is_not_captured(self):
        app = self._capture_app()
        app.current_queue_item = SimpleNamespace(queue_item_id=99)
        app.current_observation = ObservationIdentity(
            WeekendObservationSource.HOT_NOW, 98
        )
        captured = app._capture_session()
        self.assertIsNone(captured.selected_observation)
        self.assertIsNone(captured.selected_queue_item_id)
        self.assertIsNone(captured.selected_decision_release_id)

    def test_unknown_or_missing_notebook_selection_is_value_neutral(self):
        app = self._capture_app()
        for selected, widget in (("", app.project_tab), ("top", object())):
            with self.subTest(selected=selected):
                app.tabs.select.return_value = selected
                app.tabs.nametowidget.return_value = widget
                with self.assertRaises(SessionValidationError) as raised:
                    app._top_level_destination()
                self.assertNotIn(repr(widget), str(raised.exception))

    def test_malformed_tree_selection_is_value_neutral(self):
        app = self._capture_app()
        for tree, malformed in (
            (app.observation_tree, "secret-source:7"),
            (app.queue_tree, "secret-queue"),
            (app.tree, "0"),
        ):
            with self.subTest(malformed=malformed):
                tree.selection.return_value = (malformed,)
                with self.assertRaises(SessionValidationError) as raised:
                    app._capture_session()
                self.assertNotIn(malformed, str(raised.exception))
                tree.selection.return_value = ()


class SessionGeometryEdgeTestCase(unittest.TestCase):
    def test_root_and_child_configure_events(self):
        app = App.__new__(App)
        app._last_normal_geometry = (1200, 700, 1, 2)
        app.state = Mock(return_value="normal")
        app.attributes = Mock(return_value=False)
        app.update_idletasks = Mock()
        app.winfo_width = Mock(return_value=1300)
        app.winfo_height = Mock(return_value=750)
        app.winfo_x = Mock(return_value=-50)
        app.winfo_y = Mock(return_value=10)
        app._record_normal_geometry(SimpleNamespace(widget=object()))
        self.assertEqual(app._last_normal_geometry, (1200, 700, 1, 2))
        app._record_normal_geometry(SimpleNamespace(widget=app))
        self.assertEqual(app._last_normal_geometry, (1300, 750, -50, 10))

    def test_small_display_and_nonzero_origins_remain_model_valid(self):
        self.assertEqual(
            _sanitize_geometry(2000, 1000, 5000, 5000, (-800, -200, 800, 600)),
            (1050, 650, -925, -225),
        )
        width, height, _, _ = _sanitize_geometry(
            32767, 32767, -9000, 9000, (100, 200, 1400, 900)
        )
        self.assertGreaterEqual(width, 1050)
        self.assertGreaterEqual(height, 650)


if __name__ == "__main__":
    unittest.main()
