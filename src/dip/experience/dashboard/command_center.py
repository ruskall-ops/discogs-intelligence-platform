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
                overview.overview.summary_text, "Open Portfolio Workspace",
                DashboardNavigationTarget.PORTFOLIO,
            ),
            _card(
                DashboardCommandCardId.PORTFOLIO_HEALTH, "Portfolio Health",
                health.card.summary if health.card is not None else "Collection Health is unavailable.",
                "Open Collection Workspace", DashboardNavigationTarget.COLLECTION_EXPLORER,
            ),
            _card(
                DashboardCommandCardId.OPPORTUNITY_HIGHLIGHTS, "Opportunity Highlights",
                overview.opportunity_alignment.summary_text,
                "Open Portfolio → Opportunity Alignment",
                DashboardNavigationTarget.PORTFOLIO_OPPORTUNITY_ALIGNMENT,
            ),
            _card(
                DashboardCommandCardId.COLLECTION_CHANGES, "Collection Changes",
                changes.summary, "Open Collection Workspace",
                DashboardNavigationTarget.COLLECTION_EXPLORER,
            ),
            _card(
                DashboardCommandCardId.HISTORICAL_CHANGES, "Historical Changes",
                latest_change.summary_text if latest_change is not None else "No historical changes have been supplied.",
                "Open Historical Intelligence",
                DashboardNavigationTarget.HISTORICAL_INTELLIGENCE,
            ),
            _card(
                DashboardCommandCardId.MARKETPLACE_HIGHLIGHTS, "Marketplace Highlights",
                first_marketplace.insight_summary if first_marketplace is not None else "No Marketplace opportunities have been supplied.",
                "Open Marketplace Workspace",
                DashboardNavigationTarget.MARKETPLACE_WORKSPACE,
            ),
            _card(
                DashboardCommandCardId.RESEARCH_SUMMARY, "Research Summary",
                "Portfolio Research is ready for evidence-led investigation.",
                "Open Portfolio → Research",
                DashboardNavigationTarget.PORTFOLIO_RESEARCH,
            ),
            DashboardCommandCardViewModel(
                DashboardCommandCardId.QUICK_ACTIONS,
                "Quick Actions",
                "Open an existing workspace without executing intelligence.",
                (
                    DashboardNavigationAction("Portfolio", DashboardNavigationTarget.PORTFOLIO),
                    DashboardNavigationAction("Portfolio History", DashboardNavigationTarget.PORTFOLIO_HISTORY),
                    DashboardNavigationAction("Marketplace", DashboardNavigationTarget.MARKETPLACE_WORKSPACE),
                ),
            ),
        )
        return DashboardCommandCenterViewModel(cards)


def _card(card_id, title, summary, label, target):
    return DashboardCommandCardViewModel(
        card_id, title, summary, (DashboardNavigationAction(label, target),)
    )


__all__ = ["DashboardCommandCenterBuilder"]
