"""Map typed Portfolio Distribution output without calculation or sorting."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.portfolio_intelligence import (
    PortfolioDistributionAnalysisState,
    PortfolioDistributionOutput,
)

from .models import PortfolioDistributionDetailState, PortfolioDistributionViewModel


class PortfolioDistributionViewModelBuilder:
    def build(self, result):
        if result is None:
            return PortfolioDistributionViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "portfolio_distribution":
            raise ValueError("Portfolio Distribution requires portfolio_distribution.")
        output = result.metrics.get("output")
        if type(output) is not PortfolioDistributionOutput:
            raise ValueError("Portfolio Distribution requires typed output.")
        expected = (
            IntelligenceStatus.SKIPPED
            if output.analysis_state is PortfolioDistributionAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
        if result.status is not expected:
            raise ValueError("Result status contradicts Portfolio Distribution state.")
        if output.analysis_state is PortfolioDistributionAnalysisState.INSUFFICIENT_DATA:
            state = (
                PortfolioDistributionDetailState.EMPTY
                if output.summary.ownership.unique_owned_releases == 0
                else PortfolioDistributionDetailState.INSUFFICIENT_DATA
            )
        elif output.analysis_state is PortfolioDistributionAnalysisState.PARTIAL:
            state = PortfolioDistributionDetailState.PARTIAL
        else:
            state = PortfolioDistributionDetailState.AVAILABLE
        return PortfolioDistributionViewModel(
            state, result.summary, output.rule_set_version, output.rule_configuration,
            output.summary, output.summary.evidence_coverage, output.dimensions,
            output.releases, output.reason_codes, output.provenance,
            output.diagnostics, tuple(result.diagnostics),
        )


__all__ = ["PortfolioDistributionViewModelBuilder"]
