from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from dip.app import (
    MarketplaceMomentumExecutionConsistencyError,
    MarketplaceMomentumExecutionService,
)
from dip.app.marketplace_momentum import build_marketplace_momentum_input
from dip.decision_intelligence import (
    ActivityIntensity,
    EvidenceCoverage,
    MarketplaceMomentumDiagnosticCode,
    MarketplaceMomentumInput,
    MarketplaceMomentumModule,
    MarketplaceMomentumOutput,
    MomentumAnalysisState,
    MomentumAssessment,
    MomentumDirection,
)
from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceExecution,
    IntelligenceResult,
    IntelligenceStatus,
)
from dip.marketplace_intelligence import (
    ListingLifecycleModule,
    MarketplaceActivityModule,
    MarketplaceActivityOutput,
    MarketplaceActivityState,
    MarketplaceActivitySummary,
    MarketplaceDataStatus,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    PriceChangesModule,
    RareAppearancesModule,
    SupplyChangesModule,
)


START = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


def snapshot(
    snapshot_id: str,
    offset: int,
    *,
    price: str,
    supply: int,
    source_version: str = "v1",
) -> MarketplaceSnapshot:
    captured_at = START + timedelta(days=offset)
    return MarketplaceSnapshot(
        snapshot_id,
        captured_at,
        "discogs",
        MarketplaceDataStatus.COMPLETE,
        (
            MarketplaceReleaseObservation(
                1,
                captured_at,
                MarketplaceDataStatus.COMPLETE,
                lowest_price=MarketplaceMoney(Decimal(price), "GBP"),
                num_for_sale=supply,
            ),
        ),
        source_version=source_version,
    )


def source_bundle(
    *,
    previous_price: str = "10",
    latest_price: str = "12",
    previous_supply: int = 5,
    latest_supply: int = 3,
):
    history = (
        snapshot(
            "snapshot-previous",
            0,
            price=previous_price,
            supply=previous_supply,
        ),
        snapshot(
            "snapshot-latest",
            1,
            price=latest_price,
            supply=latest_supply,
        ),
    )
    comparison = IntelligenceContext(
        marketplace_comparison=MarketplaceSnapshotComparisonInput(*history)
    )
    price = PriceChangesModule().analyse(comparison)
    supply = SupplyChangesModule().analyse(comparison)
    rare = RareAppearancesModule().analyse(
        IntelligenceContext(marketplace_history=history)
    )
    activity = MarketplaceActivityModule().analyse(
        IntelligenceContext(
            marketplace_activity_sources=(price, supply, rare)
        )
    )
    lifecycle = ListingLifecycleModule().analyse(
        IntelligenceContext(marketplace_history=history)
    )
    return history, price, supply, activity, rare, lifecycle


def diagnostic_codes(
    supplied: MarketplaceMomentumInput,
) -> tuple[MarketplaceMomentumDiagnosticCode, ...]:
    return tuple(value.code for value in supplied.diagnostics)


class Provider:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0

    def execute(self):
        self.calls += 1
        return self.result


class RecordingEngine:
    def __init__(self, response: object | None = None) -> None:
        self.calls: list[IntelligenceContext] = []
        self.response = response
        self.actual = IntelligenceEngine((MarketplaceMomentumModule(),))

    def execute(self, context: IntelligenceContext):
        self.calls.append(context)
        if self.response is not None:
            return self.response
        return self.actual.execute(context)


