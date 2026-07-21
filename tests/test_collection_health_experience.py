from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import math
import unittest

from dip.app import CollectionHealthPresentationService
from dip.experience.collection_health import (
    CollectionHealthComponentViewModel,
    CollectionHealthDetailConsistencyError,
    CollectionHealthDetailState,
    CollectionHealthDetailViewModel,
    CollectionHealthDetailViewModelBuilder,
)
from dip.experience.dashboard import (
    CollectionHealthCardPresenter,
    DashboardCardState,
    DashboardCardViewModel,
    DashboardCollectionHealthViewModel,
    DashboardComponentScore,
    DashboardHomepageViewModelBuilder,
    DashboardSectionState,
)
from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus
from dip.intelligence.modules import CollectionHealthModule

from tests.test_dashboard_homepage import execution, health_record


class CollectionHealthDetailBuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = CollectionHealthDetailViewModelBuilder()

    def test_available_detail_preserves_all_existing_card_values(self) -> None:
        section = available_section(score=47.8)

        detail = self.builder.build(section)

        self.assertIs(detail.state, CollectionHealthDetailState.AVAILABLE)
        self.assertEqual(detail.overall_score, 47.8)
        self.assertEqual(detail.summary, section.card.summary)
        self.assertEqual(
            tuple(component.component_id for component in detail.components),
            (
                "metadata_completeness",
                "marketplace_coverage",
                "demand_strength",
                "valuation_coverage",
            ),
        )
        self.assertEqual(
            tuple(component.score for component in detail.components),
            (11.1, 22.2, 33.3, 44.4),
        )
        self.assertEqual(detail.strengths, section.card.strengths)
        self.assertEqual(
            detail.improvement_opportunities,
            section.card.improvement_opportunities,
        )
        self.assertEqual(detail.evidence, section.card.evidence)
        self.assertEqual(detail.diagnostics, section.card.diagnostics)

    def test_builder_does_not_recalculate_overall_score(self) -> None:
        detail = self.builder.build(available_section(score=12.3))

        self.assertEqual(detail.overall_score, 12.3)
        self.assertNotEqual(
            detail.overall_score,
            sum(component.score for component in detail.components) / 4,
        )

    def test_loading_state_contains_no_result_values(self) -> None:
        detail = self.builder.build(
            DashboardCollectionHealthViewModel(
                state=DashboardSectionState.LOADING,
                card=None,
            )
        )

        self.assertIs(detail.state, CollectionHealthDetailState.LOADING)
        self.assertIsNone(detail.overall_score)
        self.assertEqual(detail.components, ())

    def test_empty_collection_preserves_module_guidance(self) -> None:
        result = CollectionHealthModule().analyse(IntelligenceContext())
        card = CollectionHealthCardPresenter().present(result)
        section = DashboardCollectionHealthViewModel(
            state=DashboardSectionState.EMPTY,
            card=card,
        )

        detail = self.builder.build(section)

        self.assertIs(detail.state, CollectionHealthDetailState.EMPTY)
        self.assertEqual(detail.overall_score, 0.0)
        self.assertEqual(len(detail.components), 4)
        self.assertTrue(detail.improvement_opportunities)
        self.assertIn("collection is empty", detail.summary)

    def test_unavailable_state_is_explicit(self) -> None:
        section = DashboardCollectionHealthViewModel(
            state=DashboardSectionState.UNAVAILABLE,
            card=CollectionHealthCardPresenter().unavailable(),
        )

        detail = self.builder.build(section)

        self.assertIs(detail.state, CollectionHealthDetailState.UNAVAILABLE)
        self.assertIsNone(detail.overall_score)
        self.assertEqual(detail.components, ())

    def test_failed_and_incomplete_cards_map_to_error(self) -> None:
        presenter = CollectionHealthCardPresenter()
        failed_card = presenter.present(
            IntelligenceResult(
                module_id="collection_health",
                status=IntelligenceStatus.FAILED,
                summary="Collection Health failed.",
                diagnostics=("Controlled failure.",),
            )
        )
        incomplete_card = presenter.present(
            IntelligenceResult(
                module_id="collection_health",
                status=IntelligenceStatus.COMPLETED,
                summary="Collection Health is incomplete.",
                metrics={
                    "overall_health_score": 50.0,
                    "component_scores": {"metadata_completeness": 70.0},
                },
            )
        )

        failed = self.builder.build(
            DashboardCollectionHealthViewModel(
                state=DashboardSectionState.ERROR,
                card=failed_card,
            )
        )
        incomplete = self.builder.build(
            DashboardCollectionHealthViewModel(
                state=DashboardSectionState.ERROR,
                card=incomplete_card,
            )
        )

        self.assertIs(failed.state, CollectionHealthDetailState.ERROR)
        self.assertEqual(failed.diagnostics, ("Controlled failure.",))
        self.assertIs(incomplete.state, CollectionHealthDetailState.ERROR)
        self.assertEqual(incomplete.overall_score, 50.0)
        self.assertEqual(len(incomplete.components), 1)

    def test_reordered_available_components_are_rejected(self) -> None:
        section = available_section()
        reordered = replace(
            section.card,
            components=tuple(reversed(section.card.components)),
        )

        with self.assertRaisesRegex(
            CollectionHealthDetailConsistencyError,
            "canonical module order",
        ):
            self.builder.build(replace(section, card=reordered))


