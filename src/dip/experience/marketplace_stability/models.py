"""Immutable Marketplace Stability presentation models."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from dip.decision_intelligence import (
    MarketplaceStabilityDiagnostic,
    MarketplaceStabilitySummary,
    ReleaseStability,
    StabilityAnalysisState,
    StabilitySourceProvenance,
)


class MarketplaceStabilityDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class MarketplaceStabilityDetailViewModel:
    state: MarketplaceStabilityDetailState
    summary: str
    analysis_state: StabilityAnalysisState | None = None
    rule_set_version: str | None = None
    stability_summary: MarketplaceStabilitySummary | None = None
    releases: tuple[ReleaseStability, ...] = ()
    source_provenance: tuple[StabilitySourceProvenance, ...] = ()
    output_diagnostics: tuple[MarketplaceStabilityDiagnostic, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Marketplace Stability")

    def __post_init__(self) -> None:
        for name, value, value_type in (
            ("releases", self.releases, ReleaseStability),
            ("source_provenance", self.source_provenance, StabilitySourceProvenance),
            ("output_diagnostics", self.output_diagnostics, MarketplaceStabilityDiagnostic),
        ):
            values = tuple(value)
            if any(type(item) is not value_type for item in values):
                raise TypeError(f"{name} contains invalid values.")
            object.__setattr__(self, name, values)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not str for value in diagnostics):
            raise TypeError("diagnostics must contain strings.")
        object.__setattr__(self, "diagnostics", diagnostics)

    @classmethod
    def loading(cls):
        return cls(MarketplaceStabilityDetailState.LOADING, "Marketplace Stability is loading.")

    @classmethod
    def unavailable(cls):
        return cls(MarketplaceStabilityDetailState.UNAVAILABLE, "Marketplace Stability has not been supplied.")


__all__ = ["MarketplaceStabilityDetailState", "MarketplaceStabilityDetailViewModel"]

