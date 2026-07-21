"""Deterministic, storage-independent Intelligence comparison foundation."""

from .comparers import GenericModuleComparer
from .defaults import build_default_comparison_registry
from .engine import ComparisonEngine
from .models import (
    ComparisonResult,
    ExecutionComparison,
    ModuleComparison,
    ValueChange,
)
from .registry import ComparisonRegistry, ModuleComparer

__all__ = [
    "ComparisonEngine",
    "ComparisonRegistry",
    "ComparisonResult",
    "ExecutionComparison",
    "GenericModuleComparer",
    "ModuleComparer",
    "ModuleComparison",
    "ValueChange",
    "build_default_comparison_registry",
]
