"""Application presentation boundary for Supply Changes."""

from typing import Protocol
from dip.experience.supply_changes import SupplyChangesDetailViewModel
from dip.intelligence import IntelligenceResult


class _Builder(Protocol):
    def build(self, result: IntelligenceResult | None) -> SupplyChangesDetailViewModel: ...


class SupplyChangesPresentationService:
    def __init__(self, builder: _Builder) -> None:
        self._builder = builder

    def detail_for_result(self, result: IntelligenceResult | None) -> SupplyChangesDetailViewModel:
        return self._builder.build(result)


__all__ = ["SupplyChangesPresentationService"]
