"""Immutable Marketplace Scarcity presentation models."""

from dataclasses import dataclass, field
from enum import Enum

from dip.decision_intelligence import (
    MarketplaceScarcityDiagnostic,
    MarketplaceScarcitySummary,
    ReleaseScarcity,
    ScarcityAnalysisState,
    ScarcitySourceProvenance,
)


class MarketplaceScarcityDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class MarketplaceScarcityDetailViewModel:
    state: MarketplaceScarcityDetailState
    summary: str
    analysis_state: ScarcityAnalysisState | None = None
    rule_set_version: str | None = None
    scarcity_summary: MarketplaceScarcitySummary | None = None
    releases: tuple[ReleaseScarcity, ...] = ()
    source_provenance: tuple[ScarcitySourceProvenance, ...] = ()
    output_diagnostics: tuple[MarketplaceScarcityDiagnostic, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Marketplace Scarcity")

    def __post_init__(self):
        for name, expected in (
            ("releases", ReleaseScarcity),
            ("source_provenance", ScarcitySourceProvenance),
            ("output_diagnostics", MarketplaceScarcityDiagnostic),
        ):
            values = tuple(getattr(self, name))
            if any(type(value) is not expected for value in values):
                raise TypeError(f"{name} contains invalid values.")
            object.__setattr__(self, name, values)
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @classmethod
    def loading(cls):
        return cls(MarketplaceScarcityDetailState.LOADING, "Marketplace Scarcity is loading.")

    @classmethod
    def unavailable(cls):
        return cls(MarketplaceScarcityDetailState.UNAVAILABLE, "Marketplace Scarcity has not been supplied.")


__all__ = ["MarketplaceScarcityDetailState", "MarketplaceScarcityDetailViewModel"]

