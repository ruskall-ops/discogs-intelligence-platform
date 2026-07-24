"""Desktop rendering and navigation for Hidden Gems detail."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dip.experience.dashboard import (
    DashboardHiddenGemsViewModel,
    DashboardHomepageConsistencyError,
    DashboardHomepageViewModel,
    DashboardSectionId,
    DashboardSectionState,
)
from dip.experience.hidden_gems import (
    HiddenGemMetricViewModel,
    HiddenGemReleaseViewModel,
    HiddenGemsDetailState,
    HiddenGemsDetailViewModel,
)


@dataclass(frozen=True)
class DesktopHiddenGemCandidate:
    """One rendered candidate in its established rank position."""

    rank: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopHiddenGemsView:
    """Complete desktop-neutral rendering of Hidden Gems detail."""

    title: str
    state: HiddenGemsDetailState
    headline: str
    summary: str
    candidates: tuple[DesktopHiddenGemCandidate, ...] = ()
    diagnostics: str = ""


class _HiddenGemsPresentation(Protocol):
    def detail_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> HiddenGemsDetailViewModel: ...


class DesktopHiddenGemsRenderer:
    """Format typed detail without accessing intelligence or persistence."""

    def render(self, detail: HiddenGemsDetailViewModel) -> DesktopHiddenGemsView:
        """Render all candidates in their supplied canonical order."""

        if type(detail) is not HiddenGemsDetailViewModel:
            raise TypeError("detail must be a HiddenGemsDetailViewModel.")
        if detail.state in {
            HiddenGemsDetailState.LOADING,
            HiddenGemsDetailState.EMPTY,
            HiddenGemsDetailState.UNAVAILABLE,
        }:
            candidates: tuple[DesktopHiddenGemCandidate, ...] = ()
        else:
            candidates = tuple(self._candidate(candidate) for candidate in detail.candidates)
        diagnostics = self._items(detail.diagnostics, "")
        return DesktopHiddenGemsView(
            title=detail.title,
            state=detail.state,
            headline=self._headline(detail),
            summary=detail.summary,
            candidates=candidates,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _headline(detail: HiddenGemsDetailViewModel) -> str:
        if detail.state is HiddenGemsDetailState.LOADING:
            return "Loading"
        if detail.state is HiddenGemsDetailState.EMPTY:
            return "No Hidden Gems found"
        if detail.state is HiddenGemsDetailState.UNAVAILABLE:
            return "Unavailable"
        if detail.state is HiddenGemsDetailState.ERROR:
            return "Unable to display complete Hidden Gems"
        if detail.state is HiddenGemsDetailState.PARTIAL:
            return f"{detail.candidate_count} Hidden Gems · some values unavailable"
        return f"{detail.candidate_count} Hidden Gems"

    @classmethod
    def _candidate(
        cls,
        candidate: HiddenGemReleaseViewModel,
    ) -> DesktopHiddenGemCandidate:
        body = "\n\n".join(
            (
                f"Hidden Gem score: {cls._score(candidate.score)}",
                candidate.explanation,
                "Factor scores\n" + cls._metrics(candidate.factor_scores, scores=True),
                "Supporting metrics\n" + cls._metrics(candidate.supporting_metrics),
                "Evidence\n" + cls._items(
                    candidate.evidence,
                    "No evidence was reported.",
                ),
            )
        )
        return DesktopHiddenGemCandidate(
            rank=candidate.rank,
            heading=f"#{candidate.rank} · {candidate.artist} — {candidate.title}",
            body=body,
        )

    @classmethod
    def _metrics(
        cls,
        metrics: tuple[HiddenGemMetricViewModel, ...],
        *,
        scores: bool = False,
    ) -> str:
        if not metrics:
            return "No values were reported."
        return "\n".join(
            f"• {metric.label}: {cls._score(metric.value) if scores else cls._number(metric.value)}"
            for metric in metrics
        )

    @staticmethod
    def _score(value: float | None) -> str:
        return "Unavailable" if value is None else f"{value:.1f}/100"

    @staticmethod
    def _number(value: float | None) -> str:
        if value is None:
            return "Unavailable"
        return f"{value:,.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _items(items: tuple[str, ...], empty: str) -> str:
        return "\n".join(f"• {item}" for item in items) if items else empty


class DesktopHiddenGemsController:
    """Navigation boundary from Dashboard homepage to Hidden Gems detail."""

    def __init__(
        self,
        presentation: _HiddenGemsPresentation,
        renderer: DesktopHiddenGemsRenderer | None = None,
    ) -> None:
        self._presentation = presentation
        self._renderer = renderer or DesktopHiddenGemsRenderer()

    @staticmethod
    def can_open(homepage: DashboardHomepageViewModel) -> bool:
        """Return whether the current homepage offers meaningful detail."""

        if type(homepage) is not DashboardHomepageViewModel:
            raise TypeError("homepage must be a DashboardHomepageViewModel.")
        section = homepage.section_for(DashboardSectionId.HIDDEN_GEMS)
        if type(section) is not DashboardHiddenGemsViewModel:
            raise DashboardHomepageConsistencyError(
                "The homepage does not contain a Hidden Gems section."
            )
        return section.state in {
            DashboardSectionState.AVAILABLE,
            DashboardSectionState.EMPTY,
            DashboardSectionState.ERROR,
        }

    def open(
        self,
        homepage: DashboardHomepageViewModel,
    ) -> DesktopHiddenGemsView:
        """Build and render detail from the current homepage model."""

        return self._renderer.render(self._presentation.detail_for_homepage(homepage))


__all__ = [
    "DesktopHiddenGemCandidate",
    "DesktopHiddenGemsController",
    "DesktopHiddenGemsRenderer",
    "DesktopHiddenGemsView",
]
