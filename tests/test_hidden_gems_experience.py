from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import math
import unittest

from dip.app import HiddenGemsPresentationService
from dip.experience.dashboard import (
    DashboardCardState,
    DashboardHiddenGemViewModel,
    DashboardHiddenGemsViewModel,
    DashboardHomepageViewModelBuilder,
    DashboardMetricValueViewModel,
    DashboardSectionState,
    HiddenGemsCardPresenter,
    HiddenGemsCardViewModel,
)
from dip.experience.hidden_gems import (
    HiddenGemMetricViewModel,
    HiddenGemReleaseViewModel,
    HiddenGemsDetailConsistencyError,
    HiddenGemsDetailState,
    HiddenGemsDetailViewModel,
    HiddenGemsDetailViewModelBuilder,
)
from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.intelligence.modules.hidden_gems import HiddenGemCandidate

from tests.test_dashboard_homepage import execution, hidden_record


SUPPORTING_ORDER = (
    "wants",
    "copies_for_sale",
    "demand_to_supply_ratio",
    "community_rating",
    "owned_quantity",
    "lowest_price",
    "wants_per_price_unit",
)
FACTOR_ORDER = (
    "demand",
    "scarcity",
    "community_rating",
    "collection_ownership",
    "price_efficiency",
)


class HiddenGemsDetailBuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = HiddenGemsDetailViewModelBuilder()

    def test_detail_preserves_full_ranked_list_beyond_homepage_preview(self) -> None:
        candidates = tuple(candidate(release_id) for release_id in range(1, 7))
        section = DashboardHomepageViewModelBuilder().build(
            execution(1, hidden_record(1, candidates=candidates))
        ).section_for("hidden_gems")

        detail = self.builder.build(section)

        self.assertEqual(len(section.preview), 3)
        self.assertEqual(len(section.card.top_gems), 5)
        self.assertEqual(
            tuple(item.release_id for item in detail.candidates),
            (1, 2, 3, 4, 5, 6),
        )
        self.assertEqual(tuple(item.rank for item in detail.candidates), tuple(range(1, 7)))
        self.assertEqual(detail.candidates[0].score, 89.0)
        self.assertIs(detail.state, HiddenGemsDetailState.AVAILABLE)

    def test_source_presentation_copies_score_and_metrics_in_canonical_order(self) -> None:
        source = candidate(8)
        card = HiddenGemsCardPresenter().present(
            IntelligenceResult(
                module_id="hidden_gems",
                status=IntelligenceStatus.COMPLETED,
                summary="One candidate.",
                metrics={"candidate_count": 1, "ranked_candidates": (source,)},
            )
        )

        presented = card.ranked_gems[0]
        self.assertEqual(presented.score, source.hidden_gem_score)
        self.assertEqual(
            tuple(metric.metric_id for metric in presented.supporting_metrics),
            SUPPORTING_ORDER,
        )
        self.assertEqual(
            tuple(metric.metric_id for metric in presented.factor_scores),
            FACTOR_ORDER,
        )
        self.assertEqual(
            tuple(metric.value for metric in presented.factor_scores),
            tuple(source.factor_scores[key] for key in FACTOR_ORDER),
        )

    def test_missing_optional_candidate_values_are_retained_as_partial(self) -> None:
        section = available_section(
            source_candidate(
                1,
                supporting_overrides={
                    "community_rating": None,
                    "lowest_price": None,
                },
                factor_overrides={
                    "community_rating": None,
                    "price_efficiency": None,
                },
            )
        )

        detail = self.builder.build(section)

        self.assertIs(detail.state, HiddenGemsDetailState.PARTIAL)
        self.assertEqual(len(detail.candidates), 1)
        self.assertIsNone(detail.candidates[0].supporting_metrics[3].value)
        self.assertIsNone(detail.candidates[0].factor_scores[2].value)

    def test_builder_neither_recalculates_scores_nor_reranks_candidates(self) -> None:
        lower_score = replace(source_candidate(1), score=12.3)
        higher_score = replace(source_candidate(2), score=99.9)

        detail = self.builder.build(available_section(lower_score, higher_score))

        self.assertEqual(
            tuple(candidate.release_id for candidate in detail.candidates),
            (1, 2),
        )
        self.assertEqual(
            tuple(candidate.score for candidate in detail.candidates),
            (12.3, 99.9),
        )

    def test_loading_empty_unavailable_and_error_states_are_explicit(self) -> None:
        loading = self.builder.build(
            DashboardHiddenGemsViewModel(
                state=DashboardSectionState.LOADING,
                card=None,
            )
        )
        empty = self.builder.build(empty_section())
        unavailable = self.builder.build(
            DashboardHomepageViewModelBuilder().build(None).section_for("hidden_gems")
        )
        error = self.builder.build(error_section())

        self.assertIs(loading.state, HiddenGemsDetailState.LOADING)
        self.assertIs(empty.state, HiddenGemsDetailState.EMPTY)
        self.assertEqual(empty.candidate_count, 0)
        self.assertIs(unavailable.state, HiddenGemsDetailState.UNAVAILABLE)
        self.assertIsNone(unavailable.candidate_count)
        self.assertIs(error.state, HiddenGemsDetailState.ERROR)
        self.assertEqual(error.diagnostics, ("Controlled failure.",))

    def test_reordered_metrics_are_rejected(self) -> None:
        section = available_section(source_candidate(1))
        candidate_view = section.card.ranked_gems[0]
        reordered = replace(
            candidate_view,
            supporting_metrics=tuple(reversed(candidate_view.supporting_metrics)),
        )

        with self.assertRaisesRegex(
            HiddenGemsDetailConsistencyError,
            "canonical module order",
        ):
            self.builder.build(
                replace(
                    section,
                    card=replace(section.card, ranked_gems=(reordered,)),
                    preview=(reordered,),
                )
            )


