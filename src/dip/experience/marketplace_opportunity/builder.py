"""Map typed Opportunity output without synthesis or reordering."""

from collections.abc import Mapping

from dip.decision_intelligence import MarketplaceOpportunityOutput, OpportunityAnalysisState
from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .models import MarketplaceOpportunityDetailState, MarketplaceOpportunityDetailViewModel


class MarketplaceOpportunityDetailViewModelBuilder:
    def build(self, result):
        if result is None:
            return MarketplaceOpportunityDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "marketplace_opportunity":
            raise ValueError("Marketplace Opportunity detail requires marketplace_opportunity.")
        output = result.metrics.get("output")
        if type(output) is not MarketplaceOpportunityOutput:
            raise ValueError("Marketplace Opportunity requires typed output.")
        expected = IntelligenceStatus.SKIPPED if output.analysis_state is OpportunityAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise ValueError("Result status contradicts Opportunity analysis state.")
        state = (
            MarketplaceOpportunityDetailState.INSUFFICIENT_DATA if output.analysis_state is OpportunityAnalysisState.INSUFFICIENT_DATA else
            MarketplaceOpportunityDetailState.PARTIAL if output.analysis_state is OpportunityAnalysisState.PARTIAL else
            MarketplaceOpportunityDetailState.AVAILABLE if output.releases else
            MarketplaceOpportunityDetailState.EMPTY
        )
        return MarketplaceOpportunityDetailViewModel(
            state, result.summary, output.analysis_state, output.rule_set_version,
            output.rule_configuration, output.summary, output.releases,
            output.source_provenance, output.diagnostics, tuple(result.diagnostics),
        )


__all__ = ["MarketplaceOpportunityDetailViewModelBuilder"]

