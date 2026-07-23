"""Application presentation boundary for Marketplace Activity."""

from typing import Protocol
from dip.experience.marketplace_activity import MarketplaceActivityDetailViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> MarketplaceActivityDetailViewModel: ...


class MarketplaceActivityPresentationService:
    def __init__(self, builder: _Builder) -> None:
        self._builder = builder

    def detail_for_result(self, result: IntelligenceResult | None) -> MarketplaceActivityDetailViewModel:
        return self._builder.build(result)


__all__ = ["MarketplaceActivityPresentationService"]
