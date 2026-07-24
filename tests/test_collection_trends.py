from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    CollectionHealthPresentationService,
    CollectionTrendsPresentationService,
    HiddenGemsPresentationService,
    HistoricalIntelligenceExecution,
)
from dip.comparison import ComparisonEngine
from dip.experience.collection_health import CollectionHealthDetailViewModelBuilder
from dip.experience.collection_trends import (
    CollectionTrendDirection,
    CollectionTrendExecutionViewModel,
    CollectionTrendMetricViewModel,
    CollectionTrendValueKind,
    CollectionTrendsConsistencyError,
    CollectionTrendsState,
    CollectionTrendsViewModel,
    CollectionTrendsViewModelBuilder,
)
from dip.experience.dashboard import DashboardHomepageViewModelBuilder
from dip.experience.desktop import (
    DesktopCollectionExplorerController,
    DesktopCollectionExplorerRenderer,
    DesktopCollectionTrendsRenderer,
)
from dip.experience.explorer import (
    CollectionExplorerDestination,
    CollectionExplorerViewModelBuilder,
)
from dip.experience.hidden_gems import HiddenGemsDetailViewModelBuilder
from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import IntelligenceHistoryRecord, IntelligenceHistoryRun
from tests.test_dashboard_homepage import (
    execution as dashboard_execution,
    health_record,
    hidden_record,
)
from tests.test_hidden_gems_experience import candidate


METRIC_ORDER = (
    "collection_size",
    "collection_health.overall_score",
    "collection_health.metadata_completeness",
    "collection_health.marketplace_coverage",
    "collection_health.demand_strength",
    "collection_health.valuation_coverage",
    "hidden_gems.candidate_count",
    "completed_module_count",
)


class CollectionTrendsBuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = CollectionTrendsViewModelBuilder()

    def test_two_complete_executions_produce_canonical_neutral_changes(self) -> None:
        previous = trend_execution(1, score=80, size=10, hidden_count=2)
        latest = trend_execution(
            2,
            score=82,
            size=12,
            hidden_count=3,
            components=(85, 82, 83, 84),
        )

        trends = build_trends(latest, previous)

        self.assertIs(trends.state, CollectionTrendsState.AVAILABLE)
        self.assertEqual(tuple(metric.metric_id for metric in trends.metrics), METRIC_ORDER)
        by_id = {metric.metric_id: metric for metric in trends.metrics}
        self.assertEqual(by_id["collection_size"].delta, 2)
        self.assertIs(by_id["collection_size"].direction, CollectionTrendDirection.INCREASED)
        self.assertEqual(by_id["collection_health.overall_score"].delta, 2.0)
        self.assertIs(by_id["collection_health.metadata_completeness"].direction, CollectionTrendDirection.INCREASED)
        self.assertIs(by_id["collection_health.marketplace_coverage"].direction, CollectionTrendDirection.UNCHANGED)
        self.assertIs(by_id["collection_health.demand_strength"].direction, CollectionTrendDirection.UNCHANGED)
        self.assertIs(by_id["collection_health.valuation_coverage"].direction, CollectionTrendDirection.UNCHANGED)
        self.assertIs(by_id["completed_module_count"].direction, CollectionTrendDirection.UNCHANGED)

    def test_score_decrease_is_neutral_and_absolute(self) -> None:
        trends = build_trends(
            trend_execution(2, score=70, size=10, hidden_count=2),
            trend_execution(1, score=80, size=10, hidden_count=2),
        )
        metric = next(
            item for item in trends.metrics
            if item.metric_id == "collection_health.overall_score"
        )

        self.assertEqual(metric.previous_value, 80.0)
        self.assertEqual(metric.latest_value, 70.0)
        self.assertEqual(metric.delta, -10.0)
        self.assertIs(metric.direction, CollectionTrendDirection.DECREASED)
        self.assertFalse(hasattr(metric, "percentage_change"))
        self.assertNotIn("improved", trends.summary.lower())
        self.assertNotIn("worsened", trends.summary.lower())

    def test_newly_and_no_longer_available_metrics_are_partial(self) -> None:
        previous = trend_execution(1, score=None, size=10, hidden_count=2)
        latest = trend_execution(2, score=80, size=10, hidden_count=None)

        trends = build_trends(latest, previous)
        by_id = {metric.metric_id: metric for metric in trends.metrics}

        self.assertIs(trends.state, CollectionTrendsState.PARTIAL)
        self.assertIs(
            by_id["collection_health.overall_score"].direction,
            CollectionTrendDirection.NEWLY_AVAILABLE,
        )
        self.assertIs(
            by_id["hidden_gems.candidate_count"].direction,
            CollectionTrendDirection.NO_LONGER_AVAILABLE,
        )
        self.assertIsNone(by_id["hidden_gems.candidate_count"].delta)

    def test_malformed_metric_is_incomparable_without_hiding_valid_metrics(self) -> None:
        previous = trend_execution(1, score=80, size=10, hidden_count=2)
        latest = trend_execution(2, score="invalid", size=12, hidden_count=3)

        trends = build_trends(latest, previous)
        health = next(
            item for item in trends.metrics
            if item.metric_id == "collection_health.overall_score"
        )

        self.assertIs(trends.state, CollectionTrendsState.PARTIAL)
        self.assertIs(health.direction, CollectionTrendDirection.INCOMPARABLE)
        self.assertIsNone(health.latest_value)
        self.assertIsNone(health.delta)
        self.assertEqual(trends.metrics[0].delta, 2)

    def test_no_history_one_execution_and_nontrendable_history_are_explicit(self) -> None:
        no_history = self.builder.build((), None, history_exists=False)
        one = trend_execution(1, score=80, size=10, hidden_count=2)
        insufficient = self.builder.build((one,), None, history_exists=True)
        empty = self.builder.build((), None, history_exists=True)

        self.assertIs(no_history.state, CollectionTrendsState.UNAVAILABLE)
        self.assertIs(insufficient.state, CollectionTrendsState.INSUFFICIENT_HISTORY)
        self.assertEqual(insufficient.latest_execution.run_id, 1)
        self.assertIs(empty.state, CollectionTrendsState.EMPTY)


