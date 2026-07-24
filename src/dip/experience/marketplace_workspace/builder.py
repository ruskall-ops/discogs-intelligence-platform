"""Selection and filtering for an already-ordered Marketplace queue."""

from dataclasses import replace

from .models import (
    MarketplaceAttentionItemViewModel,
    MarketplaceResearchStatus,
    MarketplaceWorkspaceAvailability,
    MarketplaceWorkspaceFilters,
    MarketplaceWorkspacePane,
    MarketplaceWorkspaceState,
)


class MarketplaceWorkspaceStateBuilder:
    def build(
        self,
        queue=(),
        *,
        filters=MarketplaceWorkspaceFilters(),
        selected_release_id=None,
        current_pane=MarketplaceWorkspacePane.ATTENTION_QUEUE,
        available=True,
    ):
        queue = tuple(queue)
        if any(type(value) is not MarketplaceAttentionItemViewModel for value in queue):
            raise TypeError("queue must contain MarketplaceAttentionItemViewModel values.")
        if len({value.release_id for value in queue}) != len(queue):
            raise ValueError("Queue release identities must be unique.")
        filtered = tuple(value for value in queue if _matches(value, filters))
        if selected_release_id is None and filtered:
            selected_release_id = filtered[0].release_id
        selected = next((value for value in filtered if value.release_id == selected_release_id), None)
        availability = (
            MarketplaceWorkspaceAvailability.UNAVAILABLE if not available
            else MarketplaceWorkspaceAvailability.AVAILABLE if queue
            else MarketplaceWorkspaceAvailability.EMPTY
        )
        return MarketplaceWorkspaceState(
            availability, current_pane, queue, filtered,
            selected.release_id if selected else None,
            selected.detail if selected else None,
            selected.evidence_sections if selected else (),
            selected.history if selected else None,
            selected.insights if selected else (),
            selected.portfolio_context if selected else None,
            filters,
        )

    def select(self, state, release_id, *, pane=None):
        if type(state) is not MarketplaceWorkspaceState:
            raise TypeError("state must be MarketplaceWorkspaceState.")
        return self.build(
            state.queue, filters=state.filters, selected_release_id=release_id,
            current_pane=pane or state.current_pane,
            available=state.availability is not MarketplaceWorkspaceAvailability.UNAVAILABLE,
        )

    def with_research_status(self, state, release_id, status):
        if type(state) is not MarketplaceWorkspaceState:
            raise TypeError("state must be MarketplaceWorkspaceState.")
        if type(status) is not MarketplaceResearchStatus:
            raise TypeError("status must be MarketplaceResearchStatus.")
        if not any(value.release_id == release_id for value in state.queue):
            raise ValueError("release_id is not present in the workspace queue.")
        queue = tuple(
            replace(value, research_status=status) if value.release_id == release_id else value
            for value in state.queue
        )
        return self.build(
            queue, filters=state.filters, selected_release_id=release_id,
            current_pane=MarketplaceWorkspacePane.RESEARCH_STATUS,
            available=state.availability is not MarketplaceWorkspaceAvailability.UNAVAILABLE,
        )


def _matches(value, filters):
    return all((
        filters.research_status is None or value.research_status is filters.research_status,
        filters.marketplace_assessment is None or value.marketplace_assessment == filters.marketplace_assessment,
        filters.evidence_state is None or value.evidence_state == filters.evidence_state,
        filters.artist is None or value.artist == filters.artist,
        filters.label is None or value.label == filters.label,
        filters.owned is None or (value.portfolio_context is not None and value.portfolio_context.owned is filters.owned),
        filters.release_id is None or value.release_id == filters.release_id,
        filters.history_available is None or value.history_available is filters.history_available,
        filters.trend_available is None or value.trend_available is filters.trend_available,
    ))


__all__ = ["MarketplaceWorkspaceStateBuilder"]
