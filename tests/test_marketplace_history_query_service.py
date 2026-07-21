from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from dip.app import (
    MarketplaceHistoryCommandService,
    MarketplaceHistoryConsistencyError,
    MarketplaceHistoryQueryService,
)
from dip.marketplace_history import (
    DEFAULT_RECENT_SNAPSHOT_LIMIT,
    MAX_RECENT_SNAPSHOT_LIMIT,
    MarketplaceSnapshotConflictError,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)


CAPTURED_AT = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)


class _MarketplaceHistoryRepository:
    def __init__(
        self,
        snapshots: tuple[MarketplaceSnapshot, ...] = (),
    ) -> None:
        self.snapshots = snapshots
        self.save_calls: list[MarketplaceSnapshot] = []
        self.query_calls: list[tuple[str, object | None]] = []
        self.save_error: Exception | None = None

    def save_snapshot(self, snapshot: MarketplaceSnapshot) -> None:
        self.save_calls.append(snapshot)
        if self.save_error is not None:
            raise self.save_error

        existing = next(
            (
                value
                for value in self.snapshots
                if value.snapshot_id == snapshot.snapshot_id
            ),
            None,
        )
        if existing is None:
            self.snapshots = (snapshot, *self.snapshots)
        elif existing != snapshot:
            raise MarketplaceSnapshotConflictError(
                f"Snapshot ID {snapshot.snapshot_id!r} is already in use."
            )

    def get_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None:
        self.query_calls.append(("get_snapshot", snapshot_id))
        return next(
            (
                value
                for value in self.snapshots
                if value.snapshot_id == snapshot_id
            ),
            None,
        )

    def latest_snapshot(self) -> MarketplaceSnapshot | None:
        self.query_calls.append(("latest_snapshot", None))
        return self.snapshots[0] if self.snapshots else None

    def recent_snapshots(
        self,
        limit: int,
    ) -> tuple[MarketplaceSnapshot, ...]:
        self.query_calls.append(("recent_snapshots", limit))
        return self.snapshots[:limit]

    def previous_snapshot(
        self,
        snapshot_id: str,
    ) -> MarketplaceSnapshot | None:
        self.query_calls.append(("previous_snapshot", snapshot_id))
        for index, snapshot in enumerate(self.snapshots):
            if snapshot.snapshot_id == snapshot_id:
                next_index = index + 1
                return (
                    self.snapshots[next_index]
                    if next_index < len(self.snapshots)
                    else None
                )
        return None


class _FailingMarketplaceHistoryRepository(_MarketplaceHistoryRepository):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def latest_snapshot(self) -> MarketplaceSnapshot | None:
        raise self.error


class MarketplaceHistoryQueryServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshots = (
            snapshot(
                "complete-1",
                MarketplaceDataStatus.COMPLETE,
                CAPTURED_AT,
            ),
            snapshot(
                "partial-1",
                MarketplaceDataStatus.PARTIAL,
                CAPTURED_AT - timedelta(days=1),
            ),
            snapshot(
                "empty-1",
                MarketplaceDataStatus.EMPTY,
                CAPTURED_AT - timedelta(days=2),
            ),
            snapshot(
                "unavailable-1",
                MarketplaceDataStatus.UNAVAILABLE,
                CAPTURED_AT - timedelta(days=3),
            ),
            snapshot(
                "failed-1",
                MarketplaceDataStatus.FAILED,
                CAPTURED_AT - timedelta(days=4),
            ),
        )
        self.repository = _MarketplaceHistoryRepository(self.snapshots)
        self.service = MarketplaceHistoryQueryService(self.repository)

    def test_empty_history_uses_documented_absence_values(self) -> None:
        service = MarketplaceHistoryQueryService(_MarketplaceHistoryRepository())

        self.assertIsNone(service.get_snapshot("missing-1"))
        self.assertIsNone(service.latest_snapshot())
        self.assertEqual(service.recent_snapshots(), ())
        self.assertIsNone(service.previous_snapshot("missing-1"))

    def test_get_latest_and_previous_return_repository_snapshots(self) -> None:
        self.assertIs(self.service.get_snapshot("partial-1"), self.snapshots[1])
        self.assertIsNone(self.service.get_snapshot("missing-1"))
        self.assertIs(self.service.latest_snapshot(), self.snapshots[0])
        self.assertIs(
            self.service.previous_snapshot("partial-1"),
            self.snapshots[2],
        )
        self.assertIsNone(self.service.previous_snapshot("failed-1"))

    def test_recent_defaults_to_twenty_and_preserves_order_and_statuses(self) -> None:
        result = self.service.recent_snapshots()

        self.assertIsInstance(result, tuple)
        self.assertEqual(result, self.snapshots)
        self.assertEqual(
            tuple(value.status for value in result),
            tuple(value.status for value in self.snapshots),
        )
        self.assertEqual(
            self.repository.query_calls,
            [("recent_snapshots", DEFAULT_RECENT_SNAPSHOT_LIMIT)],
        )

    def test_recent_respects_explicit_and_maximum_limits(self) -> None:
        self.assertEqual(self.service.recent_snapshots(2), self.snapshots[:2])
        self.assertEqual(
            self.service.recent_snapshots(MAX_RECENT_SNAPSHOT_LIMIT),
            self.snapshots,
        )
        self.assertEqual(
            self.repository.query_calls,
            [
                ("recent_snapshots", 2),
                ("recent_snapshots", MAX_RECENT_SNAPSHOT_LIMIT),
            ],
        )

    def test_snapshot_queries_reject_invalid_identifiers_before_repository_access(
        self,
    ) -> None:
        for query in (self.service.get_snapshot, self.service.previous_snapshot):
            for value, error in (
                (None, TypeError),
                (True, TypeError),
                (1, TypeError),
                ("", ValueError),
                ("   ", ValueError),
                (" snapshot-1", ValueError),
                ("snapshot-1 ", ValueError),
            ):
                with self.subTest(query=query.__name__, value=value):
                    with self.assertRaises(error):
                        query(value)  # type: ignore[arg-type]

        self.assertEqual(self.repository.query_calls, [])

    def test_recent_rejects_invalid_limits_before_repository_access(self) -> None:
        for value, error in (
            (True, TypeError),
            ("1", TypeError),
            (1.0, TypeError),
            (None, TypeError),
            (0, ValueError),
            (-1, ValueError),
            (MAX_RECENT_SNAPSHOT_LIMIT + 1, ValueError),
        ):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    self.service.recent_snapshots(value)  # type: ignore[arg-type]

        self.assertEqual(self.repository.query_calls, [])

    def test_query_operations_never_write_history(self) -> None:
        self.service.get_snapshot("complete-1")
        self.service.latest_snapshot()
        self.service.recent_snapshots(3)
        self.service.previous_snapshot("complete-1")

        self.assertEqual(self.repository.save_calls, [])

    def test_repository_failures_propagate_without_being_swallowed(self) -> None:
        failure = RuntimeError("history unavailable")
        service = MarketplaceHistoryQueryService(
            _FailingMarketplaceHistoryRepository(failure)
        )

        with self.assertRaises(RuntimeError) as raised:
            service.latest_snapshot()

        self.assertIs(raised.exception, failure)

    def test_wrong_snapshot_for_requested_id_is_inconsistent(self) -> None:
        repository = _MarketplaceHistoryRepository(self.snapshots)
        repository.get_snapshot = lambda snapshot_id: self.snapshots[0]
        service = MarketplaceHistoryQueryService(repository)

        with self.assertRaisesRegex(
            MarketplaceHistoryConsistencyError,
            "for requested snapshot",
        ):
            service.get_snapshot("other-1")

    def test_repository_values_must_be_snapshots(self) -> None:
        repository = _MarketplaceHistoryRepository()
        repository.latest_snapshot = lambda: object()  # type: ignore[method-assign]
        service = MarketplaceHistoryQueryService(repository)

        with self.assertRaisesRegex(
            MarketplaceHistoryConsistencyError,
            "not a MarketplaceSnapshot",
        ):
            service.latest_snapshot()

    def test_recent_rejects_excess_duplicates_and_invalid_values(self) -> None:
        cases = (
            (self.snapshots[:2], "more Marketplace snapshots"),
            ((self.snapshots[0], self.snapshots[0]), "duplicate"),
            ((object(),), "not a MarketplaceSnapshot"),
        )
        for response, message in cases:
            repository = _MarketplaceHistoryRepository()
            repository.recent_snapshots = lambda limit, value=response: value
            service = MarketplaceHistoryQueryService(repository)
            limit = 1 if response == self.snapshots[:2] else 2

            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    MarketplaceHistoryConsistencyError,
                    message,
                ):
                    service.recent_snapshots(limit)

    def test_unexpected_noniterable_repository_result_propagates(self) -> None:
        repository = _MarketplaceHistoryRepository()
        repository.recent_snapshots = lambda limit: None
        service = MarketplaceHistoryQueryService(repository)

        with self.assertRaises(TypeError):
            service.recent_snapshots(2)

    def test_snapshot_cannot_be_its_own_predecessor(self) -> None:
        repository = _MarketplaceHistoryRepository(self.snapshots)
        repository.previous_snapshot = lambda snapshot_id: self.snapshots[0]
        service = MarketplaceHistoryQueryService(repository)

        with self.assertRaisesRegex(
            MarketplaceHistoryConsistencyError,
            "own predecessor",
        ):
            service.previous_snapshot("complete-1")


class MarketplaceHistoryCommandServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = _MarketplaceHistoryRepository()
        self.service = MarketplaceHistoryCommandService(self.repository)
        self.snapshot = snapshot(
            "snapshot-1",
            MarketplaceDataStatus.COMPLETE,
            CAPTURED_AT,
        )

    def test_records_and_returns_the_exact_supplied_snapshot(self) -> None:
        recorded = self.service.record_snapshot(self.snapshot)

        self.assertIs(recorded, self.snapshot)
        self.assertIs(self.repository.save_calls[0], self.snapshot)
        self.assertEqual(self.repository.query_calls, [])
        self.assertEqual(recorded.snapshot_id, "snapshot-1")
        self.assertEqual(recorded.captured_at, CAPTURED_AT)

    def test_identical_repeat_is_idempotent(self) -> None:
        first = self.service.record_snapshot(self.snapshot)
        second = self.service.record_snapshot(self.snapshot)

        self.assertIs(first, self.snapshot)
        self.assertIs(second, self.snapshot)
        self.assertEqual(self.repository.snapshots, (self.snapshot,))
        self.assertEqual(self.repository.save_calls, [self.snapshot, self.snapshot])

    def test_conflicting_identity_is_propagated_without_overwrite(self) -> None:
        self.service.record_snapshot(self.snapshot)
        conflicting = replace(self.snapshot, source_version="api-v2")

        with self.assertRaises(MarketplaceSnapshotConflictError):
            self.service.record_snapshot(conflicting)

        self.assertEqual(self.repository.snapshots, (self.snapshot,))

    def test_repository_conflict_instance_is_not_wrapped(self) -> None:
        conflict = MarketplaceSnapshotConflictError("conflicting snapshot")
        self.repository.save_error = conflict

        with self.assertRaises(MarketplaceSnapshotConflictError) as raised:
            self.service.record_snapshot(self.snapshot)

        self.assertIs(raised.exception, conflict)

    def test_rejects_non_snapshot_before_repository_access(self) -> None:
        for value in (None, True, {}, object()):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.service.record_snapshot(value)  # type: ignore[arg-type]

        self.assertEqual(self.repository.save_calls, [])


def diagnostic() -> MarketplaceDiagnostic:
    return MarketplaceDiagnostic(
        "source_unavailable",
        "The Marketplace source could not provide a complete response.",
    )


def snapshot(
    snapshot_id: str,
    status: MarketplaceDataStatus,
    captured_at: datetime,
) -> MarketplaceSnapshot:
    if status is MarketplaceDataStatus.COMPLETE:
        return MarketplaceSnapshot(
            snapshot_id,
            captured_at,
            "discogs",
            status,
            (
                MarketplaceReleaseObservation(
                    1,
                    captured_at,
                    status,
                    num_for_sale=0,
                ),
            ),
        )
    if status is MarketplaceDataStatus.PARTIAL:
        source_diagnostic = diagnostic()
        return MarketplaceSnapshot(
            snapshot_id,
            captured_at,
            "discogs",
            status,
            (
                MarketplaceReleaseObservation(
                    1,
                    captured_at,
                    status,
                    num_for_sale=1,
                    diagnostics=(source_diagnostic,),
                ),
            ),
            diagnostics=(source_diagnostic,),
        )
    if status in {
        MarketplaceDataStatus.UNAVAILABLE,
        MarketplaceDataStatus.FAILED,
    }:
        return MarketplaceSnapshot(
            snapshot_id,
            captured_at,
            "discogs",
            status,
            diagnostics=(diagnostic(),),
        )
    return MarketplaceSnapshot(
        snapshot_id,
        captured_at,
        "discogs",
        status,
    )


if __name__ == "__main__":
    unittest.main()
