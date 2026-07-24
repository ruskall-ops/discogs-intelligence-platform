"""Immutable Marketplace Opportunity presentation models."""

from dataclasses import dataclass, field
from enum import Enum

from dip.decision_intelligence import (
    MarketplaceOpportunityDiagnostic,
    MarketplaceOpportunitySummary,
    OpportunityAnalysisState,
    OpportunityRuleConfiguration,
    OpportunitySourceProvenance,
    ReleaseOpportunity,
)


class MarketplaceOpportunityDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class MarketplaceOpportunityDetailViewModel:
    state: MarketplaceOpportunityDetailState
    summary: str
    analysis_state: OpportunityAnalysisState | None = None
    rule_set_version: str | None = None
    rule_configuration: OpportunityRuleConfiguration | None = None
    opportunity_summary: MarketplaceOpportunitySummary | None = None
    releases: tuple[ReleaseOpportunity, ...] = ()
    source_provenance: tuple[OpportunitySourceProvenance, ...] = ()
    output_diagnostics: tuple[MarketplaceOpportunityDiagnostic, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Marketplace Opportunity")

    def __post_init__(self):
        for name, expected in (
            ("releases", ReleaseOpportunity),
            ("source_provenance", OpportunitySourceProvenance),
            ("output_diagnostics", MarketplaceOpportunityDiagnostic),
        ):
            values = tuple(getattr(self, name))
            if any(type(value) is not expected for value in values):
                raise TypeError(f"{name} contains invalid values.")
            object.__setattr__(self, name, values)
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @classmethod
    def loading(cls):
        return cls(MarketplaceOpportunityDetailState.LOADING, "Marketplace Opportunity is loading.")

    @classmethod
    def unavailable(cls):
        return cls(MarketplaceOpportunityDetailState.UNAVAILABLE, "Marketplace Opportunity has not been supplied.")


__all__ = ["MarketplaceOpportunityDetailState", "MarketplaceOpportunityDetailViewModel"]

