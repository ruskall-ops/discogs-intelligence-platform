"""Map typed Scarcity output without calculation or reordering."""

from collections.abc import Mapping

from dip.decision_intelligence import MarketplaceScarcityOutput, ScarcityAnalysisState
from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .models import MarketplaceScarcityDetailState, MarketplaceScarcityDetailViewModel


class MarketplaceScarcityDetailViewModelBuilder:
    def build(self, result):
        if result is None:
            return MarketplaceScarcityDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "marketplace_scarcity":
            raise ValueError("Marketplace Scarcity detail requires marketplace_scarcity.")
        output = result.metrics.get("output")
        if type(output) is not MarketplaceScarcityOutput:
            raise ValueError("Marketplace Scarcity requires typed output.")
        expected = IntelligenceStatus.SKIPPED if output.analysis_state is ScarcityAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise ValueError("Result status contradicts Scarcity analysis state.")
        state = (
            MarketplaceScarcityDetailState.INSUFFICIENT_DATA if output.analysis_state is ScarcityAnalysisState.INSUFFICIENT_DATA else
            MarketplaceScarcityDetailState.PARTIAL if output.analysis_state is ScarcityAnalysisState.PARTIAL else
            MarketplaceScarcityDetailState.AVAILABLE if output.releases else
            MarketplaceScarcityDetailState.EMPTY
        )
        return MarketplaceScarcityDetailViewModel(
            state, result.summary, output.analysis_state, output.rule_set_version,
            output.summary, output.releases, output.source_provenance,
            output.diagnostics, tuple(result.diagnostics),
        )


__all__ = ["MarketplaceScarcityDetailViewModelBuilder"]

