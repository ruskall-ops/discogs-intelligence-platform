"""Separate top-level Portfolio workspace composition."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from dip.intelligence import IntelligenceResult

from .portfolio_distribution_renderer import DesktopPortfolioDistributionView
from .portfolio_overview_renderer import DesktopPortfolioOverviewView
from .portfolio_concentration_renderer import DesktopPortfolioConcentrationView
from .portfolio_opportunity_alignment_renderer import DesktopPortfolioOpportunityAlignmentView


class DesktopPortfolioDestination(str, Enum):
    OVERVIEW = "overview"
    DISTRIBUTION = "distribution"
    CONCENTRATION = "concentration"
    OPPORTUNITY_ALIGNMENT = "opportunity_alignment"


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


class _ConcentrationController(Protocol):
    def open(self, result: IntelligenceResult | None) -> DesktopPortfolioConcentrationView: ...


class _AlignmentController(Protocol):
    def open(self, result: IntelligenceResult | None) -> DesktopPortfolioOpportunityAlignmentView: ...


class DesktopPortfolioController:
    """Build both tabs once from already-produced results."""

    def __init__(
        self,
        overview: _OverviewController,
        distribution: _DistributionController,
        concentration: _ConcentrationController,
        alignment: _AlignmentController | None = None,
    ):
        self._overview = overview
        self._distribution = distribution
        self._concentration = concentration
        self._alignment = alignment or _UnavailableAlignmentController()
        self._alignment_configured = alignment is not None

    def open(self, overview_result=None, distribution_result=None, concentration_result=None, alignment_result=None):
        overview = self._overview.open(overview_result)
        distribution = self._distribution.open(distribution_result)
        concentration = self._concentration.open(concentration_result)
        alignment = self._alignment.open(alignment_result)
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
                DesktopPortfolioSection(
                    DesktopPortfolioDestination.CONCENTRATION,
                    "Concentration",
                    _body(concentration.headline, concentration.summary, concentration.sections),
                ),
                *((DesktopPortfolioSection(
                    DesktopPortfolioDestination.OPPORTUNITY_ALIGNMENT,
                    "Opportunity Alignment",
                    _body(alignment.headline, alignment.summary, alignment.sections),
                ),) if self._alignment_configured else ()),
            ),
        )


def _body(headline, summary, sections):
    values = [headline, summary]
    values.extend(f"{value.title}\n{value.body}" for value in sections)
    return "\n\n".join(value for value in values if value)


class _UnavailableAlignmentController:
    def open(self, result):
        return DesktopPortfolioOpportunityAlignmentView(
            "Portfolio Opportunity Alignment", "unavailable", "Unavailable",
            "Portfolio Opportunity Alignment has not been supplied.",
        )


__all__ = [
    "DesktopPortfolioController",
    "DesktopPortfolioDestination",
    "DesktopPortfolioSection",
    "DesktopPortfolioView",
]
