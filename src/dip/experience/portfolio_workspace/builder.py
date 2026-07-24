"""Deterministic composition and navigation for Portfolio Workspace."""

from dataclasses import replace

from .models import (
    PortfolioWorkspaceAvailability,
    PortfolioWorkspaceDestination,
    PortfolioWorkspaceNavigationItem,
    PortfolioWorkspaceOverviewViewModel,
    PortfolioWorkspaceState,
)


_NAVIGATION = (
    PortfolioWorkspaceNavigationItem(
        PortfolioWorkspaceDestination.OVERVIEW, "Overview", True
    ),
    PortfolioWorkspaceNavigationItem(
        PortfolioWorkspaceDestination.DISTRIBUTION, "Distribution", False
    ),
    PortfolioWorkspaceNavigationItem(
        PortfolioWorkspaceDestination.CONCENTRATION, "Concentration", False
    ),
    PortfolioWorkspaceNavigationItem(
        PortfolioWorkspaceDestination.OPPORTUNITY_ALIGNMENT,
        "Opportunity Alignment",
        False,
    ),
    PortfolioWorkspaceNavigationItem(
        PortfolioWorkspaceDestination.HISTORY, "History", False
    ),
    PortfolioWorkspaceNavigationItem(
        PortfolioWorkspaceDestination.RESEARCH, "Research", False
    ),
)


class PortfolioWorkspaceStateBuilder:
    def build(
        self,
        overview,
        distribution,
        concentration,
        opportunity_alignment,
        *,
        current_destination=PortfolioWorkspaceDestination.OVERVIEW,
        available=True,
    ):
        if type(available) is not bool:
            raise TypeError("available must be a boolean.")
        composed = PortfolioWorkspaceOverviewViewModel(
            overview, distribution, concentration, opportunity_alignment
        )
        has_content = any(
            value.summary is not None
            for value in (
                overview,
                distribution,
                concentration,
                opportunity_alignment,
            )
        )
        availability = (
            PortfolioWorkspaceAvailability.UNAVAILABLE
            if not available
            else PortfolioWorkspaceAvailability.AVAILABLE
            if has_content
            else PortfolioWorkspaceAvailability.EMPTY
        )
        return PortfolioWorkspaceState(
            availability, current_destination, _NAVIGATION, composed
        )

    def navigate(self, state, destination):
        if type(state) is not PortfolioWorkspaceState:
            raise TypeError("state must be PortfolioWorkspaceState.")
        if type(destination) is not PortfolioWorkspaceDestination:
            raise TypeError("destination must be PortfolioWorkspaceDestination.")
        return replace(state, current_destination=destination)


__all__ = ["PortfolioWorkspaceStateBuilder"]
