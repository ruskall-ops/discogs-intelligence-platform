from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import timedelta
from decimal import Decimal
import unittest

from dip.intelligence import IntelligenceContext, IntelligenceEngine, IntelligenceModule, IntelligenceStatus, build_v02_intelligence_registry
from dip.intelligence.modules import HistoricalComparison, HistoricalIntelligenceConfig, HistoricalIntelligenceModule, HistoricalReleaseChange


def row(release_id: object, value: object = None, *, artist: str = "Artist", title: str = "Title", captured_at: str = "2026-01-01T00:00:00Z") -> dict[str, object]:
    result = {"release_id": release_id, "artist": artist, "title": title, "captured_at": captured_at}
    if value is not None:
        result["lowest_price"] = value
    return result


class HistoricalIntelligenceModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = HistoricalIntelligenceModule()

    def test_successful_comparison_calculates_collection_and_valuation_metrics(self) -> None:
        context = IntelligenceContext(history={
            1: (row(1, 10), row(2, 20), row(3, 30)),
            2: (row(1, 15, captured_at="2026-01-03T00:00:00Z"), row(2, 10, captured_at="2026-01-03T00:00:00Z"), row(4, 50, captured_at="2026-01-03T00:00:00Z")),
        })
        result = self.module.analyse(context)
        comparison = result.metrics["comparison"]

        self.assertEqual(result.status, IntelligenceStatus.COMPLETED)
        self.assertIsInstance(comparison, HistoricalComparison)
        self.assertEqual(comparison.previous_snapshot.snapshot_id, "1")
        self.assertEqual(comparison.current_snapshot.snapshot_id, "2")
        self.assertEqual(comparison.elapsed_time, timedelta(days=2))
        self.assertEqual(comparison.collection_size_change, 0)
        self.assertEqual(comparison.additions_count, 1)
        self.assertEqual(comparison.removals_count, 1)
        self.assertEqual(comparison.additions[0].release_id, 4)
        self.assertEqual(comparison.removals[0].release_id, 3)
        self.assertEqual(comparison.previous_total_estimated_value, Decimal("60.00"))
        self.assertEqual(comparison.current_total_estimated_value, Decimal("75.00"))
        self.assertEqual(comparison.total_estimated_value_change, Decimal("15.00"))
        self.assertEqual(comparison.total_estimated_value_percentage_change, Decimal("25.00"))
        self.assertEqual(comparison.previous_average_release_value, Decimal("20.00"))
        self.assertEqual(comparison.current_average_release_value, Decimal("25.00"))
        self.assertEqual(comparison.average_release_value_change, Decimal("5.00"))
        self.assertEqual(comparison.previous_median_release_value, Decimal("20.00"))
        self.assertEqual(comparison.current_median_release_value, Decimal("15.00"))
        self.assertEqual(comparison.median_release_value_change, Decimal("-5.00"))
        self.assertEqual([item.release_id for item in comparison.largest_gainers], [1])
        self.assertEqual([item.release_id for item in comparison.largest_decliners], [2])
        self.assertNotIn(4, [item.release_id for item in comparison.largest_gainers])
        self.assertNotIn(3, [item.release_id for item in comparison.largest_decliners])

    def test_rankings_are_deterministic_with_release_id_tie_breaker(self) -> None:
        context = IntelligenceContext(history={
            1: (row(4, 20), row(2, 20), row(3, 20), row(1, 20)),
            2: (row(3, 15), row(1, 25), row(4, 15), row(2, 25)),
        })
        first = self.module.analyse(context).metrics["comparison"]
        second = self.module.analyse(context).metrics["comparison"]
        self.assertEqual(first, second)
        self.assertEqual([item.release_id for item in first.largest_gainers], [1, 2])
        self.assertEqual([item.release_id for item in first.largest_decliners], [3, 4])

    def test_missing_values_withhold_aggregate_metrics_without_using_zero(self) -> None:
        result = self.module.analyse(IntelligenceContext(history={
            1: (row(1, 10), row(2)),
            2: (row(1, 12), row(2, "invalid")),
        }))
        comparison = result.metrics["comparison"]
        self.assertIsNone(comparison.previous_total_estimated_value)
        self.assertIsNone(comparison.current_total_estimated_value)
        self.assertIsNone(comparison.total_estimated_value_change)
        self.assertEqual([item.release_id for item in comparison.largest_gainers], [1])
        self.assertTrue(any("aggregate valuation metrics were withheld" in item for item in result.diagnostics))

    def test_fewer_than_two_snapshots_is_skipped(self) -> None:
        for history in ({}, {1: (row(1, 10),)}):
            result = self.module.analyse(IntelligenceContext(history=history))
            self.assertEqual(result.status, IntelligenceStatus.SKIPPED)
            self.assertIsNone(result.metrics.get("comparison"))

    def test_empty_snapshots_compare_safely(self) -> None:
        result = self.module.analyse(IntelligenceContext(history={1: (), 2: ()}))
        comparison = result.metrics["comparison"]
        self.assertEqual(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(comparison.previous_total_estimated_value, Decimal("0.00"))
        self.assertEqual(comparison.current_average_release_value, None)
        self.assertEqual(comparison.collection_size_change, 0)

    def test_configuration_limits_and_thresholds_are_respected(self) -> None:
        module = HistoricalIntelligenceModule(HistoricalIntelligenceConfig(
            maximum_gainers=1, maximum_decliners=0,
            minimum_absolute_value_change=Decimal("3"), minimum_percentage_change=Decimal("10"),
            value_decimal_places=1,
        ))
        result = module.analyse(IntelligenceContext(history={
            1: (row(1, 10), row(2, 10), row(3, 10)),
            2: (row(1, 11), row(2, 13), row(3, 15)),
        }))
        comparison = result.metrics["comparison"]
        self.assertEqual([item.release_id for item in comparison.largest_gainers], [3])
        self.assertEqual(comparison.largest_decliners, ())
        self.assertEqual(comparison.current_total_estimated_value, Decimal("39.0"))

    def test_zero_previous_value_has_no_percentage_but_can_surface(self) -> None:
        comparison = self.module.analyse(IntelligenceContext(history={1: (row(1, 0),), 2: (row(1, 5),)})).metrics["comparison"]
        self.assertIsNone(comparison.total_estimated_value_percentage_change)
        self.assertIsNone(comparison.largest_gainers[0].percentage_change)

    def test_malformed_missing_and_duplicate_records_degrade_gracefully(self) -> None:
        context = IntelligenceContext(history={
            1: (row(1, 10), row(1, 99), {"title": "missing id"}, "bad"),
            2: (row(1, 12),),
            3: ({"title": "invalid snapshot"},),
        })
        result = self.module.analyse(context)
        comparison = result.metrics["comparison"]
        self.assertEqual(comparison.previous_collection_size, 1)
        self.assertEqual(comparison.largest_gainers[0].previous_estimated_value, Decimal("10.00"))
        self.assertTrue(any("duplicate release 1" in item for item in result.diagnostics))
        self.assertTrue(any("Snapshot 3 was excluded" in item for item in result.diagnostics))

    def test_identical_timestamps_use_identifier_tie_breaker(self) -> None:
        timestamp = "2026-01-01T00:00:00Z"
        comparison = self.module.analyse(IntelligenceContext(history={2: (row(1, 12, captured_at=timestamp),), 1: (row(1, 10, captured_at=timestamp),)})).metrics["comparison"]
        self.assertEqual((comparison.previous_snapshot.snapshot_id, comparison.current_snapshot.snapshot_id), ("1", "2"))

    def test_public_models_are_immutable_and_evidence_explains_changes(self) -> None:
        result = self.module.analyse(IntelligenceContext(history={1: (row(1, 10),), 2: (row(1, 12),)}))
        comparison = result.metrics["comparison"]
        change = comparison.largest_gainers[0]
        self.assertIsInstance(change, HistoricalReleaseChange)
        self.assertIn("absolute change", change.evidence[0])
        self.assertTrue(any("release_id" in item for item in result.evidence))
        with self.assertRaises(FrozenInstanceError):
            change.title = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            comparison.current_collection_size = 99  # type: ignore[misc]

    def test_contract_registry_and_engine_failure_isolation(self) -> None:
        self.assertIsInstance(self.module, IntelligenceModule)
        registry = build_v02_intelligence_registry()
        self.assertEqual(registry.module_ids, ("collection_health", "hidden_gems", "historical_intelligence"))
        self.assertIsInstance(registry.get("historical_intelligence"), HistoricalIntelligenceModule)

        class Failing(HistoricalIntelligenceModule):
            def analyse(self, context: IntelligenceContext):
                raise RuntimeError("controlled failure")

        failed = IntelligenceEngine([Failing()]).execute(IntelligenceContext()).result_for("historical_intelligence")
        self.assertEqual(failed.status, IntelligenceStatus.FAILED)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            HistoricalIntelligenceConfig(maximum_gainers=-1)
        with self.assertRaises(ValueError):
            HistoricalIntelligenceConfig(minimum_absolute_value_change=Decimal("-1"))
        with self.assertRaises(ValueError):
            HistoricalIntelligenceConfig(value_fields=())


if __name__ == "__main__":
    unittest.main()
