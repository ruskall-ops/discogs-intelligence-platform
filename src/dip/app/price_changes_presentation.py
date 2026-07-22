"""Application-facing Price Changes presentation coordination."""

from __future__ import annotations

from typing import Protocol

from dip.experience.price_changes import PriceChangesDetailViewModel
from dip.intelligence import IntelligenceResult


class _PriceChangesBuilder(Protocol):
    def build(
        self,
        result: IntelligenceResult | None,
    ) -> PriceChangesDetailViewModel: ...


class PriceChangesPresentationService:
    """Transform one already-produced result without executing intelligence."""

    def __init__(self, builder: _PriceChangesBuilder) -> None:
        self._builder = builder

    def detail_for_result(
        self,
        result: IntelligenceResult | None,
    ) -> PriceChangesDetailViewModel:
        return self._builder.build(result)


__all__ = ["PriceChangesPresentationService"]
