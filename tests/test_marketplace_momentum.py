from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
import unittest

from dip.decision_intelligence import (
    ActivityIntensity,
    ActivityIntensityThresholds,
    EvidenceCoverage,
    MarketplaceMomentumActivityFact,
    MarketplaceMomentumAppearanceFact,
    MarketplaceMomentumDiagnosticCode,
    MarketplaceMomentumDomainError,
    MarketplaceMomentumInput,
    MarketplaceMomentumModule,
    MarketplaceMomentumOutput,
    MarketplaceMomentumPriceFact,
    MarketplaceMomentumPriceFactKind,
    MarketplaceMomentumSupplyFact,
    MarketplaceMomentumSupplyFactKind,
    MomentumAnalysisState,
    MomentumAssessment,
    MomentumDirection,
    MomentumReasonCode,
    SourceProvenance,
)
from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceStatus,
    build_v02_intelligence_registry,
)


SNAPSHOT_IDS = ("snapshot-previous", "snapshot-latest")


def provenance(
    *,
    partial_source: str | None = None,
    diagnostic_source: str | None = None,
) -> tuple[SourceProvenance, ...]:
    values = []
    for module_id in (
        "price_changes",
        "supply_changes",
        "marketplace_activity",
    ):
        values.append(
            SourceProvenance(
                module_id=module_id,
                module_version="1.0",
                result_status=IntelligenceStatus.COMPLETED,
                compatible=True,
                partial=module_id == partial_source,
                history_snapshot_ids=SNAPSHOT_IDS,
                source="discogs"
                if module_id in {"price_changes", "supply_changes"}
                else None,
                source_versions=("v1", "v1")
                if module_id in {"price_changes", "supply_changes"}
                else (None, None),
                diagnostics=("Source supplied a factual diagnostic.",)
                if module_id == diagnostic_source
                else (),
            )
        )
    return tuple(values)


def price_fact(
    release_id: int,
    suffix: str,
    kind: MarketplaceMomentumPriceFactKind,
) -> MarketplaceMomentumPriceFact:
    return MarketplaceMomentumPriceFact(
        release_id,
        f"release:{release_id}:{suffix}",
        kind,
    )


def supply_fact(
    release_id: int,
    kind: MarketplaceMomentumSupplyFactKind,
) -> MarketplaceMomentumSupplyFact:
    return MarketplaceMomentumSupplyFact(release_id, kind)


def activity_fact(
    release_id: int,
    total: int = 3,
) -> MarketplaceMomentumActivityFact:
    return MarketplaceMomentumActivityFact(
        release_id=release_id,
        total_activity_count=total,
        historical_price_change_count=0,
        historical_supply_change_count=0,
        appearance_count=total,
        appearance_ratio=Decimal(0) if total == 0 else Decimal(1),
        longest_absence=0,
    )


def momentum_input(
    *,
    price_facts: tuple[MarketplaceMomentumPriceFact, ...] = (),
    supply_facts: tuple[MarketplaceMomentumSupplyFact, ...] = (),
    activity_facts: tuple[MarketplaceMomentumActivityFact, ...] = (),
    source_provenance: tuple[SourceProvenance, ...] | None = None,
) -> MarketplaceMomentumInput:
    return MarketplaceMomentumInput(
        source_provenance=provenance()
        if source_provenance is None
        else source_provenance,
        price_facts=price_facts,
        supply_facts=supply_facts,
        activity_facts=activity_facts,
    )


def analyse(
    supplied: MarketplaceMomentumInput,
    *,
    thresholds: ActivityIntensityThresholds | None = None,
):
    result = MarketplaceMomentumModule(thresholds).analyse(
        IntelligenceContext(marketplace_momentum_input=supplied)
    )
    output = result.metrics["output"]
    assert type(output) is MarketplaceMomentumOutput
    return result, output


