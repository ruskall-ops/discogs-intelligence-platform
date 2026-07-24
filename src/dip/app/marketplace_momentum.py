"""Application orchestration for Marketplace Momentum Decision Intelligence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import timezone
from typing import Protocol

from dip.decision_intelligence import (
    MarketplaceMomentumActivityFact,
    MarketplaceMomentumAppearanceFact,
    MarketplaceMomentumDiagnostic,
    MarketplaceMomentumDiagnosticCode,
    MarketplaceMomentumInput,
    MarketplaceMomentumLifecycleFact,
    MarketplaceMomentumListingState,
    MarketplaceMomentumPriceFact,
    MarketplaceMomentumPriceFactKind,
    MarketplaceMomentumSupplyFact,
    MarketplaceMomentumSupplyFactKind,
    SourceProvenance,
)
from dip.intelligence import IntelligenceContext, IntelligenceExecution, IntelligenceResult
from dip.intelligence.models import IntelligenceStatus
from dip.marketplace_intelligence import (
    ListingLifecycleAnalysisState,
    ListingLifecycleOutput,
    ListingLifecycleState,
    ListingPriceChangeKind,
    MarketplaceActivityOutput,
    MarketplaceActivityState,
    PriceChangesComparisonState,
    PriceChangesOutput,
    RareAppearancesAnalysisState,
    RareAppearancesOutput,
    ReleasePriceChangeKind,
    SupplyChangeKind,
    SupplyChangesComparisonState,
    SupplyChangesOutput,
)


_SOURCE_ORDER = (
    "price_changes",
    "supply_changes",
    "marketplace_activity",
    "rare_appearances",
    "listing_lifecycle",
)
_REQUIRED_SOURCE_IDS = _SOURCE_ORDER[:3]
_SUPPORTED_SOURCE_VERSIONS = {source_id: "1.0" for source_id in _SOURCE_ORDER}


class _ResultExecution(Protocol):
    def execute(self) -> IntelligenceResult: ...


class _MomentumEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class MarketplaceMomentumExecutionConsistencyError(RuntimeError):
    """Raised when the dedicated Momentum engine violates its result contract."""


class MarketplaceMomentumExecutionService:
    """Obtain source results, prepare typed input, and execute Momentum once."""

    def __init__(
        self,
        price_changes: _ResultExecution,
        supply_changes: _ResultExecution,
        marketplace_activity: _ResultExecution,
        engine: _MomentumEngine,
        *,
        rare_appearances: _ResultExecution | None = None,
        listing_lifecycle: _ResultExecution | None = None,
    ) -> None:
        self._price_changes = price_changes
        self._supply_changes = supply_changes
        self._marketplace_activity = marketplace_activity
        self._rare_appearances = rare_appearances
        self._listing_lifecycle = listing_lifecycle
        self._engine = engine

    def execute(self) -> IntelligenceResult:
        """Execute each direct source provider and the Momentum module once."""

        source_results: list[object] = [
            self._price_changes.execute(),
            self._supply_changes.execute(),
            self._marketplace_activity.execute(),
        ]
        if self._rare_appearances is not None:
            source_results.append(self._rare_appearances.execute())
        if self._listing_lifecycle is not None:
            source_results.append(self._listing_lifecycle.execute())
        prepared = build_marketplace_momentum_input(tuple(source_results))
        execution = self._engine.execute(
            IntelligenceContext(marketplace_momentum_input=prepared)
        )
        if type(execution) is not IntelligenceExecution:
            raise MarketplaceMomentumExecutionConsistencyError(
                "Marketplace Momentum engine must return an IntelligenceExecution."
            )
        if len(execution.results) != 1:
            raise MarketplaceMomentumExecutionConsistencyError(
                "Marketplace Momentum engine must return exactly one result."
            )
        result = execution.results[0]
        if type(result) is not IntelligenceResult:
            raise MarketplaceMomentumExecutionConsistencyError(
                "Marketplace Momentum engine returned a non-standard result."
            )
        if result.module_id != "marketplace_momentum":
            raise MarketplaceMomentumExecutionConsistencyError(
                "Marketplace Momentum engine returned an unexpected module result."
            )
        return result


@dataclass(frozen=True)
class _PreparedSource:
    result: IntelligenceResult
    output: object
    provenance: SourceProvenance


def build_marketplace_momentum_input(
    source_results: object,
) -> MarketplaceMomentumInput:
    """Validate one already-produced source bundle and normalise factual input."""

    if isinstance(source_results, (str, bytes)):
        raise TypeError("source_results must be a collection.")
    try:
        raw_results = tuple(source_results)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError("source_results must be a collection.") from exc

    diagnostics: list[MarketplaceMomentumDiagnostic] = []
    results_by_module: dict[str, list[IntelligenceResult]] = {}
    for value in raw_results:
        if type(value) is not IntelligenceResult:
            diagnostics.append(
                MarketplaceMomentumDiagnostic(
                    MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
                    "A supplied source value is not an IntelligenceResult.",
                )
            )
            continue
        if not isinstance(value.module_id, str) or value.module_id not in _SOURCE_ORDER:
            diagnostics.append(
                MarketplaceMomentumDiagnostic(
                    MarketplaceMomentumDiagnosticCode.UNEXPECTED_SOURCE_RESULT,
                    f"Unexpected source module {value.module_id!r} was supplied.",
                )
            )
            continue
        results_by_module.setdefault(value.module_id, []).append(value)

    prepared: dict[str, _PreparedSource] = {}
    for source_id in _SOURCE_ORDER:
        matches = results_by_module.get(source_id, ())
        if len(matches) > 1:
            diagnostics.append(
                MarketplaceMomentumDiagnostic(
                    MarketplaceMomentumDiagnosticCode.DUPLICATE_SOURCE_RESULT,
                    f"Duplicate {source_id} source results were supplied.",
                    source_module_id=source_id,
                )
            )
            continue
        if not matches:
            if source_id in _REQUIRED_SOURCE_IDS:
                diagnostics.append(
                    MarketplaceMomentumDiagnostic(
                        MarketplaceMomentumDiagnosticCode.MISSING_REQUIRED_SOURCE,
                        f"Required source result {source_id} was not supplied.",
                        source_module_id=source_id,
                    )
                )
            continue
        source, source_diagnostics = _prepare_source(matches[0])
        diagnostics.extend(source_diagnostics)
        if source is not None:
            prepared[source_id] = source

    if all(
        source_id in prepared and prepared[source_id].provenance.compatible
        for source_id in _REQUIRED_SOURCE_IDS
    ):
        compatibility_diagnostics = _required_compatibility(prepared)
        diagnostics.extend(compatibility_diagnostics)
        if compatibility_diagnostics:
            _mark_incompatible(prepared, _REQUIRED_SOURCE_IDS)

    if (
        "marketplace_activity" in prepared
        and prepared["marketplace_activity"].provenance.compatible
    ):
        diagnostics.extend(_validate_optional_sources(prepared))

    provenance = tuple(
        prepared[source_id].provenance
        for source_id in _SOURCE_ORDER
        if source_id in prepared
    )
    required_compatible = all(
        source_id in prepared and prepared[source_id].provenance.compatible
        for source_id in _REQUIRED_SOURCE_IDS
    )
    if not required_compatible:
        return MarketplaceMomentumInput(
            source_provenance=provenance,
            diagnostics=tuple(diagnostics),
        )

    price = prepared["price_changes"].output
    supply = prepared["supply_changes"].output
    activity = prepared["marketplace_activity"].output
    if (
        type(price) is not PriceChangesOutput
        or type(supply) is not SupplyChangesOutput
        or type(activity) is not MarketplaceActivityOutput
    ):
        raise MarketplaceMomentumExecutionConsistencyError(
            "Validated required Momentum sources lost their typed outputs."
        )
    rare = prepared.get("rare_appearances")
    lifecycle = prepared.get("listing_lifecycle")
    rare_output = (
        rare.output
        if rare is not None
        and rare.provenance.compatible
        and type(rare.output) is RareAppearancesOutput
        else None
    )
    lifecycle_output = (
        lifecycle.output
        if lifecycle is not None
        and lifecycle.provenance.compatible
        and type(lifecycle.output) is ListingLifecycleOutput
        else None
    )
    return MarketplaceMomentumInput(
        source_provenance=provenance,
        price_facts=_price_facts(price),
        supply_facts=_supply_facts(supply),
        activity_facts=_activity_facts(activity),
        appearance_facts=_appearance_facts(rare_output),
        lifecycle_facts=_lifecycle_facts(lifecycle_output),
        diagnostics=tuple(diagnostics),
    )


def _prepare_source(
    result: IntelligenceResult,
) -> tuple[_PreparedSource | None, tuple[MarketplaceMomentumDiagnostic, ...]]:
    source_id = result.module_id
    diagnostics: list[MarketplaceMomentumDiagnostic] = []
    if type(result.status) is not IntelligenceStatus:
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
                f"{source_id} status is not an IntelligenceStatus.",
                source_module_id=source_id,
            )
        )
        return None, tuple(diagnostics)
    raw_diagnostics = _source_diagnostics(result, diagnostics)
    if result.module_version != _SUPPORTED_SOURCE_VERSIONS[source_id]:
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.UNSUPPORTED_SOURCE_VERSION,
                (
                    f"{source_id} uses unsupported version "
                    f"{result.module_version!r}; version 1.0 is required."
                ),
                source_module_id=source_id,
            )
        )
    if result.status is not IntelligenceStatus.COMPLETED:
        code = (
            MarketplaceMomentumDiagnosticCode.SOURCE_NOT_COMPLETED
            if source_id in _REQUIRED_SOURCE_IDS
            else MarketplaceMomentumDiagnosticCode.OPTIONAL_SOURCE_UNAVAILABLE
        )
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                code,
                f"{source_id} did not complete and cannot contribute.",
                source_module_id=source_id,
            )
        )

    output = (
        result.metrics.get("output")
        if isinstance(result.metrics, Mapping)
        else None
    )
    expected_type = {
        "price_changes": PriceChangesOutput,
        "supply_changes": SupplyChangesOutput,
        "marketplace_activity": MarketplaceActivityOutput,
        "rare_appearances": RareAppearancesOutput,
        "listing_lifecycle": ListingLifecycleOutput,
    }[source_id]
    malformed = type(output) is not expected_type
    if malformed:
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
                f"{source_id} does not contain its expected typed output.",
                source_module_id=source_id,
            )
        )
    partial = False if malformed else _source_is_partial(source_id, output)
    supported_state = False if malformed else _source_state_is_usable(
        source_id,
        output,
    )
    if not malformed and not supported_state:
        code = (
            MarketplaceMomentumDiagnosticCode.SOURCE_NOT_COMPLETED
            if source_id in _REQUIRED_SOURCE_IDS
            else MarketplaceMomentumDiagnosticCode.OPTIONAL_SOURCE_UNAVAILABLE
        )
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                code,
                f"{source_id} typed output is not usable by Marketplace Momentum.",
                source_module_id=source_id,
            )
        )
    if partial or raw_diagnostics:
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.PARTIAL_SOURCE_DIAGNOSTICS,
                f"{source_id} supplied partial state or source diagnostics.",
                source_module_id=source_id,
            )
        )
    compatible = (
        result.module_version == _SUPPORTED_SOURCE_VERSIONS[source_id]
        and result.status is IntelligenceStatus.COMPLETED
        and not malformed
        and supported_state
        and raw_diagnostics is not None
    )
    snapshot_ids, source, source_versions = (
        ((), None, ())
        if malformed
        else _provenance_values(source_id, output)
    )
    provenance = SourceProvenance(
        module_id=source_id,
        module_version=result.module_version,
        result_status=result.status,
        compatible=compatible,
        partial=partial,
        history_snapshot_ids=snapshot_ids,
        source=source,
        source_versions=source_versions,
        diagnostics=raw_diagnostics or (),
    )
    return _PreparedSource(result, output, provenance), tuple(diagnostics)


def _source_diagnostics(
    result: IntelligenceResult,
    diagnostics: list[MarketplaceMomentumDiagnostic],
) -> tuple[str, ...] | None:
    if not isinstance(result.diagnostics, (tuple, list)):
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
                f"{result.module_id} diagnostics are not an ordered collection.",
                source_module_id=result.module_id,
            )
        )
        return None
    values = tuple(result.diagnostics)
    if any(
        not isinstance(value, str) or not value or value.strip() != value
        for value in values
    ):
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
                f"{result.module_id} diagnostics contain malformed text.",
                source_module_id=result.module_id,
            )
        )
        return None
    return values


def _source_state_is_usable(source_id: str, output: object) -> bool:
    if source_id == "price_changes":
        return output.comparison_state in {  # type: ignore[union-attr]
            PriceChangesComparisonState.COMPLETE,
            PriceChangesComparisonState.PARTIAL,
        }
    if source_id == "supply_changes":
        return output.comparison_state in {  # type: ignore[union-attr]
            SupplyChangesComparisonState.COMPLETE,
            SupplyChangesComparisonState.PARTIAL,
        }
    if source_id == "marketplace_activity":
        return output.state in {  # type: ignore[union-attr]
            MarketplaceActivityState.COMPLETE,
            MarketplaceActivityState.PARTIAL,
        }
    if source_id == "rare_appearances":
        return output.analysis_state in {  # type: ignore[union-attr]
            RareAppearancesAnalysisState.COMPLETE,
            RareAppearancesAnalysisState.PARTIAL,
        }
    return output.analysis_state in {  # type: ignore[union-attr]
        ListingLifecycleAnalysisState.COMPLETE,
        ListingLifecycleAnalysisState.PARTIAL,
    }


def _source_is_partial(source_id: str, output: object) -> bool:
    if source_id == "price_changes":
        return (  # type: ignore[union-attr]
            output.comparison_state is PriceChangesComparisonState.PARTIAL
        )
    if source_id == "supply_changes":
        return (  # type: ignore[union-attr]
            output.comparison_state is SupplyChangesComparisonState.PARTIAL
        )
    if source_id == "marketplace_activity":
        return output.state is MarketplaceActivityState.PARTIAL  # type: ignore[union-attr]
    if source_id == "rare_appearances":
        return (  # type: ignore[union-attr]
            output.analysis_state is RareAppearancesAnalysisState.PARTIAL
        )
    return output.analysis_state is ListingLifecycleAnalysisState.PARTIAL  # type: ignore[union-attr]


def _provenance_values(
    source_id: str,
    output: object,
) -> tuple[tuple[str, ...], str | None, tuple[str | None, ...]]:
    if source_id in {"price_changes", "supply_changes"}:
        references = tuple(
            value
            for value in (
                output.previous_snapshot,  # type: ignore[union-attr]
                output.latest_snapshot,  # type: ignore[union-attr]
            )
            if value is not None
        )
        return (
            tuple(value.snapshot_id for value in references),
            output.source,  # type: ignore[union-attr]
            tuple(value.source_version for value in references),
        )
    if source_id == "marketplace_activity":
        snapshot_ids = output.history_snapshot_ids  # type: ignore[union-attr]
    else:
        snapshot_ids = tuple(  # type: ignore[union-attr]
            value.snapshot_id for value in output.snapshots
        )
    return snapshot_ids, None, (None,) * len(snapshot_ids)


def _required_compatibility(
    prepared: dict[str, _PreparedSource],
) -> tuple[MarketplaceMomentumDiagnostic, ...]:
    price = prepared["price_changes"].output
    supply = prepared["supply_changes"].output
    activity = prepared["marketplace_activity"].output
    if (
        type(price) is not PriceChangesOutput
        or type(supply) is not SupplyChangesOutput
        or type(activity) is not MarketplaceActivityOutput
    ):
        return (
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
                "Required typed source outputs are unavailable after validation.",
            ),
        )
    diagnostics: list[MarketplaceMomentumDiagnostic] = []
    price_refs = (price.previous_snapshot, price.latest_snapshot)
    supply_refs = (supply.previous_snapshot, supply.latest_snapshot)
    if any(value is None for value in (*price_refs, *supply_refs)):
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.INCOMPATIBLE_HISTORY,
                "Price Changes and Supply Changes must each reference two snapshots.",
            )
        )
        return tuple(diagnostics)
    price_pair = tuple(value.snapshot_id for value in price_refs if value is not None)
    supply_pair = tuple(
        value.snapshot_id for value in supply_refs if value is not None
    )
    if price_pair != supply_pair:
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.INCOMPATIBLE_HISTORY,
                "Price Changes and Supply Changes reference different snapshot pairs.",
            )
        )
    else:
        for price_ref, supply_ref in zip(price_refs, supply_refs, strict=True):
            if price_ref is None or supply_ref is None:
                continue
            if (
                price_ref.captured_at.astimezone(timezone.utc)
                != supply_ref.captured_at.astimezone(timezone.utc)
                or price_ref.source != supply_ref.source
                or price_ref.status is not supply_ref.status
                or price_ref.source_version != supply_ref.source_version
            ):
                diagnostics.append(
                    MarketplaceMomentumDiagnostic(
                        MarketplaceMomentumDiagnosticCode.CONFLICTING_PROVENANCE,
                        (
                            f"Snapshot {price_ref.snapshot_id} metadata conflicts "
                            "between Price Changes and Supply Changes."
                        ),
                    )
                )
    if price.source is None or price.source != supply.source:
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.CONFLICTING_PROVENANCE,
                "Price Changes and Supply Changes do not share one source identity.",
            )
        )
    if (
        len(activity.history_snapshot_ids) < 2
        or price_pair != activity.history_snapshot_ids[-2:]
    ):
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.INCOMPATIBLE_HISTORY,
                (
                    "The required comparison pair is not the latest pair in "
                    "Marketplace Activity history."
                ),
                source_module_id="marketplace_activity",
            )
        )

    price_counts = Counter(
        value.release_id
        for value in (*price.listing_changes, *price.release_changes)
    )
    supply_counts = Counter(value.release_id for value in supply.changes)
    mismatched = tuple(
        value.release_id
        for value in activity.activities
        if (
            value.historical_price_change_count != price_counts[value.release_id]
            or value.historical_supply_change_count
            != supply_counts[value.release_id]
        )
    )
    if mismatched:
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.SOURCE_ACTIVITY_MISMATCH,
                (
                    "Marketplace Activity source counts conflict for release IDs: "
                    + ", ".join(str(value) for value in sorted(mismatched))
                    + "."
                ),
                source_module_id="marketplace_activity",
            )
        )
    return tuple(diagnostics)


def _validate_optional_sources(
    prepared: dict[str, _PreparedSource],
) -> tuple[MarketplaceMomentumDiagnostic, ...]:
    activity = prepared["marketplace_activity"].output
    if type(activity) is not MarketplaceActivityOutput:
        return ()
    diagnostics: list[MarketplaceMomentumDiagnostic] = []
    rare = prepared.get("rare_appearances")
    if (
        rare is not None
        and rare.provenance.compatible
        and type(rare.output) is RareAppearancesOutput
    ):
        incompatible = tuple(value.snapshot_id for value in rare.output.snapshots) != (
            activity.history_snapshot_ids
        )
        activity_by_id = {
            value.release_id: value for value in activity.activities
        }
        rare_by_id = {
            value.release_id: value for value in rare.output.appearances
        }
        conflicts = tuple(
            release_id
            for release_id in sorted(set(activity_by_id) & set(rare_by_id))
            if not _appearance_matches(
                activity_by_id[release_id],
                rare_by_id[release_id],
            )
        )
        if incompatible or conflicts:
            message = (
                "Rare Appearances references different Marketplace history."
                if incompatible
                else (
                    "Rare Appearances conflicts with Marketplace Activity for "
                    "release IDs: "
                    + ", ".join(str(value) for value in conflicts)
                    + "."
                )
            )
            diagnostics.append(
                MarketplaceMomentumDiagnostic(
                    MarketplaceMomentumDiagnosticCode.CONFLICTING_PROVENANCE,
                    message,
                    source_module_id="rare_appearances",
                )
            )
            _mark_incompatible(prepared, ("rare_appearances",))

    lifecycle = prepared.get("listing_lifecycle")
    if (
        lifecycle is not None
        and lifecycle.provenance.compatible
        and type(lifecycle.output) is ListingLifecycleOutput
        and tuple(value.snapshot_id for value in lifecycle.output.snapshots)
        != activity.history_snapshot_ids
    ):
        diagnostics.append(
            MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.CONFLICTING_PROVENANCE,
                "Listing Lifecycle references different Marketplace history.",
                source_module_id="listing_lifecycle",
            )
        )
        _mark_incompatible(prepared, ("listing_lifecycle",))
    return tuple(diagnostics)


def _appearance_matches(activity: object, appearance: object) -> bool:
    return (
        activity.appearance_count == appearance.appearance_count
        and activity.appearance_ratio == appearance.appearance_ratio
        and activity.longest_absence == appearance.longest_absence
        and activity.first_observation.snapshot_id
        == appearance.first_observed_snapshot.snapshot_id
        and activity.latest_observation.snapshot_id
        == appearance.latest_observed_snapshot.snapshot_id
        and activity.first_observation.captured_at
        == appearance.first_observed_snapshot.captured_at
        and activity.latest_observation.captured_at
        == appearance.latest_observed_snapshot.captured_at
    )


def _mark_incompatible(
    prepared: dict[str, _PreparedSource],
    source_ids: tuple[str, ...],
) -> None:
    for source_id in source_ids:
        source = prepared.get(source_id)
        if source is not None and source.provenance.compatible:
            prepared[source_id] = replace(
                source,
                provenance=replace(source.provenance, compatible=False),
            )


def _price_facts(
    output: PriceChangesOutput,
) -> tuple[MarketplaceMomentumPriceFact, ...]:
    listing_kind = {
        ListingPriceChangeKind.INCREASED:
            MarketplaceMomentumPriceFactKind.INCREASED,
        ListingPriceChangeKind.DECREASED:
            MarketplaceMomentumPriceFactKind.DECREASED,
        ListingPriceChangeKind.NEWLY_OBSERVED:
            MarketplaceMomentumPriceFactKind.NEWLY_OBSERVED,
        ListingPriceChangeKind.NO_LONGER_OBSERVED:
            MarketplaceMomentumPriceFactKind.NO_LONGER_OBSERVED,
        ListingPriceChangeKind.INCOMPARABLE:
            MarketplaceMomentumPriceFactKind.INCOMPARABLE,
    }
    release_kind = {
        ReleasePriceChangeKind.INCREASED:
            MarketplaceMomentumPriceFactKind.INCREASED,
        ReleasePriceChangeKind.DECREASED:
            MarketplaceMomentumPriceFactKind.DECREASED,
        ReleasePriceChangeKind.NEWLY_AVAILABLE:
            MarketplaceMomentumPriceFactKind.NEWLY_OBSERVED,
        ReleasePriceChangeKind.NO_LONGER_AVAILABLE:
            MarketplaceMomentumPriceFactKind.NO_LONGER_OBSERVED,
        ReleasePriceChangeKind.INCOMPARABLE:
            MarketplaceMomentumPriceFactKind.INCOMPARABLE,
    }
    values = (
        *(
            MarketplaceMomentumPriceFact(
                value.release_id,
                f"listing:{value.release_id}:{value.listing_id}",
                listing_kind[value.change_kind],
            )
            for value in output.listing_changes
        ),
        *(
            MarketplaceMomentumPriceFact(
                value.release_id,
                f"release:{value.release_id}:{value.metric.value}",
                release_kind[value.change_kind],
            )
            for value in output.release_changes
        ),
    )
    return tuple(sorted(values, key=lambda value: (value.release_id, value.fact_id)))


def _supply_facts(
    output: SupplyChangesOutput,
) -> tuple[MarketplaceMomentumSupplyFact, ...]:
    kinds = {
        SupplyChangeKind.INCREASED:
            MarketplaceMomentumSupplyFactKind.INCREASED,
        SupplyChangeKind.DECREASED:
            MarketplaceMomentumSupplyFactKind.DECREASED,
        SupplyChangeKind.NEWLY_AVAILABLE:
            MarketplaceMomentumSupplyFactKind.NEWLY_AVAILABLE,
        SupplyChangeKind.NO_LONGER_AVAILABLE:
            MarketplaceMomentumSupplyFactKind.NO_LONGER_AVAILABLE,
        SupplyChangeKind.INCOMPARABLE:
            MarketplaceMomentumSupplyFactKind.INCOMPARABLE,
    }
    return tuple(
        MarketplaceMomentumSupplyFact(value.release_id, kinds[value.change_kind])
        for value in output.changes
    )


def _activity_facts(
    output: MarketplaceActivityOutput,
) -> tuple[MarketplaceMomentumActivityFact, ...]:
    return tuple(
        MarketplaceMomentumActivityFact(
            release_id=value.release_id,
            total_activity_count=value.total_activity_count,
            historical_price_change_count=value.historical_price_change_count,
            historical_supply_change_count=value.historical_supply_change_count,
            appearance_count=value.appearance_count,
            appearance_ratio=value.appearance_ratio,
            longest_absence=value.longest_absence,
        )
        for value in sorted(output.activities, key=lambda item: item.release_id)
    )


def _appearance_facts(
    output: RareAppearancesOutput | None,
) -> tuple[MarketplaceMomentumAppearanceFact, ...]:
    if output is None:
        return ()
    return tuple(
        MarketplaceMomentumAppearanceFact(
            value.release_id,
            value.appearance_count,
            value.appearance_ratio,
            value.longest_absence,
        )
        for value in sorted(output.appearances, key=lambda item: item.release_id)
    )


def _lifecycle_facts(
    output: ListingLifecycleOutput | None,
) -> tuple[MarketplaceMomentumLifecycleFact, ...]:
    if output is None:
        return ()
    state_mapping = {
        ListingLifecycleState.NEW: MarketplaceMomentumListingState.NEW,
        ListingLifecycleState.ACTIVE: MarketplaceMomentumListingState.ACTIVE,
        ListingLifecycleState.DISAPPEARED:
            MarketplaceMomentumListingState.DISAPPEARED,
        ListingLifecycleState.REAPPEARED:
            MarketplaceMomentumListingState.REAPPEARED,
        ListingLifecycleState.INTERMITTENT:
            MarketplaceMomentumListingState.INTERMITTENT,
        ListingLifecycleState.ENDED: MarketplaceMomentumListingState.ENDED,
    }
    return tuple(
        MarketplaceMomentumLifecycleFact(
            value.release_id,
            value.listing_id,
            state_mapping[value.lifecycle_state],
            value.currently_present,
        )
        for value in sorted(
            output.lifecycles,
            key=lambda item: (item.release_id, item.listing_id),
        )
    )


__all__ = [
    "MarketplaceMomentumExecutionConsistencyError",
    "MarketplaceMomentumExecutionService",
    "build_marketplace_momentum_input",
]
