from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceStatus,
    build_v02_intelligence_registry,
)
from dip.marketplace_intelligence import (
    ListingPriceChange,
    ListingPriceChangeKind,
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceDiagnosticSeverity,
    MarketplaceListingObservation,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    PriceChangeDelta,
    PriceChangesComparisonState,
    PriceChangesDomainError,
    PriceChangesModule,
    PriceChangesOutput,
    PriceChangesSnapshotReference,
    PriceChangesSummary,
    ReleasePriceChange,
    ReleasePriceChangeKind,
    ReleasePriceMetric,
)


PREVIOUS_CAPTURED_AT = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
LATEST_CAPTURED_AT = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)


class MarketplaceSnapshotComparisonInputTestCase(unittest.TestCase):
    def test_missing_latest_only_and_equal_capture_time_are_valid_inputs(self) -> None:
        latest = empty_snapshot("latest", LATEST_CAPTURED_AT)
        same_instant = empty_snapshot(
            "same-instant",
            LATEST_CAPTURED_AT.astimezone(timezone(timedelta(hours=2))),
        )

        self.assertEqual(MarketplaceSnapshotComparisonInput(), MarketplaceSnapshotComparisonInput())
        self.assertIs(
            MarketplaceSnapshotComparisonInput(latest_snapshot=latest).latest_snapshot,
            latest,
        )
        comparison = MarketplaceSnapshotComparisonInput(same_instant, latest)
        self.assertIs(comparison.previous_snapshot, same_instant)
        self.assertIs(comparison.latest_snapshot, latest)

    def test_input_rejects_wrong_types_missing_latest_duplicate_id_and_reverse_order(
        self,
    ) -> None:
        previous = empty_snapshot("previous", PREVIOUS_CAPTURED_AT)
        latest = empty_snapshot("latest", LATEST_CAPTURED_AT)
        later_previous = empty_snapshot(
            "later-previous",
            LATEST_CAPTURED_AT + timedelta(seconds=1),
        )
        same_id = empty_snapshot("previous", LATEST_CAPTURED_AT)

        cases = (
            lambda: MarketplaceSnapshotComparisonInput(previous_snapshot="snapshot"),
            lambda: MarketplaceSnapshotComparisonInput(previous_snapshot=previous),
            lambda: MarketplaceSnapshotComparisonInput(previous, same_id),
            lambda: MarketplaceSnapshotComparisonInput(later_previous, latest),
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises((TypeError, PriceChangesDomainError)):
                    case()

    def test_input_is_immutable(self) -> None:
        comparison = MarketplaceSnapshotComparisonInput(
            empty_snapshot("previous", PREVIOUS_CAPTURED_AT),
            empty_snapshot("latest", LATEST_CAPTURED_AT),
        )

        with self.assertRaises(FrozenInstanceError):
            comparison.latest_snapshot = None  # type: ignore[misc]


class ListingPriceComparisonTestCase(unittest.TestCase):
    def test_increase_decrease_and_unchanged_use_exact_signed_price_deltas(self) -> None:
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (
                listing("increased", 1, PREVIOUS_CAPTURED_AT, "10.10"),
                listing("decreased", 2, PREVIOUS_CAPTURED_AT, "10.30"),
                listing("unchanged", 3, PREVIOUS_CAPTURED_AT, "7.00"),
            ),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (
                listing("increased", 1, LATEST_CAPTURED_AT, "10.30"),
                listing("decreased", 2, LATEST_CAPTURED_AT, "10.10"),
                listing("unchanged", 3, LATEST_CAPTURED_AT, "7.00"),
            ),
        )

        result = analyse(previous, latest)
        output = price_output(result)
        by_id = {value.listing_id: value for value in output.listing_changes}

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(output.comparison_state, PriceChangesComparisonState.COMPLETE)
        self.assertEqual(set(by_id), {"increased", "decreased"})
        self.assertIs(
            by_id["increased"].change_kind,
            ListingPriceChangeKind.INCREASED,
        )
        self.assertEqual(by_id["increased"].delta.amount, Decimal("0.20"))
        self.assertEqual(by_id["increased"].delta.currency, "GBP")
        self.assertIs(
            by_id["decreased"].change_kind,
            ListingPriceChangeKind.DECREASED,
        )
        self.assertEqual(by_id["decreased"].delta.amount, Decimal("-0.20"))
        self.assertEqual(output.summary.listing_increased_count, 1)
        self.assertEqual(output.summary.listing_decreased_count, 1)
        self.assertEqual(output.summary.listing_unchanged_count, 1)
        self.assertEqual(output.summary.listing_change_count, 2)
        self.assertEqual(output.summary.detected_change_count, 2)

    def test_exact_delta_supports_finite_values_beyond_default_context_bounds(
        self,
    ) -> None:
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (listing("large", 1, PREVIOUS_CAPTURED_AT, "0"),),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (listing("large", 1, LATEST_CAPTURED_AT, "1E+1000000"),),
        )

        output = price_output(analyse(previous, latest))

        self.assertEqual(
            output.listing_changes[0].delta.amount,
            Decimal("1E+1000000"),
        )

        precision_previous = listing_snapshot(
            "precision-previous",
            PREVIOUS_CAPTURED_AT,
            (
                listing(
                    "precise",
                    1,
                    PREVIOUS_CAPTURED_AT,
                    "123456789012345678901234567890.1234",
                ),
            ),
        )
        precision_latest = listing_snapshot(
            "precision-latest",
            LATEST_CAPTURED_AT,
            (
                listing(
                    "precise",
                    1,
                    LATEST_CAPTURED_AT,
                    "123456789012345678901234567891.1235",
                ),
            ),
        )
        precise_delta = price_output(
            analyse(precision_previous, precision_latest)
        ).listing_changes[0].delta
        self.assertEqual(precise_delta.amount, Decimal("1.0001"))

        scale_previous = listing_snapshot(
            "scale-previous",
            PREVIOUS_CAPTURED_AT,
            (
                listing("from-zero", 1, PREVIOUS_CAPTURED_AT, "0.0000"),
                listing("to-zero", 2, PREVIOUS_CAPTURED_AT, "1.00"),
            ),
        )
        scale_latest = listing_snapshot(
            "scale-latest",
            LATEST_CAPTURED_AT,
            (
                listing("from-zero", 1, LATEST_CAPTURED_AT, "1.00"),
                listing("to-zero", 2, LATEST_CAPTURED_AT, "0.000"),
            ),
        )
        scale_changes = {
            value.listing_id: value
            for value in price_output(
                analyse(scale_previous, scale_latest)
            ).listing_changes
        }
        self.assertEqual(
            scale_changes["from-zero"].delta.amount.as_tuple().exponent,
            -4,
        )
        self.assertEqual(
            scale_changes["to-zero"].delta.amount.as_tuple().exponent,
            -3,
        )

    def test_new_and_no_longer_observed_listings_have_one_sided_evidence(self) -> None:
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (listing("gone", 1, PREVIOUS_CAPTURED_AT, "8.00"),),
            release_ids=(1, 2),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (listing("new", 2, LATEST_CAPTURED_AT, "9.00"),),
            release_ids=(1, 2),
        )

        output = price_output(analyse(previous, latest))
        by_id = {value.listing_id: value for value in output.listing_changes}

        self.assertIs(by_id["new"].change_kind, ListingPriceChangeKind.NEWLY_OBSERVED)
        self.assertIsNone(by_id["new"].previous_price)
        self.assertEqual(by_id["new"].latest_price, money("9.00"))
        self.assertIsNone(by_id["new"].delta)
        self.assertIs(
            by_id["gone"].change_kind,
            ListingPriceChangeKind.NO_LONGER_OBSERVED,
        )
        self.assertEqual(by_id["gone"].previous_price, money("8.00"))
        self.assertIsNone(by_id["gone"].latest_price)
        self.assertIsNone(by_id["gone"].delta)
        self.assertEqual(output.summary.listing_newly_observed_count, 1)
        self.assertEqual(output.summary.listing_no_longer_observed_count, 1)

    def test_currency_mismatch_is_incomparable_without_conversion(self) -> None:
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (listing("listing-1", 1, PREVIOUS_CAPTURED_AT, "10.00", "GBP"),),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (listing("listing-1", 1, LATEST_CAPTURED_AT, "12.00", "USD"),),
        )

        result = analyse(previous, latest)
        output = price_output(result)
        change = output.listing_changes[0]

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(output.comparison_state, PriceChangesComparisonState.PARTIAL)
        self.assertIs(change.change_kind, ListingPriceChangeKind.INCOMPARABLE)
        self.assertIsNone(change.delta)
        self.assertEqual(change.previous_price.currency, "GBP")
        self.assertEqual(change.latest_price.currency, "USD")
        self.assertEqual(output.summary.listing_incomparable_count, 1)
        self.assertTrue(any("different currencies" in value for value in result.diagnostics))

    def test_optional_listing_fields_do_not_change_price_classification(self) -> None:
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (
                listing(
                    "listing-1",
                    1,
                    PREVIOUS_CAPTURED_AT,
                    "10.00",
                    shipping="2.00",
                    condition="Near Mint",
                    seller_region="GB",
                ),
            ),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (
                listing(
                    "listing-1",
                    1,
                    LATEST_CAPTURED_AT,
                    "10.00",
                    shipping="8.00",
                    condition="Poor",
                    seller_region="US",
                ),
            ),
        )

        output = price_output(analyse(previous, latest))

        self.assertEqual(output.listing_changes, ())
        self.assertEqual(output.summary.listing_unchanged_count, 1)
        self.assertEqual(output.summary.detected_change_count, 0)

    def test_listing_order_is_relevant_time_descending_then_stable_identity(self) -> None:
        tie_time = LATEST_CAPTURED_AT - timedelta(hours=2)
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (
                listing("a", 1, PREVIOUS_CAPTURED_AT, "10"),
                listing("b", 1, PREVIOUS_CAPTURED_AT, "10"),
                listing("newest", 2, PREVIOUS_CAPTURED_AT, "10"),
                listing("gone", 4, PREVIOUS_CAPTURED_AT, "10"),
            ),
            release_ids=(1, 2, 3, 4),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (
                listing("b", 1, tie_time, "11"),
                listing("a", 1, tie_time, "11"),
                listing(
                    "newest",
                    2,
                    LATEST_CAPTURED_AT - timedelta(hours=1),
                    "11",
                ),
                listing(
                    "new",
                    3,
                    LATEST_CAPTURED_AT - timedelta(hours=3),
                    "5",
                ),
            ),
            release_ids=(1, 2, 3, 4),
        )

        output = price_output(analyse(previous, latest))

        self.assertEqual(
            tuple(value.listing_id for value in output.listing_changes),
            ("newest", "a", "b", "new", "gone"),
        )


