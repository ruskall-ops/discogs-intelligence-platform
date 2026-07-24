"""Map typed Portfolio Overview output without aggregation or sorting."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.portfolio_intelligence import (
    PortfolioAnalysisState,
    PortfolioOverviewOutput,
)

from .models import PortfolioOverviewDetailState, PortfolioOverviewViewModel


class PortfolioOverviewViewModelBuilder:
    def build(self, result):
        if result is None:
            return PortfolioOverviewViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "portfolio_overview":
            raise ValueError("Portfolio Overview requires portfolio_overview.")
        output = result.metrics.get("output")
        if type(output) is not PortfolioOverviewOutput:
            raise ValueError("Portfolio Overview requires typed output.")
        expected = (
            IntelligenceStatus.SKIPPED
            if output.analysis_state is PortfolioAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
        if result.status is not expected:
            raise ValueError("Result status contradicts Portfolio Overview analysis state.")
        if output.analysis_state is PortfolioAnalysisState.INSUFFICIENT_DATA:
            state = (
                PortfolioOverviewDetailState.EMPTY
                if output.summary.ownership.unique_owned_release_count == 0
                else PortfolioOverviewDetailState.INSUFFICIENT_DATA
            )
        elif output.analysis_state is PortfolioAnalysisState.PARTIAL:
            state = PortfolioOverviewDetailState.PARTIAL
        else:
            state = PortfolioOverviewDetailState.AVAILABLE
        return PortfolioOverviewViewModel(
            state=state,
            summary_text=result.summary,
            rule_set_version=output.rule_set_version,
            rule_configuration=output.rule_configuration,
            summary=output.summary,
            evidence_coverage=output.summary.evidence_coverage,
            opportunity_distribution=output.opportunity_distribution,
            momentum_distribution=output.momentum_distribution,
            stability_distribution=output.stability_distribution,
            scarcity_distribution=output.scarcity_distribution,
            concentration_facts=output.concentration_facts,
            releases=output.releases,
            reason_codes=output.reason_codes,
            source_provenance=output.source_provenance,
            output_diagnostics=output.diagnostics,
            diagnostics=tuple(result.diagnostics),
        )


__all__ = ["PortfolioOverviewViewModelBuilder"]
