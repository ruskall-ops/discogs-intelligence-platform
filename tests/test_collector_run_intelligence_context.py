from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType
import tempfile
import unittest
from pathlib import Path
from threading import RLock
from unittest.mock import patch

from dip.app.intelligence_context import IntelligenceContextFactory
from dip.intelligence import IntelligenceStatus
from dip.intelligence.modules.historical_intelligence import (
    HistoricalIntelligenceModule,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)
from dip.persistence.sqlite import Database
import dip.persistence.sqlite.repository as sqlite_repository


CAPTURED = datetime(2026, 7, 25, 12, tzinfo=timezone.utc)
DIAGNOSTIC = MarketplaceDiagnostic(
    "evidence_absent",
    "Some canonical evidence was unavailable.",
    details={"field": "num_wanted"},
)


def _observation(
    release_id: int,
    status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
    *,
    wanted: int | None = 0,
    supply: int | None = 0,
    price: Decimal | None = Decimal("12.340"),
    observed_at: datetime = CAPTURED,
) -> MarketplaceReleaseObservation:
    unavailable = status in {
        MarketplaceDataStatus.EMPTY,
        MarketplaceDataStatus.FAILED,
        MarketplaceDataStatus.UNAVAILABLE,
    }
    diagnostics = (
        (DIAGNOSTIC,)
        if status
        in {
            MarketplaceDataStatus.PARTIAL,
            MarketplaceDataStatus.FAILED,
            MarketplaceDataStatus.UNAVAILABLE,
        }
        else ()
    )
    return MarketplaceReleaseObservation(
        release_id,
        observed_at,
        status,
        lowest_price=(
            None
            if unavailable or price is None
            else MarketplaceMoney(price, "GBP")
        ),
        median_price=(
            MarketplaceMoney(Decimal("15.00"), "GBP")
            if status is MarketplaceDataStatus.PARTIAL
            and price is None
            and wanted is None
            and supply is None
            else None
        ),
        num_for_sale=None if unavailable else supply,
        num_wanted=None if unavailable else wanted,
        diagnostics=diagnostics,
    )


def _snapshot(
    snapshot_id: str,
    observations: tuple[MarketplaceReleaseObservation, ...],
    *,
    captured_at: datetime = CAPTURED,
    source: str = "discogs",
    status: MarketplaceDataStatus | None = None,
) -> MarketplaceSnapshot:
    status = status or (
        MarketplaceDataStatus.COMPLETE
        if all(
            item.status
            not in {
                MarketplaceDataStatus.PARTIAL,
                MarketplaceDataStatus.FAILED,
                MarketplaceDataStatus.UNAVAILABLE,
            }
            for item in observations
        )
        else MarketplaceDataStatus.PARTIAL
    )
    return MarketplaceSnapshot(
        snapshot_id,
        captured_at,
        source,
        status,
        observations,
        diagnostics=(DIAGNOSTIC,) if status is MarketplaceDataStatus.PARTIAL else (),
    )


class _Evidence:
    def __init__(self, rows):
        self.rows = rows
        self.requested = []

    def collection_evidence_rows(self, release_ids):
        self.requested.append(release_ids)
        return self.rows

    def review_rows(self, *, limit):
        raise AssertionError("legacy review evidence must not be queried")

    def latest_completed_analysis_run(self):
        raise AssertionError("legacy latest-run history must not be queried")

    def previous_completed_analysis_run(self, before_run_id):
        raise AssertionError("legacy predecessor history must not be queried")

    def snapshots_for_analysis_run(self, run_id):
        raise AssertionError("legacy snapshots must not be queried")


class _History:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def previous_snapshot(self, snapshot_id):
        self.calls.append(snapshot_id)
        return self.values.get(snapshot_id)


