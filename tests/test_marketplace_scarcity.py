from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest

from dip.decision_intelligence import (
    AppearanceScarcityThresholds,
    AvailabilityThresholds,
    ListingScarcityThresholds,
    MarketplaceScarcityDomainError,
    MarketplaceScarcityInput,
    MarketplaceScarcityModule,
    ScarcityAppearanceFact,
    ScarcityAssessment,
    ScarcityComponentState,
    ScarcityEvidenceCoverage,
    ScarcityLifecycleFact,
    ScarcityListingState,
    ScarcitySourceProvenance,
)
from dip.intelligence import IntelligenceContext, IntelligenceStatus


def provenance(module_id, partial=False):
    return ScarcitySourceProvenance(
        module_id, "1.0", IntelligenceStatus.COMPLETED, True, partial,
        ("a", "b", "c", "d"), ("partial",) if partial else (),
    )


def appearance(release_id=1, count=4, history=4, absence=0):
    return ScarcityAppearanceFact(
        release_id, count, history, Decimal(count) / Decimal(history), absence
    )


def listing(index, *, release_id=1, state=ScarcityListingState.ACTIVE, current=True, ratio="1", disappearances=0, reappearances=0, absence=0):
    return ScarcityLifecycleFact(
        release_id, f"listing-{index}", state, current, Decimal(ratio),
        disappearances, reappearances, absence,
    )


def supplied(*, appearances=(), lifecycles=(), partial=False):
    return MarketplaceScarcityInput(
        source_provenance=(
            provenance("rare_appearances", partial),
            provenance("listing_lifecycle", partial),
        ),
        appearance_facts=tuple(appearances),
        lifecycle_facts=tuple(lifecycles),
    )


def analyse(value, module=None):
    result = (module or MarketplaceScarcityModule()).analyse(
        IntelligenceContext(marketplace_scarcity_input=value)
    )
    return result, result.metrics["output"]


