"""Application presentation boundary for Rare Appearances."""

from typing import Protocol
from dip.experience.rare_appearances import RareAppearancesDetailViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> RareAppearancesDetailViewModel: ...


class RareAppearancesPresentationService:
    def __init__(self, builder: _Builder) -> None:
        self._builder = builder

    def detail_for_result(self, result: IntelligenceResult | None) -> RareAppearancesDetailViewModel:
        return self._builder.build(result)


__all__ = ["RareAppearancesPresentationService"]