class CollectorRunIntelligenceContextTestCase(unittest.TestCase):
    def test_canonical_mapping_preserves_absence_zero_decimal_and_immutability(self):
        nested = {"tags": ["owned"], "flags": {"original"}}
        evidence = _Evidence(
            (
                {"release_id": 1, "artist": "One", "quantity": 1, "nested": nested},
                {"release_id": 2, "artist": "Two", "quantity": 2},
                {"release_id": 3, "artist": "Three", "quantity": 1},
            )
        )
        current = _snapshot(
            "collector-run-7",
            (
                _observation(1),
                _observation(
                    2,
                    MarketplaceDataStatus.PARTIAL,
                    wanted=None,
                    supply=None,
                    price=None,
                ),
                _observation(3, MarketplaceDataStatus.UNAVAILABLE),
            ),
            status=MarketplaceDataStatus.PARTIAL,
        )

        context = IntelligenceContextFactory(
            evidence, _History({})
        ).build_collector_run(
            analysis_run_id=7,
            marketplace_snapshot=current,
            release_ids=(1, 2, 3),
            captured_at=CAPTURED,
        )

        self.assertEqual(evidence.requested, [(1, 2, 3)])
        self.assertEqual(tuple(context.marketplace), (1, 2))
        self.assertEqual(context.marketplace[1]["wants"], 0)
        self.assertEqual(context.marketplace[1]["copies_for_sale"], 0)
        self.assertEqual(context.marketplace[1]["lowest_price"], Decimal("12.340"))
        self.assertIsNone(context.marketplace[2]["wants"])
        self.assertIsNone(context.marketplace[2]["copies_for_sale"])
        self.assertIsNone(context.marketplace[2]["lowest_price"])
        self.assertNotIn("community_rating", context.marketplace[1])
        self.assertEqual(
            tuple(row["release_id"] for row in context.history["collector-run-7"]),
            (1, 2, 3),
        )
        self.assertIsInstance(context.collection[0], MappingProxyType)
        self.assertEqual(context.collection[0]["nested"]["tags"], ("owned",))
        self.assertEqual(context.collection[0]["nested"]["flags"], frozenset({"original"}))
        nested["tags"].append("mutated")
        nested["flags"].add("mutated")
        self.assertEqual(context.collection[0]["nested"]["tags"], ("owned",))
        with self.assertRaises(TypeError):
            context.marketplace[1]["wants"] = 9
        with self.assertRaises(TypeError):
            current.release_observations[2].diagnostics[0].details["raw"] = "unsafe"

    def test_nearest_eligible_predecessor_is_selected_and_retains_unavailable_ids(self):
        earlier = CAPTURED - timedelta(days=2)
        predecessor = _snapshot(
            "collector-run-2",
            (
                _observation(1, observed_at=earlier),
                _observation(
                    4,
                    MarketplaceDataStatus.UNAVAILABLE,
                    observed_at=earlier,
                ),
            ),
            captured_at=earlier,
        )
        failed = MarketplaceSnapshot(
            "collector-run-3",
            CAPTURED - timedelta(days=1),
            "discogs",
            MarketplaceDataStatus.FAILED,
            diagnostics=(DIAGNOSTIC,),
        )
        other_source = _snapshot(
            "other-source",
            (_observation(1, observed_at=CAPTURED - timedelta(hours=1)),),
            captured_at=CAPTURED - timedelta(hours=1),
            source="other",
        )
        current = _snapshot(
            "collector-run-4",
            (_observation(1), _observation(4, MarketplaceDataStatus.UNAVAILABLE)),
            status=MarketplaceDataStatus.PARTIAL,
        )
        history = _History(
            {
                "collector-run-4": other_source,
                "other-source": failed,
                "collector-run-3": predecessor,
            }
        )
        context = IntelligenceContextFactory(
            _Evidence(({"release_id": 1}, {"release_id": 4})),
            history,
        ).build_collector_run(
            analysis_run_id=4,
            marketplace_snapshot=current,
            release_ids=(1, 4),
            captured_at=CAPTURED,
        )

        self.assertEqual(
            tuple(context.history),
            ("collector-run-2", "collector-run-4"),
        )
        self.assertEqual(
            tuple(row["release_id"] for row in context.history["collector-run-2"]),
            (1, 4),
        )
        result = HistoricalIntelligenceModule().analyse(context)
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(result.metrics["removals_count"], 0)
        self.assertEqual(result.metrics["additions_count"], 0)

    def test_first_run_is_legitimately_skipped_and_cycles_are_fatal(self):
        current = _snapshot("collector-run-1", (_observation(1),))
        factory = IntelligenceContextFactory(
            _Evidence(({"release_id": 1},)), _History({})
        )
        context = factory.build_collector_run(
            analysis_run_id=1,
            marketplace_snapshot=current,
            release_ids=(1,),
            captured_at=CAPTURED,
        )
        self.assertIs(
            HistoricalIntelligenceModule().analyse(context).status,
            IntelligenceStatus.SKIPPED,
        )

        with self.assertRaisesRegex(RuntimeError, "cycled"):
            IntelligenceContextFactory(
                _Evidence(({"release_id": 1},)),
                _History({"collector-run-1": current}),
            ).build_collector_run(
                analysis_run_id=1,
                marketplace_snapshot=current,
                release_ids=(1,),
                captured_at=CAPTURED,
            )

    def test_invalid_scope_timestamp_and_returned_identities_are_rejected(self):
        current = _snapshot("collector-run-7", (_observation(1), _observation(2)))
        cases = (
            (({"release_id": 1},), ValueError),
            (({"release_id": 1}, {"release_id": 1}), ValueError),
            (({"release_id": 1}, {"release_id": 2}, {"release_id": 3}), ValueError),
            (({"release_id": "1"}, {"release_id": 2}), ValueError),
        )
        for rows, error in cases:
            with self.subTest(rows=rows), self.assertRaises(error):
                IntelligenceContextFactory(
                    _Evidence(rows), _History({})
                ).build_collector_run(
                    analysis_run_id=7,
                    marketplace_snapshot=current,
                    release_ids=(1, 2),
                    captured_at=CAPTURED,
                )
        with self.assertRaisesRegex(ValueError, "exactly match"):
            IntelligenceContextFactory(
                _Evidence(({"release_id": 1}, {"release_id": 2})), _History({})
            ).build_collector_run(
                analysis_run_id=7,
                marketplace_snapshot=current,
                release_ids=(1, 2),
                captured_at=CAPTURED + timedelta(seconds=1),
            )

    def test_explicit_collector_run_inputs_are_validated_safely(self):
        current = _snapshot("collector-run-7", (_observation(1),))
        evidence = _Evidence(({"release_id": 1},))
        cases = (
            (
                {
                    "analysis_run_id": True,
                    "marketplace_snapshot": current,
                    "release_ids": (1,),
                    "captured_at": CAPTURED,
                },
                (TypeError, ValueError),
            ),
            (
                {
                    "analysis_run_id": 0,
                    "marketplace_snapshot": current,
                    "release_ids": (1,),
                    "captured_at": CAPTURED,
                },
                ValueError,
            ),
            (
                {
                    "analysis_run_id": -1,
                    "marketplace_snapshot": current,
                    "release_ids": (1,),
                    "captured_at": CAPTURED,
                },
                ValueError,
            ),
            (
                {
                    "analysis_run_id": 8,
                    "marketplace_snapshot": current,
                    "release_ids": (1,),
                    "captured_at": CAPTURED,
                },
                ValueError,
            ),
            (
                {
                    "analysis_run_id": 7,
                    "marketplace_snapshot": current,
                    "release_ids": (1,),
                    "captured_at": CAPTURED.replace(tzinfo=None),
                },
                ValueError,
            ),
            (
                {
                    "analysis_run_id": 7,
                    "marketplace_snapshot": current,
                    "release_ids": (2,),
                    "captured_at": CAPTURED,
                },
                ValueError,
            ),
        )
        factory = IntelligenceContextFactory(evidence, _History({}))
        for values, error in cases:
            with self.subTest(values=values), self.assertRaises(error) as raised:
                factory.build_collector_run(**values)
            exposed = str(raised.exception)
            self.assertNotIn("SELECT", exposed)
            self.assertNotIn("temporary-token", exposed)
            self.assertNotIn("payload", exposed.casefold())

        failed = MarketplaceSnapshot(
            "collector-run-7",
            CAPTURED,
            "discogs",
            MarketplaceDataStatus.FAILED,
            diagnostics=(DIAGNOSTIC,),
        )
        with self.assertRaisesRegex(ValueError, "complete or partial"):
            factory.build_collector_run(
                analysis_run_id=7,
                marketplace_snapshot=failed,
                release_ids=(1,),
                captured_at=CAPTURED,
            )

    def test_empty_eligible_candidate_is_skipped_and_traversal_continues(self):
        earlier = CAPTURED - timedelta(days=2)
        predecessor = _snapshot(
            "collector-run-2",
            (_observation(1, observed_at=earlier),),
            captured_at=earlier,
        )
        empty_candidate = _unsafe_empty_partial_snapshot(
            "collector-run-3",
            CAPTURED - timedelta(days=1),
        )
        current = _snapshot("collector-run-4", (_observation(1),))
        history = _History(
            {
                "collector-run-4": empty_candidate,
                "collector-run-3": predecessor,
            }
        )

        context = IntelligenceContextFactory(
            _Evidence(({"release_id": 1},)),
            history,
        ).build_collector_run(
            analysis_run_id=4,
            marketplace_snapshot=current,
            release_ids=(1,),
            captured_at=CAPTURED,
        )

        self.assertEqual(
            history.calls,
            ["collector-run-4", "collector-run-3"],
        )
        self.assertEqual(
            tuple(context.history),
            ("collector-run-2", "collector-run-4"),
        )
        self.assertNotIn("collector-run-3", context.history)

    def test_real_historical_module_distinguishes_scope_change_from_unavailability(self):
        earlier = CAPTURED - timedelta(days=1)
        predecessor = _snapshot(
            "collector-run-10",
            (
                _observation(1, observed_at=earlier),
                _observation(2, observed_at=earlier),
                _observation(
                    4,
                    MarketplaceDataStatus.UNAVAILABLE,
                    observed_at=earlier,
                ),
            ),
            captured_at=earlier,
            status=MarketplaceDataStatus.PARTIAL,
        )
        current = _snapshot(
            "collector-run-11",
            (
                _observation(1),
                _observation(3),
                _observation(4, MarketplaceDataStatus.UNAVAILABLE),
            ),
            status=MarketplaceDataStatus.PARTIAL,
        )
        evidence = _Evidence(
            (
                {"release_id": 1, "artist": "One"},
                {"release_id": 3, "artist": "Three"},
                {"release_id": 4, "artist": "Four"},
            )
        )
        context = IntelligenceContextFactory(
            evidence,
            _History({"collector-run-11": predecessor}),
        ).build_collector_run(
            analysis_run_id=11,
            marketplace_snapshot=current,
            release_ids=(1, 3, 4),
            captured_at=CAPTURED,
        )

        result = HistoricalIntelligenceModule().analyse(context)

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(result.metrics["additions_count"], 1)
        self.assertEqual(result.metrics["removals_count"], 1)
        comparison = result.metrics["comparison"]
        self.assertEqual(
            tuple(item.release_id for item in comparison.additions),
            (3,),
        )
        self.assertEqual(
            tuple(item.release_id for item in comparison.removals),
            (2,),
        )
        self.assertNotIn(4, tuple(item.release_id for item in comparison.removals))
        self.assertEqual(evidence.requested, [(1, 3, 4)])