class MarketplaceMomentumInputPreparationTestCase(unittest.TestCase):
    def test_normalises_typed_sources_and_preserves_provenance(self) -> None:
        _, price, supply, activity, rare, lifecycle = source_bundle()

        supplied = build_marketplace_momentum_input(
            (lifecycle, activity, price, rare, supply)
        )

        self.assertTrue(supplied.required_sources_compatible)
        self.assertEqual(
            tuple(value.module_id for value in supplied.source_provenance),
            (
                "price_changes",
                "supply_changes",
                "marketplace_activity",
                "rare_appearances",
                "listing_lifecycle",
            ),
        )
        self.assertEqual(
            supplied.source_provenance[0].history_snapshot_ids,
            ("snapshot-previous", "snapshot-latest"),
        )
        self.assertEqual(
            supplied.source_provenance[0].source_versions,
            ("v1", "v1"),
        )
        self.assertEqual(len(supplied.price_facts), 1)
        self.assertEqual(len(supplied.supply_facts), 1)
        self.assertEqual(supplied.activity_facts[0].total_activity_count, 4)
        self.assertEqual(supplied.appearance_facts[0].appearance_count, 2)
        self.assertEqual(supplied.lifecycle_facts, ())

        result = MarketplaceMomentumModule().analyse(
            IntelligenceContext(marketplace_momentum_input=supplied)
        )
        output = result.metrics["output"]
        self.assertIs(type(output), MarketplaceMomentumOutput)
        self.assertIs(output.releases[0].assessment, MomentumAssessment.POSITIVE)
        self.assertIs(
            output.releases[0].components.price.direction,
            MomentumDirection.POSITIVE,
        )
        self.assertIs(
            output.releases[0].components.supply.direction,
            MomentumDirection.POSITIVE,
        )

    def test_missing_duplicate_malformed_and_unsupported_required_sources_are_diagnostic(
        self,
    ) -> None:
        _, price, supply, activity, _, _ = source_bundle()
        cases = (
            (
                "missing",
                (price, activity),
                MarketplaceMomentumDiagnosticCode.MISSING_REQUIRED_SOURCE,
            ),
            (
                "duplicate",
                (price, price, supply, activity),
                MarketplaceMomentumDiagnosticCode.DUPLICATE_SOURCE_RESULT,
            ),
            (
                "malformed output",
                (replace(price, metrics={}), supply, activity),
                MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
            ),
            (
                "unsupported version",
                (price, replace(supply, module_version="2.0"), activity),
                MarketplaceMomentumDiagnosticCode.UNSUPPORTED_SOURCE_VERSION,
            ),
            (
                "source not completed",
                (
                    price,
                    supply,
                    replace(activity, status=IntelligenceStatus.SKIPPED),
                ),
                MarketplaceMomentumDiagnosticCode.SOURCE_NOT_COMPLETED,
            ),
            (
                "non-result",
                (price, supply, object()),
                MarketplaceMomentumDiagnosticCode.MALFORMED_TYPED_OUTPUT,
            ),
        )

        for label, sources, expected_code in cases:
            with self.subTest(label=label):
                supplied = build_marketplace_momentum_input(sources)
                self.assertFalse(supplied.required_sources_compatible)
                self.assertEqual(supplied.price_facts, ())
                self.assertEqual(supplied.supply_facts, ())
                self.assertEqual(supplied.activity_facts, ())
                self.assertIn(expected_code, diagnostic_codes(supplied))
                result = MarketplaceMomentumModule().analyse(
                    IntelligenceContext(marketplace_momentum_input=supplied)
                )
                self.assertIs(result.status, IntelligenceStatus.SKIPPED)

    def test_incompatible_histories_and_conflicting_provenance_are_rejected(
        self,
    ) -> None:
        _, price, supply, activity, _, _ = source_bundle()
        other_history = (
            snapshot("other-previous", 5, price="10", supply=8),
            snapshot("other-latest", 6, price="10", supply=4),
        )
        other_supply = SupplyChangesModule().analyse(
            IntelligenceContext(
                marketplace_comparison=MarketplaceSnapshotComparisonInput(
                    *other_history
                )
            )
        )

        incompatible = build_marketplace_momentum_input(
            (price, other_supply, activity)
        )
        self.assertFalse(incompatible.required_sources_compatible)
        self.assertIn(
            MarketplaceMomentumDiagnosticCode.INCOMPATIBLE_HISTORY,
            diagnostic_codes(incompatible),
        )
        self.assertTrue(
            all(not value.compatible for value in incompatible.source_provenance)
        )

        supply_output = supply.metrics["output"]
        changed_reference = replace(
            supply_output.previous_snapshot,
            source_version="different",
        )
        conflicting_supply = replace(
            supply,
            metrics={
                "output": replace(
                    supply_output,
                    previous_snapshot=changed_reference,
                )
            },
        )
        conflicting = build_marketplace_momentum_input(
            (price, conflicting_supply, activity)
        )
        self.assertFalse(conflicting.required_sources_compatible)
        self.assertIn(
            MarketplaceMomentumDiagnosticCode.CONFLICTING_PROVENANCE,
            diagnostic_codes(conflicting),
        )

    def test_required_source_diagnostics_are_preserved_and_reduce_coverage(
        self,
    ) -> None:
        _, price, supply, activity, _, _ = source_bundle()
        price = replace(
            price,
            diagnostics=("Price source supplied partial factual evidence.",),
        )

        supplied = build_marketplace_momentum_input((price, supply, activity))
        result = MarketplaceMomentumModule().analyse(
            IntelligenceContext(marketplace_momentum_input=supplied)
        )
        output = result.metrics["output"]

        price_provenance = supplied.source_provenance[0]
        self.assertEqual(
            price_provenance.diagnostics,
            ("Price source supplied partial factual evidence.",),
        )
        self.assertIn(
            MarketplaceMomentumDiagnosticCode.PARTIAL_SOURCE_DIAGNOSTICS,
            diagnostic_codes(supplied),
        )
        self.assertIs(
            output.releases[0].components.evidence.coverage,
            EvidenceCoverage.PARTIAL,
        )
        self.assertIn(
            "price_changes: Price source supplied partial factual evidence.",
            result.diagnostics,
        )

    def test_incompatible_optional_history_is_excluded_without_reclassification(
        self,
    ) -> None:
        _, price, supply, activity, _, _ = source_bundle()
        other_history = (
            snapshot("other-previous", 5, price="10", supply=5),
            snapshot("other-latest", 6, price="12", supply=3),
        )
        other_rare = RareAppearancesModule().analyse(
            IntelligenceContext(marketplace_history=other_history)
        )

        supplied = build_marketplace_momentum_input(
            (price, supply, activity, other_rare)
        )
        result = MarketplaceMomentumModule().analyse(
            IntelligenceContext(marketplace_momentum_input=supplied)
        )
        output = result.metrics["output"]

        self.assertTrue(supplied.required_sources_compatible)
        self.assertFalse(supplied.source_provenance[3].compatible)
        self.assertEqual(supplied.appearance_facts, ())
        self.assertIn(
            MarketplaceMomentumDiagnosticCode.CONFLICTING_PROVENANCE,
            diagnostic_codes(supplied),
        )
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(
            output.releases[0].assessment,
            MomentumAssessment.POSITIVE,
        )
        self.assertIs(
            output.analysis_state,
            MomentumAnalysisState.PARTIAL,
        )

    def test_unchanged_supply_is_not_fabricated_as_neutral_release_evidence(
        self,
    ) -> None:
        _, price, supply, activity, _, _ = source_bundle(
            previous_supply=5,
            latest_supply=5,
        )

        supplied = build_marketplace_momentum_input((price, supply, activity))
        result = MarketplaceMomentumModule().analyse(
            IntelligenceContext(marketplace_momentum_input=supplied)
        )
        output = result.metrics["output"]
        release = output.releases[0]

        self.assertEqual(supplied.supply_facts, ())
        self.assertIs(
            release.components.supply.direction,
            MomentumDirection.INSUFFICIENT,
        )
        self.assertEqual(release.components.supply.comparable_change_count, 0)
        self.assertIs(release.assessment, MomentumAssessment.MIXED)
        self.assertIs(
            release.components.evidence.coverage,
            EvidenceCoverage.LIMITED,
        )
        self.assertTrue(
            any(
                value.code
                is MarketplaceMomentumDiagnosticCode.SPARSE_RELEASE_SOURCE
                and value.source_module_id == "supply_changes"
                for value in output.diagnostics
            )
        )

    def test_missing_activity_profile_is_insufficient_not_zero_activity(self) -> None:
        _, price, supply, activity, _, _ = source_bundle()
        activity_output = activity.metrics["output"]
        self.assertIs(type(activity_output), MarketplaceActivityOutput)
        sparse_activity = replace(
            activity,
            metrics={
                "output": replace(
                    activity_output,
                    state=MarketplaceActivityState.COMPLETE,
                    activities=(),
                    summary=MarketplaceActivitySummary(),
                    diagnostics=(),
                )
            },
        )

        supplied = build_marketplace_momentum_input(
            (price, supply, sparse_activity)
        )
        result = MarketplaceMomentumModule().analyse(
            IntelligenceContext(marketplace_momentum_input=supplied)
        )
        output = result.metrics["output"]
        release = output.releases[0]

        self.assertEqual(supplied.activity_facts, ())
        self.assertIsNone(release.components.activity.total_activity_count)
        self.assertIs(
            release.components.activity.intensity,
            ActivityIntensity.INSUFFICIENT,
        )
        self.assertIs(
            release.components.evidence.coverage,
            EvidenceCoverage.LIMITED,
        )
        self.assertTrue(
            any(
                value.code
                is MarketplaceMomentumDiagnosticCode.SPARSE_RELEASE_SOURCE
                and value.source_module_id == "marketplace_activity"
                for value in output.diagnostics
            )
        )


