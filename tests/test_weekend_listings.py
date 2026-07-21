from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from pathlib import Path
import unittest

from dip.intelligence import (
    IntelligenceContext,
    IntelligenceEngine,
    IntelligenceStatus,
    build_v02_intelligence_registry,
)
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    dumps_intelligence_value,
    loads_intelligence_value,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceListingObservation,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    WeekendListingCandidate,
    WeekendListingsDomainError,
    WeekendListingsModule,
    WeekendListingsOutput,
    WeekendWindow,
)


SATURDAY = datetime(2026, 7, 18, tzinfo=timezone.utc)
MONDAY = datetime(2026, 7, 20, tzinfo=timezone.utc)


class WeekendWindowTestCase(unittest.TestCase):
    def test_valid_window_is_aware_strict_and_immutable(self) -> None:
        window = WeekendWindow(SATURDAY, MONDAY)

        self.assertTrue(window.contains(SATURDAY))
        self.assertTrue(window.contains(MONDAY - timedelta(microseconds=1)))
        self.assertFalse(window.contains(MONDAY))
        with self.assertRaises(FrozenInstanceError):
            window.end = MONDAY + timedelta(days=1)  # type: ignore[misc]

    def test_naive_reversed_zero_and_overlong_windows_are_rejected(self) -> None:
        cases = (
            (SATURDAY.replace(tzinfo=None), MONDAY),
            (SATURDAY, MONDAY.replace(tzinfo=None)),
            (SATURDAY, SATURDAY),
            (SATURDAY, SATURDAY - timedelta(days=1)),
            (SATURDAY, MONDAY + timedelta(days=7)),
            (SATURDAY + timedelta(hours=1), MONDAY),
        )
        for start, end in cases:
            with self.subTest(start=start, end=end):
                with self.assertRaises(WeekendListingsDomainError):
                    WeekendWindow(start, end)

    def test_window_requires_one_explicit_timezone(self) -> None:
        with self.assertRaisesRegex(WeekendListingsDomainError, "same timezone"):
            WeekendWindow(
                SATURDAY,
                datetime(
                    2026,
                    7,
                    20,
                    tzinfo=timezone(timedelta(hours=1)),
                ),
            )

    def test_window_rejects_an_explicit_interval_over_49_hours(self) -> None:
        supplied_timezone = _TwoHourWeekendRollback()

        with self.assertRaisesRegex(WeekendListingsDomainError, "49 hours"):
            WeekendWindow(
                datetime(2026, 7, 18, tzinfo=supplied_timezone),
                datetime(2026, 7, 20, tzinfo=supplied_timezone),
            )


class WeekendListingsModuleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.window = WeekendWindow(SATURDAY, MONDAY)
        self.module = WeekendListingsModule(self.window)

    def test_collection_listing_inside_window_qualifies_with_factual_evidence(self) -> None:
        source = snapshot(
            listing("listing-1", 1, SATURDAY + timedelta(hours=10)),
        )
        context = IntelligenceContext(
            collection=(
                {"release_id": 1, "artist": "Artist", "title": "Title"},
            ),
            marketplace_snapshot=source,
        )

        result = self.module.analyse(context)
        output = result.metrics["output"]
        candidate = output.candidates[0]

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(self.module.module_id, "weekend_listings")
        self.assertEqual(self.module.module_version, "1.0")
        self.assertEqual(candidate.listing_id, "listing-1")
        self.assertEqual(candidate.artist, "Artist")
        self.assertEqual(candidate.title, "Title")
        self.assertEqual(candidate.price.amount, Decimal("20.00"))
        self.assertEqual(
            candidate.inclusion_evidence,
            (
                "Release is present in the supplied collection.",
                "Listing was observed within the supplied weekend window.",
                "Source snapshot permitted listing evaluation.",
            ),
        )
        self.assertFalse(hasattr(candidate, "score"))
        self.assertNotIn("recommend", result.summary.lower())

    def test_outside_window_and_noncollection_releases_are_excluded(self) -> None:
        source = snapshot(
            listing("before", 1, SATURDAY - timedelta(seconds=1)),
            listing("at-end", 1, MONDAY),
            listing("other-release", 2, SATURDAY),
        )

        result = self.module.analyse(
            IntelligenceContext(
                collection=({"release_id": 1},),
                marketplace_snapshot=source,
            )
        )

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(result.metrics["output"].candidates, ())
        self.assertIn("0 collection-relevant", result.summary)

    def test_candidate_order_is_timestamp_descending_then_stable_ids(self) -> None:
        same_time = SATURDAY + timedelta(hours=4)
        source = snapshot(
            listing("z-listing", 1, same_time),
            listing("a-listing", 1, same_time),
            listing("newest", 2, same_time + timedelta(hours=1)),
            listing("b-listing", 2, same_time),
        )
        result = self.module.analyse(
            IntelligenceContext(
                collection=(
                    {"release_id": 1},
                    {"release_id": 2},
                ),
                marketplace_snapshot=source,
            )
        )

        self.assertEqual(
            tuple(
                (value.release_id, value.listing_id)
                for value in result.metrics["output"].candidates
            ),
            ((2, "newest"), (1, "a-listing"), (1, "z-listing"), (2, "b-listing")),
        )

    def test_optional_fields_do_not_exclude_listing_and_currencies_are_not_compared(self) -> None:
        source = snapshot(
            listing(
                "gbp-listing",
                1,
                SATURDAY,
                currency="GBP",
                optional=False,
            ),
            listing("usd-listing", 2, SATURDAY, currency="USD"),
        )
        result = self.module.analyse(
            IntelligenceContext(
                collection=({"release_id": 1}, {"release_id": 2}),
                marketplace_snapshot=source,
            )
        )
        candidates = result.metrics["output"].candidates

        self.assertEqual(len(candidates), 2)
        self.assertIsNone(candidates[0].shipping)
        self.assertIsNone(candidates[0].condition)
        self.assertIsNone(candidates[0].seller_region)
        self.assertEqual({value.price.currency for value in candidates}, {"GBP", "USD"})

    def test_snapshot_statuses_map_to_distinct_standard_results(self) -> None:
        diagnostic = source_diagnostic()
        cases = (
            (
                MarketplaceSnapshot(
                    "empty-1",
                    MONDAY,
                    "discogs",
                    MarketplaceDataStatus.EMPTY,
                ),
                IntelligenceStatus.COMPLETED,
                MarketplaceDataStatus.EMPTY,
            ),
            (
                MarketplaceSnapshot(
                    "partial-1",
                    MONDAY,
                    "discogs",
                    MarketplaceDataStatus.PARTIAL,
                    (release(1, status=MarketplaceDataStatus.PARTIAL),),
                    (listing("listing-1", 1, SATURDAY),),
                    (diagnostic,),
                ),
                IntelligenceStatus.COMPLETED,
                MarketplaceDataStatus.PARTIAL,
            ),
            (
                MarketplaceSnapshot(
                    "unavailable-1",
                    MONDAY,
                    "discogs",
                    MarketplaceDataStatus.UNAVAILABLE,
                    diagnostics=(diagnostic,),
                ),
                IntelligenceStatus.SKIPPED,
                MarketplaceDataStatus.UNAVAILABLE,
            ),
            (
                MarketplaceSnapshot(
                    "failed-1",
                    MONDAY,
                    "discogs",
                    MarketplaceDataStatus.FAILED,
                    diagnostics=(diagnostic,),
                ),
                IntelligenceStatus.FAILED,
                MarketplaceDataStatus.FAILED,
            ),
        )
        for source, expected_status, source_status in cases:
            with self.subTest(source_status=source_status):
                result = self.module.analyse(
                    IntelligenceContext(
                        collection=({"release_id": 1},),
                        marketplace_snapshot=source,
                    )
                )
                self.assertIs(result.status, expected_status)
                self.assertIs(result.metrics["output"].snapshot_status, source_status)

    def test_partial_source_preserves_diagnostics_and_valid_candidates(self) -> None:
        diagnostic = source_diagnostic()
        source = MarketplaceSnapshot(
            "partial-1",
            MONDAY,
            "discogs",
            MarketplaceDataStatus.PARTIAL,
            (release(1, status=MarketplaceDataStatus.PARTIAL),),
            (listing("listing-1", 1, SATURDAY),),
            (diagnostic,),
        )

        result = self.module.analyse(
            IntelligenceContext(
                collection=({"release_id": 1},),
                marketplace_snapshot=source,
            )
        )

        self.assertIs(result.status, IntelligenceStatus.COMPLETED)
        self.assertEqual(result.metrics["output"].source_diagnostics, (diagnostic,))
        self.assertIn("partial_response", result.diagnostics[0])
        self.assertEqual(len(result.metrics["output"].candidates), 1)

    def test_missing_snapshot_and_malformed_collection_are_insufficient(self) -> None:
        missing = self.module.analyse(IntelligenceContext(collection=()))
        malformed = self.module.analyse(
            IntelligenceContext(
                collection=({"release_id": "not-normalized"},),
                marketplace_snapshot=snapshot(),
            )
        )

        self.assertIs(missing.status, IntelligenceStatus.SKIPPED)
        self.assertIsNone(missing.metrics["output"].snapshot_id)
        self.assertIs(malformed.status, IntelligenceStatus.SKIPPED)
        self.assertFalse(malformed.metrics["output"].collection_context_complete)

    def test_source_inputs_are_not_mutated(self) -> None:
        collection_row = {"release_id": 1, "artist": "Artist", "title": "Title"}
        source = snapshot(listing("listing-1", 1, SATURDAY))

        self.module.analyse(
            IntelligenceContext(
                collection=(collection_row,),
                marketplace_snapshot=source,
            )
        )

        self.assertEqual(
            collection_row,
            {"release_id": 1, "artist": "Artist", "title": "Title"},
        )
        self.assertEqual(source.listing_observations[0].listing_id, "listing-1")

    def test_duplicate_listing_ids_are_rejected_by_the_supplied_snapshot(self) -> None:
        duplicate = listing("duplicate", 1, SATURDAY)

        with self.assertRaisesRegex(ValueError, "unique"):
            snapshot(duplicate, duplicate)