class ReleasePriceComparisonTestCase(unittest.TestCase):
    def test_lowest_and_highest_increase_decrease_and_unchanged_are_accounted(self) -> None:
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(
                release(1, PREVIOUS_CAPTURED_AT, lowest="10.00", highest="20.00"),
                release(2, PREVIOUS_CAPTURED_AT, lowest="5.00", highest="8.00"),
            ),
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            releases=(
                release(1, LATEST_CAPTURED_AT, lowest="12.00", highest="18.00"),
                release(2, LATEST_CAPTURED_AT, lowest="5.00", highest="8.00"),
            ),
        )

        output = price_output(analyse(previous, latest))

        self.assertEqual(
            tuple((value.release_id, value.metric) for value in output.release_changes),
            (
                (1, ReleasePriceMetric.LOWEST_PRICE),
                (1, ReleasePriceMetric.HIGHEST_PRICE),
            ),
        )
        lowest, highest = output.release_changes
        self.assertIs(lowest.change_kind, ReleasePriceChangeKind.INCREASED)
        self.assertEqual(lowest.delta, PriceChangeDelta(Decimal("2.00"), "GBP"))
        self.assertIs(highest.change_kind, ReleasePriceChangeKind.DECREASED)
        self.assertEqual(highest.delta, PriceChangeDelta(Decimal("-2.00"), "GBP"))
        self.assertEqual(output.summary.release_increased_count, 1)
        self.assertEqual(output.summary.release_decreased_count, 1)
        self.assertEqual(output.summary.release_unchanged_count, 2)

    def test_newly_and_no_longer_available_release_metrics_are_one_sided(self) -> None:
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(
                release(1, PREVIOUS_CAPTURED_AT, lowest="10", highest="20"),
                release(2, PREVIOUS_CAPTURED_AT),
            ),
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            releases=(
                release(1, LATEST_CAPTURED_AT),
                release(2, LATEST_CAPTURED_AT, lowest="30", highest="40"),
            ),
        )

        output = price_output(analyse(previous, latest))

        self.assertEqual(
            tuple(
                (value.release_id, value.metric, value.change_kind)
                for value in output.release_changes
            ),
            (
                (1, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.NO_LONGER_AVAILABLE),
                (1, ReleasePriceMetric.HIGHEST_PRICE, ReleasePriceChangeKind.NO_LONGER_AVAILABLE),
                (2, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.NEWLY_AVAILABLE),
                (2, ReleasePriceMetric.HIGHEST_PRICE, ReleasePriceChangeKind.NEWLY_AVAILABLE),
            ),
        )
        self.assertTrue(all(value.delta is None for value in output.release_changes))
        self.assertEqual(output.summary.release_newly_available_count, 2)
        self.assertEqual(output.summary.release_no_longer_available_count, 2)

    def test_release_currency_mismatch_is_incomparable_in_metric_order(self) -> None:
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(
                release(
                    1,
                    PREVIOUS_CAPTURED_AT,
                    lowest="10",
                    highest="20",
                    currency="GBP",
                ),
            ),
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            releases=(
                release(
                    1,
                    LATEST_CAPTURED_AT,
                    lowest="12",
                    highest="22",
                    currency="USD",
                ),
            ),
        )

        result = analyse(previous, latest)
        output = price_output(result)

        self.assertIs(output.comparison_state, PriceChangesComparisonState.PARTIAL)
        self.assertEqual(
            tuple(value.metric for value in output.release_changes),
            (ReleasePriceMetric.LOWEST_PRICE, ReleasePriceMetric.HIGHEST_PRICE),
        )
        self.assertTrue(
            all(
                value.change_kind is ReleasePriceChangeKind.INCOMPARABLE
                and value.delta is None
                for value in output.release_changes
            )
        )
        self.assertEqual(output.summary.release_incomparable_count, 2)
        self.assertEqual(
            sum("uses different currencies" in value for value in result.diagnostics),
            2,
        )

    def test_release_order_is_release_id_then_canonical_metric(self) -> None:
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(
                release(20, PREVIOUS_CAPTURED_AT, lowest="5", highest="9"),
                release(3, PREVIOUS_CAPTURED_AT, lowest="10", highest="20"),
            ),
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            releases=(
                release(20, LATEST_CAPTURED_AT, lowest="6", highest="10"),
                release(3, LATEST_CAPTURED_AT, lowest="11", highest="21"),
            ),
        )

        output = price_output(analyse(previous, latest))

        self.assertEqual(
            tuple((value.release_id, value.metric) for value in output.release_changes),
            (
                (3, ReleasePriceMetric.LOWEST_PRICE),
                (3, ReleasePriceMetric.HIGHEST_PRICE),
                (20, ReleasePriceMetric.LOWEST_PRICE),
                (20, ReleasePriceMetric.HIGHEST_PRICE),
            ),
        )

    def test_listing_prices_do_not_create_release_level_aggregates(self) -> None:
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (listing("listing-1", 1, PREVIOUS_CAPTURED_AT, "100"),),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (
                listing("listing-1", 1, LATEST_CAPTURED_AT, "50"),
                listing("listing-2", 1, LATEST_CAPTURED_AT, "10"),
            ),
        )

        output = price_output(analyse(previous, latest))

        self.assertEqual(output.release_changes, ())
        self.assertEqual(output.summary.release_change_count, 0)
        self.assertEqual(output.summary.release_unchanged_count, 0)
        self.assertEqual(output.summary.listing_decreased_count, 1)
        self.assertEqual(output.summary.listing_newly_observed_count, 1)