class CollectionTrendsModelTestCase(unittest.TestCase):
    def test_models_are_frozen_and_defensively_freeze_metrics(self) -> None:
        trends = build_trends(
            trend_execution(2, score=82, size=12, hidden_count=3),
            trend_execution(1, score=80, size=10, hidden_count=2),
        )
        copied = replace(trends, metrics=list(trends.metrics))

        self.assertIsInstance(copied.metrics, tuple)
        with self.assertRaises(FrozenInstanceError):
            copied.summary = "Changed"  # type: ignore[misc]

    def test_duplicate_reordered_metrics_and_contradictory_states_are_rejected(self) -> None:
        trends = build_trends(
            trend_execution(2, score=82, size=12, hidden_count=3),
            trend_execution(1, score=80, size=10, hidden_count=2),
        )

        with self.assertRaisesRegex(CollectionTrendsConsistencyError, "unique"):
            replace(trends, metrics=(trends.metrics[0], trends.metrics[0]))
        with self.assertRaisesRegex(CollectionTrendsConsistencyError, "canonical"):
            replace(trends, metrics=tuple(reversed(trends.metrics)))
        with self.assertRaisesRegex(CollectionTrendsConsistencyError, "Comparable"):
            replace(trends, metrics=())

    def test_metric_delta_and_direction_are_validated(self) -> None:
        with self.assertRaisesRegex(CollectionTrendsConsistencyError, "delta"):
            CollectionTrendMetricViewModel(
                "collection_size",
                "Collection size",
                CollectionTrendValueKind.COUNT,
                10,
                12,
                3,
                CollectionTrendDirection.INCREASED,
            )

    def test_execution_order_is_validated_with_run_id_tie_breaking(self) -> None:
        moment = datetime(2026, 7, 21, tzinfo=timezone.utc)
        earlier = CollectionTrendExecutionViewModel(2, moment, "1.0")
        later = CollectionTrendExecutionViewModel(1, moment, "1.0")
        metric = CollectionTrendMetricViewModel(
            "completed_module_count",
            "Completed modules",
            CollectionTrendValueKind.COUNT,
            1,
            1,
            0,
            CollectionTrendDirection.UNCHANGED,
        )

        with self.assertRaisesRegex(CollectionTrendsConsistencyError, "must follow"):
            CollectionTrendsViewModel(
                CollectionTrendsState.AVAILABLE,
                "Comparison.",
                previous_execution=earlier,
                latest_execution=later,
                metrics=(metric,),
            )

        duplicate_run = CollectionTrendExecutionViewModel(
            2,
            datetime(2026, 7, 22, tzinfo=timezone.utc),
            "1.0",
        )
        with self.assertRaisesRegex(CollectionTrendsConsistencyError, "distinct"):
            CollectionTrendsViewModel(
                CollectionTrendsState.AVAILABLE,
                "Comparison.",
                previous_execution=earlier,
                latest_execution=duplicate_run,
                metrics=(metric,),
            )


