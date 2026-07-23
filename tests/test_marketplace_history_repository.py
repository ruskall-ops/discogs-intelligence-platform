from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dip.marketplace_history import (
    MarketplaceHistoryIntegrityError,
    MarketplaceHistoryPersistenceError,
    MarketplaceHistoryRepository,
    MarketplaceSnapshotConflictError,
)
from dip.marketplace_intelligence import (
    MARKETPLACE_SCHEMA_VERSION,
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceDiagnosticSeverity,
    MarketplaceListingObservation,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSerializationError,
    MarketplaceSnapshot,
    dumps_marketplace_snapshot,
)
from dip.persistence.sqlite import Database, SQLiteMarketplaceHistoryRepository


class MarketplaceHistoryRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database = Database(
            Path(self.temp_directory.name) / "marketplace_history.db"
        )
        self.repository = SQLiteMarketplaceHistoryRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def test_implements_repository_protocol_and_empty_absence_contract(self) -> None:
        repository: MarketplaceHistoryRepository = self.repository

        self.assertIs(repository, self.repository)
        self.assertIsNone(repository.get_snapshot("missing"))
        self.assertIsNone(repository.latest_snapshot())
        self.assertEqual(repository.recent_snapshots(5), ())
        self.assertEqual(repository.all_snapshots(), ())
        self.assertIsNone(repository.previous_snapshot("missing"))

    def test_full_snapshot_round_trip_uses_the_canonical_payload(self) -> None:
        captured_at = datetime(
            2026,
            7,
            21,
            18,
            45,
            12,
            345678,
            tzinfo=timezone(timedelta(hours=5, minutes=30)),
        )
        snapshot = complete_snapshot(
            "snapshot-full",
            captured_at,
            amount="10.2300",
        )
        original_payload = dumps_marketplace_snapshot(snapshot)

        result = self.repository.save_snapshot(snapshot)
        restored = self.repository.get_snapshot(snapshot.snapshot_id)

        self.assertIsNone(result)
        self.assertEqual(restored, snapshot)
        self.assertIsNot(restored, snapshot)
        self.assertEqual(
            restored.release_observations[0].lowest_price.amount.as_tuple(),
            Decimal("10.2300").as_tuple(),
        )
        self.assertEqual(
            restored.captured_at.utcoffset(),
            timedelta(hours=5, minutes=30),
        )
        self.assertEqual(restored.listing_observations, snapshot.listing_observations)
        self.assertEqual(
            dict(restored.diagnostics[0].details),
            {"attempt": "1", "provider": "discogs"},
        )

        row = self.database.conn.execute(
            "SELECT * FROM marketplace_snapshots WHERE snapshot_id = ?",
            (snapshot.snapshot_id,),
        ).fetchone()
        self.assertEqual(row["payload_json"], original_payload)
        self.assertEqual(row["schema_version"], MARKETPLACE_SCHEMA_VERSION)
        self.assertEqual(row["source"], snapshot.source)
        self.assertEqual(row["status"], snapshot.status.value)
        self.assertEqual(
            row["captured_at"],
            captured_at.astimezone(timezone.utc).isoformat(timespec="microseconds"),
        )
        raw_money = json.loads(row["payload_json"])["release_observations"][0][
            "lowest_price"
        ]["amount"]
        self.assertEqual(raw_money, "10.2300")
        self.assertIsInstance(raw_money, str)

    def test_every_valid_snapshot_status_round_trips_without_filtering(self) -> None:
        captured_at = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
        snapshots = tuple(
            status_snapshot(status, captured_at + timedelta(minutes=index))
            for index, status in enumerate(MarketplaceDataStatus)
        )

        for snapshot in snapshots:
            self.repository.save_snapshot(snapshot)

        self.assertEqual(
            tuple(
                self.repository.get_snapshot(snapshot.snapshot_id)
                for snapshot in snapshots
            ),
            snapshots,
        )
        self.assertEqual(
            {snapshot.status for snapshot in self.repository.recent_snapshots(10)},
            set(MarketplaceDataStatus),
        )

    def test_identical_save_is_idempotent_and_conflict_never_overwrites(self) -> None:
        snapshot = complete_snapshot(
            "stable-id",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        self.repository.save_snapshot(snapshot)
        original_payload = self._stored_payload(snapshot.snapshot_id)

        self.repository.save_snapshot(snapshot)

        self.assertEqual(self._snapshot_count(), 1)
        self.assertEqual(self._stored_payload(snapshot.snapshot_id), original_payload)

        conflicting = replace(snapshot, source_version="different-provider-version")
        with self.assertRaises(MarketplaceSnapshotConflictError):
            self.repository.save_snapshot(conflicting)

        self.assertEqual(self._snapshot_count(), 1)
        self.assertEqual(self._stored_payload(snapshot.snapshot_id), original_payload)
        self.assertEqual(self.repository.get_snapshot(snapshot.snapshot_id), snapshot)

    def test_distinct_snapshot_saves_without_mutating_the_first(self) -> None:
        first = empty_snapshot(
            "snapshot-1",
            datetime(2026, 7, 21, 10, tzinfo=timezone.utc),
        )
        second = empty_snapshot(
            "snapshot-2",
            datetime(2026, 7, 21, 11, tzinfo=timezone.utc),
        )

        self.repository.save_snapshot(first)
        self.repository.save_snapshot(second)

        self.assertEqual(self._snapshot_count(), 2)
        self.assertEqual(self.repository.get_snapshot(first.snapshot_id), first)
        self.assertEqual(self.repository.get_snapshot(second.snapshot_id), second)

    def test_recent_latest_and_previous_use_utc_then_id_descending(self) -> None:
        earlier_instant = empty_snapshot(
            "snapshot-wall-later",
            datetime(
                2026,
                7,
                21,
                15,
                tzinfo=timezone(timedelta(hours=5)),
            ),
        )
        tie_a = empty_snapshot(
            "snapshot-a",
            datetime(2026, 7, 21, 11, tzinfo=timezone.utc),
        )
        tie_z = empty_snapshot(
            "snapshot-z",
            datetime(
                2026,
                7,
                21,
                12,
                tzinfo=timezone(timedelta(hours=1)),
            ),
        )
        latest = empty_snapshot(
            "snapshot-latest",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        for snapshot in (tie_a, latest, earlier_instant, tie_z):
            self.repository.save_snapshot(snapshot)

        self.assertEqual(self.repository.latest_snapshot(), latest)
        self.assertEqual(
            tuple(
                snapshot.snapshot_id
                for snapshot in self.repository.recent_snapshots(3)
            ),
            ("snapshot-latest", "snapshot-z", "snapshot-a"),
        )
        self.assertEqual(
            tuple(snapshot.snapshot_id for snapshot in self.repository.all_snapshots()),
            ("snapshot-wall-later", "snapshot-a", "snapshot-z", "snapshot-latest"),
        )
        self.assertEqual(self.repository.previous_snapshot(latest.snapshot_id), tie_z)
        self.assertEqual(self.repository.previous_snapshot(tie_z.snapshot_id), tie_a)
        self.assertEqual(
            self.repository.previous_snapshot(tie_a.snapshot_id),
            earlier_instant,
        )
        self.assertIsNone(
            self.repository.previous_snapshot(earlier_instant.snapshot_id)
        )
        self.assertIsNone(self.repository.previous_snapshot("unknown-snapshot"))

    def test_caller_owned_transaction_retains_final_commit_control(self) -> None:
        snapshot = empty_snapshot(
            "pending-snapshot",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        self.database.conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?)",
            ("caller", "pending"),
        )

        self.repository.save_snapshot(snapshot)

        self.assertTrue(self.database.conn.in_transaction)
        self.database.conn.rollback()
        self.assertIsNone(self.repository.get_snapshot(snapshot.snapshot_id))
        self.assertEqual(
            self.database.conn.execute(
                "SELECT COUNT(*) FROM app_settings WHERE key = ?",
                ("caller",),
            ).fetchone()[0],
            0,
        )

    def test_conflict_savepoint_preserves_unrelated_caller_work(self) -> None:
        snapshot = empty_snapshot(
            "existing-snapshot",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        self.repository.save_snapshot(snapshot)
        self.database.conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?)",
            ("caller", "preserved"),
        )

        with self.assertRaises(MarketplaceSnapshotConflictError):
            self.repository.save_snapshot(replace(snapshot, source_version="changed"))

        self.assertTrue(self.database.conn.in_transaction)
        self.assertEqual(
            self.database.conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                ("caller",),
            ).fetchone()[0],
            "preserved",
        )
        self.assertEqual(self.repository.get_snapshot(snapshot.snapshot_id), snapshot)
        self.database.conn.commit()

    def test_sqlite_write_failure_is_typed_and_rolls_back(self) -> None:
        self.database.conn.execute(
            """
            CREATE TRIGGER reject_marketplace_snapshot
            BEFORE INSERT ON marketplace_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'controlled Marketplace History failure');
            END
            """
        )
        self.database.conn.commit()
        snapshot = empty_snapshot(
            "rejected-snapshot",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )

        with self.assertRaises(MarketplaceHistoryPersistenceError) as raised:
            self.repository.save_snapshot(snapshot)

        self.assertIsInstance(raised.exception.__cause__, sqlite3.DatabaseError)
        self.assertEqual(self._snapshot_count(), 0)
        self.assertFalse(self.database.conn.in_transaction)

    def test_serialization_failure_occurs_before_transaction_entry(self) -> None:
        snapshot = empty_snapshot(
            "serialization-failure",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        failure = MarketplaceSerializationError("controlled failure")

        with patch(
            "dip.persistence.sqlite.marketplace_history.dumps_marketplace_snapshot",
            side_effect=failure,
        ):
            with self.assertRaises(MarketplaceSerializationError) as raised:
                self.repository.save_snapshot(snapshot)

        self.assertIs(raised.exception, failure)
        self.assertFalse(self.database.conn.in_transaction)
        self.assertEqual(self._snapshot_count(), 0)

    def test_repository_rejects_invalid_ids_and_limits_before_sql(self) -> None:
        for value, error in (
            (None, TypeError),
            (True, TypeError),
            (1, TypeError),
            ("", ValueError),
            (" snapshot-1", ValueError),
            ("snapshot-1 ", ValueError),
        ):
            for query in (
                self.repository.get_snapshot,
                self.repository.previous_snapshot,
            ):
                with self.subTest(query=query.__name__, value=value):
                    with self.assertRaises(error):
                        query(value)  # type: ignore[arg-type]

        for value, error in (
            (True, TypeError),
            ("1", TypeError),
            (1.0, TypeError),
            (0, ValueError),
            (-1, ValueError),
            (101, ValueError),
        ):
            with self.subTest(limit=value):
                with self.assertRaises(error):
                    self.repository.recent_snapshots(value)  # type: ignore[arg-type]

    def test_closed_connection_read_failure_is_typed(self) -> None:
        self.database.close()

        with self.assertRaises(MarketplaceHistoryPersistenceError) as raised:
            self.repository.latest_snapshot()

        self.assertIsInstance(raised.exception.__cause__, sqlite3.DatabaseError)

    def test_repository_uses_database_lock_without_an_independent_lock(self) -> None:
        attempted = threading.Event()
        finished = threading.Event()

        def retrieve() -> None:
            attempted.set()
            self.repository.latest_snapshot()
            finished.set()

        with self.database.locked_connection():
            thread = threading.Thread(target=retrieve)
            thread.start()
            self.assertTrue(attempted.wait(1))
            self.assertFalse(finished.wait(0.05))

        thread.join(timeout=1)
        self.assertTrue(finished.is_set())
        self.assertFalse(hasattr(self.repository, "_lock"))

    def test_corrupt_or_inconsistent_storage_fails_loudly(self) -> None:
        captured_at = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
        cases = (
            ("invalid-json", "payload_json", lambda payload: "{not-json"),
            (
                "unsupported-schema",
                "payload_json",
                lambda payload: changed_payload(payload, schema_version=2),
            ),
            (
                "payload-id-mismatch",
                "payload_json",
                lambda payload: changed_payload(payload, snapshot_id="different-id"),
            ),
            (
                "indexed-time-mismatch",
                "captured_at",
                lambda payload: "2026-07-21T11:00:00.000000+00:00",
            ),
            (
                "indexed-source-mismatch",
                "source",
                lambda payload: "other_source",
            ),
            (
                "indexed-status-mismatch",
                "status",
                lambda payload: MarketplaceDataStatus.EMPTY.value,
            ),
            (
                "indexed-schema-mismatch",
                "schema_version",
                lambda payload: MARKETPLACE_SCHEMA_VERSION + 1,
            ),
            (
                "noncanonical-json",
                "payload_json",
                lambda payload: json.dumps(
                    json.loads(payload),
                    indent=2,
                    sort_keys=True,
                ),
            ),
        )

        for index, (name, column, corrupt) in enumerate(cases):
            with self.subTest(case=name):
                snapshot = complete_snapshot(
                    f"corrupt-{index}",
                    captured_at + timedelta(minutes=index),
                )
                self.repository.save_snapshot(snapshot)
                payload = self._stored_payload(snapshot.snapshot_id)
                self.database.conn.execute(
                    f"UPDATE marketplace_snapshots SET {column} = ? "
                    "WHERE snapshot_id = ?",
                    (corrupt(payload), snapshot.snapshot_id),
                )
                self.database.conn.commit()

                with self.assertRaises(MarketplaceHistoryIntegrityError):
                    self.repository.get_snapshot(snapshot.snapshot_id)

    def _snapshot_count(self) -> int:
        return int(
            self.database.conn.execute(
                "SELECT COUNT(*) FROM marketplace_snapshots"
            ).fetchone()[0]
        )

    def _stored_payload(self, snapshot_id: str) -> str:
        return str(
            self.database.conn.execute(
                "SELECT payload_json FROM marketplace_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()[0]
        )


def complete_snapshot(
    snapshot_id: str,
    captured_at: datetime,
    *,
    amount: str = "10.00",
) -> MarketplaceSnapshot:
    observed_at = captured_at - timedelta(minutes=30)
    diagnostic = MarketplaceDiagnostic(
        "source_note",
        "The provider supplied an informational note.",
        MarketplaceDiagnosticSeverity.INFO,
        {"provider": "discogs", "attempt": "1"},
    )
    lowest = MarketplaceMoney(Decimal(amount), "GBP")
    release = MarketplaceReleaseObservation(
        release_id=101,
        observed_at=observed_at,
        status=MarketplaceDataStatus.COMPLETE,
        lowest_price=lowest,
        median_price=MarketplaceMoney(Decimal("15.5000"), "GBP"),
        highest_price=MarketplaceMoney(Decimal("30.0000"), "GBP"),
        num_for_sale=3,
        num_wanted=41,
        last_sold=date(2026, 7, 20),
        diagnostics=(diagnostic,),
    )
    listing = MarketplaceListingObservation(
        listing_id="listing-101",
        release_id=101,
        observed_at=observed_at,
        price=lowest,
        shipping=MarketplaceMoney(Decimal("2.7500"), "GBP"),
        condition="Near Mint",
        seller_region="GB",
    )
    return MarketplaceSnapshot(
        snapshot_id=snapshot_id,
        captured_at=captured_at,
        source="discogs",
        status=MarketplaceDataStatus.COMPLETE,
        release_observations=(release,),
        listing_observations=(listing,),
        diagnostics=(diagnostic,),
        source_version="api-v2",
    )


def empty_snapshot(snapshot_id: str, captured_at: datetime) -> MarketplaceSnapshot:
    return MarketplaceSnapshot(
        snapshot_id=snapshot_id,
        captured_at=captured_at,
        source="discogs",
        status=MarketplaceDataStatus.EMPTY,
    )


def status_snapshot(
    status: MarketplaceDataStatus,
    captured_at: datetime,
) -> MarketplaceSnapshot:
    snapshot_id = f"snapshot-{status.value}"
    diagnostic = MarketplaceDiagnostic(
        "capture_diagnostic",
        "The capture status is preserved.",
    )
    if status is MarketplaceDataStatus.COMPLETE:
        return complete_snapshot(snapshot_id, captured_at)
    if status is MarketplaceDataStatus.PARTIAL:
        release = MarketplaceReleaseObservation(
            release_id=101,
            observed_at=captured_at,
            status=status,
            num_for_sale=2,
            diagnostics=(diagnostic,),
        )
        return MarketplaceSnapshot(
            snapshot_id,
            captured_at,
            "discogs",
            status,
            release_observations=(release,),
            diagnostics=(diagnostic,),
        )
    return MarketplaceSnapshot(
        snapshot_id,
        captured_at,
        "discogs",
        status,
        diagnostics=(diagnostic,)
        if status in {MarketplaceDataStatus.UNAVAILABLE, MarketplaceDataStatus.FAILED}
        else (),
    )


def changed_payload(payload: str, **changes: object) -> str:
    value = json.loads(payload)
    value.update(changes)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


if __name__ == "__main__":
    unittest.main()
