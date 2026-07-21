from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import unittest

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import (
    MARKETPLACE_SCHEMA_VERSION,
    MarketplaceDataStatus,
    MarketplaceDeserializationError,
    MarketplaceDiagnostic,
    MarketplaceDiagnosticSeverity,
    MarketplaceExecutionContext,
    MarketplaceModuleResult,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSerializationError,
    MarketplaceSnapshot,
    dumps_marketplace_module_result,
    dumps_marketplace_snapshot,
    loads_marketplace_module_result,
    loads_marketplace_snapshot,
    marketplace_module_result_from_dict,
    marketplace_module_result_to_dict,
    marketplace_snapshot_from_dict,
    marketplace_snapshot_to_dict,
)
from tests.test_marketplace_intelligence_models import (
    CAPTURED_AT,
    diagnostic,
    listing_observation,
    money,
    release_observation,
)


class MarketplaceSnapshotSerializationTestCase(unittest.TestCase):
    def test_complete_snapshot_round_trip_preserves_money_time_and_diagnostics(self) -> None:
        observed_at = datetime(
            2026,
            7,
            21,
            11,
            30,
            tzinfo=timezone(timedelta(hours=1)),
        )
        release = MarketplaceReleaseObservation(
            1,
            observed_at,
            MarketplaceDataStatus.COMPLETE,
            lowest_price=MarketplaceMoney(Decimal("10.2300"), "GBP"),
            num_for_sale=1,
            num_wanted=25,
            last_sold=date(2026, 7, 20),
            diagnostics=(
                MarketplaceDiagnostic(
                    "source_note",
                    "The provider supplied an informational note.",
                    MarketplaceDiagnosticSeverity.INFO,
                    {"z_value": "last", "a_value": "first"},
                ),
            ),
        )
        snapshot = MarketplaceSnapshot(
            "snapshot-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (release,),
            source_version="api-v2",
        )

        restored = loads_marketplace_snapshot(dumps_marketplace_snapshot(snapshot))

        self.assertEqual(restored, snapshot)
        restored_release = restored.release_observations[0]
        self.assertEqual(restored_release.lowest_price.amount, Decimal("10.2300"))
        self.assertEqual(restored_release.observed_at.utcoffset(), timedelta(hours=1))
        self.assertEqual(
            dict(restored_release.diagnostics[0].details),
            {"a_value": "first", "z_value": "last"},
        )

    def test_empty_partial_unavailable_and_failed_snapshots_round_trip(self) -> None:
        snapshots = (
            MarketplaceSnapshot(
                "empty-1", CAPTURED_AT, "discogs", MarketplaceDataStatus.EMPTY
            ),
            MarketplaceSnapshot(
                "partial-1",
                CAPTURED_AT,
                "discogs",
                MarketplaceDataStatus.PARTIAL,
                (release_observation(1, status=MarketplaceDataStatus.PARTIAL),),
                diagnostics=(diagnostic(),),
            ),
            MarketplaceSnapshot(
                "unavailable-1",
                CAPTURED_AT,
                "discogs",
                MarketplaceDataStatus.UNAVAILABLE,
                diagnostics=(diagnostic("source_unavailable"),),
            ),
            MarketplaceSnapshot(
                "failed-1",
                CAPTURED_AT,
                "discogs",
                MarketplaceDataStatus.FAILED,
                diagnostics=(diagnostic("capture_failed"),),
            ),
        )

        for snapshot in snapshots:
            with self.subTest(status=snapshot.status):
                self.assertEqual(
                    loads_marketplace_snapshot(dumps_marketplace_snapshot(snapshot)),
                    snapshot,
                )

    def test_serialization_is_deterministic_and_uses_json_primitives_only(self) -> None:
        first_diagnostic = MarketplaceDiagnostic(
            "source_note",
            "Source note.",
            details={"z_value": "last", "a_value": "first"},
        )
        second_diagnostic = MarketplaceDiagnostic(
            "source_note",
            "Source note.",
            details={"a_value": "first", "z_value": "last"},
        )
        first = MarketplaceSnapshot(
            "snapshot-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (release_observation(2), release_observation(1)),
            (listing_observation("listing-2", 2), listing_observation("listing-1", 1)),
            (first_diagnostic,),
        )
        second = MarketplaceSnapshot(
            "snapshot-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (release_observation(1), release_observation(2)),
            (listing_observation("listing-1", 1), listing_observation("listing-2", 2)),
            (second_diagnostic,),
        )

        payloads = {dumps_marketplace_snapshot(first) for _ in range(20)}

        self.assertEqual(len(payloads), 1)
        self.assertEqual(dumps_marketplace_snapshot(first), dumps_marketplace_snapshot(second))
        tree = marketplace_snapshot_to_dict(first)
        json.dumps(tree, allow_nan=False)
        assert_json_tree(self, tree)
        self.assertEqual(tree["schema_version"], MARKETPLACE_SCHEMA_VERSION)

    def test_dict_deserialization_does_not_mutate_payload(self) -> None:
        snapshot = MarketplaceSnapshot(
            "snapshot-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (release_observation(1),),
        )
        payload = marketplace_snapshot_to_dict(snapshot)
        original = deepcopy(payload)

        restored = marketplace_snapshot_from_dict(payload)

        self.assertEqual(restored, snapshot)
        self.assertEqual(payload, original)


