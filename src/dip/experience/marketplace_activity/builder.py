"""Map typed Marketplace Activity output without aggregation or sorting."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import MarketplaceActivityOutput, MarketplaceActivityState

from .models import MarketplaceActivityDetailConsistencyError, MarketplaceActivityDetailState, MarketplaceActivityDetailViewModel, ReleaseActivityViewModel


class MarketplaceActivityDetailViewModelBuilder:
    def build(self, result: IntelligenceResult | None) -> MarketplaceActivityDetailViewModel:
        if result is None:
            return MarketplaceActivityDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the standard IntelligenceResult contract.")
        if result.module_id != "marketplace_activity":
            raise MarketplaceActivityDetailConsistencyError("Marketplace Activity detail requires the marketplace_activity result.")
        output = result.metrics.get("output")
        if type(output) is not MarketplaceActivityOutput:
            raise MarketplaceActivityDetailConsistencyError("Marketplace Activity requires typed output.")
        expected = IntelligenceStatus.SKIPPED if output.state is MarketplaceActivityState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise MarketplaceActivityDetailConsistencyError("Result status contradicts activity state.")
        state = MarketplaceActivityDetailState.INSUFFICIENT_DATA if output.state is MarketplaceActivityState.INSUFFICIENT_DATA else (MarketplaceActivityDetailState.PARTIAL if output.state is MarketplaceActivityState.PARTIAL else (MarketplaceActivityDetailState.AVAILABLE if output.activities else MarketplaceActivityDetailState.EMPTY))
        activities = tuple(ReleaseActivityViewModel(value.release_id, value.total_activity_count, value.historical_price_change_count, value.historical_supply_change_count, value.appearance_count, value.appearance_ratio, value.longest_absence, value.first_observation.snapshot_id, value.first_observation.captured_at, value.latest_observation.snapshot_id, value.latest_observation.captured_at) for value in output.activities)
        return MarketplaceActivityDetailViewModel(state, result.summary, output.state, output.summary.release_count, output.summary.total_activity_count, activities, tuple(result.diagnostics))


__all__ = ["MarketplaceActivityDetailViewModelBuilder"]
