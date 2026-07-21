"""Immutable, presentation-ready Collection Intelligence Explorer models."""

from __future__ import annotations

from dataclasses import dataclass

from dip.experience.dashboard import (
    DashboardCardState,
    DashboardComponentScore,
    DashboardReleaseViewModel,
)


@dataclass(frozen=True)
class CollectionHealthExplorerViewModel:
    module_id: str
    title: str
    state: DashboardCardState
    overall_health: float | None
    summary: str
    component_scores: tuple[DashboardComponentScore, ...] = ()
    evidence: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class HiddenGemsExplorerViewModel:
    module_id: str
    title: str
    state: DashboardCardState
    total_hidden_gems: int | None
    summary: str
    ranked_releases: tuple[DashboardReleaseViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalIntelligenceExplorerViewModel:
    module_id: str
    title: str
    state: DashboardCardState
    summary: str
    latest_snapshot: str | None = None
    previous_snapshot: str | None = None
    collection_size_change: int | None = None
    collection_value_change: str | None = None
    average_value_change: str | None = None
    median_value_change: str | None = None
    releases_added: int | None = None
    releases_removed: int | None = None
    added_releases: tuple[DashboardReleaseViewModel, ...] = ()
    removed_releases: tuple[DashboardReleaseViewModel, ...] = ()
    top_gainers: tuple[DashboardReleaseViewModel, ...] = ()
    top_decliners: tuple[DashboardReleaseViewModel, ...] = ()
    evidence_coverage: str = ""
    diagnostics: tuple[str, ...] = ()


ExplorerSection = (
    CollectionHealthExplorerViewModel
    | HiddenGemsExplorerViewModel
    | HistoricalIntelligenceExplorerViewModel
)


@dataclass(frozen=True)
class CollectionIntelligenceExplorerViewModel:
    sections: tuple[ExplorerSection, ...] = ()

    def section_for(self, module_id: str) -> ExplorerSection | None:
        return next(
            (
                section
                for section in self.sections
                if section.module_id == module_id
            ),
            None,
        )
