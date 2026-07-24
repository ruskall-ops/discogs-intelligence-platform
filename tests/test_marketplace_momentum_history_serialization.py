from __future__ import annotations

import unittest
from decimal import Decimal

from dip.decision_intelligence import (
    ActivityIntensity,
    ActivityIntensityComponent,
    ActivityIntensityThresholds,
    AppearancePersistenceContext,
    EvidenceCoverage,
    EvidenceCoverageComponent,
    FactualSupportingContext,
    MarketplaceMomentumOutput,
    MarketplaceMomentumSummary,
    MomentumAnalysisState,
    MomentumAssessment,
    MomentumComponents,
    MomentumDirection,
    MomentumReasonCode,
    PriceDirectionComponent,
    ReleaseMomentum,
    SourceProvenance,
    SupplyDirectionComponent,
)
from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    dumps_intelligence_value,
    loads_intelligence_value,
)


class MarketplaceMomentumHistorySerializationTestCase(unittest.TestCase):
    def test_typed_output_round_trips_through_existing_history_wire_format(
        self,
    ) -> None:
        thresholds = ActivityIntensityThresholds()
        provenance = (
            source("price_changes", ("previous", "latest"), "discogs"),
            source("supply_changes", ("previous", "latest"), "discogs"),
            source("marketplace_activity", ("previous", "latest"), None),
        )
        release = ReleaseMomentum(
            release_id=7,
            assessment=MomentumAssessment.POSITIVE,
            components=MomentumComponents(
                price=PriceDirectionComponent(
                    increase_count=2,
                    decrease_count=0,
                    newly_observed_count=1,
                    no_longer_observed_count=0,
                    incomparable_count=0,
                    comparable_change_count=2,
                    net_price_direction=2,
                    direction=MomentumDirection.POSITIVE,
                ),
                supply=SupplyDirectionComponent(
                    increase_count=0,
                    decrease_count=1,
                    newly_available_count=0,
                    no_longer_available_count=0,
                    incomparable_count=0,
                    comparable_change_count=1,
                    net_supply_pressure=1,
                    direction=MomentumDirection.POSITIVE,
                ),
                activity=ActivityIntensityComponent(
                    total_activity_count=5,
                    intensity=ActivityIntensity.MODERATE,
                    thresholds=thresholds,
                ),
                evidence=EvidenceCoverageComponent(
                    coverage=EvidenceCoverage.COMPLETE,
                    price_comparable=True,
                    supply_comparable=True,
                    activity_available=True,
                    required_sources_partial=False,
                    required_source_diagnostics=False,
                ),
            ),
            supporting_context=FactualSupportingContext(
                appearance=AppearancePersistenceContext(
                    appearance_count=2,
                    appearance_ratio=Decimal("0.5"),
                    longest_absence=1,
                    source_module_id="marketplace_activity",
                )
            ),
            contributing_source_ids=(
                "price_changes",
                "supply_changes",
                "marketplace_activity",
            ),
            reason_codes=(MomentumReasonCode.ALIGNED_POSITIVE,),
        )
        output = MarketplaceMomentumOutput(
            analysis_state=MomentumAnalysisState.COMPLETE,
            rule_set_version="1.0",
            activity_thresholds=thresholds,
            source_provenance=provenance,
            releases=(release,),
            summary=MarketplaceMomentumSummary(
                release_count=1,
                positive_count=1,
                complete_evidence_count=1,
            ),
        )
        result = IntelligenceResult(
            module_id="marketplace_momentum",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Assessed observed Marketplace momentum for 1 release.",
            metrics={"output": output},
        )
        record = IntelligenceHistoryRecord(
            record_id=None,
            run_id=1,
            module_id=result.module_id,
            module_version=result.module_version,
            status=result.status,
            summary=result.summary,
            metrics=result.metrics,
        )

        restored = loads_intelligence_value(dumps_intelligence_value(record))

        self.assertEqual(restored, record)
        restored_output = restored.metrics["output"]
        self.assertIs(type(restored_output), MarketplaceMomentumOutput)
        self.assertIs(
            restored_output.releases[0].assessment,
            MomentumAssessment.POSITIVE,
        )
        self.assertEqual(
            restored_output.releases[0]
            .supporting_context.appearance.appearance_ratio,
            Decimal("0.5"),
        )
        self.assertEqual(restored_output.rule_set_version, "1.0")
        self.assertEqual(restored_output.activity_thresholds, thresholds)


def source(
    module_id: str,
    history_snapshot_ids: tuple[str, ...],
    marketplace_source: str | None,
) -> SourceProvenance:
    return SourceProvenance(
        module_id=module_id,
        module_version="1.0",
        result_status=IntelligenceStatus.COMPLETED,
        compatible=True,
        partial=False,
        history_snapshot_ids=history_snapshot_ids,
        source=marketplace_source,
        source_versions=(None,) * len(history_snapshot_ids),
    )


if __name__ == "__main__":
    unittest.main()
