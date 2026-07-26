from __future__ import annotations

import sqlite3
import tempfile
import unittest
from unittest.mock import Mock
from datetime import date, datetime, timezone
from pathlib import Path

from dip.app.collection_intelligence import (
    CollectionIntelligenceExecutionService,
    IntelligenceExecutionIncompleteError,
    RecordedIntelligenceExecution,
)
from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceExecution,
    IntelligenceResult,
    IntelligenceStatus,
    build_v02_intelligence_registry,
)
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)
from dip.persistence.sqlite import Database, SQLiteIntelligenceHistoryRepository


class _Engine:
    def __init__(self, execution: IntelligenceExecution) -> None:
        self.execution = execution
        self.contexts: list[IntelligenceContext] = []

    def execute(self, context: IntelligenceContext) -> IntelligenceExecution:
        self.contexts.append(context)
        return self.execution


class _FailingEngine:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def execute(self, context: IntelligenceContext) -> IntelligenceExecution:
        raise self.error


class _HistoryRepository:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.saved: list[
            tuple[IntelligenceHistoryRun, tuple[IntelligenceHistoryRecord, ...]]
        ] = []

    def save_execution(
        self,
        run: IntelligenceHistoryRun,
        records: tuple[IntelligenceHistoryRecord, ...],
    ) -> IntelligenceHistoryRun:
        self.saved.append((run, records))
        if self.error is not None:
            raise self.error
        return IntelligenceHistoryRun(
            run_id=41,
            executed_at=run.executed_at,
            engine_version=run.engine_version,
            collection_snapshot_id=run.collection_snapshot_id,
            result_count=run.result_count,
            marketplace_snapshot_id=run.marketplace_snapshot_id,
        )


class _ContextFactory:
    def __init__(self, context: IntelligenceContext) -> None:
        self.context = context
        self.calls = []

    def build_collector_run(self, **values) -> IntelligenceContext:
        self.calls.append(values)
        return self.context


class CollectionIntelligenceExecutionServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.executed_at = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
        self.results = (
            IntelligenceResult(
                module_id="collection_health",
                module_version="1.2",
                status=IntelligenceStatus.COMPLETED,
                summary="Collection health completed.",
                insights=("Coverage improved",),
                metrics={
                    "score": 82,
                    "observed_on": date(2026, 7, 21),
                    "series": (80, 82),
                },
                evidence=("82 releases assessed",),
                diagnostics=("Deterministic",),
            ),
            IntelligenceResult(
                module_id="hidden_gems",
                module_version="2.0",
                status="completed",
                summary="Hidden Gems completed.",
                metrics={"candidate_count": 3},
            ),
        )

    def test_success_maps_results_in_engine_order_and_returns_persisted_run(self) -> None:
        engine = _Engine(IntelligenceExecution(self.results))
        repository = _HistoryRepository()
        clock_calls = 0

        def clock() -> datetime:
            nonlocal clock_calls
            clock_calls += 1
            return self.executed_at

        service = CollectionIntelligenceExecutionService(
            engine,
            repository,
            engine_version="0.3.0",
            clock=clock,
        )
        context = IntelligenceContext(collection=({"release_id": 1},))

        outcome = service.execute(context, collection_snapshot_id=77)

        self.assertIsInstance(outcome, RecordedIntelligenceExecution)
        self.assertEqual(outcome.execution.results, self.results)
        self.assertEqual(outcome.history_run.run_id, 41)
        self.assertEqual(engine.contexts, [context])
        self.assertEqual(len(repository.saved), 1)
        run, records = repository.saved[0]
        self.assertEqual(clock_calls, 1)
        self.assertEqual(run.executed_at, self.executed_at)
        self.assertEqual(run.engine_version, "0.3.0")
        self.assertEqual(run.collection_snapshot_id, 77)
        self.assertEqual(run.result_count, 2)
        self.assertEqual(
            tuple(record.module_id for record in records),
            ("collection_health", "hidden_gems"),
        )
        self.assertTrue(all(record.run_id is None for record in records))
        self.assertTrue(all(record.record_id is None for record in records))
        self.assertEqual(records[0].module_version, "1.2")
        self.assertIs(records[1].status, IntelligenceStatus.COMPLETED)
        self.assertEqual(records[0].summary, self.results[0].summary)
        self.assertEqual(records[0].insights, self.results[0].insights)
        self.assertEqual(dict(records[0].metrics), self.results[0].metrics)
        self.assertEqual(records[0].evidence, self.results[0].evidence)
        self.assertEqual(records[0].diagnostics, self.results[0].diagnostics)

    def test_empty_execution_is_recorded_as_a_valid_observation(self) -> None:
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution(())),
            repository,
            clock=lambda: self.executed_at,
        )

        outcome = service.execute(IntelligenceContext())

        run, records = repository.saved[0]
        self.assertEqual(outcome.execution.results, ())
        self.assertEqual(run.result_count, 0)
        self.assertEqual(records, ())

    def test_engine_exception_is_visible_and_repository_is_not_called(self) -> None:
        failure = RuntimeError("engine failed")
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _FailingEngine(failure),
            repository,
        )

        with self.assertRaises(RuntimeError) as raised:
            service.execute(IntelligenceContext())

        self.assertIs(raised.exception, failure)
        self.assertEqual(repository.saved, [])

    def test_incomplete_execution_is_visible_and_not_persisted(self) -> None:
        failed = IntelligenceResult(
            module_id="hidden_gems",
            module_version="1.0",
            status=IntelligenceStatus.FAILED,
            summary="Failed.",
            diagnostics=("RuntimeError: failure",),
        )
        execution = IntelligenceExecution((self.results[0], failed))
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _Engine(execution),
            repository,
        )

        with self.assertRaises(IntelligenceExecutionIncompleteError) as raised:
            service.execute(IntelligenceContext())

        self.assertIs(raised.exception.execution, execution)
        self.assertIn("hidden_gems", str(raised.exception))
        self.assertEqual(repository.saved, [])

    def test_skipped_execution_is_not_persisted(self) -> None:
        skipped = IntelligenceResult(
            module_id="historical_intelligence",
            module_version="0.2",
            status=IntelligenceStatus.SKIPPED,
            summary="Insufficient history.",
        )
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution((skipped,))),
            repository,
        )

        with self.assertRaises(IntelligenceExecutionIncompleteError):
            service.execute(IntelligenceContext())

        self.assertEqual(repository.saved, [])

    def test_conversion_failure_occurs_before_repository_call(self) -> None:
        invalid = IntelligenceResult(
            module_id="invalid",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Completed.",
            metrics={"unsupported": object()},
        )
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution((invalid,))),
            repository,
        )

        with self.assertRaises(TypeError):
            service.execute(IntelligenceContext())

        self.assertEqual(repository.saved, [])

    def test_persistence_failure_is_propagated_without_success_result(self) -> None:
        failure = RuntimeError("history unavailable")
        repository = _HistoryRepository(error=failure)
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution((self.results[0],))),
            repository,
            clock=lambda: self.executed_at,
        )

        with self.assertRaises(RuntimeError) as raised:
            service.execute(IntelligenceContext())

        self.assertIs(raised.exception, failure)
        self.assertEqual(len(repository.saved), 1)

    def test_collector_run_persists_completed_and_skipped_in_registry_order(self):
        skipped = IntelligenceResult(
            module_id="historical_intelligence",
            module_version="0.2",
            status=IntelligenceStatus.SKIPPED,
            summary="A predecessor is not yet available.",
            metrics={"snapshot_count": 1},
            evidence=("Current canonical snapshot retained.",),
            diagnostics=("Two snapshots are required.",),
        )
        execution = IntelligenceExecution((self.results[0], skipped))
        repository = _HistoryRepository()
        context = IntelligenceContext()
        factory = _ContextFactory(context)
        clock = Mock(side_effect=AssertionError("collector execution used clock"))
        service = CollectionIntelligenceExecutionService(
            _Engine(execution),
            repository,
            factory,
            engine_version="0.2",
            clock=clock,
        )
        snapshot = MarketplaceSnapshot(
            "collector-run-7",
            self.executed_at,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (
                MarketplaceReleaseObservation(
                    1,
                    self.executed_at,
                    MarketplaceDataStatus.COMPLETE,
                    num_wanted=0,
                ),
            ),
        )

        outcome = service.execute_collector_run(
            analysis_run_id=7,
            marketplace_snapshot=snapshot,
            release_ids=(1,),
            executed_at=self.executed_at,
        )

        clock.assert_not_called()
        self.assertEqual(factory.calls[0]["captured_at"], self.executed_at)
        run, records = repository.saved[0]
        self.assertEqual(run.marketplace_snapshot_id, "collector-run-7")
        self.assertEqual(run.executed_at, self.executed_at)
        self.assertEqual(run.engine_version, "0.2")
        self.assertEqual(
            tuple(record.status for record in records),
            (IntelligenceStatus.COMPLETED, IntelligenceStatus.SKIPPED),
        )
        self.assertEqual(records[1].metrics["snapshot_count"], 1)
        self.assertEqual(records[1].evidence, skipped.evidence)
        self.assertEqual(records[1].diagnostics, skipped.diagnostics)
        self.assertEqual(
            outcome.history_run.marketplace_snapshot_id,
            "collector-run-7",
        )

    def test_collector_run_all_skipped_persists_but_failed_does_not(self):
        snapshot = MarketplaceSnapshot(
            "collector-run-7",
            self.executed_at,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (
                MarketplaceReleaseObservation(
                    1,
                    self.executed_at,
                    MarketplaceDataStatus.COMPLETE,
                    num_wanted=0,
                ),
            ),
        )
        skipped = IntelligenceResult(
            module_id="historical_intelligence",
            module_version="0.2",
            status=IntelligenceStatus.SKIPPED,
            summary="Skipped.",
        )
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution((skipped,))),
            repository,
            _ContextFactory(IntelligenceContext()),
        )
        service.execute_collector_run(
            analysis_run_id=7,
            marketplace_snapshot=snapshot,
            release_ids=(1,),
            executed_at=self.executed_at,
        )
        self.assertEqual(len(repository.saved), 1)

        failed = IntelligenceResult(
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.FAILED,
            summary="Failed.",
            diagnostics=("Safe failure.",),
        )
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution((skipped, failed))),
            repository,
            _ContextFactory(IntelligenceContext()),
        )
        with self.assertRaises(IntelligenceExecutionIncompleteError):
            service.execute_collector_run(
                analysis_run_id=7,
                marketplace_snapshot=snapshot,
                release_ids=(1,),
                executed_at=self.executed_at,
            )
        self.assertEqual(repository.saved, [])

    def test_collector_run_invalid_status_rejects_without_history_mutation(self):
        snapshot = MarketplaceSnapshot(
            "collector-run-7",
            self.executed_at,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (
                MarketplaceReleaseObservation(
                    1,
                    self.executed_at,
                    MarketplaceDataStatus.COMPLETE,
                    num_wanted=0,
                ),
            ),
        )
        invalid = IntelligenceResult(
            module_id="collection_health",
            module_version="1.0",
            status="not-a-status",
            summary="Invalid.",
        )
        repository = _HistoryRepository()
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution((invalid,))),
            repository,
            _ContextFactory(IntelligenceContext()),
        )
        with self.assertRaises(ValueError):
            service.execute_collector_run(
                analysis_run_id=7,
                marketplace_snapshot=snapshot,
                release_ids=(1,),
                executed_at=self.executed_at,
            )
        self.assertEqual(repository.saved, [])


class CollectionIntelligenceExecutionSQLiteTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database = Database(
            Path(self.temp_directory.name) / "execution_history.db"
        )
        self.repository = SQLiteIntelligenceHistoryRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def test_default_engine_persists_complex_completed_results(self) -> None:
        context = IntelligenceContext(
            collection=(
                {
                    "release_id": 1,
                    "artist": "Artist",
                    "title": "Title",
                    "label": "Label",
                    "rating": 4.5,
                },
            ),
            marketplace={
                1: {
                    "wants": 200,
                    "copies_for_sale": 2,
                    "community_rating": 4.5,
                    "lowest_price": 12,
                }
            },
            history={
                1: (
                    {
                        "release_id": 1,
                        "artist": "Artist",
                        "title": "Title",
                        "captured_at": "2026-07-20T10:00:00Z",
                        "lowest_price": 10,
                    },
                ),
                2: (
                    {
                        "release_id": 1,
                        "artist": "Artist",
                        "title": "Title",
                        "captured_at": "2026-07-21T10:00:00Z",
                        "lowest_price": 12,
                    },
                ),
            },
        )
        service = CollectionIntelligenceExecutionService(
            IntelligenceEngine(build_v02_intelligence_registry()),
            self.repository,
            engine_version="0.3.0",
            clock=lambda: datetime(2026, 7, 21, 12, tzinfo=timezone.utc),
        )

        outcome = service.execute(context, collection_snapshot_id=88)

        self.assertEqual(outcome.history_run.result_count, 3)
        self.assertEqual(outcome.history_run.collection_snapshot_id, 88)
        self.assertEqual(
            tuple(
                record.module_id
                for record in self.repository.history_for_module(
                    "historical_intelligence"
                )
            ),
            ("historical_intelligence",),
        )
        historical = self.repository.latest_result("historical_intelligence")
        self.assertEqual(
            historical.metrics["comparison"].current_total_estimated_value,
            outcome.execution.result_for("historical_intelligence").metrics[
                "comparison"
            ].current_total_estimated_value,
        )

    def test_database_failure_rolls_back_complete_orchestration_save(self) -> None:
        duplicate_results = (
            self._result("duplicate", 1),
            self._result("duplicate", 2),
        )
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution(duplicate_results)),
            self.repository,
            clock=lambda: datetime(2026, 7, 21, 12),
        )

        with self.assertRaises(sqlite3.IntegrityError):
            service.execute(IntelligenceContext())

        self.assertIsNone(self.repository.latest_run())

    def test_orchestration_respects_caller_owned_transaction(self) -> None:
        self.database.conn.execute(
            "INSERT INTO app_settings(key, value) VALUES (?, ?)",
            ("caller", "pending"),
        )
        service = CollectionIntelligenceExecutionService(
            _Engine(IntelligenceExecution((self._result("module", 1),))),
            self.repository,
            clock=lambda: datetime(2026, 7, 21, 12),
        )

        outcome = service.execute(IntelligenceContext())

        self.assertIsNotNone(outcome.history_run.run_id)
        self.assertTrue(self.database.conn.in_transaction)
        self.database.conn.rollback()
        self.assertIsNone(self.repository.latest_run())

    @staticmethod
    def _result(module_id: str, value: int) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=module_id,
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Completed.",
            metrics={"value": value},
        )


if __name__ == "__main__":
    unittest.main()
