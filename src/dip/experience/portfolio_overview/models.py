"""Immutable Portfolio Overview presentation models."""

from dataclasses import dataclass, field
from enum import Enum

from dip.portfolio_intelligence import (
    PortfolioConcentrationFacts,
    PortfolioDistribution,
    PortfolioEvidenceCoverage,
    PortfolioOverviewDiagnostic,
    PortfolioOverviewReasonCode,
    PortfolioOverviewRuleConfiguration,
    PortfolioOverviewSummary,
    PortfolioReleaseOverview,
    PortfolioSourceProvenance,
)


class PortfolioOverviewDetailState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class PortfolioOverviewViewModel:
    state: PortfolioOverviewDetailState
    summary_text: str
    rule_set_version: str | None = None
    rule_configuration: PortfolioOverviewRuleConfiguration | None = None
    summary: PortfolioOverviewSummary | None = None
    evidence_coverage: PortfolioEvidenceCoverage | None = None
    opportunity_distribution: PortfolioDistribution | None = None
    momentum_distribution: PortfolioDistribution | None = None
    stability_distribution: PortfolioDistribution | None = None
    scarcity_distribution: PortfolioDistribution | None = None
    concentration_facts: tuple[PortfolioConcentrationFacts, ...] = ()
    releases: tuple[PortfolioReleaseOverview, ...] = ()
    reason_codes: tuple[PortfolioOverviewReasonCode, ...] = ()
    source_provenance: PortfolioSourceProvenance | None = None
    output_diagnostics: tuple[PortfolioOverviewDiagnostic, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Portfolio Overview")

    def __post_init__(self) -> None:
        for name in ("concentration_facts", "releases", "reason_codes", "output_diagnostics", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    @classmethod
    def unavailable(cls):
        return cls(PortfolioOverviewDetailState.UNAVAILABLE, "Portfolio Overview has not been supplied.")


__all__ = ["PortfolioOverviewDetailState", "PortfolioOverviewViewModel"]
