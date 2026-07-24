"""Application presentation boundary for Portfolio Distribution."""

from typing import Protocol

from dip.experience.portfolio_distribution import PortfolioDistributionViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> PortfolioDistributionViewModel: ...


class PortfolioDistributionPresentationService:
    def __init__(self, builder: _Builder):
        self._builder = builder

    def distribution_for_result(self, result):
        return self._builder.build(result)


__all__ = ["PortfolioDistributionPresentationService"]
