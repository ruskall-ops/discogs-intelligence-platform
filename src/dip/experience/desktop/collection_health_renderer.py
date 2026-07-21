"""Desktop rendering and navigation for Collection Health detail."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from dip.experience.collection_health import (
    CollectionHealthDetailState,
    CollectionHealthDetailViewModel,
)
from dip.experience.dashboard import DashboardHomepageViewModel


class DesktopCollectionHealthSectionId(str, Enum):
    """Stable section identifiers for deterministic desktop rendering."""

    COMPONENTS = "components"
    STRENGTHS = "strengths"
    IMPROVEMENT_OPPORTUNITIES = "improvement_opportunities"
    EVIDENCE = "evidence"
    DIAGNOSTICS = "diagnostics"


@dataclass(frozen=True)
class DesktopCollectionHealthSection:
    """One rendered detail section."""

    section_id: DesktopCollectionHealthSectionId
    title: str
    body: str


@dataclass(frozen=True)
class DesktopCollectionHealthView:
    """Complete desktop-neutral rendering of Collection Health detail."""

    title: str
    state: CollectionHealthDetailState
    headline: str
    summary: str
    sections: tuple[DesktopCollectionHealthSection, ...] = ()


class _CollectionHealthPresentation(Protocol):
    def detail_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> CollectionHealthDetailViewModel: ...


class DesktopCollectionHealthRenderer:
    """Format typed detail without accessing intelligence or persistence."""

    def render(
        self,
        detail: CollectionHealthDetailViewModel,
    ) -> DesktopCollectionHealthView:
        """Render detail sections in one explicit order."""

        if type(detail) is not CollectionHealthDetailViewModel:
            raise TypeError("detail must be a CollectionHealthDetailViewModel.")
        headline = self._headline(detail)
        if detail.state in {
            CollectionHealthDetailState.LOADING,
            CollectionHealthDetailState.UNAVAILABLE,
        }:
            sections: tuple[DesktopCollectionHealthSection, ...] = ()
        else:
            sections = (
                DesktopCollectionHealthSection(
                    DesktopCollectionHealthSectionId.COMPONENTS,
                    "Component scores",
                    self._components(detail),
                ),
                DesktopCollectionHealthSection(
                    DesktopCollectionHealthSectionId.STRENGTHS,
                    "Strengths",
                    self._items(detail.strengths, "No strengths were reported."),
                ),
                DesktopCollectionHealthSection(
                    DesktopCollectionHealthSectionId.IMPROVEMENT_OPPORTUNITIES,
                    "Improvement opportunities",
                    self._items(
                        detail.improvement_opportunities,
                        "No improvement opportunities were reported.",
                    ),
                ),
                DesktopCollectionHealthSection(
                    DesktopCollectionHealthSectionId.EVIDENCE,
                    "Evidence",
                    self._items(detail.evidence, "No evidence was reported."),
                ),
                DesktopCollectionHealthSection(
                    DesktopCollectionHealthSectionId.DIAGNOSTICS,
                    "Diagnostics",
                    self._items(detail.diagnostics, "No diagnostics were reported."),
                ),
            )
        return DesktopCollectionHealthView(
            title=detail.title,
            state=detail.state,
            headline=headline,
            summary=detail.summary,
            sections=sections,
        )

    @staticmethod
    def _headline(detail: CollectionHealthDetailViewModel) -> str:
        if detail.state is CollectionHealthDetailState.LOADING:
            return "Loading"
        if detail.state is CollectionHealthDetailState.UNAVAILABLE:
            return "Unavailable"
        if detail.state is CollectionHealthDetailState.ERROR:
            return "Unable to display complete Collection Health"
        if detail.overall_score is None:
            return "Overall health unavailable"
        return f"Overall health: {detail.overall_score:.1f}/100"

    @staticmethod
    def _components(detail: CollectionHealthDetailViewModel) -> str:
        if not detail.components:
            return "No component scores are available."
        return "\n".join(
            f"• {component.label}: {component.score:.1f}/100"
            for component in detail.components
        )

    @staticmethod
    def _items(items: tuple[str, ...], empty: str) -> str:
        return "\n".join(f"• {item}" for item in items) if items else empty


class DesktopCollectionHealthController:
    """Navigation boundary from Dashboard homepage to Collection Health detail."""

    def __init__(
        self,
        presentation: _CollectionHealthPresentation,
        renderer: DesktopCollectionHealthRenderer | None = None,
    ) -> None:
        self._presentation = presentation
        self._renderer = renderer or DesktopCollectionHealthRenderer()

    def open(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> DesktopCollectionHealthView:
        """Build and render detail from the current homepage model."""

        return self._renderer.render(
            self._presentation.detail_for_homepage(homepage)
        )


__all__ = [
    "DesktopCollectionHealthController",
    "DesktopCollectionHealthRenderer",
    "DesktopCollectionHealthSection",
    "DesktopCollectionHealthSectionId",
    "DesktopCollectionHealthView",
]
