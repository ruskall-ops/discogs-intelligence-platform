from __future__ import annotations

import unittest
from datetime import datetime, timezone

from dip.app.price_changes import (
    PriceChangesExecutionConsistencyError,
    PriceChangesExecutionService,
)
from dip.intelligence import (
    IntelligenceContext,
    IntelligenceExecution,
    IntelligenceResult,
    IntelligenceStatus,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
)


class _HistoryQueries:
    def __init__(
        self,
        snapshots: tuple[MarketplaceSnapshot, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.snapshots = snapshots
        self.error = error
        self.limits: list[int] = []

    def recent_snapshots(self, limit: int) -> tuple[MarketplaceSnapshot, ...]:
        self.limits.append(limit)
        if self.error is not None:
            raise self.error
        return self.snapshots


class _Engine:
    def __init__(
        self,
        execution: object,
        *,
        error: Exception | None = None,
    ) -> None:
        self.execution = execution
        self.error = error
        self.contexts: list[IntelligenceContext] = []

    def execute(self, context: IntelligenceContext) -> object:
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self.execution


class PriceChangesExecutionServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.result = price_changes_result()
        self.execution = IntelligenceExecution((self.result,))

    def test_no_snapshots_executes_once_with_an_empty_typed_comparison(self) -> None:
        queries = _HistoryQueries()
        engine = _Engine(self.execution)

        result = PriceChangesExecutionService(queries, engine).execute()

        self.assertIs(result, self.result)
        self.assertEqual(queries.limits, [2])
        self.assertEqual(len(engine.contexts), 1)
        context = engine.contexts[0]
        comparison = context.marketplace_comparison
        self.assertIsInstance(comparison, MarketplaceSnapshotComparisonInput)
        self.assertIsNone(comparison.previous_snapshot)
        self.assertIsNone(comparison.latest_snapshot)
        self.assertIsNone(context.marketplace_snapshot)

    def test_one_snapshot_becomes_latest_with_no_previous_snapshot(self) -> None:
        latest = snapshot(
            "snapshot-latest",
            datetime(2026, 7, 22, 12, tzinfo=timezone.utc),
        )
        queries = _HistoryQueries((latest,))
        engine = _Engine(self.execution)

        PriceChangesExecutionService(queries, engine).execute()

        self.assertEqual(queries.limits, [2])
        self.assertEqual(len(engine.contexts), 1)
        comparison = engine.contexts[0].marketplace_comparison
        self.assertIsNone(comparison.previous_snapshot)
        self.assertIs(comparison.latest_snapshot, latest)

    def test_two_newest_first_snapshots_map_to_previous_and_latest_roles(self) -> None:
        previous = snapshot(
            "snapshot-previous",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )
        latest = snapshot(
            "snapshot-latest",
            datetime(2026, 7, 22, 12, tzinfo=timezone.utc),
        )
        queries = _HistoryQueries((latest, previous))
        engine = _Engine(self.execution)

        PriceChangesExecutionService(queries, engine).execute()

        self.assertEqual(queries.limits, [2])
        self.assertEqual(len(engine.contexts), 1)
        comparison = engine.contexts[0].marketplace_comparison
        self.assertIs(comparison.previous_snapshot, previous)
        self.assertIs(comparison.latest_snapshot, latest)

    def test_source_mismatch_is_passed_unchanged_to_the_module_context(self) -> None:
        previous = snapshot(
            "discogs-snapshot",
            datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
            source="discogs",
        )
        latest = snapshot(
            "ebay-snapshot",
            datetime(2026, 7, 22, 12, tzinfo=timezone.utc),
            source="ebay",
        )
        queries = _HistoryQueries((latest, previous))
        engine = _Engine(self.execution)

        PriceChangesExecutionService(queries, engine).execute()

        comparison = engine.contexts[0].marketplace_comparison
        self.assertIs(comparison.previous_snapshot, previous)
        self.assertIs(comparison.latest_snapshot, latest)
        self.assertEqual(queries.limits, [2])
        self.assertEqual(len(engine.contexts), 1)

    def test_history_query_failure_propagates_without_engine_execution(self) -> None:
        failure = RuntimeError("Marketplace History unavailable")
        queries = _HistoryQueries(error=failure)
        engine = _Engine(self.execution)

        with self.assertRaises(RuntimeError) as raised:
            PriceChangesExecutionService(queries, engine).execute()

        self.assertIs(raised.exception, failure)
        self.assertEqual(queries.limits, [2])
        self.assertEqual(engine.contexts, [])

    def test_engine_failure_propagates_after_one_query_and_execution(self) -> None:
        failure = RuntimeError("engine unavailable")
        queries = _HistoryQueries()
        engine = _Engine(self.execution, error=failure)

        with self.assertRaises(RuntimeError) as raised:
            PriceChangesExecutionService(queries, engine).execute()

        self.assertIs(raised.exception, failure)
        self.assertEqual(queries.limits, [2])
        self.assertEqual(len(engine.contexts), 1)

    def test_malformed_dedicated_engine_results_are_rejected(self) -> None:
        other_result = IntelligenceResult(
            module_id="other_module",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Other module completed.",
        )
        malformed = (
            object(),
            IntelligenceExecution(()),
            IntelligenceExecution((self.result, self.result)),
            IntelligenceExecution((object(),)),
            IntelligenceExecution((other_result,)),
        )

        for execution in malformed:
            with self.subTest(execution=execution):
                queries = _HistoryQueries()
                engine = _Engine(execution)

                with self.assertRaises(PriceChangesExecutionConsistencyError):
                    PriceChangesExecutionService(queries, engine).execute()

                self.assertEqual(queries.limits, [2])
                self.assertEqual(len(engine.contexts), 1)


def price_changes_result() -> IntelligenceResult:
    return IntelligenceResult(
        module_id="price_changes",
        module_version="1.0",
        status=IntelligenceStatus.COMPLETED,
        summary="Price Changes completed.",
    )


def snapshot(
    snapshot_id: str,
    captured_at: datetime,
    *,
    source: str = "discogs",
) -> MarketplaceSnapshot:
    return MarketplaceSnapshot(
        snapshot_id=snapshot_id,
        captured_at=captured_at,
        source=source,
        status=MarketplaceDataStatus.EMPTY,
    )


if __name__ == "__main__":
    unittest.main()
