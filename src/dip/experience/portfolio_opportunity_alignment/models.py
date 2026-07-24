"""Immutable Portfolio Opportunity Alignment presentation models."""

from dataclasses import dataclass, field
from enum import Enum

from dip.portfolio_decision_intelligence import (
    PortfolioDimensionAlignment,
    PortfolioOpportunityAlignmentDiagnostic,
    PortfolioOpportunityAlignmentProvenance,
    PortfolioOpportunityAlignmentReasonCode,
    PortfolioOpportunityAlignmentRuleConfiguration,
    PortfolioOpportunityAlignmentSummary,
    PortfolioOpportunityBreadth,
)


class PortfolioOpportunityAlignmentDetailState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class PortfolioOpportunityAlignmentViewModel:
    state: PortfolioOpportunityAlignmentDetailState
    summary_text: str
    rule_set_version: str | None = None
    rule_configuration: PortfolioOpportunityAlignmentRuleConfiguration | None = None
    summary: PortfolioOpportunityAlignmentSummary | None = None
    breadth: PortfolioOpportunityBreadth | None = None
    dimensions: tuple[PortfolioDimensionAlignment, ...] = ()
    reason_codes: tuple[PortfolioOpportunityAlignmentReasonCode, ...] = ()
    provenance: PortfolioOpportunityAlignmentProvenance | None = None
    output_diagnostics: tuple[PortfolioOpportunityAlignmentDiagnostic, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Portfolio Opportunity Alignment")

    def __post_init__(self):
        for name in ("dimensions", "reason_codes", "output_diagnostics", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    @classmethod
    def unavailable(cls):
        return cls(
            PortfolioOpportunityAlignmentDetailState.UNAVAILABLE,
            "Portfolio Opportunity Alignment has not been supplied.",
        )

