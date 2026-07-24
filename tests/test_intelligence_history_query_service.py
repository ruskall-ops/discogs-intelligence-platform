from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from dip.app import (
    HistoricalIntelligenceExecution,
    HistoricalModuleResult,
    IntelligenceHistoryConsistencyError,
    IntelligenceHistoryQueryService,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)


class _HistoryRepository:
    def __init__(
        self,
        executions: tuple[
            tuple[
                IntelligenceHistoryRun,
                tuple[IntelligenceHistoryRecord, ...],
            ],
            ...,
        ] = (),
    ) -> None:
        self.executions = executions
        self.save_calls = 0

    def save_execution(
        self,
        run: IntelligenceHistoryRun,
        records: tuple[IntelligenceHistoryRecord, ...],
    ) -> IntelligenceHistoryRun:
        self.save_calls += 1
        raise AssertionError("The query service must not write history.")

    def latest_run(self) -> IntelligenceHistoryRun | None:
        runs = self._newest_first_runs()
        return runs[0] if runs else None

    def previous_run(self) -> IntelligenceHistoryRun | None:
        runs = self._newest_first_runs()
        return runs[1] if len(runs) > 1 else None

    def run_by_id(self, run_id: int) -> IntelligenceHistoryRun | None:
        return next(
            (run for run, _ in self.executions if run.run_id == run_id),
            None,
        )

    def recent_runs(
        self,
        limit: int,
    ) -> tuple[IntelligenceHistoryRun, ...]:
        return self._newest_first_runs()[:limit]

    def records_for_run(
        self,
        run_id: int,
    ) -> tuple[IntelligenceHistoryRecord, ...]:
        return next(
            (records for run, records in self.executions if run.run_id == run_id),
            (),
        )

    def latest_result(
        self,
        module_id: str,
    ) -> IntelligenceHistoryRecord | None:
        history = self.history_for_module(module_id)
        return history[-1] if history else None

    def previous_result(
        self,
        module_id: str,
    ) -> IntelligenceHistoryRecord | None:
        history = self.history_for_module(module_id)
        return history[-2] if len(history) > 1 else None

    def history_for_module(
        self,
        module_id: str,
    ) -> tuple[IntelligenceHistoryRecord, ...]:
        return tuple(
            record
            for run in self._oldest_first_runs()
            for record in self.records_for_run(run.run_id)
            if record.module_id == module_id
        )

    def _newest_first_runs(self) -> tuple[IntelligenceHistoryRun, ...]:
        return tuple(reversed(self._oldest_first_runs()))

    def _oldest_first_runs(self) -> tuple[IntelligenceHistoryRun, ...]:
        return tuple(
            sorted(
                (run for run, _ in self.executions),
                key=lambda run: (run.executed_at, run.run_id),
            )
        )


class _FailingHistoryRepository(_HistoryRepository):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def latest_run(self) -> IntelligenceHistoryRun | None:
        raise self.error


class IntelligenceHistoryQueryServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        first = self._execution(
            1,
            datetime(2026, 7, 19, 10, tzinfo=timezone.utc),
            ("collection_health",),
        )
        gap = self._execution(
            2,
            datetime(2026, 7, 20, 10, tzinfo=timezone.utc),
            ("hidden_gems",),
        )
        latest = self._execution(
            3,
            datetime(2026, 7, 21, 10, tzinfo=timezone.utc),
            ("hidden_gems", "collection_health"),
        )
        self.executions = (first, gap, latest)
        self.repository = _HistoryRepository(self.executions)
        self.service = IntelligenceHistoryQueryService(self.repository)

    def test_empty_history_uses_documented_absence_values(self) -> None:
        service = IntelligenceHistoryQueryService(_HistoryRepository())

        self.assertIsNone(service.latest_execution())
        self.assertIsNone(service.previous_execution())
        self.assertIsNone(service.execution(1))
        self.assertEqual(service.recent_executions(3), ())
        self.assertEqual(service.module_history("collection_health"), ())
        self.assertIsNone(service.latest_module_result("collection_health"))
        self.assertIsNone(service.previous_module_result("collection_health"))

    def test_latest_execution_contains_all_records_in_persisted_order(self) -> None:
        execution = self.service.latest_execution()

        self.assertIsInstance(execution, HistoricalIntelligenceExecution)
        self.assertEqual(execution.run.run_id, 3)
        self.assertEqual(
            tuple(record.module_id for record in execution.records),
            ("hidden_gems", "collection_health"),
        )
        self.assertIsInstance(execution.records, tuple)

    def test_execution_models_are_immutable_including_record_metrics(self) -> None:
        execution = self.service.latest_execution()

        with self.assertRaises(FrozenInstanceError):
            execution.records = ()
        with self.assertRaises(TypeError):
            execution.records[0].metrics["score"] = 99

    def test_execution_model_detaches_a_mutable_records_collection(self) -> None:
        run, records = self.executions[0]
        mutable_records = list(records)

        execution = HistoricalIntelligenceExecution(
            run=run,
            records=mutable_records,
        )
        mutable_records.clear()

        self.assertEqual(execution.records, records)

    def test_previous_execution_is_the_immediate_global_predecessor(self) -> None:
        execution = self.service.previous_execution()

        self.assertEqual(execution.run.run_id, 2)
        self.assertEqual(execution.records[0].module_id, "hidden_gems")

    def test_previous_execution_is_absent_with_fewer_than_two_runs(self) -> None:
        service = IntelligenceHistoryQueryService(
            _HistoryRepository((self.executions[0],))
        )

        self.assertIsNone(service.previous_execution())

    def test_execution_by_id_returns_complete_execution_or_none(self) -> None:
        execution = self.service.execution(1)

        self.assertEqual(execution.run.run_id, 1)
        self.assertEqual(len(execution.records), 1)
        self.assertIsNone(self.service.execution(99))

    def test_execution_rejects_invalid_run_ids(self) -> None:
        for value, error in (
            (True, TypeError),
            (False, TypeError),
            ("1", TypeError),
            (1.0, TypeError),
            (None, TypeError),
            (0, ValueError),
            (-1, ValueError),
        ):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    self.service.execution(value)

    def test_recent_executions_respects_limit_and_newest_first_order(self) -> None:
        executions = self.service.recent_executions(2)

        self.assertEqual(
            tuple(execution.run.run_id for execution in executions),
            (3, 2),
        )
        self.assertTrue(
            all(execution.run.result_count == len(execution.records)
                for execution in executions)
        )

    def test_recent_executions_uses_run_id_to_break_timestamp_ties(self) -> None:
        timestamp = datetime(2026, 7, 21, 10, tzinfo=timezone.utc)
        first = self._execution(4, timestamp, ("collection_health",))
        second = self._execution(5, timestamp, ("collection_health",))
        service = IntelligenceHistoryQueryService(
            _HistoryRepository((first, second))
        )

        self.assertEqual(
            tuple(item.run.run_id for item in service.recent_executions(2)),
            (5, 4),
        )

    def test_recent_executions_rejects_invalid_limits(self) -> None:
        for value, error in (
            (True, TypeError),
            ("2", TypeError),
            (2.0, TypeError),
            (None, TypeError),
            (0, ValueError),
            (-2, ValueError),
        ):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    self.service.recent_executions(value)

    def test_module_history_is_newest_first_with_parent_run_context(self) -> None:
        history = self.service.module_history("collection_health")

        self.assertTrue(
            all(isinstance(item, HistoricalModuleResult) for item in history)
        )
        self.assertEqual(tuple(item.run.run_id for item in history), (3, 1))
        self.assertEqual(
            tuple(item.record.metrics["score"] for item in history),
            (31, 10),
        )

    def test_module_history_limit_selects_the_most_recent_results(self) -> None:
        history = self.service.module_history("collection_health", limit=1)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].run.run_id, 3)

    def test_module_history_handles_missing_module(self) -> None:
        self.assertEqual(self.service.module_history("not_registered"), ())

    def test_module_queries_reject_invalid_module_ids_and_limits(self) -> None:
        for value, error in (
            (None, TypeError),
            (1, TypeError),
            ("", ValueError),
            ("   ", ValueError),
            (" collection_health", ValueError),
            ("collection_health ", ValueError),
        ):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    self.service.module_history(value)

        for value, error in (
            (True, TypeError),
            ("1", TypeError),
            (1.0, TypeError),
            (0, ValueError),
            (-1, ValueError),
        ):
            with self.subTest(limit=value):
                with self.assertRaises(error):
                    self.service.module_history("collection_health", value)

    def test_latest_and_previous_module_results_are_module_specific(self) -> None:
        latest = self.service.latest_module_result("collection_health")
        previous = self.service.previous_module_result("collection_health")

        self.assertEqual(latest.run.run_id, 3)
        self.assertEqual(previous.run.run_id, 1)
        self.assertEqual(previous.record.module_id, "collection_health")

    def test_latest_and_previous_module_result_validate_module_id(self) -> None:
        for query in (
            self.service.latest_module_result,
            self.service.previous_module_result,
        ):
            with self.subTest(query=query.__name__):
                with self.assertRaises(TypeError):
                    query(True)
                with self.assertRaises(ValueError):
                    query("")

    def test_result_count_mismatch_is_reported_as_inconsistent_history(self) -> None:
        run, records = self.executions[-1]
        invalid_run = IntelligenceHistoryRun(
            run_id=run.run_id,
            executed_at=run.executed_at,
            result_count=run.result_count + 1,
        )
        service = IntelligenceHistoryQueryService(
            _HistoryRepository(((invalid_run, records),))
        )

        with self.assertRaisesRegex(
            IntelligenceHistoryConsistencyError,
            "result_count",
        ):
            service.latest_execution()

    def test_wrong_run_association_is_reported_as_inconsistent_history(self) -> None:
        run, records = self.executions[0]
        wrong_record = self._record(20, 2, "collection_health")
        service = IntelligenceHistoryQueryService(
            _HistoryRepository(((run, (wrong_record,)),))
        )

        with self.assertRaisesRegex(
            IntelligenceHistoryConsistencyError,
            "belong to the execution run",
        ):
            service.latest_execution()

    def test_duplicate_module_records_are_reported_as_inconsistent_history(
        self,
    ) -> None:
        run = self._run(4, result_count=2)
        records = (
            self._record(40, 4, "collection_health"),
            self._record(41, 4, "collection_health"),
        )
        service = IntelligenceHistoryQueryService(
            _HistoryRepository(((run, records),))
        )

        with self.assertRaisesRegex(
            IntelligenceHistoryConsistencyError,
            "unique",
        ):
            service.latest_execution()

    def test_missing_module_parent_run_is_reported_as_inconsistent(self) -> None:
        repository = _HistoryRepository()
        record = self._record(50, 5, "collection_health")
        repository.latest_result = lambda module_id: record
        service = IntelligenceHistoryQueryService(repository)

        with self.assertRaisesRegex(
            IntelligenceHistoryConsistencyError,
            "missing run 5",
        ):
            service.latest_module_result("collection_health")

    def test_repository_returning_wrong_module_is_reported_as_inconsistent(
        self,
    ) -> None:
        repository = _HistoryRepository(self.executions)
        repository.latest_result = lambda module_id: self.executions[-1][1][0]
        service = IntelligenceHistoryQueryService(repository)

        with self.assertRaisesRegex(
            IntelligenceHistoryConsistencyError,
            "for requested module",
        ):
            service.latest_module_result("collection_health")

    def test_repository_failures_propagate_without_being_swallowed(self) -> None:
        failure = RuntimeError("history unavailable")
        service = IntelligenceHistoryQueryService(
            _FailingHistoryRepository(failure)
        )

        with self.assertRaises(RuntimeError) as raised:
            service.latest_execution()

        self.assertIs(raised.exception, failure)

    def test_queries_never_call_the_repository_write_method(self) -> None:
        self.service.latest_execution()
        self.service.previous_execution()
        self.service.execution(1)
        self.service.recent_executions(2)
        self.service.module_history("collection_health")
        self.service.latest_module_result("collection_health")
        self.service.previous_module_result("collection_health")

        self.assertEqual(self.repository.save_calls, 0)

    @classmethod
    def _execution(
        cls,
        run_id: int,
        executed_at: datetime,
        module_ids: tuple[str, ...],
    ) -> tuple[
        IntelligenceHistoryRun,
        tuple[IntelligenceHistoryRecord, ...],
    ]:
        run = IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=executed_at,
            engine_version="0.3.0",
            result_count=len(module_ids),
        )
        records = tuple(
            cls._record(run_id * 10 + index, run_id, module_id)
            for index, module_id in enumerate(module_ids)
        )
        return run, records

    @staticmethod
    def _run(
        run_id: int,
        *,
        result_count: int,
    ) -> IntelligenceHistoryRun:
        return IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
            result_count=result_count,
        )

    @staticmethod
    def _record(
        record_id: int,
        run_id: int,
        module_id: str,
    ) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=record_id,
            run_id=run_id,
            module_id=module_id,
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary=f"{module_id} completed.",
            metrics={"score": record_id},
        )


if __name__ == "__main__":
    unittest.main()
