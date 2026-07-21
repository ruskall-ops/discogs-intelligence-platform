from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import IntelligenceHistoryRecord, IntelligenceHistoryRun


class IntelligenceHistoryModelTestCase(unittest.TestCase):
    def test_run_supports_documented_optional_fields(self) -> None:
        executed_at = datetime(2026, 7, 21, 12, 30, tzinfo=timezone.utc)

        run = IntelligenceHistoryRun(run_id=None, executed_at=executed_at)

        self.assertIsNone(run.engine_version)
        self.assertIsNone(run.collection_snapshot_id)
        self.assertEqual(run.result_count, 0)

    def test_run_is_immutable_and_has_value_equality(self) -> None:
        executed_at = datetime(2026, 7, 21, 12, 30)
        run = IntelligenceHistoryRun(4, executed_at, "0.2.0", 8, 3)

        self.assertEqual(
            run,
            IntelligenceHistoryRun(4, executed_at, "0.2.0", 8, 3),
        )
        with self.assertRaises(FrozenInstanceError):
            run.result_count = 4

    def test_record_is_immutable_and_preserves_standard_status(self) -> None:
        record = IntelligenceHistoryRecord(
            record_id=2,
            run_id=4,
            module_id="collection_health",
            module_version="1.1",
            status=IntelligenceStatus.COMPLETED,
            summary="Collection health completed.",
        )

        self.assertIs(record.status, IntelligenceStatus.COMPLETED)
        with self.assertRaises(FrozenInstanceError):
            record.summary = "Changed"

    def test_record_detaches_collection_fields_from_mutable_inputs(self) -> None:
        insights = ["One"]
        metrics = {"score": 81}
        evidence = ["Evidence"]
        diagnostics = ["Diagnostic"]

        record = IntelligenceHistoryRecord(
            record_id=None,
            run_id=4,
            module_id="collection_health",
            module_version=None,
            status=IntelligenceStatus.COMPLETED,
            summary="Completed.",
            insights=insights,
            metrics=metrics,
            evidence=evidence,
            diagnostics=diagnostics,
        )
        insights.append("Two")
        metrics["score"] = 0
        evidence.clear()
        diagnostics.clear()

        self.assertEqual(record.insights, ("One",))
        self.assertEqual(dict(record.metrics), {"score": 81})
        self.assertEqual(record.evidence, ("Evidence",))
        self.assertEqual(record.diagnostics, ("Diagnostic",))
        with self.assertRaises(TypeError):
            record.metrics["score"] = 0

    def test_record_recursively_freezes_nested_mappings_and_lists(self) -> None:
        metrics = {
            "history": [{"score": 80}],
            "details": {"labels": ["A"]},
            "coordinates": ([1, 2],),
        }
        record = IntelligenceHistoryRecord(
            record_id=None,
            run_id=4,
            module_id="collection_health",
            module_version=None,
            status=IntelligenceStatus.COMPLETED,
            summary="Completed.",
            metrics=metrics,
        )

        metrics["history"][0]["score"] = 0
        metrics["details"]["labels"].append("B")

        self.assertEqual(record.metrics["history"][0]["score"], 80)
        self.assertEqual(list(record.metrics["details"]["labels"]), ["A"])
        with self.assertRaises(TypeError):
            record.metrics["history"][0]["score"] = 0
        with self.assertRaises(AttributeError):
            record.metrics["history"].append({"score": 0})
        with self.assertRaises(AttributeError):
            record.metrics["coordinates"][0].append(3)
        with self.assertRaises(AttributeError):
            record.metrics["history"]._values = ()

    def test_record_rejects_mutable_values_in_non_metric_fields(self) -> None:
        required = {
            "record_id": None,
            "run_id": 4,
            "module_id": "collection_health",
            "module_version": None,
            "status": IntelligenceStatus.COMPLETED,
            "summary": "Completed.",
        }

        for field, value in (
            ("summary", []),
            ("insights", (["mutable"],)),
            ("evidence", "not a tuple"),
            ("diagnostics", ({"mutable": True},)),
            ("metrics", []),
        ):
            with self.subTest(field=field):
                with self.assertRaises(TypeError):
                    IntelligenceHistoryRecord(**required, **{field: value})


if __name__ == "__main__":
    unittest.main()
