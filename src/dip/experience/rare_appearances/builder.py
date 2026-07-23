"""Map typed Rare Appearances output into immutable presentation values."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import RareAppearancesAnalysisState, RareAppearancesOutput

from .models import RareAppearanceViewModel, RareAppearancesDetailConsistencyError, RareAppearancesDetailState, RareAppearancesDetailViewModel


class RareAppearancesDetailViewModelBuilder:
    def build(self, result: IntelligenceResult | None) -> RareAppearancesDetailViewModel:
        if result is None:
            return RareAppearancesDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the standard IntelligenceResult contract.")
        if result.module_id != "rare_appearances":
            raise RareAppearancesDetailConsistencyError("Rare Appearances detail requires the rare_appearances result.")
        output = result.metrics.get("output")
        if type(output) is not RareAppearancesOutput:
            raise RareAppearancesDetailConsistencyError("Rare Appearances requires typed output.")
        expected = IntelligenceStatus.SKIPPED if output.analysis_state is RareAppearancesAnalysisState.INSUFFICIENT_HISTORY else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise RareAppearancesDetailConsistencyError("Result status contradicts analysis state.")
        state = RareAppearancesDetailState.INSUFFICIENT_HISTORY if output.analysis_state is RareAppearancesAnalysisState.INSUFFICIENT_HISTORY else (RareAppearancesDetailState.PARTIAL if output.analysis_state is RareAppearancesAnalysisState.PARTIAL else (RareAppearancesDetailState.AVAILABLE if output.appearances else RareAppearancesDetailState.EMPTY))
        values = tuple(RareAppearanceViewModel(value.release_id, value.appearance_count, value.history_snapshot_count, value.appearance_ratio, value.first_observed_snapshot.snapshot_id, value.first_observed_snapshot.captured_at, value.latest_observed_snapshot.snapshot_id, value.latest_observed_snapshot.captured_at, value.longest_absence, value.observation_snapshot_ids) for value in output.appearances)
        return RareAppearancesDetailViewModel(state, result.summary, output.analysis_state, output.threshold, output.summary.history_snapshot_count, output.summary.release_count, output.summary.excluded_snapshot_count, values, tuple(result.diagnostics))


__all__ = ["RareAppearancesDetailViewModelBuilder"]
