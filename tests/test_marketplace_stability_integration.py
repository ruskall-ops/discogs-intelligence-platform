from dataclasses import replace
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    MarketplaceStabilityExecutionService,
    MarketplaceStabilityPresentationService,
)
from dip.app.marketplace_stability import build_marketplace_stability_input
from dip.decision_intelligence import MarketplaceStabilityInput, MarketplaceStabilityModule, MarketplaceStabilityOutput
from dip.experience.desktop.marketplace_stability_renderer import DesktopMarketplaceStabilityRenderer
from dip.experience.desktop.collection_explorer_renderer import DesktopCollectionExplorerController
from dip.experience.explorer import CollectionExplorerDestination, CollectionExplorerViewModelBuilder
from dip.experience.marketplace_stability import MarketplaceStabilityDetailViewModelBuilder
from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceExecution, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from tests.test_marketplace_momentum_execution_service import source_bundle
from tests.test_collection_explorer import available_homepage, health_service, hidden_service


class Provider:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def execute(self):
        self.calls += 1
        return self.value


class RecordingEngine:
    def __init__(self):
        self.calls = []
        self.engine = IntelligenceEngine((MarketplaceStabilityModule(),))

    def execute(self, context):
        self.calls.append(context)
        return self.engine.execute(context)


class MarketplaceStabilityIntegrationTestCase(unittest.TestCase):
    def test_preparation_execution_presentation_and_rendering(self):
        _, price, supply, activity, rare, lifecycle = source_bundle()
        providers = tuple(Provider(value) for value in (activity, lifecycle, price, supply, rare))
        engine = RecordingEngine()
        service = MarketplaceStabilityExecutionService(
            providers[0], providers[1], engine,
            price_changes=providers[2], supply_changes=providers[3],
            rare_appearances=providers[4],
        )
        result = service.execute()
        self.assertEqual(tuple(value.calls for value in providers), (1, 1, 1, 1, 1))
        self.assertEqual(len(engine.calls), 1)
        self.assertIs(type(engine.calls[0].marketplace_stability_input), MarketplaceStabilityInput)
        self.assertIs(type(result.metrics["output"]), MarketplaceStabilityOutput)
        detail = MarketplaceStabilityPresentationService(
            MarketplaceStabilityDetailViewModelBuilder()
        ).detail_for_result(result)
        rendered = DesktopMarketplaceStabilityRenderer().render(detail)
        self.assertEqual(rendered.title, "Marketplace Stability")
        self.assertIn("Rule set: 1.0", rendered.context)
        self.assertIn("Price-change stability", rendered.releases[0].body)

    def test_missing_duplicate_unsupported_and_incompatible_sources_are_diagnostic(self):
        _, _, _, activity, _, lifecycle = source_bundle()
        lifecycle_output = lifecycle.metrics["output"]
        incompatible_lifecycle = replace(
            lifecycle,
            metrics={
                "output": replace(
                    lifecycle_output,
                    snapshots=tuple(
                        replace(value, snapshot_id=f"other-{index}")
                        for index, value in enumerate(lifecycle_output.snapshots)
                    ),
                )
            },
        )
        cases = (
            (activity,),
            (activity, activity, lifecycle),
            (replace(activity, module_version="2.0"), lifecycle),
            (
                activity,
                incompatible_lifecycle,
            ),
        )
        for values in cases:
            with self.subTest(values=len(values)):
                prepared = build_marketplace_stability_input(values)
                self.assertFalse(prepared.required_sources_compatible)
                result = MarketplaceStabilityModule().analyse(
                    IntelligenceContext(marketplace_stability_input=prepared)
                )
                self.assertIs(result.status, IntelligenceStatus.SKIPPED)

    def test_explorer_consumes_stability_once_as_destination_twelve(self):
        _, _, _, activity, _, lifecycle = source_bundle()
        supplied = build_marketplace_stability_input((activity, lifecycle))
        result = MarketplaceStabilityModule().analyse(
            IntelligenceContext(marketplace_stability_input=supplied)
        )
        real = MarketplaceStabilityPresentationService(
            MarketplaceStabilityDetailViewModelBuilder()
        )

        class Recording:
            def __init__(self):
                self.calls = []

            def detail_for_result(self, value):
                self.calls.append(value)
                return real.detail_for_result(value)

        stability = Recording()
        controller = DesktopCollectionExplorerController(
            CollectionExplorerPresentationService(
                health_service(), hidden_service(),
                CollectionExplorerViewModelBuilder(),
                marketplace_stability=stability,
            )
        )
        rendered = controller.open(
            available_homepage(), marketplace_stability_result=result
        )
        self.assertEqual(stability.calls, [result])
        self.assertEqual(len(rendered.sections), 13)
        self.assertIs(
            rendered.sections[11].destination,
            CollectionExplorerDestination.MARKETPLACE_STABILITY,
        )

    def test_typed_output_round_trips_through_existing_history_wire_format(self):
        _, _, _, activity, _, lifecycle = source_bundle()
        result = MarketplaceStabilityModule().analyse(
            IntelligenceContext(
                marketplace_stability_input=build_marketplace_stability_input(
                    (activity, lifecycle)
                )
            )
        )
        output = result.metrics["output"]
        self.assertEqual(
            loads_intelligence_value(dumps_intelligence_value(output)),
            output,
        )


if __name__ == "__main__":
    unittest.main()
