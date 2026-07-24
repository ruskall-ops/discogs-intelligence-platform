from __future__ import annotations

import unittest
from datetime import datetime, timezone

from dip.app import (
    ComparisonPresentationService,
    HistoricalIntelligenceExecution,
)
from dip.comparison import ComparisonEngine, ExecutionComparison
from dip.experience.comparison import (
    ComparisonViewModelBuilder,
    ComparisonViewModelConsistencyError,
    ExecutionComparisonViewModel,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)


class _ComparisonService:
    def __init__(
        self,
        comparison: ExecutionComparison,
        *,
        error: Exception | None = None,
    ) -> None:
        self.comparison = comparison
        self.error = error
        self.latest_calls = 0
        self.run_id_calls: list[tuple[int, int]] = []

    def compare_latest(self) -> ExecutionComparison:
        self.latest_calls += 1
        if self.error is not None:
            raise self.error
        return self.comparison

    def compare_by_run_ids(
        self,
        current_run_id: int,
        previous_run_id: int,
    ) -> ExecutionComparison:
        self.run_id_calls.append((current_run_id, previous_run_id))
        if self.error is not None:
            raise self.error
        return self.comparison


class _TrackingBuilder:
    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.builder = ComparisonViewModelBuilder()
        self.error = error
        self.comparisons: list[ExecutionComparison] = []

    def build(
        self,
        comparison: ExecutionComparison,
    ) -> ExecutionComparisonViewModel:
        self.comparisons.append(comparison)
        if self.error is not None:
            raise self.error
        return self.builder.build(comparison)


class ComparisonPresentationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.comparison = self._comparison()
        self.comparison_service = _ComparisonService(self.comparison)
        self.builder = _TrackingBuilder()
        self.service = ComparisonPresentationService(
            self.comparison_service,
            self.builder,
        )

    def test_latest_comparison_is_transformed_to_view_model(self) -> None:
        view_model = self.service.latest_view_model()

        self.assertIsInstance(view_model, ExecutionComparisonViewModel)
        self.assertEqual(view_model.current_run_id, 2)
        self.assertEqual(view_model.previous_run_id, 1)
        self.assertEqual(self.comparison_service.latest_calls, 1)
        self.assertEqual(self.builder.comparisons, [self.comparison])

    def test_run_id_comparison_is_transformed_to_view_model(self) -> None:
        view_model = self.service.view_model_for_runs(8, 5)

        self.assertEqual(view_model.current_run_id, 2)
        self.assertEqual(self.comparison_service.run_id_calls, [(8, 5)])
        self.assertEqual(self.builder.comparisons, [self.comparison])

    def test_existing_comparison_build_does_not_call_comparison_service(self) -> None:
        view_model = self.service.build_view_model(self.comparison)

        self.assertEqual(view_model.total_module_count, 1)
        self.assertEqual(self.comparison_service.latest_calls, 0)
        self.assertEqual(self.comparison_service.run_id_calls, [])

    def test_comparison_service_failures_propagate_unchanged(self) -> None:
        failure = RuntimeError("comparison unavailable")
        service = ComparisonPresentationService(
            _ComparisonService(self.comparison, error=failure),
            _TrackingBuilder(),
        )

        with self.assertRaises(RuntimeError) as raised:
            service.latest_view_model()

        self.assertIs(raised.exception, failure)

    def test_builder_failures_propagate_unchanged(self) -> None:
        failure = ComparisonViewModelConsistencyError("malformed comparison")
        service = ComparisonPresentationService(
            self.comparison_service,
            _TrackingBuilder(error=failure),
        )

        with self.assertRaises(ComparisonViewModelConsistencyError) as raised:
            service.latest_view_model()

        self.assertIs(raised.exception, failure)

    @staticmethod
    def _comparison() -> ExecutionComparison:
        previous = ComparisonPresentationServiceTestCase._execution(1, score=80)
        current = ComparisonPresentationServiceTestCase._execution(2, score=82)
        return ComparisonEngine().compare(current, previous)

    @staticmethod
    def _execution(
        run_id: int,
        *,
        score: int,
    ) -> HistoricalIntelligenceExecution:
        run = IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=datetime(2026, 7, run_id, tzinfo=timezone.utc),
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