class MarketplaceMomentumRulesTestCase(unittest.TestCase):
    def test_direction_and_assessment_rules_are_explicit(self) -> None:
        cases = (
            (
                "positive",
                (
                    price_fact(1, "price", MarketplaceMomentumPriceFactKind.INCREASED),
                ),
                (
                    supply_fact(
                        1,
                        MarketplaceMomentumSupplyFactKind.DECREASED,
                    ),
                ),
                MomentumDirection.POSITIVE,
                MomentumDirection.POSITIVE,
                MomentumAssessment.POSITIVE,
                EvidenceCoverage.COMPLETE,
                MomentumReasonCode.ALIGNED_POSITIVE,
            ),
            (
                "negative",
                (
                    price_fact(1, "price", MarketplaceMomentumPriceFactKind.DECREASED),
                ),
                (
                    supply_fact(
                        1,
                        MarketplaceMomentumSupplyFactKind.INCREASED,
                    ),
                ),
                MomentumDirection.NEGATIVE,
                MomentumDirection.NEGATIVE,
                MomentumAssessment.NEGATIVE,
                EvidenceCoverage.COMPLETE,
                MomentumReasonCode.ALIGNED_NEGATIVE,
            ),
            (
                "conflicting",
                (
                    price_fact(1, "price", MarketplaceMomentumPriceFactKind.INCREASED),
                ),
                (
                    supply_fact(
                        1,
                        MarketplaceMomentumSupplyFactKind.INCREASED,
                    ),
                ),
                MomentumDirection.POSITIVE,
                MomentumDirection.NEGATIVE,
                MomentumAssessment.MIXED,
                EvidenceCoverage.COMPLETE,
                MomentumReasonCode.CONFLICTING_DIRECTIONS,
            ),
            (
                "price only",
                (
                    price_fact(1, "price", MarketplaceMomentumPriceFactKind.INCREASED),
                ),
                (),
                MomentumDirection.POSITIVE,
                MomentumDirection.INSUFFICIENT,
                MomentumAssessment.MIXED,
                EvidenceCoverage.LIMITED,
                MomentumReasonCode.DIRECTION_WITH_MISSING_COUNTERPART,
            ),
            (
                "supply only",
                (),
                (
                    supply_fact(
                        1,
                        MarketplaceMomentumSupplyFactKind.DECREASED,
                    ),
                ),
                MomentumDirection.INSUFFICIENT,
                MomentumDirection.POSITIVE,
                MomentumAssessment.MIXED,
                EvidenceCoverage.LIMITED,
                MomentumReasonCode.DIRECTION_WITH_MISSING_COUNTERPART,
            ),
            (
                "balanced comparable price",
                (
                    price_fact(1, "a", MarketplaceMomentumPriceFactKind.INCREASED),
                    price_fact(1, "b", MarketplaceMomentumPriceFactKind.DECREASED),
                ),
                (),
                MomentumDirection.NEUTRAL,
                MomentumDirection.INSUFFICIENT,
                MomentumAssessment.NEUTRAL,
                EvidenceCoverage.LIMITED,
                MomentumReasonCode.BALANCED_COMPARABLE_EVIDENCE,
            ),
            (
                "no comparable direction",
                (
                    price_fact(
                        1,
                        "new",
                        MarketplaceMomentumPriceFactKind.NEWLY_OBSERVED,
                    ),
                ),
                (
                    supply_fact(
                        1,
                        MarketplaceMomentumSupplyFactKind.INCOMPARABLE,
                    ),
                ),
                MomentumDirection.INSUFFICIENT,
                MomentumDirection.INSUFFICIENT,
                MomentumAssessment.INSUFFICIENT,
                EvidenceCoverage.INSUFFICIENT,
                MomentumReasonCode.NO_COMPARABLE_DIRECTION,
            ),
        )

        for (
            label,
            price_facts,
            supply_facts,
            price_direction,
            supply_direction,
            assessment,
            coverage,
            reason,
        ) in cases:
            with self.subTest(label=label):
                result, output = analyse(
                    momentum_input(
                        price_facts=price_facts,
                        supply_facts=supply_facts,
                        activity_facts=(activity_fact(1),),
                    )
                )
                release = output.releases[0]

                self.assertIs(result.status, IntelligenceStatus.COMPLETED)
                self.assertIs(release.components.price.direction, price_direction)
                self.assertIs(release.components.supply.direction, supply_direction)
                self.assertIs(release.assessment, assessment)
                self.assertIs(release.components.evidence.coverage, coverage)
                self.assertIs(release.reason_codes[0], reason)

    def test_non_directional_facts_are_visible_but_excluded_from_net(self) -> None:
        price_facts = (
            price_fact(1, "a", MarketplaceMomentumPriceFactKind.INCREASED),
            price_fact(1, "b", MarketplaceMomentumPriceFactKind.DECREASED),
            price_fact(1, "c", MarketplaceMomentumPriceFactKind.NEWLY_OBSERVED),
            price_fact(
                1,
                "d",
                MarketplaceMomentumPriceFactKind.NO_LONGER_OBSERVED,
            ),
            price_fact(1, "e", MarketplaceMomentumPriceFactKind.INCOMPARABLE),
        )
        _, output = analyse(
            momentum_input(
                price_facts=price_facts,
                supply_facts=(
                    supply_fact(
                        1,
                        MarketplaceMomentumSupplyFactKind.NEWLY_AVAILABLE,
                    ),
                ),
                activity_facts=(activity_fact(1),),
            )
        )

        release = output.releases[0]
        price = release.components.price
        supply = release.components.supply
        self.assertEqual(
            (
                price.increase_count,
                price.decrease_count,
                price.newly_observed_count,
                price.no_longer_observed_count,
                price.incomparable_count,
                price.comparable_change_count,
                price.net_price_direction,
            ),
            (1, 1, 1, 1, 1, 2, 0),
        )
        self.assertIs(price.direction, MomentumDirection.NEUTRAL)
        self.assertEqual(supply.newly_available_count, 1)
        self.assertEqual(supply.comparable_change_count, 0)
        self.assertEqual(supply.net_supply_pressure, 0)
        self.assertIs(supply.direction, MomentumDirection.INSUFFICIENT)

    def test_required_partial_state_and_diagnostics_downgrade_coverage(self) -> None:
        supplied = momentum_input(
            source_provenance=provenance(
                partial_source="supply_changes",
                diagnostic_source="price_changes",
            ),
            price_facts=(
                price_fact(1, "price", MarketplaceMomentumPriceFactKind.INCREASED),
            ),
            supply_facts=(
                supply_fact(1, MarketplaceMomentumSupplyFactKind.DECREASED),
            ),
            activity_facts=(activity_fact(1),),
        )

        _, output = analyse(supplied)
        evidence = output.releases[0].components.evidence

        self.assertIs(evidence.coverage, EvidenceCoverage.PARTIAL)
        self.assertTrue(evidence.required_sources_partial)
        self.assertTrue(evidence.required_source_diagnostics)
        self.assertIn(
            MomentumReasonCode.PARTIAL_REQUIRED_SOURCE,
            output.releases[0].reason_codes,
        )
        self.assertIn(
            MomentumReasonCode.REQUIRED_SOURCE_DIAGNOSTICS,
            output.releases[0].reason_codes,
        )
        self.assertIs(output.analysis_state, MomentumAnalysisState.PARTIAL)

    def test_activity_thresholds_and_order_are_explicit_and_preserved(self) -> None:
        thresholds = ActivityIntensityThresholds(1, 3)
        price_facts = tuple(
            price_fact(
                release_id,
                "price",
                MarketplaceMomentumPriceFactKind.INCREASED,
            )
            for release_id in range(1, 6)
        )
        supply_facts = tuple(
            supply_fact(
                release_id,
                MarketplaceMomentumSupplyFactKind.DECREASED,
            )
            for release_id in range(1, 6)
        )
        activity_facts = tuple(
            activity_fact(release_id, release_id - 1)
            for release_id in range(1, 6)
        )

        _, output = analyse(
            momentum_input(
                price_facts=price_facts,
                supply_facts=supply_facts,
                activity_facts=activity_facts,
            ),
            thresholds=thresholds,
        )

        self.assertEqual(output.activity_thresholds, thresholds)
        self.assertEqual(
            tuple(value.release_id for value in output.releases),
            (5, 4, 3, 2, 1),
        )
        self.assertEqual(
            tuple(value.components.activity.intensity for value in output.releases),
            (
                ActivityIntensity.HIGH,
                ActivityIntensity.MODERATE,
                ActivityIntensity.MODERATE,
                ActivityIntensity.LOW,
                ActivityIntensity.NONE,
            ),
        )
        self.assertTrue(
            all(
                value.components.activity.thresholds == thresholds
                for value in output.releases
            )
        )

    def test_canonical_order_uses_assessment_then_coverage_then_activity(self) -> None:
        supplied = momentum_input(
            price_facts=(
                price_fact(1, "a", MarketplaceMomentumPriceFactKind.INCREASED),
                price_fact(2, "a", MarketplaceMomentumPriceFactKind.INCREASED),
                price_fact(3, "a", MarketplaceMomentumPriceFactKind.INCREASED),
                price_fact(3, "b", MarketplaceMomentumPriceFactKind.DECREASED),
                price_fact(4, "a", MarketplaceMomentumPriceFactKind.DECREASED),
                price_fact(5, "a", MarketplaceMomentumPriceFactKind.NEWLY_OBSERVED),
                price_fact(6, "a", MarketplaceMomentumPriceFactKind.INCREASED),
            ),
            supply_facts=(
                supply_fact(1, MarketplaceMomentumSupplyFactKind.DECREASED),
                supply_fact(2, MarketplaceMomentumSupplyFactKind.INCREASED),
                supply_fact(4, MarketplaceMomentumSupplyFactKind.INCREASED),
                supply_fact(5, MarketplaceMomentumSupplyFactKind.INCOMPARABLE),
            ),
            activity_facts=tuple(activity_fact(value) for value in range(1, 7)),
        )

        _, output = analyse(supplied)

        self.assertEqual(
            tuple(value.release_id for value in output.releases),
            (1, 2, 6, 3, 4, 5),
        )
        self.assertEqual(
            tuple(value.assessment for value in output.releases),
            (
                MomentumAssessment.POSITIVE,
                MomentumAssessment.MIXED,
                MomentumAssessment.MIXED,
                MomentumAssessment.NEUTRAL,
                MomentumAssessment.NEGATIVE,
                MomentumAssessment.INSUFFICIENT,
            ),
        )
        self.assertIs(
            output.releases[1].components.evidence.coverage,
            EvidenceCoverage.COMPLETE,
        )
        self.assertIs(
            output.releases[2].components.evidence.coverage,
            EvidenceCoverage.LIMITED,
        )

    def test_optional_context_does_not_add_or_reclassify_releases(self) -> None:
        rare_provenance = SourceProvenance(
            module_id="rare_appearances",
            module_version="1.0",
            result_status=IntelligenceStatus.COMPLETED,
            compatible=True,
            partial=False,
            history_snapshot_ids=SNAPSHOT_IDS,
            source_versions=(None, None),
        )
        supplied = MarketplaceMomentumInput(
            source_provenance=(*provenance(), rare_provenance),
            price_facts=(
                price_fact(
                    1,
                    "price",
                    MarketplaceMomentumPriceFactKind.INCREASED,
                ),
            ),
            supply_facts=(
                supply_fact(
                    1,
                    MarketplaceMomentumSupplyFactKind.DECREASED,
                ),
            ),
            activity_facts=(activity_fact(1),),
            appearance_facts=(
                MarketplaceMomentumAppearanceFact(
                    2,
                    1,
                    Decimal("0.5"),
                    0,
                ),
            ),
        )

        _, output = analyse(supplied)

        self.assertEqual(
            tuple(value.release_id for value in output.releases),
            (1,),
        )
        self.assertIs(
            output.releases[0].assessment,
            MomentumAssessment.POSITIVE,
        )


