"""Desktop rendering of the immutable Dashboard command centre."""

from dataclasses import dataclass

from dip.experience.dashboard.command_center_models import (
    DashboardCommandCenterViewModel,
    DashboardNavigationAction,
)


@dataclass(frozen=True)
class DesktopDashboardCommandCard:
    title: str
    body: str
    actions: tuple[DashboardNavigationAction, ...]


@dataclass(frozen=True)
class DesktopDashboardCommandCenterView:
    title: str
    cards: tuple[DesktopDashboardCommandCard, ...]


class DesktopDashboardCommandCenterRenderer:
    def render(self, dashboard):
        if type(dashboard) is not DashboardCommandCenterViewModel:
            raise TypeError("dashboard must be DashboardCommandCenterViewModel.")
        return DesktopDashboardCommandCenterView(
            dashboard.title,
            tuple(
                DesktopDashboardCommandCard(card.title, card.summary, card.actions)
                for card in dashboard.cards
            ),
        )


class DesktopDashboardCommandCenterController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopDashboardCommandCenterRenderer()

    def open(self, collection, **supplied):
        return self._renderer.render(
            self._presentation.dashboard(collection, **supplied)
        )


__all__ = [
    "DesktopDashboardCommandCard", "DesktopDashboardCommandCenterController",
    "DesktopDashboardCommandCenterRenderer",
    "DesktopDashboardCommandCenterView",
]
