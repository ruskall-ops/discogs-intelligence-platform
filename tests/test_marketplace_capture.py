from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
import unittest

from dip.app import marketplace_capture as capture_module
from dip.app.marketplace_capture import (
    MarketplaceCaptureAttempt,
    MarketplaceCaptureAttemptStatus,
    ProviderFactState,
    build_marketplace_snapshot,
    failed_capture_attempt,
    normalize_provider_facts,
    project_legacy_marketplace_facts,
    successful_capture_attempt,
    unavailable_capture_attempt,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceDiagnosticSeverity,
)


CAPTURED_AT = datetime(2026, 7, 26, 10, 20, 30, 456789, tzinfo=timezone.utc)


def _facts(**overrides):
    values = {
        "wants": 10,
        "haves": 20,
        "copies_for_sale": 2,
        "lowest_price": Decimal("12.3400"),
        "currency": "GBP",
        "styles": "Ambient",
        "genres": "Electronic",
        "discogs_uri": "/release/1",
    }
    values.update(overrides)
    return normalize_provider_facts(values)


def _snapshot(*attempts):
    return build_marketplace_snapshot(41, CAPTURED_AT, attempts)


class MarketplaceCaptureMappingTestCase(unittest.TestCase):
    def test_normalization_is_immutable_exact_and_rejects_boolean_counts(self):
        facts = normalize_provider_facts(
            {
                "wants": 0,
                "haves": True,
                "copies_for_sale": None,
                "lowest_price": Decimal("10.2300"),
                "currency": "GBP",
            }
        )

        self.assertIs(facts.wants_state, ProviderFactState.VALID)
        self.assertEqual(facts.wants, 0)
        self.assertIsNone(facts.haves)
        self.assertIs(facts.supply_state, ProviderFactState.MISSING)
        self.assertEqual(facts.lowest_price, Decimal("10.2300"))
        with self.assertRaises(FrozenInstanceError):
            facts.wants = 2  # type: ignore[misc]

    def test_legacy_projection_contains_defaults_and_converts_money_only_there(self):
        exact = project_legacy_marketplace_facts(_facts())
        missing = project_legacy_marketplace_facts(
            normalize_provider_facts({})
        )
        invalid_currency = project_legacy_marketplace_facts(
            _facts(currency="gbp")
        )

        self.assertIs(type(exact["lowest_price"]), float)
        self.assertEqual(exact["lowest_price"], 12.34)
        self.assertEqual(
            missing,
            {
                "wants": 0,
                "haves": 0,
                "copies_for_sale": 0,
                "lowest_price": 0.0,
                "currency": "",
                "styles": "",
                "genres": "",
                "discogs_uri": "",
            },
        )
        self.assertEqual(invalid_currency["lowest_price"], 0.0)
        self.assertEqual(invalid_currency["currency"], "gbp")

    def test_complete_release_preserves_exact_money_and_requested_identity(self):
        snapshot = _snapshot(successful_capture_attempt(9, _facts()))

        observation = snapshot.release_observations[0]
        self.assertIs(snapshot.status, MarketplaceDataStatus.COMPLETE)
        self.assertEqual(observation.release_id, 9)
        self.assertIs(observation.status, MarketplaceDataStatus.COMPLETE)
        self.assertEqual(observation.lowest_price.amount, Decimal("12.3400"))
        self.assertEqual(observation.num_wanted, 10)
        self.assertEqual(observation.num_for_sale, 2)
        self.assertEqual(observation.observed_at, CAPTURED_AT)
        self.assertEqual(snapshot.diagnostics, ())

    def test_zero_supply_without_price_is_complete_and_wanted_zero_is_valid(self):
        snapshot = _snapshot(
            successful_capture_attempt(
                1,
                _facts(
                    wants=0,
                    copies_for_sale=0,
                    lowest_price=None,
                    currency=None,
                ),
            )
        )

        observation = snapshot.release_observations[0]
        self.assertIs(observation.status, MarketplaceDataStatus.COMPLETE)
        self.assertEqual(observation.num_wanted, 0)
        self.assertEqual(observation.num_for_sale, 0)
        self.assertIsNone(observation.lowest_price)

    def test_missing_expected_facts_are_partial_in_field_order(self):
        for overrides, expected_field in (
            ({"wants": None}, "num_wanted"),
            ({"copies_for_sale": None}, "num_for_sale"),
            ({"lowest_price": None}, "lowest_price"),
        ):
            with self.subTest(overrides=overrides):
                observation = _snapshot(
                    successful_capture_attempt(1, _facts(**overrides))
                ).release_observations[0]
                self.assertIs(observation.status, MarketplaceDataStatus.PARTIAL)
                self.assertEqual(
                    tuple(value.details["field"] for value in observation.diagnostics),
                    (expected_field,),
                )
                self.assertTrue(
                    all(
                        value.code == "marketplace_fact_missing"
                        for value in observation.diagnostics
                    )
                )

        ordered = _snapshot(
            successful_capture_attempt(
                1,
                _facts(wants=None, copies_for_sale=None),
            )
        ).release_observations[0]
        self.assertEqual(
            tuple(value.details["field"] for value in ordered.diagnostics),
            ("num_wanted", "num_for_sale"),
        )

    def test_unusable_money_is_partial_with_limited_stable_reasons(self):
        cases = (
            ({"currency": None}, "missing_currency"),
            ({"currency": "gbp"}, "invalid_currency"),
            ({"lowest_price": Decimal("-1")}, "invalid_amount"),
            ({"lowest_price": Decimal("NaN")}, "invalid_amount"),
            ({"lowest_price": object()}, "invalid_amount"),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason, overrides=overrides):
                observation = _snapshot(
                    successful_capture_attempt(1, _facts(**overrides))
                ).release_observations[0]
                self.assertIs(observation.status, MarketplaceDataStatus.PARTIAL)
                self.assertIsNone(observation.lowest_price)
                diagnostic = observation.diagnostics[-1]
                self.assertEqual(diagnostic.code, "marketplace_money_unusable")
                self.assertEqual(diagnostic.details["reason"], reason)
                self.assertNotIn(repr(overrides.get("lowest_price")), diagnostic.message)

    def test_supplied_unusable_money_with_zero_supply_is_partial(self):
        observation = _snapshot(
            successful_capture_attempt(
                1,
                _facts(copies_for_sale=0, lowest_price=Decimal("1"), currency=None),
            )
        ).release_observations[0]

        self.assertIs(observation.status, MarketplaceDataStatus.PARTIAL)
        self.assertEqual(
            observation.diagnostics[0].details["reason"],
            "missing_currency",
        )

    def test_no_usable_facts_creates_empty_release_and_partial_snapshot(self):
        snapshot = _snapshot(
            successful_capture_attempt(
                1,
                normalize_provider_facts({}),
            )
        )

        self.assertIs(snapshot.status, MarketplaceDataStatus.PARTIAL)
        self.assertIs(
            snapshot.release_observations[0].status,
            MarketplaceDataStatus.EMPTY,
        )
        self.assertEqual(
            tuple(value.details["field"] for value in snapshot.diagnostics),
            ("num_wanted", "num_for_sale"),
        )

    def test_mixed_provider_outcomes_are_partial_and_safe(self):
        snapshot = _snapshot(
            unavailable_capture_attempt(3),
            failed_capture_attempt(1),
            successful_capture_attempt(2, _facts()),
        )

        self.assertIs(snapshot.status, MarketplaceDataStatus.PARTIAL)
        self.assertEqual(
            tuple(value.release_id for value in snapshot.release_observations),
            (1, 2, 3),
        )
        self.assertEqual(
            tuple(value.code for value in snapshot.diagnostics),
            (
                "provider_observation_unavailable",
                "provider_request_failed",
            ),
        )
        self.assertEqual(
            tuple(value.severity for value in snapshot.diagnostics),
            (
                MarketplaceDiagnosticSeverity.WARNING,
                MarketplaceDiagnosticSeverity.ERROR,
            ),
        )
        self.assertNotIn("token", repr(snapshot))
        self.assertNotIn("exception", repr(snapshot))

    def test_empty_success_plus_failure_is_partial_with_attempt_order_diagnostics(self):
        snapshot = _snapshot(
            successful_capture_attempt(2, normalize_provider_facts({})),
            failed_capture_attempt(1),
        )

        self.assertIs(snapshot.status, MarketplaceDataStatus.PARTIAL)
        self.assertEqual(
            tuple(
                (value.release_id, value.status)
                for value in snapshot.release_observations
            ),
            (
                (1, MarketplaceDataStatus.FAILED),
                (2, MarketplaceDataStatus.EMPTY),
            ),
        )
        self.assertEqual(
            tuple(
                (
                    value.code,
                    value.details.get("release_id"),
                    value.details.get("field"),
                )
                for value in snapshot.diagnostics
            ),
            (
                ("marketplace_fact_missing", "2", "num_wanted"),
                ("marketplace_fact_missing", "2", "num_for_sale"),
                ("provider_request_failed", "1", None),
            ),
        )

    def test_multiple_successful_empty_observations_make_partial_aggregate(self):
        snapshot = _snapshot(
            successful_capture_attempt(3, normalize_provider_facts({})),
            successful_capture_attempt(1, normalize_provider_facts({})),
        )

        self.assertIs(snapshot.status, MarketplaceDataStatus.PARTIAL)
        self.assertEqual(
            tuple(
                (value.release_id, value.status)
                for value in snapshot.release_observations
            ),
            (
                (1, MarketplaceDataStatus.EMPTY),
                (3, MarketplaceDataStatus.EMPTY),
            ),
        )
        self.assertEqual(
            tuple(
                (value.details["release_id"], value.details["field"])
                for value in snapshot.diagnostics
            ),
            (
                ("3", "num_wanted"),
                ("3", "num_for_sale"),
                ("1", "num_wanted"),
                ("1", "num_for_sale"),
            ),
        )

    def test_zero_success_is_failed_without_release_observations(self):
        snapshot = _snapshot(
            failed_capture_attempt(4),
            unavailable_capture_attempt(2),
        )

        self.assertIs(snapshot.status, MarketplaceDataStatus.FAILED)
        self.assertEqual(snapshot.release_observations, ())
        self.assertEqual(
            tuple(value.code for value in snapshot.diagnostics),
            (
                "provider_request_failed",
                "provider_observation_unavailable",
                "marketplace_capture_failed",
            ),
        )
        self.assertEqual(
            dict(snapshot.diagnostics[-1].details),
            {
                "attempted": "2",
                "failed": "2",
                "release_ids": "4,2",
            },
        )

    def test_snapshot_metadata_ordering_and_duplicate_rejection(self):
        snapshot = build_marketplace_snapshot(
            87,
            CAPTURED_AT,
            (
                successful_capture_attempt(8, _facts()),
                successful_capture_attempt(2, _facts()),
            ),
        )

        self.assertEqual(snapshot.snapshot_id, "collector-run-87")
        self.assertEqual(snapshot.captured_at, CAPTURED_AT)
        self.assertEqual(snapshot.source, "discogs")
        self.assertIsNone(snapshot.source_version)
        self.assertEqual(snapshot.listing_observations, ())
        self.assertEqual(
            tuple(value.release_id for value in snapshot.release_observations),
            (2, 8),
        )
        self.assertTrue(
            all(value.observed_at == CAPTURED_AT for value in snapshot.release_observations)
        )
        with self.assertRaisesRegex(ValueError, "duplicates"):
            _snapshot(
                successful_capture_attempt(1, _facts()),
                successful_capture_attempt(1, _facts()),
            )

    def test_attempt_invariants_reject_unsafe_shapes(self):
        with self.assertRaises(TypeError):
            MarketplaceCaptureAttempt(
                1,
                MarketplaceCaptureAttemptStatus.SUCCESS,
            )
        with self.assertRaises(ValueError):
            MarketplaceCaptureAttempt(
                1,
                MarketplaceCaptureAttemptStatus.FAILED,
                _facts(),
            )

    def test_exact_diagnostic_duplicates_preserve_first_occurrence_only(self):
        first = MarketplaceDiagnostic(
            "marketplace_fact_missing",
            "An expected marketplace fact was not supplied.",
            MarketplaceDiagnosticSeverity.WARNING,
            {"release_id": "1", "field": "num_wanted"},
        )
        duplicate = MarketplaceDiagnostic(
            "marketplace_fact_missing",
            "A different fixed rendering does not change diagnostic identity.",
            MarketplaceDiagnosticSeverity.WARNING,
            {"field": "num_wanted", "release_id": "1"},
        )
        other_release = MarketplaceDiagnostic(
            "marketplace_fact_missing",
            "An expected marketplace fact was not supplied.",
            MarketplaceDiagnosticSeverity.WARNING,
            {"release_id": "2", "field": "num_wanted"},
        )

        result = capture_module._deduplicate_diagnostics(
            (first, duplicate, other_release)
        )

        self.assertEqual(result, (first, other_release))


if __name__ == "__main__":
    unittest.main()
