"""Compose existing immutable presentation state into Dashboard cards."""

from dip.experience.dashboard.homepage_models import (
    DashboardChangeSummaryViewModel,
    DashboardCollectionHealthViewModel,
    DashboardHomepageViewModel,
)
from dip.experience.history_explorer import HistoryExplorerState
from dip.experience.marketplace_workspace import MarketplaceWorkspaceState
from dip.experience.portfolio_workspace import PortfolioWorkspaceState

from .command_center_models import (
    DashboardCommandCardId,
    DashboardCommandCardViewModel,
    DashboardCommandCenterViewModel,
    DashboardNavigationAction,
    DashboardNavigationTarget,
)


class DashboardCommandCenterBuilder:
    def build(self, collection, portfolio, marketplace, history):
        if type(collection) is not DashboardHomepageViewModel:
            raise TypeError("collection must be DashboardHomepageViewModel.")
        if type(portfolio) is not PortfolioWorkspaceState:
            raise TypeError("portfolio must be PortfolioWorkspaceState.")
        if type(marketplace) is not MarketplaceWorkspaceState:
            raise TypeError("marketplace must be MarketplaceWorkspaceState.")
        if type(history) is not HistoryExplorerState:
            raise TypeError("history must be HistoryExplorerState.")
        health = next(
            value for value in collection.sections
            if type(value) is DashboardCollectionHealthViewModel
        )
        changes = next(
            value for value in collection.sections
            if type(value) is DashboardChangeSummaryViewModel
        )
        first_marketplace = (
            marketplace.filtered_queue[0] if marketplace.filtered_queue else None
        )
        latest_change = history.changes[-1] if history.changes else None
        overview = portfolio.overview
        cards = (
            _card(
                DashboardCommandCardId.PORTFOLIO_SUMMARY, "Portfolio Summary",
                "Not available in this release", "Open Portfolio Workspace",
                DashboardNavigationTarget.PORTFOLIO, enabled=False,
            ),
            _card(
                DashboardCommandCardId.PORTFOLIO_HEALTH, "Collection Health",
                health.card.summary if health.card is not None else "Collection Health is unavailable.",
                "Open Collection Workspace", DashboardNavigationTarget.COLLECTION_EXPLORER,
            ),
            _card(
                DashboardCommandCardId.OPPORTUNITY_HIGHLIGHTS, "Opportunity Highlights",
                "Not available in this release",
                "Open Portfolio → Opportunity Alignment",
                DashboardNavigationTarget.PORTFOLIO_OPPORTUNITY_ALIGNMENT,
                enabled=False,
            ),
            _card(
                DashboardCommandCardId.COLLECTION_CHANGES, "Collection Changes",
                changes.summary, "Open Collection Workspace",
                DashboardNavigationTarget.COLLECTION_EXPLORER,
            ),
            _card(
                DashboardCommandCardId.HISTORICAL_CHANGES, "Historical Changes",
                "Not available in this release",
                "Open Historical Intelligence",
                DashboardNavigationTarget.HISTORICAL_INTELLIGENCE,
                enabled=False,
            ),
            _card(
                DashboardCommandCardId.MARKETPLACE_HIGHLIGHTS, "Marketplace Highlights",
                "Not available in this release",
                "Open Marketplace Workspace",
                DashboardNavigationTarget.MARKETPLACE_WORKSPACE,
                enabled=False,
            ),
            _card(
                DashboardCommandCardId.RESEARCH_SUMMARY, "Research Summary",
                "Not available in this release",
                "Open Portfolio → Research",
                DashboardNavigationTarget.PORTFOLIO_RESEARCH,
                enabled=False,
            ),
            DashboardCommandCardViewModel(
                DashboardCommandCardId.QUICK_ACTIONS,
                "Quick Actions",
                "Open an existing workspace without executing intelligence.",
                (
                    DashboardNavigationAction("Portfolio", DashboardNavigationTarget.PORTFOLIO, False),
                    DashboardNavigationAction("Portfolio History", DashboardNavigationTarget.PORTFOLIO_HISTORY, False),
                    DashboardNavigationAction("Marketplace", DashboardNavigationTarget.MARKETPLACE_WORKSPACE, False),
                ),
            ),
        )
        return DashboardCommandCenterViewModel(cards)


def _card(card_id, title, summary, label, target, *, enabled=True):
    return DashboardCommandCardViewModel(
        card_id, title, summary,
        (DashboardNavigationAction(label, target, enabled),),
    )


__all__ = ["DashboardCommandCenterBuilder"]
