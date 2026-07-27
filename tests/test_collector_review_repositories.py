from __future__ import annotations

import tempfile
import threading
import sqlite3
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dip.app.collector_run import CollectorRunService
from dip.collector_review import (
    NewWeekendReviewQueueEntry,
    QueueAddOutcome,
    WeekendObservationSource,
    CollectorReviewIntegrityError,
    CollectorReviewPersistenceError,
    WeekendReviewConflictError,
    WeekendReviewStatus,
)
from dip.persistence.sqlite import (
    Database,
    SQLiteHotNowCalculatedStateRepository,
    SQLiteWeekendReviewQueueRepository,
)


UTC = timezone.utc


class CollectorReviewRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "collector-review.db"
        self.database = Database(self.path)
        self.database.conn.executemany(
            """
            INSERT INTO releases(release_id, artist, title)
            VALUES (?, ?, ?)
            """,
            ((1, "One", "First"), (2, "Two", "Second"), (3, "Three", "Third")),
        )
        self.database.conn.commit()
        self.repository = SQLiteWeekendReviewQueueRepository(self.database)
        self.observed = datetime(2026, 7, 25, 9, tzinfo=UTC)

    def tearDown(self) -> None:
        self.database.close()
        self.directory.cleanup()

    def test_add_duplicate_order_and_restart_reconstruct_typed_items(self) -> None:
        later = self._entry(2, self.observed + timedelta(hours=2))
        earlier = self._entry(1, self.observed + timedelta(hours=1))

        second = self.repository.add_or_get_existing(later)
        first = self.repository.add_or_get_existing(earlier)
        duplicate = self.repository.add_or_get_existing(
            replace(earlier, source_summary="Different frozen source.")
        )

        self.assertEqual(second.outcome, QueueAddOutcome.ADDED)
        self.assertEqual(first.outcome, QueueAddOutcome.ADDED)
        self.assertEqual(duplicate.outcome, QueueAddOutcome.EXISTING_ACTIVE)
        self.assertEqual(
            duplicate.item.source_summary,
            "Hot now research signal.",
        )
        self.assertEqual(
            tuple(item.release_id for item in self.repository.list_queue()),
            (1, 2),
        )

        self.database.close()
        self.database = Database(self.path)
        self.repository = SQLiteWeekendReviewQueueRepository(self.database)
        restored = self.repository.get_by_release_id(1)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.added_at, earlier.added_at)
        self.assertEqual(restored.status, WeekendReviewStatus.TO_REVIEW)

    def test_save_and_delete_use_optimistic_timestamp(self) -> None:
        added = self.repository.add_or_get_existing(
            self._entry(1, self.observed)
        ).item
        updated = replace(
            added,
            review_note="Inspect evidence.",
            updated_at=added.updated_at + timedelta(minutes=1),
        )
        persisted = self.repository.save(
            updated,
            expected_updated_at=added.updated_at,
        )
        self.assertEqual(persisted.review_note, "Inspect evidence.")

        with self.assertRaises(WeekendReviewConflictError):
            self.repository.save(
                replace(
                    persisted,
                    review_note="Stale edit.",
                    updated_at=persisted.updated_at + timedelta(minutes=1),
                ),
                expected_updated_at=added.updated_at,
            )
        deleted = self.repository.delete(
            persisted.queue_item_id,
            expected_updated_at=persisted.updated_at,
        )
        self.assertEqual(deleted.release_id, 1)
        self.assertIsNone(self.repository.get_by_id(persisted.queue_item_id))

    def test_nested_savepoint_respects_outer_rollback(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.database.transaction():
                self.repository.add_or_get_existing(
                    self._entry(1, self.observed)
                )
                raise RuntimeError("rollback")
        self.assertEqual(self.repository.list_queue(), ())

    def test_caller_owned_transaction_controls_add_save_and_delete(self) -> None:
        with self.database.transaction():
            added = self.repository.add_or_get_existing(
                self._entry(1, self.observed)
            ).item
            self.assertTrue(self.database.conn.in_transaction)
            saved = self.repository.save(
                replace(
                    added,
                    review_note="Owned transaction",
                    updated_at=added.updated_at + timedelta(microseconds=1),
                ),
                expected_updated_at=added.updated_at,
            )
            self.assertTrue(self.database.conn.in_transaction)
        self.assertEqual(
            self.repository.get_by_id(added.queue_item_id).review_note,
            "Owned transaction",
        )

        with self.assertRaisesRegex(RuntimeError, "outer rollback"):
            with self.database.transaction():
                self.repository.delete(
                    saved.queue_item_id,
                    expected_updated_at=saved.updated_at,
                )
                self.assertTrue(self.database.conn.in_transaction)
                raise RuntimeError("outer rollback")
        self.assertIsNotNone(self.repository.get_by_id(saved.queue_item_id))

        with self.database.transaction():
            self.repository.delete(
                saved.queue_item_id,
                expected_updated_at=saved.updated_at,
            )
        self.assertIsNone(self.repository.get_by_id(saved.queue_item_id))

        with self.database.transaction():
            with self.assertRaises(CollectorReviewPersistenceError):
                self.repository.add_or_get_existing(
                    replace(self._entry(2, self.observed), release_id=999)
                )
            isolated = self.repository.add_or_get_existing(
                self._entry(2, self.observed)
            ).item
        self.assertEqual(
            self.repository.get_by_id(isolated.queue_item_id),
            isolated,
        )

    def test_separate_connections_duplicate_add_and_stale_mutations(self) -> None:
        second_database = Database(self.path)
        second_repository = SQLiteWeekendReviewQueueRepository(second_database)
        try:
            barrier = threading.Barrier(2)
            results = []
            failures = []

            def add(repository, summary):
                try:
                    barrier.wait(timeout=5)
                    results.append(
                        repository.add_or_get_existing(
                            replace(
                                self._entry(1, self.observed),
                                source_summary=summary,
                            )
                        )
                    )
                except BaseException as exc:
                    failures.append(exc)

            threads = (
                threading.Thread(
                    target=add,
                    args=(self.repository, "First contender."),
                ),
                threading.Thread(
                    target=add,
                    args=(second_repository, "Second contender."),
                ),
            )
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
                self.assertFalse(thread.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(len(results), 2)
            self.assertEqual(
                {result.item.queue_item_id for result in results},
                {results[0].item.queue_item_id},
            )
            self.assertEqual(results[0].item, results[1].item)
            persisted = self.repository.list_queue()
            self.assertEqual(len(persisted), 1)
            self.assertEqual(results[0].item, persisted[0])
            self.assertEqual(
                {result.item.source_summary for result in results},
                {persisted[0].source_summary},
            )

            original = persisted[0]
            winner = self.repository.save(
                replace(
                    original,
                    review_note="Winner",
                    updated_at=original.updated_at + timedelta(microseconds=1),
                ),
                expected_updated_at=original.updated_at,
            )
            with self.assertRaises(WeekendReviewConflictError):
                second_repository.save(
                    replace(
                        original,
                        review_note="Stale",
                        updated_at=original.updated_at + timedelta(seconds=1),
                    ),
                    expected_updated_at=original.updated_at,
                )
            self.assertEqual(
                second_repository.get_by_id(original.queue_item_id).review_note,
                "Winner",
            )
            with self.assertRaises(WeekendReviewConflictError):
                second_repository.delete(
                    original.queue_item_id,
                    expected_updated_at=original.updated_at,
                )
            self.assertEqual(
                self.repository.get_by_id(original.queue_item_id),
                winner,
            )
        finally:
            second_database.close()

    def test_corrupt_reconstruction_and_constraint_matrix(self) -> None:
        added = self.repository.add_or_get_existing(
            self._entry(1, self.observed)
        ).item
        corruptions = {
            "id": ("id", 0),
            "added_at": ("added_at", "malformed"),
            "updated_at": ("updated_at", "malformed"),
            "source_observed_at": ("source_observed_at", "malformed"),
            "resolved_at": ("resolved_at", "malformed"),
            "status": ("status", "invalid"),
            "source_type": ("source_type", "invalid"),
            "source_summary": ("source_summary", " untrimmed "),
            "review_note": ("review_note", " untrimmed\rnote "),
        }
        for name, (column, value) in corruptions.items():
            with self.subTest(name=name):
                self.database.conn.execute("PRAGMA ignore_check_constraints=ON")
                self.database.conn.execute(
                    f"UPDATE weekend_review_queue SET {column}=? WHERE id=?",
                    (value, added.queue_item_id),
                )
                self.database.conn.commit()
                with self.assertRaises(CollectorReviewIntegrityError):
                    self.repository.list_queue()
                self.database.conn.rollback()
                self.database.conn.execute(
                    "DELETE FROM weekend_review_queue"
                )
                self.database.conn.commit()
                added = self.repository.add_or_get_existing(
                    self._entry(1, self.observed)
                ).item
                self.database.conn.execute("PRAGMA ignore_check_constraints=OFF")

        with self.assertRaises(CollectorReviewPersistenceError):
            self.repository.add_or_get_existing(
                replace(self._entry(2, self.observed), release_id=999)
            )

        base_values = (
            2,
            self.observed.isoformat(timespec="microseconds"),
            "to_review",
            "",
            self.observed.isoformat(timespec="microseconds"),
            None,
            "hot_now",
            self.observed.isoformat(timespec="microseconds"),
            "Valid source summary.",
            None,
            None,
        )
        invalid_sql_values = (
            ("invalid lifecycle", {2: "resolved"}),
            (
                "source after added",
                {
                    7: (
                        self.observed + timedelta(seconds=1)
                    ).isoformat(timespec="microseconds")
                },
            ),
            (
                "added after updated",
                {
                    1: (
                        self.observed + timedelta(seconds=1)
                    ).isoformat(timespec="microseconds")
                },
            ),
            ("hot intelligence provenance", {9: 999}),
            (
                "hidden without intelligence provenance",
                {6: "hidden_gem", 9: None},
            ),
            (
                "nonexistent intelligence provenance",
                {6: "hidden_gem", 9: 999},
            ),
            (
                "nonexistent marketplace provenance",
                {10: "collector-run-999"},
            ),
            (
                "resolved before added",
                {
                    2: "resolved",
                    5: (
                        self.observed - timedelta(seconds=1)
                    ).isoformat(timespec="microseconds"),
                },
            ),
            (
                "resolved after updated",
                {
                    2: "resolved",
                    5: (
                        self.observed + timedelta(seconds=1)
                    ).isoformat(timespec="microseconds"),
                },
            ),
        )
        insert_sql = """
            INSERT INTO weekend_review_queue(
                release_id, added_at, status, review_note, updated_at,
                resolved_at, source_type, source_observed_at, source_summary,
                source_intelligence_run_id, source_marketplace_snapshot_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for name, changes in invalid_sql_values:
            with self.subTest(name=name):
                values = list(base_values)
                for index, value in changes.items():
                    values[index] = value
                with self.assertRaises(sqlite3.IntegrityError):
                    self.database.conn.execute(insert_sql, values)

    def test_all_provenance_foreign_keys_restrict_parent_changes(self) -> None:
        captured = self.observed.isoformat(timespec="microseconds")
        self.database.conn.execute(
            """
            INSERT INTO marketplace_snapshots(
                snapshot_id, captured_at, source, status,
                schema_version, payload_json
            ) VALUES ('collector-run-1', ?, 'discogs', 'complete', 1, '{}')
            """,
            (captured,),
        )
        cursor = self.database.conn.execute(
            """
            INSERT INTO intelligence_runs(
                executed_at, executed_at_json, engine_version,
                collection_snapshot_id, result_count
            ) VALUES (?, ?, '0.2', NULL, 0)
            """,
            (captured, f'"{captured}"'),
        )
        run_id = int(cursor.lastrowid)
        self.database.conn.execute(
            """
            INSERT INTO weekend_review_queue(
                release_id, added_at, status, review_note, updated_at,
                resolved_at, source_type, source_observed_at, source_summary,
                source_intelligence_run_id, source_marketplace_snapshot_id
            ) VALUES (3, ?, 'to_review', '', ?, NULL, 'hidden_gem', ?,
                      'Hidden Gem source.', ?, 'collector-run-1')
            """,
            (captured, captured, captured, run_id),
        )
        self.database.conn.commit()

        attempts = (
            ("DELETE FROM releases WHERE release_id=3", ()),
            ("UPDATE releases SET release_id=30 WHERE release_id=3", ()),
            ("DELETE FROM intelligence_runs WHERE id=?", (run_id,)),
            (
                "UPDATE intelligence_runs SET id=? WHERE id=?",
                (run_id + 1, run_id),
            ),
            (
                "DELETE FROM marketplace_snapshots WHERE snapshot_id=?",
                ("collector-run-1",),
            ),
            (
                """
                UPDATE marketplace_snapshots SET snapshot_id=?
                WHERE snapshot_id=?
                """,
                ("collector-run-2", "collector-run-1"),
            ),
        )
        for statement, parameters in attempts:
            with self.subTest(statement=statement):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.database.conn.execute(statement, parameters)
                self.database.conn.rollback()
        self.assertIsNotNone(self.repository.get_by_release_id(3))

    def test_restart_preserves_frozen_hot_now_and_hidden_gem_evidence(self) -> None:
        captured = self.observed.isoformat(timespec="microseconds")
        self.database.conn.execute(
            """
            INSERT INTO marketplace_snapshots(
                snapshot_id, captured_at, source, status,
                schema_version, payload_json
            ) VALUES ('collector-run-7', ?, 'discogs', 'complete', 1, '{}')
            """,
            (captured,),
        )
        run_cursor = self.database.conn.execute(
            """
            INSERT INTO intelligence_runs(
                executed_at, executed_at_json, engine_version,
                collection_snapshot_id, result_count,
                marketplace_snapshot_id
            ) VALUES (?, ?, '0.2', NULL, 0, 'collector-run-7')
            """,
            (captured, f'"{captured}"'),
        )
        run_id = int(run_cursor.lastrowid)
        self.database.conn.commit()
        hot = self.repository.add_or_get_existing(
            replace(
                self._entry(1, self.observed),
                review_note="Frozen note",
                source_summary="Original Hot now evidence.",
                source_marketplace_snapshot_id="collector-run-7",
            )
        ).item
        hidden = self.repository.add_or_get_existing(
            NewWeekendReviewQueueEntry(
                release_id=2,
                added_at=self.observed,
                status=WeekendReviewStatus.REVIEWING,
                review_note="Hidden note",
                updated_at=self.observed,
                resolved_at=None,
                source_type=WeekendObservationSource.HIDDEN_GEM,
                source_observed_at=self.observed,
                source_summary="Original Hidden Gem evidence.",
                source_intelligence_run_id=run_id,
                source_marketplace_snapshot_id="collector-run-7",
            )
        ).item

        self.database.close()
        self.database = Database(self.path)
        self.repository = SQLiteWeekendReviewQueueRepository(self.database)
        self.database.conn.execute(
            """
            INSERT INTO scores(
                release_id, calculated_at, opportunity_score,
                sell_window, explanation
            ) VALUES (1, ?, 1.0, 'Not urgent', 'Replacement evidence')
            ON CONFLICT(release_id) DO UPDATE SET
                calculated_at=excluded.calculated_at,
                opportunity_score=excluded.opportunity_score,
                sell_window=excluded.sell_window,
                explanation=excluded.explanation
            """,
            ((self.observed + timedelta(days=1)).isoformat(),),
        )
        self.database.conn.commit()

        self.assertEqual(self.repository.get_by_id(hot.queue_item_id), hot)
        self.assertEqual(self.repository.get_by_id(hidden.queue_item_id), hidden)

    def test_hot_now_query_uses_exact_score_origin_and_complete_order(self) -> None:
        run = self.database.start_analysis_run()
        for release_id, opportunity, momentum in (
            (1, 80.0, 40.0),
            (2, 80.0, 40.0),
            (3, 70.0, 60.0),
        ):
            captured = (
                self.observed + timedelta(minutes=release_id)
            ).isoformat(timespec="seconds")
            self.database.add_snapshot(
                run,
                release_id,
                captured,
                {
                    "wants": release_id * 10,
                    "haves": release_id,
                    "copies_for_sale": 2,
                    "lowest_price": 12.5 + release_id,
                    "currency": "GBP",
                    "discogs_uri": f"https://example.test/{release_id}",
                },
            )
            self.database.upsert_score(
                release_id,
                captured,
                {
                    "value_score": 10.0,
                    "demand_score": 20.0,
                    "liquidity_score": 30.0,
                    "momentum_score": momentum,
                    "opportunity_score": opportunity,
                    "sell_window": "Hot now",
                    "priority": "Worth reviewing",
                    "explanation": "Stored explanation.",
                },
            )
        self.database.complete_analysis_run(run, 3, 3, 0)

        rows = SQLiteHotNowCalculatedStateRepository(
            self.database
        ).list_hot_now()

        self.assertEqual(tuple(row.release_id for row in rows), (2, 1, 3))
        self.assertEqual(rows[0].legacy_analysis_run_id, run)
        self.assertEqual(str(rows[0].lowest_price), "14.5")
        self.assertEqual(rows[0].wants, 20)

    def test_later_collector_run_does_not_mutate_durable_queue_state(self) -> None:
        queued = self.repository.add_or_get_existing(
            self._entry(1, self.observed)
        ).item

        class Provider:
            def get_release(self, release_id):
                return {
                    "wants": 100,
                    "haves": 20,
                    "copies_for_sale": 2,
                    "lowest_price": Decimal("12.50"),
                    "currency": "GBP",
                }

        class Recorder:
            def record_snapshot(self, snapshot):
                return snapshot

        class Executor:
            def execute_collector_run(self, **values):
                return object()

        service = CollectorRunService(
            self.database,
            lambda token: Provider(),
            lambda current, previous: {
                "value_score": 10.0,
                "demand_score": 20.0,
                "liquidity_score": 30.0,
                "momentum_score": 40.0,
                "opportunity_score": 50.0,
                "sell_window": "Hot now",
                "priority": "Worth reviewing",
                "explanation": "Stored explanation.",
            },
            "0.4.0",
            0,
            Recorder(),
            Executor(),
            clock=lambda: self.observed + timedelta(days=1),
            wait=lambda seconds: None,
        )

        service.run("temporary-token")

        self.assertEqual(self.repository.get_by_id(queued.queue_item_id), queued)

    def _entry(
        self,
        release_id: int,
        added_at: datetime,
    ) -> NewWeekendReviewQueueEntry:
        return NewWeekendReviewQueueEntry(
            release_id=release_id,
            added_at=added_at,
            status=WeekendReviewStatus.TO_REVIEW,
            review_note="",
            updated_at=added_at,
            resolved_at=None,
            source_type=WeekendObservationSource.HOT_NOW,
            source_observed_at=self.observed,
            source_summary="Hot now research signal.",
            source_intelligence_run_id=None,
            source_marketplace_snapshot_id=None,
        )


if __name__ == "__main__":
    unittest.main()
