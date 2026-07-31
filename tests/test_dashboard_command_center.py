from dataclasses import FrozenInstanceError
import unittest

from dip.app import (
    DashboardIntegrationPresentationService,
    HistoryExplorerPresentationService,
    MarketplaceWorkspacePresentationService,
)
from dip.experience.dashboard import (
    DashboardCommandCardId,
    DashboardCommandCenterBuilder,
    DashboardHomepageViewModelBuilder,
    DashboardNavigationTarget,
)
from dip.experience.desktop.dashboard_command_center_renderer import (
    DesktopDashboardCommandCenterController,
)
from dip.experience.history_explorer import HistoryExplorerStateBuilder
from dip.experience.marketplace_workspace import MarketplaceWorkspaceStateBuilder
from tests.test_history_explorer import supplied_view_models
from tests.test_marketplace_workspace import queue
from tests.test_portfolio_workspace import presentation as portfolio_presentation, results


def service():
    return DashboardIntegrationPresentationService(
        portfolio_presentation(),
        MarketplaceWorkspacePresentationService(MarketplaceWorkspaceStateBuilder()),
        HistoryExplorerPresentationService(HistoryExplorerStateBuilder()),
        DashboardCommandCenterBuilder(),
    )


class DashboardIntegrationTestCase(unittest.TestCase):
    def test_model_creation_and_canonical_card_order_are_immutable(self):
        snapshots, changes, trends = supplied_view_models()
        dashboard = service().dashboard(
            DashboardHomepageViewModelBuilder().build(None),
            portfolio_results=results(),
            marketplace_queue=queue(),
            history_observations=snapshots,
            history_changes=changes,
            history_trends=trends,
        )
        self.assertEqual(
            tuple(card.card_id for card in dashboard.cards),
            tuple(DashboardCommandCardId),
        )
        with self.assertRaises(FrozenInstanceError):
            dashboard.cards = ()

    def test_builder_is_deterministic_and_copies_existing_summaries(self):
        snapshots, changes, trends = supplied_view_models()
        supplied = dict(
            portfolio_results=results(),
            marketplace_queue=queue(),
            history_observations=snapshots,
            history_changes=changes,
            history_trends=trends,
        )
        homepage = DashboardHomepageViewModelBuilder().build(None)
        first = service().dashboard(homepage, **supplied)
        second = service().dashboard(homepage, **supplied)
        self.assertEqual(first, second)
        cards = {card.card_id: card for card in first.cards}
        self.assertEqual(
            cards[DashboardCommandCardId.MARKETPLACE_HIGHLIGHTS].summary,
            "Not available in this release",
        )
        self.assertEqual(
            cards[DashboardCommandCardId.HISTORICAL_CHANGES].summary,
            "Not available in this release",
        )
        self.assertEqual(
            cards[DashboardCommandCardId.PORTFOLIO_HEALTH].title,
            "Collection Health",
        )
        self.assertFalse(
            cards[DashboardCommandCardId.MARKETPLACE_HIGHLIGHTS].actions[0].enabled
        )

    def test_renderer_preserves_summaries_and_navigation_actions(self):
        rendered = DesktopDashboardCommandCenterController(service()).open(
            DashboardHomepageViewModelBuilder().build(None),
            portfolio_results=results(),
            marketplace_queue=queue(),
        )
        self.assertEqual(len(rendered.cards), 8)
        actions = tuple(
            action.target for card in rendered.cards for action in card.actions
        )
        for target in (
            DashboardNavigationTarget.PORTFOLIO,
            DashboardNavigationTarget.PORTFOLIO_OPPORTUNITY_ALIGNMENT,
            DashboardNavigationTarget.COLLECTION_EXPLORER,
            DashboardNavigationTarget.HISTORICAL_INTELLIGENCE,
            DashboardNavigationTarget.MARKETPLACE_WORKSPACE,
            DashboardNavigationTarget.PORTFOLIO_HISTORY,
            DashboardNavigationTarget.PORTFOLIO_RESEARCH,
        ):
            self.assertIn(target, actions)

    def test_presentation_invokes_each_workspace_boundary_once(self):
        portfolio_state = portfolio_presentation().workspace(*results())
        marketplace_state = MarketplaceWorkspacePresentationService(
            MarketplaceWorkspaceStateBuilder()
        ).workspace(queue())
        history_state = HistoryExplorerStateBuilder().build()
        calls = []

        class Portfolio:
            def workspace(self, *values):
                calls.append(("portfolio", values))
                return portfolio_state

        class Marketplace:
            def workspace(self, values):
                calls.append(("marketplace", values))
                return marketplace_state

        class History:
            def explorer(self, observations, changes, trends):
                calls.append(("history", observations, changes, trends))
                return history_state

        presentation = DashboardIntegrationPresentationService(
            Portfolio(), Marketplace(), History(), DashboardCommandCenterBuilder()
        )
        presentation.dashboard(
            DashboardHomepageViewModelBuilder().build(None),
            portfolio_results=("a", "b", "c", "d"),
            marketplace_queue=("market",),
        )
        self.assertEqual(
            calls,
            [
                ("portfolio", ("a", "b", "c", "d")),
                ("marketplace", ("market",)),
                ("history", (), (), ()),
            ],
        )


if __name__ == "__main__":
    unittest.main()
