"""Application validation and execution for Portfolio Concentration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from dip.portfolio_intelligence import (
    PortfolioConcentrationDiagnostic,
    PortfolioConcentrationDiagnosticCode,
    PortfolioConcentrationInput,
    PortfolioConcentrationProvenance,
    PortfolioDistributionAnalysisState,
    PortfolioDistributionOutput,
)


class _DistributionProvider(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _Engine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class PortfolioConcentrationExecutionConsistencyError(RuntimeError):
    """Raised when the concentration execution boundary is violated."""


class PortfolioConcentrationExecutionService:
    def __init__(self, distribution: _DistributionProvider, engine: _Engine):
        self._distribution = distribution
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        source = self._distribution.execute()
        prepared = build_portfolio_concentration_input(source)
        execution = self._engine.execute(
            IntelligenceContext(portfolio_concentration_input=prepared)
        )
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise PortfolioConcentrationExecutionConsistencyError(
                "Portfolio Concentration engine must return exactly one result."
            )
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "portfolio_concentration":
            raise PortfolioConcentrationExecutionConsistencyError(
                "Portfolio Concentration engine returned an unexpected result."
            )
        return result


def build_portfolio_concentration_input(source) -> PortfolioConcentrationInput:
    diagnostics = []
    output = None
    module_id = "portfolio_distribution"
    module_version = None
    if source is None:
        diagnostics.append(_diagnostic(
            PortfolioConcentrationDiagnosticCode.MISSING_DISTRIBUTION_SOURCE,
            "Portfolio Distribution result was not supplied.",
        ))
    elif type(source) is not IntelligenceResult:
        diagnostics.append(_diagnostic(
            PortfolioConcentrationDiagnosticCode.MALFORMED_SOURCE_OUTPUT,
            "Portfolio Distribution source is not an IntelligenceResult.",
        ))
    else:
        module_id = source.module_id
        module_version = source.module_version
        if source.module_id != "portfolio_distribution":
            diagnostics.append(_diagnostic(
                PortfolioConcentrationDiagnosticCode.SOURCE_MODULE_MISMATCH,
                f"Expected portfolio_distribution but received {source.module_id!r}.",
            ))
        if source.module_version != "1.0":
            diagnostics.append(_diagnostic(
                PortfolioConcentrationDiagnosticCode.UNSUPPORTED_SOURCE_VERSION,
                f"Portfolio Distribution version {source.module_version!r} is unsupported.",
            ))
        if isinstance(source.metrics, Mapping):
            output = source.metrics.get("output")
        if type(output) is not PortfolioDistributionOutput:
            diagnostics.append(_diagnostic(
                PortfolioConcentrationDiagnosticCode.MALFORMED_SOURCE_OUTPUT,
                "Portfolio Distribution does not contain its typed output.",
            ))
        else:
            if output.rule_set_version != "1.0":
                diagnostics.append(_diagnostic(
                    PortfolioConcentrationDiagnosticCode.UNSUPPORTED_SOURCE_RULE_SET,
                    f"Portfolio Distribution rule set {output.rule_set_version!r} is unsupported.",
                ))
            expected = (
                IntelligenceStatus.SKIPPED
                if output.analysis_state is PortfolioDistributionAnalysisState.INSUFFICIENT_DATA
                else IntelligenceStatus.COMPLETED
            )
            if source.status is not expected:
                diagnostics.append(_diagnostic(
                    PortfolioConcentrationDiagnosticCode.SOURCE_NOT_COMPLETED,
                    "Portfolio Distribution status contradicts its analysis state.",
                ))
        if type(source.diagnostics) is tuple:
            diagnostics.extend(
                _diagnostic(
                    PortfolioConcentrationDiagnosticCode.SOURCE_DIAGNOSTIC_PRESERVED,
                    value,
                )
                for value in source.diagnostics
                if type(value) is str and value
            )
    compatible = (
        type(source) is IntelligenceResult
        and source.module_id == "portfolio_distribution"
        and source.module_version == "1.0"
        and type(output) is PortfolioDistributionOutput
        and output.rule_set_version == "1.0"
        and source.status is (
            IntelligenceStatus.SKIPPED
            if output.analysis_state is PortfolioDistributionAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
    )
    if type(output) is PortfolioDistributionOutput:
        summary = output.summary
        supported = tuple(value.value for value in summary.supported_dimensions)
        source_coverage = summary.evidence_coverage
        distribution_provenance = output.provenance
        dimensions = output.dimensions if compatible else ()
        ownership = summary.ownership
        releases = ownership.unique_owned_releases
        copies = ownership.total_owned_copies
        duplicates = ownership.duplicate_copy_count
        rule_set = output.rule_set_version
    else:
        supported, source_coverage, distribution_provenance = (), None, None
        dimensions, releases, copies, duplicates, rule_set = (), 0, 0, 0, None
    provenance = PortfolioConcentrationProvenance(
        module_id, module_version, rule_set, source_coverage,
        distribution_provenance, supported,
    )
    return PortfolioConcentrationInput(
        compatible, provenance, dimensions, releases, copies, duplicates,
        tuple(sorted(diagnostics, key=_diagnostic_order)),
    )


def _diagnostic(code, message):
    return PortfolioConcentrationDiagnostic(code, message)


def _diagnostic_order(value):
    return tuple(PortfolioConcentrationDiagnosticCode).index(value.code), value.message


__all__ = [
    "PortfolioConcentrationExecutionConsistencyError",
    "PortfolioConcentrationExecutionService",
    "build_portfolio_concentration_input",
]
