from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import MarketplaceActivityDomainError, MarketplaceActivityModule, MarketplaceActivityOutput, MarketplaceActivityState, MarketplaceDataStatus, MarketplaceMoney, MarketplaceReleaseObservation, MarketplaceSnapshot, MarketplaceSnapshotComparisonInput, PriceChangesModule, RareAppearancesAnalysisState, RareAppearancesModule, SupplyChangesModule


START = datetime(2026, 7, 1, tzinfo=timezone.utc)


def observation(release_id, when, supply, price):
    return MarketplaceReleaseObservation(release_id, when, MarketplaceDataStatus.COMPLETE, lowest_price=MarketplaceMoney(Decimal(price), "GBP"), num_for_sale=supply)


def snapshot(index, values):
    when = START + timedelta(days=index)
    releases = tuple(observation(release_id, when, supply, price) for release_id, supply, price in values)
    return MarketplaceSnapshot(f"snapshot-{index}", when, "discogs", MarketplaceDataStatus.COMPLETE if releases else MarketplaceDataStatus.EMPTY, releases)


def source_results():
    history = (snapshot(0, ((1, 5, "10"), (2, 2, "5"))), snapshot(1, ((2, 2, "5"),)), snapshot(2, ((1, 7, "12"),)))
    comparison = IntelligenceContext(marketplace_comparison=MarketplaceSnapshotComparisonInput(history[1], history[2]))
    price = PriceChangesModule().analyse(comparison)
    supply = SupplyChangesModule().analyse(comparison)
    rare = RareAppearancesModule().analyse(IntelligenceContext(marketplace_history=history))
    return history, price, supply, rare


def activity(*sources):
    result = MarketplaceActivityModule().analyse(IntelligenceContext(marketplace_activity_sources=tuple(sources)))
    value = result.metrics["output"]
    assert type(value) is MarketplaceActivityOutput
    return result, value


