from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from dip.app.marketplace_capture import (
    build_marketplace_snapshot,
    normalize_provider_facts,
    project_legacy_marketplace_facts,
    successful_capture_attempt,
)
from dip.data_sources.discogs.client import DiscogsClient
from dip.marketplace_intelligence import MarketplaceDataStatus


CAPTURED_AT = datetime(2026, 7, 26, 12, tzinfo=timezone.utc)


class _Response:
    def __init__(self, status_code=200, payload=None, text="provider detail"):
        self.status_code = status_code
        self.payload = payload or {}
        self.text = text
        self.headers = {}
        self.json_calls = []

    def json(self, **kwargs):
        self.json_calls.append(kwargs)
        return self.payload


class _Session:
    def __init__(self, response):
        self.responses = (
            list(response) if isinstance(response, (list, tuple)) else [response]
        )
        self.calls = []

    def get(self, url, timeout):
        self.calls.append((url, timeout))
        return self.responses.pop(0)


class DiscogsProviderParsingTestCase(unittest.TestCase):
    def client(self, response):
        client = DiscogsClient("temporary-token")
        client.session = _Session(response)
        return client

    def canonical(self, response, release_id=1):
        data = self.client(response).get_release(release_id)
        facts = normalize_provider_facts(data)
        snapshot = build_marketplace_snapshot(
            7,
            CAPTURED_AT,
            (successful_capture_attempt(release_id, facts),),
        )
        return data, facts, snapshot, project_legacy_marketplace_facts(facts)

    def test_success_uses_decimal_decoder_and_preserves_exact_optional_facts(self):
        response = _Response(
            payload={
                "community": {"want": 0, "have": 4},
                "num_for_sale": 2,
                "lowest_price": {
                    "value": Decimal("12.3400"),
                    "currency": "GBP",
                },
                "styles": [],
                "genres": ["Electronic", "Ambient"],
                "uri": "/release/7",
            }
        )

        result = self.client(response).get_release(7)

        self.assertEqual(response.json_calls, [{"parse_float": Decimal}])
        self.assertEqual(result["wants"], 0)
        self.assertEqual(result["haves"], 4)
        self.assertEqual(result["copies_for_sale"], 2)
        self.assertEqual(result["lowest_price"], Decimal("12.3400"))
        self.assertIs(type(result["lowest_price"]), Decimal)
        self.assertEqual(result["currency"], "GBP")
        self.assertEqual(result["styles"], "")
        self.assertEqual(result["genres"], "Electronic, Ambient")
        self.assertEqual(result["discogs_uri"], "/release/7")

    def test_integer_price_is_exact_and_missing_fields_remain_none(self):
        integer = _Response(payload={"lowest_price": {"value": 12}})
        absent = _Response(payload={})

        integer_result = self.client(integer).get_release(1)
        absent_result = self.client(absent).get_release(1)

        self.assertIs(type(integer_result["lowest_price"]), int)
        self.assertEqual(integer_result["lowest_price"], 12)
        for key in (
            "wants",
            "haves",
            "copies_for_sale",
            "lowest_price",
            "currency",
            "styles",
            "genres",
            "discogs_uri",
        ):
            self.assertIsNone(absent_result[key], key)

    def test_nested_integer_price_reaches_canonical_money_exactly(self):
        response = _Response(
            payload={
                "community": {"want": 1},
                "num_for_sale": 1,
                "lowest_price": {"value": 12, "currency": "GBP"},
            }
        )

        data, _, snapshot, legacy = self.canonical(response)

        self.assertIs(type(data["lowest_price"]), int)
        money = snapshot.release_observations[0].lowest_price
        self.assertEqual(money.amount, Decimal(12))
        self.assertIs(type(money.amount), Decimal)
        self.assertEqual(legacy["lowest_price"], 12.0)

    def test_scalar_integer_price_uses_only_explicit_top_level_currency(self):
        response = _Response(
            payload={
                "community": {"want": 1},
                "num_for_sale": 1,
                "lowest_price": 12,
                "currency": "GBP",
            }
        )

        data, _, snapshot, _ = self.canonical(response)

        self.assertEqual(data["currency"], "GBP")
        self.assertEqual(
            snapshot.release_observations[0].lowest_price.amount,
            Decimal(12),
        )

    def test_scalar_fractional_price_remains_exact_through_mapper(self):
        response = _Response(
            payload={
                "community": {"want": 1},
                "num_for_sale": 1,
                "lowest_price": Decimal("12.3400"),
                "currency": "GBP",
            }
        )
        client = self.client(response)

        data = client.get_release(1)
        facts = normalize_provider_facts(data)
        snapshot = build_marketplace_snapshot(
            7,
            CAPTURED_AT,
            (successful_capture_attempt(1, facts),),
        )

        self.assertEqual(response.json_calls, [{"parse_float": Decimal}])
        self.assertIs(type(data["lowest_price"]), Decimal)
        self.assertEqual(
            snapshot.release_observations[0].lowest_price.amount,
            Decimal("12.3400"),
        )

    def test_boolean_price_is_unusable_and_never_integer_money(self):
        response = _Response(
            payload={
                "community": {"want": 1},
                "num_for_sale": 1,
                "lowest_price": {"value": True, "currency": "GBP"},
            }
        )

        data, _, snapshot, legacy = self.canonical(response)

        self.assertIs(type(data["lowest_price"]), object)
        observation = snapshot.release_observations[0]
        self.assertIs(observation.status, MarketplaceDataStatus.PARTIAL)
        self.assertIsNone(observation.lowest_price)
        diagnostic = observation.diagnostics[0]
        self.assertEqual(diagnostic.code, "marketplace_money_unusable")
        self.assertEqual(diagnostic.details["reason"], "invalid_amount")
        self.assertNotIn("True", repr(diagnostic))
        self.assertEqual(legacy["lowest_price"], 0.0)

    def test_missing_currency_is_not_invented_and_zero_differs_from_missing(self):
        supplied_zero = _Response(
            payload={
                "community": {"want": 0, "have": 0},
                "num_for_sale": 0,
                "lowest_price": {"value": 0},
            }
        )

        result = self.client(supplied_zero).get_release(1)

        self.assertEqual(result["wants"], 0)
        self.assertEqual(result["haves"], 0)
        self.assertEqual(result["copies_for_sale"], 0)
        self.assertEqual(result["lowest_price"], 0)
        self.assertIsNone(result["currency"])

    def test_malformed_price_is_not_coerced_to_float_or_decimal(self):
        response = _Response(
            payload={
                "lowest_price": {
                    "value": 1.25,
                    "currency": "GBP",
                }
            }
        )

        result = self.client(response).get_release(1)

        self.assertIs(type(result["lowest_price"]), object)
        self.assertNotIsInstance(result["lowest_price"], (float, Decimal))

    def test_not_found_and_other_http_errors_preserve_existing_behavior(self):
        self.assertIsNone(self.client(_Response(404)).get_release(1))
        response = _Response(400, text="sensitive provider response")
        with self.assertRaisesRegex(RuntimeError, "Discogs API 400"):
            self.client(response).get_release(1)

    def test_uri_preserves_strings_and_rejects_non_string_without_raw_value(self):
        for uri in (None, "", "/release/1"):
            with self.subTest(uri=uri):
                result = self.client(_Response(payload={"uri": uri})).get_release(1)
                self.assertEqual(result["discogs_uri"], uri)

        malformed = {"private": "raw-value"}
        with self.assertRaises(TypeError) as caught:
            self.client(_Response(payload={"uri": malformed})).get_release(1)
        self.assertEqual(str(caught.exception), "Discogs uri must be a string or null.")
        self.assertNotIn("raw-value", str(caught.exception))

    def test_malformed_styles_and_genres_fail_safely(self):
        for field, value in (
            ("styles", {"raw": "style"}),
            ("genres", [object()]),
        ):
            with self.subTest(field=field):
                with self.assertRaises(TypeError) as caught:
                    self.client(_Response(payload={field: value})).get_release(1)
                self.assertEqual(
                    str(caught.exception),
                    f"Discogs {field} must be a list of strings or null.",
                )
                self.assertNotIn("raw", str(caught.exception))

    def test_retryable_responses_wait_and_eventually_succeed(self):
        responses = [
            _Response(429),
            _Response(503),
            _Response(payload={"community": {"want": 0}, "num_for_sale": 0}),
        ]
        responses[0].headers["Retry-After"] = "2.5"
        client = self.client(responses)

        with patch("dip.data_sources.discogs.client.time.sleep") as wait:
            result = client.get_release(1)

        self.assertEqual(result["wants"], 0)
        self.assertEqual(len(client.session.calls), 3)
        self.assertEqual(
            [call.args[0] for call in wait.call_args_list],
            [2.5, 4],
        )

    def test_retry_exhaustion_uses_existing_attempt_count_and_error(self):
        client = self.client([_Response(503) for _ in range(5)])

        with (
            patch("dip.data_sources.discogs.client.time.sleep") as wait,
            self.assertRaisesRegex(
                RuntimeError,
                "Discogs API failed after repeated retries",
            ),
        ):
            client.get_release(1)

        self.assertEqual(len(client.session.calls), 5)
        self.assertEqual(
            [call.args[0] for call in wait.call_args_list],
            [2, 4, 8, 16, 32],
        )


if __name__ == "__main__":
    unittest.main()
