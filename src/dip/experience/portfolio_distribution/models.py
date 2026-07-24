"""Immutable Portfolio Distribution presentation models."""

from dataclasses import dataclass, field
from enum import Enum

from dip.portfolio_intelligence import (
    PortfolioDimensionDistribution,
    PortfolioDistributionDiagnostic,
    PortfolioDistributionEvidenceCoverage,
    PortfolioDistributionProvenance,
    PortfolioDistributionReasonCode,
    PortfolioDistributionRuleConfiguration,
    PortfolioDistributionSummary,
    PortfolioReleaseDistributionDetail,
)


class PortfolioDistributionDetailState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class PortfolioDistributionViewModel:
    state: PortfolioDistributionDetailState
    summary_text: str
    rule_set_version: str | None = None
    rule_configuration: PortfolioDistributionRuleConfiguration | None = None
    summary: PortfolioDistributionSummary | None = None
    evidence_coverage: PortfolioDistributionEvidenceCoverage | None = None
    dimensions: tuple[PortfolioDimensionDistribution, ...] = ()
    releases: tuple[PortfolioReleaseDistributionDetail, ...] = ()
    reason_codes: tuple[PortfolioDistributionReasonCode, ...] = ()
    provenance: PortfolioDistributionProvenance | None = None
    output_diagnostics: tuple[PortfolioDistributionDiagnostic, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Portfolio Distribution")

    def __post_init__(self) -> None:
        for name in ("dimensions", "releases", "reason_codes", "output_diagnostics", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    @classmethod
    def unavailable(cls):
        return cls(
            PortfolioDistributionDetailState.UNAVAILABLE,
            "Portfolio Distribution has not been supplied.",
        )


__all__ = ["PortfolioDistributionDetailState", "PortfolioDistributionViewModel"]