class CollectionEvidenceSQLiteTestCase(unittest.TestCase):
    def test_query_is_fixed_score_free_detached_and_ordered(self):
        temporary = tempfile.TemporaryDirectory()
        database = Database(Path(temporary.name) / "context.db")
        try:
            database.import_releases(
                (
                    {"Release ID": "2", "Artist": "Two", "Title": "Second"},
                    {"Release ID": "1", "Artist": "One", "Title": "First"},
                    {"Release ID": "3", "Artist": "Unrelated", "Title": "Third"},
                ),
                "Release ID",
            )
            rows = database.collection_evidence_rows((1, 2))
            self.assertEqual(tuple(row["release_id"] for row in rows), (1, 2))
            self.assertEqual(
                tuple(rows[0]),
                ("release_id", "artist", "title", "label", "quantity"),
            )
            self.assertNotIn("score", rows[0])
            self.assertNotIn("decision", rows[0])
            rows[0]["artist"] = "Detached"
            self.assertEqual(
                database.collection_evidence_rows((1,))[0]["artist"],
                "One",
            )
            for invalid in ((True,), (0,), (1, 1)):
                with self.subTest(invalid=invalid), self.assertRaises(
                    (TypeError, ValueError)
                ):
                    database.collection_evidence_rows(invalid)
        finally:
            database.close()
            temporary.cleanup()

    def test_production_query_batches_and_globally_orders_results(self):
        connection = _BatchConnection(reverse=True)
        database = _database_with_connection(connection)
        release_ids = tuple(range(1, 8))

        with patch.object(
            sqlite_repository,
            "_COLLECTION_EVIDENCE_BATCH_SIZE",
            3,
        ):
            rows = database.collection_evidence_rows(release_ids)

        self.assertEqual(
            tuple(row["release_id"] for row in rows),
            release_ids,
        )
        self.assertEqual(
            tuple(len(parameters) for _, parameters in connection.calls),
            (3, 3, 1),
        )
        self.assertEqual(
            tuple(
                value
                for _, parameters in connection.calls
                for value in parameters
            ),
            release_ids,
        )
        self.assertTrue(
            all(
                statement.count("?") == len(parameters) <= 3
                for statement, parameters in connection.calls
            )
        )

    def test_more_than_current_sqlite_ceiling_is_partitioned_safely(self):
        connection = _BatchConnection(return_rows=False)
        database = _database_with_connection(connection)
        release_ids = tuple(range(1, 32_768))

        rows = database.collection_evidence_rows(release_ids)

        self.assertEqual(rows, ())
        self.assertEqual(len(connection.calls), 37)
        self.assertLessEqual(
            max(len(parameters) for _, parameters in connection.calls),
            900,
        )
        self.assertTrue(
            all(
                statement.count("?") == len(parameters)
                for statement, parameters in connection.calls
            )
        )

    def test_duplicate_and_unexpected_query_results_are_rejected(self):
        for connection, message in (
            (_BatchConnection(duplicate=1), "duplicate"),
            (_BatchConnection(unexpected=99), "unexpected"),
        ):
            with self.subTest(message=message), self.assertRaisesRegex(
                ValueError,
                message,
            ):
                _database_with_connection(
                    connection
                ).collection_evidence_rows((1, 2))

    def test_missing_identity_in_later_batch_is_rejected_by_context(self):
        connection = _BatchConnection(missing={3})
        database = _database_with_connection(connection)
        current = _snapshot(
            "collector-run-8",
            (_observation(1), _observation(2), _observation(3)),
        )

        with (
            patch.object(
                sqlite_repository,
                "_COLLECTION_EVIDENCE_BATCH_SIZE",
                2,
            ),
            self.assertRaisesRegex(ValueError, "fixed run scope"),
        ):
            IntelligenceContextFactory(
                database,
                _History({}),
            ).build_collector_run(
                analysis_run_id=8,
                marketplace_snapshot=current,
                release_ids=(1, 2, 3),
                captured_at=CAPTURED,
            )
        self.assertEqual(
            tuple(len(parameters) for _, parameters in connection.calls),
            (2, 1),
        )


