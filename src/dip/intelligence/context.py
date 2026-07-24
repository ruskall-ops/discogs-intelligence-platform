"""Prepared, presentation-independent input for intelligence modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping, Sequence

if TYPE_CHECKING:
    from dip.decision_intelligence import MarketplaceMomentumInput
    from dip.decision_intelligence import MarketplaceStabilityInput
    from dip.decision_intelligence import MarketplaceScarcityInput
    from dip.decision_intelligence import MarketplaceOpportunityInput
    from dip.portfolio_intelligence import PortfolioOverviewInput
    from dip.portfolio_intelligence import PortfolioDistributionInput
    from dip.portfolio_intelligence import PortfolioConcentrationInput
    from dip.portfolio_decision_intelligence import PortfolioOpportunityAlignmentInput
    from dip.marketplace_intelligence.price_changes import (
        MarketplaceSnapshotComparisonInput,
    )
    from dip.marketplace_intelligence.models import MarketplaceSnapshot


@dataclass(frozen=True)
class IntelligenceContext:
    """One consistent view of the evidence available to an analysis run.

    Modules receive this context instead of querying SQLite or external data
    providers directly. Defaults preserve the lightweight context introduced
    with the original package foundation.
    """

    collection: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    marketplace: Mapping[int, Mapping[str, Any]] = field(default_factory=dict)
    history: Mapping[int, Sequence[Mapping[str, Any]]] = field(default_factory=dict)
    user_context: Mapping[str, Any] = field(default_factory=dict)
    filters: Mapping[str, Any] = field(default_factory=dict)
    analysis_run_id: int | None = None
    captured_at: datetime | None = None
    marketplace_snapshot: MarketplaceSnapshot | None = None
    marketplace_comparison: MarketplaceSnapshotComparisonInput | None = None
    marketplace_history: tuple[MarketplaceSnapshot, ...] = ()
    marketplace_activity_sources: tuple["IntelligenceResult", ...] = ()
    marketplace_momentum_input: MarketplaceMomentumInput | None = None
    marketplace_stability_input: MarketplaceStabilityInput | None = None
    marketplace_scarcity_input: MarketplaceScarcityInput | None = None
    marketplace_opportunity_input: MarketplaceOpportunityInput | None = None
    portfolio_overview_input: PortfolioOverviewInput | None = None
    portfolio_distribution_input: PortfolioDistributionInput | None = None
    portfolio_concentration_input: PortfolioConcentrationInput | None = None
    portfolio_opportunity_alignment_input: PortfolioOpportunityAlignmentInput | None = None
