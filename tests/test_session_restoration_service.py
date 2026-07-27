from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from dip.app.session_restoration import SessionRestorationService
from dip.collector_review import WeekendObservationSource
from dip.session import (
    CollectionReviewDestination,
    DecisionPriorityFilter,
    DecisionStateFilter,
    DesktopSessionCapture,
    QueueStatusFilter,
    SessionPersistenceError,
    TopLevelDestination,
)


def capture():
    return DesktopSessionCapture(
        "current_collection",
        1380,
        820,
        20,
        30,
        TopLevelDestination.PROJECT,
        CollectionReviewDestination.OBSERVATIONS,
        WeekendObservationSource.HOT_NOW,
        QueueStatusFilter.ACTIVE,
        DecisionPriorityFilter.ALL,
        DecisionStateFilter.ALL,
    )


class SessionRestorationServiceTestCase(unittest.TestCase):
    def test_load_preserves_absence_and_translates_unexpected_failure(self):
        repository = Mock()
        repository.get.return_value = None
        self.assertIsNone(SessionRestorationService(repository).load())
        repository.get.side_effect = RuntimeError("unsafe")
        with self.assertRaises(SessionPersistenceError) as raised:
            SessionRestorationService(repository).load()
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)

    def test_save_calls_clock_once_and_normalizes_to_utc(self):
        repository = Mock()
        clock = Mock(
            return_value=datetime(
                2026,
                7,
                27,
                14,
                tzinfo=timezone(timedelta(hours=2)),
            )
        )
        saved = SessionRestorationService(repository, clock).save(capture())
        clock.assert_called_once_with()
        repository.save.assert_called_once_with(saved)
        self.assertEqual(saved.saved_at.hour, 12)
        self.assertEqual(saved.saved_at.tzinfo, timezone.utc)

    def test_save_validates_clock_and_translates_repository_failure(self):
        repository = Mock()
        with self.assertRaises(ValueError):
            SessionRestorationService(
                repository,
                lambda: datetime(2026, 7, 27),
            ).save(capture())
        repository.save.side_effect = RuntimeError("unsafe")
        with self.assertRaises(SessionPersistenceError):
            SessionRestorationService(
                repository,
                lambda: datetime.now(timezone.utc),
            ).save(capture())


if __name__ == "__main__":
    unittest.main()