class MarketplaceMomentumExecutionServiceTestCase(unittest.TestCase):
    def test_executes_each_source_and_the_decision_module_exactly_once(self) -> None:
        _, price, supply, activity, rare, lifecycle = source_bundle()
        providers = tuple(
            Provider(value)
            for value in (price, supply, activity, rare, lifecycle)
        )
        engine = RecordingEngine()
        service = MarketplaceMomentumExecutionService(
            providers[0],
            providers[1],
            providers[2],
            engine,
            rare_appearances=providers[3],
            listing_lifecycle=providers[4],
        )

        result = service.execute()

        self.assertEqual(tuple(value.calls for value in providers), (1, 1, 1, 1, 1))
        self.assertEqual(len(engine.calls), 1)
        self.assertIs(
            type(engine.calls[0].marketplace_momentum_input),
            MarketplaceMomentumInput,
        )
        self.assertEqual(result.module_id, "marketplace_momentum")
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)

    def test_engine_must_return_exactly_one_standard_momentum_result(self) -> None:
        _, price, supply, activity, _, _ = source_bundle()
        valid = IntelligenceEngine((MarketplaceMomentumModule(),)).execute(
            IntelligenceContext(
                marketplace_momentum_input=build_marketplace_momentum_input(
                    (price, supply, activity)
                )
            )
        ).results[0]
        responses = (
            ("execution", object(), "IntelligenceExecution"),
            ("empty", IntelligenceExecution(()), "exactly one"),
            (
                "multiple",
                IntelligenceExecution((valid, valid)),
                "exactly one",
            ),
            (
                "wrong module",
                IntelligenceExecution((replace(valid, module_id="other"),)),
                "unexpected",
            ),
            (
                "non-standard",
                IntelligenceExecution((object(),)),  # type: ignore[arg-type]
                "non-standard",
            ),
        )

        for label, response, message in responses:
            with self.subTest(label=label):
                service = MarketplaceMomentumExecutionService(
                    Provider(price),
                    Provider(supply),
                    Provider(activity),
                    RecordingEngine(response),
                )
                with self.assertRaisesRegex(
                    MarketplaceMomentumExecutionConsistencyError,
                    message,
                ):
                    service.execute()


if __name__ == "__main__":
    unittest.main()
