"""Desktop-neutral rendering and navigation for the Collection Explorer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dip.experience.dashboard import (
    DashboardHomepageConsistencyError,
    DashboardHomepageViewModel,
    DashboardSectionId,
    DashboardSectionState,
)
from dip.experience.explorer import (
    CollectionExplorerDestination,
    CollectionExplorerState,
    CollectionExplorerViewModel,
)
from dip.intelligence import IntelligenceResult

from .collection_health_renderer import DesktopCollectionHealthRenderer
from .collection_trends_renderer import DesktopCollectionTrendsRenderer
from .hidden_gems_renderer import DesktopHiddenGemsRenderer
from .weekend_listings_renderer import DesktopWeekendListingsRenderer


@dataclass(frozen=True)
class DesktopCollectionExplorerNavigationItem:
    """One rendered navigation item in deterministic destination order."""

    destination: CollectionExplorerDestination
    label: str
    state: CollectionExplorerState
    selected: bool


@dataclass(frozen=True)
class DesktopCollectionExplorerSection:
    """One complete scrollable destination body."""

    destination: CollectionExplorerDestination
    title: str
    state: CollectionExplorerState
    body: str


@dataclass(frozen=True)
class DesktopCollectionExplorerView:
    """Desktop-ready unified Explorer built once for one homepage result."""

    title: str
    state: CollectionExplorerState
    selected_destination: CollectionExplorerDestination
    navigation: tuple[DesktopCollectionExplorerNavigationItem, ...]
    sections: tuple[DesktopCollectionExplorerSection, ...]


class _CollectionExplorerPresentation(Protocol):
    def explorer_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
        *,
        selected_destination: CollectionExplorerDestination,
        weekend_listings_result: IntelligenceResult | None = None,
    ) -> CollectionExplorerViewModel: ...


class DesktopCollectionExplorerRenderer:
    """Render composed Explorer models without querying or recalculating."""

    def __init__(
        self,
        collection_health: DesktopCollectionHealthRenderer | None = None,
        hidden_gems: DesktopHiddenGemsRenderer | None = None,
        collection_trends: DesktopCollectionTrendsRenderer | None = None,
        weekend_listings: DesktopWeekendListingsRenderer | None = None,
    ) -> None:
        self._collection_health = (
            collection_health or DesktopCollectionHealthRenderer()
        )
        self._hidden_gems = hidden_gems or DesktopHiddenGemsRenderer()
        self._collection_trends = collection_trends or DesktopCollectionTrendsRenderer()
        self._weekend_listings = weekend_listings or DesktopWeekendListingsRenderer()

    def render(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerView:
        """Render all five destinations once in their validated order."""

        if type(explorer) is not CollectionExplorerViewModel:
            raise TypeError("explorer must be a CollectionExplorerViewModel.")
        navigation = tuple(
            DesktopCollectionExplorerNavigationItem(
                destination=item.destination,
                label=item.label,
                state=item.state,
                selected=item.destination is explorer.selected_destination,
            )
            for item in explorer.destinations
        )
        sections = (
            DesktopCollectionExplorerSection(
                destination=CollectionExplorerDestination.OVERVIEW,
                title="Overview",
                state=explorer.overview.state,
                body=self._overview(explorer),
            ),
            self._health(explorer),
            self._gems(explorer),
            self._trends(explorer),
            self._weekend(explorer),
        )
        return DesktopCollectionExplorerView(
            title=explorer.title,
            state=explorer.state,
            selected_destination=explorer.selected_destination,
            navigation=navigation,
            sections=sections,
        )

    @staticmethod
    def _overview(explorer: CollectionExplorerViewModel) -> str:
        overview = explorer.overview
        lines = [
            _state_heading(overview.state),
            overview.summary,
        ]
        if overview.state is CollectionExplorerState.AVAILABLE:
            lines.extend(
                (
                    "",
                    "Current collection intelligence",
                    f"Collection size: {_count(overview.collection_size)}",
                    (
                        "Execution status: "
                        f"{overview.execution_status.value.title()}"
                    ),
                    (
                        "Completed modules: "
                        f"{overview.completed_module_count}/"
                        f"{overview.total_module_count}"
                    ),
                    f"Latest execution: {_date(overview.executed_at)}",
                    f"Run ID: {overview.run_id}",
                    f"Engine version: {overview.engine_version or 'Unavailable'}",
                    (
                        "Collection Health: "
                        f"{_score(overview.collection_health_score)}"
                    ),
                    f"Hidden Gems: {_count(overview.hidden_gems_count)}",
                )
            )
        lines.extend(
            (
                "",
                "Recent comparison",
                (
                    "Status: "
                    f"{overview.comparison_state.value.replace('_', ' ').title()}"
                ),
                overview.comparison_summary,
            )
        )
        return "\n".join(lines)

    def _health(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerSection:
        rendered = self._collection_health.render(explorer.collection_health)
        parts = [rendered.headline, rendered.summary]
        for section in rendered.sections:
            parts.extend(("", section.title, section.body))
        return DesktopCollectionExplorerSection(
            destination=CollectionExplorerDestination.COLLECTION_HEALTH,
            title=rendered.title,
            state=CollectionExplorerState(rendered.state.value),
            body="\n".join(parts),
        )

    def _gems(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerSection:
        rendered = self._hidden_gems.render(explorer.hidden_gems)
        parts = [rendered.headline, rendered.summary]
        for candidate in rendered.candidates:
            parts.extend(("", candidate.heading, candidate.body))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            destination=CollectionExplorerDestination.HIDDEN_GEMS,
            title=rendered.title,
            state=CollectionExplorerState(rendered.state.value),
            body="\n".join(parts),
        )

    def _trends(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerSection:
        rendered = self._collection_trends.render(explorer.collection_trends)
        parts = [rendered.headline]
        if rendered.comparison:
            parts.extend(("", "Comparing", rendered.comparison))
        for metric in rendered.metrics:
            parts.extend(("", metric.heading, metric.body))
        if rendered.messages:
            parts.extend(("", "Messages", rendered.messages))
        return DesktopCollectionExplorerSection(
            destination=CollectionExplorerDestination.COLLECTION_TRENDS,
            title=rendered.title,
            state=CollectionExplorerState(rendered.state.value),
            body="\n".join(parts),
        )

    def _weekend(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerSection:
        rendered = self._weekend_listings.render(explorer.weekend_listings)
        parts = [rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "Observation context", rendered.context))
        for candidate in rendered.candidates:
            parts.extend(("", candidate.heading, candidate.body))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            destination=CollectionExplorerDestination.WEEKEND_LISTINGS,
            title=rendered.title,
            state=CollectionExplorerState(rendered.state.value),
            body="\n".join(parts),
        )


class DesktopCollectionExplorerController:
    """Open one cached Explorer model from the current homepage source."""

    def __init__(
        self,
        presentation: _CollectionExplorerPresentation,
        renderer: DesktopCollectionExplorerRenderer | None = None,
    ) -> None:
        self._presentation = presentation
        self._renderer = renderer or DesktopCollectionExplorerRenderer()

    @staticmethod
    def can_open(homepage: DashboardHomepageViewModel) -> bool:
        """Reject only stale/loading homepage models at the navigation boundary."""

        if type(homepage) is not DashboardHomepageViewModel:
            raise TypeError("homepage must be a DashboardHomepageViewModel.")
        overview = homepage.section_for(DashboardSectionId.COLLECTION_OVERVIEW)
        if overview is None:
            raise DashboardHomepageConsistencyError(
                "The homepage does not contain a Collection overview section."
            )
        return overview.state is not DashboardSectionState.LOADING

    def open(
        self,
        homepage: DashboardHomepageViewModel,
        *,
        selected_destination: CollectionExplorerDestination = (
            CollectionExplorerDestination.OVERVIEW
        ),
        weekend_listings_result: IntelligenceResult | None = None,
    ) -> DesktopCollectionExplorerView:
        """Build and render one Explorer; tab changes need no further service call."""

        if weekend_listings_result is None:
            explorer = self._presentation.explorer_for_homepage(
                homepage,
                selected_destination=selected_destination,
            )
        else:
            explorer = self._presentation.explorer_for_homepage(
                homepage,
                selected_destination=selected_destination,
                weekend_listings_result=weekend_listings_result,
            )
        return self._renderer.render(explorer)


def _state_heading(state: CollectionExplorerState) -> str:
    labels = {
        CollectionExplorerState.LOADING: "Loading",
        CollectionExplorerState.AVAILABLE: "Available",
        CollectionExplorerState.PARTIAL: "Partially available",
        CollectionExplorerState.EMPTY: "No intelligence history",
        CollectionExplorerState.UNAVAILABLE: "Unavailable",
        CollectionExplorerState.ERROR: "Unable to display",
    }
    return labels[state]


def _count(value: int | None) -> str:
    return "Unavailable" if value is None else f"{value:,}"


def _score(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:.1f}/100"


def _date(value) -> str:
    return value.strftime("%d %b %Y %H:%M") if value is not None else "Unavailable"


__all__ = [
    "DesktopCollectionExplorerController",
    "DesktopCollectionExplorerNavigationItem",
    "DesktopCollectionExplorerRenderer",
    "DesktopCollectionExplorerSection",
    "DesktopCollectionExplorerView",
]
