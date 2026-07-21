from __future__ import annotations

import unittest
from datetime import datetime, timezone

from dip.app import (
    ComparisonHistoryUnavailableError,
    HistoricalExecutionNotFoundError,
    HistoricalIntelligenceExecution,
    IntelligenceComparisonService,
)
from dip.comparison import ComparisonEngine, ExecutionComparison
from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)


class _HistoryQueries:
    def __init__(
        self,
        executions: tuple[HistoricalIntelligenceExecution, ...] = (),
        *,
        error: Exception | None = None,
    ) -> None:
        self.executions = executions
        self.error = error
        self.requested_ids: list[int] = []

    def recent_executions(
        self,
        limit: int,
    ) -> tuple[HistoricalIntelligenceExecution, ...]:
        if self.error is not None:
            raise self.error
        return tuple(reversed(self.executions))[:limit]

    def execution(
        self,
        run_id: int,
    ) -> HistoricalIntelligenceExecution | None:
        self.requested_ids.append(run_id)
        return next(
            (
                execution
                for execution in self.executions
                if execution.run.run_id == run_id
            ),
            None,
        )


class _TrackingComparisonEngine:
    def __init__(self) -> None:
        self.engine = ComparisonEngine()
        self.calls: list[
            tuple[
                HistoricalIntelligenceExecution,
                HistoricalIntelligenceExecution,
            ]
        ] = []

    def compare(
        self,
        current: HistoricalIntelligenceExecution,
        previous: HistoricalIntelligenceExecution,
    ) -> ExecutionComparison:
        self.calls.append((current, previous))
        return self.engine.compare(current, previous)


class IntelligenceComparisonServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.first = self._execution(1, score=70)
        self.latest = self._execution(2, score=80)
        self.queries = _HistoryQueries((self.first, self.latest))
        self.engine = _TrackingComparisonEngine()
        self.service = IntelligenceComparisonService(self.queries, self.engine)

    def test_compare_latest_uses_latest_and_immediate_previous_execution(
        self,
    ) -> None:
        result = self.service.compare_latest()

        self.assertEqual(result.current_run.run_id, 2)
        self.assertEqual(result.previous_run.run_id, 1)
        self.assertEqual(self.engine.calls, [(self.latest, self.first)])

    def test_compare_latest_rejects_empty_history(self) -> None:
        service = IntelligenceComparisonService(
            _HistoryQueries(),
            _TrackingComparisonEngine(),
        )

        with self.assertRaisesRegex(
            ComparisonHistoryUnavailableError,
            "history is empty",
        ):
            service.compare_latest()

    def test_compare_latest_rejects_one_historical_execution(self) -> None:
        service = IntelligenceComparisonService(
            _HistoryQueries((self.first,)),
            _TrackingComparisonEngine(),
        )

        with self.assertRaisesRegex(
            ComparisonHistoryUnavailableError,
            "At least two",
        ):
            service.compare_latest()

    def test_compare_supplied_executions_delegates_without_repository_access(
        self,
    ) -> None:
        queries = _HistoryQueries(error=AssertionError("unexpected query"))
        engine = _TrackingComparisonEngine()
        service = IntelligenceComparisonService(queries, engine)

        result = service.compare(self.latest, self.first)

        self.assertEqual(result.current_run.run_id, 2)
        self.assertEqual(engine.calls, [(self.latest, self.first)])

    def test_compare_by_run_ids_loads_current_then_previous(self) -> None:
        result = self.service.compare_by_run_ids(2, 1)

        self.assertEqual(self.queries.requested_ids, [2, 1])
        self.assertEqual(result.current_run.run_id, 2)
        self.assertEqual(result.previous_run.run_id, 1)

    def test_compare_by_run_ids_rejects_invalid_ids_before_querying(self) -> None:
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
                    self.service.compare_by_run_ids(value, 1)

        self.assertEqual(self.queries.requested_ids, [])

    def test_compare_by_run_ids_rejects_same_run_before_querying(self) -> None:
        with self.assertRaisesRegex(ValueError, "with itself"):
            self.service.compare_by_run_ids(1, 1)

        self.assertEqual(self.queries.requested_ids, [])

    def test_compare_by_run_ids_reports_missing_current_run(self) -> None:
        with self.assertRaises(HistoricalExecutionNotFoundError) as raised:
            self.service.compare_by_run_ids(99, 1)

        self.assertEqual(raised.exception.run_id, 99)
        self.assertEqual(self.queries.requested_ids, [99])

    def test_compare_by_run_ids_reports_missing_previous_run(self) -> None:
        with self.assertRaises(HistoricalExecutionNotFoundError) as raised:
            self.service.compare_by_run_ids(2, 99)

        self.assertEqual(raised.exception.run_id, 99)
        self.assertEqual(self.queries.requested_ids, [2, 99])

    def test_history_query_failures_propagate(self) -> None:
        failure = RuntimeError("history unavailable")
        service = IntelligenceComparisonService(
            _HistoryQueries(error=failure),
            _TrackingComparisonEngine(),
        )

        with self.assertRaises(RuntimeError) as raised:
            service.compare_latest()

        self.assertIs(raised.exception, failure)

    @staticmethod
    def _execution(
        run_id: int,
        *,
        score: int,
    ) -> HistoricalIntelligenceExecution:
        run = IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=datetime(2026, 7, run_id, tzinfo=timezone.utc),
            engine_version="0.3.0",
            result_count=1,
        )
        record = IntelligenceHistoryRecord(
            record_id=run_id * 10,
            run_id=run_id,
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Collection Health completed.",
            metrics={"score": score},
            evidence=("Collection analysed",),
            diagnostics=(),
        )
        return HistoricalIntelligenceExecution(run=run, records=(record,))


if __name__ == "__main__":
    unittest.main()
