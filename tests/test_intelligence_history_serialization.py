from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceDeserializationError,
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
    IntelligenceSerializationError,
    deserialize_intelligence_value,
    dumps_intelligence_value,
    loads_intelligence_value,
    serialize_intelligence_value,
)


class _UnregisteredStatus(str, Enum):
    READY = "ready"


class IntelligenceHistorySerializationTestCase(unittest.TestCase):
    def test_primitives_and_nested_collections_round_trip(self) -> None:
        value = {
            "none": None,
            "bool": True,
            "int": 7,
            "float": 2.5,
            "str": "Café",
            "list": [1, {"nested": False}],
            "tuple": ("A", ["B"]),
        }

        restored = loads_intelligence_value(dumps_intelligence_value(value))

        self.assertEqual(restored, value)
        self.assertIsInstance(restored["list"], list)
        self.assertIsInstance(restored["tuple"], tuple)

    def test_dates_and_datetimes_round_trip_without_type_loss(self) -> None:
        naive = datetime(2026, 7, 21, 9, 15, 30, 123456)
        aware = datetime(
            2026,
            7,
            21,
            9,
            15,
            tzinfo=timezone(timedelta(hours=1)),
        )
        value = (date(2026, 7, 21), naive, aware)

        restored = loads_intelligence_value(dumps_intelligence_value(value))

        self.assertEqual(restored, value)
        self.assertIs(type(restored[0]), date)
        self.assertIs(type(restored[1]), datetime)
        self.assertIsNone(restored[1].tzinfo)
        self.assertEqual(restored[2].utcoffset(), timedelta(hours=1))

    def test_intelligence_status_round_trips_as_an_enum(self) -> None:
        restored = loads_intelligence_value(
            dumps_intelligence_value(IntelligenceStatus.SKIPPED)
        )

        self.assertIs(restored, IntelligenceStatus.SKIPPED)

    def test_unregistered_enum_type_is_rejected_deterministically(self) -> None:
        with self.assertRaisesRegex(
            IntelligenceSerializationError,
            "enum type is not registered",
        ):
            dumps_intelligence_value(_UnregisteredStatus.READY)

    def test_approved_history_models_round_trip(self) -> None:
        run = IntelligenceHistoryRun(
            run_id=9,
            executed_at=datetime(2026, 7, 21, 10, tzinfo=timezone.utc),
            engine_version="0.2.0",
            collection_snapshot_id=41,
            result_count=1,
        )
        record = IntelligenceHistoryRecord(
            record_id=10,
            run_id=9,
            module_id="collection_health",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Collection health completed.",
            insights=("Coverage improved",),
            metrics={"score": 84, "observed_on": date(2026, 7, 21)},
            evidence=("84 of 100 releases assessed",),
            diagnostics=(),
        )

        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(run)), run)
        restored_record = loads_intelligence_value(dumps_intelligence_value(record))
        self.assertEqual(restored_record, record)
        self.assertEqual(dict(restored_record.metrics), dict(record.metrics))

    def test_public_tree_api_preserves_tuples(self) -> None:
        serialized = serialize_intelligence_value((1, 2))

        self.assertEqual(
            deserialize_intelligence_value(serialized),
            (1, 2),
        )

    def test_output_is_compact_unicode_json_with_sorted_keys(self) -> None:
        first = {"z": 1, "a": "Café", "middle": {"b": 2, "a": 1}}
        second = {"middle": {"a": 1, "b": 2}, "a": "Café", "z": 1}

        first_payload = dumps_intelligence_value(first)
        second_payload = dumps_intelligence_value(second)

        self.assertEqual(first_payload, second_payload)
        self.assertEqual(serialize_intelligence_value(first), serialize_intelligence_value(second))

    def test_repeated_model_serialization_is_byte_for_byte_deterministic(self) -> None:
        record = IntelligenceHistoryRecord(
            record_id=None,
            run_id=1,
            module_id="hidden_gems",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Completed.",
            metrics={"z": 3, "a": (1, 2)},
        )

        payloads = {dumps_intelligence_value(record) for _ in range(20)}

        self.assertEqual(len(payloads), 1)

    def test_unsupported_values_raise_with_the_nested_location(self) -> None:
        unsupported = (
            complex(1, 2),
            {1, 2},
            b"bytes",
            Decimal("1.5"),
            object(),
            lambda: None,
            (item for item in (1, 2)),
        )

        for value in unsupported:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(
                    IntelligenceSerializationError,
                    r"\$\.metrics\[0\]",
                ):
                    dumps_intelligence_value({"metrics": [value]})

    def test_non_finite_floats_are_rejected_for_serialization_and_loading(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(IntelligenceSerializationError):
                    dumps_intelligence_value(value)

        for payload in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(payload=payload):
                with self.assertRaises(IntelligenceDeserializationError):
                    loads_intelligence_value(payload)

    def test_mappings_require_string_keys_and_allow_the_tag_key(self) -> None:
        with self.assertRaisesRegex(IntelligenceSerializationError, "keys must be strings"):
            serialize_intelligence_value({1: "value"})
        value = {"__dip_type__": "ordinary data", "value": {"z": 1, "a": 2}}
        self.assertEqual(loads_intelligence_value(dumps_intelligence_value(value)), value)

    def test_unsupported_dataclass_is_rejected(self) -> None:
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class OtherRecord:
            value: int

        with self.assertRaises(IntelligenceSerializationError):
            serialize_intelligence_value(OtherRecord(1))

    def test_malformed_tagged_values_are_rejected(self) -> None:
        malformed_values = (
            {"__dip_type__": "unknown", "value": "x"},
            {"__dip_type__": "tuple"},
            {"__dip_type__": "tuple", "items": "not a list"},
            {"__dip_type__": "date", "value": "2026-02-30"},
            {"__dip_type__": "datetime", "value": "not a datetime"},
            {
                "__dip_type__": "enum",
                "enum": "dip.intelligence.models.IntelligenceStatus",
                "value": "unknown",
            },
        )

        for value in malformed_values:
            with self.subTest(value=value):
                with self.assertRaises(IntelligenceDeserializationError):
                    deserialize_intelligence_value(value)

    def test_mapping_payload_requires_sorted_unique_string_keys(self) -> None:
        malformed_values = (
            {"__dip_type__": "mapping", "items": [["b", 1], ["a", 2]]},
            {"__dip_type__": "mapping", "items": [["a", 1], ["a", 2]]},
            {"__dip_type__": "mapping", "items": [[1, "value"]]},
            {"__dip_type__": "mapping", "items": [["a"]]},
            {"__dip_type__": "mapping", "items": "invalid"},
        )

        for value in malformed_values:
            with self.subTest(value=value):
                with self.assertRaises(IntelligenceDeserializationError):
                    deserialize_intelligence_value(value)

    def test_run_deserialization_strictly_validates_field_types(self) -> None:
        valid = serialize_intelligence_value(
            IntelligenceHistoryRun(
                run_id=1,
                executed_at=datetime(2026, 7, 21, 10),
                engine_version="0.2.0",
                collection_snapshot_id=2,
                result_count=1,
            )
        )
        invalid_values = (
            ("run_id", "1"),
            ("run_id", True),
            ("executed_at", "2026-07-21T10:00:00"),
            ("engine_version", 2),
            ("collection_snapshot_id", False),
            ("result_count", "1"),
            ("result_count", -1),
        )

        for field, invalid in invalid_values:
            with self.subTest(field=field, invalid=invalid):
                payload = dict(valid)
                payload[field] = invalid
                with self.assertRaisesRegex(
                    IntelligenceDeserializationError,
                    field,
                ):
                    deserialize_intelligence_value(payload)

    def test_record_deserialization_strictly_validates_field_types(self) -> None:
        valid = serialize_intelligence_value(
            IntelligenceHistoryRecord(
                record_id=2,
                run_id=1,
                module_id="collection_health",
                module_version="1.0",
                status=IntelligenceStatus.COMPLETED,
                summary="Completed.",
                insights=("Insight",),
                metrics={"score": 80},
                evidence=("Evidence",),
                diagnostics=("Diagnostic",),
            )
        )
        invalid_values = (
            ("record_id", False),
            ("run_id", "1"),
            ("module_id", 1),
            ("module_version", 1),
            ("status", "completed"),
            ("summary", []),
            ("insights", ["Insight"]),
            ("metrics", []),
            ("evidence", (1,)),
            ("diagnostics", "Diagnostic"),
        )

        for field, invalid in invalid_values:
            with self.subTest(field=field, invalid=invalid):
                payload = dict(valid)
                payload[field] = invalid
                with self.assertRaisesRegex(
                    IntelligenceDeserializationError,
                    field,
                ):
                    deserialize_intelligence_value(payload)

    def test_invalid_json_and_duplicate_keys_are_rejected(self) -> None:
        for payload in ('{"a":', '{"a":1,"a":2}'):
            with self.subTest(payload=payload):
                with self.assertRaises(IntelligenceDeserializationError):
                    loads_intelligence_value(payload)


if __name__ == "__main__":
    unittest.main()
