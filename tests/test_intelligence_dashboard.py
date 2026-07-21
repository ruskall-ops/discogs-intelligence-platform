from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from dip.experience.dashboard import (
    CollectionHealthCardPresenter,
    DashboardCardState,
    IntelligenceDashboardPresenter,
)
from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceResult,
    IntelligenceStatus,
)
from dip.intelligence.modules import CollectionHealthModule


class CollectionHealthCardPresenterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.presenter = CollectionHealthCardPresenter()

    def test_completed_result_is_presented_without_recalculation(self) -> None:
        result = IntelligenceResult(
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Prepared Collection Health summary.",
            metrics={
                "overall_health_score": 47.8,
                "component_scores": {
                    "metadata_completeness": 11.1,
                    "marketplace_coverage": 22.2,
                    "demand_strength": 33.3,
                    "valuation_coverage": 44.4,
                },
                "strengths": ("Reliable strength",),
                "improvement_opportunities": ("Clear opportunity",),
            },
            evidence=("2/4 releases have usable demand evidence.",),
            diagnostics=("Marketplace coverage is incomplete.",),
        )

        card = self.presenter.present(result)

        self.assertEqual(card.state, DashboardCardState.READY)
        self.assertEqual(card.headline_score, 47.8)
        self.assertEqual(card.summary, result.summary)
        self.assertEqual(
            tuple(component.score for component in card.components),
            (11.1, 22.2, 33.3, 44.4),
        )
        self.assertEqual(card.strengths, ("Reliable strength",))
        self.assertEqual(
            card.improvement_opportunities,
            ("Clear opportunity",),
        )
        self.assertEqual(card.evidence, result.evidence)
        self.assertEqual(card.diagnostics, result.diagnostics)

    def test_skipped_result_is_safe_and_retains_guidance(self) -> None:
        result = CollectionHealthModule().analyse(IntelligenceContext())

        card = self.presenter.present(result)

        self.assertEqual(card.state, DashboardCardState.SKIPPED)
        self.assertEqual(card.headline_score, 0.0)
        self.assertIn("collection is empty", card.summary)
        self.assertEqual(len(card.components), 4)
        self.assertTrue(card.improvement_opportunities)
        self.assertIn("Analysis skipped safely", card.diagnostics[0])

    def test_failed_result_is_safe_and_does_not_expect_metrics(self) -> None:
        result = IntelligenceResult(
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.FAILED,
            summary="Collection Health could not complete its analysis.",
            diagnostics=("RuntimeError: controlled failure",),
        )

        card = self.presenter.present(result)

        self.assertEqual(card.state, DashboardCardState.FAILED)
        self.assertIsNone(card.headline_score)
        self.assertEqual(card.components, ())
        self.assertEqual(card.strengths, ())
        self.assertEqual(card.improvement_opportunities, ())
        self.assertEqual(card.diagnostics, result.diagnostics)

    def test_incomplete_completed_result_is_marked_incomplete(self) -> None:
        result = IntelligenceResult(
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Only partial card metrics are available.",
            metrics={
                "overall_health_score": "unknown",
                "component_scores": {
                    "metadata_completeness": 75.0,
                },
            },
            diagnostics=("Original diagnostic",),
        )

        card = self.presenter.present(result)

        self.assertEqual(card.state, DashboardCardState.INCOMPLETE)
        self.assertIsNone(card.headline_score)
        self.assertEqual(len(card.components), 1)
        self.assertEqual(card.diagnostics[0], "Original diagnostic")
        self.assertIn("result is incomplete", card.diagnostics[-1])

    def test_wrong_module_result_is_rejected(self) -> None:
        result = IntelligenceResult(
            module_id="another_module",
            status="completed",
            summary="Not Collection Health.",
        )

        with self.assertRaisesRegex(ValueError, "collection_health"):
            self.presenter.present(result)

    def test_card_view_model_is_read_only(self) -> None:
        result = CollectionHealthModule().analyse(IntelligenceContext())
        card = self.presenter.present(result)

        with self.assertRaises(FrozenInstanceError):
            card.summary = "Changed"  # type: ignore[misc]


class IntelligenceDashboardPresenterTestCase(unittest.TestCase):
    def test_dashboard_consumes_collection_health_engine_execution(self) -> None:
        execution = IntelligenceEngine([CollectionHealthModule()]).execute(
            IntelligenceContext()
        )

        dashboard = IntelligenceDashboardPresenter().present(execution)
        card = dashboard.card_for("collection_health")

        self.assertEqual(len(dashboard.cards), 3)
        self.assertIsNotNone(card)
        self.assertEqual(card.state, DashboardCardState.SKIPPED)

    def test_dashboard_ignores_unsupported_results_and_keeps_card_slots(self) -> None:
        unsupported = IntelligenceResult(
            module_id="future_module",
            status="completed",
            summary="Outside the current dashboard slice.",
        )

        dashboard = IntelligenceDashboardPresenter().present([unsupported])

        self.assertEqual(len(dashboard.cards), 3)
        self.assertTrue(
            all(
                card.state == DashboardCardState.UNAVAILABLE
                for card in dashboard.cards
            )
        )


if __name__ == "__main__":
    unittest.main()
