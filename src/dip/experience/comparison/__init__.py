"""Presentation-neutral comparison ViewModel boundary."""

from .builder import ComparisonViewModelBuilder
from .models import (
    ComparisonValueAvailability,
    ComparisonViewModelConsistencyError,
    ExecutionComparisonViewModel,
    FieldChangeViewModel,
    ModuleComparisonState,
    ModuleComparisonViewModel,
)

__all__ = [
    "ComparisonValueAvailability",
    "ComparisonViewModelBuilder",
    "ComparisonViewModelConsistencyError",
    "ExecutionComparisonViewModel",
    "FieldChangeViewModel",
    "ModuleComparisonState",
    "ModuleComparisonViewModel",
]
