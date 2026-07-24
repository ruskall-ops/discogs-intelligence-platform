"""Build Hidden Gems detail from the established Dashboard presentation."""

from __future__ import annotations

from dip.experience.dashboard import (
    DashboardCardState,
    DashboardHiddenGemsViewModel,
    DashboardMetricValueViewModel,
    DashboardSectionState,
)

from .models import (
    HiddenGemMetricViewModel,
    HiddenGemReleaseViewModel,
    HiddenGemsDetailConsistencyError,
    HiddenGemsDetailState,
    HiddenGemsDetailViewModel,
)


_SUPPORTING_METRIC_ORDER = (
    "wants",
    "copies_for_sale",
    "demand_to_supply_ratio",
    "community_rating",
    "owned_quantity",
    "lowest_price",
    "wants_per_price_unit",
)
_FACTOR_SCORE_ORDER = (
    "demand",
    "scarcity",
    "community_rating",
    "collection_ownership",
    "price_efficiency",
)


class HiddenGemsDetailViewModelBuilder:
    """Copy existing Hidden Gems presentation values without recalculation."""

    def build(
        self,
        section: DashboardHiddenGemsViewModel,
    ) -> HiddenGemsDetailViewModel:
        """Transform one validated homepage section into richer detail."""

        if type(section) is not DashboardHiddenGemsViewModel:
            raise TypeError("section must be a DashboardHiddenGemsViewModel.")
        if section.state is DashboardSectionState.LOADING:
            return HiddenGemsDetailViewModel.loading()
        if section.card is None:
            raise HiddenGemsDetailConsistencyError(
                "A non-loading Hidden Gems section requires a card."
            )

        card = section.card
        state = self._state(section.state, card.state)
        candidates = tuple(
            HiddenGemReleaseViewModel(
                rank=rank,
                release_id=candidate.release_id,
                artist=candidate.artist,
                title=candidate.title,
                score=candidate.score,
                explanation=candidate.explanation,
                supporting_metrics=self._metrics(candidate.supporting_metrics),
                factor_scores=self._metrics(candidate.factor_scores),
                evidence=candidate.evidence,
            )
            for rank, candidate in enumerate(card.ranked_gems, start=1)
        )

        if state in {
            HiddenGemsDetailState.AVAILABLE,
            HiddenGemsDetailState.PARTIAL,
            HiddenGemsDetailState.EMPTY,
        }:
            self._validate_metric_order(candidates)
        if state is HiddenGemsDetailState.AVAILABLE and any(
            candidate.has_unavailable_values for candidate in candidates
        ):
            state = HiddenGemsDetailState.PARTIAL

        return HiddenGemsDetailViewModel(
            state=state,
            summary=card.summary,
            candidate_count=card.total_hidden_gems,
            candidates=candidates,
            diagnostics=card.diagnostics,
        )

    @staticmethod
    def _metrics(
        metrics: tuple[DashboardMetricValueViewModel, ...],
    ) -> tuple[HiddenGemMetricViewModel, ...]:
        return tuple(
            HiddenGemMetricViewModel(
                metric_id=metric.metric_id,
                label=metric.label,
                value=metric.value,
            )
            for metric in metrics
        )

    @staticmethod
    def _validate_metric_order(
        candidates: tuple[HiddenGemReleaseViewModel, ...],
    ) -> None:
        for candidate in candidates:
            if tuple(
                metric.metric_id for metric in candidate.supporting_metrics
            ) != _SUPPORTING_METRIC_ORDER:
                raise HiddenGemsDetailConsistencyError(
                    "Supporting metrics must preserve canonical module order."
                )
            if tuple(
                metric.metric_id for metric in candidate.factor_scores
            ) != _FACTOR_SCORE_ORDER:
                raise HiddenGemsDetailConsistencyError(
                    "Factor scores must preserve canonical module order."
                )

    @staticmethod
    def _state(
        section_state: DashboardSectionState,
        card_state: DashboardCardState,
    ) -> HiddenGemsDetailState:
        expected = {
            DashboardCardState.READY: {
                DashboardSectionState.AVAILABLE,
                DashboardSectionState.EMPTY,
            },
            DashboardCardState.SKIPPED: {DashboardSectionState.EMPTY},
            DashboardCardState.FAILED: {DashboardSectionState.ERROR},
            DashboardCardState.INCOMPLETE: {DashboardSectionState.ERROR},
            DashboardCardState.UNAVAILABLE: {DashboardSectionState.UNAVAILABLE},
        }
        if card_state not in expected:
            raise HiddenGemsDetailConsistencyError(
                "Hidden Gems card has an unsupported state."
            )
        if section_state not in expected[card_state]:
            raise HiddenGemsDetailConsistencyError(
                "Hidden Gems section and card states contradict one another."
            )
        return {
            DashboardSectionState.AVAILABLE: HiddenGemsDetailState.AVAILABLE,
            DashboardSectionState.EMPTY: HiddenGemsDetailState.EMPTY,
            DashboardSectionState.UNAVAILABLE: HiddenGemsDetailState.UNAVAILABLE,
            DashboardSectionState.ERROR: HiddenGemsDetailState.ERROR,
        }[section_state]


__all__ = ["HiddenGemsDetailViewModelBuilder"]
