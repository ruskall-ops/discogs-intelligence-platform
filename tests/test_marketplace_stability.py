from dataclasses import FrozenInstanceError
from decimal import Decimal
import unittest

from dip.decision_intelligence import (
    AppearanceContinuityThresholds,
    ChangeStabilityThresholds,
    ListingPersistenceThresholds,
    MarketplaceStabilityDomainError,
    MarketplaceStabilityInput,
    MarketplaceStabilityModule,
    StabilityActivityFact,
    StabilityAssessment,
    StabilityComponentState,
    StabilityEvidenceCoverage,
    StabilityLifecycleFact,
    StabilityListingState,
    StabilitySourceProvenance,
)
from dip.intelligence import IntelligenceContext, IntelligenceStatus


def provenance(module_id, *, partial=False):
    return StabilitySourceProvenance(
        module_id, "1.0", IntelligenceStatus.COMPLETED, True, partial,
        ("a", "b"), ("partial evidence",) if partial else (),
    )


def activity(release_id=1, *, price=0, supply=0, appearances=2, ratio="1", absence=0):
    return StabilityActivityFact(
        release_id, price, supply, appearances, Decimal(ratio), absence,
        price + supply + appearances,
    )


def lifecycle(
    listing_id="listing",
    *,
    release_id=1,
    state=StabilityListingState.ACTIVE,
    current=True,
    disappearances=0,
    reappearances=0,
):
    return StabilityLifecycleFact(
        release_id, listing_id, state, current, disappearances, reappearances
    )


def supplied(*, activities=(), lifecycles=(), partial=False):
    return MarketplaceStabilityInput(
        source_provenance=(
            provenance("marketplace_activity", partial=partial),
            provenance("listing_lifecycle", partial=partial),
        ),
        activity_facts=tuple(activities),
        lifecycle_facts=tuple(lifecycles),
    )


def analyse(value, module=None):
    result = (module or MarketplaceStabilityModule()).analyse(
        IntelligenceContext(marketplace_stability_input=value)
    )
    return result, result.metrics["output"]


