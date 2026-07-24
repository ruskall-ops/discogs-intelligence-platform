from dataclasses import FrozenInstanceError
import unittest

from dip.app import (
    PortfolioConcentrationPresentationService,
    PortfolioDistributionPresentationService,
    PortfolioOpportunityAlignmentPresentationService,
    PortfolioOverviewPresentationService,
    PortfolioWorkspacePresentationService,
)
from dip.experience.desktop.portfolio_workspace_renderer import (
    DesktopPortfolioWorkspaceController,
    DesktopPortfolioWorkspaceRenderer,
)
from dip.experience.portfolio_concentration import PortfolioConcentrationViewModelBuilder
from dip.experience.portfolio_distribution import PortfolioDistributionViewModelBuilder
from dip.experience.portfolio_opportunity_alignment import (
    PortfolioOpportunityAlignmentViewModelBuilder,
)
from dip.experience.portfolio_overview import PortfolioOverviewViewModelBuilder
from dip.experience.portfolio_workspace import (
    PortfolioWorkspaceAvailability,
    PortfolioWorkspaceDestination,
    PortfolioWorkspaceOverviewViewModel,
    PortfolioWorkspaceStateBuilder,
)
from tests.test_portfolio_opportunity_alignment import alignment, sources


def presentation():
    return PortfolioWorkspacePresentationService(
        PortfolioOverviewPresentationService(PortfolioOverviewViewModelBuilder()),
        PortfolioDistributionPresentationService(
            PortfolioDistributionViewModelBuilder()
        ),
        PortfolioConcentrationPresentationService(
            PortfolioConcentrationViewModelBuilder()
        ),
        PortfolioOpportunityAlignmentPresentationService(
            PortfolioOpportunityAlignmentViewModelBuilder()
        ),
        PortfolioWorkspaceStateBuilder(),
    )


def results():
    overview, distribution, concentration = sources()
    opportunity_alignment, _ = alignment()
    return overview, distribution, concentration, opportunity_alignment


class PortfolioWorkspaceTestCase(unittest.TestCase):
    def test_workspace_models_are_immutable_and_preserve_supplied_view_models(self):
        service = presentation()
        state = service.workspace(*results())
        self.assertIs(state.availability, PortfolioWorkspaceAvailability.AVAILABLE)
        self.assertIsInstance(state.overview, PortfolioWorkspaceOverviewViewModel)
        expected = (
            PortfolioWorkspaceDestination.OVERVIEW,
            PortfolioWorkspaceDestination.DISTRIBUTION,
            PortfolioWorkspaceDestination.CONCENTRATION,
            PortfolioWorkspaceDestination.OPPORTUNITY_ALIGNMENT,
            PortfolioWorkspaceDestination.HISTORY,
            PortfolioWorkspaceDestination.RESEARCH,
        )
        self.assertEqual(tuple(value.destination for value in state.navigation), expected)
        self.assertEqual(
            tuple(value.implemented for value in state.navigation),
            (True, False, False, False, False, False),
        )
        with self.assertRaises(FrozenInstanceError):
            state.current_destination = PortfolioWorkspaceDestination.HISTORY

    def test_builder_composition_and_navigation_are_deterministic(self):
        service = presentation()
        first = service.workspace(*results())
        second = service.workspace(*results())
        self.assertEqual(first, second)
        navigated = service.navigate(first, PortfolioWorkspaceDestination.HISTORY)
        self.assertIs(
            navigated.current_destination, PortfolioWorkspaceDestination.HISTORY
        )
        self.assertEqual(navigated.overview, first.overview)
        self.assertIs(first.current_destination, PortfolioWorkspaceDestination.OVERVIEW)
        with self.assertRaises(TypeError):
            service.navigate(first, "history")
        with self.assertRaises(TypeError):
            service.workspace(*results(), available=0)

    def test_presentation_reuses_each_existing_service_once(self):
        calls = []

        class Overview:
            def overview_for_result(self, value):
                calls.append(("overview", value))
                return PortfolioOverviewViewModelBuilder().build(None)

        class Distribution:
            def distribution_for_result(self, value):
                calls.append(("distribution", value))
                return PortfolioDistributionViewModelBuilder().build(None)

        class Concentration:
            def concentration_for_result(self, value):
                calls.append(("concentration", value))
                return PortfolioConcentrationViewModelBuilder().build(None)

        class Alignment:
            def alignment_for_result(self, value):
                calls.append(("alignment", value))
                return PortfolioOpportunityAlignmentViewModelBuilder().build(None)

        service = PortfolioWorkspacePresentationService(
            Overview(),
            Distribution(),
            Concentration(),
            Alignment(),
            PortfolioWorkspaceStateBuilder(),
        )
        state = service.workspace("one", "two", "three", "four")
        self.assertIs(state.availability, PortfolioWorkspaceAvailability.EMPTY)
        self.assertEqual(
            calls,
            [
                ("overview", "one"),
                ("distribution", "two"),
                ("concentration", "three"),
                ("alignment", "four"),
            ],
        )

    def test_renderer_unifies_existing_portfolio_presentations_on_overview(self):
        rendered = DesktopPortfolioWorkspaceController(
            presentation(), DesktopPortfolioWorkspaceRenderer()
        ).open(*results())
        self.assertEqual(rendered.heading, "Overview")
        for expected in (
            "Portfolio Overview",
            "Portfolio Distribution",
            "Portfolio Concentration",
            "Portfolio Opportunity Alignment",
            "Ownership and Marketplace intelligence coverage",
            "Artist distribution",
            "Normalized HHI",
            "Observed alignment",
        ):
            self.assertIn(expected, rendered.body)
        for forbidden in ("should buy", "recommend buying", "forecast"):
            self.assertNotIn(forbidden, rendered.body.lower())

    def test_placeholder_navigation_and_unavailable_state_are_explicit(self):
        controller = DesktopPortfolioWorkspaceController(presentation())
        opened = controller.open()
        self.assertIs(opened.availability, PortfolioWorkspaceAvailability.EMPTY)
        for destination in tuple(PortfolioWorkspaceDestination)[1:]:
            with self.subTest(destination=destination):
                rendered = controller.navigate(opened.state, destination)
                self.assertIs(rendered.current_destination, destination)
                self.assertIn("is not implemented in Portfolio Workspace 1.0", rendered.body)
        unavailable = controller.open(available=False)
        self.assertIs(
            unavailable.availability, PortfolioWorkspaceAvailability.UNAVAILABLE
        )
        self.assertEqual(unavailable.body, "Portfolio Workspace is unavailable.")


if __name__ == "__main__":
    unittest.main()
