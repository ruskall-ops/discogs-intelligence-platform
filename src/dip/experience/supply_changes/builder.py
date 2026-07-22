"""Build Supply Changes detail from typed module output."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import SupplyChangesComparisonState, SupplyChangesOutput

from .models import ReleaseSupplyChangeViewModel, SupplyChangesDetailConsistencyError, SupplyChangesDetailState, SupplyChangesDetailViewModel, SupplyChangesSnapshotViewModel


class SupplyChangesDetailViewModelBuilder:
    def build(self, result: IntelligenceResult | None) -> SupplyChangesDetailViewModel:
        if result is None:
            return SupplyChangesDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult:
            raise TypeError("result must be an IntelligenceResult or None.")
        if result.module_id != "supply_changes":
            raise SupplyChangesDetailConsistencyError("Supply Changes detail requires the supply_changes result.")
        if type(result.status) is not IntelligenceStatus or not isinstance(result.metrics, Mapping):
            raise TypeError("Supply Changes result has an invalid standard contract.")
        output = result.metrics.get("output")
        if type(output) is not SupplyChangesOutput:
            raise SupplyChangesDetailConsistencyError("Supply Changes result requires typed output.")
        expected = {SupplyChangesComparisonState.COMPLETE: IntelligenceStatus.COMPLETED, SupplyChangesComparisonState.PARTIAL: IntelligenceStatus.COMPLETED, SupplyChangesComparisonState.INSUFFICIENT_HISTORY: IntelligenceStatus.SKIPPED, SupplyChangesComparisonState.INSUFFICIENT_DATA: IntelligenceStatus.SKIPPED, SupplyChangesComparisonState.FAILED: IntelligenceStatus.FAILED}[output.comparison_state]
        if result.status is not expected:
            raise SupplyChangesDetailConsistencyError("Supply Changes status contradicts its comparison state.")
        state = ({SupplyChangesComparisonState.PARTIAL: SupplyChangesDetailState.PARTIAL, SupplyChangesComparisonState.INSUFFICIENT_HISTORY: SupplyChangesDetailState.INSUFFICIENT_HISTORY, SupplyChangesComparisonState.INSUFFICIENT_DATA: SupplyChangesDetailState.INSUFFICIENT_DATA, SupplyChangesComparisonState.FAILED: SupplyChangesDetailState.ERROR}.get(output.comparison_state) or (SupplyChangesDetailState.AVAILABLE if output.summary.change_count else SupplyChangesDetailState.EMPTY))
        snapshot = lambda value: None if value is None else SupplyChangesSnapshotViewModel(value.snapshot_id, value.captured_at, value.source, value.status, value.source_version)
        return SupplyChangesDetailViewModel(state, result.summary, output.comparison_state, snapshot(output.previous_snapshot), snapshot(output.latest_snapshot), output.source, output.summary.change_count, output.summary.unchanged_count, output.summary.incomparable_count, tuple(ReleaseSupplyChangeViewModel(c.release_id, c.previous_supply, c.latest_supply, c.delta, c.change_kind, c.previous_snapshot_id, c.latest_snapshot_id, c.evidence) for c in output.changes), tuple(result.diagnostics))


__all__ = ["SupplyChangesDetailViewModelBuilder"]
