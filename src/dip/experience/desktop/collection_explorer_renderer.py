"""Desktop-neutral rendering and navigation for the Collection Explorer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol
from dip.app.marketplace_change_workspace import MarketplaceChangeOutcomeReason, MarketplaceChangeWorkspace, MarketplaceChangeWorkspaceState

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
    MarketplaceChangePresentationOutcome,
)
from dip.experience.explorer.state_adapter import marketplace_outcome_state_kind
from dip.experience.results_presentation import presentation_state_copy
from dip.intelligence import IntelligenceResult

from .collection_health_renderer import DesktopCollectionHealthRenderer
from .collection_trends_renderer import DesktopCollectionTrendsRenderer
from .hidden_gems_renderer import DesktopHiddenGemsRenderer
from .price_changes_renderer import DesktopPriceChangesRenderer
from .supply_changes_renderer import DesktopSupplyChangesRenderer
from .rare_appearances_renderer import DesktopRareAppearancesRenderer
from .marketplace_activity_renderer import DesktopMarketplaceActivityRenderer
from .listing_lifecycle_renderer import DesktopListingLifecycleRenderer
from .marketplace_momentum_renderer import DesktopMarketplaceMomentumRenderer
from .marketplace_stability_renderer import DesktopMarketplaceStabilityRenderer
from .marketplace_scarcity_renderer import DesktopMarketplaceScarcityRenderer
from .marketplace_opportunity_renderer import DesktopMarketplaceOpportunityRenderer
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
    marketplace_change_outcome: MarketplaceChangePresentationOutcome | None = None


class _CollectionExplorerPresentation(Protocol):
    def explorer_for_homepage(
        self,
        homepage: DashboardHomepageViewModel,
        *,
        selected_destination: CollectionExplorerDestination,
        weekend_listings_result: IntelligenceResult | None = None,
        price_changes_result: IntelligenceResult | None = None,
        supply_changes_result: IntelligenceResult | None = None,
        rare_appearances_result: IntelligenceResult | None = None,
        marketplace_activity_result: IntelligenceResult | None = None,
        listing_lifecycle_result: IntelligenceResult | None = None,
        marketplace_momentum_result: IntelligenceResult | None = None,
        marketplace_stability_result: IntelligenceResult | None = None,
        marketplace_scarcity_result: IntelligenceResult | None = None,
        marketplace_opportunity_result: IntelligenceResult | None = None,
    ) -> CollectionExplorerViewModel: ...


class _MarketplaceChangeWorkspaceService(Protocol):
    def build(self) -> MarketplaceChangeWorkspace: ...


class DesktopCollectionExplorerRenderer:
    """Render composed Explorer models without querying or recalculating."""

    def __init__(
        self,
        collection_health: DesktopCollectionHealthRenderer | None = None,
        hidden_gems: DesktopHiddenGemsRenderer | None = None,
        collection_trends: DesktopCollectionTrendsRenderer | None = None,
        weekend_listings: DesktopWeekendListingsRenderer | None = None,
        price_changes: DesktopPriceChangesRenderer | None = None,
        supply_changes: DesktopSupplyChangesRenderer | None = None,
        rare_appearances: DesktopRareAppearancesRenderer | None = None,
        marketplace_activity: DesktopMarketplaceActivityRenderer | None = None,
        listing_lifecycle: DesktopListingLifecycleRenderer | None = None,
        marketplace_momentum: DesktopMarketplaceMomentumRenderer | None = None,
        marketplace_stability: DesktopMarketplaceStabilityRenderer | None = None,
        marketplace_scarcity: DesktopMarketplaceScarcityRenderer | None = None,
        marketplace_opportunity: DesktopMarketplaceOpportunityRenderer | None = None,
    ) -> None:
        self._collection_health = (
            collection_health or DesktopCollectionHealthRenderer()
        )
        self._hidden_gems = hidden_gems or DesktopHiddenGemsRenderer()
        self._collection_trends = collection_trends or DesktopCollectionTrendsRenderer()
        self._weekend_listings = weekend_listings or DesktopWeekendListingsRenderer()
        self._price_changes = price_changes or DesktopPriceChangesRenderer()
        self._supply_changes = supply_changes or DesktopSupplyChangesRenderer()
        self._rare_appearances = rare_appearances or DesktopRareAppearancesRenderer()
        self._marketplace_activity = marketplace_activity or DesktopMarketplaceActivityRenderer()
        self._listing_lifecycle = listing_lifecycle or DesktopListingLifecycleRenderer()
        self._marketplace_momentum = (
            marketplace_momentum or DesktopMarketplaceMomentumRenderer()
        )
        self._marketplace_stability = (
            marketplace_stability or DesktopMarketplaceStabilityRenderer()
        )
        self._marketplace_scarcity = marketplace_scarcity or DesktopMarketplaceScarcityRenderer()
        self._marketplace_opportunity = marketplace_opportunity or DesktopMarketplaceOpportunityRenderer()

    def render(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerView:
        """Render all destinations once in their validated order."""

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
            self._price(explorer),
            self._supply(explorer),
            self._rare(explorer),
            self._activity(explorer),
            self._lifecycle(explorer),
            self._momentum(explorer),
            self._stability(explorer),
            self._scarcity(explorer),
            self._opportunity(explorer),
        )
        return DesktopCollectionExplorerView(
            title=explorer.title,
            state=explorer.state,
            selected_destination=explorer.selected_destination,
            navigation=navigation,
            sections=sections,
            marketplace_change_outcome=explorer.marketplace_change_outcome,
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

    def _price(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerSection:
        rendered = self._price_changes.render(explorer.price_changes)
        parts = [_marketplace_outcome_copy(explorer.marketplace_change_outcome) or rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "Comparison context", rendered.context))
        if rendered.counts:
            parts.extend(("", "Comparison counts", rendered.counts))
        if rendered.listing_changes:
            parts.extend(("", "Listing changes"))
            for change in rendered.listing_changes:
                parts.extend(("", change.heading, change.body))
        if rendered.release_changes:
            parts.extend(("", "Release-level changes"))
            for change in rendered.release_changes:
                parts.extend(("", change.heading, change.body))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            destination=CollectionExplorerDestination.PRICE_CHANGES,
            title=rendered.title,
            state=CollectionExplorerState(rendered.state.value),
            body="\n".join(parts),
        )

    def _supply(self, explorer: CollectionExplorerViewModel) -> DesktopCollectionExplorerSection:
        rendered = self._supply_changes.render(explorer.supply_changes)
        parts = [_marketplace_outcome_copy(explorer.marketplace_change_outcome) or rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "Comparison context", rendered.context))
        if rendered.counts:
            parts.extend(("", "Comparison counts", rendered.counts))
        for change in rendered.changes:
            parts.extend(("", change.heading, change.body))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            CollectionExplorerDestination.SUPPLY_CHANGES,
            rendered.title,
            CollectionExplorerState(rendered.state.value),
            "\n".join(parts),
        )

    def _rare(self, explorer: CollectionExplorerViewModel) -> DesktopCollectionExplorerSection:
        rendered = self._rare_appearances.render(explorer.rare_appearances)
        parts = [rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "History context", rendered.context))
        for appearance in rendered.appearances:
            parts.extend(("", appearance.heading, appearance.body))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(CollectionExplorerDestination.RARE_APPEARANCES, rendered.title, CollectionExplorerState(rendered.state.value), "\n".join(parts))

    def _activity(self, explorer: CollectionExplorerViewModel) -> DesktopCollectionExplorerSection:
        rendered = self._marketplace_activity.render(explorer.marketplace_activity)
        parts = [rendered.headline, rendered.summary]
        if rendered.counts:
            parts.extend(("", "Activity counts", rendered.counts))
        for activity in rendered.activities:
            parts.extend(("", activity.heading, activity.body))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(CollectionExplorerDestination.MARKETPLACE_ACTIVITY, rendered.title, CollectionExplorerState(rendered.state.value), "\n".join(parts))

    def _lifecycle(self, explorer: CollectionExplorerViewModel) -> DesktopCollectionExplorerSection:
        rendered = self._listing_lifecycle.render(explorer.listing_lifecycle)
        parts = [rendered.headline, rendered.summary]
        if rendered.counts:
            parts.extend(("", "Lifecycle counts", rendered.counts))
        for lifecycle in rendered.lifecycles:
            parts.extend(("", lifecycle.heading, lifecycle.body))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(CollectionExplorerDestination.LISTING_LIFECYCLE, rendered.title, CollectionExplorerState(rendered.state.value), "\n".join(parts))

    def _momentum(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerSection:
        rendered = self._marketplace_momentum.render(
            explorer.marketplace_momentum
        )
        parts = [rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "Assessment context", rendered.context))
        for release in rendered.releases:
            parts.extend(("", release.heading, release.body))
        if rendered.source_provenance:
            parts.extend(("", "Source provenance", rendered.source_provenance))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            CollectionExplorerDestination.MARKETPLACE_MOMENTUM,
            rendered.title,
            CollectionExplorerState(rendered.state.value),
            "\n".join(parts),
        )

    def _stability(
        self,
        explorer: CollectionExplorerViewModel,
    ) -> DesktopCollectionExplorerSection:
        rendered = self._marketplace_stability.render(explorer.marketplace_stability)
        parts = [rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "Assessment context", rendered.context))
        for release in rendered.releases:
            parts.extend(("", release.heading, release.body))
        if rendered.source_provenance:
            parts.extend(("", "Source provenance", rendered.source_provenance))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            CollectionExplorerDestination.MARKETPLACE_STABILITY,
            rendered.title,
            CollectionExplorerState(rendered.state.value),
            "\n".join(parts),
        )

    def _scarcity(self, explorer):
        rendered = self._marketplace_scarcity.render(explorer.marketplace_scarcity)
        parts = [rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "Assessment context", rendered.context))
        for release in rendered.releases:
            parts.extend(("", release.heading, release.body))
        if rendered.source_provenance:
            parts.extend(("", "Source provenance", rendered.source_provenance))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            CollectionExplorerDestination.MARKETPLACE_SCARCITY,
            rendered.title,
            CollectionExplorerState(rendered.state.value),
            "\n".join(parts),
        )

    def _opportunity(self, explorer):
        rendered = self._marketplace_opportunity.render(explorer.marketplace_opportunity)
        parts = [rendered.headline, rendered.summary]
        if rendered.context:
            parts.extend(("", "Synthesis context", rendered.context))
        for release in rendered.releases:
            parts.extend(("", release.heading, release.body))
        if rendered.source_provenance:
            parts.extend(("", "Source provenance", rendered.source_provenance))
        if rendered.diagnostics:
            parts.extend(("", "Diagnostics", rendered.diagnostics))
        return DesktopCollectionExplorerSection(
            CollectionExplorerDestination.MARKETPLACE_OPPORTUNITY,
            rendered.title,
            CollectionExplorerState(rendered.state.value),
            "\n".join(parts),
        )


class DesktopCollectionExplorerController:
    """Open one cached Explorer model from the current homepage source."""

    def __init__(
        self,
        presentation: _CollectionExplorerPresentation,
        renderer: DesktopCollectionExplorerRenderer | None = None,
        marketplace_changes: _MarketplaceChangeWorkspaceService | None = None,
        marketplace_refresh_allowed: Callable[[], bool] | None = None,
    ) -> None:
        self._presentation = presentation
        self._renderer = renderer or DesktopCollectionExplorerRenderer()
        self._marketplace_changes = marketplace_changes
        self._marketplace_cache: MarketplaceChangeWorkspace | None = None
        self._marketplace_refresh_allowed = marketplace_refresh_allowed or (lambda: True)

    def set_marketplace_refresh_allowed(self, allowed: Callable[[], bool]) -> None:
        if not callable(allowed):
            raise TypeError("allowed must be callable.")
        self._marketplace_refresh_allowed = allowed

    def invalidate_marketplace_changes(self) -> None:
        """Invalidate cached read-only Marketplace projections without rebuilding."""

        self._marketplace_cache = None

    def refresh_marketplace_changes(self) -> MarketplaceChangeWorkspace | None:
        """Build but do not publish a candidate replacement workspace."""

        if self._marketplace_changes is None or not self._marketplace_refresh_allowed():
            return None
        candidate = self._construct_marketplace_candidate()
        return self._validate_marketplace_candidate(candidate)

    def _construct_marketplace_candidate(self) -> MarketplaceChangeWorkspace:
        """Construct a detached candidate at an independently testable seam."""

        return self._marketplace_changes.build()

    @staticmethod
    def _validate_marketplace_candidate(
        candidate: MarketplaceChangeWorkspace,
    ) -> MarketplaceChangeWorkspace | None:
        """Fail closed when a service returns no valid final workspace model."""

        if type(candidate) is not MarketplaceChangeWorkspace:
            raise TypeError("candidate must be a MarketplaceChangeWorkspace.")
        if candidate.state is MarketplaceChangeWorkspaceState.ERROR:
            return None
        return candidate

    def install_marketplace_changes(self, candidate: MarketplaceChangeWorkspace) -> MarketplaceChangeWorkspace | None:
        """Publish a candidate only after presentation and window rendering succeed."""

        if type(candidate) is not MarketplaceChangeWorkspace:
            raise TypeError("candidate must be a MarketplaceChangeWorkspace.")
        previous = self._marketplace_cache
        self._marketplace_cache = candidate
        return previous

    def restore_marketplace_changes(self, previous: MarketplaceChangeWorkspace | None) -> None:
        """Restore the exact prior cache when window publication fails."""

        if previous is not None and type(previous) is not MarketplaceChangeWorkspace:
            raise TypeError("previous must be a MarketplaceChangeWorkspace or None.")
        self._marketplace_cache = previous

    @property
    def marketplace_cache(self) -> MarketplaceChangeWorkspace | None:
        return self._marketplace_cache

    def render_marketplace_candidate(
        self,
        homepage: DashboardHomepageViewModel,
        candidate: MarketplaceChangeWorkspace,
        *,
        selected_destination: CollectionExplorerDestination,
    ) -> DesktopCollectionExplorerView:
        """Render a detached candidate without changing the installed cache."""

        if type(candidate) is not MarketplaceChangeWorkspace:
            raise TypeError("candidate must be a MarketplaceChangeWorkspace.")
        explorer = self.present_marketplace_candidate(
            homepage,
            candidate,
            selected_destination=selected_destination,
        )
        return self.render_marketplace_presentation(explorer)

    def present_marketplace_candidate(
        self,
        homepage: DashboardHomepageViewModel,
        candidate: MarketplaceChangeWorkspace,
        *,
        selected_destination: CollectionExplorerDestination,
    ):
        """Construct candidate presentation without rendering or cache mutation."""

        if type(candidate) is not MarketplaceChangeWorkspace:
            raise TypeError("candidate must be a MarketplaceChangeWorkspace.")
        return self._presentation.explorer_for_homepage(
            homepage,
            selected_destination=selected_destination,
            price_changes_detail=candidate.price_changes,
            supply_changes_detail=candidate.supply_changes,
            marketplace_change_outcome=_presentation_outcome(candidate.outcome_reason),
        )

    def render_marketplace_presentation(self, explorer):
        """Invoke the installed Explorer renderer at a distinct refresh stage."""

        renderer = self._marketplace_renderer_for_refresh()
        return renderer.render(explorer)

    def _marketplace_renderer_for_refresh(self) -> DesktopCollectionExplorerRenderer:
        """Return the renderer at a distinct construction/acquisition seam."""

        return self._renderer

    @property
    def has_marketplace_cache(self) -> bool:
        return self._marketplace_cache is not None

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
        price_changes_result: IntelligenceResult | None = None,
        supply_changes_result: IntelligenceResult | None = None,
        rare_appearances_result: IntelligenceResult | None = None,
        marketplace_activity_result: IntelligenceResult | None = None,
        listing_lifecycle_result: IntelligenceResult | None = None,
        marketplace_momentum_result: IntelligenceResult | None = None,
        marketplace_stability_result: IntelligenceResult | None = None,
        marketplace_scarcity_result: IntelligenceResult | None = None,
        marketplace_opportunity_result: IntelligenceResult | None = None,
        refresh_marketplace: bool = False,
        collector_run_active: bool = False,
    ) -> DesktopCollectionExplorerView:
        """Build and render one Explorer; tab changes need no further service call."""

        if type(selected_destination) is not CollectionExplorerDestination:
            selected_destination = CollectionExplorerDestination.OVERVIEW
        disabled = frozenset((CollectionExplorerDestination.WEEKEND_LISTINGS, CollectionExplorerDestination.RARE_APPEARANCES, CollectionExplorerDestination.MARKETPLACE_ACTIVITY, CollectionExplorerDestination.LISTING_LIFECYCLE, CollectionExplorerDestination.MARKETPLACE_MOMENTUM, CollectionExplorerDestination.MARKETPLACE_STABILITY, CollectionExplorerDestination.MARKETPLACE_SCARCITY, CollectionExplorerDestination.MARKETPLACE_OPPORTUNITY))
        disabled_request = selected_destination in disabled
        if disabled_request:
            selected_destination = CollectionExplorerDestination.OVERVIEW
        result_arguments = {}
        if weekend_listings_result is not None:
            result_arguments["weekend_listings_result"] = weekend_listings_result
        if price_changes_result is not None:
            result_arguments["price_changes_result"] = price_changes_result
        if supply_changes_result is not None:
            result_arguments["supply_changes_result"] = supply_changes_result
        if rare_appearances_result is not None:
            result_arguments["rare_appearances_result"] = rare_appearances_result
        if marketplace_activity_result is not None:
            result_arguments["marketplace_activity_result"] = marketplace_activity_result
        if listing_lifecycle_result is not None:
            result_arguments["listing_lifecycle_result"] = listing_lifecycle_result
        if marketplace_momentum_result is not None:
            result_arguments["marketplace_momentum_result"] = (
                marketplace_momentum_result
            )
        if marketplace_stability_result is not None:
            result_arguments["marketplace_stability_result"] = marketplace_stability_result
        if marketplace_scarcity_result is not None:
            result_arguments["marketplace_scarcity_result"] = marketplace_scarcity_result
        if marketplace_opportunity_result is not None:
            result_arguments["marketplace_opportunity_result"] = marketplace_opportunity_result
        if disabled_request:
            result_arguments.clear()
        candidate = None
        if self._marketplace_changes is not None and price_changes_result is None and supply_changes_result is None and not disabled_request:
            refresh_allowed = not collector_run_active and self._marketplace_refresh_allowed()
            if refresh_allowed and (refresh_marketplace or self._marketplace_cache is None):
                candidate = self._marketplace_changes.build()
            supplied = candidate or self._marketplace_cache
            if supplied is not None:
                result_arguments["price_changes_detail"] = supplied.price_changes
                result_arguments["supply_changes_detail"] = supplied.supply_changes
                result_arguments["marketplace_change_outcome"] = _presentation_outcome(getattr(supplied, "outcome_reason", None))
        explorer = self._presentation.explorer_for_homepage(
            homepage,
            selected_destination=selected_destination,
            **result_arguments,
        )
        rendered = self._renderer.render(explorer)
        if candidate is not None:
            self._marketplace_cache = candidate
        return rendered


def _state_heading(state: CollectionExplorerState) -> str:
    labels = {
        CollectionExplorerState.LOADING: "Loading",
        CollectionExplorerState.AVAILABLE: "Available",
        CollectionExplorerState.PARTIAL: "Partially available",
        CollectionExplorerState.EMPTY: "No intelligence history",
        CollectionExplorerState.UNAVAILABLE: "Unavailable",
        CollectionExplorerState.ERROR: "Unable to display",
        CollectionExplorerState.INSUFFICIENT_HISTORY: "Insufficient history",
        CollectionExplorerState.INSUFFICIENT_DATA: "Insufficient data",
    }
    return labels[state]


def _presentation_outcome(
    reason: MarketplaceChangeOutcomeReason | None,
) -> MarketplaceChangePresentationOutcome | None:
    if reason is None:
        return None
    if type(reason) is not MarketplaceChangeOutcomeReason:
        raise TypeError("Marketplace outcome reason must be typed.")
    return MarketplaceChangePresentationOutcome(reason.value)


def _marketplace_outcome_copy(
    outcome: MarketplaceChangePresentationOutcome | None,
) -> str | None:
    if outcome is None:
        return None
    if type(outcome) is not MarketplaceChangePresentationOutcome:
        raise TypeError("Marketplace presentation outcome must be typed.")
    return presentation_state_copy(marketplace_outcome_state_kind(outcome)).heading


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
