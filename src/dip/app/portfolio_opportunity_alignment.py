"""Application validation and execution for Portfolio Opportunity Alignment."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from dip.portfolio_decision_intelligence import (
    PortfolioOpportunityAlignmentDiagnostic,
    PortfolioOpportunityAlignmentDiagnosticCode as Code,
    PortfolioOpportunityAlignmentInput,
    PortfolioOpportunityAlignmentProvenance,
)
from dip.portfolio_intelligence import (
    PortfolioAnalysisState,
    PortfolioConcentrationAnalysisState,
    PortfolioConcentrationOutput,
    PortfolioDistributionAnalysisState,
    PortfolioDistributionOutput,
    PortfolioOverviewOutput,
)


class _Provider(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _Engine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class PortfolioOpportunityAlignmentExecutionConsistencyError(RuntimeError):
    """Raised when the explicitly configured execution boundary is violated."""


class PortfolioOpportunityAlignmentExecutionService:
    def __init__(self, overview: _Provider, distribution: _Provider, concentration: _Provider, engine: _Engine):
        self._overview = overview
        self._distribution = distribution
        self._concentration = concentration
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        sources = (self._overview.execute(), self._distribution.execute(), self._concentration.execute())
        prepared = build_portfolio_opportunity_alignment_input(*sources)
        execution = self._engine.execute(IntelligenceContext(portfolio_opportunity_alignment_input=prepared))
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise PortfolioOpportunityAlignmentExecutionConsistencyError(
                "Portfolio Opportunity Alignment engine must return exactly one result."
            )
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "portfolio_opportunity_alignment":
            raise PortfolioOpportunityAlignmentExecutionConsistencyError(
                "Portfolio Opportunity Alignment engine returned an unexpected result."
            )
        return result


def build_portfolio_opportunity_alignment_input(overview_result, distribution_result, concentration_result):
    diagnostics = []
    overview = _validate(
        overview_result, "portfolio_overview", PortfolioOverviewOutput, PortfolioAnalysisState,
        diagnostics,
    )
    distribution = _validate(
        distribution_result, "portfolio_distribution", PortfolioDistributionOutput,
        PortfolioDistributionAnalysisState, diagnostics,
    )
    concentration = _validate(
        concentration_result, "portfolio_concentration", PortfolioConcentrationOutput,
        PortfolioConcentrationAnalysisState, diagnostics,
    )
    initially_valid = not any(value.code is not Code.SOURCE_DIAGNOSTIC_PRESERVED for value in diagnostics)
    if overview is not None and distribution is not None and concentration is not None:
        overview_ids = tuple(value.release_id for value in overview.releases)
        distribution_ids = tuple(value.release_id for value in distribution.releases)
        if overview_ids != distribution_ids:
            diagnostics.append(_d(Code.INCONSISTENT_RELEASE_POPULATION, "Overview and Distribution release populations differ."))
        release_totals = (
            overview.summary.ownership.unique_owned_release_count,
            distribution.summary.ownership.unique_owned_releases,
            concentration.summary.unique_owned_releases,
        )
        if len(set(release_totals)) != 1:
            diagnostics.append(_d(Code.INCONSISTENT_OWNED_RELEASE_TOTAL, "Required sources report different owned release totals."))
        copy_totals = (
            overview.summary.ownership.total_owned_entry_count,
            distribution.summary.ownership.total_owned_copies,
            concentration.summary.total_owned_copies,
        )
        if len(set(copy_totals)) != 1:
            diagnostics.append(_d(Code.INCONSISTENT_OWNED_COPY_TOTAL, "Required sources report different owned copy totals."))
        source = concentration.provenance
        if (
            source.source_module_id != "portfolio_distribution"
            or source.source_module_version != "1.0"
            or source.source_rule_set_version != "1.0"
            or source.distribution_provenance != distribution.provenance
            or source.supported_dimensions != tuple(value.value for value in distribution.summary.supported_dimensions)
        ):
            diagnostics.append(_d(Code.INCOMPATIBLE_DISTRIBUTION_REFERENCE, "Concentration does not reference the supplied Distribution result."))
        snapshots = tuple(value for value in (
            overview.source_provenance.collection_snapshot_id,
            distribution.provenance.collection_snapshot_id,
            source.distribution_provenance.collection_snapshot_id if source.distribution_provenance else None,
        ) if value is not None)
        if len(set(snapshots)) > 1:
            diagnostics.append(_d(Code.INCOMPATIBLE_COLLECTION_SNAPSHOT, "Required sources identify different collection snapshots."))
    else:
        snapshots = ()
    compatible = initially_valid and not any(value.code is not Code.SOURCE_DIAGNOSTIC_PRESERVED for value in diagnostics)
    provenance = PortfolioOpportunityAlignmentProvenance(
        getattr(overview_result, "module_version", None), getattr(overview, "rule_set_version", None),
        getattr(distribution_result, "module_version", None), getattr(distribution, "rule_set_version", None),
        getattr(concentration_result, "module_version", None), getattr(concentration, "rule_set_version", None),
        snapshots[0] if snapshots and len(set(snapshots)) == 1 else None,
        tuple(value.value for value in distribution.summary.supported_dimensions) if distribution else (),
        concentration.summary.analysed_dimensions if concentration else (),
        concentration.summary.unusable_dimensions if concentration else (),
        overview.summary.evidence_coverage if overview else None,
        distribution.summary.evidence_coverage if distribution else None,
        concentration.summary.evidence_coverage if concentration else None,
    )
    return PortfolioOpportunityAlignmentInput(
        compatible, overview, distribution, concentration, provenance,
        tuple(sorted(diagnostics, key=_order)),
    )


def _validate(result, module_id, output_type, state_type, diagnostics):
    if result is None:
        diagnostics.append(_d(Code.MISSING_REQUIRED_SOURCE, f"{module_id} was not supplied.", module_id))
        return None
    if type(result) is not IntelligenceResult:
        diagnostics.append(_d(Code.MALFORMED_SOURCE_OUTPUT, f"{module_id} is not an IntelligenceResult.", module_id))
        return None
    if result.module_id != module_id:
        diagnostics.append(_d(Code.SOURCE_MODULE_MISMATCH, f"Expected {module_id} but received {result.module_id!r}.", module_id))
    if result.module_version != "1.0":
        diagnostics.append(_d(Code.UNSUPPORTED_SOURCE_VERSION, f"{module_id} version {result.module_version!r} is unsupported.", module_id))
    output = result.metrics.get("output") if isinstance(result.metrics, Mapping) else None
    if type(output) is not output_type:
        diagnostics.append(_d(Code.MALFORMED_SOURCE_OUTPUT, f"{module_id} does not contain its typed output.", module_id))
        return None
    if output.rule_set_version != "1.0":
        diagnostics.append(_d(Code.UNSUPPORTED_SOURCE_RULE_SET, f"{module_id} rule set {output.rule_set_version!r} is unsupported.", module_id))
    expected = IntelligenceStatus.SKIPPED if output.analysis_state.value == "insufficient_data" else IntelligenceStatus.COMPLETED
    if result.status is not expected:
        diagnostics.append(_d(Code.SOURCE_STATUS_INCOMPATIBLE, f"{module_id} status contradicts its analysis state.", module_id))
    diagnostics.extend(
        _d(Code.SOURCE_DIAGNOSTIC_PRESERVED, value, module_id)
        for value in result.diagnostics if type(value) is str and value
    )
    return output


def _d(code, message, source=None):
    return PortfolioOpportunityAlignmentDiagnostic(code, message, source)


def _order(value):
    return tuple(Code).index(value.code), value.source_module_id or "", value.message


__all__ = [
    "PortfolioOpportunityAlignmentExecutionConsistencyError",
    "PortfolioOpportunityAlignmentExecutionService",
    "build_portfolio_opportunity_alignment_input",
]
