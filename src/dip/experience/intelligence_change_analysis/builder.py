"""Map one typed comparison result without comparison or calculation."""

from collections.abc import Mapping

from dip.historical_intelligence import IntelligenceComparisonOutput, IntelligenceComparisonState
from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .models import IntelligenceChangeAnalysisDetailState as State
from .models import IntelligenceChangeAnalysisViewModel


class IntelligenceChangeAnalysisViewModelBuilder:
    def build(self, result):
        if result is None:
            return IntelligenceChangeAnalysisViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "intelligence_change_analysis" or result.module_version != "1.0":
            raise ValueError("Change Analysis requires its canonical 1.0 result.")
        output = result.metrics.get("output")
        if type(output) is not IntelligenceComparisonOutput:
            raise ValueError("Change Analysis requires typed output.")
        insufficient = output.summary.comparison_state is IntelligenceComparisonState.INSUFFICIENT
        expected = IntelligenceStatus.SKIPPED if insufficient else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise ValueError("Result status contradicts Change Analysis state.")
        return IntelligenceChangeAnalysisViewModel(
            State.INSUFFICIENT if insufficient else State.AVAILABLE,
            result.summary, output, tuple(result.diagnostics),
        )