class HiddenGemsDetailModelTestCase(unittest.TestCase):
    def test_models_defensively_freeze_nested_collections(self) -> None:
        metrics = [HiddenGemMetricViewModel("wants", "Wants", 100)]
        evidence = ["Existing evidence."]
        candidates = [
            HiddenGemReleaseViewModel(
                rank=1,
                release_id=1,
                artist="Artist",
                title="Title",
                score=90,
                explanation="Existing explanation.",
                supporting_metrics=metrics,
                evidence=evidence,
            )
        ]
        detail = HiddenGemsDetailViewModel(
            state=HiddenGemsDetailState.AVAILABLE,
            summary="Prepared detail.",
            candidate_count=1,
            candidates=candidates,
        )

        metrics.clear()
        evidence.clear()
        candidates.clear()

        self.assertEqual(detail.candidates[0].evidence, ("Existing evidence.",))
        self.assertEqual(detail.candidates[0].supporting_metrics[0].value, 100.0)
        with self.assertRaises(FrozenInstanceError):
            detail.summary = "Changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            detail.candidates[0].score = 0  # type: ignore[misc]

    def test_duplicate_release_ids_and_noncontiguous_ranks_are_rejected(self) -> None:
        first = detail_candidate(1, rank=1)
        duplicate = detail_candidate(1, rank=2)
        wrong_rank = detail_candidate(2, rank=3)

        with self.assertRaisesRegex(HiddenGemsDetailConsistencyError, "unique"):
            HiddenGemsDetailViewModel(
                state=HiddenGemsDetailState.AVAILABLE,
                summary="Prepared detail.",
                candidate_count=2,
                candidates=(first, duplicate),
            )
        with self.assertRaisesRegex(HiddenGemsDetailConsistencyError, "contiguous"):
            HiddenGemsDetailViewModel(
                state=HiddenGemsDetailState.AVAILABLE,
                summary="Prepared detail.",
                candidate_count=2,
                candidates=(first, wrong_rank),
            )

    def test_contradictory_states_and_counts_are_rejected(self) -> None:
        candidate_view = detail_candidate(1)
        cases = (
            dict(
                state=HiddenGemsDetailState.LOADING,
                summary="Loading.",
                candidate_count=1,
            ),
            dict(
                state=HiddenGemsDetailState.EMPTY,
                summary="Empty.",
                candidate_count=1,
            ),
            dict(
                state=HiddenGemsDetailState.AVAILABLE,
                summary="Available.",
                candidate_count=2,
                candidates=(candidate_view,),
            ),
        )

        for values in cases:
            with self.subTest(values=values):
                with self.assertRaises(HiddenGemsDetailConsistencyError):
                    HiddenGemsDetailViewModel(**values)

    def test_invalid_numeric_values_are_rejected(self) -> None:
        for value in (True, -1, math.nan, math.inf):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    HiddenGemMetricViewModel("wants", "Wants", value)

        with self.assertRaisesRegex(ValueError, "factor score"):
            HiddenGemReleaseViewModel(
                rank=1,
                release_id=1,
                artist="Artist",
                title="Title",
                score=90,
                explanation="Existing explanation.",
                factor_scores=(
                    HiddenGemMetricViewModel("demand", "Demand", 101),
                ),
            )


