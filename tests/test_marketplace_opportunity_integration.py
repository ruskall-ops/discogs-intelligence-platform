from dataclasses import replace
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    MarketplaceOpportunityExecutionService,
    MarketplaceOpportunityPresentationService,
)
from dip.app.marketplace_momentum import build_marketplace_momentum_input
from dip.app.marketplace_opportunity import build_marketplace_opportunity_input
from dip.app.marketplace_scarcity import build_marketplace_scarcity_input
from dip.app.marketplace_stability import build_marketplace_stability_input
from dip.decision_intelligence import (
    MarketplaceMomentumModule,
    MarketplaceOpportunityInput,
    MarketplaceOpportunityModule,
    MarketplaceOpportunityOutput,
    MarketplaceScarcityModule,
    MarketplaceStabilityModule,
)
from dip.experience.desktop.collection_explorer_renderer import DesktopCollectionExplorerController
from dip.experience.desktop.marketplace_opportunity_renderer import DesktopMarketplaceOpportunityRenderer
from dip.experience.explorer import CollectionExplorerDestination, CollectionExplorerViewModelBuilder
from dip.experience.marketplace_opportunity import MarketplaceOpportunityDetailViewModelBuilder
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
        self.engine = IntelligenceEngine((MarketplaceOpportunityModule(),))

    def execute(self, context):
        self.calls.append(context)
        return self.engine.execute(context)


def decision_results():
    _, price, supply, activity, rare, lifecycle = source_bundle()
    momentum = MarketplaceMomentumModule().analyse(IntelligenceContext(
        marketplace_momentum_input=build_marketplace_momentum_input((price, supply, activity, rare, lifecycle))
    ))
    stability = MarketplaceStabilityModule().analyse(IntelligenceContext(
        marketplace_stability_input=build_marketplace_stability_input((activity, lifecycle))
    ))
    scarcity = MarketplaceScarcityModule().analyse(IntelligenceContext(
        marketplace_scarcity_input=build_marketplace_scarcity_input((rare, lifecycle))
    ))
    return momentum, stability, scarcity


class MarketplaceOpportunityIntegrationTestCase(unittest.TestCase):
    def test_execution_presentation_renderer_and_history_round_trip(self):
        providers = tuple(Provider(value) for value in decision_results())
        engine = RecordingEngine()
        result = MarketplaceOpportunityExecutionService(*providers, engine).execute()
        self.assertEqual(tuple(value.calls for value in providers), (1, 1, 1))
        self.assertEqual(len(engine.calls), 1)
        self.assertIs(type(engine.calls[0].marketplace_opportunity_input), MarketplaceOpportunityInput)
        output = result.metrics["output"]
        self.assertIs(type(output), MarketplaceOpportunityOutput)
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(output)), output)
        detail = MarketplaceOpportunityPresentationService(
            MarketplaceOpportunityDetailViewModelBuilder()
        ).detail_for_result(result)
        rendered = DesktopMarketplaceOpportunityRenderer().render(detail)
        self.assertEqual(rendered.title, "Marketplace Opportunity")
        self.assertIn("Rule set: 1.0", rendered.context)
        self.assertIn("Momentum:", rendered.releases[0].body)

    def test_missing_duplicate_unsupported_and_incompatible_sources(self):
        momentum, stability, scarcity = decision_results()
        incompatible = replace(
            scarcity,
            metrics={"output": replace(
                scarcity.metrics["output"],
                source_provenance=tuple(
                    replace(value, history_snapshot_ids=("other-a", "other-b"))
                    if value.module_id == "rare_appearances" else value
                    for value in scarcity.metrics["output"].source_provenance
                ),
            )},
        )
        cases = (
            (momentum, stability),
            (momentum, momentum, stability, scarcity),
            (replace(momentum, module_version="2.0"), stability, scarcity),
            (momentum, stability, incompatible),
        )
        for values in cases:
            prepared = build_marketplace_opportunity_input(values)
            self.assertFalse(prepared.required_sources_compatible)
            result = MarketplaceOpportunityModule().analyse(
                IntelligenceContext(marketplace_opportunity_input=prepared)
            )
            self.assertIs(result.status, IntelligenceStatus.SKIPPED)

    def test_explorer_consumes_result_once_as_destination_fourteen(self):
        result = MarketplaceOpportunityModule().analyse(IntelligenceContext(
            marketplace_opportunity_input=build_marketplace_opportunity_input(decision_results())
        ))
        real = MarketplaceOpportunityPresentationService(MarketplaceOpportunityDetailViewModelBuilder())

        class Recording:
            def __init__(self):
                self.calls = []

            def detail_for_result(self, value):
                self.calls.append(value)
                return real.detail_for_result(value)

        opportunity = Recording()
        controller = DesktopCollectionExplorerController(CollectionExplorerPresentationService(
            health_service(), hidden_service(), CollectionExplorerViewModelBuilder(),
            marketplace_opportunity=opportunity,
        ))
        rendered = controller.open(available_homepage(), marketplace_opportunity_result=result)
        self.assertEqual(opportunity.calls, [result])
        self.assertEqual(len(rendered.sections), 14)
        self.assertIs(rendered.sections[13].destination, CollectionExplorerDestination.MARKETPLACE_OPPORTUNITY)


if __name__ == "__main__":
    unittest.main()

