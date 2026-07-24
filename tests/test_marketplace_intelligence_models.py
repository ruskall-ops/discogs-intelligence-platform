from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import unittest

from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceDiagnosticSeverity,
    MarketplaceDomainError,
    MarketplaceExecutionContext,
    MarketplaceListingObservation,
    MarketplaceModuleResult,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)


CAPTURED_AT = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)


class MarketplaceMoneyTestCase(unittest.TestCase):
    def test_money_preserves_exact_decimal_currency_and_zero(self) -> None:
        value = MarketplaceMoney(Decimal("0.000"), "GBP")

        self.assertEqual(value.amount, Decimal("0.000"))
        self.assertEqual(value.currency, "GBP")
        self.assertEqual(value, MarketplaceMoney(Decimal("0.000"), "GBP"))
        with self.assertRaises(FrozenInstanceError):
            value.currency = "USD"  # type: ignore[misc]

    def test_money_rejects_float_negative_nonfinite_and_malformed_currency(self) -> None:
        for amount in (1.0, 1, "1.00"):
            with self.subTest(amount=amount):
                with self.assertRaises(TypeError):
                    MarketplaceMoney(amount, "GBP")  # type: ignore[arg-type]
        for amount in (Decimal("-0.01"), Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(amount=amount):
                with self.assertRaises(MarketplaceDomainError):
                    MarketplaceMoney(amount, "GBP")
        for currency in ("gbp", "GB", "GB12", " G", "€UR"):
            with self.subTest(currency=currency):
                with self.assertRaises(MarketplaceDomainError):
                    MarketplaceMoney(Decimal("1.00"), currency)


class MarketplaceObservationModelTestCase(unittest.TestCase):
    def test_listing_is_immutable_and_requires_aware_time_and_one_currency(self) -> None:
        listing = listing_observation("listing-1", 1)

        with self.assertRaises(FrozenInstanceError):
            listing.condition = "Poor"  # type: ignore[misc]
        with self.assertRaises(MarketplaceDomainError):
            MarketplaceListingObservation(
                "listing-1",
                1,
                datetime(2026, 7, 21, 12),
                money("10"),
            )
        with self.assertRaisesRegex(MarketplaceDomainError, "same currency"):
            MarketplaceListingObservation(
                "listing-1",
                1,
                CAPTURED_AT,
                money("10", "GBP"),
                shipping=money("2", "USD"),
            )

    def test_release_accepts_supplied_facts_without_calculating_aggregates(self) -> None:
        release = release_observation(1)

        self.assertEqual(release.lowest_price, money("10.00"))
        self.assertEqual(release.median_price, money("12.50"))
        self.assertEqual(release.highest_price, money("20.00"))
        self.assertEqual(release.num_for_sale, 2)
        self.assertEqual(release.num_wanted, 20)

    def test_release_supports_partial_empty_unavailable_and_failed_states(self) -> None:
        partial = MarketplaceReleaseObservation(
            1,
            CAPTURED_AT,
            MarketplaceDataStatus.PARTIAL,
            num_for_sale=2,
            diagnostics=(diagnostic(),),
        )
        empty = MarketplaceReleaseObservation(
            2,
            CAPTURED_AT,
            MarketplaceDataStatus.EMPTY,
        )
        unavailable = MarketplaceReleaseObservation(
            3,
            CAPTURED_AT,
            MarketplaceDataStatus.UNAVAILABLE,
            diagnostics=(diagnostic("source_unavailable"),),
        )
        failed = MarketplaceReleaseObservation(
            4,
            CAPTURED_AT,
            MarketplaceDataStatus.FAILED,
            diagnostics=(diagnostic("capture_failed"),),
        )

        self.assertIs(partial.status, MarketplaceDataStatus.PARTIAL)
        self.assertIs(empty.status, MarketplaceDataStatus.EMPTY)
        self.assertIs(unavailable.status, MarketplaceDataStatus.UNAVAILABLE)
        self.assertIs(failed.status, MarketplaceDataStatus.FAILED)

    def test_release_rejects_contradictory_statuses_and_malformed_facts(self) -> None:
        cases = (
            lambda: MarketplaceReleaseObservation(
                1, CAPTURED_AT, MarketplaceDataStatus.COMPLETE
            ),
            lambda: MarketplaceReleaseObservation(
                1,
                CAPTURED_AT,
                MarketplaceDataStatus.PARTIAL,
                num_for_sale=1,
            ),
            lambda: MarketplaceReleaseObservation(
                1,
                CAPTURED_AT,
                MarketplaceDataStatus.EMPTY,
                num_for_sale=0,
            ),
            lambda: MarketplaceReleaseObservation(
                1, CAPTURED_AT, MarketplaceDataStatus.FAILED
            ),
            lambda: MarketplaceReleaseObservation(
                1,
                CAPTURED_AT,
                MarketplaceDataStatus.COMPLETE,
                num_for_sale=-1,
            ),
            lambda: MarketplaceReleaseObservation(
                1,
                CAPTURED_AT,
                MarketplaceDataStatus.COMPLETE,
                num_for_sale=True,
            ),
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises((TypeError, MarketplaceDomainError)):
                    case()

    def test_release_rejects_currency_price_and_date_inconsistency(self) -> None:
        with self.assertRaisesRegex(MarketplaceDomainError, "one currency"):
            MarketplaceReleaseObservation(
                1,
                CAPTURED_AT,
                MarketplaceDataStatus.COMPLETE,
                lowest_price=money("10", "GBP"),
                highest_price=money("20", "USD"),
            )
        with self.assertRaisesRegex(MarketplaceDomainError, "must be ordered"):
            MarketplaceReleaseObservation(
                1,
                CAPTURED_AT,
                MarketplaceDataStatus.COMPLETE,
                lowest_price=money("20"),
                highest_price=money("10"),
            )
        with self.assertRaisesRegex(MarketplaceDomainError, "last_sold"):
            MarketplaceReleaseObservation(
                1,
                CAPTURED_AT,
                MarketplaceDataStatus.COMPLETE,
                num_for_sale=1,
                last_sold=date(2026, 7, 22),
            )


class MarketplaceSnapshotModelTestCase(unittest.TestCase):
    def test_snapshot_defensively_copies_and_canonicalises_observations(self) -> None:
        details = {"page": "1"}
        diagnostics = [diagnostic(details=details)]
        releases = [release_observation(2), release_observation(1)]
        listings = [
            listing_observation("listing-2", 2),
            listing_observation("listing-1", 1),
        ]
        snapshot = MarketplaceSnapshot(
            "snapshot-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.COMPLETE,
            releases,
            listings,
            diagnostics,
            "api-v2",
        )

        releases.clear()
        listings.clear()
        diagnostics.clear()
        details["page"] = "changed"

        self.assertEqual(
            tuple(value.release_id for value in snapshot.release_observations),
            (1, 2),
        )
        self.assertEqual(
            tuple(value.listing_id for value in snapshot.listing_observations),
            ("listing-1", "listing-2"),
        )
        self.assertEqual(dict(snapshot.diagnostics[0].details), {"page": "1"})
        with self.assertRaises(TypeError):
            snapshot.diagnostics[0].details["page"] = "changed"
        with self.assertRaises(FrozenInstanceError):
            snapshot.source = "other"  # type: ignore[misc]

    def test_snapshot_supports_empty_partial_unavailable_and_failed_states(self) -> None:
        empty = MarketplaceSnapshot(
            "empty-1", CAPTURED_AT, "discogs", MarketplaceDataStatus.EMPTY
        )
        partial = MarketplaceSnapshot(
            "partial-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.PARTIAL,
            (release_observation(1, status=MarketplaceDataStatus.PARTIAL),),
            diagnostics=(diagnostic(),),
        )
        unavailable = MarketplaceSnapshot(
            "unavailable-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.UNAVAILABLE,
            diagnostics=(diagnostic("source_unavailable"),),
        )
        failed = MarketplaceSnapshot(
            "failed-1",
            CAPTURED_AT,
            "discogs",
            MarketplaceDataStatus.FAILED,
            diagnostics=(diagnostic("capture_failed"),),
        )

        self.assertIs(empty.status, MarketplaceDataStatus.EMPTY)
        self.assertIs(partial.status, MarketplaceDataStatus.PARTIAL)
        self.assertIs(unavailable.status, MarketplaceDataStatus.UNAVAILABLE)
        self.assertIs(failed.status, MarketplaceDataStatus.FAILED)

    def test_snapshot_rejects_duplicate_observations_and_unknown_release_references(self) -> None:
        release = release_observation(1)
        listing = listing_observation("listing-1", 1)
        for releases, listings in (
            ((release, release), ()),
            ((release,), (listing, listing)),
            ((release,), (listing_observation("listing-2", 2),)),
        ):
            with self.subTest(releases=releases, listings=listings):
                with self.assertRaises(MarketplaceDomainError):
                    MarketplaceSnapshot(
                        "snapshot-1",
                        CAPTURED_AT,
                        "discogs",
                        MarketplaceDataStatus.COMPLETE,
                        releases,
                        listings,
                    )

    def test_snapshot_rejects_contradictory_state_and_future_observation(self) -> None:
        release = release_observation(1)
        cases = (
            lambda: MarketplaceSnapshot(
                "snapshot-1",
                CAPTURED_AT,
                "discogs",
                MarketplaceDataStatus.EMPTY,
                (release,),
            ),
            lambda: MarketplaceSnapshot(
                "snapshot-1",
                CAPTURED_AT,
                "discogs",
                MarketplaceDataStatus.PARTIAL,
                (release,),
            ),
            lambda: MarketplaceSnapshot(
                "snapshot-1",
                CAPTURED_AT,
                "discogs",
                MarketplaceDataStatus.COMPLETE,
                (
                    MarketplaceReleaseObservation(
                        1,
                        CAPTURED_AT + timedelta(seconds=1),
                        MarketplaceDataStatus.COMPLETE,
                        num_for_sale=1,
                    ),
                ),
            ),
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(MarketplaceDomainError):
                    case()


class MarketplaceModuleResultModelTestCase(unittest.TestCase):
    def test_execution_context_and_standard_result_are_immutable(self) -> None:
        snapshot_ids = ["snapshot-1", "snapshot-2"]
        nested = {"values": [Decimal("1.20"), money("2.30")]}
        result = IntelligenceResult(
            module_id="marketplace_example",
            module_version="1.0",
            status=IntelligenceStatus.COMPLETED,
            summary="Marketplace example completed.",
            insights=("Observed supplied marketplace facts.",),
            metrics=nested,
            evidence=("Two snapshots supplied.",),
        )
        wrapped = MarketplaceModuleResult(
            MarketplaceExecutionContext("execution-1", snapshot_ids, CAPTURED_AT),
            result,
        )

        snapshot_ids.append("snapshot-3")
        nested["values"].append(Decimal("9.99"))

        self.assertEqual(wrapped.context.snapshot_ids, ("snapshot-1", "snapshot-2"))
        self.assertEqual(
            wrapped.result.metrics["values"],
            (Decimal("1.20"), money("2.30")),
        )
        with self.assertRaises(TypeError):
            wrapped.result.metrics["new"] = True
        with self.assertRaises(FrozenInstanceError):
            wrapped.context.executed_at = CAPTURED_AT  # type: ignore[misc]

    def test_context_rejects_naive_time_duplicate_or_empty_snapshot_ids(self) -> None:
        for snapshot_ids, executed_at in (
            ((), CAPTURED_AT),
            (("snapshot-1", "snapshot-1"), CAPTURED_AT),
            (("snapshot-1",), datetime(2026, 7, 21, 12)),
        ):
            with self.subTest(snapshot_ids=snapshot_ids, executed_at=executed_at):
                with self.assertRaises(MarketplaceDomainError):
                    MarketplaceExecutionContext(
                        "execution-1",
                        snapshot_ids,
                        executed_at,
                    )

    def test_failed_result_rejects_successful_outputs_and_requires_diagnostics(self) -> None:
        context = MarketplaceExecutionContext(
            "execution-1", ("snapshot-1",), CAPTURED_AT
        )
        for result in (
            IntelligenceResult(
                "marketplace_example",
                IntelligenceStatus.FAILED,
                "Failed.",
            ),
            IntelligenceResult(
                "marketplace_example",
                IntelligenceStatus.FAILED,
                "Failed.",
                metrics={"count": 1},
                diagnostics=("Failure.",),
            ),
        ):
            with self.subTest(result=result):
                with self.assertRaises(MarketplaceDomainError):
                    MarketplaceModuleResult(context, result)

    def test_result_rejects_unsupported_mutable_nonfinite_and_naive_metrics(self) -> None:
        context = MarketplaceExecutionContext(
            "execution-1", ("snapshot-1",), CAPTURED_AT
        )
        for value in ({1, 2}, float("nan"), Decimal("Infinity"), datetime(2026, 7, 21)):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, MarketplaceDomainError)):
                    MarketplaceModuleResult(
                        context,
                        IntelligenceResult(
                            "marketplace_example",
                            IntelligenceStatus.COMPLETED,
                            "Completed.",
                            metrics={"value": value},
                        ),
                    )


def money(amount: str, currency: str = "GBP") -> MarketplaceMoney:
    return MarketplaceMoney(Decimal(amount), currency)


def diagnostic(
    code: str = "partial_response",
    *,
    details=None,
) -> MarketplaceDiagnostic:
    return MarketplaceDiagnostic(
        code,
        "The source response was incomplete.",
        MarketplaceDiagnosticSeverity.WARNING,
        {} if details is None else details,
    )


def release_observation(
    release_id: int,
    *,
    status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
) -> MarketplaceReleaseObservation:
    if status is MarketplaceDataStatus.PARTIAL:
        return MarketplaceReleaseObservation(
            release_id,
            CAPTURED_AT,
            status,
            lowest_price=money("10.00"),
            num_for_sale=2,
            diagnostics=(diagnostic(),),
        )
    return MarketplaceReleaseObservation(
        release_id,
        CAPTURED_AT,
        status,
        lowest_price=money("10.00"),
        median_price=money("12.50"),
        highest_price=money("20.00"),
        num_for_sale=2,
        num_wanted=20,
        last_sold=date(2026, 7, 20),
    )


def listing_observation(
    listing_id: str,
    release_id: int,
) -> MarketplaceListingObservation:
    return MarketplaceListingObservation(
        listing_id,
        release_id,
        CAPTURED_AT,
        money("10.00"),
        shipping=money("2.00"),
        condition="Very Good Plus",
        seller_region="GB",
    )


if __name__ == "__main__":
    unittest.main()
