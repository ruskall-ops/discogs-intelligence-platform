"""Immutable presentation-only state for the History Explorer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dip.experience.intelligence_change_analysis import IntelligenceChangeAnalysisViewModel
from dip.experience.intelligence_trend_analysis import IntelligenceTrendAnalysisViewModel


class HistoryExplorerPane(str, Enum):
    TIMELINE = "timeline"
    SNAPSHOT = "snapshot"
    CHANGE = "change"
    TREND = "trend"
    DETAILS = "details"


class HistoryExplorerAvailability(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class HistoricalSnapshotViewModel:
    observation_number: int
    module_id: str
    module_version: str
    rule_set_version: str
    snapshot_identity: int | None
    portfolio_identity: Any
    assessment: Any
    evidence: Any
    metrics: tuple[Any, ...] = ()
    reasons: tuple[Any, ...] = ()
    diagnostics: tuple[Any, ...] = ()
    provenance: Any = None
    configuration: Any = None
    history_identity: Any = None

    def __post_init__(self):
        if type(self.observation_number) is not int or self.observation_number <= 0:
            raise ValueError("observation_number must be a positive integer.")
        for name in ("module_id", "module_version", "rule_set_version"):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise TypeError(f"{name} must be a non-empty string.")
        for name in ("metrics", "reasons", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class HistoryExplorerFilters:
    observation_number: int | None = None
    module_id: str | None = None
    module_version: str | None = None
    rule_set_version: str | None = None
    portfolio_identity: Any = None
    snapshot_identity: int | None = None


@dataclass(frozen=True)
class HistoryExplorerState:
    availability: HistoryExplorerAvailability
    current_pane: HistoryExplorerPane
    observations: tuple[HistoricalSnapshotViewModel, ...]
    changes: tuple[IntelligenceChangeAnalysisViewModel, ...]
    trends: tuple[IntelligenceTrendAnalysisViewModel, ...]
    filters: HistoryExplorerFilters
    selected_observation: int | None = None
    selected_transition: int | None = None
    selected_trend: int | None = None
    history_available: bool = True
    title: str = field(init=False, default="History Explorer")

    def __post_init__(self):
        for name in ("observations", "changes", "trends"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if type(self.availability) is not HistoryExplorerAvailability:
            raise TypeError("availability must be HistoryExplorerAvailability.")
        if type(self.current_pane) is not HistoryExplorerPane:
            raise TypeError("current_pane must be HistoryExplorerPane.")
        if type(self.filters) is not HistoryExplorerFilters:
            raise TypeError("filters must be HistoryExplorerFilters.")
        if self.selected_observation is not None and not 0 <= self.selected_observation < len(self.observations):
            raise ValueError("selected_observation is outside the filtered observations.")
        if self.selected_transition is not None and not 0 <= self.selected_transition < len(self.changes):
            raise ValueError("selected_transition is outside the supplied changes.")
        if self.selected_trend is not None and not 0 <= self.selected_trend < len(self.trends):
            raise ValueError("selected_trend is outside the supplied trends.")


__all__ = [
    "HistoricalSnapshotViewModel", "HistoryExplorerAvailability",
    "HistoryExplorerFilters", "HistoryExplorerPane", "HistoryExplorerState",
]
