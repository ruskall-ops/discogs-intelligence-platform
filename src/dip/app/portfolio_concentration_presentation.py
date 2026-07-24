"""Application presentation boundary for Portfolio Concentration."""

from typing import Protocol

from dip.experience.portfolio_concentration import PortfolioConcentrationViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> PortfolioConcentrationViewModel: ...


class PortfolioConcentrationPresentationService:
    def __init__(self, builder: _Builder):
        self._builder = builder

    def concentration_for_result(self, result):
        return self._builder.build(result)


__all__ = ["PortfolioConcentrationPresentationService"]
