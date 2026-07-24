"""Map typed Alignment output without synthesis, calculation, or sorting."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.portfolio_decision_intelligence import (
    PortfolioOpportunityAlignmentAnalysisState,
    PortfolioOpportunityAlignmentOutput,
)

from .models import PortfolioOpportunityAlignmentDetailState as State
from .models import PortfolioOpportunityAlignmentViewModel


class PortfolioOpportunityAlignmentViewModelBuilder:
    def build(self, result):
        if result is None:
            return PortfolioOpportunityAlignmentViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "portfolio_opportunity_alignment":
            raise ValueError("Portfolio Opportunity Alignment requires its canonical module result.")
        output = result.metrics.get("output")
        if type(output) is not PortfolioOpportunityAlignmentOutput:
            raise ValueError("Portfolio Opportunity Alignment requires typed output.")
        expected = IntelligenceStatus.SKIPPED if output.analysis_state is PortfolioOpportunityAlignmentAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        if result.status is not expected:
            raise ValueError("Result status contradicts Alignment state.")
        state = (
            State.EMPTY if output.analysis_state is PortfolioOpportunityAlignmentAnalysisState.INSUFFICIENT_DATA
            and output.breadth.valid_owned_releases == 0 and output.provenance.overview_module_version == "1.0"
            else State.INSUFFICIENT_DATA if output.analysis_state is PortfolioOpportunityAlignmentAnalysisState.INSUFFICIENT_DATA
            else State.PARTIAL if output.analysis_state is PortfolioOpportunityAlignmentAnalysisState.PARTIAL
            else State.AVAILABLE
        )
        return PortfolioOpportunityAlignmentViewModel(
            state, result.summary, output.rule_set_version, output.rule_configuration,
            output.summary, output.breadth, output.dimensions, output.reason_codes,
            output.provenance, output.diagnostics, tuple(result.diagnostics),
        )

