from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from dip.collector_review import (
    CollectorReviewDomainError,
    HiddenGemObservation,
    NewWeekendReviewQueueEntry,
    ObservationIdentity,
    QueueMembership,
    WeekendObservationSource,
    WeekendReviewQueueItem,
    WeekendReviewStatus,
    normalize_review_note,
    normalize_source_summary,
)


UTC = timezone.utc


class CollectorReviewModelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.observed = datetime(2026, 7, 25, 9, tzinfo=UTC)
        self.added = self.observed + timedelta(hours=1)

    def test_queue_identity_rejects_bool_and_non_positive_values(self) -> None:
        values = (True, False, 0, -1)
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    self._item(queue_item_id=value)  # type: ignore[arg-type]

    def test_queue_timestamp_and_status_invariants_use_utc_instants(self) -> None:
        offset = timezone(timedelta(hours=2))
        item = self._item(
            added_at=self.added.astimezone(offset),
            updated_at=(self.added + timedelta(minutes=2)).astimezone(UTC),
        )
        self.assertEqual(
            item.added_at.astimezone(UTC),
            self.added,
        )

        with self.assertRaisesRegex(
            CollectorReviewDomainError,
            "source_observed_at",
        ):
            self._item(source_observed_at=self.added + timedelta(seconds=1))
        with self.assertRaisesRegex(
            CollectorReviewDomainError,
            "resolved item requires",
        ):
            self._item(status=WeekendReviewStatus.RESOLVED)
        with self.assertRaisesRegex(
            CollectorReviewDomainError,
            "active item cannot",
        ):
            self._item(resolved_at=self.added)

    def test_source_and_note_normalization_are_explicit(self) -> None:
        self.assertEqual(
            normalize_source_summary("  Hidden   Gem\n signal  "),
            "Hidden Gem signal",
        )
        self.assertEqual(
            normalize_review_note("  line one\r\nline  two\r  "),
            "line one\nline  two",
        )
        with self.assertRaisesRegex(
            CollectorReviewDomainError,
            "source_summary",
        ):
            self._item(source_summary="Hidden  Gem")
        with self.assertRaisesRegex(
            CollectorReviewDomainError,
            "review_note",
        ):
            self._item(review_note=" note ")

    def test_source_provenance_rules_are_enforced(self) -> None:
        with self.assertRaisesRegex(
            CollectorReviewDomainError,
            "Hidden Gem",
        ):
            self._item(source_type=WeekendObservationSource.HIDDEN_GEM)
        with self.assertRaisesRegex(
            CollectorReviewDomainError,
            "Hot-now",
        ):
            self._item(source_intelligence_run_id=8)
        hidden = self._item(
            source_type=WeekendObservationSource.HIDDEN_GEM,
            source_intelligence_run_id=8,
        )
        self.assertEqual(hidden.source_intelligence_run_id, 8)

    def test_hidden_gem_recursively_freezes_input_mappings(self) -> None:
        factors = {"demand": 80.0}
        supporting = {"nested": {"values": [1, 2]}}
        observation = HiddenGemObservation(
            observation_id=ObservationIdentity(
                WeekendObservationSource.HIDDEN_GEM,
                11,
            ),
            release_id=11,
            artist="Artist",
            title="Title",
            rank=1,
            hidden_gem_score=75.0,
            factor_scores=factors,
            supporting_metrics=supporting,
            summary="Persisted result.",
            evidence=("Evidence.",),
            execution_timestamp=self.observed,
            source_intelligence_run_id=4,
            source_marketplace_snapshot_id=None,
            marketplace_evidence=None,
            queue_membership=QueueMembership(),
        )

        factors["demand"] = 0.0
        supporting["nested"]["values"].append(3)  # type: ignore[index,union-attr]

        self.assertEqual(observation.factor_scores["demand"], 80.0)
        self.assertEqual(
            observation.supporting_metrics["nested"]["values"],
            (1, 2),
        )
        with self.assertRaises(TypeError):
            observation.factor_scores["demand"] = 1.0  # type: ignore[index]

    def test_new_entry_and_reconstructed_item_share_invariants(self) -> None:
        entry = NewWeekendReviewQueueEntry(
            release_id=11,
            added_at=self.added,
            status=WeekendReviewStatus.TO_REVIEW,
            review_note="",
            updated_at=self.added,
            resolved_at=None,
            source_type=WeekendObservationSource.HOT_NOW,
            source_observed_at=self.observed,
            source_summary="Hot now research signal.",
            source_intelligence_run_id=None,
            source_marketplace_snapshot_id=None,
        )
        self.assertEqual(entry.status, WeekendReviewStatus.TO_REVIEW)

    def _item(self, **changes: object) -> WeekendReviewQueueItem:
        values = {
            "queue_item_id": 1,
            "release_id": 11,
            "added_at": self.added,
            "status": WeekendReviewStatus.TO_REVIEW,
            "review_note": "",
            "updated_at": self.added,
            "resolved_at": None,
            "source_type": WeekendObservationSource.HOT_NOW,
            "source_observed_at": self.observed,
            "source_summary": "Hot now research signal.",
            "source_intelligence_run_id": None,
            "source_marketplace_snapshot_id": None,
        }
        values.update(changes)
        return WeekendReviewQueueItem(**values)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