class CollectionTrendsPresentationServiceTestCase(unittest.TestCase):
    def test_queries_once_and_selects_latest_two_from_five_candidate_window(self) -> None:
        executions = tuple(
            trend_execution(run_id, score=70 + run_id, size=10, hidden_count=2)
            for run_id in range(4, 0, -1)
        )
        history = RecordingHistory(executions)
        comparison = RecordingComparison()
        service = CollectionTrendsPresentationService(
            history,
            comparison,
            CollectionTrendsViewModelBuilder(),
        )

        trends = service.latest_trends()

        self.assertEqual(history.limits, [5])
        self.assertEqual(comparison.calls, [(executions[0], executions[1])])
        self.assertEqual(trends.latest_execution.run_id, 4)
        self.assertEqual(trends.previous_execution.run_id, 3)

    def test_noncomparable_failed_latest_execution_is_skipped(self) -> None:
        failed = failed_execution(3)
        second = trend_execution(2, score=80, size=10, hidden_count=2)
        first = trend_execution(1, score=70, size=9, hidden_count=1)
        history = RecordingHistory((failed, second, first))
        comparison = RecordingComparison()

        trends = CollectionTrendsPresentationService(
            history,
            comparison,
            CollectionTrendsViewModelBuilder(),
        ).latest_trends()

        self.assertEqual(comparison.calls, [(second, first)])
        self.assertEqual(trends.latest_execution.run_id, 2)

    def test_empty_one_and_only_failed_history_states(self) -> None:
        cases = (
            ((), CollectionTrendsState.UNAVAILABLE),
            ((trend_execution(1, score=80, size=10, hidden_count=2),), CollectionTrendsState.INSUFFICIENT_HISTORY),
            ((failed_execution(1),), CollectionTrendsState.EMPTY),
        )
        for executions, expected in cases:
            with self.subTest(expected=expected):
                trends = CollectionTrendsPresentationService(
                    RecordingHistory(executions),
                    RecordingComparison(),
                    CollectionTrendsViewModelBuilder(),
                ).latest_trends()
                self.assertIs(trends.state, expected)

    def test_history_and_comparison_failures_propagate(self) -> None:
        failure = RuntimeError("history failed")

        class BrokenHistory:
            def recent_executions(self, limit):
                raise failure

        service = CollectionTrendsPresentationService(
            BrokenHistory(),
            RecordingComparison(),
            CollectionTrendsViewModelBuilder(),
        )
        with self.assertRaises(RuntimeError) as raised:
            service.latest_trends()
        self.assertIs(raised.exception, failure)


class CollectionTrendsRendererAndExplorerTestCase(unittest.TestCase):
    def test_renderer_formats_values_deltas_timestamps_and_missing_values(self) -> None:
        trends = build_trends(
            trend_execution(2, score=82, size=12, hidden_count=None),
            trend_execution(1, score=80, size=10, hidden_count=2),
        )

        rendered = DesktopCollectionTrendsRenderer().render(trends)

        self.assertIn("01 Jul 2026", rendered.comparison)
        self.assertIn("02 Jul 2026", rendered.comparison)
        self.assertEqual(rendered.metrics[0].heading, "Collection size")
        self.assertIn("10 → 12", rendered.metrics[0].body)
        self.assertIn("Change: +2", rendered.metrics[0].body)
        hidden = next(row for row in rendered.metrics if row.metric_id == "hidden_gems.candidate_count")
        self.assertIn("2 → Unavailable", hidden.body)
        self.assertIn("No Longer Available", hidden.body)

    def test_insufficient_and_unavailable_states_render_clear_messages(self) -> None:
        renderer = DesktopCollectionTrendsRenderer()
        unavailable = renderer.render(CollectionTrendsViewModel.unavailable())
        one = trend_execution(1, score=80, size=10, hidden_count=2)
        insufficient = renderer.render(
            CollectionTrendsViewModelBuilder().build((one,), None, history_exists=True)
        )

        self.assertIn("No intelligence history", unavailable.headline)
        self.assertIn("Insufficient history", insufficient.headline)
        self.assertTrue(insufficient.comparison)

    def test_trends_is_fourth_and_explorer_queries_once_during_open(self) -> None:
        previous = trend_execution(1, score=80, size=10, hidden_count=2)
        latest = trend_execution(2, score=82, size=12, hidden_count=3)
        history = RecordingHistory((latest, previous))
        trends_service = CollectionTrendsPresentationService(
            history,
            RecordingComparison(),
            CollectionTrendsViewModelBuilder(),
        )
        homepage = trends_homepage(2)
        service = CollectionExplorerPresentationService(
            CollectionHealthPresentationService(CollectionHealthDetailViewModelBuilder()),
            HiddenGemsPresentationService(HiddenGemsDetailViewModelBuilder()),
            CollectionExplorerViewModelBuilder(),
            collection_trends=trends_service,
        )

        rendered = DesktopCollectionExplorerController(
            service,
            DesktopCollectionExplorerRenderer(),
        ).open(homepage)

        self.assertEqual(history.limits, [5])
        self.assertEqual(
            tuple(section.destination for section in rendered.sections),
            tuple(CollectionExplorerDestination),
        )
        self.assertIs(
            rendered.sections[3].destination,
            CollectionExplorerDestination.COLLECTION_TRENDS,
        )
        self.assertIs(rendered.selected_destination, CollectionExplorerDestination.OVERVIEW)
        self.assertIn("Collection size", rendered.sections[3].body)

        for _ in range(3):
            for destination in CollectionExplorerDestination:
                next(
                    section
                    for section in rendered.sections
                    if section.destination is destination
                )
        self.assertEqual(history.limits, [5])

    def test_trends_failure_propagates_to_existing_explorer_error_boundary(self) -> None:
        class BrokenTrends:
            def latest_trends(self):
                raise RuntimeError("trends failed")

        latest = trend_execution(1, score=80, size=10, hidden_count=2)
        service = CollectionExplorerPresentationService(
            CollectionHealthPresentationService(CollectionHealthDetailViewModelBuilder()),
            HiddenGemsPresentationService(HiddenGemsDetailViewModelBuilder()),
            CollectionExplorerViewModelBuilder(),
            collection_trends=BrokenTrends(),
        )
        with self.assertRaisesRegex(RuntimeError, "trends failed"):
            service.explorer_for_homepage(trends_homepage(1))

    def test_trends_layers_have_no_persistence_sqlite_or_engine_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = (
            root / "src/dip/experience/collection_trends/models.py",
            root / "src/dip/experience/collection_trends/builder.py",
            root / "src/dip/app/collection_trends_presentation.py",
            root / "src/dip/experience/desktop/collection_trends_renderer.py",
        )
        for path in files:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("dip.persistence", source)
            self.assertNotIn("sqlite3", source)
            self.assertNotIn("IntelligenceEngine", source)
            self.assertNotIn("execute(", source)
            self.assertNotIn("commit(", source)


