"""Map typed Stability output without calculation or reordering."""

from collections.abc import Mapping

from dip.decision_intelligence import MarketplaceStabilityOutput, StabilityAnalysisState
from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .models import MarketplaceStabilityDetailState, MarketplaceStabilityDetailViewModel


class MarketplaceStabilityDetailViewModelBuilder:
    def build(self, result: IntelligenceResult | None) -> MarketplaceStabilityDetailViewModel:
        if result is None:
            return MarketplaceStabilityDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "marketplace_stability":
            raise ValueError("Marketplace Stability detail requires marketplace_stability.")
        output = result.metrics.get("output")
        if type(output) is not MarketplaceStabilityOutput:
            raise ValueError("Marketplace Stability requires typed output.")
        expected = IntelligenceStatus.SKIPPED if output.analysis_state is StabilityAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise ValueError("Result status contradicts Stability analysis state.")
        state = (
            MarketplaceStabilityDetailState.INSUFFICIENT_DATA
            if output.analysis_state is StabilityAnalysisState.INSUFFICIENT_DATA
            else MarketplaceStabilityDetailState.PARTIAL
            if output.analysis_state is StabilityAnalysisState.PARTIAL
            else MarketplaceStabilityDetailState.AVAILABLE
            if output.releases
            else MarketplaceStabilityDetailState.EMPTY
        )
        return MarketplaceStabilityDetailViewModel(
            state, result.summary, output.analysis_state, output.rule_set_version,
            output.summary, output.releases, output.source_provenance,
            output.diagnostics, tuple(result.diagnostics),
        )


__all__ = ["MarketplaceStabilityDetailViewModelBuilder"]

