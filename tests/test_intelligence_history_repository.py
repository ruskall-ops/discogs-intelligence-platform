from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceDeserializationError,
    IntelligenceHistoryRecord,
    IntelligenceHistoryRepository,
    IntelligenceHistoryRun,
    IntelligenceSerializationError,
)
from dip.persistence.sqlite import Database, SQLiteIntelligenceHistoryRepository


class IntelligenceHistoryRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "history.db"
        self.database = Database(database_path)
        self.repository = SQLiteIntelligenceHistoryRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def test_implements_repository_protocol(self) -> None:
        repository: IntelligenceHistoryRepository = self.repository

        self.assertIs(repository, self.repository)

    def test_empty_repository_returns_no_history(self) -> None:
        self.assertIsNone(self.repository.latest_run())
        self.assertIsNone(self.repository.previous_run())
        self.assertIsNone(self.repository.latest_result("collection_health"))
        self.assertIsNone(self.repository.previous_result("collection_health"))
        self.assertEqual(
            self.repository.history_for_module("collection_health"),
            (),
        )

    def test_saves_execution_with_zero_results(self) -> None:
        run = self._run(datetime(2026, 7, 21, 10), result_count=0)

        saved_run = self.repository.save_execution(run, ())

        self.assertEqual(self.repository.latest_run(), saved_run)
        self.assertEqual(saved_run.result_count, 0)

    def test_saves_and_reconstructs_a_complete_execution(self) -> None:
        run = self._run(
            datetime(2026, 7, 21, 10, tzinfo=timezone.utc),
            result_count=2,
            engine_version="0.3.0",
            collection_snapshot_id=42,
        )
        records = (
            self._record("collection_health", score=82, module_version="1.2"),
            self._record("hidden_gems", score=7, module_version="2.0"),
        )

        saved_run = self.repository.save_execution(run, records)

        self.assertIsNotNone(saved_run.run_id)
        self.assertEqual(self.repository.latest_run(), saved_run)
        self.assertEqual(saved_run.engine_version, "0.3.0")
        self.assertEqual(saved_run.collection_snapshot_id, 42)
        collection_health = self.repository.latest_result("collection_health")
        self.assertIsNotNone(collection_health.record_id)
        self.assertEqual(collection_health.run_id, saved_run.run_id)
        self.assertEqual(collection_health.module_version, "1.2")
        self.assertEqual(collection_health.metrics["score"], 82)

    def test_latest_and_previous_runs_are_ordered_by_execution_time(self) -> None:
        first = self._save_at(datetime(2026, 7, 20, 10), score=70)
        second = self._save_at(datetime(2026, 7, 21, 10), score=80)
        latest = self._save_at(datetime(2026, 7, 22, 10), score=90)

        self.assertEqual(self.repository.latest_run(), latest)
        self.assertEqual(self.repository.previous_run(), second)
        self.assertNotEqual(self.repository.previous_run(), first)

    def test_module_results_are_latest_previous_and_chronological(self) -> None:
        timestamps = (
            datetime(2026, 7, 20, 10),
            datetime(2026, 7, 21, 10),
            datetime(2026, 7, 22, 10),
        )
        for score, executed_at in zip((70, 80, 90), timestamps, strict=True):
            self._save_at(executed_at, score=score)

        history = self.repository.history_for_module("collection_health")

        self.assertEqual(
            tuple(record.metrics["score"] for record in history),
            (70, 80, 90),
        )
        self.assertEqual(
            self.repository.latest_result("collection_health").metrics["score"],
            90,
        )
        self.assertEqual(
            self.repository.previous_result("collection_health").metrics["score"],
            80,
        )

    def test_module_retrieval_skips_runs_without_that_module(self) -> None:
        self._save_at(datetime(2026, 7, 20, 10), score=70)
        run = self._run(datetime(2026, 7, 21, 10), result_count=1)
        self.repository.save_execution(run, (self._record("hidden_gems", 5),))
        self._save_at(datetime(2026, 7, 22, 10), score=90)

        self.assertEqual(
            self.repository.previous_result("collection_health").metrics["score"],
            70,
        )

    def test_duplicate_module_ids_are_allowed_across_runs(self) -> None:
        self._save_at(datetime(2026, 7, 20, 10), score=70)
        self._save_at(datetime(2026, 7, 21, 10), score=80)

        rows = self.database.conn.execute(
            """
            SELECT COUNT(*)
            FROM intelligence_results
            WHERE module_id = ?
            """,
            ("collection_health",),
        ).fetchone()[0]

        self.assertEqual(rows, 2)

    def test_run_id_breaks_equal_timestamp_ties_deterministically(self) -> None:
        executed_at = datetime(2026, 7, 21, 10, tzinfo=timezone.utc)
        first = self._save_at(executed_at, score=70)
        second = self._save_at(executed_at, score=80)

        self.assertGreater(second.run_id, first.run_id)
        self.assertEqual(self.repository.latest_run(), second)
        self.assertEqual(self.repository.previous_run(), first)
        self.assertEqual(
            tuple(
                result.metrics["score"]
                for result in self.repository.history_for_module(
                    "collection_health"
                )
            ),
            (70, 80),
        )

    def test_aware_timestamps_are_ordered_by_their_utc_instant(self) -> None:
        later_wall_time_but_earlier_instant = datetime(
            2026,
            7,
            21,
            10,
            tzinfo=timezone(timedelta(hours=5)),
        )
        earlier_wall_time_but_later_instant = datetime(
            2026,
            7,
            21,
            9,
            tzinfo=timezone.utc,
        )
        first = self._save_at(later_wall_time_but_earlier_instant, score=70)
        second = self._save_at(earlier_wall_time_but_later_instant, score=80)

        self.assertEqual(self.repository.latest_run(), second)
        self.assertEqual(self.repository.previous_run(), first)

    def test_duplicate_module_in_one_execution_rolls_back_every_insert(self) -> None:
        run = self._run(datetime(2026, 7, 21, 10), result_count=2)
        records = (
            self._record("collection_health", 70),
            self._record("collection_health", 80),
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_execution(run, records)

        run_count = self.database.conn.execute(
            "SELECT COUNT(*) FROM intelligence_runs"
        ).fetchone()[0]
        result_count = self.database.conn.execute(
            "SELECT COUNT(*) FROM intelligence_results"
        ).fetchone()[0]
        self.assertEqual((run_count, result_count), (0, 0))

    def test_active_caller_transaction_retains_commit_ownership(self) -> None:
        self.database.conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?)",
            ("caller", "pending"),
        )
        self.assertTrue(self.database.conn.in_transaction)

        self._save_at(datetime(2026, 7, 21, 10), score=70)

        self.assertTrue(self.database.conn.in_transaction)
        self.database.conn.rollback()
        self.assertEqual(
            self.database.conn.execute(
                "SELECT COUNT(*) FROM app_settings WHERE key = ?",
                ("caller",),
            ).fetchone()[0],
            0,
        )
        self.assertIsNone(self.repository.latest_run())

    def test_repository_failure_preserves_unrelated_caller_work(self) -> None:
        self.database.conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?)",
            ("caller", "preserved"),
        )
        run = self._run(datetime(2026, 7, 21, 10), result_count=2)

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_execution(
                run,
                (
                    self._record("collection_health", 70),
                    self._record("collection_health", 80),
                ),
            )

        self.assertTrue(self.database.conn.in_transaction)
        self.assertEqual(
            self.database.conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                ("caller",),
            ).fetchone()[0],
            "preserved",
        )
        self.assertIsNone(self.repository.latest_run())
        self.database.conn.commit()

    def test_repository_uses_database_lock_without_an_independent_lock(self) -> None:
        attempted = threading.Event()
        finished = threading.Event()

        def retrieve() -> None:
            attempted.set()
            self.repository.latest_run()
            finished.set()

        with self.database.locked_connection():
            thread = threading.Thread(target=retrieve)
            thread.start()
            self.assertTrue(attempted.wait(1))
            self.assertFalse(finished.wait(0.05))

        thread.join(timeout=1)
        self.assertTrue(finished.is_set())
        self.assertFalse(hasattr(self.repository, "_lock"))

    def test_serialization_failure_happens_before_transaction_entry(self) -> None:
        run = self._run(datetime(2026, 7, 21, 10), result_count=1)
        record = self._record("collection_health", 70)
        record = IntelligenceHistoryRecord(
            record_id=None,
            run_id=None,
            module_id=record.module_id,
            module_version=record.module_version,
            status=record.status,
            summary=record.summary,
            metrics={"score": float("nan")},
        )

        with self.assertRaises(IntelligenceSerializationError):
            self.repository.save_execution(run, (record,))

        self.assertFalse(self.database.conn.in_transaction)
        self.assertIsNone(self.repository.latest_run())

    def test_retrieval_rejects_malformed_stored_payloads(self) -> None:
        saved_run = self._save_at(datetime(2026, 7, 21, 10), score=70)
        self.database.conn.execute(
            """
            UPDATE intelligence_results
            SET metrics_json = ?
            WHERE run_id = ?
            """,
            ('{"__dip_type__":"mapping","items":"invalid"}', saved_run.run_id),
        )
        self.database.conn.commit()

        with self.assertRaises(IntelligenceDeserializationError):
            self.repository.latest_result("collection_health")

    def test_retrieval_rejects_malformed_run_timestamp(self) -> None:
        saved_run = self._save_at(datetime(2026, 7, 21, 10), score=70)
        self.database.conn.execute(
            """
            UPDATE intelligence_runs
            SET executed_at_json = ?
            WHERE id = ?
            """,
            ('"not a datetime"', saved_run.run_id),
        )
        self.database.conn.commit()

        with self.assertRaises(IntelligenceDeserializationError):
            self.repository.latest_run()

    def test_optional_versions_and_snapshot_linkage_are_preserved(self) -> None:
        run = self._run(datetime(2026, 7, 21, 10), result_count=1)
        saved_run = self.repository.save_execution(
            run,
            (self._record("collection_health", 70, module_version=None),),
        )

        restored_run = self.repository.latest_run()
        restored_record = self.repository.latest_result("collection_health")
        self.assertEqual(restored_run, saved_run)
        self.assertIsNone(restored_run.engine_version)
        self.assertIsNone(restored_run.collection_snapshot_id)
        self.assertIsNone(restored_record.module_version)

    def test_result_foreign_key_is_enforced_and_run_delete_is_restricted(self) -> None:
        saved_run = self._save_at(datetime(2026, 7, 21, 10), score=70)

        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.conn:
                self.database.conn.execute(
                    "DELETE FROM intelligence_runs WHERE id = ?",
                    (saved_run.run_id,),
                )

        self.assertIsNotNone(self.repository.latest_run())

    def test_orphan_result_insert_is_rejected_by_foreign_key(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.conn:
                self.database.conn.execute(
                    """
                    INSERT INTO intelligence_results (
                        run_id,
                        module_id,
                        module_version,
                        status_json,
                        summary,
                        insights_json,
                        metrics_json,
                        evidence_json,
                        diagnostics_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        999,
                        "collection_health",
                        None,
                        '"completed"',
                        "Completed.",
                        '{"__dip_type__":"tuple","items":[]}',
                        '{"__dip_type__":"mapping","items":[]}',
                        '{"__dip_type__":"tuple","items":[]}',
                        '{"__dip_type__":"tuple","items":[]}',
                    ),
                )

    def test_save_rejects_existing_ids_and_incorrect_result_count(self) -> None:
        run = self._run(datetime(2026, 7, 21, 10), result_count=1)

        with self.assertRaisesRegex(ValueError, "result_count"):
            self.repository.save_execution(run, ())
        with self.assertRaisesRegex(ValueError, "must not have a run_id"):
            self.repository.save_execution(
                IntelligenceHistoryRun(5, run.executed_at, result_count=0),
                (),
            )
        with self.assertRaisesRegex(ValueError, "must not have a record_id"):
            self.repository.save_execution(
                run,
                (
                    IntelligenceHistoryRecord(
                        record_id=5,
                        run_id=None,
                        module_id="collection_health",
                        module_version=None,
                        status=IntelligenceStatus.COMPLETED,
                        summary="Completed.",
                    ),
                ),
            )
        with self.assertRaisesRegex(ValueError, "run_id=None"):
            self.repository.save_execution(
                run,
                (
                    IntelligenceHistoryRecord(
                        record_id=None,
                        run_id=99,
                        module_id="collection_health",
                        module_version=None,
                        status=IntelligenceStatus.COMPLETED,
                        summary="Completed.",
                    ),
                ),
            )

    def test_closed_connection_failure_matches_existing_sqlite_behavior(self) -> None:
        self.database.close()

        with self.assertRaises(sqlite3.ProgrammingError):
            self.repository.latest_run()

    def _save_at(
        self,
        executed_at: datetime,
        score: int,
    ) -> IntelligenceHistoryRun:
        run = self._run(executed_at, result_count=1)
        return self.repository.save_execution(
            run,
            (self._record("collection_health", score),),
        )

    @staticmethod
    def _run(
        executed_at: datetime,
        *,
        result_count: int,
        engine_version: str | None = None,
        collection_snapshot_id: int | None = None,
    ) -> IntelligenceHistoryRun:
        return IntelligenceHistoryRun(
            run_id=None,
            executed_at=executed_at,
            engine_version=engine_version,
            collection_snapshot_id=collection_snapshot_id,
            result_count=result_count,
        )

    @staticmethod
    def _record(
        module_id: str,
        score: int,
        module_version: str | None = "1.0",
    ) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=None,
            run_id=None,
            module_id=module_id,
            module_version=module_version,
            status=IntelligenceStatus.COMPLETED,
            summary=f"{module_id} completed.",
            insights=("Stable result",),
            metrics={"score": score, "history": [score - 1, score]},
            evidence=("Deterministic evidence",),
            diagnostics=(),
        )


if __name__ == "__main__":
    unittest.main()
