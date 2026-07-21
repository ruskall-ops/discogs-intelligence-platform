"""Explicit Version 0.2 intelligence module registration."""

from __future__ import annotations

from .modules import (
    CollectionHealthConfig,
    CollectionHealthModule,
    HiddenGemsConfig,
    HiddenGemsModule,
    HistoricalIntelligenceConfig,
    HistoricalIntelligenceModule,
)
from .registry import IntelligenceRegistry


def build_v02_intelligence_registry(
    *,
    collection_health_config: CollectionHealthConfig | None = None,
    hidden_gems_config: HiddenGemsConfig | None = None,
    historical_intelligence_config: HistoricalIntelligenceConfig | None = None,
) -> IntelligenceRegistry:
    """Register the currently implemented Version 0.2 modules."""

    return IntelligenceRegistry(
        (
            CollectionHealthModule(collection_health_config),
            HiddenGemsModule(hidden_gems_config),
            HistoricalIntelligenceModule(historical_intelligence_config),
        )
    )