class PriceChangesModuleResultTestCase(unittest.TestCase):
    def test_no_snapshot_and_one_snapshot_are_typed_insufficient_history(self) -> None:
        latest = empty_snapshot("latest", LATEST_CAPTURED_AT)
        cases = (
            (IntelligenceContext(), None),
            (
                IntelligenceContext(
                    marketplace_comparison=MarketplaceSnapshotComparisonInput()
                ),
                None,
            ),
            (
                IntelligenceContext(
                    marketplace_comparison=MarketplaceSnapshotComparisonInput(
                        latest_snapshot=latest
                    )
                ),
                latest,
            ),
        )

        for context, expected_latest in cases:
            with self.subTest(context=context):
                result = PriceChangesModule().analyse(context)
                output = price_output(result)

                self.assertIs(result.status, IntelligenceStatus.SKIPPED)
                self.assertIs(
                    output.comparison_state,
                    PriceChangesComparisonState.INSUFFICIENT_HISTORY,
                )
                self.assertIsNone(output.previous_snapshot)
                self.assertEqual(
                    None if output.latest_snapshot is None else output.latest_snapshot.snapshot_id,
                    None if expected_latest is None else expected_latest.snapshot_id,
                )
                self.assertEqual(output.listing_changes, ())
                self.assertEqual(output.release_changes, ())

    def test_unavailable_and_failed_snapshot_statuses_map_distinctly(self) -> None:
        previous = empty_snapshot("previous", PREVIOUS_CAPTURED_AT)
        unavailable = state_snapshot(
            "unavailable",
            LATEST_CAPTURED_AT,
            MarketplaceDataStatus.UNAVAILABLE,
        )
        failed = state_snapshot(
            "failed",
            LATEST_CAPTURED_AT,
            MarketplaceDataStatus.FAILED,
        )

        unavailable_result = analyse(previous, unavailable)
        failed_result = analyse(previous, failed)

        self.assertIs(unavailable_result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(
            price_output(unavailable_result).comparison_state,
            PriceChangesComparisonState.INSUFFICIENT_DATA,
        )
        self.assertIs(failed_result.status, IntelligenceStatus.FAILED)
        self.assertIs(
            price_output(failed_result).comparison_state,
            PriceChangesComparisonState.FAILED,
        )
        self.assertTrue(unavailable_result.diagnostics)
        self.assertTrue(failed_result.diagnostics)

    def test_equal_capture_instants_are_skipped_without_arbitrary_ordering(self) -> None:
        previous = empty_snapshot("previous", LATEST_CAPTURED_AT)
        latest = empty_snapshot(
            "latest",
            LATEST_CAPTURED_AT.astimezone(timezone(timedelta(hours=-4))),
        )

        result = analyse(previous, latest)

        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(
            price_output(result).comparison_state,
            PriceChangesComparisonState.INSUFFICIENT_DATA,
        )
        self.assertTrue(any("Equal capture times" in value for value in result.diagnostics))

    def test_source_mismatch_is_skipped_and_retains_both_provenance_references(self) -> None:
        previous = empty_snapshot("previous", PREVIOUS_CAPTURED_AT, source="discogs")
        latest = empty_snapshot("latest", LATEST_CAPTURED_AT, source="other_source")

        result = analyse(previous, latest)
        output = price_output(result)

        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(output.comparison_state, PriceChangesComparisonState.INSUFFICIENT_DATA)
        self.assertIsNone(output.source)
        self.assertEqual(output.previous_snapshot.source, "discogs")
        self.assertEqual(output.latest_snapshot.source, "other_source")
        self.assertTrue(any("sources differ" in value for value in result.diagnostics))

    def test_two_empty_snapshots_complete_with_no_invented_changes(self) -> None:
        result = analyse(
            empty_snapshot("previous", PREVIOUS_CAPTURED_AT),
            empty_snapshot("latest", LATEST_CAPTURED_AT),
        )
        output = price_output(result)

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(output.comparison_state, PriceChangesComparisonState.COMPLETE)
        self.assertEqual(output.summary, PriceChangesSummary())
        self.assertEqual(output.listing_changes, ())
        self.assertEqual(output.release_changes, ())
        self.assertEqual(result.evidence, ())
        self.assertIn("No listing or supplied release-price changes", result.summary)

    def test_partial_snapshot_and_version_change_degrade_but_still_complete(self) -> None:
        source_diagnostic = diagnostic("partial_response", details={"page": "2"})
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(release(1, PREVIOUS_CAPTURED_AT, lowest="10"),),
            source_version="api-v1",
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            status=MarketplaceDataStatus.PARTIAL,
            releases=(release(1, LATEST_CAPTURED_AT, lowest="10"),),
            diagnostics=(source_diagnostic,),
            source_version="api-v2",
        )

        result = analyse(previous, latest)
        output = price_output(result)

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(output.comparison_state, PriceChangesComparisonState.PARTIAL)
        self.assertEqual(output.diagnostics, (source_diagnostic,))
        self.assertTrue(any("latest snapshot latest" in value for value in result.diagnostics))
        self.assertTrue(any("source versions differ" in value for value in result.diagnostics))

    def test_source_version_change_alone_is_diagnostic_not_partial(self) -> None:
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(release(1, PREVIOUS_CAPTURED_AT, lowest="10"),),
            source_version="api-v1",
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            releases=(release(1, LATEST_CAPTURED_AT, lowest="11"),),
            source_version="api-v2",
        )

        result = analyse(previous, latest)

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertIs(
            price_output(result).comparison_state,
            PriceChangesComparisonState.COMPLETE,
        )
        self.assertTrue(
            any("source versions differ" in value for value in result.diagnostics)
        )

    def test_nonempty_snapshots_without_supported_prices_are_insufficient_data(
        self,
    ) -> None:
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(release(1, PREVIOUS_CAPTURED_AT),),
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            releases=(release(1, LATEST_CAPTURED_AT),),
        )

        result = analyse(previous, latest)
        output = price_output(result)

        self.assertIs(result.status, IntelligenceStatus.SKIPPED)
        self.assertIs(
            output.comparison_state,
            PriceChangesComparisonState.INSUFFICIENT_DATA,
        )
        self.assertEqual(output.summary.assessed_price_count, 0)
        self.assertEqual(output.listing_changes, ())
        self.assertEqual(output.release_changes, ())
        self.assertIn("no supported price evidence", result.summary.lower())
        self.assertTrue(
            any("lowest/highest price evidence" in value for value in result.diagnostics)
        )

    def test_release_level_diagnostics_are_preserved_with_snapshot_provenance(self) -> None:
        release_diagnostic = diagnostic(
            "release_warning",
            details={"field": "lowest_price"},
        )
        previous = snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            releases=(
                release(
                    1,
                    PREVIOUS_CAPTURED_AT,
                    lowest="10",
                    diagnostics=(release_diagnostic,),
                ),
            ),
        )
        latest = snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            releases=(release(1, LATEST_CAPTURED_AT, lowest="10"),),
        )

        result = analyse(previous, latest)
        output = price_output(result)

        self.assertEqual(output.diagnostics, (release_diagnostic,))
        self.assertTrue(
            any(
                value.startswith("previous snapshot previous, release 1:")
                and "field=lowest_price" in value
                for value in result.diagnostics
            )
        )

    def test_structured_diagnostics_and_deterministic_details_are_preserved(self) -> None:
        previous_diagnostic = diagnostic(
            "previous_gap",
            details={"z": "last", "a": "first"},
        )
        latest_diagnostic = diagnostic(
            "latest_note",
            severity=MarketplaceDiagnosticSeverity.INFO,
        )
        previous = listing_snapshot(
            "previous",
            PREVIOUS_CAPTURED_AT,
            (listing("listing-1", 1, PREVIOUS_CAPTURED_AT, "10", "GBP"),),
            diagnostics=(previous_diagnostic,),
        )
        latest = listing_snapshot(
            "latest",
            LATEST_CAPTURED_AT,
            (listing("listing-1", 1, LATEST_CAPTURED_AT, "12", "USD"),),
            diagnostics=(latest_diagnostic,),
        )

        result = analyse(previous, latest)
        output = price_output(result)

        self.assertEqual(output.diagnostics, (previous_diagnostic, latest_diagnostic))
        self.assertTrue(result.diagnostics[0].startswith("previous snapshot previous:"))
        self.assertIn("; a=first; z=last", result.diagnostics[0])
        self.assertTrue(result.diagnostics[1].startswith("latest snapshot latest:"))
        self.assertTrue(any("Listing listing-1" in value for value in result.diagnostics))

    def test_explicit_one_module_engine_runs_and_default_registry_is_unchanged(self) -> None:
        registry = build_v02_intelligence_registry()
        engine = IntelligenceEngine((PriceChangesModule(),))
        context = IntelligenceContext(
            marketplace_comparison=MarketplaceSnapshotComparisonInput(
                empty_snapshot("previous", PREVIOUS_CAPTURED_AT),
                empty_snapshot("latest", LATEST_CAPTURED_AT),
            )
        )

        execution = engine.execute(context)

        self.assertEqual(
            registry.module_ids,
            ("collection_health", "hidden_gems", "historical_intelligence"),
        )
        self.assertEqual(execution.module_count, 1)
        self.assertEqual(execution.results[0].module_id, "price_changes")
        self.assertEqual(execution.results[0].module_version, "1.0")
        self.assertIs(execution.results[0].status, IntelligenceStatus.COMPLETED)


class PriceChangesOutputInvariantTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous = reference("previous", PREVIOUS_CAPTURED_AT)
        self.latest = reference("latest", LATEST_CAPTURED_AT)

    def test_delta_summary_and_snapshot_reference_validate_public_values(self) -> None:
        for amount, currency in (
            (1, "GBP"),
            (Decimal("NaN"), "GBP"),
            (Decimal("1"), "gbp"),
            (Decimal("1"), "GB"),
        ):
            with self.subTest(amount=amount, currency=currency):
                with self.assertRaises((TypeError, PriceChangesDomainError)):
                    PriceChangeDelta(amount, currency)  # type: ignore[arg-type]

        for kwargs in (
            {"listing_increased_count": -1},
            {"release_unchanged_count": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises((TypeError, PriceChangesDomainError)):
                    PriceChangesSummary(**kwargs)

        with self.assertRaises(PriceChangesDomainError):
            PriceChangesSnapshotReference(
                "snapshot",
                LATEST_CAPTURED_AT.replace(tzinfo=None),
                "discogs",
                MarketplaceDataStatus.COMPLETE,
            )

    def test_detail_classification_rejects_wrong_delta_and_contradictory_sides(self) -> None:
        with self.assertRaisesRegex(PriceChangesDomainError, "Delta must equal"):
            listing_change(
                "listing-1",
                1,
                previous_amount="10",
                latest_amount="12",
                delta_amount="1",
            )
        with self.assertRaisesRegex(PriceChangesDomainError, "only a latest"):
            ReleasePriceChange(
                1,
                ReleasePriceMetric.LOWEST_PRICE,
                ReleasePriceChangeKind.NEWLY_AVAILABLE,
                money("10"),
                money("12"),
                None,
                "previous",
                "latest",
                ("Evidence.",),
            )

    def test_output_rejects_inconsistent_context_state_and_successful_values(self) -> None:
        cases = (
            lambda: PriceChangesOutput(
                None,
                self.latest,
                None,
                PriceChangesComparisonState.COMPLETE,
            ),
            lambda: PriceChangesOutput(
                self.previous,
                self.latest,
                "other",
                PriceChangesComparisonState.COMPLETE,
            ),
            lambda: PriceChangesOutput(
                self.previous,
                self.latest,
                "discogs",
                PriceChangesComparisonState.PARTIAL,
            ),
            lambda: PriceChangesOutput(
                self.previous,
                self.latest,
                "discogs",
                PriceChangesComparisonState.INSUFFICIENT_DATA,
                PriceChangesSummary(listing_unchanged_count=1),
            ),
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(PriceChangesDomainError):
                    case()

    def test_unsuccessful_states_require_corresponding_input_evidence(self) -> None:
        failed_reference = reference(
            "failed",
            PREVIOUS_CAPTURED_AT,
            status=MarketplaceDataStatus.FAILED,
        )
        unavailable_reference = reference(
            "unavailable",
            PREVIOUS_CAPTURED_AT,
            status=MarketplaceDataStatus.UNAVAILABLE,
        )
        source_diagnostic = diagnostic("failed_snapshot")

        with self.assertRaisesRegex(PriceChangesDomainError, "failed input"):
            PriceChangesOutput(
                self.previous,
                self.latest,
                "discogs",
                PriceChangesComparisonState.FAILED,
                diagnostics=(source_diagnostic,),
            )
        with self.assertRaisesRegex(PriceChangesDomainError, "Insufficient data"):
            PriceChangesOutput(
                failed_reference,
                self.latest,
                "discogs",
                PriceChangesComparisonState.INSUFFICIENT_DATA,
                diagnostics=(source_diagnostic,),
            )
        with self.assertRaisesRegex(PriceChangesDomainError, "source diagnostics"):
            PriceChangesOutput(
                unavailable_reference,
                self.latest,
                "discogs",
                PriceChangesComparisonState.INSUFFICIENT_DATA,
            )

        failed = PriceChangesOutput(
            failed_reference,
            self.latest,
            "discogs",
            PriceChangesComparisonState.FAILED,
            diagnostics=(source_diagnostic,),
        )
        unavailable = PriceChangesOutput(
            unavailable_reference,
            self.latest,
            "discogs",
            PriceChangesComparisonState.INSUFFICIENT_DATA,
            diagnostics=(source_diagnostic,),
        )

        self.assertIs(failed.comparison_state, PriceChangesComparisonState.FAILED)
        self.assertIs(
            unavailable.comparison_state,
            PriceChangesComparisonState.INSUFFICIENT_DATA,
        )

    def test_output_rejects_summary_mismatch_and_change_snapshot_mismatch(self) -> None:
        change = listing_change("listing-1", 1)

        with self.assertRaisesRegex(PriceChangesDomainError, "does not match"):
            PriceChangesOutput(
                self.previous,
                self.latest,
                "discogs",
                PriceChangesComparisonState.COMPLETE,
                PriceChangesSummary(),
                (change,),
            )
        with self.assertRaisesRegex(PriceChangesDomainError, "snapshot IDs"):
            PriceChangesOutput(
                self.previous,
                self.latest,
                "discogs",
                PriceChangesComparisonState.COMPLETE,
                PriceChangesSummary(listing_increased_count=1),
                (replace(change, latest_snapshot_id="different"),),
            )

    def test_output_rejects_noncanonical_listing_and_release_order(self) -> None:
        listing_first = listing_change("a", 1)
        listing_second = listing_change("b", 2)
        release_first = release_change(1, ReleasePriceMetric.LOWEST_PRICE)
        release_second = release_change(2, ReleasePriceMetric.LOWEST_PRICE)

        with self.assertRaisesRegex(PriceChangesDomainError, "canonical"):
            PriceChangesOutput(
                self.previous,
                self.latest,
                "discogs",
                PriceChangesComparisonState.COMPLETE,
                PriceChangesSummary(listing_increased_count=2),
                (listing_second, listing_first),
            )
        with self.assertRaisesRegex(PriceChangesDomainError, "canonical"):
            PriceChangesOutput(
                self.previous,
                self.latest,
                "discogs",
                PriceChangesComparisonState.COMPLETE,
                PriceChangesSummary(release_increased_count=2),
                release_changes=(release_second, release_first),
            )

    def test_outputs_defensively_copy_collections_and_remain_immutable(self) -> None:
        result = analyse(
            listing_snapshot(
                "previous",
                PREVIOUS_CAPTURED_AT,
                (listing("listing-1", 1, PREVIOUS_CAPTURED_AT, "10"),),
            ),
            listing_snapshot(
                "latest",
                LATEST_CAPTURED_AT,
                (listing("listing-1", 1, LATEST_CAPTURED_AT, "12"),),
            ),
        )
        output = price_output(result)
        source_changes = list(output.listing_changes)
        copied = PriceChangesOutput(
            output.previous_snapshot,
            output.latest_snapshot,
            output.source,
            output.comparison_state,
            output.summary,
            source_changes,
            list(output.release_changes),
            list(output.diagnostics),
        )

        source_changes.clear()

        self.assertEqual(copied, output)
        self.assertIsInstance(copied.listing_changes, tuple)
        self.assertIsInstance(copied.diagnostics, tuple)
        with self.assertRaises(FrozenInstanceError):
            output.source = "other"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            output.summary.listing_increased_count = 2  # type: ignore[misc]
        with self.assertRaises(TypeError):
            result.metrics["output"] = None  # type: ignore[index]


class PriceChangesArchitectureTestCase(unittest.TestCase):
    def test_module_has_no_clock_network_persistence_application_or_ui_coupling(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "src/dip/marketplace_intelligence/price_changes.py"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "datetime.now",
            "datetime.utcnow",
            "requests",
            "urllib",
            "httpx",
            "sqlite3",
            "dip.persistence",
            "dip.marketplace_history",
            "dip.app",
            "dip.experience",
            "context.collection",
            "context.history",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_module_does_not_score_recommend_or_aggregate_listing_prices(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "src/dip/marketplace_intelligence/price_changes.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("recommend", source.lower())
        self.assertNotIn("opportunity", source.lower())
        self.assertNotIn("score", source.lower())
        self.assertNotIn("min(value.price", source)
        self.assertNotIn("max(value.price", source)

    def test_default_registry_does_not_implicitly_register_price_changes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        defaults_source = (root / "src/dip/intelligence/defaults.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("PriceChangesModule", defaults_source)
        self.assertNotIn("price_changes", build_v02_intelligence_registry().module_ids)


def money(amount: str, currency: str = "GBP") -> MarketplaceMoney:
    return MarketplaceMoney(Decimal(amount), currency)


def diagnostic(
    code: str = "source_warning",
    *,
    severity: MarketplaceDiagnosticSeverity = MarketplaceDiagnosticSeverity.WARNING,
    details: dict[str, str] | None = None,
) -> MarketplaceDiagnostic:
    return MarketplaceDiagnostic(
        code,
        "The supplied Marketplace evidence was incomplete.",
        severity,
        {} if details is None else details,
    )


def listing(
    listing_id: str,
    release_id: int,
    observed_at: datetime,
    amount: str,
    currency: str = "GBP",
    *,
    shipping: str | None = None,
    condition: str | None = None,
    seller_region: str | None = None,
) -> MarketplaceListingObservation:
    return MarketplaceListingObservation(
        listing_id,
        release_id,
        observed_at,
        money(amount, currency),
        None if shipping is None else money(shipping, currency),
        condition,
        seller_region,
    )


def release(
    release_id: int,
    observed_at: datetime,
    *,
    lowest: str | None = None,
    highest: str | None = None,
    currency: str = "GBP",
    status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
    diagnostics: tuple[MarketplaceDiagnostic, ...] = (),
) -> MarketplaceReleaseObservation:
    return MarketplaceReleaseObservation(
        release_id,
        observed_at,
        status,
        lowest_price=None if lowest is None else money(lowest, currency),
        highest_price=None if highest is None else money(highest, currency),
        num_for_sale=1,
        diagnostics=diagnostics,
    )


def snapshot(
    snapshot_id: str,
    captured_at: datetime,
    *,
    source: str = "discogs",
    status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
    releases: tuple[MarketplaceReleaseObservation, ...] = (),
    listings: tuple[MarketplaceListingObservation, ...] = (),
    diagnostics: tuple[MarketplaceDiagnostic, ...] = (),
    source_version: str | None = "api-v1",
) -> MarketplaceSnapshot:
    return MarketplaceSnapshot(
        snapshot_id,
        captured_at,
        source,
        status,
        releases,
        listings,
        diagnostics,
        source_version,
    )


def empty_snapshot(
    snapshot_id: str,
    captured_at: datetime,
    *,
    source: str = "discogs",
    source_version: str | None = "api-v1",
) -> MarketplaceSnapshot:
    return snapshot(
        snapshot_id,
        captured_at,
        source=source,
        status=MarketplaceDataStatus.EMPTY,
        source_version=source_version,
    )


def state_snapshot(
    snapshot_id: str,
    captured_at: datetime,
    status: MarketplaceDataStatus,
) -> MarketplaceSnapshot:
    return snapshot(
        snapshot_id,
        captured_at,
        status=status,
        diagnostics=(diagnostic(f"{status.value}_snapshot"),),
    )


def listing_snapshot(
    snapshot_id: str,
    captured_at: datetime,
    listings: tuple[MarketplaceListingObservation, ...],
    *,
    release_ids: tuple[int, ...] | None = None,
    diagnostics: tuple[MarketplaceDiagnostic, ...] = (),
) -> MarketplaceSnapshot:
    ids = (
        tuple(sorted({value.release_id for value in listings}))
        if release_ids is None
        else release_ids
    )
    return snapshot(
        snapshot_id,
        captured_at,
        releases=tuple(release(value, captured_at) for value in ids),
        listings=listings,
        diagnostics=diagnostics,
    )


def analyse(
    previous: MarketplaceSnapshot,
    latest: MarketplaceSnapshot,
):
    return PriceChangesModule().analyse(
        IntelligenceContext(
            marketplace_comparison=MarketplaceSnapshotComparisonInput(previous, latest)
        )
    )


def price_output(result) -> PriceChangesOutput:
    output = result.metrics["output"]
    if type(output) is not PriceChangesOutput:
        raise AssertionError("Price Changes did not return its typed output.")
    return output


def reference(
    snapshot_id: str,
    captured_at: datetime,
    *,
    source: str = "discogs",
    status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
    source_version: str | None = "api-v1",
) -> PriceChangesSnapshotReference:
    return PriceChangesSnapshotReference(
        snapshot_id,
        captured_at,
        source,
        status,
        source_version,
    )


def listing_change(
    listing_id: str,
    release_id: int,
    *,
    previous_amount: str = "10",
    latest_amount: str = "12",
    delta_amount: str = "2",
) -> ListingPriceChange:
    return ListingPriceChange(
        listing_id,
        release_id,
        ListingPriceChangeKind.INCREASED,
        money(previous_amount),
        money(latest_amount),
        PriceChangeDelta(Decimal(delta_amount), "GBP"),
        PREVIOUS_CAPTURED_AT,
        LATEST_CAPTURED_AT,
        "previous",
        "latest",
        ("The listing price increased.",),
    )


def release_change(
    release_id: int,
    metric: ReleasePriceMetric,
) -> ReleasePriceChange:
    return ReleasePriceChange(
        release_id,
        metric,
        ReleasePriceChangeKind.INCREASED,
        money("10"),
        money("12"),
        PriceChangeDelta(Decimal("2"), "GBP"),
        "previous",
        "latest",
        ("The supplied release price increased.",),
    )


if __name__ == "__main__":
    unittest.main()
