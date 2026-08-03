"""Allowlisted copy for canonical factual presentation states."""

from __future__ import annotations

from .models import PresentationStateCopy, PresentationStateKind


_COPY = {
    PresentationStateKind.AVAILABLE: PresentationStateCopy(
        PresentationStateKind.AVAILABLE,
        "Results available",
        "Results use the comparison shown below.",
    ),
    PresentationStateKind.NO_CHANGES: PresentationStateCopy(
        PresentationStateKind.NO_CHANGES,
        "No changes observed",
        "Comparable values were unchanged between these snapshots.",
    ),
    PresentationStateKind.EMPTY: PresentationStateCopy(
        PresentationStateKind.EMPTY,
        "No matching results",
        "The calculation completed, but no detail rows met this result’s criteria.",
    ),
    PresentationStateKind.PARTIAL: PresentationStateCopy(
        PresentationStateKind.PARTIAL,
        "Partial evidence",
        "Some supplied evidence was incomplete; available comparisons remain shown.",
    ),
    PresentationStateKind.INSUFFICIENT_HISTORY: PresentationStateCopy(
        PresentationStateKind.INSUFFICIENT_HISTORY,
        "More history required",
        "Two compatible snapshots captured at different times are required.",
    ),
    PresentationStateKind.INSUFFICIENT_DATA: PresentationStateCopy(
        PresentationStateKind.INSUFFICIENT_DATA,
        "No comparable facts",
        "A compatible snapshot pair exists, but it contains no comparable facts for this result.",
    ),
    PresentationStateKind.STALE: PresentationStateCopy(
        PresentationStateKind.STALE,
        "Newer history is available",
        "These cached results predate the latest completed Collector Run.",
        "Refresh Marketplace Changes",
    ),
    PresentationStateKind.UNAVAILABLE: PresentationStateCopy(
        PresentationStateKind.UNAVAILABLE,
        "Not available",
        "This destination has no production data path in this release.",
    ),
    PresentationStateKind.ERROR: PresentationStateCopy(
        PresentationStateKind.ERROR,
        "Results could not be displayed",
        "Saved data was not changed. Previous results remain available where shown.",
        "Retry",
    ),
    PresentationStateKind.NO_IMPORTED_COLLECTION: PresentationStateCopy(
        PresentationStateKind.NO_IMPORTED_COLLECTION,
        "Import a collection to begin",
        "No Current Collection releases are available.",
        "Import Collection CSV",
    ),
    PresentationStateKind.IMPORTED_NOT_ANALYSED: PresentationStateCopy(
        PresentationStateKind.IMPORTED_NOT_ANALYSED,
        "Collection imported",
        "Imported collection facts are available. No completed Collector Run intelligence is available yet.",
        "Run Collector Update",
    ),
    PresentationStateKind.POST_IMPORT_DISPLAY_WARNING: PresentationStateCopy(
        PresentationStateKind.POST_IMPORT_DISPLAY_WARNING,
        "Import saved; display refresh failed",
        "The import committed successfully, but the display could not be refreshed.",
        "Reopen view",
    ),
}

if set(_COPY) != set(PresentationStateKind):
    raise RuntimeError("Canonical presentation-state copy must be exhaustive.")


def presentation_state_copy(kind: PresentationStateKind) -> PresentationStateCopy:
    """Return fixed immutable copy for one typed state."""

    if type(kind) is not PresentationStateKind:
        raise TypeError("kind must be a PresentationStateKind.")
    return _COPY[kind]


__all__ = ["presentation_state_copy"]
