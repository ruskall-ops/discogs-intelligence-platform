from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest

from dip.app import (
    CollectionExplorerPresentationService,
    PriceChangesPresentationService,
)
from dip.experience.desktop import (
    DesktopCollectionExplorerController,
    DesktopCollectionExplorerRenderer,
    DesktopPriceChangesRenderer,
)
from dip.experience.explorer import (
    CollectionExplorerDestination,
    CollectionExplorerState,
    CollectionExplorerViewModelBuilder,
)
from dip.experience.price_changes import (
    PriceChangesDetailConsistencyError,
    PriceChangesDetailState,
    PriceChangesDetailViewModel,
    PriceChangesDetailViewModelBuilder,
)
from dip.intelligence import IntelligenceContext, IntelligenceStatus
from dip.marketplace_intelligence import (
    ListingPriceChangeKind,
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceListingObservation,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    PriceChangeDelta,
    PriceChangesModule,
)

from tests.test_collection_explorer import (
    available_homepage,
    health_service,
    hidden_service,
)


PREVIOUS_TIME = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
LATEST_TIME = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)


class PriceChangesPresentationModelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = PriceChangesDetailViewModelBuilder()

    def test_available_model_is_frozen_and_preserves_typed_values_and_order(self) -> None:
        detail = self.builder.build(changed_result())
        copied = replace(
            detail,
            listing_changes=list(detail.listing_changes),
            release_changes=list(detail.release_changes),
        )

        self.assertIs(detail.state, PriceChangesDetailState.AVAILABLE)
        self.assertEqual(detail.previous_snapshot.snapshot_id, "previous")
        self.assertEqual(detail.latest_snapshot.snapshot_id, "latest")
        self.assertEqual(detail.source, "discogs")
        self.assertEqual(detail.listing_change_count, 1)
        self.assertEqual(detail.release_change_count, 2)
        self.assertEqual(detail.unchanged_count, 0)
        self.assertEqual(detail.incomparable_count, 0)
        self.assertEqual(detail.listing_changes[0].listing_id, "listing-1")
        self.assertEqual(
            detail.listing_changes[0].delta.amount.as_tuple().exponent,
            -2,
        )
        self.assertIsInstance(copied.listing_changes, tuple)
        self.assertIsInstance(copied.release_changes, tuple)
        with self.assertRaises(FrozenInstanceError):
            detail.summary = "Changed"  # type: ignore[misc]

    def test_all_explicit_states_are_distinct(self) -> None:
        loading = PriceChangesDetailViewModel.loading()
        available = self.builder.build(changed_result())
        partial = self.builder.build(cross_currency_result())
        empty = self.builder.build(unchanged_result())
        unavailable = self.builder.build(None)
        insufficient_history = self.builder.build(
            PriceChangesModule().analyse(IntelligenceContext())
        )
        insufficient_data = self.builder.build(different_source_result())
        error = self.builder.build(failed_result())

        self.assertEqual(
            {
                loading.state,
                available.state,
                partial.state,
                empty.state,
                unavailable.state,
                insufficient_history.state,
                insufficient_data.state,
                error.state,
            },
            set(PriceChangesDetailState),
        )
        self.assertIsNone(insufficient_history.previous_snapshot)
        self.assertIsNone(insufficient_history.latest_snapshot)
        self.assertIsNotNone(insufficient_data.previous_snapshot)
        self.assertIsNotNone(insufficient_data.latest_snapshot)
        self.assertIsNone(insufficient_data.source)
        self.assertIsNotNone(error.previous_snapshot)
        self.assertIsNotNone(error.latest_snapshot)

    def test_one_snapshot_retains_latest_context_as_insufficient_history(self) -> None:
        latest = market_snapshot("latest", LATEST_TIME, listing_price="12.00")
        result = PriceChangesModule().analyse(
            IntelligenceContext(
                marketplace_comparison=MarketplaceSnapshotComparisonInput(
                    latest_snapshot=latest
                )
            )
        )

        detail = self.builder.build(result)

        self.assertIs(detail.state, PriceChangesDetailState.INSUFFICIENT_HISTORY)
        self.assertIsNone(detail.previous_snapshot)
        self.assertEqual(detail.latest_snapshot.snapshot_id, "latest")
        self.assertEqual(detail.latest_snapshot.source, "discogs")

    def test_builder_rejects_wrong_module_missing_output_and_status_mismatch(self) -> None:
        result = changed_result()

        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "requires"):
            self.builder.build(replace(result, module_id="other_module"))
        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "typed"):
            self.builder.build(replace(result, metrics={}))
        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "status"):
            self.builder.build(replace(result, status=IntelligenceStatus.SKIPPED))

    def test_model_rejects_reordering_count_mismatch_and_renderer_inconsistent_kind(self) -> None:
        detail = self.builder.build(changed_result())

        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "order"):
            replace(detail, release_changes=tuple(reversed(detail.release_changes)))
        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "count"):
            replace(detail, listing_change_count=2)
        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "sign"):
            replace(
                detail.listing_changes[0],
                change_kind=ListingPriceChangeKind.DECREASED,
            )
        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "sign"):
            replace(
                detail.listing_changes[0],
                delta=PriceChangeDelta(Decimal("0"), "GBP"),
            )
        insufficient = self.builder.build(
            PriceChangesModule().analyse(IntelligenceContext())
        )
        with self.assertRaisesRegex(PriceChangesDetailConsistencyError, "zero"):
            replace(insufficient, unchanged_count=1)


class PriceChangesRendererTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = PriceChangesDetailViewModelBuilder()
        self.renderer = DesktopPriceChangesRenderer()

    def test_renderer_preserves_snapshot_money_delta_release_and_evidence(self) -> None:
        rendered = self.renderer.render(self.builder.build(changed_result()))

        self.assertIn("Previous snapshot: previous", rendered.context)
        self.assertIn("2026-07-18T12:00+00:00", rendered.context)
        self.assertIn("Latest snapshot: latest", rendered.context)
        self.assertIn("Comparison source: discogs", rendered.context)
        self.assertIn("Previous price: GBP 10.00", rendered.listing_changes[0].body)
        self.assertIn("Latest price: GBP 12.00", rendered.listing_changes[0].body)
        self.assertIn("Delta: GBP +2.00", rendered.listing_changes[0].body)
        self.assertIn("Continuing listing price was higher", rendered.listing_changes[0].body)
        self.assertEqual(rendered.release_changes[0].heading, "Release 1 · Lowest Price")
        self.assertIn("Delta: GBP +1.00", rendered.release_changes[0].body)

    def test_cross_currency_and_state_messages_are_explicit(self) -> None:
        partial = self.renderer.render(self.builder.build(cross_currency_result()))
        empty = self.renderer.render(self.builder.build(unchanged_result()))
        unavailable = self.renderer.render(PriceChangesDetailViewModel.unavailable())
        insufficient_history = self.renderer.render(
            self.builder.build(PriceChangesModule().analyse(IntelligenceContext()))
        )
        insufficient_data = self.renderer.render(
            self.builder.build(different_source_result())
        )
        error = self.renderer.render(self.builder.build(failed_result()))

        self.assertIn("partial evidence", partial.headline)
        self.assertIn("Delta: Unavailable", partial.listing_changes[0].body)
        self.assertIn("different currencies", partial.listing_changes[0].body)
        self.assertIn("No price changes", empty.headline)
        self.assertIn("unavailable", unavailable.headline.lower())
        self.assertIn("history", insufficient_history.headline.lower())
        self.assertIn("Insufficient data", insufficient_data.headline)
        self.assertIn("could not", error.headline)

    def test_renderer_has_neutral_wording_and_no_comparison_calculations(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src/dip/experience/desktop/price_changes_renderer.py"
        ).read_text(encoding="utf-8").lower()
        for forbidden in (
            "buy now",
            "sell now",
            "bargain",
            "good deal",
            "opportunity",
            "underpriced",
            "recommended",
            "improved",
            "worsened",
        ):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("latest.amount - previous.amount", source)
        self.assertNotIn("sorted(", source)


