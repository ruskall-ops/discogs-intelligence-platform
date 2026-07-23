from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    MarketplaceMomentumPresentationService,
)
from dip.app.marketplace_momentum import build_marketplace_momentum_input
from dip.decision_intelligence import (
    MarketplaceMomentumLifecycleFact,
    MarketplaceMomentumListingState,
    MarketplaceMomentumModule,
    MomentumAnalysisState,
)
from dip.experience.desktop.collection_explorer_renderer import (
    DesktopCollectionExplorerController,
)
from dip.experience.desktop.marketplace_momentum_renderer import (
    DesktopMarketplaceMomentumRenderer,
)
from dip.experience.dashboard import DashboardHomepageViewModel
from dip.experience.explorer import (
    CollectionExplorerDestination,
    CollectionExplorerState,
    CollectionExplorerViewModelBuilder,
)
from dip.experience.marketplace_momentum import (
    MarketplaceMomentumDetailConsistencyError,
    MarketplaceMomentumDetailState,
    MarketplaceMomentumDetailViewModelBuilder,
)
from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from tests.test_collection_explorer import (
    available_homepage,
    health_service,
    hidden_service,
)
from tests.test_marketplace_momentum_execution_service import source_bundle


class MarketplaceMomentumPresentationTestCase(unittest.TestCase):
    def test_builder_preserves_typed_values_order_context_and_provenance(self) -> None:
        result = momentum_result()
        output = result.metrics["output"]

        detail = MarketplaceMomentumDetailViewModelBuilder().build(result)

        self.assertIs(detail.state, MarketplaceMomentumDetailState.AVAILABLE)
        self.assertIs(detail.analysis_state, MomentumAnalysisState.COMPLETE)
        self.assertEqual(detail.rule_set_version, output.rule_set_version)
        self.assertEqual(
            (
                detail.activity_thresholds.low_maximum,
                detail.activity_thresholds.moderate_maximum,
            ),
            (
                output.activity_thresholds.low_maximum,
                output.activity_thresholds.moderate_maximum,
            ),
        )
        self.assertEqual(
            tuple(value.release_id for value in detail.releases),
            tuple(value.release_id for value in output.releases),
        )
        domain = output.releases[0]
        release = detail.releases[0]
        self.assertEqual(release.assessment, domain.assessment)
        self.assertEqual(release.price.net_price_direction, 1)
        self.assertEqual(release.supply.net_supply_pressure, 1)
        self.assertEqual(
            release.activity.total_activity_count,
            domain.components.activity.total_activity_count,
        )
        self.assertEqual(
            release.supporting_context.appearance.appearance_ratio,
            domain.supporting_context.appearance.appearance_ratio,
        )
        self.assertEqual(
            release.supporting_context.listing_persistence.listing_count,
            2,
        )
        self.assertEqual(
            tuple(value.module_id for value in detail.source_provenance),
            tuple(value.module_id for value in output.source_provenance),
        )
        with self.assertRaises(FrozenInstanceError):
            release.release_id = 2  # type: ignore[misc]

    def test_builder_maps_absence_insufficient_and_rejects_bad_contracts(self) -> None:
        builder = MarketplaceMomentumDetailViewModelBuilder()
        self.assertIs(
            builder.build(None).state,
            MarketplaceMomentumDetailState.UNAVAILABLE,
        )
        insufficient = MarketplaceMomentumModule().analyse(IntelligenceContext())
        self.assertIs(
            builder.build(insufficient).state,
            MarketplaceMomentumDetailState.INSUFFICIENT_DATA,
        )
        with self.assertRaisesRegex(
            MarketplaceMomentumDetailConsistencyError,
            "marketplace_momentum",
        ):
            builder.build(replace(momentum_result(), module_id="another_module"))
        with self.assertRaisesRegex(
            MarketplaceMomentumDetailConsistencyError,
            "typed output",
        ):
            builder.build(replace(momentum_result(), metrics={}))
        with self.assertRaisesRegex(
            MarketplaceMomentumDetailConsistencyError,
            "status contradicts",
        ):
            builder.build(
                replace(momentum_result(), status=IntelligenceStatus.SKIPPED)
            )