class MarketplaceScarcityModuleTestCase(unittest.TestCase):
    def test_observed_availability_default_bands(self):
        appearances = tuple(appearance(value) for value in range(1, 6))
        lifecycles = tuple(
            listing(index, release_id=release_id)
            for release_id, count in enumerate((0, 1, 2, 5, 10), 1)
            for index in range(count)
        )
        _, output = analyse(supplied(appearances=appearances, lifecycles=lifecycles))
        by_id = {value.release_id: value for value in output.releases}
        self.assertEqual(
            tuple(by_id[value].components.observed_availability.state for value in range(1, 6)),
            (
                ScarcityComponentState.INSUFFICIENT,
                ScarcityComponentState.SCARCE,
                ScarcityComponentState.LIMITED,
                ScarcityComponentState.COMMON,
                ScarcityComponentState.ABUNDANT,
            ),
        )

    def test_zero_current_listings_are_very_scarce_not_a_sale_inference(self):
        ended = tuple(listing(value, state=ScarcityListingState.ENDED, current=False, disappearances=1) for value in range(3))
        _, output = analyse(supplied(appearances=(appearance(count=1),), lifecycles=ended))
        release = output.releases[0]
        self.assertIs(release.components.observed_availability.state, ScarcityComponentState.VERY_SCARCE)
        self.assertIs(release.components.listing_persistence.state, ScarcityComponentState.VERY_SCARCE)
        self.assertIs(release.assessment, ScarcityAssessment.VERY_SCARCE)

    def test_appearance_decimal_boundaries_and_absence_are_preserved(self):
        appearances = (
            appearance(1, 4, 4),
            appearance(2, 3, 4),
            appearance(3, 2, 4, 1),
            appearance(4, 1, 4, 2),
        )
        lifecycles = tuple(listing(value, release_id=value) for value in range(1, 5))
        _, output = analyse(supplied(appearances=appearances, lifecycles=lifecycles))
        by_id = {value.release_id: value for value in output.releases}
        self.assertEqual(
            tuple(by_id[value].components.appearance.state for value in range(1, 5)),
            (
                ScarcityComponentState.ABUNDANT,
                ScarcityComponentState.COMMON,
                ScarcityComponentState.LIMITED,
                ScarcityComponentState.SCARCE,
            ),
        )
        self.assertEqual(by_id[4].components.appearance.appearance_ratio, Decimal("0.25"))
        self.assertEqual(by_id[4].components.appearance.longest_internal_absence, 2)

    def test_listing_persistence_aggregates_exact_facts(self):
        lifecycles = (
            listing(1),
            listing(2, state=ScarcityListingState.REAPPEARED, ratio="0.75", disappearances=1, reappearances=1, absence=1),
            listing(3, state=ScarcityListingState.ENDED, current=False, ratio="0.5", disappearances=1, absence=2),
            listing(4, state=ScarcityListingState.INTERMITTENT, ratio="0.5", disappearances=2, reappearances=2, absence=2),
        )
        _, output = analyse(supplied(appearances=(appearance(),), lifecycles=lifecycles))
        component = output.releases[0].components.listing_persistence
        self.assertIs(component.state, ScarcityComponentState.SCARCE)
        self.assertEqual(component.currently_present_count, 3)
        self.assertEqual(component.disrupted_listing_count, 3)
        self.assertEqual(component.disrupted_ratio, Decimal("0.75"))
        self.assertEqual(component.average_observation_ratio, Decimal("0.6875"))
        self.assertEqual(component.total_disappearance_count, 4)
        self.assertEqual(component.total_reappearance_count, 3)
        self.assertEqual(component.longest_listing_absence, 2)

    def test_assessment_rules_and_evidence_coverage(self):
        ten = tuple(listing(value) for value in range(10))
        _, abundant = analyse(supplied(appearances=(appearance(),), lifecycles=ten))
        self.assertIs(abundant.releases[0].assessment, ScarcityAssessment.ABUNDANT)
        self.assertIs(abundant.releases[0].components.evidence_coverage, ScarcityEvidenceCoverage.COMPLETE)

        _, partial = analyse(supplied(appearances=(appearance(),), lifecycles=ten, partial=True))
        self.assertIs(partial.releases[0].components.evidence_coverage, ScarcityEvidenceCoverage.PARTIAL)

        _, limited = analyse(supplied(appearances=(appearance(),), lifecycles=()))
        self.assertIs(limited.releases[0].components.evidence_coverage, ScarcityEvidenceCoverage.LIMITED)

        result, insufficient = analyse(MarketplaceScarcityInput())
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertEqual(insufficient.releases, ())

    def test_custom_and_invalid_thresholds(self):
        custom = MarketplaceScarcityModule(
            availability_thresholds=AvailabilityThresholds(6, 4, 2),
            appearance_thresholds=AppearanceScarcityThresholds(Decimal("0.8"), Decimal("0.4")),
            listing_thresholds=ListingScarcityThresholds(Decimal("0.6"), Decimal("0.4")),
        )
        _, output = analyse(supplied(
            appearances=(appearance(count=3),),
            lifecycles=tuple(listing(value) for value in range(6)),
        ), custom)
        self.assertIs(output.releases[0].components.observed_availability.state, ScarcityComponentState.ABUNDANT)
        self.assertEqual(output.availability_thresholds.abundant_minimum, 6)
        for constructor in (
            lambda: AvailabilityThresholds(5, 5, 2),
            lambda: AvailabilityThresholds(5, 3, 1),
            lambda: AppearanceScarcityThresholds(Decimal("0.5"), Decimal("0.75")),
            lambda: ListingScarcityThresholds(Decimal("1.1"), Decimal("0.5")),
        ):
            with self.assertRaises((TypeError, MarketplaceScarcityDomainError)):
                constructor()

    def test_sparse_evidence_order_summary_and_immutability(self):
        _, output = analyse(supplied(
            appearances=(appearance(2, 1, 4),),
            lifecycles=(listing(1, release_id=1),),
        ))
        self.assertEqual(output.rule_set_version, "1.0")
        self.assertEqual(output.summary.release_count, 2)
        self.assertEqual(tuple(value.release_id for value in output.releases), (1, 2))
        with self.assertRaises(FrozenInstanceError):
            output.summary.release_count = 3

    def test_duplicate_listing_identity_is_rejected(self):
        with self.assertRaisesRegex(MarketplaceScarcityDomainError, "duplicate"):
            supplied(appearances=(appearance(),), lifecycles=(listing(1), listing(1)))


if __name__ == "__main__":
    unittest.main()