class HiddenGemsPresentationServiceTestCase(unittest.TestCase):
    def test_service_builds_from_current_homepage_hidden_gems_section(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(1, hidden_record(1, candidates=(candidate(1),)))
        )
        service = HiddenGemsPresentationService(HiddenGemsDetailViewModelBuilder())

        detail = service.detail_for_homepage(homepage)

        self.assertEqual(detail.candidates[0].release_id, 1)

    def test_builder_failure_propagates(self) -> None:
        failure = RuntimeError("builder failure")

        class BrokenBuilder:
            def build(self, section):
                raise failure

        service = HiddenGemsPresentationService(BrokenBuilder())

        with self.assertRaises(RuntimeError) as raised:
            service.detail_for_homepage(DashboardHomepageViewModelBuilder().build(None))

        self.assertIs(raised.exception, failure)


def candidate(release_id: int) -> HiddenGemCandidate:
    return HiddenGemCandidate(
        release_id=release_id,
        artist=f"Artist {release_id}",
        title=f"Title {release_id}",
        hidden_gem_score=90.0 - release_id,
        evidence=(f"Evidence {release_id}.",),
        supporting_metrics={
            "wants": 200.0,
            "copies_for_sale": 2.0,
            "demand_to_supply_ratio": 100.0,
            "community_rating": 4.5,
            "owned_quantity": 1.0,
            "lowest_price": 10.0,
            "wants_per_price_unit": 20.0,
        },
        factor_scores={
            "demand": 100.0,
            "scarcity": 90.0,
            "community_rating": 90.0,
            "collection_ownership": 100.0,
            "price_efficiency": 87.0,
        },
    )


def source_candidate(
    release_id: int,
    *,
    supporting_overrides: dict[str, float | None] | None = None,
    factor_overrides: dict[str, float | None] | None = None,
) -> DashboardHiddenGemViewModel:
    source = candidate(release_id)
    supporting = dict(source.supporting_metrics)
    factors = dict(source.factor_scores)
    supporting.update(supporting_overrides or {})
    factors.update(factor_overrides or {})
    labels = {key: key.replace("_", " ").title() for key in (*SUPPORTING_ORDER, *FACTOR_ORDER)}
    return DashboardHiddenGemViewModel(
        release_id=source.release_id,
        artist=source.artist,
        title=source.title,
        score=source.hidden_gem_score,
        explanation="Existing module explanation.",
        evidence=source.evidence,
        supporting_metrics=tuple(
            DashboardMetricValueViewModel(key, labels[key], supporting[key])
            for key in SUPPORTING_ORDER
        ),
        factor_scores=tuple(
            DashboardMetricValueViewModel(key, labels[key], factors[key])
            for key in FACTOR_ORDER
        ),
    )


def available_section(
    *candidates: DashboardHiddenGemViewModel,
) -> DashboardHiddenGemsViewModel:
    return DashboardHiddenGemsViewModel(
        state=DashboardSectionState.AVAILABLE,
        card=HiddenGemsCardViewModel(
            module_id="hidden_gems",
            title="Hidden Gems",
            state=DashboardCardState.READY,
            total_hidden_gems=len(candidates),
            summary="Existing Hidden Gems summary.",
            top_gems=candidates[:5],
            ranked_gems=candidates,
        ),
        preview=candidates[:3],
    )


def empty_section() -> DashboardHiddenGemsViewModel:
    return DashboardHiddenGemsViewModel(
        state=DashboardSectionState.EMPTY,
        card=HiddenGemsCardViewModel(
            module_id="hidden_gems",
            title="Hidden Gems",
            state=DashboardCardState.READY,
            total_hidden_gems=0,
            summary="No Hidden Gems were found.",
        ),
    )


def error_section() -> DashboardHiddenGemsViewModel:
    return DashboardHiddenGemsViewModel(
        state=DashboardSectionState.ERROR,
        card=HiddenGemsCardViewModel(
            module_id="hidden_gems",
            title="Hidden Gems",
            state=DashboardCardState.FAILED,
            total_hidden_gems=None,
            summary="Hidden Gems failed.",
            diagnostics=("Controlled failure.",),
        ),
    )


def detail_candidate(release_id: int, *, rank: int = 1) -> HiddenGemReleaseViewModel:
    return HiddenGemReleaseViewModel(
        rank=rank,
        release_id=release_id,
        artist="Artist",
        title="Title",
        score=90,
        explanation="Existing explanation.",
    )


if __name__ == "__main__":
    unittest.main()
