"""Immutable command-centre presentation models."""

from dataclasses import dataclass, field
from enum import Enum


class DashboardCommandCardId(str, Enum):
    PORTFOLIO_SUMMARY = "portfolio_summary"
    PORTFOLIO_HEALTH = "portfolio_health"
    OPPORTUNITY_HIGHLIGHTS = "opportunity_highlights"
    COLLECTION_CHANGES = "collection_changes"
    HISTORICAL_CHANGES = "historical_changes"
    MARKETPLACE_HIGHLIGHTS = "marketplace_highlights"
    RESEARCH_SUMMARY = "research_summary"
    QUICK_ACTIONS = "quick_actions"


class DashboardNavigationTarget(str, Enum):
    PORTFOLIO = "portfolio"
    PORTFOLIO_OPPORTUNITY_ALIGNMENT = "portfolio_opportunity_alignment"
    PORTFOLIO_HISTORY = "portfolio_history"
    PORTFOLIO_RESEARCH = "portfolio_research"
    COLLECTION_EXPLORER = "collection_explorer"
    HISTORICAL_INTELLIGENCE = "historical_intelligence"
    MARKETPLACE_WORKSPACE = "marketplace_workspace"


@dataclass(frozen=True)
class DashboardNavigationAction:
    label: str
    target: DashboardNavigationTarget

    def __post_init__(self):
        if type(self.label) is not str or not self.label:
            raise TypeError("label must be a non-empty string.")
        if type(self.target) is not DashboardNavigationTarget:
            raise TypeError("target must be DashboardNavigationTarget.")


@dataclass(frozen=True)
class DashboardCommandCardViewModel:
    card_id: DashboardCommandCardId
    title: str
    summary: str
    actions: tuple[DashboardNavigationAction, ...]

    def __post_init__(self):
        object.__setattr__(self, "actions", tuple(self.actions))
        if type(self.card_id) is not DashboardCommandCardId:
            raise TypeError("card_id must be DashboardCommandCardId.")
        for name in ("title", "summary"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise TypeError(f"{name} must be a non-empty string.")
        if not self.actions or any(
            type(value) is not DashboardNavigationAction for value in self.actions
        ):
            raise TypeError("actions must contain DashboardNavigationAction values.")


@dataclass(frozen=True)
class DashboardCommandCenterViewModel:
    cards: tuple[DashboardCommandCardViewModel, ...]
    title: str = field(init=False, default="Dashboard")

    def __post_init__(self):
        object.__setattr__(self, "cards", tuple(self.cards))
        if any(type(value) is not DashboardCommandCardViewModel for value in self.cards):
            raise TypeError("cards must contain DashboardCommandCardViewModel values.")
        identifiers = tuple(value.card_id for value in self.cards)
        if identifiers != tuple(DashboardCommandCardId):
            raise ValueError("Dashboard command cards must use canonical order.")


__all__ = [
    "DashboardCommandCardId", "DashboardCommandCardViewModel",
    "DashboardCommandCenterViewModel", "DashboardNavigationAction",
    "DashboardNavigationTarget",
]
