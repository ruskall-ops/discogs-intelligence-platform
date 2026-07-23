"""Application orchestration for Marketplace Stability Decision Intelligence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from dip.decision_intelligence import (
    MarketplaceStabilityDiagnostic,
    MarketplaceStabilityDiagnosticCode,
    MarketplaceStabilityInput,
    StabilityActivityFact,
    StabilityLifecycleFact,
    StabilityListingState,
    StabilityMomentumContext,
    StabilitySourceProvenance,
)
from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import (
    ListingLifecycleAnalysisState,
    ListingLifecycleOutput,
    MarketplaceActivityOutput,
    MarketplaceActivityState,
    PriceChangesOutput,
    RareAppearancesOutput,
    SupplyChangesOutput,
)
from dip.decision_intelligence import MarketplaceMomentumOutput


_SOURCE_ORDER = (
    "marketplace_activity",
    "listing_lifecycle",
    "price_changes",
    "supply_changes",
    "rare_appearances",
    "marketplace_momentum",
)
_REQUIRED = _SOURCE_ORDER[:2]
_EXPECTED = {
    "marketplace_activity": MarketplaceActivityOutput,
    "listing_lifecycle": ListingLifecycleOutput,
    "price_changes": PriceChangesOutput,
    "supply_changes": SupplyChangesOutput,
    "rare_appearances": RareAppearancesOutput,
    "marketplace_momentum": MarketplaceMomentumOutput,
}


class _Provider(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _Engine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class MarketplaceStabilityExecutionConsistencyError(RuntimeError):
    """Raised when the Stability execution boundary is violated."""


class MarketplaceStabilityExecutionService:
    def __init__(
        self,
        marketplace_activity: _Provider,
        listing_lifecycle: _Provider,
        engine: _Engine,
        *,
        price_changes: _Provider | None = None,
        supply_changes: _Provider | None = None,
        rare_appearances: _Provider | None = None,
        marketplace_momentum: _Provider | None = None,
    ) -> None:
        self._providers = (
            marketplace_activity,
            listing_lifecycle,
            price_changes,
            supply_changes,
            rare_appearances,
            marketplace_momentum,
        )
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        results = tuple(provider.execute() for provider in self._providers if provider is not None)
        prepared = build_marketplace_stability_input(results)
        execution = self._engine.execute(IntelligenceContext(marketplace_stability_input=prepared))
        if type(execution) is not IntelligenceExecution or len(execution.results) != 1:
            raise MarketplaceStabilityExecutionConsistencyError(
                "Marketplace Stability engine must return exactly one IntelligenceExecution result."
            )
        result = execution.results[0]
        if type(result) is not IntelligenceResult or result.module_id != "marketplace_stability":
            raise MarketplaceStabilityExecutionConsistencyError(
                "Marketplace Stability engine returned an unexpected result."
            )
        return result


@dataclass(frozen=True)
class _Prepared:
    result: IntelligenceResult
    output: object
    provenance: StabilitySourceProvenance


def build_marketplace_stability_input(source_results: object) -> MarketplaceStabilityInput:
    if isinstance(source_results, (str, bytes)):
        raise TypeError("source_results must be a collection.")
    try:
        values = tuple(source_results)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError("source_results must be a collection.") from exc
    diagnostics: list[MarketplaceStabilityDiagnostic] = []
    grouped: dict[str, list[IntelligenceResult]] = {}
    for value in values:
        if type(value) is not IntelligenceResult:
            diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.MALFORMED_TYPED_OUTPUT, "A supplied source is not an IntelligenceResult."))
        elif value.module_id not in _SOURCE_ORDER:
            diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.UNEXPECTED_SOURCE_RESULT, f"Unexpected source module {value.module_id!r}."))
        else:
            grouped.setdefault(value.module_id, []).append(value)
    prepared: dict[str, _Prepared] = {}
    for source_id in _SOURCE_ORDER:
        matches = grouped.get(source_id, ())
        if len(matches) > 1:
            diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.DUPLICATE_SOURCE_RESULT, f"Duplicate {source_id} results were supplied.", source_id))
            continue
        if not matches:
            if source_id in _REQUIRED:
                diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.MISSING_REQUIRED_SOURCE, f"Required source {source_id} was not supplied.", source_id))
            continue
        item, item_diagnostics = _prepare(matches[0])
        diagnostics.extend(item_diagnostics)
        if item is not None:
            prepared[source_id] = item
    if all(source in prepared and prepared[source].provenance.compatible for source in _REQUIRED):
        activity_ids = prepared["marketplace_activity"].provenance.history_snapshot_ids
        lifecycle_ids = prepared["listing_lifecycle"].provenance.history_snapshot_ids
        if activity_ids != lifecycle_ids:
            diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.INCOMPATIBLE_HISTORY, "Marketplace Activity and Listing Lifecycle reference different analyzed histories."))
            for source in _REQUIRED:
                prepared[source] = replace(prepared[source], provenance=replace(prepared[source].provenance, compatible=False))
        else:
            for source_id in _SOURCE_ORDER[2:]:
                item = prepared.get(source_id)
                if item is not None and item.provenance.compatible:
                    optional_ids = item.provenance.history_snapshot_ids
                    if optional_ids and not _compatible_optional(optional_ids, activity_ids):
                        diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.OPTIONAL_SOURCE_EXCLUDED, f"{source_id} references incompatible Marketplace history and was excluded.", source_id))
                        prepared[source_id] = replace(item, provenance=replace(item.provenance, compatible=False))
    provenance = tuple(prepared[source].provenance for source in _SOURCE_ORDER if source in prepared)
    required_ok = all(source in prepared and prepared[source].provenance.compatible for source in _REQUIRED)
    if not required_ok:
        return MarketplaceStabilityInput(source_provenance=provenance, diagnostics=tuple(diagnostics))
    activity = prepared["marketplace_activity"].output
    lifecycle = prepared["listing_lifecycle"].output
    if type(activity) is not MarketplaceActivityOutput or type(lifecycle) is not ListingLifecycleOutput:
        raise MarketplaceStabilityExecutionConsistencyError("Validated Stability outputs lost their types.")
    momentum_item = prepared.get("marketplace_momentum")
    momentum = momentum_item.output if momentum_item and momentum_item.provenance.compatible and type(momentum_item.output) is MarketplaceMomentumOutput else None
    return MarketplaceStabilityInput(
        source_provenance=provenance,
        activity_facts=tuple(
            StabilityActivityFact(
                value.release_id, value.historical_price_change_count,
                value.historical_supply_change_count, value.appearance_count,
                value.appearance_ratio, value.longest_absence,
                value.total_activity_count,
            ) for value in activity.activities
        ),
        lifecycle_facts=tuple(
            StabilityLifecycleFact(
                value.release_id, value.listing_id,
                StabilityListingState(value.lifecycle_state.value),
                value.currently_present, value.disappearance_count,
                value.reappearance_count,
            ) for value in lifecycle.lifecycles
        ),
        momentum_context=() if momentum is None else tuple(
            StabilityMomentumContext(value.release_id, value.assessment.value)
            for value in momentum.releases
        ),
        diagnostics=tuple(diagnostics),
    )


def _prepare(result: IntelligenceResult):
    source_id = result.module_id
    diagnostics = []
    output = result.metrics.get("output") if isinstance(result.metrics, Mapping) else None
    malformed = type(output) is not _EXPECTED[source_id]
    if result.module_version != "1.0":
        diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.UNSUPPORTED_SOURCE_VERSION, f"{source_id} uses unsupported version {result.module_version!r}.", source_id))
    if result.status is not IntelligenceStatus.COMPLETED:
        diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.SOURCE_NOT_COMPLETED if source_id in _REQUIRED else MarketplaceStabilityDiagnosticCode.OPTIONAL_SOURCE_EXCLUDED, f"{source_id} did not complete.", source_id))
    if malformed:
        diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.MALFORMED_TYPED_OUTPUT, f"{source_id} does not contain its expected typed output.", source_id))
    raw_diagnostics = tuple(result.diagnostics) if type(result.diagnostics) is tuple and all(type(value) is str for value in result.diagnostics) else ()
    if result.diagnostics and not raw_diagnostics:
        malformed = True
        diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.MALFORMED_TYPED_OUTPUT, f"{source_id} diagnostics are malformed.", source_id))
    partial = False if malformed else _partial(source_id, output)
    if partial or raw_diagnostics:
        diagnostics.append(_diagnostic(MarketplaceStabilityDiagnosticCode.PARTIAL_SOURCE_DIAGNOSTICS, f"{source_id} supplied partial state or diagnostics.", source_id))
    compatible = result.module_version == "1.0" and result.status is IntelligenceStatus.COMPLETED and not malformed and _usable(source_id, output)
    provenance = StabilitySourceProvenance(
        source_id, result.module_version, result.status, compatible, partial,
        () if malformed else _history_ids(source_id, output), raw_diagnostics,
    )
    return _Prepared(result, output, provenance), tuple(diagnostics)


def _history_ids(source_id, output):
    if source_id == "marketplace_activity":
        return output.history_snapshot_ids
    if source_id == "listing_lifecycle":
        return tuple(value.snapshot_id for value in output.snapshots)
    if source_id in {"price_changes", "supply_changes"}:
        refs = (output.previous_snapshot, output.latest_snapshot)
        return tuple(value.snapshot_id for value in refs if value is not None)
    if source_id == "rare_appearances":
        return tuple(value.snapshot_id for value in output.snapshots)
    if source_id == "marketplace_momentum":
        activity = next((value for value in output.source_provenance if value.module_id == "marketplace_activity" and value.compatible), None)
        return () if activity is None else activity.history_snapshot_ids
    return ()


def _partial(source_id, output):
    state = getattr(output, "state", getattr(output, "analysis_state", None))
    return getattr(state, "value", "") == "partial"


def _usable(source_id, output):
    state = getattr(output, "state", getattr(output, "analysis_state", None))
    return getattr(state, "value", "") not in {"insufficient_data", "insufficient_history"}


def _compatible_optional(optional_ids, activity_ids):
    if len(optional_ids) == 2:
        return optional_ids == activity_ids[-2:]
    return optional_ids == activity_ids


def _diagnostic(code, message, source=None):
    return MarketplaceStabilityDiagnostic(code, message, source_module_id=source)


__all__ = [
    "MarketplaceStabilityExecutionConsistencyError",
    "MarketplaceStabilityExecutionService",
    "build_marketplace_stability_input",
]