class MarketplaceActivityTestCase(unittest.TestCase):
    def test_aggregates_only_typed_source_facts_and_orders_activity(self):
        _, price, supply, rare = source_results()
        result, output = activity(price, supply, rare)
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(tuple(value.release_id for value in output.activities), (1, 2))
        first = output.activities[0]
        self.assertEqual(first.appearance_count, 2)
        self.assertEqual(first.appearance_ratio, Decimal(2) / Decimal(3))
        self.assertEqual(first.historical_price_change_count, 1)
        self.assertEqual(first.historical_supply_change_count, 1)
        self.assertEqual(first.total_activity_count, 4)
        self.assertEqual(first.first_observation.snapshot_id, "snapshot-0")
        self.assertEqual(first.latest_observation.snapshot_id, "snapshot-2")
        self.assertEqual(first.longest_absence, 1)
        self.assertEqual(output.summary.total_activity_count, sum(value.total_activity_count for value in output.activities))

    def test_missing_required_source_is_skipped(self):
        _, price, _, rare = source_results()
        result, output = activity(price, rare)
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(output.state, MarketplaceActivityState.INSUFFICIENT_DATA)
        self.assertIn("supply_changes", result.diagnostics[0])

    def test_direct_domain_rejects_historical_future_listing_and_wrong_source_identities(self):
        _, price, supply, rare = source_results()
        hostile = "TOKEN-SQL-/private/live.sqlite-99.0"
        cases = (
            (replace(price, module_version="1.0"), supply, rare),
            (replace(price, module_version="99.0"), supply, rare),
            (replace(price, module_id="listing_price_changes", module_version="1.0"), supply, rare),
            (replace(price, module_id=hostile), supply, rare),
            (price, replace(supply, module_version="1.0"), rare),
            (price, replace(supply, module_version="99.0"), rare),
            (price, replace(supply, module_id="listing_price_changes", module_version="1.0"), rare),
            (price, replace(supply, module_id=hostile), rare),
        )
        for sources in cases:
            with self.subTest(identities=tuple((v.module_id, v.module_version) for v in sources)):
                result, output = activity(*sources)
                self.assertIs(result.status, IntelligenceStatus.SKIPPED)
                self.assertIs(output.state, MarketplaceActivityState.INSUFFICIENT_DATA)
                self.assertIn(
                    result.diagnostics,
                    (
                        ("A required Marketplace Activity source is incompatible.",),
                        ("Missing required source intelligence: price_changes.",),
                        ("Missing required source intelligence: supply_changes.",),
                    ),
                )
                self.assertNotIn(hostile, repr(result))

    def test_direct_domain_accepts_only_one_current_weekend_optional_source(self):
        _, price, supply, rare = source_results()
        weekend = IntelligenceResult(
            "weekend_listings",
            IntelligenceStatus.COMPLETED,
            "Weekend Listings completed.",
            module_version="1.0",
        )
        accepted, _ = activity(price, supply, rare, weekend)
        self.assertIs(accepted.status, IntelligenceStatus.COMPLETED)
        hostile = "TOKEN-SQL-/private/live.sqlite"
        cases = (
            (replace(weekend, module_version="99.0"),),
            (replace(weekend, module_version="0.9"),),
            (replace(weekend, module_id=hostile),),
            (replace(weekend, module_id="listing_price_changes"),),
            (price,),
            (supply,),
            (rare,),
            (weekend, weekend),
            (weekend, replace(weekend, module_id=hostile)),
        )
        for extras in cases:
            with self.subTest(extras=tuple((v.module_id, v.module_version) for v in extras)):
                try:
                    result, output = activity(price, supply, rare, *extras)
                except MarketplaceActivityDomainError as exc:
                    self.assertEqual(
                        str(exc),
                        "Marketplace Activity source identities must be unique.",
                    )
                    self.assertNotIn(hostile, str(exc))
                else:
                    self.assertIs(result.status, IntelligenceStatus.SKIPPED)
                    self.assertIs(output.state, MarketplaceActivityState.INSUFFICIENT_DATA)
                    self.assertEqual(
                        result.diagnostics,
                        ("The optional Marketplace Activity source is incompatible.",),
                    )
                    self.assertNotIn(hostile, repr(result))

    def test_direct_domain_rejects_every_malformed_optional_member_value_neutrally(self):
        _, price, supply, rare = source_results()
        hostile = "ACCESS-TOKEN SELECT-secret /private/live.sqlite 987"
        weekend = IntelligenceResult(
            "weekend_listings",
            IntelligenceStatus.COMPLETED,
            "Weekend Listings completed.",
            module_version="1.0",
        )

        class IdentityOnly:
            module_id = hostile

        class VersionOnly:
            module_version = hostile

        class NonStringIdentity:
            module_id = 99
            module_version = object()

        malformed = (
            hostile,
            object(),
            IdentityOnly(),
            VersionOnly(),
            NonStringIdentity(),
        )
        for value in malformed:
            for extras in ((value,), (weekend, value)):
                with self.subTest(value=type(value).__name__, with_weekend=len(extras) == 2):
                    with self.assertRaises(TypeError) as raised:
                        MarketplaceActivityModule().analyse(
                            IntelligenceContext(
                                marketplace_activity_sources=(price, supply, rare, *extras)
                            )
                        )
                    self.assertEqual(
                        str(raised.exception),
                        "marketplace_activity_sources must be a tuple of IntelligenceResult values.",
                    )
                    self.assertNotIn(hostile, str(raised.exception))

    def test_incompatible_histories_are_skipped(self):
        _, price, _, rare = source_results()
        other_old = snapshot(5, ((1, 1, "1"),))
        other_new = snapshot(6, ((1, 2, "1"),))
        supply = SupplyChangesModule().analyse(IntelligenceContext(marketplace_comparison=MarketplaceSnapshotComparisonInput(other_old, other_new)))
        result, output = activity(price, supply, rare)
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(output.state, MarketplaceActivityState.INSUFFICIENT_DATA)
        self.assertTrue(any("different snapshot pairs" in value for value in result.diagnostics))

    def test_duplicate_sources_rejected_and_models_are_frozen(self):
        _, price, supply, rare = source_results()
        with self.assertRaisesRegex(ValueError, "identities must be unique"):
            activity(price, price, supply, rare)
        _, output = activity(price, supply, rare)
        with self.assertRaises(FrozenInstanceError):
            output.activities = ()

    def test_partial_source_produces_partial_composite(self):
        _, price, supply, rare = source_results()
        rare_output = rare.metrics["output"]
        partial_rare = replace(rare, metrics={"output": replace(rare_output, analysis_state=RareAppearancesAnalysisState.PARTIAL)}, diagnostics=("Included partial history.",))
        result, output = activity(price, supply, partial_rare)
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(output.state, MarketplaceActivityState.PARTIAL)
        self.assertIn("Included partial history.", result.diagnostics)

    def test_default_registry_requires_explicit_registration(self):
        execution = IntelligenceEngine((MarketplaceActivityModule(),)).execute(IntelligenceContext())
        self.assertEqual(execution.results[0].module_id, "marketplace_activity")


if __name__ == "__main__":
    unittest.main()
