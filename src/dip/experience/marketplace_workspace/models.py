"""Immutable presentation state for Marketplace Workspace workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dip.experience.history_explorer import HistoryExplorerState
from dip.experience.intelligence_insights import IntelligenceInsightCollection
from dip.experience.marketplace_opportunity import MarketplaceOpportunityDetailViewModel


class MarketplaceResearchStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    REVIEWING = "reviewing"
    RESEARCHED = "researched"
    WATCHING = "watching"
    DISMISSED = "dismissed"
    ARCHIVED = "archived"


class MarketplaceWorkspacePane(str, Enum):
    ATTENTION_QUEUE = "attention_queue"
    OPPORTUNITY_DETAIL = "opportunity_detail"
    EVIDENCE = "evidence"
    MARKETPLACE_HISTORY = "marketplace_history"
    PORTFOLIO_CONTEXT = "portfolio_context"
    RESEARCH_STATUS = "research_status"


class MarketplaceWorkspaceAvailability(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class MarketplaceEvidenceSectionViewModel:
    section_id: str
    title: str
    items: tuple[Any, ...]

    def __post_init__(self):
        if type(self.section_id) is not str or not self.section_id:
            raise TypeError("section_id must be a non-empty string.")
        if type(self.title) is not str or not self.title:
            raise TypeError("title must be a non-empty string.")
        object.__setattr__(self, "items", tuple(self.items))


@dataclass(frozen=True)
class MarketplacePortfolioContextViewModel:
    owned: bool
    owned_copies: int
    portfolio_alignment: Any = None
    collection_gap: Any = None
    duplication: Any = None
    concentration_context: Any = None
    coverage: Any = None
    provenance: Any = None

    def __post_init__(self):
        if type(self.owned) is not bool:
            raise TypeError("owned must be a boolean.")
        if type(self.owned_copies) is not int or self.owned_copies < 0:
            raise ValueError("owned_copies must be a non-negative integer.")


@dataclass(frozen=True)
class MarketplaceAttentionItemViewModel:
    release_id: int
    artist: str
    title: str
    label: str | None
    marketplace_assessment: Any
    evidence_state: Any
    opportunity_classification: Any
    insight_summary: str
    reason_codes: tuple[Any, ...]
    diagnostics: tuple[Any, ...]
    history_available: bool
    trend_available: bool
    research_status: MarketplaceResearchStatus
    detail: MarketplaceOpportunityDetailViewModel | None = None
    evidence_sections: tuple[MarketplaceEvidenceSectionViewModel, ...] = ()
    history: HistoryExplorerState | None = None
    insights: tuple[IntelligenceInsightCollection, ...] = ()
    portfolio_context: MarketplacePortfolioContextViewModel | None = None
    provenance: Any = None
    configuration: Any = None

    def __post_init__(self):
        if type(self.release_id) is not int or self.release_id <= 0:
            raise ValueError("release_id must be a positive integer.")
        for name in ("artist", "title", "insight_summary"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise TypeError(f"{name} must be a non-empty string.")
        if type(self.research_status) is not MarketplaceResearchStatus:
            raise TypeError("research_status must be MarketplaceResearchStatus.")
        for name in ("reason_codes", "diagnostics", "evidence_sections", "insights"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class MarketplaceWorkspaceFilters:
    research_status: MarketplaceResearchStatus | None = None
    marketplace_assessment: Any = None
    evidence_state: Any = None
    artist: str | None = None
    label: str | None = None
    owned: bool | None = None
    release_id: int | None = None
    history_available: bool | None = None
    trend_available: bool | None = None


@dataclass(frozen=True)
class MarketplaceWorkspaceState:
    availability: MarketplaceWorkspaceAvailability
    current_pane: MarketplaceWorkspacePane
    queue: tuple[MarketplaceAttentionItemViewModel, ...]
    filtered_queue: tuple[MarketplaceAttentionItemViewModel, ...]
    selected_release_id: int | None
    selected_detail: MarketplaceOpportunityDetailViewModel | None
    selected_evidence_sections: tuple[MarketplaceEvidenceSectionViewModel, ...]
    selected_history: HistoryExplorerState | None
    selected_insights: tuple[IntelligenceInsightCollection, ...]
    selected_portfolio_context: MarketplacePortfolioContextViewModel | None
    filters: MarketplaceWorkspaceFilters
    title: str = field(init=False, default="Marketplace Workspace")

    def __post_init__(self):
        for name in ("queue", "filtered_queue", "selected_evidence_sections", "selected_insights"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if type(self.availability) is not MarketplaceWorkspaceAvailability:
            raise TypeError("availability must be MarketplaceWorkspaceAvailability.")
        if type(self.current_pane) is not MarketplaceWorkspacePane:
            raise TypeError("current_pane must be MarketplaceWorkspacePane.")
        if type(self.filters) is not MarketplaceWorkspaceFilters:
            raise TypeError("filters must be MarketplaceWorkspaceFilters.")
        if self.selected_release_id is not None and self.selected_release_id not in tuple(value.release_id for value in self.filtered_queue):
            raise ValueError("selected_release_id must be present in the filtered queue.")


__all__ = [
    "MarketplaceAttentionItemViewModel", "MarketplaceEvidenceSectionViewModel",
    "MarketplacePortfolioContextViewModel", "MarketplaceResearchStatus",
    "MarketplaceWorkspaceAvailability", "MarketplaceWorkspaceFilters",
    "MarketplaceWorkspacePane", "MarketplaceWorkspaceState",
]
