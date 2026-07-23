from dataclasses import replace
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    MarketplaceScarcityExecutionService,
    MarketplaceScarcityPresentationService,
)
from dip.app.marketplace_scarcity import build_marketplace_scarcity_input
from dip.decision_intelligence import MarketplaceScarcityInput, MarketplaceScarcityModule, MarketplaceScarcityOutput
from dip.experience.desktop.collection_explorer_renderer import DesktopCollectionExplorerController
from dip.experience.desktop.marketplace_scarcity_renderer import DesktopMarketplaceScarcityRenderer
from dip.experience.explorer import CollectionExplorerDestination, CollectionExplorerViewModelBuilder
from dip.experience.marketplace_scarcity import MarketplaceScarcityDetailViewModelBuilder
from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceStatus
from dip.intelligence_history import dumps_intelligence_value, loads_intelligence_value
from tests.test_collection_explorer import available_homepage, health_service, hidden_service
from tests.test_marketplace_momentum_execution_service import source_bundle


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
        self.engine = IntelligenceEngine((MarketplaceScarcityModule(),))

    def execute(self, context):
        self.calls.append(context)
        return self.engine.execute(context)


class MarketplaceScarcityIntegrationTestCase(unittest.TestCase):
    def test_execution_presentation_renderer_and_history_round_trip(self):
        _, _, supply, activity, rare, lifecycle = source_bundle()
        providers = tuple(Provider(value) for value in (rare, lifecycle, activity, supply))
        engine = RecordingEngine()
        result = MarketplaceScarcityExecutionService(
            providers[0], providers[1], engine,
            marketplace_activity=providers[2], supply_changes=providers[3],
        ).execute()
        self.assertEqual(tuple(value.calls for value in providers), (1, 1, 1, 1))
        self.assertEqual(len(engine.calls), 1)
        self.assertIs(type(engine.calls[0].marketplace_scarcity_input), MarketplaceScarcityInput)
        output = result.metrics["output"]
        self.assertIs(type(output), MarketplaceScarcityOutput)
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        detail = MarketplaceScarcityPresentationService(
            MarketplaceScarcityDetailViewModelBuilder()
        ).detail_for_result(result)
        rendered = DesktopMarketplaceScarcityRenderer().render(detail)
        self.assertEqual(rendered.title, "Marketplace Scarcity")
        self.assertIn("Rule set: 1.0", rendered.context)
        self.assertIn("Observed Marketplace scarcity assessment", rendered.releases[0].body)

    def test_missing_duplicate_unsupported_and_incompatible_required_sources(self):
        _, _, _, _, rare, lifecycle = source_bundle()
        lifecycle_output = lifecycle.metrics["output"]
        incompatible = replace(lifecycle, metrics={"output": replace(
            lifecycle_output,
            snapshots=tuple(replace(value, snapshot_id=f"other-{index}") for index, value in enumerate(lifecycle_output.snapshots)),
        )})
        cases = (
            (rare,),
            (rare, rare, lifecycle),
            (replace(rare, module_version="2.0"), lifecycle),
            (rare, incompatible),
        )
        for values in cases:
            prepared = build_marketplace_scarcity_input(values)
            self.assertFalse(prepared.required_sources_compatible)
            result = MarketplaceScarcityModule().analyse(IntelligenceContext(marketplace_scarcity_input=prepared))
            self.assertIs(result.status, IntelligenceStatus.SKIPPED)

    def test_explorer_consumes_result_once_as_destination_thirteen(self):
        _, _, _, _, rare, lifecycle = source_bundle()
        result = MarketplaceScarcityModule().analyse(IntelligenceContext(
            marketplace_scarcity_input=build_marketplace_scarcity_input((rare, lifecycle))
        ))
        real = MarketplaceScarcityPresentationService(MarketplaceScarcityDetailViewModelBuilder())

        class Recording:
            def __init__(self):
                self.calls = []

            def detail_for_result(self, value):
                self.calls.append(value)
                return real.detail_for_result(value)

        scarcity = Recording()
        controller = DesktopCollectionExplorerController(CollectionExplorerPresentationService(
            health_service(), hidden_service(), CollectionExplorerViewModelBuilder(),
            marketplace_scarcity=scarcity,
        ))
        rendered = controller.open(available_homepage(), marketplace_scarcity_result=result)
        self.assertEqual(scarcity.calls, [result])
        self.assertEqual(len(rendered.sections), 14)
        self.assertIs(rendered.sections[12].destination, CollectionExplorerDestination.MARKETPLACE_SCARCITY)


if __name__ == "__main__":
    unittest.main()
