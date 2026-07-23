"""Application presentation boundary for Marketplace Stability."""

from typing import Protocol

from dip.experience.marketplace_stability import MarketplaceStabilityDetailViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> MarketplaceStabilityDetailViewModel: ...


class MarketplaceStabilityPresentationService:
    def __init__(self, builder: _Builder) -> None:
        self._builder = builder

    def detail_for_result(self, result: IntelligenceResult | None) -> MarketplaceStabilityDetailViewModel:
        return self._builder.build(result)


__all__ = ["MarketplaceStabilityPresentationService"]

