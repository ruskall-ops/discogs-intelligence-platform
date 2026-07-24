"""Map typed Trend Analysis output without calculation or sorting."""

from collections.abc import Mapping

from dip.historical_intelligence import IntelligenceTrendAnalysisOutput, IntelligenceTrendEvidenceCoverage
from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .models import IntelligenceTrendAnalysisDetailState as State
from .models import IntelligenceTrendAnalysisViewModel


class IntelligenceTrendAnalysisViewModelBuilder:
    def build(self, result):
        if result is None:
            return IntelligenceTrendAnalysisViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "intelligence_trend_analysis" or result.module_version != "1.0":
            raise ValueError("Trend Analysis requires its canonical 1.0 result.")
        output = result.metrics.get("output")
        if type(output) is not IntelligenceTrendAnalysisOutput:
            raise ValueError("Trend Analysis requires typed output.")
        insufficient = output.summary.evidence_coverage is IntelligenceTrendEvidenceCoverage.INSUFFICIENT
        if result.status is not (IntelligenceStatus.SKIPPED if insufficient else IntelligenceStatus.COMPLETED):
            raise ValueError("Result status contradicts Trend Analysis evidence.")
        return IntelligenceTrendAnalysisViewModel(
            State.INSUFFICIENT if insufficient else State.AVAILABLE,
            result.summary, output, tuple(result.diagnostics),
        )
