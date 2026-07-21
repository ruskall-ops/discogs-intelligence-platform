"""Default comparer registration for current Collection Intelligence modules."""

from .comparers import GenericModuleComparer
from .registry import ComparisonRegistry


DEFAULT_COMPARISON_MODULE_IDS = (
    "collection_health",
    "hidden_gems",
    "historical_intelligence",
)


def build_default_comparison_registry() -> ComparisonRegistry:
    """Register generic comparers and retain a generic future-module fallback."""

    return ComparisonRegistry(
        (
            GenericModuleComparer(module_id)
            for module_id in DEFAULT_COMPARISON_MODULE_IDS
        ),
        fallback_factory=GenericModuleComparer,
    )
