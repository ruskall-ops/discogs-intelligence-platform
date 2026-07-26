"""Explainable, presentation-independent collection intelligence."""

from .context import IntelligenceContext
from .defaults import (
    COLLECTION_INTELLIGENCE_ENGINE_VERSION,
    build_v02_intelligence_registry,
)
from .engine import IntelligenceEngine
from .models import IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from .registry import IntelligenceModule, IntelligenceRegistry

__all__ = [
    "IntelligenceContext",
    "COLLECTION_INTELLIGENCE_ENGINE_VERSION",
    "IntelligenceEngine",
    "IntelligenceExecution",
    "IntelligenceModule",
    "IntelligenceRegistry",
    "IntelligenceResult",
    "IntelligenceStatus",
    "build_v02_intelligence_registry",
]
