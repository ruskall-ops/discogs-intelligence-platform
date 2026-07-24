"""Build Collection Health detail from the established Dashboard presentation."""

from __future__ import annotations

from dip.experience.dashboard import (
    DashboardCardState,
    DashboardCollectionHealthViewModel,
    DashboardSectionState,
)

from .models import (
    CollectionHealthComponentViewModel,
    CollectionHealthDetailConsistencyError,
    CollectionHealthDetailState,
    CollectionHealthDetailViewModel,
)


_COMPONENT_ORDER = (
    "metadata_completeness",
    "marketplace_coverage",
    "demand_strength",
    "valuation_coverage",
)


class CollectionHealthDetailViewModelBuilder:
    """Copy existing Collection Health presentation values without recalculation."""

    def build(
        self,
        section: DashboardCollectionHealthViewModel,
    ) -> CollectionHealthDetailViewModel:
        """Transform one validated homepage section into richer detail."""

        if type(section) is not DashboardCollectionHealthViewModel:
            raise TypeError(
                "section must be a DashboardCollectionHealthViewModel."
            )
        if section.state is DashboardSectionState.LOADING:
            return CollectionHealthDetailViewModel.loading()
        if section.card is None:
            raise CollectionHealthDetailConsistencyError(
                "A non-loading Collection Health section requires a card."
            )

        card = section.card
        components = tuple(
            CollectionHealthComponentViewModel(
                component_id=component.key,
                label=component.label,
                score=component.score,
            )
            for component in card.components
        )
        state = self._state(section.state, card.state)
        if state in {
            CollectionHealthDetailState.AVAILABLE,
            CollectionHealthDetailState.EMPTY,
        } and tuple(component.component_id for component in components) != _COMPONENT_ORDER:
            raise CollectionHealthDetailConsistencyError(
                "Collection Health components must preserve canonical module order."
            )

        return CollectionHealthDetailViewModel(
            state=state,
            summary=card.summary,
            overall_score=card.headline_score,
            components=components,
            strengths=card.strengths,
            improvement_opportunities=card.improvement_opportunities,
            evidence=card.evidence,
            diagnostics=card.diagnostics,
        )

    @staticmethod
    def _state(
        section_state: DashboardSectionState,
        card_state: DashboardCardState,
    ) -> CollectionHealthDetailState:
        expected = {
            DashboardCardState.READY: DashboardSectionState.AVAILABLE,
            DashboardCardState.SKIPPED: DashboardSectionState.EMPTY,
            DashboardCardState.FAILED: DashboardSectionState.ERROR,
            DashboardCardState.INCOMPLETE: DashboardSectionState.ERROR,
            DashboardCardState.UNAVAILABLE: DashboardSectionState.UNAVAILABLE,
        }
        if card_state not in expected:
            raise CollectionHealthDetailConsistencyError(
                "Collection Health card has an unsupported state."
            )
        if section_state is not expected[card_state]:
            raise CollectionHealthDetailConsistencyError(
                "Collection Health section and card states contradict one another."
            )
        return {
            DashboardSectionState.AVAILABLE: CollectionHealthDetailState.AVAILABLE,
            DashboardSectionState.EMPTY: CollectionHealthDetailState.EMPTY,
            DashboardSectionState.UNAVAILABLE: CollectionHealthDetailState.UNAVAILABLE,
            DashboardSectionState.ERROR: CollectionHealthDetailState.ERROR,
        }[section_state]


__all__ = ["CollectionHealthDetailViewModelBuilder"]
