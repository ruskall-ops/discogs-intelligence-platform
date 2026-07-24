"""Application presentation boundary for Portfolio Overview."""

from typing import Protocol

from dip.experience.portfolio_overview import PortfolioOverviewViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> PortfolioOverviewViewModel: ...


class PortfolioOverviewPresentationService:
    def __init__(self, builder: _Builder):
        self._builder = builder

    def overview_for_result(self, result):
        return self._builder.build(result)


__all__ = ["PortfolioOverviewPresentationService"]
