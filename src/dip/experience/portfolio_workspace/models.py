"""Immutable presentation state for the Portfolio Workspace."""

from dataclasses import dataclass, field
from enum import Enum

from dip.experience.portfolio_concentration import PortfolioConcentrationViewModel
from dip.experience.portfolio_distribution import PortfolioDistributionViewModel
from dip.experience.portfolio_opportunity_alignment import (
    PortfolioOpportunityAlignmentViewModel,
)
from dip.experience.portfolio_overview import PortfolioOverviewViewModel


class PortfolioWorkspaceDestination(str, Enum):
    OVERVIEW = "overview"
    DISTRIBUTION = "distribution"
    CONCENTRATION = "concentration"
    OPPORTUNITY_ALIGNMENT = "opportunity_alignment"
    HISTORY = "history"
    RESEARCH = "research"


class PortfolioWorkspaceAvailability(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class PortfolioWorkspaceNavigationItem:
    destination: PortfolioWorkspaceDestination
    title: str
    implemented: bool

    def __post_init__(self):
        if type(self.destination) is not PortfolioWorkspaceDestination:
            raise TypeError("destination must be PortfolioWorkspaceDestination.")
        if type(self.title) is not str or not self.title:
            raise TypeError("title must be a non-empty string.")
        if type(self.implemented) is not bool:
            raise TypeError("implemented must be a boolean.")


@dataclass(frozen=True)
class PortfolioWorkspaceOverviewViewModel:
    overview: PortfolioOverviewViewModel
    distribution: PortfolioDistributionViewModel
    concentration: PortfolioConcentrationViewModel
    opportunity_alignment: PortfolioOpportunityAlignmentViewModel

    def __post_init__(self):
        expected = (
            ("overview", PortfolioOverviewViewModel),
            ("distribution", PortfolioDistributionViewModel),
            ("concentration", PortfolioConcentrationViewModel),
            ("opportunity_alignment", PortfolioOpportunityAlignmentViewModel),
        )
        for name, value_type in expected:
            if type(getattr(self, name)) is not value_type:
                raise TypeError(f"{name} must be {value_type.__name__}.")


@dataclass(frozen=True)
class PortfolioWorkspaceState:
    availability: PortfolioWorkspaceAvailability
    current_destination: PortfolioWorkspaceDestination
    navigation: tuple[PortfolioWorkspaceNavigationItem, ...]
    overview: PortfolioWorkspaceOverviewViewModel
    title: str = field(init=False, default="Portfolio Workspace")

    def __post_init__(self):
        object.__setattr__(self, "navigation", tuple(self.navigation))
        if type(self.availability) is not PortfolioWorkspaceAvailability:
            raise TypeError("availability must be PortfolioWorkspaceAvailability.")
        if type(self.current_destination) is not PortfolioWorkspaceDestination:
            raise TypeError("current_destination must be PortfolioWorkspaceDestination.")
        if any(type(value) is not PortfolioWorkspaceNavigationItem for value in self.navigation):
            raise TypeError("navigation must contain PortfolioWorkspaceNavigationItem values.")
        destinations = tuple(value.destination for value in self.navigation)
        if len(set(destinations)) != len(destinations):
            raise ValueError("navigation destinations must be unique.")
        if self.current_destination not in destinations:
            raise ValueError("current_destination must be present in navigation.")
        if type(self.overview) is not PortfolioWorkspaceOverviewViewModel:
            raise TypeError("overview must be PortfolioWorkspaceOverviewViewModel.")


__all__ = [
    "PortfolioWorkspaceAvailability",
    "PortfolioWorkspaceDestination",
    "PortfolioWorkspaceNavigationItem",
    "PortfolioWorkspaceOverviewViewModel",
    "PortfolioWorkspaceState",
]