class MarketplaceModuleResultSerializationTestCase(unittest.TestCase):
    def test_module_result_round_trip_preserves_supported_typed_metrics(self) -> None:
        metric_time = datetime(
            2026,
            7,
            21,
            13,
            tzinfo=timezone(timedelta(hours=1)),
        )
        module_result = MarketplaceModuleResult(
            MarketplaceExecutionContext(
                "execution-1",
                ("snapshot-1", "snapshot-2"),
                CAPTURED_AT,
            ),
            IntelligenceResult(
                module_id="marketplace_example",
                module_version="1.0",
                status=IntelligenceStatus.COMPLETED,
                summary="Marketplace example completed.",
                insights=("Supplied marketplace facts were interpreted.",),
                metrics={
                    "available": True,
                    "count": 2,
                    "ratio": 1.5,
                    "amount": Decimal("12.3400"),
                    "money": money("9.9900"),
                    "observed_on": date(2026, 7, 21),
                    "observed_at": metric_time,
                    "values": [1, {"b": 2, "a": 1}],
                    "diagnostic": diagnostic(),
                },
                evidence=("Two immutable snapshots supplied.",),
            ),
        )

        restored = loads_marketplace_module_result(
            dumps_marketplace_module_result(module_result)
        )

        self.assertEqual(restored, module_result)
        self.assertEqual(restored.result.metrics["amount"], Decimal("12.3400"))
        self.assertEqual(restored.result.metrics["money"], money("9.9900"))
        self.assertEqual(
            restored.result.metrics["observed_at"].utcoffset(),
            timedelta(hours=1),
        )
        self.assertIsInstance(restored.result.metrics["values"], tuple)

    def test_failed_module_result_round_trip(self) -> None:
        module_result = MarketplaceModuleResult(
            MarketplaceExecutionContext(
                "execution-1", ("snapshot-1",), CAPTURED_AT
            ),
            IntelligenceResult(
                module_id="marketplace_example",
                module_version=None,
                status=IntelligenceStatus.FAILED,
                summary="Marketplace example failed.",
                diagnostics=("Provider data was inconsistent.",),
            ),
        )

        self.assertEqual(
            loads_marketplace_module_result(
                dumps_marketplace_module_result(module_result)
            ),
            module_result,
        )

    def test_module_result_serialization_is_deterministic_and_does_not_mutate(self) -> None:
        first = module_result({"z_value": 2, "a_value": {"b": 2, "a": 1}})
        second = module_result({"a_value": {"a": 1, "b": 2}, "z_value": 2})
        tree = marketplace_module_result_to_dict(first)
        original = deepcopy(tree)

        restored = marketplace_module_result_from_dict(tree)

        self.assertEqual(restored, first)
        self.assertEqual(tree, original)
        self.assertEqual(
            dumps_marketplace_module_result(first),
            dumps_marketplace_module_result(second),
        )
        assert_json_tree(self, tree)


class MarketplaceDeserializationFailureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = MarketplaceSnapshot(
            "snapshot-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            (release_observation(1),),
        )

    def test_schema_missing_unknown_keys_and_wrong_primitives_are_rejected(self) -> None:
        valid = marketplace_snapshot_to_dict(self.snapshot)
        variants = []
        for version in (2, "1", True):
            payload = deepcopy(valid)
            payload["schema_version"] = version
            variants.append(payload)
        missing = deepcopy(valid)
        del missing["snapshot_id"]
        variants.append(missing)
        unknown = deepcopy(valid)
        unknown["unexpected"] = True
        variants.append(unknown)
        wrong_id = deepcopy(valid)
        wrong_id["snapshot_id"] = 1
        variants.append(wrong_id)

        for payload in variants:
            with self.subTest(payload=payload):
                with self.assertRaises(MarketplaceDeserializationError):
                    marketplace_snapshot_from_dict(payload)

    def test_invalid_enum_timestamp_decimal_and_currency_are_rejected(self) -> None:
        valid = marketplace_snapshot_to_dict(self.snapshot)
        variants = []
        invalid_status = deepcopy(valid)
        invalid_status["status"] = "unknown"
        variants.append(invalid_status)
        invalid_time = deepcopy(valid)
        invalid_time["captured_at"] = "not-a-datetime"
        variants.append(invalid_time)
        naive_time = deepcopy(valid)
        naive_time["captured_at"] = "2026-07-21T12:00:00"
        variants.append(naive_time)
        invalid_decimal = deepcopy(valid)
        invalid_decimal["release_observations"][0]["lowest_price"]["amount"] = "bad"
        variants.append(invalid_decimal)
        nonfinite_decimal = deepcopy(valid)
        nonfinite_decimal["release_observations"][0]["lowest_price"]["amount"] = "NaN"
        variants.append(nonfinite_decimal)
        invalid_currency = deepcopy(valid)
        invalid_currency["release_observations"][0]["lowest_price"]["currency"] = "gbp"
        variants.append(invalid_currency)

        for payload in variants:
            with self.subTest(payload=payload):
                with self.assertRaises(MarketplaceDeserializationError):
                    marketplace_snapshot_from_dict(payload)

    def test_duplicate_serialized_observations_are_rejected_by_domain_validation(self) -> None:
        payload = marketplace_snapshot_to_dict(self.snapshot)
        payload["release_observations"].append(
            deepcopy(payload["release_observations"][0])
        )

        with self.assertRaisesRegex(MarketplaceDeserializationError, "unique"):
            marketplace_snapshot_from_dict(payload)

    def test_malformed_metric_tags_and_mapping_order_are_rejected(self) -> None:
        valid = marketplace_module_result_to_dict(module_result({"a": 1, "b": 2}))
        variants = []
        unknown = deepcopy(valid)
        unknown["result"]["metrics"]["__marketplace_type__"] = "unknown"
        variants.append(unknown)
        unsorted = deepcopy(valid)
        unsorted["result"]["metrics"]["items"].reverse()
        variants.append(unsorted)
        duplicate = deepcopy(valid)
        duplicate["result"]["metrics"]["items"].append(
            deepcopy(duplicate["result"]["metrics"]["items"][0])
        )
        variants.append(duplicate)
        untagged = deepcopy(valid)
        untagged["result"]["metrics"] = {"a": 1}
        variants.append(untagged)

        for payload in variants:
            with self.subTest(payload=payload):
                with self.assertRaises(MarketplaceDeserializationError):
                    marketplace_module_result_from_dict(payload)

    def test_invalid_json_duplicate_keys_and_nonfinite_constants_are_rejected(self) -> None:
        payloads = (
            "{",
            '{"schema_version":1,"schema_version":1}',
            '{"schema_version":NaN}',
            '{"schema_version":Infinity}',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(MarketplaceDeserializationError):
                    loads_marketplace_snapshot(payload)

    def test_unsupported_metric_type_is_rejected_before_serialization(self) -> None:
        with self.assertRaises(TypeError):
            module_result({"unsupported": object()})
        with self.assertRaises((TypeError, ValueError)):
            module_result({"nonfinite": float("inf")})


class MarketplaceArchitectureBoundaryTestCase(unittest.TestCase):
    def test_package_exports_only_the_deliberate_foundation_api(self) -> None:
        import dip.marketplace_intelligence as marketplace_api

        expected = {
            "MarketplaceSnapshot",
            "MarketplaceListingObservation",
            "MarketplaceReleaseObservation",
            "MarketplaceMoney",
            "MarketplaceModuleResult",
            "marketplace_snapshot_to_dict",
            "marketplace_snapshot_from_dict",
            "marketplace_module_result_to_dict",
            "marketplace_module_result_from_dict",
        }

        self.assertTrue(expected.issubset(set(marketplace_api.__all__)))
        self.assertFalse(any(name.startswith("_") for name in marketplace_api.__all__))

    def test_package_has_no_forbidden_layer_or_network_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[1] / "src/dip/marketplace_intelligence"
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(root.glob("*.py"))
        )

        forbidden = (
            "dip.persistence",
            "sqlite3",
            "dip.experience",
            "dip.app",
            "dip.collection",
            "requests",
            "urllib",
            "httpx",
            "tkinter",
        )
        for dependency in forbidden:
            with self.subTest(dependency=dependency):
                self.assertNotIn(dependency, source)
        self.assertNotIn("datetime.now", source)
        self.assertNotIn("datetime.utcnow", source)

    def test_public_money_contract_contains_no_float_coercion(self) -> None:
        model_source = (
            Path(__file__).resolve().parents[1]
            / "src/dip/marketplace_intelligence/models.py"
        ).read_text(encoding="utf-8")

        money_block = model_source.split("class MarketplaceMoney:", 1)[1].split(
            "@dataclass", 1
        )[0]
        self.assertNotIn("float(", money_block)


def module_result(metrics) -> MarketplaceModuleResult:
    return MarketplaceModuleResult(
        MarketplaceExecutionContext(
            "execution-1",
            ("snapshot-1", "snapshot-2"),
            CAPTURED_AT,
        ),
        IntelligenceResult(
            module_id="marketplace_example",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Marketplace example completed.",
            metrics=metrics,
        ),
    )


def assert_json_tree(test: unittest.TestCase, value) -> None:
    if value is None or type(value) in {bool, int, float, str}:
        return
    if isinstance(value, list):
        for item in value:
            assert_json_tree(test, item)
        return
    test.assertIsInstance(value, dict)
    for key, item in value.items():
        test.assertIsInstance(key, str)
        assert_json_tree(test, item)


if __name__ == "__main__":
    unittest.main()