class PriceChangesExplorerIntegrationTestCase(unittest.TestCase):
    def test_price_changes_is_sixth_and_overview_remains_selected(self) -> None:
        result = changed_result()
        rendered = explorer_controller().open(
            available_homepage(),
            price_changes_result=result,
        )

        self.assertEqual(
            tuple(section.destination for section in rendered.sections),
            tuple(CollectionExplorerDestination),
        )
        self.assertEqual(len(rendered.sections), 8)
        self.assertIs(
            rendered.sections[4].destination,
            CollectionExplorerDestination.WEEKEND_LISTINGS,
        )
        self.assertIs(
            rendered.sections[5].destination,
            CollectionExplorerDestination.PRICE_CHANGES,
        )
        self.assertIs(
            rendered.selected_destination,
            CollectionExplorerDestination.OVERVIEW,
        )
        self.assertIn("Listing listing-1", rendered.sections[5].body)
        self.assertIn("Release-level changes", rendered.sections[5].body)

    def test_result_is_consumed_once_and_repeated_destination_access_does_no_work(self) -> None:
        result = changed_result()
        real = PriceChangesPresentationService(
            PriceChangesDetailViewModelBuilder()
        )

        class RecordingPriceChangesPresentation:
            def __init__(self) -> None:
                self.calls = []

            def detail_for_result(self, supplied):
                self.calls.append(supplied)
                return real.detail_for_result(supplied)

        price_changes = RecordingPriceChangesPresentation()
        controller = DesktopCollectionExplorerController(
            explorer_presentation(price_changes)
        )

        rendered = controller.open(
            available_homepage(),
            price_changes_result=result,
        )
        for _ in range(3):
            for destination in CollectionExplorerDestination:
                next(
                    section
                    for section in rendered.sections
                    if section.destination is destination
                )

        self.assertEqual(price_changes.calls, [result])

    def test_unavailable_stays_usable_and_partial_marks_workspace_partial(self) -> None:
        unavailable = explorer_controller().open(available_homepage())
        partial = explorer_controller().open(
            available_homepage(),
            price_changes_result=cross_currency_result(),
        )

        self.assertIs(unavailable.state, CollectionExplorerState.AVAILABLE)
        self.assertIs(
            unavailable.navigation[5].state,
            CollectionExplorerState.UNAVAILABLE,
        )
        self.assertIs(partial.state, CollectionExplorerState.PARTIAL)
        self.assertIs(
            partial.navigation[5].state,
            CollectionExplorerState.PARTIAL,
        )

    def test_loading_workspace_does_not_consume_supplied_result(self) -> None:
        class UnexpectedPriceChangesPresentation:
            def detail_for_result(self, result):
                raise AssertionError("loading Explorer must not consume Price Changes")

        from dip.experience.dashboard import DashboardHomepageViewModel

        explorer = explorer_presentation(
            UnexpectedPriceChangesPresentation()
        ).explorer_for_homepage(
            DashboardHomepageViewModel.loading(),
            price_changes_result=changed_result(),
        )

        self.assertIs(explorer.state, CollectionExplorerState.LOADING)
        self.assertTrue(
            all(
                value.state is CollectionExplorerState.LOADING
                for value in explorer.destinations
            )
        )

    def test_presentation_has_no_execution_history_persistence_or_network_dependency(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = (
            root / "src/dip/app/price_changes_presentation.py",
            root / "src/dip/experience/price_changes/models.py",
            root / "src/dip/experience/price_changes/builder.py",
            root / "src/dip/experience/desktop/price_changes_renderer.py",
        )
        for path in files:
            source = path.read_text(encoding="utf-8")
            for forbidden in (
                "PriceChangesModule",
                "MarketplaceHistory",
                "dip.persistence",
                "sqlite3",
                "requests",
                "urllib",
            ):
                self.assertNotIn(forbidden, source)


def explorer_presentation(price_changes) -> CollectionExplorerPresentationService:
    return CollectionExplorerPresentationService(
        health_service(),
        hidden_service(),
        CollectionExplorerViewModelBuilder(),
        price_changes=price_changes,
    )


def explorer_controller() -> DesktopCollectionExplorerController:
    return DesktopCollectionExplorerController(
        explorer_presentation(
            PriceChangesPresentationService(PriceChangesDetailViewModelBuilder())
        ),
        DesktopCollectionExplorerRenderer(),
    )


def money(amount: str, currency: str = "GBP") -> MarketplaceMoney:
    return MarketplaceMoney(Decimal(amount), currency)


def market_snapshot(
    snapshot_id: str,
    captured_at: datetime,
    *,
    listing_price: str = "10.00",
    lowest_price: str = "8.00",
    highest_price: str = "12.00",
    currency: str = "GBP",
    source: str = "discogs",
    status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
) -> MarketplaceSnapshot:
    diagnostic = MarketplaceDiagnostic(
        "source_incomplete" if status is MarketplaceDataStatus.PARTIAL else "source_failed",
        "The supplied Marketplace source was incomplete."
        if status is MarketplaceDataStatus.PARTIAL
        else "The supplied Marketplace source failed.",
    )
    if status in {
        MarketplaceDataStatus.EMPTY,
        MarketplaceDataStatus.UNAVAILABLE,
        MarketplaceDataStatus.FAILED,
    }:
        return MarketplaceSnapshot(
            snapshot_id,
            captured_at,
            source,
            status,
            diagnostics=(diagnostic,)
            if status in {
                MarketplaceDataStatus.UNAVAILABLE,
                MarketplaceDataStatus.FAILED,
            }
            else (),
            source_version="v1",
        )
    observation_status = (
        MarketplaceDataStatus.PARTIAL
        if status is MarketplaceDataStatus.PARTIAL
        else MarketplaceDataStatus.COMPLETE
    )
    release_diagnostics = (diagnostic,) if status is MarketplaceDataStatus.PARTIAL else ()
    observed_at = captured_at - timedelta(hours=1)
    release = MarketplaceReleaseObservation(
        1,
        observed_at,
        observation_status,
        lowest_price=money(lowest_price, currency),
        highest_price=money(highest_price, currency),
        diagnostics=release_diagnostics,
    )
    listing = MarketplaceListingObservation(
        "listing-1",
        1,
        observed_at,
        money(listing_price, currency),
    )
    return MarketplaceSnapshot(
        snapshot_id,
        captured_at,
        source,
        status,
        (release,),
        (listing,),
        (diagnostic,) if status is MarketplaceDataStatus.PARTIAL else (),
        "v1",
    )


def compare(previous: MarketplaceSnapshot, latest: MarketplaceSnapshot):
    return PriceChangesModule().analyse(
        IntelligenceContext(
            marketplace_comparison=MarketplaceSnapshotComparisonInput(
                previous,
                latest,
            )
        )
    )


def changed_result():
    return compare(
        market_snapshot("previous", PREVIOUS_TIME),
        market_snapshot(
            "latest",
            LATEST_TIME,
            listing_price="12.00",
            lowest_price="9.00",
            highest_price="13.00",
        ),
    )


def unchanged_result():
    return compare(
        market_snapshot("previous", PREVIOUS_TIME),
        market_snapshot("latest", LATEST_TIME),
    )


def cross_currency_result():
    return compare(
        market_snapshot("previous", PREVIOUS_TIME, currency="GBP"),
        market_snapshot("latest", LATEST_TIME, currency="USD"),
    )


def different_source_result():
    return compare(
        market_snapshot("previous", PREVIOUS_TIME, source="discogs"),
        market_snapshot("latest", LATEST_TIME, source="another_source"),
    )


def failed_result():
    return compare(
        market_snapshot(
            "previous",
            PREVIOUS_TIME,
            status=MarketplaceDataStatus.FAILED,
        ),
        market_snapshot(
            "latest",
            LATEST_TIME,
            status=MarketplaceDataStatus.EMPTY,
        ),
    )


if __name__ == "__main__":
    unittest.main()
