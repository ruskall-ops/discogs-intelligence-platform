from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceStatus
from dip.marketplace_intelligence import ListingLifecycleModule, ListingLifecycleOutput, ListingLifecycleState, MarketplaceDataStatus, MarketplaceListingObservation, MarketplaceMoney, MarketplaceReleaseObservation, MarketplaceSnapshot


START = datetime(2026, 7, 1, tzinfo=timezone.utc)
PATTERNS = {
    "active": (1, 1, 1, 1, 1, 1),
    "new": (0, 0, 0, 0, 0, 1),
    "disappeared": (1, 1, 1, 1, 1, 0),
    "reappeared": (1, 0, 1, 1, 1, 1),
    "intermittent": (1, 0, 1, 0, 1, 1),
    "ended": (1, 1, 1, 0, 0, 0),
}


def history(patterns=PATTERNS):
    snapshots = []
    identities = tuple(enumerate(patterns.items(), 1))
    for index in range(6):
        when = START + timedelta(days=index)
        present = tuple((release_id, listing_id) for release_id, (listing_id, pattern) in identities if pattern[index])
        releases = tuple(MarketplaceReleaseObservation(release_id, when, MarketplaceDataStatus.COMPLETE, num_for_sale=1) for release_id, _ in present)
        listings = tuple(MarketplaceListingObservation(listing_id, release_id, when, MarketplaceMoney(Decimal("10"), "GBP")) for release_id, listing_id in present)
        snapshots.append(MarketplaceSnapshot(f"snapshot-{index}", when, "discogs", MarketplaceDataStatus.COMPLETE if releases else MarketplaceDataStatus.EMPTY, releases, listings))
    return tuple(snapshots)


def output(snapshots):
    result = ListingLifecycleModule().analyse(IntelligenceContext(marketplace_history=tuple(snapshots)))
    value = result.metrics["output"]
    assert type(value) is ListingLifecycleOutput
    return result, value


class ListingLifecycleTestCase(unittest.TestCase):
    def test_all_lifecycle_states_and_factual_counts(self):
        result, value = output(history())
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        by_id = {item.listing_id: item for item in value.lifecycles}
        expected = {"active": ListingLifecycleState.ACTIVE, "new": ListingLifecycleState.NEW, "disappeared": ListingLifecycleState.DISAPPEARED, "reappeared": ListingLifecycleState.REAPPEARED, "intermittent": ListingLifecycleState.INTERMITTENT, "ended": ListingLifecycleState.ENDED}
        self.assertEqual({key: by_id[key].lifecycle_state for key in expected}, expected)
        self.assertEqual(by_id["active"].continuous_lifetime, 6)
        self.assertEqual(by_id["active"].observation_ratio, Decimal(1))
        self.assertEqual(by_id["new"].snapshots_observed, 1)
        self.assertTrue(by_id["new"].currently_present)
        self.assertEqual(by_id["reappeared"].reappearance_count, 1)
        self.assertEqual(by_id["reappeared"].disappearance_count, 1)
        self.assertEqual(by_id["reappeared"].longest_absence, 1)
        self.assertEqual(by_id["reappeared"].continuous_lifetime, 4)
        self.assertEqual(by_id["intermittent"].reappearance_count, 2)
        self.assertEqual(by_id["intermittent"].disappearance_count, 2)
        self.assertEqual(by_id["ended"].longest_absence, 0)
        self.assertFalse(by_id["ended"].currently_present)
        for lifecycle in by_id.values():
            self.assertEqual(lifecycle.disappearance_count, lifecycle.reappearance_count + (0 if lifecycle.currently_present else 1))

    def test_order_is_state_then_ratio_descending_then_identity(self):
        patterns = {
            "active-full": (1, 1, 1, 1, 1, 1),
            "active-short-a": (0, 0, 1, 1, 1, 1),
            "active-short-b": (0, 0, 1, 1, 1, 1),
        }
        _, value = output(history(patterns))
        self.assertEqual(tuple(item.listing_id for item in value.lifecycles), ("active-full", "active-short-a", "active-short-b"))
        self.assertEqual(value.lifecycles[1].observation_ratio, Decimal(2) / Decimal(3))

    def test_duplicate_listing_and_history_id_are_rejected(self):
        snapshots = list(history({"active": (1, 1, 1, 1, 1, 1)}))
        first = snapshots[0]
        object.__setattr__(first, "listing_observations", (first.listing_observations[0], first.listing_observations[0]))
        with self.assertRaisesRegex(ValueError, "Duplicate listing identity"):
            output(snapshots)
        clean = history({"active": (1, 1, 1, 1, 1, 1)})
        with self.assertRaisesRegex(ValueError, "unique"):
            output((clean[0], clean[0]))

    def test_models_are_frozen_and_validate_state_consistency(self):
        _, value = output(history())
        with self.assertRaises(FrozenInstanceError):
            value.lifecycles = ()
        active = next(item for item in value.lifecycles if item.lifecycle_state is ListingLifecycleState.ACTIVE)
        with self.assertRaisesRegex(ValueError, "NEW"):
            replace(active, lifecycle_state=ListingLifecycleState.NEW)

    def test_empty_or_failed_only_history_has_explicit_results(self):
        when = START
        empty = MarketplaceSnapshot("empty", when, "discogs", MarketplaceDataStatus.EMPTY)
        result, value = output((empty,))
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(value.summary.listing_count, 0)
        from dip.marketplace_intelligence import MarketplaceDiagnostic
        failed = MarketplaceSnapshot("failed", when, "discogs", MarketplaceDataStatus.FAILED, diagnostics=(MarketplaceDiagnostic("capture_failed", "Capture failed."),))
        result, value = output((failed,))
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)

    def test_explicit_engine_registration(self):
        execution = IntelligenceEngine((ListingLifecycleModule(),)).execute(IntelligenceContext())
        self.assertEqual(execution.results[0].module_id, "listing_lifecycle")


if __name__ == "__main__":
    unittest.main()