class MarketplaceStabilityModuleTestCase(unittest.TestCase):
    def test_change_threshold_bands_and_custom_thresholds(self):
        _, output = analyse(supplied(
            activities=(
                activity(1, price=0, supply=0),
                activity(2, price=1, supply=2),
                activity(3, price=3, supply=4),
            ),
            lifecycles=tuple(lifecycle(str(value), release_id=value) for value in (1, 2, 3)),
        ))
        by_id = {value.release_id: value for value in output.releases}
        self.assertEqual(
            tuple(by_id[value].components.price.state for value in (1, 2, 3)),
            (
                StabilityComponentState.STABLE,
                StabilityComponentState.MIXED,
                StabilityComponentState.VOLATILE,
            ),
        )
        self.assertIs(by_id[2].components.supply.state, StabilityComponentState.MIXED)
        self.assertIs(by_id[3].components.supply.state, StabilityComponentState.VOLATILE)

        custom = MarketplaceStabilityModule(
            price_thresholds=ChangeStabilityThresholds(4),
            supply_thresholds=ChangeStabilityThresholds(4),
        )
        _, custom_output = analyse(
            supplied(activities=(activity(price=3, supply=4),), lifecycles=(lifecycle(),)),
            custom,
        )
        self.assertIs(custom_output.releases[0].components.price.state, StabilityComponentState.MIXED)
        self.assertEqual(custom_output.price_thresholds.mixed_maximum, 4)

    def test_appearance_continuity_uses_exact_decimal_and_absence(self):
        _, output = analyse(supplied(
            activities=(
                activity(1),
                activity(2, ratio="0.75", absence=1),
                activity(3, ratio="0.5", absence=2),
            ),
            lifecycles=tuple(lifecycle(str(value), release_id=value) for value in (1, 2, 3)),
        ))
        by_id = {value.release_id: value for value in output.releases}
        self.assertIs(by_id[1].components.appearance.state, StabilityComponentState.STABLE)
        self.assertIs(by_id[2].components.appearance.state, StabilityComponentState.MIXED)
        self.assertIs(by_id[3].components.appearance.state, StabilityComponentState.VOLATILE)
        self.assertEqual(by_id[2].components.appearance.appearance_ratio, Decimal("0.75"))

    def test_listing_aggregation_and_classification_are_visible(self):
        values = (
            lifecycle("active"),
            lifecycle("ended", state=StabilityListingState.ENDED, current=False, disappearances=1),
            lifecycle("returned", state=StabilityListingState.REAPPEARED, reappearances=1),
            lifecycle("intermittent", state=StabilityListingState.INTERMITTENT, disappearances=2, reappearances=2),
        )
        _, output = analyse(supplied(activities=(activity(),), lifecycles=values))
        component = output.releases[0].components.listing
        facts = component.facts
        self.assertIs(component.state, StabilityComponentState.VOLATILE)
        self.assertEqual(facts.total_listing_count, 4)
        self.assertEqual(facts.currently_present_count, 3)
        self.assertEqual(facts.ended_count, 1)
        self.assertEqual(facts.reappeared_count, 1)
        self.assertEqual(facts.intermittent_count, 1)
        self.assertEqual(facts.total_disappearance_count, 3)
        self.assertEqual(facts.total_reappearance_count, 3)
        self.assertEqual(facts.currently_present_ratio, Decimal("0.75"))
        self.assertEqual(facts.disrupted_ratio, Decimal("0.75"))

    def test_assessment_precedence_complete_partial_limited_and_insufficient(self):
        _, stable = analyse(supplied(activities=(activity(),), lifecycles=(lifecycle(),)))
        self.assertIs(stable.releases[0].assessment, StabilityAssessment.STABLE)
        self.assertIs(stable.releases[0].components.evidence_coverage, StabilityEvidenceCoverage.COMPLETE)

        _, partial = analyse(supplied(activities=(activity(),), lifecycles=(lifecycle(),), partial=True))
        self.assertIs(partial.releases[0].components.evidence_coverage, StabilityEvidenceCoverage.PARTIAL)

        _, limited = analyse(supplied(activities=(activity(price=1),), lifecycles=()))
        self.assertIs(limited.releases[0].components.evidence_coverage, StabilityEvidenceCoverage.LIMITED)

        result, insufficient = analyse(MarketplaceStabilityInput())
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertEqual(insufficient.releases, ())

    def test_two_volatile_components_produce_volatile_assessment(self):
        _, output = analyse(supplied(
            activities=(activity(price=3, supply=3),),
            lifecycles=(lifecycle(),),
        ))
        self.assertIs(output.releases[0].assessment, StabilityAssessment.VOLATILE)

    def test_sparse_required_release_presence_is_explicit(self):
        _, output = analyse(supplied(
            activities=(activity(1),),
            lifecycles=(lifecycle("other", release_id=2),),
        ))
        by_id = {value.release_id: value for value in output.releases}
        self.assertIs(by_id[1].components.listing.state, StabilityComponentState.INSUFFICIENT)
        self.assertIs(by_id[2].components.price.state, StabilityComponentState.INSUFFICIENT)
        self.assertIs(by_id[2].assessment, StabilityAssessment.INSUFFICIENT)

    def test_order_summary_rule_version_and_immutability(self):
        _, output = analyse(supplied(
            activities=(activity(2, price=3, supply=3), activity(1)),
            lifecycles=(lifecycle("2", release_id=2), lifecycle("1", release_id=1)),
        ))
        self.assertEqual(tuple(value.release_id for value in output.releases), (1, 2))
        self.assertEqual(output.rule_set_version, "1.0")
        self.assertEqual(output.summary.release_count, 2)
        self.assertEqual(output.summary.stable_count, 1)
        self.assertEqual(output.summary.volatile_count, 1)
        with self.assertRaises(FrozenInstanceError):
            output.summary.release_count = 4

    def test_invalid_thresholds_and_duplicate_identities_are_rejected(self):
        with self.assertRaises((TypeError, MarketplaceStabilityDomainError)):
            ChangeStabilityThresholds(0)
        with self.assertRaises((TypeError, MarketplaceStabilityDomainError)):
            AppearanceContinuityThresholds(-1)
        with self.assertRaises((TypeError, MarketplaceStabilityDomainError)):
            ListingPersistenceThresholds(Decimal("1.1"), 2)
        with self.assertRaisesRegex(MarketplaceStabilityDomainError, "Duplicate lifecycle"):
            supplied(activities=(activity(),), lifecycles=(lifecycle(), lifecycle()))


if __name__ == "__main__":
    unittest.main()

