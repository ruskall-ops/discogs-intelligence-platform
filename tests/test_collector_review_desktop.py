from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
import inspect
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from dip.collector_review import (
    ObservationSectionStatus,
    ObservationSourceSection,
    NewWeekendReviewQueueEntry,
    WeekendObservationSource,
    WeekendObservationWorkspace,
    WeekendReviewItemNotFoundError,
    WeekendReviewStatus,
)
from dip.app.collector_run import CollectorRunStatus
from dip.app.collector_review import WeekendObservationService
from dip.app.collector_review import WeekendReviewService
from dip.app.intelligence_history import IntelligenceHistoryQueryService
from dip.app.marketplace_history import MarketplaceHistoryQueryService
from dip.experience.desktop.app import App
from dip.persistence.sqlite import (
    Database,
    SQLiteHotNowCalculatedStateRepository,
    SQLiteIntelligenceHistoryRepository,
    SQLiteMarketplaceHistoryRepository,
    SQLiteWeekendReviewQueueRepository,
)


def _workspace(count: int = 0) -> WeekendObservationWorkspace:
    from datetime import datetime, timezone

    from dip.collector_review import (
        HotNowObservation,
        ObservationIdentity,
        QueueMembership,
    )

    values = tuple(
        HotNowObservation(
            observation_id=ObservationIdentity(
                WeekendObservationSource.HOT_NOW,
                release_id,
            ),
            release_id=release_id,
            artist=f"Artist {release_id}",
            title=f"Title {release_id}",
            calculated_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            source_observed_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            value_score=10.0,
            demand_score=20.0,
            liquidity_score=30.0,
            momentum_score=40.0,
            opportunity_score=50.0,
            sell_window="Hot now",
            priority="Worth reviewing",
            explanation="Stored explanation.",
            evidence=None,
            queue_membership=QueueMembership(),
        )
        for release_id in range(1, count + 1)
    )
    return WeekendObservationWorkspace(
        ObservationSourceSection(
            WeekendObservationSource.HOT_NOW,
            ObservationSectionStatus.AVAILABLE,
            "Stored Hot now signals.",
            values,
        ),
        ObservationSourceSection(
            WeekendObservationSource.HIDDEN_GEM,
            ObservationSectionStatus.NO_HISTORY,
            "No persisted History.",
        ),
    )


