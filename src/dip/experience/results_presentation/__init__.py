"""Shared factual result-presentation primitives."""

from .copy import presentation_state_copy
from .terminology import (
    FixedPresentationVocabulary,
    PresentationSurface,
    PresentationTerm,
    presentation_label,
    presentation_vocabulary,
)
from .models import (
    ComparisonContextViewModel,
    CURRENT_METADATA_EXPLANATION,
    EvidenceLimitationState,
    INCOMPLETE_EVIDENCE_LIMITATION,
    PresentationStateCopy,
    PresentationStateKind,
    SAFE_ERROR_SUMMARY,
    SummaryCount,
    SummaryCountIdentifier,
    safe_evidence_limitations,
)

__all__ = [
    "ComparisonContextViewModel",
    "CURRENT_METADATA_EXPLANATION",
    "EvidenceLimitationState",
    "INCOMPLETE_EVIDENCE_LIMITATION",
    "PresentationStateCopy",
    "PresentationStateKind",
    "SAFE_ERROR_SUMMARY",
    "SummaryCount",
    "SummaryCountIdentifier",
    "safe_evidence_limitations",
    "presentation_state_copy",
    "FixedPresentationVocabulary",
    "PresentationSurface",
    "PresentationTerm",
    "presentation_label",
    "presentation_vocabulary",
]
