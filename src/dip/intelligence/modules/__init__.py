"""Independent, versioned intelligence modules."""

from .collection_health import (
    CollectionHealthConfig,
    CollectionHealthModule,
    CollectionHealthWeights,
)
from .hidden_gems import (
    HiddenGemCandidate,
    HiddenGemsConfig,
    HiddenGemsModule,
)
from .historical_intelligence import (
    HistoricalComparison,
    HistoricalIntelligenceConfig,
    HistoricalIntelligenceModule,
    HistoricalReleaseChange,
    HistoricalReleaseIdentity,
    HistoricalSnapshotInfo,
)
from .opportunity_scoring import calculate

__all__ = [
    "CollectionHealthConfig",
    "CollectionHealthModule",
    "CollectionHealthWeights",
    "HiddenGemCandidate",
    "HiddenGemsConfig",
    "HiddenGemsModule",
    "HistoricalComparison",
    "HistoricalIntelligenceConfig",
    "HistoricalIntelligenceModule",
    "HistoricalReleaseChange",
    "HistoricalReleaseIdentity",
    "HistoricalSnapshotInfo",
    "calculate",
]