class _BatchConnection:
    def __init__(
        self,
        *,
        reverse: bool = False,
        return_rows: bool = True,
        missing: set[int] | None = None,
        duplicate: int | None = None,
        unexpected: int | None = None,
    ):
        self.reverse = reverse
        self.return_rows = return_rows
        self.missing = missing or set()
        self.duplicate = duplicate
        self.unexpected = unexpected
        self.calls = []

    def execute(self, statement, parameters):
        supplied = tuple(parameters)
        self.calls.append((statement, supplied))
        if not self.return_rows:
            return _Rows(())
        identities = [
            value for value in supplied if value not in self.missing
        ]
        if self.reverse:
            identities.reverse()
        rows = [
            {
                "release_id": value,
                "artist": f"Artist {value}",
                "title": f"Title {value}",
                "label": f"Label {value}",
                "quantity": 1,
            }
            for value in identities
        ]
        if self.duplicate is not None and self.duplicate in supplied:
            rows.append(dict(rows[identities.index(self.duplicate)]))
        if self.unexpected is not None:
            rows.append(
                {
                    "release_id": self.unexpected,
                    "artist": "Unexpected",
                    "title": "Unexpected",
                    "label": "Unexpected",
                    "quantity": 1,
                }
            )
        return _Rows(rows)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


def _database_with_connection(connection):
    database = Database.__new__(Database)
    database.conn = connection
    database._lock = RLock()
    return database


def _unsafe_empty_partial_snapshot(
    snapshot_id: str,
    captured_at: datetime,
) -> MarketplaceSnapshot:
    snapshot = object.__new__(MarketplaceSnapshot)
    object.__setattr__(snapshot, "snapshot_id", snapshot_id)
    object.__setattr__(snapshot, "captured_at", captured_at)
    object.__setattr__(snapshot, "source", "discogs")
    object.__setattr__(
        snapshot,
        "status",
        MarketplaceDataStatus.PARTIAL,
    )
    object.__setattr__(snapshot, "release_observations", ())
    object.__setattr__(snapshot, "listing_observations", ())
    object.__setattr__(snapshot, "diagnostics", (DIAGNOSTIC,))
    object.__setattr__(snapshot, "source_version", None)
    return snapshot


if __name__ == "__main__":
    unittest.main()
