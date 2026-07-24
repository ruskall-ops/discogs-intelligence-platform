"""Map typed Listing Lifecycle output without calculation or sorting."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import ListingLifecycleAnalysisState, ListingLifecycleOutput

from .models import ListingLifecycleDetailConsistencyError, ListingLifecycleDetailState, ListingLifecycleDetailViewModel, ListingLifecycleViewModel


class ListingLifecycleDetailViewModelBuilder:
    def build(self, result: IntelligenceResult | None) -> ListingLifecycleDetailViewModel:
        if result is None:
            return ListingLifecycleDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the standard IntelligenceResult contract.")
        if result.module_id != "listing_lifecycle":
            raise ListingLifecycleDetailConsistencyError("Listing Lifecycle detail requires the listing_lifecycle result.")
        output = result.metrics.get("output")
        if type(output) is not ListingLifecycleOutput:
            raise ListingLifecycleDetailConsistencyError("Listing Lifecycle requires typed output.")
        expected = IntelligenceStatus.SKIPPED if output.analysis_state is ListingLifecycleAnalysisState.INSUFFICIENT_HISTORY else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise ListingLifecycleDetailConsistencyError("Result status contradicts analysis state.")
        state = ListingLifecycleDetailState.INSUFFICIENT_HISTORY if output.analysis_state is ListingLifecycleAnalysisState.INSUFFICIENT_HISTORY else (ListingLifecycleDetailState.PARTIAL if output.analysis_state is ListingLifecycleAnalysisState.PARTIAL else (ListingLifecycleDetailState.AVAILABLE if output.lifecycles else ListingLifecycleDetailState.EMPTY))
        values = tuple(ListingLifecycleViewModel(value.release_id, value.listing_id, value.lifecycle_state, value.currently_present, value.first_observation.snapshot_id, value.first_observation.captured_at, value.latest_observation.snapshot_id, value.latest_observation.captured_at, value.snapshots_observed, value.history_snapshot_count, value.observation_ratio, value.continuous_lifetime, value.disappearance_count, value.reappearance_count, value.longest_absence, value.diagnostics) for value in output.lifecycles)
        return ListingLifecycleDetailViewModel(state, result.summary, output.analysis_state, output.summary.history_snapshot_count, output.summary.listing_count, output.summary.currently_present_count, values, tuple(result.diagnostics))


__all__ = ["ListingLifecycleDetailViewModelBuilder"]