class MarketplaceMomentumValidationTestCase(unittest.TestCase):
    def test_thresholds_reject_booleans_non_positive_and_overlapping_bands(self) -> None:
        for values in ((True, 5), (0, 5), (2, 2), (5, 2)):
            with self.subTest(values=values):
                with self.assertRaises((TypeError, MarketplaceMomentumDomainError)):
                    ActivityIntensityThresholds(*values)
        with self.assertRaises(TypeError):
            MarketplaceMomentumModule("invalid")  # type: ignore[arg-type]

    def test_models_are_frozen_defensively_tuplified_and_consistent(self) -> None:
        supplied = MarketplaceMomentumInput(
            source_provenance=list(provenance()),  # type: ignore[arg-type]
            price_facts=[
                price_fact(1, "price", MarketplaceMomentumPriceFactKind.INCREASED)
            ],  # type: ignore[arg-type]
            supply_facts=[
                supply_fact(1, MarketplaceMomentumSupplyFactKind.DECREASED)
            ],  # type: ignore[arg-type]
            activity_facts=[activity_fact(1)],  # type: ignore[arg-type]
        )
        _, output = analyse(supplied)
        release = output.releases[0]

        self.assertIsInstance(supplied.source_provenance, tuple)
        self.assertIsInstance(supplied.price_facts, tuple)
        self.assertIsInstance(output.releases, tuple)
        with self.assertRaises(FrozenInstanceError):
            output.releases = ()  # type: ignore[misc]
        with self.assertRaisesRegex(
            MarketplaceMomentumDomainError,
            "net_price_direction",
        ):
            replace(
                release.components.price,
                net_price_direction=99,
            )
        with self.assertRaisesRegex(
            MarketplaceMomentumDomainError,
            "assessment contradicts",
        ):
            replace(release, assessment=MomentumAssessment.NEGATIVE)
        with self.assertRaisesRegex(
            MarketplaceMomentumDomainError,
            "reason codes",
        ):
            replace(release, reason_codes=(MomentumReasonCode.ALIGNED_NEGATIVE,))
        with self.assertRaisesRegex(
            MarketplaceMomentumDomainError,
            "identities must be unique",
        ):
            replace(output, releases=(release, release))
        with self.assertRaisesRegex(
            MarketplaceMomentumDomainError,
            "unique release IDs",
        ):
            replace(
                supplied,
                supply_facts=(supplied.supply_facts[0], supplied.supply_facts[0]),
            )

    def test_output_rejects_reordering_and_inconsistent_summary(self) -> None:
        supplied = momentum_input(
            price_facts=(
                price_fact(1, "a", MarketplaceMomentumPriceFactKind.INCREASED),
                price_fact(2, "a", MarketplaceMomentumPriceFactKind.DECREASED),
            ),
            supply_facts=(
                supply_fact(1, MarketplaceMomentumSupplyFactKind.DECREASED),
                supply_fact(2, MarketplaceMomentumSupplyFactKind.INCREASED),
            ),
            activity_facts=(activity_fact(1), activity_fact(2)),
        )
        _, output = analyse(supplied)

        with self.assertRaisesRegex(
            MarketplaceMomentumDomainError,
            "canonical assessment order",
        ):
            replace(output, releases=tuple(reversed(output.releases)))
        with self.assertRaisesRegex(
            MarketplaceMomentumDomainError,
            "summary counts",
        ):
            replace(output.summary, release_count=3)

    def test_missing_input_is_typed_insufficient_result(self) -> None:
        result = MarketplaceMomentumModule().analyse(IntelligenceContext())
        output = result.metrics["output"]

        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(type(output), MarketplaceMomentumOutput)
        self.assertIs(output.analysis_state, MomentumAnalysisState.INSUFFICIENT_DATA)
        self.assertEqual(output.releases, ())
        self.assertEqual(output.rule_set_version, "1.0")
        self.assertIs(
            output.diagnostics[0].code,
            MarketplaceMomentumDiagnosticCode.MISSING_REQUIRED_SOURCE,
        )

    def test_module_version_rule_version_and_registry_boundary_are_stable(self) -> None:
        result, output = analyse(
            momentum_input(
                price_facts=(
                    price_fact(
                        1,
                        "price",
                        MarketplaceMomentumPriceFactKind.INCREASED,
                    ),
                ),
                supply_facts=(
                    supply_fact(
                        1,
                        MarketplaceMomentumSupplyFactKind.DECREASED,
                    ),
                ),
                activity_facts=(activity_fact(1),),
            )
        )

        self.assertEqual(result.module_id, "marketplace_momentum")
        self.assertEqual(result.module_version, "1.0")
        self.assertEqual(output.rule_set_version, "1.0")
        self.assertEqual(
            build_v02_intelligence_registry().module_ids,
            (
                "collection_health",
                "hidden_gems",
                "historical_intelligence",
            ),
        )
        execution = IntelligenceEngine((MarketplaceMomentumModule(),)).execute(
            IntelligenceContext()
        )
        self.assertEqual(
            tuple(value.module_id for value in execution.results),
            ("marketplace_momentum",),
        )
        with self.assertRaises(TypeError):
            result.metrics["changed"] = True  # type: ignore[index]

    def test_domain_module_has_no_raw_history_persistence_network_or_ui_imports(
        self,
    ) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src/dip/decision_intelligence/marketplace_momentum.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "MarketplaceSnapshot",
            "MarketplaceHistory",
            "marketplace_history",
            "dip.persistence",
            "sqlite3",
            "requests",
            "urllib",
            "PriceChangesModule",
            "SupplyChangesModule",
            "RareAppearancesModule",
            "MarketplaceActivityModule",
            "ListingLifecycleModule",
            "datetime.now",
            "dip.experience",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
