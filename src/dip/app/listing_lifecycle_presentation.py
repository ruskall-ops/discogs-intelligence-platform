"""Application presentation boundary for Listing Lifecycle."""

from typing import Protocol
from dip.experience.listing_lifecycle import ListingLifecycleDetailViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> ListingLifecycleDetailViewModel: ...


class ListingLifecyclePresentationService:
    def __init__(self, builder: _Builder) -> None:
        self._builder = builder

    def detail_for_result(self, result: IntelligenceResult | None) -> ListingLifecycleDetailViewModel:
        return self._builder.build(result)


__all__ = ["ListingLifecyclePresentationService"]
