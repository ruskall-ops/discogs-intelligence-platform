from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dip.collector_review import ObservationIdentity, WeekendObservationSource
from dip.persistence.sqlite import Database, SQLiteSessionRepository
from dip.session import (
    CollectionReviewDestination,
    DecisionPriorityFilter,
    DecisionStateFilter,
    DesktopSession,
    QueueStatusFilter,
    SessionCompatibilityError,
    SessionIntegrityError,
    SessionPersistenceError,
    TopLevelDestination,
)


def session(**changes):
    values = {
        "format_version": 1,
        "saved_at": datetime(
            2026,
            7,
            27,
            14,
            30,
            1,
            123456,
            tzinfo=timezone(timedelta(hours=2)),
        ),
        "active_project_id": "current_collection",
        "window_width": 1380,
        "window_height": 820,
        "window_x": -1200,
        "window_y": 25,
        "top_level_destination": TopLevelDestination.COLLECTION_REVIEW,
        "collection_review_destination":
            CollectionReviewDestination.WEEKEND_REVIEW_QUEUE,
        "observation_source": WeekendObservationSource.HIDDEN_GEM,
        "queue_filter": QueueStatusFilter.ALL,
        "decision_priority_filter":
            DecisionPriorityFilter.HIGH_PRIORITY_REVIEW,
        "decision_state_filter": DecisionStateFilter.REVIEW,
        "selected_observation": ObservationIdentity(
            WeekendObservationSource.HIDDEN_GEM,
            7,
        ),
        "selected_queue_item_id": 8,
        "selected_decision_release_id": 9,
    }
    values.update(changes)
    return DesktopSession(**values)


class SQLiteSessionRepositoryTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "session.db")
        self.repository = SQLiteSessionRepository(self.database)

    def tearDown(self):
        try:
            self.database.close()
        except Exception:
            pass
        self.temp.cleanup()

    def test_absence_round_trip_and_replacement(self):
        self.assertIsNone(self.repository.get())
        first = session()
        self.repository.save(first)
        restored = self.repository.get()
        self.assertEqual(
            restored,
            replace(
                first,
                saved_at=first.saved_at.astimezone(timezone.utc),
            ),
        )
        self.assertEqual(
            self.database.conn.execute(
                "SELECT saved_at FROM desktop_session"
            ).fetchone()["saved_at"],
            "2026-07-27T12:30:01.123456+00:00",
        )
        second = replace(first, window_width=1500)
        self.repository.save(second)
        self.assertEqual(self.repository.get().window_width, 1500)
        self.assertEqual(
            self.database.conn.execute(
                "SELECT COUNT(*) FROM desktop_session"
            ).fetchone()[0],
            1,
        )

    def test_outer_transaction_controls_commit_and_rollback(self):
        with self.database.transaction():
            self.repository.save(session(window_width=1400))
        self.assertEqual(self.repository.get().window_width, 1400)
        with self.assertRaises(RuntimeError):
            with self.database.transaction():
                self.repository.save(session(window_width=1600))
                raise RuntimeError("rollback")
        self.assertEqual(self.repository.get().window_width, 1400)

    def test_failed_nested_save_preserves_previous_row(self):
        self.repository.save(session(window_width=1400))
        with self.database.transaction() as connection:
            connection.execute(
                """
                CREATE TRIGGER reject_session_update
                BEFORE UPDATE ON desktop_session
                BEGIN SELECT RAISE(ABORT, 'rejected'); END
                """
            )
            with self.assertRaises(SessionPersistenceError):
                self.repository.save(session(window_width=1600))
            self.assertEqual(self.repository.get().window_width, 1400)

    def test_corrupt_values_are_rejected_as_one_record(self):
        self.repository.save(session())
        corruptions = (
            ("singleton_id", 2),
            ("format_version", b"1"),
            ("saved_at", "2026-07-27T12:30:01"),
            ("saved_at", "2026-07-27T12:30:01.000000+01:00"),
            ("saved_at", "2026-7-27T12:30:01.000000+00:00"),
            ("active_project_id", ""),
            ("active_project_id", " project"),
            ("active_project_id", b"project"),
            ("window_width", 1049),
            ("window_width", b"1050"),
            ("window_height", 649),
            ("window_height", b"650"),
            ("window_x", -2147483649),
            ("window_x", b"0"),
            ("window_y", 2147483648),
            ("window_y", b"0"),
            ("top_level_destination", "unknown"),
            ("collection_review_destination", "unknown"),
            ("observation_source", "unknown"),
            ("queue_filter", "unknown"),
            ("decision_priority_filter", "unknown"),
            ("decision_state_filter", "unknown"),
            ("selected_observation_source", "unknown"),
            ("selected_observation_release_id", 0),
            ("selected_observation_release_id", b"7"),
            ("selected_queue_item_id", 0),
            ("selected_queue_item_id", b"8"),
            ("selected_decision_release_id", -1),
            ("selected_decision_release_id", b"9"),
        )
        for column, value in corruptions:
            with self.subTest(column=column, kind=type(value).__name__):
                self.database.conn.execute("PRAGMA ignore_check_constraints=ON")
                self.database.conn.execute(
                    f"UPDATE desktop_session SET {column}=?",
                    (value,),
                )
                self.database.conn.commit()
                self.database.conn.execute("PRAGMA ignore_check_constraints=OFF")
                with self.assertRaises(SessionIntegrityError):
                    self.repository.get()
                self.database.conn.execute("DELETE FROM desktop_session")
                self.database.conn.commit()
                self.repository.save(session())

    def test_corruption_messages_do_not_disclose_stored_values(self):
        self.repository.save(session())
        secret = "stored-secret-value"
        self.database.conn.execute("PRAGMA ignore_check_constraints=ON")
        self.database.conn.execute(
            "UPDATE desktop_session SET top_level_destination=?",
            (secret,),
        )
        self.database.conn.commit()
        self.database.conn.execute("PRAGMA ignore_check_constraints=OFF")
        with self.assertRaises(SessionIntegrityError) as raised:
            self.repository.get()
        self.assertNotIn(secret, str(raised.exception))

    def test_unknown_version_and_incomplete_identity_are_distinct(self):
        self.repository.save(session())
        self.database.conn.execute("PRAGMA ignore_check_constraints=ON")
        self.database.conn.execute(
            "UPDATE desktop_session SET format_version=2"
        )
        self.database.conn.commit()
        self.database.conn.execute("PRAGMA ignore_check_constraints=OFF")
        with self.assertRaises(SessionCompatibilityError):
            self.repository.get()
        try:
            self.repository.get()
        except SessionCompatibilityError as exc:
            self.assertNotIn("2", str(exc))
        self.database.conn.execute("DELETE FROM desktop_session")
        self.database.conn.commit()
        self.repository.save(session())
        self.database.conn.execute("PRAGMA ignore_check_constraints=ON")
        self.database.conn.execute(
            "UPDATE desktop_session SET selected_observation_source=NULL"
        )
        self.database.conn.commit()
        self.database.conn.execute("PRAGMA ignore_check_constraints=OFF")
        with self.assertRaises(SessionIntegrityError):
            self.repository.get()

    def test_closed_database_failure_is_safe(self):
        self.database.close()
        with self.assertRaises(SessionPersistenceError):
            self.repository.get()
        with self.assertRaises(SessionPersistenceError):
            self.repository.save(session())

    def test_genuine_temporary_database_restart_reconstructs_frozen_session(self):
        path = Path(self.temp.name) / "restart.db"
        first_database = Database(path)
        first_repository = SQLiteSessionRepository(first_database)
        expected = session()
        first_repository.save(expected)
        first_database.close()

        second_database = Database(path)
        try:
            restored = SQLiteSessionRepository(second_database).get()
            self.assertEqual(
                restored,
                replace(expected, saved_at=expected.saved_at.astimezone(timezone.utc)),
            )
            with self.assertRaises(Exception):
                restored.window_width = 1
        finally:
            second_database.close()


if __name__ == "__main__":
    unittest.main()
