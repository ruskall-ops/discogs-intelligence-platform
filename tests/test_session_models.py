from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone

from dip.collector_review import ObservationIdentity, WeekendObservationSource
from dip.session import (
    CollectionReviewDestination,
    DecisionPriorityFilter,
    DecisionStateFilter,
    DesktopSession,
    DesktopSessionCapture,
    QueueStatusFilter,
    SESSION_FORMAT_VERSION,
    SessionCompatibilityError,
    TopLevelDestination,
)


def session(**changes):
    values = {
        "format_version": SESSION_FORMAT_VERSION,
        "saved_at": datetime(2026, 7, 27, 12, tzinfo=timezone.utc),
        "active_project_id": "current_collection",
        "window_width": 1380,
        "window_height": 820,
        "window_x": -1200,
        "window_y": 40,
        "top_level_destination": TopLevelDestination.COLLECTION_REVIEW,
        "collection_review_destination":
            CollectionReviewDestination.WEEKEND_REVIEW_QUEUE,
        "observation_source": WeekendObservationSource.HIDDEN_GEM,
        "queue_filter": QueueStatusFilter.ALL,
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


class SessionModelTestCase(unittest.TestCase):
    def test_model_is_frozen_and_enum_values_are_stable(self):
        value = session()
        with self.assertRaises(FrozenInstanceError):
            value.window_width = 1500
        self.assertEqual(
            tuple(item.value for item in TopLevelDestination),
            ("project", "dashboard", "collection_review"),
        )
        self.assertEqual(
            tuple(item.value for item in CollectionReviewDestination),
            ("observations", "weekend_review_queue", "collection_decisions"),
        )
        self.assertEqual(
            tuple(item.value for item in QueueStatusFilter),
            ("active", "resolved", "all"),
        )

    def test_rejects_unsupported_format_and_naive_timestamp(self):
        malformed = 987654
        with self.assertRaises(SessionCompatibilityError) as raised:
            session(format_version=malformed)
        self.assertNotIn(str(malformed), str(raised.exception))
        with self.assertRaises(ValueError):
            session(saved_at=datetime(2026, 7, 27))
        with self.assertRaises(TypeError):
            session(format_version=True)

    def test_rejects_boolean_and_out_of_range_geometry(self):
        for name, value in (
            ("window_width", True),
            ("window_height", False),
            ("window_x", True),
            ("window_y", False),
        ):
            with self.subTest(name=name):
                with self.assertRaises(TypeError):
                    session(**{name: value})
        for name, value in (
            ("window_width", 1049),
            ("window_width", 32768),
            ("window_height", 649),
            ("window_height", 32768),
            ("window_x", -2147483649),
            ("window_y", 2147483648),
        ):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    session(**{name: value})

    def test_requires_exact_enums_and_valid_optional_values(self):
        with self.assertRaises(TypeError):
            session(top_level_destination="project")
        with self.assertRaises(TypeError):
            session(active_project_id=" current_collection")
        with self.assertRaises(TypeError):
            session(selected_observation=("hot_now", 1))
        for name, value in (
            ("selected_queue_item_id", True),
            ("selected_queue_item_id", 0),
            ("selected_decision_release_id", -1),
        ):
            with self.subTest(name=name):
                with self.assertRaises((TypeError, ValueError)):
                    session(**{name: value})

    def test_capture_has_same_validation_without_timestamp(self):
        value = session()
        capture = DesktopSessionCapture(
            value.active_project_id,
            value.window_width,
            value.window_height,
            value.window_x,
            value.window_y,
            value.top_level_destination,
            value.collection_review_destination,
            value.observation_source,
            value.queue_filter,
            value.decision_priority_filter,
            value.decision_state_filter,
            value.selected_observation,
            value.selected_queue_item_id,
            value.selected_decision_release_id,
        )
        self.assertEqual(capture.window_width, value.window_width)
        with self.assertRaises(ValueError):
            replace(capture, window_height=1)


if __name__ == "__main__":
    unittest.main()
