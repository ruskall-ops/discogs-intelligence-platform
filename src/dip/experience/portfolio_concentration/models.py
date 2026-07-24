"""Immutable Portfolio Concentration presentation models."""

from dataclasses import dataclass, field
from enum import Enum

from dip.portfolio_intelligence import (
    PortfolioConcentrationDiagnostic,
    PortfolioConcentrationEvidenceCoverage,
    PortfolioConcentrationProvenance,
    PortfolioConcentrationReasonCode,
    PortfolioConcentrationRuleConfiguration,
    PortfolioConcentrationSummary,
    PortfolioDimensionConcentration,
)


class PortfolioConcentrationDetailState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class PortfolioConcentrationViewModel:
    state: PortfolioConcentrationDetailState
    summary_text: str
    rule_set_version: str | None = None
    rule_configuration: PortfolioConcentrationRuleConfiguration | None = None
    summary: PortfolioConcentrationSummary | None = None
    evidence_coverage: PortfolioConcentrationEvidenceCoverage | None = None
    dimensions: tuple[PortfolioDimensionConcentration, ...] = ()
    reason_codes: tuple[PortfolioConcentrationReasonCode, ...] = ()
    provenance: PortfolioConcentrationProvenance | None = None
    output_diagnostics: tuple[PortfolioConcentrationDiagnostic, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Portfolio Concentration")

    def __post_init__(self):
        for name in ("dimensions", "reason_codes", "output_diagnostics", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    @classmethod
    def unavailable(cls):
        return cls(
            PortfolioConcentrationDetailState.UNAVAILABLE,
            "Portfolio Concentration has not been supplied.",
        )


__all__ = ["PortfolioConcentrationDetailState", "PortfolioConcentrationViewModel"]
