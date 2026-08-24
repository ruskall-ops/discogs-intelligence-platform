"""Closed presentation terminology shared by screens and legacy exports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class PresentationSurface(str, Enum):
    """Fixed destinations whose truthful labels may intentionally differ."""

    SCREEN = "screen"
    LEGACY_MARKDOWN = "legacy_markdown"
    LEGACY_EXCEL = "legacy_excel"


class PresentationTerm(str, Enum):
    """Closed semantic identifiers for potentially ambiguous visible phrases."""

    PREVIOUS_SNAPSHOT = "previous_snapshot"
    LATEST_SNAPSHOT = "latest_snapshot"
    CURRENT_CATALOGUE_METADATA = "current_catalogue_metadata"
    CURRENT_COLLECTION_LABELS = "current_collection_labels"
    COLLECTOR_RUN = "collector_run"
    MARKETPLACE_CHANGES = "marketplace_changes"
    PRICE_CHANGES = "price_changes"
    SUPPLY_CHANGES = "supply_changes"
    LISTING_PRICE_CHANGES = "listing_price_changes"
    MARKETPLACE_ACTIVITY = "marketplace_activity"
    LEGACY_COLLECTOR_RUN_ANALYSIS = "legacy_collector_run_analysis"
    LEGACY_COLLECTOR_RUN_REVIEW_ANALYSIS = (
        "legacy_collector_run_review_analysis"
    )


@dataclass(frozen=True)
class FixedPresentationVocabulary:
    """One immutable, exhaustive surface mapping for a semantic term."""

    term: PresentationTerm
    labels: tuple[tuple[PresentationSurface, str], ...]

    def __post_init__(self) -> None:
        if type(self.term) is not PresentationTerm:
            raise TypeError("term must be a PresentationTerm.")
        labels = tuple(self.labels)
        object.__setattr__(self, "labels", labels)
        if any(
            type(surface) is not PresentationSurface
            or not isinstance(label, str)
            or not label
            or label.strip() != label
            for surface, label in labels
        ):
            raise ValueError("labels must contain fixed trimmed non-empty copy.")
        if tuple(surface for surface, _label in labels) != tuple(
            PresentationSurface
        ):
            raise ValueError("labels must exhaust surfaces in canonical order.")

    def label_for(self, surface: PresentationSurface) -> str:
        if type(surface) is not PresentationSurface:
            raise TypeError("surface must be a PresentationSurface.")
        return dict(self.labels)[surface]


def _entry(
    term: PresentationTerm,
    screen: str,
    legacy_markdown: str | None = None,
    legacy_excel: str | None = None,
) -> FixedPresentationVocabulary:
    return FixedPresentationVocabulary(
        term,
        (
            (PresentationSurface.SCREEN, screen),
            (
                PresentationSurface.LEGACY_MARKDOWN,
                screen if legacy_markdown is None else legacy_markdown,
            ),
            (
                PresentationSurface.LEGACY_EXCEL,
                screen if legacy_excel is None else legacy_excel,
            ),
        ),
    )


_VOCABULARY = MappingProxyType(
    {
        value.term: value
        for value in (
            _entry(PresentationTerm.PREVIOUS_SNAPSHOT, "Previous snapshot"),
            _entry(PresentationTerm.LATEST_SNAPSHOT, "Latest snapshot"),
            _entry(
                PresentationTerm.CURRENT_CATALOGUE_METADATA,
                "Current catalogue metadata",
            ),
            _entry(
                PresentationTerm.CURRENT_COLLECTION_LABELS,
                "Current collection labels",
            ),
            _entry(PresentationTerm.COLLECTOR_RUN, "Collector Run"),
            _entry(PresentationTerm.MARKETPLACE_CHANGES, "Marketplace Changes"),
            _entry(
                PresentationTerm.PRICE_CHANGES,
                "Price Changes",
                "Price Changes 2.0",
                "Price Changes 2.0",
            ),
            _entry(
                PresentationTerm.SUPPLY_CHANGES,
                "Supply Changes",
                "Supply Changes 2.0",
                "Supply Changes 2.0",
            ),
            _entry(
                PresentationTerm.LISTING_PRICE_CHANGES,
                "Listing Price Changes 1.0",
            ),
            _entry(
                PresentationTerm.MARKETPLACE_ACTIVITY,
                "Marketplace Activity 1.0",
            ),
            _entry(
                PresentationTerm.LEGACY_COLLECTOR_RUN_ANALYSIS,
                "Legacy Collector Run analysis",
            ),
            _entry(
                PresentationTerm.LEGACY_COLLECTOR_RUN_REVIEW_ANALYSIS,
                "Legacy Collector Run review analysis",
            ),
        )
    }
)

if set(_VOCABULARY) != set(PresentationTerm):
    raise RuntimeError("Presentation terminology must be exhaustive.")


def presentation_vocabulary(
    term: PresentationTerm,
) -> FixedPresentationVocabulary:
    """Return one fixed vocabulary value without accepting rendered strings."""

    if type(term) is not PresentationTerm:
        raise TypeError("term must be a PresentationTerm.")
    return _VOCABULARY[term]


def presentation_label(
    term: PresentationTerm,
    surface: PresentationSurface = PresentationSurface.SCREEN,
) -> str:
    """Return exhaustive fixed copy for a typed term and surface."""

    return presentation_vocabulary(term).label_for(surface)


__all__ = [
    "FixedPresentationVocabulary",
    "PresentationSurface",
    "PresentationTerm",
    "presentation_label",
    "presentation_vocabulary",
]
