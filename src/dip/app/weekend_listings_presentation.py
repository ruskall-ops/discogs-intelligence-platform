"""Application-facing Weekend Listings presentation coordination."""

from __future__ import annotations

from typing import Protocol

from dip.experience.weekend_listings import WeekendListingsDetailViewModel
from dip.intelligence import IntelligenceResult


class _WeekendListingsBuilder(Protocol):
    def build(
        self,
        result: IntelligenceResult | None,
    ) -> WeekendListingsDetailViewModel: ...


class WeekendListingsPresentationService:
    """Transform one already-produced result without executing intelligence."""

    def __init__(self, builder: _WeekendListingsBuilder) -> None:
        self._builder = builder

    def detail_for_result(
        self,
        result: IntelligenceResult | None,
    ) -> WeekendListingsDetailViewModel:
        return self._builder.build(result)


__all__ = ["WeekendListingsPresentationService"]
