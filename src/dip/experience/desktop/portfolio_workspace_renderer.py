"""Desktop rendering for immutable Portfolio Workspace state."""

from dataclasses import dataclass

from dip.experience.portfolio_workspace import (
    PortfolioWorkspaceAvailability,
    PortfolioWorkspaceDestination,
    PortfolioWorkspaceNavigationItem,
    PortfolioWorkspaceState,
)

from .portfolio_concentration_renderer import DesktopPortfolioConcentrationRenderer
from .portfolio_distribution_renderer import DesktopPortfolioDistributionRenderer
from .portfolio_opportunity_alignment_renderer import (
    DesktopPortfolioOpportunityAlignmentRenderer,
)
from .portfolio_overview_renderer import DesktopPortfolioOverviewRenderer


@dataclass(frozen=True)
class DesktopPortfolioWorkspaceView:
    title: str
    availability: PortfolioWorkspaceAvailability
    navigation: tuple[PortfolioWorkspaceNavigationItem, ...]
    current_destination: PortfolioWorkspaceDestination
    heading: str
    body: str
    state: PortfolioWorkspaceState


class DesktopPortfolioWorkspaceRenderer:
    def __init__(
        self,
        overview_renderer=None,
        distribution_renderer=None,
        concentration_renderer=None,
        opportunity_alignment_renderer=None,
    ):
        self._overview = overview_renderer or DesktopPortfolioOverviewRenderer()
        self._distribution = (
            distribution_renderer or DesktopPortfolioDistributionRenderer()
        )
        self._concentration = (
            concentration_renderer or DesktopPortfolioConcentrationRenderer()
        )
        self._opportunity_alignment = (
            opportunity_alignment_renderer
            or DesktopPortfolioOpportunityAlignmentRenderer()
        )

    def render(self, state):
        if type(state) is not PortfolioWorkspaceState:
            raise TypeError("state must be PortfolioWorkspaceState.")
        if state.availability is PortfolioWorkspaceAvailability.UNAVAILABLE:
            return DesktopPortfolioWorkspaceView(
                state.title,
                state.availability,
                state.navigation,
                state.current_destination,
                "Portfolio Workspace unavailable",
                "Portfolio Workspace is unavailable.",
                state,
            )
        if state.current_destination is not PortfolioWorkspaceDestination.OVERVIEW:
            title = next(
                value.title
                for value in state.navigation
                if value.destination is state.current_destination
            )
            return DesktopPortfolioWorkspaceView(
                state.title,
                state.availability,
                state.navigation,
                state.current_destination,
                title,
                "Not available in this release",
                state,
            )
        overview = state.overview
        sections = (
            _rendered_body(self._overview.render(overview.overview)),
            _rendered_body(self._distribution.render(overview.distribution)),
            _rendered_body(self._concentration.render(overview.concentration)),
            _rendered_body(
                self._opportunity_alignment.render(
                    overview.opportunity_alignment
                )
            ),
        )
        return DesktopPortfolioWorkspaceView(
            state.title,
            state.availability,
            state.navigation,
            state.current_destination,
            "Overview",
            "\n\n".join(sections),
            state,
        )


class DesktopPortfolioWorkspaceController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopPortfolioWorkspaceRenderer()

    def open(
        self,
        overview_result=None,
        distribution_result=None,
        concentration_result=None,
        opportunity_alignment_result=None,
        **state,
    ):
        workspace = self._presentation.workspace(
            overview_result,
            distribution_result,
            concentration_result,
            opportunity_alignment_result,
            **state,
        )
        return self._renderer.render(workspace)

    def navigate(self, state, destination):
        return self._renderer.render(
            self._presentation.navigate(state, destination)
        )


def _rendered_body(value):
    lines = (value.title, value.headline, value.summary)
    sections = tuple(
        f"{section.title}\n{section.body}" for section in value.sections
    )
    return "\n\n".join(item for item in (*lines, *sections) if item)


__all__ = [
    "DesktopPortfolioWorkspaceController",
    "DesktopPortfolioWorkspaceRenderer",
    "DesktopPortfolioWorkspaceView",
]
