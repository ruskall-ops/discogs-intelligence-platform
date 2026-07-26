from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryConflictError,
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)
from dip.intelligence_history.serialization import IntelligenceDeserializationError
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)
from dip.persistence.sqlite import (
    Database,
    SQLiteIntelligenceHistoryRepository,
    SQLiteMarketplaceHistoryRepository,
)


EXECUTED_AT = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)


def _snapshot(snapshot_id: str = "collector-run-9") -> MarketplaceSnapshot:
    return MarketplaceSnapshot(
        snapshot_id,
        EXECUTED_AT,
        "discogs",
        MarketplaceDataStatus.COMPLETE,
        (
            MarketplaceReleaseObservation(
                1,
                EXECUTED_AT,
                MarketplaceDataStatus.COMPLETE,
                num_wanted=0,
            ),
        ),
    )


def _run(snapshot_id: str | None = "collector-run-9") -> IntelligenceHistoryRun:
    return IntelligenceHistoryRun(
        None,
        EXECUTED_AT,
        "0.2",
        None,
        2,
        snapshot_id,
    )


def _records() -> tuple[IntelligenceHistoryRecord, ...]:
    return (
        IntelligenceHistoryRecord(
            None,
            None,
            "collection_health",
            "1.0",
            IntelligenceStatus.COMPLETED,
            "Complete.",
            ("Healthy.",),
            {"coverage": 1},
            ("Canonical.",),
            (),
        ),
        IntelligenceHistoryRecord(
            None,
            None,
            "historical_intelligence",
            "0.2",
            IntelligenceStatus.SKIPPED,
            "A predecessor is not yet available.",
            (),
            {"snapshot_count": 1},
            ("One canonical snapshot was available.",),
            ("Two snapshots are required.",),
        ),
    )


class IntelligenceHistoryProvenanceTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "history.db"
        self.database = Database(self.path)
        SQLiteMarketplaceHistoryRepository(self.database).save_snapshot(_snapshot())
        self.repository = SQLiteIntelligenceHistoryRepository(self.database)

    def tearDown(self):
        self.database.close()
        self.temporary.cleanup()

    def test_exact_replay_returns_existing_identity_without_mutation(self):
        first = self.repository.save_execution(_run(), _records())
        original_records = self.repository.records_for_run(first.run_id)

        replayed = self.repository.save_execution(_run(), _records())

        self.assertEqual(replayed, first)
        self.assertEqual(
            self.repository.records_for_run(first.run_id),
            original_records,
        )
        with self.database.locked_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM intelligence_runs"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM intelligence_results"
                ).fetchone()[0],
                2,
            )

    def test_replay_survives_reopen_and_different_content_conflicts(self):
        first = self.repository.save_execution(_run(), _records())
        self.database.close()
        self.database = Database(self.path)
        self.repository = SQLiteIntelligenceHistoryRepository(self.database)
        self.assertEqual(
            self.repository.save_execution(_run(), _records()).run_id,
            first.run_id,
        )

        differences = (
            replace(_run(), engine_version="different"),
            replace(_run(), collection_snapshot_id=4),
            replace(_run(), executed_at=EXECUTED_AT.replace(hour=13)),
        )
        for changed in differences:
            with self.subTest(changed=changed), self.assertRaises(
                IntelligenceHistoryConflictError
            ):
                self.repository.save_execution(changed, _records())
        changed_records = (
            _records()[1],
            _records()[0],
        )
        with self.assertRaises(IntelligenceHistoryConflictError):
            self.repository.save_execution(_run(), changed_records)
        with self.database.locked_connection() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM intelligence_runs"
                ).fetchone()[0],
                1,
            )

    def test_every_record_content_difference_is_a_conflict(self):
        self.repository.save_execution(_run(), _records())
        original = _records()
        variants = (
            replace(original[0], module_id="changed_module"),
            replace(original[0], module_version="9.9"),
            replace(original[0], status=IntelligenceStatus.SKIPPED),
            replace(original[0], summary="Changed."),
            replace(original[0], insights=("Changed.",)),
            replace(original[0], metrics={"coverage": 2}),
            replace(original[0], evidence=("Changed.",)),
            replace(original[0], diagnostics=("Changed.",)),
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(
                IntelligenceHistoryConflictError
            ):
                self.repository.save_execution(
                    _run(),
                    (changed, original[1]),
                )
        with self.assertRaises(IntelligenceHistoryConflictError):
            self.repository.save_execution(
                replace(_run(), result_count=1),
                (original[0],),
            )

    def test_null_provenance_remains_append_only_and_missing_fk_is_rejected(self):
        null_run = replace(_run(None), result_count=0)
        first = self.repository.save_execution(null_run, ())
        second = self.repository.save_execution(null_run, ())
        self.assertNotEqual(first.run_id, second.run_id)

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save_execution(
                replace(_run("missing"), result_count=0),
                (),
            )

    def test_persisted_input_ids_are_rejected_before_replay(self):
        persisted = self.repository.save_execution(_run(), _records())
        with self.assertRaisesRegex(ValueError, "run_id"):
            self.repository.save_execution(persisted, _records())
        with self.assertRaisesRegex(ValueError, "record_id"):
            self.repository.save_execution(
                _run(),
                (replace(_records()[0], record_id=5), _records()[1]),
            )

    def test_corrupt_existing_provenance_is_not_treated_as_replay_or_conflict(self):
        persisted = self.repository.save_execution(_run(), _records())
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE intelligence_runs SET result_count = 1 WHERE id = ?",
                (persisted.run_id,),
            )

        with self.assertRaises(IntelligenceDeserializationError):
            self.repository.save_execution(_run(), _records())

    def test_schema_has_restricting_fk_and_partial_unique_index(self):
        with self.database.locked_connection() as connection:
            foreign_key = next(
                row
                for row in connection.execute(
                    "PRAGMA foreign_key_list(intelligence_runs)"
                ).fetchall()
                if row["from"] == "marketplace_snapshot_id"
            )
            self.assertEqual(
                (
                    foreign_key["table"],
                    foreign_key["to"],
                    foreign_key["on_update"],
                    foreign_key["on_delete"],
                ),
                ("marketplace_snapshots", "snapshot_id", "RESTRICT", "RESTRICT"),
            )
            index = next(
                row
                for row in connection.execute(
                    "PRAGMA index_list(intelligence_runs)"
                ).fetchall()
                if row["name"] == "idx_intelligence_runs_marketplace_snapshot"
            )
            self.assertEqual((index["unique"], index["partial"]), (1, 1))
            sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = ?",
                ("idx_intelligence_runs_marketplace_snapshot",),
            ).fetchone()["sql"]
            self.assertIn(
                "WHERE marketplace_snapshot_id IS NOT NULL",
                " ".join(sql.split()),
            )

    def test_first_save_participates_in_caller_transaction_and_rolls_back(self):
        self.database.conn.execute("BEGIN")

        persisted = self.repository.save_execution(_run(), _records())

        self.assertTrue(self.database.conn.in_transaction)
        self.assertIsNotNone(self.repository.run_by_id(persisted.run_id))
        self.database.conn.rollback()
        self.assertIsNone(self.repository.run_by_id(persisted.run_id))
        self.assertEqual(self.repository.records_for_run(persisted.run_id), ())

    def test_replay_and_conflict_preserve_usable_caller_transaction(self):
        persisted = self.repository.save_execution(_run(), _records())
        self.database.conn.execute("BEGIN")

        replayed = self.repository.save_execution(_run(), _records())
        self.assertEqual(replayed.run_id, persisted.run_id)
        self.assertTrue(self.database.conn.in_transaction)
        with self.assertRaises(IntelligenceHistoryConflictError):
            self.repository.save_execution(
                replace(_run(), engine_version="conflicting"),
                _records(),
            )
        self.assertTrue(self.database.conn.in_transaction)
        self.assertEqual(
            self.database.conn.execute("SELECT 1").fetchone()[0],
            1,
        )
        self.assertEqual(
            self.database.conn.execute(
                "SELECT COUNT(*) FROM intelligence_runs"
            ).fetchone()[0],
            1,
        )
        self.database.conn.rollback()
        self.assertEqual(self.repository.latest_run(), persisted)

    def test_identical_separate_connection_race_resolves_to_one_execution(self):
        second_database = Database(self.path)
        second_repository = SQLiteIntelligenceHistoryRepository(second_database)
        try:
            outcomes, errors = self._concurrent_saves(
                (
                    (self.repository, _run(), _records()),
                    (second_repository, _run(), _records()),
                )
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(outcomes), 2)
            self.assertEqual(len(set(outcomes)), 1)
            self.assertEqual(
                self._row_counts(),
                (1, 2),
            )
            run = self.repository.latest_run()
            self.assertEqual(run.run_id, outcomes[0])
            self.assertEqual(
                len(self.repository.records_for_run(run.run_id)),
                2,
            )
        finally:
            second_database.close()

    def test_conflicting_separate_connection_race_keeps_one_complete_execution(self):
        second_database = Database(self.path)
        second_repository = SQLiteIntelligenceHistoryRepository(second_database)
        conflicting = (
            replace(_records()[0], summary="Conflicting immutable content."),
            _records()[1],
        )
        try:
            outcomes, errors = self._concurrent_saves(
                (
                    (self.repository, _run(), _records()),
                    (second_repository, _run(), conflicting),
                )
            )
            self.assertEqual(len(outcomes), 1)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(
                errors[0],
                IntelligenceHistoryConflictError,
            )
            self.assertNotIsInstance(errors[0], sqlite3.OperationalError)
            self.assertEqual(self._row_counts(), (1, 2))
            run = self.repository.latest_run()
            records = self.repository.records_for_run(run.run_id)
            self.assertEqual(len(records), 2)
            self.assertEqual(run.result_count, len(records))
        finally:
            second_database.close()

    def _concurrent_saves(self, saves):
        barrier = threading.Barrier(len(saves))
        lock = threading.Lock()
        outcomes = []
        errors = []

        def save(repository, run, records):
            try:
                barrier.wait(timeout=5)
                persisted = repository.save_execution(run, records)
            except Exception as exc:
                with lock:
                    errors.append(exc)
            else:
                with lock:
                    outcomes.append(persisted.run_id)

        threads = [
            threading.Thread(
                target=save,
                args=values,
                daemon=True,
            )
            for values in saves
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        return outcomes, errors

    def _row_counts(self):
        with self.database.locked_connection() as connection:
            return (
                connection.execute(
                    "SELECT COUNT(*) FROM intelligence_runs"
                ).fetchone()[0],
                connection.execute(
                    "SELECT COUNT(*) FROM intelligence_results"
                ).fetchone()[0],
            )


if __name__ == "__main__":
    unittest.main()
