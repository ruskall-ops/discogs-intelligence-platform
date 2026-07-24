"""Separate top-level Portfolio workspace composition."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from dip.intelligence import IntelligenceResult

from .portfolio_distribution_renderer import DesktopPortfolioDistributionView
from .portfolio_overview_renderer import DesktopPortfolioOverviewView


class DesktopPortfolioDestination(str, Enum):
    OVERVIEW = "overview"
    DISTRIBUTION = "distribution"


@dataclass(frozen=True)
class DesktopPortfolioSection:
    destination: DesktopPortfolioDestination
    title: str
    body: str


@dataclass(frozen=True)
class DesktopPortfolioView:
    title: str
    sections: tuple[DesktopPortfolioSection, ...]


class _OverviewController(Protocol):
    def open(self, result: IntelligenceResult | None) -> DesktopPortfolioOverviewView: ...


class _DistributionController(Protocol):
    def open(self, result: IntelligenceResult | None) -> DesktopPortfolioDistributionView: ...


class DesktopPortfolioController:
    """Build both tabs once from already-produced results."""

    def __init__(self, overview: _OverviewController, distribution: _DistributionController):
        self._overview = overview
        self._distribution = distribution

    def open(self, overview_result=None, distribution_result=None):
        overview = self._overview.open(overview_result)
        distribution = self._distribution.open(distribution_result)
        return DesktopPortfolioView(
            "Portfolio",
            (
                DesktopPortfolioSection(
                    DesktopPortfolioDestination.OVERVIEW,
                    "Overview",
                    _body(overview.headline, overview.summary, overview.sections),
                ),
                DesktopPortfolioSection(
                    DesktopPortfolioDestination.DISTRIBUTION,
                    "Distribution",
                    _body(distribution.headline, distribution.summary, distribution.sections),
                ),
            ),
        )


def _body(headline, summary, sections):
    values = [headline, summary]
    values.extend(f"{value.title}\n{value.body}" for value in sections)
    return "\n\n".join(value for value in values if value)


__all__ = [
    "DesktopPortfolioController",
    "DesktopPortfolioDestination",
    "DesktopPortfolioSection",
    "DesktopPortfolioView",
]