class WeekendListingsOutputAndIntegrationTestCase(unittest.TestCase):
    def test_output_rejects_duplicates_wrong_order_window_and_snapshot_mismatch(self) -> None:
        window = WeekendWindow(SATURDAY, MONDAY)
        later = candidate("later", 1, SATURDAY + timedelta(hours=2))
        earlier = candidate("earlier", 1, SATURDAY + timedelta(hours=1))
        cases = (
            (later, later),
            (earlier, later),
            (replace(later, observed_at=MONDAY),),
            (replace(later, snapshot_id="other"),),
        )
        for candidates in cases:
            with self.subTest(candidates=candidates):
                with self.assertRaises(WeekendListingsDomainError):
                    WeekendListingsOutput(
                        window,
                        "snapshot-1",
                        MarketplaceDataStatus.COMPLETE,
                        candidates,
                    )

    def test_incomplete_source_output_requires_source_diagnostics(self) -> None:
        with self.assertRaisesRegex(WeekendListingsDomainError, "diagnostics"):
            WeekendListingsOutput(
                WeekendWindow(SATURDAY, MONDAY),
                "snapshot-1",
                MarketplaceDataStatus.PARTIAL,
            )

    def test_typed_output_is_frozen_and_history_serializable(self) -> None:
        result = WeekendListingsModule(WeekendWindow(SATURDAY, MONDAY)).analyse(
            IntelligenceContext(
                collection=({"release_id": 1},),
                marketplace_snapshot=snapshot(listing("listing-1", 1, SATURDAY)),
            )
        )
        output = result.metrics["output"]
        record = IntelligenceHistoryRecord(
            record_id=None,
            run_id=1,
            module_id=result.module_id,
            module_version=result.module_version,
            status=result.status,
            summary=result.summary,
            metrics=result.metrics,
            evidence=result.evidence,
            diagnostics=result.diagnostics,
        )

        restored = loads_intelligence_value(dumps_intelligence_value(record))

        self.assertEqual(restored, record)
        self.assertEqual(restored.metrics["output"], output)
        with self.assertRaises(FrozenInstanceError):
            output.collection_context_complete = False  # type: ignore[misc]
        with self.assertRaises(TypeError):
            result.metrics["output"] = None  # type: ignore[index]

    def test_default_registry_is_unchanged_and_explicit_engine_skips_cleanly(self) -> None:
        registry = build_v02_intelligence_registry()
        module = WeekendListingsModule(WeekendWindow(SATURDAY, MONDAY))

        result = IntelligenceEngine((module,)).execute(IntelligenceContext())

        self.assertEqual(
            registry.module_ids,
            ("collection_health", "hidden_gems", "historical_intelligence"),
        )
        self.assertEqual(result.module_count, 1)
        self.assertIs(result.results[0].status, IntelligenceStatus.SKIPPED)
        self.assertTrue(result.successful)

    def test_existing_modules_ignore_additive_typed_snapshot_context(self) -> None:
        registry = build_v02_intelligence_registry()
        source = snapshot()
        without = IntelligenceEngine(registry).execute(IntelligenceContext())
        with_snapshot = IntelligenceEngine(registry).execute(
            IntelligenceContext(marketplace_snapshot=source)
        )

        self.assertEqual(with_snapshot, without)

    def test_module_boundary_has_no_clock_network_persistence_or_presentation(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src/dip/marketplace_intelligence/weekend_listings.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "datetime.now",
            "datetime.utcnow",
            "requests",
            "urllib",
            "sqlite3",
            "dip.persistence",
            "dip.experience",
            "dip.app",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertNotIn("score", source.lower())
        self.assertNotIn("sorted(values, key=lambda value: value.price", source)


def money(amount: str = "20.00", currency: str = "GBP") -> MarketplaceMoney:
    return MarketplaceMoney(Decimal(amount), currency)


def source_diagnostic() -> MarketplaceDiagnostic:
    return MarketplaceDiagnostic(
        "partial_response",
        "The supplied source response was incomplete.",
    )


def release(
    release_id: int,
    *,
    status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
) -> MarketplaceReleaseObservation:
    return MarketplaceReleaseObservation(
        release_id,
        MONDAY,
        status,
        num_for_sale=1,
        diagnostics=(source_diagnostic(),) if status is MarketplaceDataStatus.PARTIAL else (),
    )


def listing(
    listing_id: str,
    release_id: int,
    observed_at: datetime,
    *,
    currency: str = "GBP",
    optional: bool = True,
) -> MarketplaceListingObservation:
    return MarketplaceListingObservation(
        listing_id,
        release_id,
        observed_at,
        money(currency=currency),
        shipping=money("3.00", currency) if optional else None,
        condition="Near Mint" if optional else None,
        seller_region="GB" if optional else None,
    )


def snapshot(*listings: MarketplaceListingObservation) -> MarketplaceSnapshot:
    release_ids = sorted({value.release_id for value in listings} or {1})
    return MarketplaceSnapshot(
        "snapshot-1",
        MONDAY,
        "discogs",
        MarketplaceDataStatus.COMPLETE,
        tuple(release(value) for value in release_ids),
        listings,
    )


def candidate(
    listing_id: str,
    release_id: int,
    observed_at: datetime,
) -> WeekendListingCandidate:
    return WeekendListingCandidate(
        listing_id,
        release_id,
        observed_at,
        money(),
        "snapshot-1",
        MarketplaceDataStatus.COMPLETE,
        (
            "Release is present in the supplied collection.",
            "Listing was observed within the supplied weekend window.",
            "Source snapshot permitted listing evaluation.",
        ),
    )


class _TwoHourWeekendRollback(tzinfo):
    """Deterministic supplied timezone used to exercise the duration guard."""

    def utcoffset(self, value: datetime | None) -> timedelta:
        if value is not None and value.weekday() == 5:
            return timedelta(hours=2)
        return timedelta(0)

    def dst(self, value: datetime | None) -> timedelta:
        return timedelta(0)

    def tzname(self, value: datetime | None) -> str:
        return "Weekend rollback test timezone"


if __name__ == "__main__":
    unittest.main()
