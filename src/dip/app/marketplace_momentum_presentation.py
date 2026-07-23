"""Application presentation boundary for Marketplace Momentum."""

from typing import Protocol

from dip.experience.marketplace_momentum import (
    MarketplaceMomentumDetailViewModel,
)
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(
        self,
        result: IntelligenceResult | None,
    ) -> MarketplaceMomentumDetailViewModel: ...


class MarketplaceMomentumPresentationService:
    """Map an already-produced Momentum result for presentation."""

    def __init__(self, builder: _Builder) -> None:
        self._builder = builder

    def detail_for_result(
        self,
        result: IntelligenceResult | None,
    ) -> MarketplaceMomentumDetailViewModel:
        return self._builder.build(result)


__all__ = ["MarketplaceMomentumPresentationService"]