class MarketplaceMomentumRendererTestCase(unittest.TestCase):
    def test_renderer_exposes_components_context_provenance_and_reasons(self) -> None:
        detail = MarketplaceMomentumDetailViewModelBuilder().build(
            momentum_result()
        )

        rendered = DesktopMarketplaceMomentumRenderer().render(detail)
        body = rendered.releases[0].body

        self.assertIn("Release 1", rendered.releases[0].heading)
        self.assertIn("Positive observed momentum", body)
        self.assertIn("Evidence coverage: Complete", body)
        self.assertIn("Observed price direction: Positive", body)
        self.assertIn("Price increases observed: 1", body)
        self.assertIn("Net observed price direction: 1", body)
        self.assertIn("Observed supply pressure: Positive", body)
        self.assertIn("Supply decreases observed: 1", body)
        self.assertIn("Net observed supply pressure: 1", body)
        self.assertIn("Observed activity intensity: Moderate", body)
        self.assertIn("Total activity observed: 4", body)
        self.assertIn("Appearance observations: 2", body)
        self.assertIn("Listings observed: 2", body)
        self.assertIn("Assessment reasons: Aligned positive", body)
        self.assertIn("Rule set: 1.0", rendered.context)
        self.assertIn(
            "Source intelligence: price_changes",
            rendered.source_provenance,
        )

    def test_renderer_and_presentation_source_are_non_prescriptive_and_mapping_only(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        renderer = (
            root / "src/dip/experience/desktop/marketplace_momentum_renderer.py"
        ).read_text(encoding="utf-8").lower()
        builder = (
            root / "src/dip/experience/marketplace_momentum/builder.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "buy",
            "sell",
            "invest",
            "undervalued",
            "overvalued",
            "winner",
            "loser",
            "likely to rise",
            "likely to fall",
            "guaranteed",
            "opportunity",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, renderer)
        for forbidden in ("sorted(", "sum(", "Counter(", "assessment ="):
            self.assertNotIn(forbidden, builder)


class MarketplaceMomentumExplorerIntegrationTestCase(unittest.TestCase):
    def test_momentum_is_eleventh_and_consumes_one_already_produced_result(self) -> None:
        result = momentum_result()
        real = MarketplaceMomentumPresentationService(
            MarketplaceMomentumDetailViewModelBuilder()
        )

        class RecordingMomentumPresentation:
            def __init__(self) -> None:
                self.calls: list[IntelligenceResult | None] = []

            def detail_for_result(self, supplied):
                self.calls.append(supplied)
                return real.detail_for_result(supplied)

        momentum = RecordingMomentumPresentation()
        controller = explorer_controller(momentum)

        rendered = controller.open(
            available_homepage(),
            marketplace_momentum_result=result,
        )
        for _ in range(3):
            rendered.sections[10]

        self.assertEqual(momentum.calls, [result])
        self.assertEqual(len(rendered.sections), 13)
        self.assertIs(
            rendered.sections[10].destination,
            CollectionExplorerDestination.MARKETPLACE_MOMENTUM,
        )
        self.assertIn("Positive observed momentum", rendered.sections[10].body)
        self.assertIs(
            rendered.selected_destination,
            CollectionExplorerDestination.OVERVIEW,
        )

    def test_absent_result_is_unavailable_and_loading_does_not_consume_result(
        self,
    ) -> None:
        controller = explorer_controller()
        rendered = controller.open(available_homepage())
        self.assertIs(
            rendered.navigation[10].state,
            CollectionExplorerState.UNAVAILABLE,
        )
        self.assertIs(rendered.state, CollectionExplorerState.AVAILABLE)

        class ForbiddenMomentumPresentation:
            def detail_for_result(self, supplied):
                raise AssertionError("Loading Explorer must not consume Momentum.")

        loading = explorer_controller(ForbiddenMomentumPresentation()).open(
            DashboardHomepageViewModel.loading(),
            marketplace_momentum_result=momentum_result(),
        )
        self.assertIs(loading.state, CollectionExplorerState.LOADING)
        self.assertIs(
            loading.navigation[10].state,
            CollectionExplorerState.LOADING,
        )


def momentum_result() -> IntelligenceResult:
    _, price, supply, activity, rare, lifecycle = source_bundle()
    supplied = build_marketplace_momentum_input(
        (price, supply, activity, rare, lifecycle)
    )
    supplied = replace(
        supplied,
        lifecycle_facts=(
            MarketplaceMomentumLifecycleFact(
                1,
                "listing-active",
                MarketplaceMomentumListingState.ACTIVE,
                True,
            ),
            MarketplaceMomentumLifecycleFact(
                1,
                "listing-ended",
                MarketplaceMomentumListingState.ENDED,
                False,
            ),
        ),
    )
    return MarketplaceMomentumModule().analyse(
        IntelligenceContext(marketplace_momentum_input=supplied)
    )


def explorer_controller(
    momentum_presentation=None,
) -> DesktopCollectionExplorerController:
    presentation = CollectionExplorerPresentationService(
        health_service(),
        hidden_service(),
        CollectionExplorerViewModelBuilder(),
        marketplace_momentum=(
            momentum_presentation
            or MarketplaceMomentumPresentationService(
                MarketplaceMomentumDetailViewModelBuilder()
            )
        ),
    )
    return DesktopCollectionExplorerController(presentation)


if __name__ == "__main__":
    unittest.main()
