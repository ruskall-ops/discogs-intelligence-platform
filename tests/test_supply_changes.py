from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import unittest

from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceStatus
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    SupplyChangeKind,
    SupplyChangesComparisonState,
    SupplyChangesModule,
    SupplyChangesOutput,
)


NOW = datetime(2026, 7, 22, tzinfo=timezone.utc)
OLD = datetime(2026, 7, 21, tzinfo=timezone.utc)


def observation(release_id, supply, *, status=MarketplaceDataStatus.COMPLETE):
    diagnostics = (MarketplaceDiagnostic("partial_supply", "Supply was incomplete."),) if status is MarketplaceDataStatus.PARTIAL else ()
    return MarketplaceReleaseObservation(release_id, OLD, status, num_for_sale=supply, num_wanted=1 if status is MarketplaceDataStatus.PARTIAL and supply is None else None, diagnostics=diagnostics)


def snapshot(identifier, captured, releases=(), *, status=MarketplaceDataStatus.COMPLETE, listings=()):
    diagnostics = (MarketplaceDiagnostic("partial_snapshot", "Snapshot was incomplete."),) if status is MarketplaceDataStatus.PARTIAL else ()
    return MarketplaceSnapshot(identifier, captured, "discogs", status, tuple(releases), tuple(listings), diagnostics)


def output(previous, latest):
    result = SupplyChangesModule().analyse(IntelligenceContext(marketplace_comparison=MarketplaceSnapshotComparisonInput(previous, latest)))
    value = result.metrics["output"]
    assert type(value) is SupplyChangesOutput
    return result, value


class SupplyChangesTestCase(unittest.TestCase):
    def test_compares_only_release_supply_and_orders_by_release_id(self):
        previous = snapshot("old", OLD, (observation(3, 4), observation(1, 12), observation(2, 15), observation(4, 7)))
        latest = snapshot("new", NOW, (observation(5, 9), observation(2, 12), observation(1, 15), observation(3, 4)))
        result, value = output(previous, latest)
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(tuple(change.release_id for change in value.changes), (1, 2, 4, 5))
        self.assertEqual(tuple(change.change_kind for change in value.changes), (SupplyChangeKind.INCREASED, SupplyChangeKind.DECREASED, SupplyChangeKind.NO_LONGER_AVAILABLE, SupplyChangeKind.NEWLY_AVAILABLE))
        self.assertEqual(tuple(change.delta for change in value.changes), (3, -3, None, None))
        self.assertEqual(value.summary.unchanged_count, 1)
        self.assertEqual(value.summary.change_count, 4)

    def test_missing_partial_fact_is_incomparable(self):
        previous = snapshot("old", OLD, (observation(1, None, status=MarketplaceDataStatus.PARTIAL),), status=MarketplaceDataStatus.PARTIAL)
        latest = snapshot("new", NOW, (observation(1, 2),))
        result, value = output(previous, latest)
        self.assertIs(value.comparison_state, SupplyChangesComparisonState.PARTIAL)
        self.assertIs(value.changes[0].change_kind, SupplyChangeKind.INCOMPARABLE)
        self.assertIsNone(value.changes[0].previous_supply)

    def test_empty_pair_is_valid_and_unavailable_failed_are_explicit(self):
        result, value = output(snapshot("old", OLD, status=MarketplaceDataStatus.EMPTY), snapshot("new", NOW, status=MarketplaceDataStatus.EMPTY))
        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(value.comparison_state, SupplyChangesComparisonState.COMPLETE)
        unavailable = MarketplaceSnapshot("new", NOW, "discogs", MarketplaceDataStatus.UNAVAILABLE, diagnostics=(_diagnostic(),))
        result, value = output(snapshot("old", OLD, status=MarketplaceDataStatus.EMPTY), unavailable)
        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(value.comparison_state, SupplyChangesComparisonState.INSUFFICIENT_DATA)

    def test_one_snapshot_is_insufficient_history_and_models_are_frozen(self):
        latest = snapshot("new", NOW, (observation(1, 2),))
        result = SupplyChangesModule().analyse(IntelligenceContext(marketplace_comparison=MarketplaceSnapshotComparisonInput(latest_snapshot=latest)))
        value = result.metrics["output"]
        self.assertIs(value.comparison_state, SupplyChangesComparisonState.INSUFFICIENT_HISTORY)
        with self.assertRaises(FrozenInstanceError):
            value.source = "other"

    def test_explicit_engine_registration(self):
        execution = IntelligenceEngine((SupplyChangesModule(),)).execute(IntelligenceContext())
        self.assertEqual(execution.results[0].module_id, "supply_changes")


def _diagnostic():
    return MarketplaceDiagnostic("not_available", "Source was unavailable.")


if __name__ == "__main__":
    unittest.main()
