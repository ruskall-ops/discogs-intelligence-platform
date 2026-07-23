"""Map typed Marketplace Momentum output without interpretation or ordering."""

from collections.abc import Mapping

from dip.decision_intelligence import (
    AppearancePersistenceContext,
    FactualSupportingContext,
    ListingPersistenceContext,
    MarketplaceMomentumDiagnostic,
    MarketplaceMomentumOutput,
    MomentumAnalysisState,
    ReleaseMomentum,
    SourceProvenance,
)
from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .models import (
    ActivityIntensityComponentViewModel,
    ActivityIntensityThresholdsViewModel,
    AppearancePersistenceContextViewModel,
    EvidenceCoverageComponentViewModel,
    FactualSupportingContextViewModel,
    ListingPersistenceContextViewModel,
    MarketplaceMomentumDetailConsistencyError,
    MarketplaceMomentumDetailState,
    MarketplaceMomentumDetailViewModel,
    MarketplaceMomentumDiagnosticViewModel,
    MarketplaceMomentumSummaryViewModel,
    PriceDirectionComponentViewModel,
    ReleaseMomentumViewModel,
    SourceProvenanceViewModel,
    SupplyDirectionComponentViewModel,
)


class MarketplaceMomentumDetailViewModelBuilder:
    """Project one typed Momentum result directly into immutable ViewModels."""

    def build(
        self,
        result: IntelligenceResult | None,
    ) -> MarketplaceMomentumDetailViewModel:
        if result is None:
            return MarketplaceMomentumDetailViewModel.unavailable()
        if type(result) is not IntelligenceResult or not isinstance(
            result.metrics,
            Mapping,
        ):
            raise TypeError(
                "result must use the standard IntelligenceResult contract."
            )
        if result.module_id != "marketplace_momentum":
            raise MarketplaceMomentumDetailConsistencyError(
                "Marketplace Momentum detail requires the "
                "marketplace_momentum result."
            )
        output = result.metrics.get("output")
        if type(output) is not MarketplaceMomentumOutput:
            raise MarketplaceMomentumDetailConsistencyError(
                "Marketplace Momentum requires typed output."
            )
        expected_status = (
            IntelligenceStatus.SKIPPED
            if output.analysis_state is MomentumAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
        if result.status is not expected_status:
            raise MarketplaceMomentumDetailConsistencyError(
                "Result status contradicts Momentum analysis state."
            )

        if output.analysis_state is MomentumAnalysisState.INSUFFICIENT_DATA:
            state = MarketplaceMomentumDetailState.INSUFFICIENT_DATA
        elif output.analysis_state is MomentumAnalysisState.PARTIAL:
            state = MarketplaceMomentumDetailState.PARTIAL
        elif output.releases:
            state = MarketplaceMomentumDetailState.AVAILABLE
        else:
            state = MarketplaceMomentumDetailState.EMPTY

        return MarketplaceMomentumDetailViewModel(
            state=state,
            summary=result.summary,
            analysis_state=output.analysis_state,
            rule_set_version=output.rule_set_version,
            activity_thresholds=ActivityIntensityThresholdsViewModel(
                low_maximum=output.activity_thresholds.low_maximum,
                moderate_maximum=output.activity_thresholds.moderate_maximum,
            ),
            momentum_summary=MarketplaceMomentumSummaryViewModel(
                release_count=output.summary.release_count,
                positive_count=output.summary.positive_count,
                mixed_count=output.summary.mixed_count,
                neutral_count=output.summary.neutral_count,
                negative_count=output.summary.negative_count,
                insufficient_count=output.summary.insufficient_count,
                complete_evidence_count=output.summary.complete_evidence_count,
                partial_evidence_count=output.summary.partial_evidence_count,
                limited_evidence_count=output.summary.limited_evidence_count,
                insufficient_evidence_count=(
                    output.summary.insufficient_evidence_count
                ),
            ),
            source_provenance=tuple(
                _source_provenance(value)
                for value in output.source_provenance
            ),
            releases=tuple(_release(value) for value in output.releases),
            output_diagnostics=tuple(
                _diagnostic(value) for value in output.diagnostics
            ),
            diagnostics=tuple(result.diagnostics),
        )


def _release(value: ReleaseMomentum) -> ReleaseMomentumViewModel:
    price = value.components.price
    supply = value.components.supply
    activity = value.components.activity
    evidence = value.components.evidence
    return ReleaseMomentumViewModel(
        release_id=value.release_id,
        assessment=value.assessment,
        price=PriceDirectionComponentViewModel(
            increase_count=price.increase_count,
            decrease_count=price.decrease_count,
            newly_observed_count=price.newly_observed_count,
            no_longer_observed_count=price.no_longer_observed_count,
            incomparable_count=price.incomparable_count,
            comparable_change_count=price.comparable_change_count,
            net_price_direction=price.net_price_direction,
            direction=price.direction,
        ),
        supply=SupplyDirectionComponentViewModel(
            increase_count=supply.increase_count,
            decrease_count=supply.decrease_count,
            newly_available_count=supply.newly_available_count,
            no_longer_available_count=supply.no_longer_available_count,
            incomparable_count=supply.incomparable_count,
            comparable_change_count=supply.comparable_change_count,
            net_supply_pressure=supply.net_supply_pressure,
            direction=supply.direction,
        ),
        activity=ActivityIntensityComponentViewModel(
            total_activity_count=activity.total_activity_count,
            intensity=activity.intensity,
            thresholds=ActivityIntensityThresholdsViewModel(
                low_maximum=activity.thresholds.low_maximum,
                moderate_maximum=activity.thresholds.moderate_maximum,
            ),
        ),
        evidence=EvidenceCoverageComponentViewModel(
            coverage=evidence.coverage,
            price_comparable=evidence.price_comparable,
            supply_comparable=evidence.supply_comparable,
            activity_available=evidence.activity_available,
            required_sources_partial=evidence.required_sources_partial,
            required_source_diagnostics=evidence.required_source_diagnostics,
        ),
        supporting_context=_supporting_context(value.supporting_context),
        contributing_source_ids=value.contributing_source_ids,
        reason_codes=value.reason_codes,
    )


def _supporting_context(
    value: FactualSupportingContext,
) -> FactualSupportingContextViewModel:
    return FactualSupportingContextViewModel(
        appearance=(
            None
            if value.appearance is None
            else _appearance_context(value.appearance)
        ),
        listing_persistence=(
            None
            if value.listing_persistence is None
            else _listing_context(value.listing_persistence)
        ),
    )


def _appearance_context(
    value: AppearancePersistenceContext,
) -> AppearancePersistenceContextViewModel:
    return AppearancePersistenceContextViewModel(
        appearance_count=value.appearance_count,
        appearance_ratio=value.appearance_ratio,
        longest_absence=value.longest_absence,
        source_module_id=value.source_module_id,
    )


def _listing_context(
    value: ListingPersistenceContext,
) -> ListingPersistenceContextViewModel:
    return ListingPersistenceContextViewModel(
        listing_count=value.listing_count,
        currently_present_count=value.currently_present_count,
        new_count=value.new_count,
        active_count=value.active_count,
        disappeared_count=value.disappeared_count,
        reappeared_count=value.reappeared_count,
        intermittent_count=value.intermittent_count,
        ended_count=value.ended_count,
    )


def _source_provenance(
    value: SourceProvenance,
) -> SourceProvenanceViewModel:
    return SourceProvenanceViewModel(
        module_id=value.module_id,
        module_version=value.module_version,
        result_status=value.result_status,
        compatible=value.compatible,
        partial=value.partial,
        history_snapshot_ids=value.history_snapshot_ids,
        source=value.source,
        source_versions=value.source_versions,
        diagnostics=value.diagnostics,
    )


def _diagnostic(
    value: MarketplaceMomentumDiagnostic,
) -> MarketplaceMomentumDiagnosticViewModel:
    return MarketplaceMomentumDiagnosticViewModel(
        code=value.code,
        message=value.message,
        source_module_id=value.source_module_id,
        release_id=value.release_id,
    )


__all__ = ["MarketplaceMomentumDetailViewModelBuilder"]
