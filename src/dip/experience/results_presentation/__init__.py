"""Shared factual result-presentation primitives."""

from .copy import presentation_state_copy
from .models import (
    ComparisonContextViewModel,
    PresentationStateCopy,
    PresentationStateKind,
    SummaryCount,
    SummaryCountIdentifier,
)

__all__ = [
    "ComparisonContextViewModel",
    "PresentationStateCopy",
    "PresentationStateKind",
    "SummaryCount",
    "SummaryCountIdentifier",
    "presentation_state_copy",
]