class RecordingHistory:
    def __init__(self, executions):
        self.executions = tuple(executions)
        self.limits = []

    def recent_executions(self, limit):
        self.limits.append(limit)
        return self.executions[:limit]


class RecordingComparison:
    def __init__(self):
        self.calls = []

    def compare(self, current, previous):
        self.calls.append((current, previous))
        return ComparisonEngine().compare(current, previous)


def build_trends(latest, previous):
    return CollectionTrendsViewModelBuilder().build(
        (latest, previous),
        ComparisonEngine().compare(latest, previous),
        history_exists=True,
    )


def trend_execution(
    run_id,
    *,
    score,
    size,
    hidden_count,
    components=(81, 82, 83, 84),
):
    records = (
        IntelligenceHistoryRecord(
            record_id=run_id * 10 + 1,
            run_id=run_id,
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Collection Health result.",
            metrics={
                "collection_release_count": size,
                **({} if score is None else {"overall_health_score": score}),
                "component_scores": dict(
                    zip(
                        (
                            "metadata_completeness",
                            "marketplace_coverage",
                            "demand_strength",
                            "valuation_coverage",
                        ),
                        components,
                        strict=True,
                    )
                ),
                "strengths": (),
                "improvement_opportunities": (),
            },
        ),
        IntelligenceHistoryRecord(
            record_id=run_id * 10 + 2,
            run_id=run_id,
            module_id="hidden_gems",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Hidden Gems result.",
            metrics={
                "collection_release_count": size,
                **({} if hidden_count is None else {"candidate_count": hidden_count}),
                "ranked_candidates": (),
            },
        ),
    )
    return HistoricalIntelligenceExecution(
        IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=datetime(2026, 7, run_id, 10, tzinfo=timezone.utc),
            engine_version="1.0",
            result_count=len(records),
        ),
        records,
    )


def failed_execution(run_id):
    record = IntelligenceHistoryRecord(
        record_id=run_id * 10 + 1,
        run_id=run_id,
        module_id="collection_health",
        module_version="1.0",
        status=IntelligenceStatus.FAILED,
        summary="Failed.",
    )
    return HistoricalIntelligenceExecution(
        IntelligenceHistoryRun(
            run_id=run_id,
            executed_at=datetime(2026, 7, run_id, 10, tzinfo=timezone.utc),
            engine_version="1.0",
            result_count=1,
        ),
        (record,),
    )


def trends_homepage(run_id):
    return DashboardHomepageViewModelBuilder().build(
        dashboard_execution(
            run_id,
            health_record(run_id),
            hidden_record(run_id, candidates=(candidate(run_id),)),
        )
    )


if __name__ == "__main__":
    unittest.main()