class CollectorReviewDesktopTestCase(unittest.TestCase):
    def test_dashboard_hot_now_uses_workspace_count_and_availability(self) -> None:
        app = App.__new__(App)
        app.current_observation_workspace = _workspace(3)
        widget = Mock()
        app.kpis = {"hot_now": widget}
        app.hot_now_kpi_button = widget

        app._apply_hot_now_dashboard_state()

        widget.configure.assert_called_once_with(text="3")
        widget.state.assert_called_once_with(["!disabled"])

        app.current_observation_workspace = WeekendObservationWorkspace.unavailable(
            "Collector Review observations are unavailable."
        )
        widget.reset_mock()
        app._apply_hot_now_dashboard_state()
        widget.configure.assert_called_once_with(text="—")
        widget.state.assert_called_once_with(["disabled"])

    def test_dashboard_navigation_opens_observations_source(self) -> None:
        app = App.__new__(App)
        app.current_observation_workspace = _workspace()
        app.observation_source_var = Mock()
        app.tabs = Mock()
        app.review_tab = object()
        app.collection_review_tabs = Mock()
        app.observations_tab = object()
        app._render_observations = Mock()

        app.open_collection_review_observations(
            WeekendObservationSource.HOT_NOW
        )

        app.observation_source_var.set.assert_called_once_with("Hot now")
        app.tabs.select.assert_called_once_with(app.review_tab)
        app.collection_review_tabs.select.assert_called_once_with(
            app.observations_tab
        )
        app._render_observations.assert_called_once_with()

    def test_unsaved_note_prompt_supports_save_discard_and_cancel(self) -> None:
        app = App.__new__(App)
        app._queue_note_dirty = True
        app._save_queue_note = Mock(return_value=True)
        with patch(
            "dip.experience.desktop.app.messagebox.askyesnocancel",
            side_effect=(True, False, None),
        ):
            self.assertTrue(app._confirm_unsaved_queue_note())
            app._queue_note_dirty = True
            self.assertTrue(app._confirm_unsaved_queue_note())
            app._queue_note_dirty = True
            self.assertFalse(app._confirm_unsaved_queue_note())
        app._save_queue_note.assert_called_once_with()

    def test_new_desktop_behavior_uses_application_services_not_sql(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "src/dip/experience/desktop/app.py"
        ).read_text(encoding="utf-8")

        self.assertIn("Weekend Review Queue", source)
        self.assertIn("Review in Observations", source)
        self.assertIn("Open Collection Decision", source)
        self.assertNotIn("INSERT INTO weekend_review_queue", source)
        self.assertNotIn("UPDATE weekend_review_queue", source)
        self.assertNotIn("DELETE FROM weekend_review_queue", source)

    def test_selection_cancel_restores_item_and_save_failure_preserves_buffer(
        self,
    ) -> None:
        app = App.__new__(App)
        app.current_queue_item = SimpleNamespace(
            queue_item_id=1,
            updated_at=object(),
        )
        app.queue_tree = Mock()
        app.queue_tree.selection.return_value = ("2",)
        app._confirm_unsaved_queue_note = Mock(return_value=False)
        app.collector_review_service = Mock()
        app._load_queue_item = Mock()

        app._on_queue_selected()

        app.queue_tree.selection_set.assert_called_once_with("1")
        app.collector_review_service.get.assert_not_called()
        app._load_queue_item.assert_not_called()

        note = Mock()
        note.get.return_value = "unsaved buffer"
        app.queue_note = note
        app.queue_detail_var = Mock()
        app._set_queue_controls_enabled = Mock()
        app.collector_review_service.save_note.side_effect = (
            WeekendReviewItemNotFoundError("safe")
        )
        app._queue_note_dirty = True
        self.assertFalse(app._save_queue_note())
        note.delete.assert_not_called()
        app._set_queue_controls_enabled.assert_called_once_with(False)

    def test_selection_event_save_and_discard_paths_load_requested_item(
        self,
    ) -> None:
        for response, expected_saves in ((True, 1), (False, 0)):
            with self.subTest(response=response):
                app = App.__new__(App)
                app.current_queue_item = SimpleNamespace(
                    queue_item_id=1,
                    updated_at=object(),
                )
                app._queue_note_dirty = True
                app.queue_tree = Mock()
                app.queue_tree.selection.return_value = ("2",)
                requested = SimpleNamespace(queue_item_id=2)
                app.collector_review_service = Mock()
                app.collector_review_service.get.return_value = requested
                app._save_queue_note = Mock(return_value=True)
                app._load_queue_item = Mock()
                with patch(
                    "dip.experience.desktop.app.messagebox.askyesnocancel",
                    return_value=response,
                ):
                    app._on_queue_selected()
                self.assertEqual(app._save_queue_note.call_count, expected_saves)
                app.collector_review_service.get.assert_called_once_with(2)
                app._load_queue_item.assert_called_once_with(requested)

    def test_destination_and_close_cancel_prevent_navigation_and_shutdown(
        self,
    ) -> None:
        app = App.__new__(App)
        app._review_tab_change_guard = False
        app.queue_tab = object()
        selected_tab = object()
        app.collection_review_tabs = Mock()
        app.collection_review_tabs.select.return_value = "selected"
        app.collection_review_tabs.nametowidget.return_value = selected_tab
        app._last_collection_review_destination = app.queue_tab
        app._confirm_unsaved_queue_note = Mock(return_value=False)

        app._on_collection_review_destination_changed()

        app.collection_review_tabs.select.assert_called_with(app.queue_tab)
        self.assertIs(app._last_collection_review_destination, app.queue_tab)

        app.db = Mock()
        app.destroy = Mock()
        app.on_close()
        app.db.close.assert_not_called()
        app.destroy.assert_not_called()
        app._confirm_unsaved_queue_note.return_value = True
        app.on_close()
        app.db.close.assert_called_once_with()
        app.destroy.assert_called_once_with()

    def test_destination_and_close_save_discard_paths_use_dirty_prompt(
        self,
    ) -> None:
        for response, expected_saves in ((True, 1), (False, 0)):
            with self.subTest(destination_response=response):
                app = App.__new__(App)
                app._review_tab_change_guard = False
                app.queue_tab = object()
                selected_tab = object()
                app.collection_review_tabs = Mock()
                app.collection_review_tabs.select.return_value = "selected"
                app.collection_review_tabs.nametowidget.return_value = selected_tab
                app._last_collection_review_destination = app.queue_tab
                app._queue_note_dirty = True
                app._save_queue_note = Mock(return_value=True)
                with patch(
                    "dip.experience.desktop.app.messagebox.askyesnocancel",
                    return_value=response,
                ):
                    app._on_collection_review_destination_changed()
                self.assertEqual(
                    app._save_queue_note.call_count,
                    expected_saves,
                )
                self.assertIs(
                    app._last_collection_review_destination,
                    selected_tab,
                )

            with self.subTest(close_response=response):
                app = App.__new__(App)
                app._queue_note_dirty = True
                app._save_queue_note = Mock(return_value=True)
                app.db = Mock()
                app.destroy = Mock()
                with patch(
                    "dip.experience.desktop.app.messagebox.askyesnocancel",
                    return_value=response,
                ):
                    app.on_close()
                self.assertEqual(
                    app._save_queue_note.call_count,
                    expected_saves,
                )
                app.db.close.assert_called_once_with()
                app.destroy.assert_called_once_with()

        failed = App.__new__(App)
        failed._queue_note_dirty = True
        failed._save_queue_note = Mock(return_value=False)
        failed.db = Mock()
        failed.destroy = Mock()
        with patch(
            "dip.experience.desktop.app.messagebox.askyesnocancel",
            return_value=True,
        ):
            failed.on_close()
        failed.db.close.assert_not_called()
        failed.destroy.assert_not_called()

    def test_queue_navigation_targets_exact_existing_decision(self) -> None:
        app = App.__new__(App)
        app.tabs = Mock()
        app.review_tab = object()
        app.collection_review_tabs = Mock()
        app.decisions_tab = object()
        app.load_table = Mock()
        app.tree = Mock()
        app.tree.exists.return_value = True
        app.edit_selected = Mock()

        app.open_collection_decision(42)

        app.tabs.select.assert_called_once_with(app.review_tab)
        app.collection_review_tabs.select.assert_called_once_with(
            app.decisions_tab
        )
        app.tree.selection_set.assert_called_once_with("42")
        app.tree.see.assert_called_once_with("42")
        app.edit_selected.assert_called_once_with()

    def test_collector_run_terminal_refresh_does_not_reload_queue(self) -> None:
        app = App.__new__(App)
        app._restore_refresh_controls = Mock()
        app.status_var = Mock()
        app.refresh_dashboard = Mock()
        app.load_table = Mock()
        app.refresh_weekend_review_queue = Mock()
        with patch("dip.experience.desktop.app.messagebox.showinfo"):
            app.finish_refresh(
                SimpleNamespace(
                    status=CollectorRunStatus.COMPLETED,
                    successful_releases=1,
                    failed_releases=0,
                )
            )
        app.refresh_dashboard.assert_called_once_with()
        app.refresh_weekend_review_queue.assert_not_called()

    def test_real_observation_service_drives_dashboard_and_drilldown_equally(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "dashboard.db")
            try:
                database.conn.execute(
                    """
                    INSERT INTO releases(release_id, artist, title)
                    VALUES (1, 'Artist', 'Title')
                    """
                )
                database.upsert_score(
                    1,
                    "2026-07-25T09:00:00+00:00",
                    {
                        "value_score": 10.0,
                        "demand_score": 20.0,
                        "liquidity_score": 30.0,
                        "momentum_score": 40.0,
                        "opportunity_score": 80.0,
                        "sell_window": "Hot now",
                        "priority": "Worth reviewing",
                        "explanation": "Stored.",
                    },
                )
                service = WeekendObservationService(
                    SQLiteHotNowCalculatedStateRepository(database),
                    IntelligenceHistoryQueryService(
                        SQLiteIntelligenceHistoryRepository(database)
                    ),
                    MarketplaceHistoryQueryService(
                        SQLiteMarketplaceHistoryRepository(database)
                    ),
                    SQLiteWeekendReviewQueueRepository(database),
                )
                app = App.__new__(App)
                app.db = Mock()
                app.db.dashboard.return_value = {
                    "unique_releases": 1,
                    "owned_copies": 1,
                    "high_priority": 0,
                    "worth_reviewing": 0,
                    "hot_now": 999,
                    "protected": 0,
                }
                widgets = {
                    key: Mock()
                    for key in app.db.dashboard.return_value
                }
                app.kpis = widgets
                app.hot_now_kpi_button = widgets["hot_now"]
                app.collector_review_observations = service
                app._render_observations = Mock()
                app.refresh_intelligence_dashboard = Mock()

                app.refresh_dashboard()

                self.assertEqual(len(app.current_observation_workspace.hot_now), 1)
                widgets["hot_now"].configure.assert_called_with(text="1")
                app._render_observations.assert_called_once_with()
            finally:
                database.close()

    def test_collector_run_worker_never_touches_queue_widgets_or_controls(
        self,
    ) -> None:
        start_source = inspect.getsource(App.start_refresh)
        worker_source = inspect.getsource(App.refresh_market_data)
        finish_source = inspect.getsource(App.finish_refresh)
        self.assertNotIn("queue_", start_source)
        self.assertNotIn("queue_", worker_source)
        self.assertNotIn("refresh_weekend_review_queue", finish_source)
        self.assertIn("self.after(0", worker_source)
        self.assertIn("self.refresh_dashboard()", finish_source)

    def test_real_selection_event_save_persists_before_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "dirty-note.db")
            try:
                database.conn.executemany(
                    """
                    INSERT INTO releases(release_id, artist, title)
                    VALUES (?, ?, ?)
                    """,
                    ((1, "One", "First"), (2, "Two", "Second")),
                )
                database.conn.commit()
                repository = SQLiteWeekendReviewQueueRepository(database)
                instant = datetime(2026, 7, 25, 9, tzinfo=timezone.utc)

                def entry(release_id):
                    return NewWeekendReviewQueueEntry(
                        release_id,
                        instant,
                        WeekendReviewStatus.TO_REVIEW,
                        "",
                        instant,
                        None,
                        WeekendObservationSource.HOT_NOW,
                        instant,
                        f"Release {release_id} evidence.",
                        None,
                        None,
                    )

                first = repository.add_or_get_existing(entry(1)).item
                second = repository.add_or_get_existing(entry(2)).item
                app = App.__new__(App)
                app.current_queue_item = first
                app.collector_review_service = WeekendReviewService(
                    repository,
                    clock=lambda: instant,
                )
                app._queue_note_dirty = True
                app.queue_note = Mock()
                app.queue_note.get.return_value = "persist before navigation"
                app.queue_tree = Mock()
                app.queue_tree.selection.return_value = (
                    str(second.queue_item_id),
                )
                app._load_queue_item = Mock()
                with patch(
                    "dip.experience.desktop.app.messagebox.askyesnocancel",
                    return_value=True,
                ):
                    app._on_queue_selected()
                self.assertEqual(
                    repository.get_by_id(first.queue_item_id).review_note,
                    "persist before navigation",
                )
                self.assertGreater(
                    repository.get_by_id(first.queue_item_id).updated_at,
                    first.updated_at,
                )
                self.assertEqual(
                    app._load_queue_item.call_args_list[-1].args[0],
                    second,
                )
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
