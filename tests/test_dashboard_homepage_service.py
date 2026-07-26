from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from dip.app import (
    CollectionIntelligencePresentationService,
    ComparisonHistoryUnavailableError,
    DashboardHomepageService,
)
from dip.app.intelligence_history import IntelligenceHistoryQueryService
from dip.experience.dashboard import (
    DashboardHomepageViewModelBuilder,
    DashboardSectionState,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)
from dip.persistence.sqlite import Database, SQLiteIntelligenceHistoryRepository

from tests.test_dashboard_homepage import (
    comparison_view_model,
    execution,
    health_record,
)


class _HistoryQueries:
    def __init__(self, latest) -> None:
        self.latest = latest
        self.calls = 0

    def latest_execution(self):
        self.calls += 1
        return self.latest


class _ComparisonPresentation:
    def __init__(self, view_model=None, error: Exception | None = None) -> None:
        self.view_model = view_model
        self.error = error
        self.calls = 0

    def latest_view_model(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.view_model


class DashboardHomepageServiceTestCase(unittest.TestCase):
    def test_empty_history_does_not_request_a_comparison(self) -> None:
        history = _HistoryQueries(None)
        comparisons = _ComparisonPresentation(error=AssertionError("not called"))
        service = DashboardHomepageService(
            history,
            comparisons,
            DashboardHomepageViewModelBuilder(),
        )

        homepage = service.homepage()

        self.assertEqual(history.calls, 1)
        self.assertEqual(comparisons.calls, 0)
        self.assertIs(
            homepage.section_for("collection_overview").state,
            DashboardSectionState.EMPTY,
        )

    def test_one_execution_degrades_expected_comparison_availability(self) -> None:
        latest = execution(1, health_record(1))
        comparisons = _ComparisonPresentation(
            error=ComparisonHistoryUnavailableError("one execution")
        )
        service = DashboardHomepageService(
            _HistoryQueries(latest),
            comparisons,
            DashboardHomepageViewModelBuilder(),
        )

        homepage = service.homepage()

        self.assertEqual(comparisons.calls, 1)
        self.assertIs(
            homepage.section_for("what_changed").state,
            DashboardSectionState.INSUFFICIENT_HISTORY,
        )
        self.assertIs(
            homepage.section_for("collection_health").state,
            DashboardSectionState.AVAILABLE,
        )

    def test_two_executions_coordinate_existing_comparison_view_model(self) -> None:
        previous = execution(1, health_record(1, score=80.0))
        current = execution(2, health_record(2, score=82.0))
        comparisons = _ComparisonPresentation(
            comparison_view_model(current, previous)
        )
        service = DashboardHomepageService(
            _HistoryQueries(current),
            comparisons,
            DashboardHomepageViewModelBuilder(),
        )

        homepage = service.homepage()

        changes = homepage.section_for("what_changed")
        self.assertEqual(comparisons.calls, 1)
        self.assertTrue(changes.has_changes)
        self.assertEqual(changes.changed_module_count, 1)

    def test_unexpected_comparison_failure_propagates(self) -> None:
        failure = RuntimeError("programming defect")
        service = DashboardHomepageService(
            _HistoryQueries(execution(1, health_record(1))),
            _ComparisonPresentation(error=failure),
            DashboardHomepageViewModelBuilder(),
        )

        with self.assertRaises(RuntimeError) as raised:
            service.homepage()

        self.assertIs(raised.exception, failure)

    def test_unexpected_history_failure_propagates(self) -> None:
        class BrokenHistory:
            def latest_execution(self):
                raise ValueError("corrupt history")

        failure_service = DashboardHomepageService(
            BrokenHistory(),
            _ComparisonPresentation(),
            DashboardHomepageViewModelBuilder(),
        )

        with self.assertRaisesRegex(ValueError, "corrupt history"):
            failure_service.homepage()

    def test_real_history_with_skipped_module_builds_complete_homepage(self):
        temporary = tempfile.TemporaryDirectory()
        database = Database(Path(temporary.name) / "dashboard-history.db")
        try:
            repository = SQLiteIntelligenceHistoryRepository(database)
            executed_at = datetime(2026, 7, 26, 9, tzinfo=timezone.utc)
            run = IntelligenceHistoryRun(
                None,
                executed_at,
                "0.2",
                None,
                3,
            )
            records = (
                IntelligenceHistoryRecord(
                    None,
                    None,
                    "collection_health",
                    "1.0",
                    IntelligenceStatus.COMPLETED,
                    "Collection Health completed.",
                    metrics={
                        "overall_health_score": 80.0,
                        "component_scores": {
                            "metadata_completeness": 80.0,
                            "marketplace_coverage": 80.0,
                            "demand_strength": 80.0,
                            "valuation_coverage": 80.0,
                        },
                        "strengths": (),
                        "improvement_opportunities": (),
                        "collection_release_count": 4,
                    },
                ),
                IntelligenceHistoryRecord(
                    None,
                    None,
                    "hidden_gems",
                    "1.0",
                    IntelligenceStatus.COMPLETED,
                    "No candidates.",
                    metrics={
                        "candidate_count": 0,
                        "ranked_candidates": (),
                        "collection_release_count": 4,
                    },
                ),
                IntelligenceHistoryRecord(
                    None,
                    None,
                    "historical_intelligence",
                    "0.2",
                    IntelligenceStatus.SKIPPED,
                    "A predecessor is not yet available.",
                    metrics={"comparable_snapshot_count": 1},
                    evidence=("One canonical snapshot was available.",),
                    diagnostics=("Two snapshots are required.",),
                ),
            )
            repository.save_execution(run, records)
            queries = IntelligenceHistoryQueryService(repository)
            service = DashboardHomepageService(
                queries,
                _ComparisonPresentation(
                    error=ComparisonHistoryUnavailableError("one execution")
                ),
                DashboardHomepageViewModelBuilder(),
            )

            reconstructed = queries.latest_execution()
            homepage = service.homepage()

            self.assertEqual(len(reconstructed.records), 3)
            skipped = reconstructed.records[2]
            self.assertIs(skipped.status, IntelligenceStatus.SKIPPED)
            self.assertEqual(
                skipped.summary,
                "A predecessor is not yet available.",
            )
            self.assertEqual(
                skipped.evidence,
                ("One canonical snapshot was available.",),
            )
            self.assertIs(
                homepage.section_for("collection_health").state,
                DashboardSectionState.AVAILABLE,
            )
            self.assertIs(
                homepage.section_for("hidden_gems").state,
                DashboardSectionState.EMPTY,
            )
            overview = homepage.section_for("collection_overview")
            self.assertIs(
                overview.current_status,
                IntelligenceStatus.SKIPPED,
            )
            latest = homepage.section_for("latest_execution")
            self.assertIs(latest.state, DashboardSectionState.AVAILABLE)
            self.assertNotIn(
                "No completed intelligence execution",
                latest.summary,
            )
        finally:
            database.close()
            temporary.cleanup()


class CollectionIntelligencePresentationServiceTestCase(unittest.TestCase):
    def test_existing_collection_intelligence_boundaries_are_coordinated(self) -> None:
        calls = []
        context = object()
        execution_result = object()
        dashboard = object()

        class ContextFactory:
            def build(self):
                calls.append("context")
                return context

        class Engine:
            def execute(self, supplied_context):
                self.assert_context = supplied_context
                calls.append("engine")
                return execution_result

        class Presenter:
            def present(self, supplied_execution):
                self.assert_execution = supplied_execution
                calls.append("presenter")
                return dashboard

        engine = Engine()
        presenter = Presenter()
        service = CollectionIntelligencePresentationService(
            ContextFactory(),
            engine,
            presenter,
        )

        result = service.dashboard()

        self.assertIs(result, dashboard)
        self.assertIs(engine.assert_context, context)
        self.assertIs(presenter.assert_execution, execution_result)
        self.assertEqual(calls, ["context", "engine", "presenter"])


if __name__ == "__main__":
    unittest.main()
