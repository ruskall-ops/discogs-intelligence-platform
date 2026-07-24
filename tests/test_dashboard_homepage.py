from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import unittest

from dip.app import HistoricalIntelligenceExecution
from dip.comparison import ComparisonEngine
from dip.experience.comparison import ComparisonViewModelBuilder, ModuleComparisonState
from dip.experience.dashboard import (
    DashboardChangeSummaryViewModel,
    DashboardCollectionHealthViewModel,
    DashboardCollectionOverviewViewModel,
    DashboardExecutionViewModel,
    DashboardHiddenGemsViewModel,
    DashboardHomepageConsistencyError,
    DashboardHomepageViewModel,
    DashboardHomepageViewModelBuilder,
    DashboardSectionId,
    DashboardSectionState,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence.modules.hidden_gems import HiddenGemCandidate
from dip.intelligence_history import IntelligenceHistoryRecord, IntelligenceHistoryRun


class DashboardHomepageBuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = DashboardHomepageViewModelBuilder()

    def test_no_history_has_explicit_empty_and_unavailable_states(self) -> None:
        homepage = self.builder.build(None)

        self.assertEqual(
            tuple(section.section_id for section in homepage.sections),
            tuple(DashboardSectionId),
        )
        self.assertIs(
            homepage.section_for("collection_overview").state,
            DashboardSectionState.EMPTY,
        )
        self.assertIs(
            homepage.section_for("collection_health").state,
            DashboardSectionState.UNAVAILABLE,
        )
        self.assertIs(
            homepage.section_for("hidden_gems").state,
            DashboardSectionState.UNAVAILABLE,
        )
        self.assertIs(
            homepage.section_for("what_changed").state,
            DashboardSectionState.INSUFFICIENT_HISTORY,
        )
        self.assertIs(
            homepage.section_for("latest_execution").state,
            DashboardSectionState.EMPTY,
        )

    def test_one_execution_uses_existing_module_values_without_recalculation(self) -> None:
        latest = execution(
            1,
            health_record(1, score=47.8, collection_size=12),
            hidden_record(1, candidates=(candidate(7, 91.0),)),
            engine_version="0.2",
        )

        homepage = self.builder.build(latest)
        overview = homepage.section_for(DashboardSectionId.COLLECTION_OVERVIEW)
        health = homepage.section_for(DashboardSectionId.COLLECTION_HEALTH)
        hidden = homepage.section_for(DashboardSectionId.HIDDEN_GEMS)
        changes = homepage.section_for(DashboardSectionId.WHAT_CHANGED)
        latest_section = homepage.section_for(DashboardSectionId.LATEST_EXECUTION)

        self.assertIsInstance(overview, DashboardCollectionOverviewViewModel)
        self.assertEqual(overview.collection_size, 12)
        self.assertEqual(overview.completed_module_count, 2)
        self.assertIs(overview.current_status, IntelligenceStatus.COMPLETED)
        self.assertIsInstance(health, DashboardCollectionHealthViewModel)
        self.assertEqual(health.card.headline_score, 47.8)
        self.assertIs(health.state, DashboardSectionState.AVAILABLE)
        self.assertIsInstance(hidden, DashboardHiddenGemsViewModel)
        self.assertEqual(hidden.card.total_hidden_gems, 1)
        self.assertEqual(hidden.preview[0].release_id, 7)
        self.assertIs(changes.state, DashboardSectionState.INSUFFICIENT_HISTORY)
        self.assertIsInstance(latest_section, DashboardExecutionViewModel)
        self.assertEqual(latest_section.module_count, 2)
        self.assertEqual(latest_section.engine_version, "0.2")
        self.assertTrue(latest_section.successful)

    def test_absent_modules_remain_independently_unavailable(self) -> None:
        homepage = self.builder.build(execution(1))

        self.assertIs(
            homepage.section_for("collection_health").state,
            DashboardSectionState.UNAVAILABLE,
        )
        self.assertIs(
            homepage.section_for("hidden_gems").state,
            DashboardSectionState.UNAVAILABLE,
        )
        self.assertIs(
            homepage.section_for("collection_overview").state,
            DashboardSectionState.AVAILABLE,
        )

    def test_unavailable_and_failed_collection_health_are_typed(self) -> None:
        absent = self.builder.build(execution(1)).section_for("collection_health")
        failed = self.builder.build(
            execution(
                2,
                health_record(
                    2,
                    status=IntelligenceStatus.FAILED,
                    metrics={},
                ),
            )
        ).section_for("collection_health")

        self.assertIs(absent.state, DashboardSectionState.UNAVAILABLE)
        self.assertIs(failed.state, DashboardSectionState.ERROR)
        self.assertIsNone(failed.card.headline_score)

    def test_no_hidden_gems_is_an_explicit_empty_result(self) -> None:
        section = self.builder.build(
            execution(1, hidden_record(1, candidates=()))
        ).section_for("hidden_gems")

        self.assertIs(section.state, DashboardSectionState.EMPTY)
        self.assertEqual(section.card.total_hidden_gems, 0)
        self.assertEqual(section.preview, ())

    def test_hidden_gems_preview_is_bounded_and_preserves_ranked_order(self) -> None:
        candidates = tuple(candidate(index, 100.0 - index) for index in range(1, 6))
        section = self.builder.build(
            execution(1, hidden_record(1, candidates=candidates))
        ).section_for("hidden_gems")

        self.assertEqual(section.preview_limit, 3)
        self.assertEqual(
            tuple(release.release_id for release in section.preview),
            (1, 2, 3),
        )
        self.assertTrue(all(type(release.release_id) is int for release in section.preview))

    def test_two_identical_executions_have_an_unchanged_summary(self) -> None:
        previous = execution(1, health_record(1, score=80.0))
        current = execution(2, health_record(2, score=80.0))

        section = self.builder.build(
            current,
            comparison_view_model(current, previous),
        ).section_for("what_changed")

        self.assertIs(section.state, DashboardSectionState.AVAILABLE)
        self.assertFalse(section.has_changes)
        self.assertEqual(section.unchanged_module_count, 1)
        self.assertEqual(section.changed_modules, ())

    def test_changed_added_and_removed_modules_preserve_comparison_order(self) -> None:
        previous = execution(
            1,
            health_record(1, score=80.0),
            generic_record(1, "removed_module"),
        )
        current = execution(
            2,
            health_record(2, score=82.0),
            generic_record(2, "added_module"),
        )

        section = self.builder.build(
            current,
            comparison_view_model(current, previous),
        ).section_for("what_changed")

        self.assertTrue(section.has_changes)
        self.assertEqual(section.changed_module_count, 1)
        self.assertEqual(section.added_module_count, 1)
        self.assertEqual(section.removed_module_count, 1)
        self.assertEqual(
            tuple(module.module_id for module in section.changed_modules),
            ("collection_health", "added_module", "removed_module"),
        )
        self.assertEqual(
            tuple(module.state for module in section.changed_modules),
            (
                ModuleComparisonState.CHANGED,
                ModuleComparisonState.ADDED,
                ModuleComparisonState.REMOVED,
            ),
        )

    def test_comparison_for_another_latest_run_is_rejected(self) -> None:
        previous = execution(1, health_record(1))
        current = execution(2, health_record(2))

        with self.assertRaisesRegex(
            DashboardHomepageConsistencyError,
            "latest comparison",
        ):
            self.builder.build(
                execution(3, health_record(3)),
                comparison_view_model(current, previous),
            )


class DashboardHomepageModelTestCase(unittest.TestCase):
    def test_loading_factory_uses_typed_loading_states(self) -> None:
        homepage = DashboardHomepageViewModel.loading()

        self.assertTrue(
            all(
                section.state is DashboardSectionState.LOADING
                for section in homepage.sections
            )
        )

    def test_homepage_and_nested_sections_are_frozen(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(None)

        with self.assertRaises(FrozenInstanceError):
            homepage.sections = ()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            homepage.sections[0].summary = "Changed"  # type: ignore[misc]

    def test_section_order_is_an_invariant(self) -> None:
        sections = DashboardHomepageViewModelBuilder().build(None).sections

        with self.assertRaisesRegex(
            DashboardHomepageConsistencyError,
            "documented order",
        ):
            DashboardHomepageViewModel(sections=(sections[1], sections[0], *sections[2:]))

    def test_change_counts_must_match_supplied_modules(self) -> None:
        previous = execution(1, health_record(1, score=80.0))
        current = execution(2, health_record(2, score=82.0))
        section = DashboardHomepageViewModelBuilder().build(
            current,
            comparison_view_model(current, previous),
        ).section_for("what_changed")

        with self.assertRaisesRegex(
            DashboardHomepageConsistencyError,
            "entries",
        ):
            replace(section, changed_modules=())

    def test_malformed_hidden_gems_preview_is_rejected(self) -> None:
        section = DashboardHomepageViewModelBuilder().build(
            execution(
                1,
                hidden_record(1, candidates=(candidate(1), candidate(2))),
            )
        ).section_for("hidden_gems")

        with self.assertRaisesRegex(
            DashboardHomepageConsistencyError,
            "ranked candidate order",
        ):
            replace(section, preview=tuple(reversed(section.preview)))

    def test_hidden_gems_candidate_count_must_match_ranked_candidates(self) -> None:
        section = DashboardHomepageViewModelBuilder().build(
            execution(1, hidden_record(1, candidates=(candidate(1),)))
        ).section_for("hidden_gems")

        with self.assertRaisesRegex(
            DashboardHomepageConsistencyError,
            "candidate count",
        ):
            replace(section, card=replace(section.card, total_hidden_gems=2))


def execution(
    run_id: int,
    *records: IntelligenceHistoryRecord,
    engine_version: str | None = "engine-1",
) -> HistoricalIntelligenceExecution:
    run = IntelligenceHistoryRun(
        run_id=run_id,
        executed_at=datetime(2026, 7, run_id, 10, 0, tzinfo=timezone.utc),
        engine_version=engine_version,
        result_count=len(records),
    )
    return HistoricalIntelligenceExecution(run=run, records=records)


def health_record(
    run_id: int,
    *,
    score: float = 80.0,
    collection_size: int = 10,
    status: IntelligenceStatus = IntelligenceStatus.COMPLETED,
    metrics=None,
) -> IntelligenceHistoryRecord:
    health_metrics = {
        "overall_health_score": score,
        "component_scores": {
            "metadata_completeness": 81.0,
            "marketplace_coverage": 82.0,
            "demand_strength": 83.0,
            "valuation_coverage": 84.0,
        },
        "collection_release_count": collection_size,
        "strengths": ("Existing strength",),
        "improvement_opportunities": (),
    }
    return record(
        run_id,
        "collection_health",
        status=status,
        metrics=health_metrics if metrics is None else metrics,
    )


def hidden_record(
    run_id: int,
    *,
    candidates: tuple[HiddenGemCandidate, ...],
) -> IntelligenceHistoryRecord:
    return record(
        run_id,
        "hidden_gems",
        metrics={
            "candidate_count": len(candidates),
            "ranked_candidates": candidates,
            "collection_release_count": 10,
        },
    )


def generic_record(run_id: int, module_id: str) -> IntelligenceHistoryRecord:
    return record(run_id, module_id, metrics={"value": 1})


def record(
    run_id: int,
    module_id: str,
    *,
    status: IntelligenceStatus = IntelligenceStatus.COMPLETED,
    metrics=None,
) -> IntelligenceHistoryRecord:
    offset = {
        "collection_health": 1,
        "hidden_gems": 2,
        "added_module": 3,
        "removed_module": 4,
    }.get(module_id, 9)
    return IntelligenceHistoryRecord(
        record_id=run_id * 10 + offset,
        run_id=run_id,
        module_id=module_id,
        module_version="1.0",
        status=status,
        summary=f"{module_id} result.",
        metrics={} if metrics is None else metrics,
    )


def candidate(
    release_id: int,
    score: float = 90.0,
) -> HiddenGemCandidate:
    return HiddenGemCandidate(
        release_id=release_id,
        artist=f"Artist {release_id}",
        title=f"Title {release_id}",
        hidden_gem_score=score,
        evidence=(f"Evidence {release_id}",),
        supporting_metrics={},
        factor_scores={},
    )


def comparison_view_model(current, previous):
    comparison = ComparisonEngine().compare(current, previous)
    return ComparisonViewModelBuilder().build(comparison)


if __name__ == "__main__":
    unittest.main()
