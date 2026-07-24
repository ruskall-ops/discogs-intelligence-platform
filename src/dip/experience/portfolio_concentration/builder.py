"""Map typed Portfolio Concentration output without calculation or sorting."""

from collections.abc import Mapping

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.portfolio_intelligence import (
    PortfolioConcentrationAnalysisState,
    PortfolioConcentrationOutput,
)

from .models import PortfolioConcentrationDetailState, PortfolioConcentrationViewModel


class PortfolioConcentrationViewModelBuilder:
    def build(self, result):
        if result is None:
            return PortfolioConcentrationViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(result.metrics, Mapping):
            raise TypeError("result must use the IntelligenceResult contract.")
        if result.module_id != "portfolio_concentration":
            raise ValueError("Portfolio Concentration requires portfolio_concentration.")
        output = result.metrics.get("output")
        if type(output) is not PortfolioConcentrationOutput:
            raise ValueError("Portfolio Concentration requires typed output.")
        expected = (
            IntelligenceStatus.SKIPPED
            if output.analysis_state is PortfolioConcentrationAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
        if result.status is not expected:
            raise ValueError("Result status contradicts Portfolio Concentration state.")
        if output.analysis_state is PortfolioConcentrationAnalysisState.INSUFFICIENT_DATA:
            state = (
                PortfolioConcentrationDetailState.EMPTY
                if output.summary.unique_owned_releases == 0
                and output.provenance.source_module_version == "1.0"
                else PortfolioConcentrationDetailState.INSUFFICIENT_DATA
            )
        elif output.analysis_state is PortfolioConcentrationAnalysisState.PARTIAL:
            state = PortfolioConcentrationDetailState.PARTIAL
        else:
            state = PortfolioConcentrationDetailState.AVAILABLE
        return PortfolioConcentrationViewModel(
            state, result.summary, output.rule_set_version, output.rule_configuration,
            output.summary, output.summary.evidence_coverage, output.dimensions,
            output.reason_codes, output.provenance, output.diagnostics,
            tuple(result.diagnostics),
        )


__all__ = ["PortfolioConcentrationViewModelBuilder"]
