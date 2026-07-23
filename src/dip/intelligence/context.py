"""Prepared, presentation-independent input for intelligence modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping, Sequence

if TYPE_CHECKING:
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
