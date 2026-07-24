"""Application presentation boundary for Marketplace Opportunity."""

from typing import Protocol

from dip.experience.marketplace_opportunity import MarketplaceOpportunityDetailViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> MarketplaceOpportunityDetailViewModel: ...


class MarketplaceOpportunityPresentationService:
    def __init__(self, builder: _Builder):
        self._builder = builder

    def detail_for_result(self, result):
        return self._builder.build(result)


__all__ = ["MarketplaceOpportunityPresentationService"]

