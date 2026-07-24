"""Application orchestration for Marketplace Opportunity synthesis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from dip.decision_intelligence import (
    MarketplaceMomentumOutput,
    MarketplaceOpportunityDiagnostic,
    MarketplaceOpportunityDiagnosticCode,
    MarketplaceOpportunityInput,
    MarketplaceScarcityOutput,
    MarketplaceStabilityOutput,
    OpportunityDimensionFact,
    OpportunityEvidenceCoverage,
    OpportunitySourceProvenance,
)
from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult, IntelligenceStatus


_SOURCE_ORDER = ("marketplace_momentum", "marketplace_stability", "marketplace_scarcity")
_EXPECTED = {
    "marketplace_momentum": MarketplaceMomentumOutput,
    "marketplace_stability": MarketplaceStabilityOutput,
    "marketplace_scarcity": MarketplaceScarcityOutput,
}


class _Provider(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _Engine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class MarketplaceOpportunityExecutionConsistencyError(RuntimeError):
    """Raised when the Opportunity execution boundary is violated."""


class MarketplaceOpportunityExecutionService:
    def __init__(self, momentum: _Provider, stability: _Provider, scarcity: _Provider, engine: _Engine):
        self._providers = (momentum, stability, scarcity)
        self._engine = engine

    def execute(self):
        prepared = build_marketplace_opportunity_input(tuple(provider.execute() for provider in self._providers))
        execution = self._engine.execute(IntelligenceContext(marketplace_opportunity_input=prepared))
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise MarketplaceOpportunityExecutionConsistencyError("Marketplace Opportunity engine must return exactly one result.")
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "marketplace_opportunity":
            raise MarketplaceOpportunityExecutionConsistencyError("Marketplace Opportunity engine returned an unexpected result.")
        return result


@dataclass(frozen=True)
class _Prepared:
    output: object
    provenance: OpportunitySourceProvenance


def build_marketplace_opportunity_input(source_results):
    if isinstance(source_results, (str, bytes)):
        raise TypeError("source_results must be a collection.")
    try:
        values = tuple(source_results)
    except TypeError as exc:
        raise TypeError("source_results must be a collection.") from exc
    diagnostics = []
    grouped = {}
    for value in values:
        if type(value) is not IntelligenceResult:
            diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.MALFORMED_TYPED_OUTPUT, "A supplied source is not an IntelligenceResult."))
        elif value.module_id not in _SOURCE_ORDER:
            diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.UNEXPECTED_SOURCE_RESULT, f"Unexpected source module {value.module_id!r}."))
        else:
            grouped.setdefault(value.module_id, []).append(value)
    prepared = {}
    for source_id in _SOURCE_ORDER:
        matches = grouped.get(source_id, ())
        if len(matches) > 1:
            diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.DUPLICATE_SOURCE_RESULT, f"Duplicate {source_id} results were supplied.", source_id))
            continue
        if not matches:
            diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.MISSING_REQUIRED_SOURCE, f"Required source {source_id} was not supplied.", source_id))
            continue
        item, item_diagnostics = _prepare(matches[0])
        prepared[source_id] = item
        diagnostics.extend(item_diagnostics)
    if all(source in prepared and prepared[source].provenance.compatible for source in _SOURCE_ORDER):
        identities = {prepared[source].provenance.history_snapshot_ids for source in _SOURCE_ORDER}
        if len(identities) != 1:
            diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.INCOMPATIBLE_PROVENANCE, "Required Decision Intelligence sources reference different evidence windows."))
            for source in _SOURCE_ORDER:
                prepared[source] = replace(prepared[source], provenance=replace(prepared[source].provenance, compatible=False))
    provenance = tuple(prepared[source].provenance for source in _SOURCE_ORDER if source in prepared)
    if not all(source in prepared and prepared[source].provenance.compatible for source in _SOURCE_ORDER):
        return MarketplaceOpportunityInput(source_provenance=provenance, diagnostics=tuple(diagnostics))
    momentum = prepared["marketplace_momentum"].output
    stability = prepared["marketplace_stability"].output
    scarcity = prepared["marketplace_scarcity"].output
    if type(momentum) is not MarketplaceMomentumOutput or type(stability) is not MarketplaceStabilityOutput or type(scarcity) is not MarketplaceScarcityOutput:
        raise MarketplaceOpportunityExecutionConsistencyError("Validated Opportunity sources lost their typed outputs.")
    releases = {
        "marketplace_momentum": {value.release_id: value for value in momentum.releases},
        "marketplace_stability": {value.release_id: value for value in stability.releases},
        "marketplace_scarcity": {value.release_id: value for value in scarcity.releases},
    }
    release_ids = sorted(set().union(*(set(values) for values in releases.values())))
    facts = []
    for release_id in release_ids:
        for source_id in _SOURCE_ORDER:
            value = releases[source_id].get(release_id)
            if value is None:
                diagnostics.append(MarketplaceOpportunityDiagnostic(
                    MarketplaceOpportunityDiagnosticCode.RELEASE_MISSING_FROM_SOURCE,
                    f"Release {release_id} is absent from {source_id}.",
                    source_module_id=source_id, release_id=release_id,
                ))
                continue
            coverage = (
                value.components.evidence.coverage
                if source_id == "marketplace_momentum"
                else value.components.evidence_coverage
                if source_id in {"marketplace_stability", "marketplace_scarcity"}
                else None
            )
            normalized_coverage = OpportunityEvidenceCoverage(coverage.value)
            if (
                prepared[source_id].provenance.diagnostics
                and normalized_coverage is OpportunityEvidenceCoverage.COMPLETE
            ):
                normalized_coverage = OpportunityEvidenceCoverage.PARTIAL
            facts.append(OpportunityDimensionFact(
                release_id, source_id, value.assessment.value,
                normalized_coverage,
            ))
    return MarketplaceOpportunityInput(provenance, tuple(facts), tuple(diagnostics))


def _prepare(result):
    source_id = result.module_id
    diagnostics = []
    output = result.metrics.get("output") if isinstance(result.metrics, Mapping) else None
    malformed = type(output) is not _EXPECTED[source_id]
    if result.module_version != "1.0":
        diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.UNSUPPORTED_SOURCE_VERSION, f"{source_id} uses unsupported version {result.module_version!r}.", source_id))
    rule_version = None if malformed else output.rule_set_version
    if rule_version != "1.0":
        diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.UNSUPPORTED_RULE_SET_VERSION, f"{source_id} uses unsupported rule set {rule_version!r}.", source_id))
    if result.status is not IntelligenceStatus.COMPLETED:
        diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.SOURCE_NOT_COMPLETED, f"{source_id} did not complete.", source_id))
    if malformed:
        diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.MALFORMED_TYPED_OUTPUT, f"{source_id} does not contain its expected typed output.", source_id))
    raw_diagnostics = tuple(result.diagnostics) if type(result.diagnostics) is tuple and all(type(value) is str for value in result.diagnostics) else ()
    if raw_diagnostics:
        diagnostics.append(_diagnostic(MarketplaceOpportunityDiagnosticCode.PARTIAL_SOURCE_DIAGNOSTICS, f"{source_id} supplied diagnostics that reduce synthesis coverage.", source_id))
    compatible = result.module_version == "1.0" and rule_version == "1.0" and result.status is IntelligenceStatus.COMPLETED and not malformed
    provenance = OpportunitySourceProvenance(
        source_id, result.module_version, rule_version, result.status, compatible,
        () if malformed else _history_ids(source_id, output), raw_diagnostics,
    )
    return _Prepared(output, provenance), tuple(diagnostics)


def _history_ids(source_id, output):
    target = {
        "marketplace_momentum": "marketplace_activity",
        "marketplace_stability": "listing_lifecycle",
        "marketplace_scarcity": "rare_appearances",
    }[source_id]
    value = next((value for value in output.source_provenance if value.module_id == target and value.compatible), None)
    return () if value is None else value.history_snapshot_ids


def _diagnostic(code, message, source=None):
    return MarketplaceOpportunityDiagnostic(code, message, source_module_id=source)


__all__ = [
    "MarketplaceOpportunityExecutionConsistencyError",
    "MarketplaceOpportunityExecutionService",
    "build_marketplace_opportunity_input",
]
