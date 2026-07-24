"""Build Price Changes detail from its typed standard result."""

from __future__ import annotations

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import (
    PriceChangesComparisonState,
    PriceChangesOutput,
    PriceChangesSnapshotReference,
)

from .models import (
    ListingPriceChangeViewModel,
    PriceChangesDetailConsistencyError,
    PriceChangesDetailState,
    PriceChangesDetailViewModel,
    PriceChangesSnapshotViewModel,
    ReleasePriceChangeViewModel,
)


class PriceChangesDetailViewModelBuilder:
    """Copy typed comparison output without comparing, classifying, or sorting."""

    def build(
        self,
        result: IntelligenceResult | None,
    ) -> PriceChangesDetailViewModel:
        if result is None:
            return PriceChangesDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult:
            raise TypeError("result must be an IntelligenceResult or None.")
        if result.module_id != "price_changes":
            raise PriceChangesDetailConsistencyError(
                "Price Changes detail requires the price_changes result."
            )
        if type(result.status) is not IntelligenceStatus:
            raise TypeError("Price Changes result status must be IntelligenceStatus.")
        if not isinstance(result.metrics, Mapping):
            raise TypeError("Price Changes result metrics must be a mapping.")
        output = result.metrics.get("output")
        if type(output) is not PriceChangesOutput:
            raise PriceChangesDetailConsistencyError(
                "Price Changes result requires typed output."
            )

        state = self._state(result, output)
        return PriceChangesDetailViewModel(
            state=state,
            summary=result.summary,
            comparison_state=output.comparison_state,
            previous_snapshot=_snapshot(output.previous_snapshot),
            latest_snapshot=_snapshot(output.latest_snapshot),
            source=output.source,
            listing_change_count=output.summary.listing_change_count,
            release_change_count=output.summary.release_change_count,
            unchanged_count=output.summary.unchanged_count,
            incomparable_count=output.summary.incomparable_count,
            listing_changes=tuple(
                ListingPriceChangeViewModel(
                    listing_id=value.listing_id,
                    release_id=value.release_id,
                    change_kind=value.change_kind,
                    previous_price=value.previous_price,
                    latest_price=value.latest_price,
                    delta=value.delta,
                    previous_observed_at=value.previous_observed_at,
                    latest_observed_at=value.latest_observed_at,
                    previous_snapshot_id=value.previous_snapshot_id,
                    latest_snapshot_id=value.latest_snapshot_id,
                    evidence=value.evidence,
                )
                for value in output.listing_changes
            ),
            release_changes=tuple(
                ReleasePriceChangeViewModel(
                    release_id=value.release_id,
                    metric=value.metric,
                    change_kind=value.change_kind,
                    previous_value=value.previous_value,
                    latest_value=value.latest_value,
                    delta=value.delta,
                    previous_snapshot_id=value.previous_snapshot_id,
                    latest_snapshot_id=value.latest_snapshot_id,
                    evidence=value.evidence,
                )
                for value in output.release_changes
            ),
            diagnostics=tuple(result.diagnostics),
        )

    @staticmethod
    def _state(
        result: IntelligenceResult,
        output: PriceChangesOutput,
    ) -> PriceChangesDetailState:
        expected_status = {
            PriceChangesComparisonState.COMPLETE: IntelligenceStatus.COMPLETED,
            PriceChangesComparisonState.PARTIAL: IntelligenceStatus.COMPLETED,
            PriceChangesComparisonState.INSUFFICIENT_HISTORY: (
                IntelligenceStatus.SKIPPED
            ),
            PriceChangesComparisonState.INSUFFICIENT_DATA: IntelligenceStatus.SKIPPED,
            PriceChangesComparisonState.FAILED: IntelligenceStatus.FAILED,
        }[output.comparison_state]
        if result.status is not expected_status:
            raise PriceChangesDetailConsistencyError(
                "Price Changes result status contradicts its typed comparison state."
            )
        if output.comparison_state is PriceChangesComparisonState.COMPLETE:
            return (
                PriceChangesDetailState.AVAILABLE
                if (
                    output.summary.listing_change_count
                    or output.summary.release_change_count
                )
                else PriceChangesDetailState.EMPTY
            )
        return {
            PriceChangesComparisonState.PARTIAL: PriceChangesDetailState.PARTIAL,
            PriceChangesComparisonState.INSUFFICIENT_HISTORY: (
                PriceChangesDetailState.INSUFFICIENT_HISTORY
            ),
            PriceChangesComparisonState.INSUFFICIENT_DATA: (
                PriceChangesDetailState.INSUFFICIENT_DATA
            ),
            PriceChangesComparisonState.FAILED: PriceChangesDetailState.ERROR,
        }[output.comparison_state]


def _snapshot(
    value: PriceChangesSnapshotReference | None,
) -> PriceChangesSnapshotViewModel | None:
    if value is None:
        return None
    return PriceChangesSnapshotViewModel(
        snapshot_id=value.snapshot_id,
        captured_at=value.captured_at,
        source=value.source,
        status=value.status,
        source_version=value.source_version,
    )


__all__ = ["PriceChangesDetailViewModelBuilder"]
