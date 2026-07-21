"""Build Weekend Listings detail from its typed standard result."""

from __future__ import annotations

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import MarketplaceDataStatus, WeekendListingsOutput

from .models import (
    WeekendListingViewModel,
    WeekendListingsDetailConsistencyError,
    WeekendListingsDetailState,
    WeekendListingsDetailViewModel,
)


class WeekendListingsDetailViewModelBuilder:
    """Copy typed module output without qualification, filtering or ranking."""

    def build(
        self,
        result: IntelligenceResult | None,
    ) -> WeekendListingsDetailViewModel:
        if result is None:
            return WeekendListingsDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult:
            raise TypeError("result must be an IntelligenceResult or None.")
        if result.module_id != "weekend_listings":
            raise WeekendListingsDetailConsistencyError(
                "Weekend Listings detail requires the weekend_listings result."
            )
        if type(result.status) is not IntelligenceStatus:
            raise TypeError("Weekend Listings result status must be IntelligenceStatus.")
        if not isinstance(result.metrics, Mapping):
            raise TypeError("Weekend Listings result metrics must be a mapping.")
        output = result.metrics.get("output")
        if type(output) is not WeekendListingsOutput:
            raise WeekendListingsDetailConsistencyError(
                "Weekend Listings result requires typed output."
            )
        candidates = tuple(
            WeekendListingViewModel(
                listing_id=value.listing_id,
                release_id=value.release_id,
                artist=value.artist,
                title=value.title,
                observed_at=value.observed_at,
                price=value.price,
                shipping=value.shipping,
                condition=value.condition,
                seller_region=value.seller_region,
                inclusion_evidence=value.inclusion_evidence,
            )
            for value in output.candidates
        )
        state = self._state(result, output, candidates)
        return WeekendListingsDetailViewModel(
            state=state,
            summary=result.summary,
            window=output.window,
            snapshot_id=output.snapshot_id,
            snapshot_status=output.snapshot_status,
            candidate_count=len(candidates),
            candidates=candidates,
            diagnostics=tuple(result.diagnostics),
        )

    @staticmethod
    def _state(
        result: IntelligenceResult,
        output: WeekendListingsOutput,
        candidates: tuple[WeekendListingViewModel, ...],
    ) -> WeekendListingsDetailState:
        if result.status is IntelligenceStatus.FAILED:
            if candidates:
                raise WeekendListingsDetailConsistencyError(
                    "A failed Weekend Listings result cannot contain candidates."
                )
            return WeekendListingsDetailState.ERROR
        if result.status is IntelligenceStatus.SKIPPED:
            if candidates:
                raise WeekendListingsDetailConsistencyError(
                    "A skipped Weekend Listings result cannot contain candidates."
                )
            if output.snapshot_status in {
                None,
                MarketplaceDataStatus.UNAVAILABLE,
            }:
                return WeekendListingsDetailState.UNAVAILABLE
            return WeekendListingsDetailState.INSUFFICIENT_DATA
        if result.status is not IntelligenceStatus.COMPLETED:
            raise WeekendListingsDetailConsistencyError(
                "Weekend Listings result has an unsupported status."
            )
        if not candidates:
            if (
                output.snapshot_status is MarketplaceDataStatus.PARTIAL
                or not output.collection_context_complete
            ):
                return WeekendListingsDetailState.INSUFFICIENT_DATA
            return WeekendListingsDetailState.EMPTY
        if (
            output.snapshot_status is MarketplaceDataStatus.PARTIAL
            or not output.collection_context_complete
            or result.diagnostics
            or any(value.has_missing_optional_evidence for value in candidates)
        ):
            return WeekendListingsDetailState.PARTIAL
        return WeekendListingsDetailState.AVAILABLE


__all__ = ["WeekendListingsDetailViewModelBuilder"]