class CollectionHealthDetailModelTestCase(unittest.TestCase):
    def test_models_defensively_freeze_collections(self) -> None:
        components = [
            CollectionHealthComponentViewModel("metadata", "Metadata", 80)
        ]
        strengths = ["Existing strength"]

        detail = CollectionHealthDetailViewModel(
            state=CollectionHealthDetailState.AVAILABLE,
            summary="Prepared detail.",
            overall_score=80,
            components=components,
            strengths=strengths,
        )
        components.clear()
        strengths.clear()

        self.assertEqual(len(detail.components), 1)
        self.assertEqual(detail.strengths, ("Existing strength",))
        with self.assertRaises(FrozenInstanceError):
            detail.summary = "Changed"  # type: ignore[misc]

    def test_duplicate_components_are_rejected(self) -> None:
        component = CollectionHealthComponentViewModel("metadata", "Metadata", 80)

        with self.assertRaisesRegex(
            CollectionHealthDetailConsistencyError,
            "unique",
        ):
            CollectionHealthDetailViewModel(
                state=CollectionHealthDetailState.AVAILABLE,
                summary="Prepared detail.",
                overall_score=80,
                components=(component, component),
            )

    def test_invalid_scores_are_rejected(self) -> None:
        for value in (True, math.nan, math.inf, -1, 101):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    CollectionHealthComponentViewModel(
                        "metadata",
                        "Metadata",
                        value,
                    )

    def test_impossible_loading_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            CollectionHealthDetailConsistencyError,
            "loading",
        ):
            CollectionHealthDetailViewModel(
                state=CollectionHealthDetailState.LOADING,
                summary="Loading.",
                evidence=("Unexpected evidence.",),
            )


class CollectionHealthPresentationServiceTestCase(unittest.TestCase):
    def test_service_builds_from_the_homepage_collection_health_section(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(1, health_record(1, score=63.4))
        )
        service = CollectionHealthPresentationService(
            CollectionHealthDetailViewModelBuilder()
        )

        detail = service.detail_for_homepage(homepage)

        self.assertEqual(detail.overall_score, 63.4)
        self.assertIs(detail.state, CollectionHealthDetailState.AVAILABLE)

    def test_builder_failure_propagates(self) -> None:
        failure = RuntimeError("builder failure")

        class BrokenBuilder:
            def build(self, section):
                raise failure

        service = CollectionHealthPresentationService(BrokenBuilder())
        homepage = DashboardHomepageViewModelBuilder().build(None)

        with self.assertRaises(RuntimeError) as raised:
            service.detail_for_homepage(homepage)

        self.assertIs(raised.exception, failure)


def available_section(score: float = 47.8) -> DashboardCollectionHealthViewModel:
    return DashboardCollectionHealthViewModel(
        state=DashboardSectionState.AVAILABLE,
        card=DashboardCardViewModel(
            module_id="collection_health",
            title="Collection Health",
            state=DashboardCardState.READY,
            headline_label="Overall health score",
            headline_score=score,
            summary="Prepared Collection Health summary.",
            components=(
                DashboardComponentScore(
                    "metadata_completeness",
                    "Metadata completeness",
                    11.1,
                ),
                DashboardComponentScore(
                    "marketplace_coverage",
                    "Marketplace coverage",
                    22.2,
                ),
                DashboardComponentScore(
                    "demand_strength",
                    "Demand strength",
                    33.3,
                ),
                DashboardComponentScore(
                    "valuation_coverage",
                    "Valuation coverage",
                    44.4,
                ),
            ),
            strengths=("Core metadata is well populated.",),
            improvement_opportunities=("Refresh marketplace evidence.",),
            evidence=("10 collection releases were assessed.",),
            diagnostics=("Prepared context only.",),
        ),
    )


if __name__ == "__main__":
    unittest.main()
