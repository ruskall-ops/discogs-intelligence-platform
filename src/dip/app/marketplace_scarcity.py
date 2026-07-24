"""Application orchestration for Marketplace Scarcity Decision Intelligence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from dip.decision_intelligence import (
    MarketplaceMomentumOutput,
    MarketplaceScarcityDiagnostic,
    MarketplaceScarcityDiagnosticCode,
    MarketplaceScarcityInput,
    MarketplaceStabilityOutput,
    ScarcityAppearanceFact,
    ScarcityDecisionContext,
    ScarcityLifecycleFact,
    ScarcityListingState,
    ScarcitySourceProvenance,
    ScarcitySupplyContext,
)
from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import (
    ListingLifecycleOutput,
    MarketplaceActivityOutput,
    RareAppearancesOutput,
    SupplyChangeKind,
    SupplyChangesOutput,
)


_SOURCE_ORDER = (
    "rare_appearances",
    "listing_lifecycle",
    "marketplace_activity",
    "supply_changes",
    "marketplace_stability",
    "marketplace_momentum",
)
_REQUIRED = _SOURCE_ORDER[:2]
_EXPECTED = {
    "rare_appearances": RareAppearancesOutput,
    "listing_lifecycle": ListingLifecycleOutput,
    "marketplace_activity": MarketplaceActivityOutput,
    "supply_changes": SupplyChangesOutput,
    "marketplace_stability": MarketplaceStabilityOutput,
    "marketplace_momentum": MarketplaceMomentumOutput,
}


class _Provider(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _Engine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class MarketplaceScarcityExecutionConsistencyError(RuntimeError):
    """Raised when the dedicated Scarcity execution contract is violated."""


class MarketplaceScarcityExecutionService:
    def __init__(
        self,
        rare_appearances: _Provider,
        listing_lifecycle: _Provider,
        engine: _Engine,
        *,
        marketplace_activity: _Provider | None = None,
        supply_changes: _Provider | None = None,
        marketplace_stability: _Provider | None = None,
        marketplace_momentum: _Provider | None = None,
    ):
        self._providers = (
            rare_appearances, listing_lifecycle, marketplace_activity,
            supply_changes, marketplace_stability, marketplace_momentum,
        )
        self._engine = engine

    def execute(self):
        results = tuple(provider.execute() for provider in self._providers if provider is not None)
        prepared = build_marketplace_scarcity_input(results)
        execution = self._engine.execute(IntelligenceContext(marketplace_scarcity_input=prepared))
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise MarketplaceScarcityExecutionConsistencyError("Marketplace Scarcity engine must return exactly one result.")
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "marketplace_scarcity":
            raise MarketplaceScarcityExecutionConsistencyError("Marketplace Scarcity engine returned an unexpected result.")
        return result


@dataclass(frozen=True)
class _Prepared:
    output: object
    provenance: ScarcitySourceProvenance


def build_marketplace_scarcity_input(source_results):
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
            diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.MALFORMED_TYPED_OUTPUT, "A supplied source is not an IntelligenceResult."))
        elif value.module_id not in _SOURCE_ORDER:
            diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.UNEXPECTED_SOURCE_RESULT, f"Unexpected source module {value.module_id!r}."))
        else:
            grouped.setdefault(value.module_id, []).append(value)
    prepared = {}
    for source_id in _SOURCE_ORDER:
        matches = grouped.get(source_id, ())
        if len(matches) > 1:
            diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.DUPLICATE_SOURCE_RESULT, f"Duplicate {source_id} results were supplied.", source_id))
            continue
        if not matches:
            if source_id in _REQUIRED:
                diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.MISSING_REQUIRED_SOURCE, f"Required source {source_id} was not supplied.", source_id))
            continue
        item, item_diagnostics = _prepare(matches[0])
        prepared[source_id] = item
        diagnostics.extend(item_diagnostics)
    if all(source in prepared and prepared[source].provenance.compatible for source in _REQUIRED):
        history_ids = prepared["rare_appearances"].provenance.history_snapshot_ids
        if history_ids != prepared["listing_lifecycle"].provenance.history_snapshot_ids:
            diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.INCOMPATIBLE_HISTORY, "Rare Appearances and Listing Lifecycle reference different analyzed histories."))
            for source in _REQUIRED:
                prepared[source] = replace(prepared[source], provenance=replace(prepared[source].provenance, compatible=False))
        else:
            for source in _SOURCE_ORDER[2:]:
                item = prepared.get(source)
                if item and item.provenance.compatible and item.provenance.history_snapshot_ids and not _optional_compatible(item.provenance.history_snapshot_ids, history_ids):
                    diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.OPTIONAL_SOURCE_EXCLUDED, f"{source} references incompatible Marketplace history and was excluded.", source))
                    prepared[source] = replace(item, provenance=replace(item.provenance, compatible=False))
    provenance = tuple(prepared[source].provenance for source in _SOURCE_ORDER if source in prepared)
    if not all(source in prepared and prepared[source].provenance.compatible for source in _REQUIRED):
        return MarketplaceScarcityInput(source_provenance=provenance, diagnostics=tuple(diagnostics))
    rare = prepared["rare_appearances"].output
    lifecycle = prepared["listing_lifecycle"].output
    if type(rare) is not RareAppearancesOutput or type(lifecycle) is not ListingLifecycleOutput:
        raise MarketplaceScarcityExecutionConsistencyError("Validated required outputs lost their types.")
    activity = _optional_output(prepared, "marketplace_activity", MarketplaceActivityOutput)
    supply = _optional_output(prepared, "supply_changes", SupplyChangesOutput)
    stability = _optional_output(prepared, "marketplace_stability", MarketplaceStabilityOutput)
    momentum = _optional_output(prepared, "marketplace_momentum", MarketplaceMomentumOutput)
    supply_context = _supply_context(activity, supply)
    stability_by_id = {} if stability is None else {value.release_id: value.assessment.value for value in stability.releases}
    momentum_by_id = {} if momentum is None else {value.release_id: value.assessment.value for value in momentum.releases}
    context_ids = sorted(set(stability_by_id) | set(momentum_by_id))
    return MarketplaceScarcityInput(
        source_provenance=provenance,
        appearance_facts=tuple(ScarcityAppearanceFact(
            value.release_id, value.appearance_count, value.history_snapshot_count,
            value.appearance_ratio, value.longest_absence,
        ) for value in rare.appearances),
        lifecycle_facts=tuple(ScarcityLifecycleFact(
            value.release_id, value.listing_id, ScarcityListingState(value.lifecycle_state.value),
            value.currently_present, value.observation_ratio, value.disappearance_count,
            value.reappearance_count, value.longest_absence,
        ) for value in lifecycle.lifecycles),
        supply_context=supply_context,
        decision_context=tuple(ScarcityDecisionContext(
            release_id, stability_by_id.get(release_id), momentum_by_id.get(release_id)
        ) for release_id in context_ids),
        diagnostics=tuple(diagnostics),
    )


def _prepare(result):
    source_id = result.module_id
    diagnostics = []
    output = result.metrics.get("output") if isinstance(result.metrics, Mapping) else None
    malformed = type(output) is not _EXPECTED[source_id]
    if result.module_version != "1.0":
        diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.UNSUPPORTED_SOURCE_VERSION, f"{source_id} uses unsupported version {result.module_version!r}.", source_id))
    if result.status is not IntelligenceStatus.COMPLETED:
        diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.SOURCE_NOT_COMPLETED if source_id in _REQUIRED else MarketplaceScarcityDiagnosticCode.OPTIONAL_SOURCE_EXCLUDED, f"{source_id} did not complete.", source_id))
    if malformed:
        diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.MALFORMED_TYPED_OUTPUT, f"{source_id} does not contain its expected typed output.", source_id))
    raw_diagnostics = tuple(result.diagnostics) if type(result.diagnostics) is tuple and all(type(value) is str for value in result.diagnostics) else ()
    partial = False if malformed else getattr(getattr(output, "analysis_state", getattr(output, "state", getattr(output, "comparison_state", None))), "value", "") == "partial"
    if partial or raw_diagnostics:
        diagnostics.append(_diagnostic(MarketplaceScarcityDiagnosticCode.PARTIAL_SOURCE_DIAGNOSTICS, f"{source_id} supplied partial state or diagnostics.", source_id))
    state = getattr(getattr(output, "analysis_state", getattr(output, "state", getattr(output, "comparison_state", None))), "value", "")
    compatible = result.module_version == "1.0" and result.status is IntelligenceStatus.COMPLETED and not malformed and state not in {"insufficient_data", "insufficient_history", "failed"}
    return _Prepared(output, ScarcitySourceProvenance(
        source_id, result.module_version, result.status, compatible, partial,
        () if malformed else _history_ids(source_id, output), raw_diagnostics,
    )), tuple(diagnostics)


def _history_ids(source_id, output):
    if source_id in {"rare_appearances", "listing_lifecycle"}:
        return tuple(value.snapshot_id for value in output.snapshots)
    if source_id == "marketplace_activity":
        return output.history_snapshot_ids
    if source_id == "supply_changes":
        return tuple(value.snapshot_id for value in (output.previous_snapshot, output.latest_snapshot) if value is not None)
    if source_id == "marketplace_stability":
        rare = next((value for value in output.source_provenance if value.module_id == "rare_appearances" and value.compatible), None)
        return () if rare is None else rare.history_snapshot_ids
    if source_id == "marketplace_momentum":
        activity = next((value for value in output.source_provenance if value.module_id == "marketplace_activity" and value.compatible), None)
        return () if activity is None else activity.history_snapshot_ids
    return ()


def _optional_compatible(optional_ids, history_ids):
    return optional_ids == history_ids or (len(optional_ids) == 2 and optional_ids == history_ids[-2:])


def _optional_output(prepared, source_id, expected):
    item = prepared.get(source_id)
    return item.output if item and item.provenance.compatible and type(item.output) is expected else None


def _supply_context(activity, supply):
    activity_counts = {} if activity is None else {value.release_id: value.historical_supply_change_count for value in activity.activities}
    changes = {} if supply is None else {value.release_id: value for value in supply.changes}
    values = []
    for release_id in sorted(set(activity_counts) | set(changes)):
        change = changes.get(release_id)
        kind = None if change is None else change.change_kind
        values.append(ScarcitySupplyContext(
            release_id, activity_counts.get(release_id),
            int(kind is SupplyChangeKind.INCREASED),
            int(kind is SupplyChangeKind.DECREASED),
            int(kind is SupplyChangeKind.NEWLY_AVAILABLE),
            int(kind is SupplyChangeKind.NO_LONGER_AVAILABLE),
        ))
    return tuple(values)


def _diagnostic(code, message, source=None):
    return MarketplaceScarcityDiagnostic(code, message, source_module_id=source)


__all__ = [
    "MarketplaceScarcityExecutionConsistencyError",
    "MarketplaceScarcityExecutionService",
    "build_marketplace_scarcity_input",
]

