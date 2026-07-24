"""Compatibility presenter for the original current-engine Explorer."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from dip.experience.dashboard import (
    DashboardCardState,
    DashboardCardViewModel,
    HiddenGemsCardViewModel,
    HistoricalIntelligenceCardViewModel,
    IntelligenceDashboardViewModel,
)

from .models import (
    CollectionHealthExplorerViewModel,
    CollectionIntelligenceExplorerViewModel,
    HiddenGemsExplorerViewModel,
    HistoricalIntelligenceExplorerViewModel,
)


class CollectionIntelligenceExplorerPresenter:
    """Preserve the prior Explorer API for non-desktop compatibility clients."""

    def present(
        self,
        dashboard: IntelligenceDashboardViewModel,
    ) -> CollectionIntelligenceExplorerViewModel:
        sections = (
            self._safely(
                self._collection_health,
                dashboard.card_for("collection_health"),
                self._unavailable_health(),
            ),
            self._safely(
                self._hidden_gems,
                dashboard.card_for("hidden_gems"),
                self._unavailable_hidden_gems(),
            ),
            self._safely(
                self._historical,
                dashboard.card_for("historical_intelligence"),
                self._unavailable_historical(),
            ),
        )
        return CollectionIntelligenceExplorerViewModel(sections=sections)

    @staticmethod
    def _collection_health(card: Any) -> CollectionHealthExplorerViewModel:
        if not isinstance(card, DashboardCardViewModel):
            raise TypeError("Collection Health dashboard model is unavailable.")
        return CollectionHealthExplorerViewModel(
            module_id=card.module_id,
            title=card.title,
            state=card.state,
            overall_health=card.headline_score,
            summary=card.summary,
            component_scores=card.components,
            evidence=card.evidence,
            diagnostics=card.diagnostics,
        )

    @staticmethod
    def _hidden_gems(card: Any) -> HiddenGemsExplorerViewModel:
        if not isinstance(card, HiddenGemsCardViewModel):
            raise TypeError("Hidden Gems dashboard model is unavailable.")
        return HiddenGemsExplorerViewModel(
            module_id=card.module_id,
            title=card.title,
            state=card.state,
            total_hidden_gems=card.total_hidden_gems,
            summary=card.summary,
            ranked_releases=card.ranked_gems,
            diagnostics=card.diagnostics,
        )

    @staticmethod
    def _historical(card: Any) -> HistoricalIntelligenceExplorerViewModel:
        if not isinstance(card, HistoricalIntelligenceCardViewModel):
            raise TypeError("Historical Intelligence dashboard model is unavailable.")
        return HistoricalIntelligenceExplorerViewModel(
            module_id=card.module_id,
            title=card.title,
            state=card.state,
            summary=card.summary,
            latest_snapshot=card.latest_snapshot_date,
            previous_snapshot=card.previous_snapshot_date,
            collection_size_change=card.collection_size_change,
            collection_value_change=card.collection_value_change,
            average_value_change=card.average_value_change,
            median_value_change=card.median_value_change,
            releases_added=card.releases_added,
            releases_removed=card.releases_removed,
            added_releases=card.added_releases,
            removed_releases=card.removed_releases,
            top_gainers=card.ranked_gainers,
            top_decliners=card.ranked_decliners,
            evidence_coverage=card.evidence_coverage_summary,
            diagnostics=card.diagnostics,
        )

    @staticmethod
    def _safely(mapper, card, unavailable):
        if card is None:
            return unavailable
        try:
            return mapper(card)
        except Exception as exc:
            return replace(
                unavailable,
                state=DashboardCardState.FAILED,
                summary=f"{unavailable.title} could not be displayed.",
                diagnostics=(f"{type(exc).__name__}: {exc}",),
            )

    @staticmethod
    def _unavailable_health() -> CollectionHealthExplorerViewModel:
        return CollectionHealthExplorerViewModel(
            "collection_health",
            "Collection Health",
            DashboardCardState.UNAVAILABLE,
            None,
            "Collection Health intelligence is unavailable.",
        )

    @staticmethod
    def _unavailable_hidden_gems() -> HiddenGemsExplorerViewModel:
        return HiddenGemsExplorerViewModel(
            "hidden_gems",
            "Hidden Gems",
            DashboardCardState.UNAVAILABLE,
            None,
            "Hidden Gems intelligence is unavailable.",
        )

    @staticmethod
    def _unavailable_historical() -> HistoricalIntelligenceExplorerViewModel:
        return HistoricalIntelligenceExplorerViewModel(
            "historical_intelligence",
            "Historical Intelligence",
            DashboardCardState.UNAVAILABLE,
            "Historical Intelligence is unavailable.",
        )
