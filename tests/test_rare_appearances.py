from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceStatus
from dip.marketplace_intelligence import MarketplaceDataStatus, MarketplaceDiagnostic, MarketplaceReleaseObservation, MarketplaceSnapshot, RareAppearancesAnalysisState, RareAppearancesModule, RareAppearancesOutput


START = datetime(2026, 7, 1, tzinfo=timezone.utc)


def release(release_id, when):
    return MarketplaceReleaseObservation(release_id, when, MarketplaceDataStatus.COMPLETE, num_for_sale=1)


def snapshot(index, release_ids=(), status=MarketplaceDataStatus.COMPLETE):
    when = START + timedelta(days=index)
    if not release_ids and status is MarketplaceDataStatus.COMPLETE:
        status = MarketplaceDataStatus.EMPTY
    diagnostics = (MarketplaceDiagnostic("history_status", "Snapshot status was reported."),) if status in {MarketplaceDataStatus.PARTIAL, MarketplaceDataStatus.UNAVAILABLE, MarketplaceDataStatus.FAILED} else ()
    releases = tuple(release(value, when) for value in release_ids)
    return MarketplaceSnapshot(f"snapshot-{index}", when, "discogs", status, releases, diagnostics=diagnostics)


def output(history, threshold=3):
    result = RareAppearancesModule(threshold).analyse(IntelligenceContext(marketplace_history=tuple(history)))
    value = result.metrics["output"]
    assert type(value) is RareAppearancesOutput
    return result, value


class RareAppearancesTestCase(unittest.TestCase):
    def test_counts_observations_ratio_boundaries_and_longest_internal_absence(self):
        history = (snapshot(0, (1, 2)), snapshot(1, (2,)), snapshot(2, (2,)), snapshot(3, (1,)), snapshot(4, (3,)))
        result, value = output(history)
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        by_id = {item.release_id: item for item in value.appearances}
        self.assertEqual(by_id[1].appearance_count, 2)
        self.assertEqual(by_id[1].appearance_ratio, Decimal(2) / Decimal(5))
        self.assertEqual(by_id[1].longest_absence, 2)
        self.assertEqual(by_id[1].first_observed_snapshot.snapshot_id, "snapshot-0")
        self.assertEqual(by_id[1].latest_observed_snapshot.snapshot_id, "snapshot-3")
        self.assertEqual(by_id[3].longest_absence, 0)
        self.assertNotIn(2, by_id)

    def test_threshold_and_canonical_order(self):
        history = (snapshot(0, (3, 4)), snapshot(1, (4,)), snapshot(2), snapshot(3, (4, 2)), snapshot(4, (1, 3)))
        _, value = output(history, threshold=4)
        self.assertEqual(tuple(item.release_id for item in value.appearances), (1, 2, 3, 4))
        self.assertTrue(all(item.appearance_count < 4 for item in value.appearances))

    def test_unavailable_failed_excluded_partial_and_empty_count(self):
        history = (snapshot(0, (1,)), snapshot(1, status=MarketplaceDataStatus.UNAVAILABLE), snapshot(2, status=MarketplaceDataStatus.FAILED), snapshot(3, status=MarketplaceDataStatus.EMPTY), snapshot(4, (1,), MarketplaceDataStatus.PARTIAL))
        result, value = output(history)
        self.assertIs(value.analysis_state, RareAppearancesAnalysisState.PARTIAL)
        self.assertEqual(value.summary.history_snapshot_count, 3)
        self.assertEqual(value.summary.excluded_snapshot_count, 2)
        self.assertEqual(value.appearances[0].appearance_ratio, Decimal(2) / Decimal(3))
        self.assertIn("Ignored 1 unavailable", "\n".join(result.diagnostics))
        self.assertIn("Excluded 1 failed", "\n".join(result.diagnostics))

    def test_no_usable_history_skips_and_output_is_frozen(self):
        result, value = output((snapshot(1, status=MarketplaceDataStatus.FAILED),))
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(value.analysis_state, RareAppearancesAnalysisState.INSUFFICIENT_HISTORY)
        with self.assertRaises(FrozenInstanceError):
            value.threshold = 4

    def test_rejects_invalid_threshold_duplicate_or_unordered_history(self):
        for value in (True, 0, -1):
            with self.assertRaises((TypeError, ValueError)):
                RareAppearancesModule(value)
        with self.assertRaisesRegex(ValueError, "unique"):
            output((snapshot(0), snapshot(0)))
        with self.assertRaisesRegex(ValueError, "chronological"):
            output((snapshot(1), snapshot(0)))

    def test_explicit_engine_registration(self):
        execution = IntelligenceEngine((RareAppearancesModule(),)).execute(IntelligenceContext())
        self.assertEqual(execution.results[0].module_id, "rare_appearances")


if __name__ == "__main__":
    unittest.main()
