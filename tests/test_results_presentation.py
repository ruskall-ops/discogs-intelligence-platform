from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dip.app.marketplace_change_workspace import (
    MarketplaceChangeOutcomeReason,
    MarketplaceChangeWorkspace,
    MarketplaceChangeWorkspaceState,
    MarketplaceSnapshotProvenance,
    MarketplaceSnapshotWindow,
)
from dip.experience.desktop.price_changes_renderer import DesktopPriceChangesRenderer
from dip.experience.desktop.supply_changes_renderer import DesktopSupplyChangesRenderer
from dip.experience.desktop.collection_explorer_renderer import _marketplace_outcome_copy
from dip.experience.explorer import MarketplaceChangePresentationOutcome
from dip.experience.explorer.state_adapter import marketplace_outcome_state_kind
from dip.experience.price_changes import (
    PriceChangesDetailState,
    PriceChangesDetailViewModel,
    PriceChangesSnapshotViewModel,
    ReleasePriceChangeViewModel,
    price_presentation_state_kind,
)
from dip.experience.results_presentation import (
    ComparisonContextViewModel,
    PresentationStateCopy,
    PresentationStateKind,
    SummaryCount,
    SummaryCountIdentifier,
    presentation_state_copy,
)
from dip.experience.supply_changes import (
    ReleaseSupplyChangeViewModel,
    SupplyChangesDetailState,
    SupplyChangesDetailViewModel,
    SupplyChangesSnapshotViewModel,
    supply_presentation_state_kind,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceMoney,
    PriceChangeDelta,
    PriceChangesComparisonState,
    ReleasePriceChangeKind,
    ReleasePriceMetric,
    SupplyChangesComparisonState,
    SupplyChangeKind,
)


NOW = datetime(2026, 8, 2, 12, tzinfo=timezone.utc)


EXPECTED_COPY = {
    PresentationStateKind.AVAILABLE: (
        "Results available",
        "Results use the comparison shown below.",
        None,
    ),
    PresentationStateKind.NO_CHANGES: (
        "No changes observed",
        "Comparable values were unchanged between these snapshots.",
        None,
    ),
    PresentationStateKind.EMPTY: (
        "No matching results",
        "The calculation completed, but no detail rows met this result’s criteria.",
        None,
    ),
    PresentationStateKind.PARTIAL: (
        "Partial evidence",
        "Some supplied evidence was incomplete; available comparisons remain shown.",
        None,
    ),
    PresentationStateKind.INSUFFICIENT_HISTORY: (
        "More history required",
        "Two compatible snapshots captured at different times are required.",
        None,
    ),
    PresentationStateKind.INSUFFICIENT_DATA: (
        "No comparable facts",
        "A compatible snapshot pair exists, but it contains no comparable facts for this result.",
        None,
    ),
    PresentationStateKind.STALE: (
        "Newer history is available",
        "These cached results predate the latest completed Collector Run.",
        "Refresh Marketplace Changes",
    ),
    PresentationStateKind.UNAVAILABLE: (
        "Not available",
        "This destination has no production data path in this release.",
        None,
    ),
    PresentationStateKind.ERROR: (
        "Results could not be displayed",
        "Saved data was not changed. Previous results remain available where shown.",
        "Retry",
    ),
    PresentationStateKind.NO_IMPORTED_COLLECTION: (
        "Import a collection to begin",
        "No Current Collection releases are available.",
        "Import Collection CSV",
    ),
    PresentationStateKind.IMPORTED_NOT_ANALYSED: (
        "Collection imported",
        "Imported collection facts are available. No completed Collector Run intelligence is available yet.",
        "Run Collector Update",
    ),
    PresentationStateKind.POST_IMPORT_DISPLAY_WARNING: (
        "Import saved; display refresh failed",
        "The import committed successfully, but the display could not be refreshed.",
        "Reopen view",
    ),
}


class CanonicalStateCopyTest(unittest.TestCase):
    def test_every_state_has_exact_deterministic_frozen_copy(self):
        self.assertEqual(set(EXPECTED_COPY), set(PresentationStateKind))
        for kind, expected in EXPECTED_COPY.items():
            first = presentation_state_copy(kind)
            second = presentation_state_copy(kind)
            self.assertIs(first, second)
            self.assertEqual(
                (first.heading, first.body, first.action_label),
                expected,
            )
            with self.assertRaises(FrozenInstanceError):
                first.heading = "changed"  # type: ignore[misc]

    def test_unknown_raw_and_malformed_values_are_rejected(self):
        for value in ("available", None, object(), True):
            with self.assertRaises(TypeError):
                presentation_state_copy(value)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            PresentationStateCopy("available", "Heading", "Body")  # type: ignore[arg-type]
        for heading, body, action in (("", "Body", None), (" Heading", "Body", None), ("Heading", " ", None), ("Heading", "Body", " ")):
            with self.assertRaises((TypeError, ValueError)):
                PresentationStateCopy(PresentationStateKind.AVAILABLE, heading, body, action)

    def test_hostile_values_cannot_enter_or_alter_canonical_copy(self):
        sentinels = (
            "token=secret",
            "SELECT * FROM personal_notes",
            "/private/database.sqlite",
            "CSV row value",
            "provider payload",
            "GBP 123.45 supply 9",
        )
        rendered = repr(tuple(presentation_state_copy(kind) for kind in PresentationStateKind))
        for sentinel in sentinels:
            self.assertNotIn(sentinel, rendered)
            with self.assertRaises(TypeError):
                presentation_state_copy(sentinel)  # type: ignore[arg-type]


class SummaryCountTest(unittest.TestCase):
    def test_zero_positive_validation_and_immutability(self):
        zero = SummaryCount(SummaryCountIdentifier.UNCHANGED, "Unchanged", 0)
        positive = SummaryCount(SummaryCountIdentifier.RELEASE_CHANGES, "Changes", 3)
        self.assertEqual((zero.value, positive.value), (0, 3))
        with self.assertRaises(FrozenInstanceError):
            zero.value = 1  # type: ignore[misc]

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(TypeError):
            SummaryCount("unchanged", "Unchanged", 1)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            SummaryCount(SummaryCountIdentifier.UNCHANGED, "Unchanged", True)
        with self.assertRaises(ValueError):
            SummaryCount(SummaryCountIdentifier.UNCHANGED, "Unchanged", -1)
        with self.assertRaises(ValueError):
            SummaryCount(SummaryCountIdentifier.UNCHANGED, " ", 0)


class ComparisonContextTest(unittest.TestCase):
    def _context(self, **changes):
        values = {
            "previous_snapshot_id": "previous",
            "previous_captured_at": NOW - timedelta(days=1),
            "previous_source": "discogs",
            "previous_source_version": "v1",
            "latest_snapshot_id": "latest",
            "latest_captured_at": NOW,
            "latest_source": "discogs",
            "latest_source_version": "v1",
        }
        values.update(changes)
        return ComparisonContextViewModel.from_snapshot_values(**values)

    def test_valid_offsets_none_versions_and_original_instants_are_preserved(self):
        previous = datetime(2026, 8, 1, 13, tzinfo=timezone(timedelta(hours=1)))
        latest = datetime(2026, 8, 2, 8, tzinfo=timezone(timedelta(hours=-4)))
        value = self._context(
            previous_captured_at=previous,
            latest_captured_at=latest,
            previous_source_version=None,
            latest_source_version=None,
        )
        self.assertIs(value.previous_captured_at, previous)
        self.assertIs(value.latest_captured_at, latest)
        self.assertIsNone(value.source_version)

    def test_invalid_time_identity_source_and_version_are_rejected(self):
        cases = (
            {"previous_captured_at": NOW.replace(tzinfo=None)},
            {"latest_captured_at": NOW.replace(tzinfo=None)},
            {"previous_captured_at": NOW},
            {"previous_captured_at": NOW + timedelta(seconds=1)},
            {
                "previous_captured_at": datetime(2026, 8, 2, 13, tzinfo=timezone(timedelta(hours=1))),
                "latest_captured_at": NOW,
            },
            {"previous_snapshot_id": "latest"},
            {"previous_snapshot_id": " "},
            {"latest_snapshot_id": ""},
            {"latest_source": "other"},
            {"latest_source_version": "v2"},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises((TypeError, ValueError)):
                    self._context(**changes)


def _price_snapshots():
    return (
        PriceChangesSnapshotViewModel("previous", NOW - timedelta(days=1), "discogs", MarketplaceDataStatus.COMPLETE, "v1"),
        PriceChangesSnapshotViewModel("latest", NOW, "discogs", MarketplaceDataStatus.COMPLETE, "v1"),
    )


def _supply_snapshots():
    return (
        SupplyChangesSnapshotViewModel("previous", NOW - timedelta(days=1), "discogs", MarketplaceDataStatus.COMPLETE, "v1"),
        SupplyChangesSnapshotViewModel("latest", NOW, "discogs", MarketplaceDataStatus.COMPLETE, "v1"),
    )


def _price(state, comparison, *, unchanged=0, release_changes=()):
    previous, latest = _price_snapshots()
    return PriceChangesDetailViewModel(
        state,
        "Original Price summary.",
        comparison,
        previous_snapshot=None if state is PriceChangesDetailState.INSUFFICIENT_HISTORY else previous,
        latest_snapshot=latest,
        source="discogs",
        listing_change_count=0,
        release_change_count=len(release_changes),
        unchanged_count=unchanged,
        incomparable_count=0,
        release_changes=release_changes,
    )


def _supply(state, comparison, *, unchanged=0):
    previous, latest = _supply_snapshots()
    return SupplyChangesDetailViewModel(
        state,
        "Original Supply summary.",
        comparison,
        previous_snapshot=None if state is SupplyChangesDetailState.INSUFFICIENT_HISTORY else previous,
        latest_snapshot=latest,
        source="discogs",
        change_count=0,
        unchanged_count=unchanged,
        incomparable_count=0,
    )


class MarketplaceStateAdapterTest(unittest.TestCase):
    def test_price_and_supply_distinguish_every_current_shared_state(self):
        price_cases = (
            (_price(PriceChangesDetailState.EMPTY, PriceChangesComparisonState.COMPLETE, unchanged=1), PresentationStateKind.NO_CHANGES),
            (_price(PriceChangesDetailState.EMPTY, PriceChangesComparisonState.COMPLETE), PresentationStateKind.EMPTY),
            (_price(PriceChangesDetailState.PARTIAL, PriceChangesComparisonState.PARTIAL), PresentationStateKind.PARTIAL),
            (_price(PriceChangesDetailState.INSUFFICIENT_HISTORY, PriceChangesComparisonState.INSUFFICIENT_HISTORY), PresentationStateKind.INSUFFICIENT_HISTORY),
            (_price(PriceChangesDetailState.INSUFFICIENT_DATA, PriceChangesComparisonState.INSUFFICIENT_DATA), PresentationStateKind.INSUFFICIENT_DATA),
        )
        supply_cases = (
            (_supply(SupplyChangesDetailState.EMPTY, SupplyChangesComparisonState.COMPLETE, unchanged=1), PresentationStateKind.NO_CHANGES),
            (_supply(SupplyChangesDetailState.EMPTY, SupplyChangesComparisonState.COMPLETE), PresentationStateKind.EMPTY),
            (_supply(SupplyChangesDetailState.PARTIAL, SupplyChangesComparisonState.PARTIAL), PresentationStateKind.PARTIAL),
            (_supply(SupplyChangesDetailState.INSUFFICIENT_HISTORY, SupplyChangesComparisonState.INSUFFICIENT_HISTORY), PresentationStateKind.INSUFFICIENT_HISTORY),
            (_supply(SupplyChangesDetailState.INSUFFICIENT_DATA, SupplyChangesComparisonState.INSUFFICIENT_DATA), PresentationStateKind.INSUFFICIENT_DATA),
        )
        for detail, expected in (*price_cases, *supply_cases):
            self.assertIs(detail.state_copy.kind, expected)

    def test_available_and_error_adapters_and_unrepresented_legacy_states(self):
        previous, latest = _price_snapshots()
        change = ReleasePriceChangeViewModel(
            7,
            ReleasePriceMetric.LOWEST_PRICE,
            ReleasePriceChangeKind.INCREASED,
            MarketplaceMoney(Decimal("10.00"), "GBP"),
            MarketplaceMoney(Decimal("12.50"), "GBP"),
            PriceChangeDelta(Decimal("2.50"), "GBP"),
            previous.snapshot_id,
            latest.snapshot_id,
            ("Observed lowest price increased.",),
        )
        available = _price(
            PriceChangesDetailState.AVAILABLE,
            PriceChangesComparisonState.COMPLETE,
            release_changes=(change,),
        )
        error = PriceChangesDetailViewModel(
            PriceChangesDetailState.ERROR,
            "Safe failure.",
            PriceChangesComparisonState.FAILED,
            listing_change_count=0,
            release_change_count=0,
            unchanged_count=0,
            incomparable_count=0,
        )
        self.assertIs(price_presentation_state_kind(available), PresentationStateKind.AVAILABLE)
        self.assertIs(price_presentation_state_kind(error), PresentationStateKind.ERROR)
        self.assertIsNone(price_presentation_state_kind(PriceChangesDetailViewModel.loading()))
        self.assertIsNone(supply_presentation_state_kind(SupplyChangesDetailViewModel.unavailable()))

    def test_workspace_outcomes_are_typed_and_do_not_collapse_data_into_history(self):
        expected = {
            MarketplaceChangePresentationOutcome.NO_ELIGIBLE_CURRENT: PresentationStateKind.INSUFFICIENT_HISTORY,
            MarketplaceChangePresentationOutcome.NO_COMPATIBLE_BASELINE: PresentationStateKind.INSUFFICIENT_HISTORY,
            MarketplaceChangePresentationOutcome.NO_COMPARABLE_FACTS: PresentationStateKind.INSUFFICIENT_DATA,
            MarketplaceChangePresentationOutcome.HISTORY_UNREADABLE: PresentationStateKind.ERROR,
            MarketplaceChangePresentationOutcome.HISTORY_INVALID: PresentationStateKind.ERROR,
            MarketplaceChangePresentationOutcome.COMPARISON_FAILED: PresentationStateKind.ERROR,
        }
        self.assertEqual(
            {outcome: marketplace_outcome_state_kind(outcome) for outcome in expected},
            expected,
        )
        with self.assertRaises(TypeError):
            marketplace_outcome_state_kind("no_comparable_facts")  # type: ignore[arg-type]

    def test_equivalent_price_and_supply_states_render_identical_copy_and_context(self):
        price = _price(PriceChangesDetailState.PARTIAL, PriceChangesComparisonState.PARTIAL)
        supply = _supply(SupplyChangesDetailState.PARTIAL, SupplyChangesComparisonState.PARTIAL)
        rendered_price = DesktopPriceChangesRenderer().render(price)
        rendered_supply = DesktopSupplyChangesRenderer().render(supply)
        self.assertEqual(
            (rendered_price.headline, rendered_price.summary),
            (rendered_supply.headline, rendered_supply.summary),
        )
        self.assertEqual(price.comparison_context, supply.comparison_context)
        self.assertEqual(
            tuple(value.identifier for value in price.summary_counts[:3]),
            (
                SummaryCountIdentifier.INCREASED,
                SummaryCountIdentifier.DECREASED,
                SummaryCountIdentifier.UNCHANGED,
            ),
        )

    def test_workspace_rejects_price_and_supply_context_disagreement(self):
        price = _price(
            PriceChangesDetailState.EMPTY,
            PriceChangesComparisonState.COMPLETE,
        )
        previous, latest = _supply_snapshots()
        previous = replace(previous, source="other")
        latest = replace(latest, source="other")
        supply = SupplyChangesDetailViewModel(
            SupplyChangesDetailState.EMPTY,
            "Original Supply summary.",
            SupplyChangesComparisonState.COMPLETE,
            previous_snapshot=previous,
            latest_snapshot=latest,
            source="other",
            change_count=0,
            unchanged_count=0,
            incomparable_count=0,
        )
        window = MarketplaceSnapshotWindow(
            MarketplaceSnapshotProvenance(
                "latest", NOW, "discogs", "v1", MarketplaceDataStatus.COMPLETE
            ),
            MarketplaceSnapshotProvenance(
                "previous",
                NOW - timedelta(days=1),
                "discogs",
                "v1",
                MarketplaceDataStatus.COMPLETE,
            ),
        )
        with self.assertRaisesRegex(ValueError, "share one presentation context"):
            MarketplaceChangeWorkspace(
                MarketplaceChangeWorkspaceState.EMPTY,
                window,
                price,
                supply,
            )

    def test_state_aware_summary_projection_and_unsuccessful_renderer_suppression(self):
        price_error = PriceChangesDetailViewModel(
            PriceChangesDetailState.ERROR,
            "Safe failure.",
            PriceChangesComparisonState.FAILED,
            listing_change_count=0,
            release_change_count=0,
            unchanged_count=0,
            incomparable_count=0,
        )
        supply_error = SupplyChangesDetailViewModel(
            SupplyChangesDetailState.ERROR,
            "Safe failure.",
            SupplyChangesComparisonState.FAILED,
            change_count=0,
            unchanged_count=0,
            incomparable_count=0,
        )
        price_history = PriceChangesDetailViewModel(
            PriceChangesDetailState.INSUFFICIENT_HISTORY,
            "History unavailable.",
            PriceChangesComparisonState.INSUFFICIENT_HISTORY,
            listing_change_count=0,
            release_change_count=0,
            unchanged_count=0,
            incomparable_count=0,
        )
        supply_history = SupplyChangesDetailViewModel(
            SupplyChangesDetailState.INSUFFICIENT_HISTORY,
            "History unavailable.",
            SupplyChangesComparisonState.INSUFFICIENT_HISTORY,
            change_count=0,
            unchanged_count=0,
            incomparable_count=0,
        )
        for detail, rendered in (
            (price_error, DesktopPriceChangesRenderer().render(price_error)),
            (price_history, DesktopPriceChangesRenderer().render(price_history)),
            (supply_error, DesktopSupplyChangesRenderer().render(supply_error)),
            (supply_history, DesktopSupplyChangesRenderer().render(supply_history)),
        ):
            self.assertEqual(detail.summary_counts, ())
            self.assertEqual(rendered.counts, "")
            self.assertNotIn("changes: 0", rendered.counts.lower())
            self.assertNotIn("unchanged", rendered.counts.lower())

        price_no_changes = _price(
            PriceChangesDetailState.EMPTY,
            PriceChangesComparisonState.COMPLETE,
            unchanged=2,
        )
        supply_no_changes = _supply(
            SupplyChangesDetailState.EMPTY,
            SupplyChangesComparisonState.COMPLETE,
            unchanged=2,
        )
        self.assertEqual(price_no_changes.summary_counts[2].value, 2)
        self.assertEqual(supply_no_changes.summary_counts[2].value, 2)
        price_partial = _price(
            PriceChangesDetailState.PARTIAL,
            PriceChangesComparisonState.PARTIAL,
        )
        supply_partial = _supply(
            SupplyChangesDetailState.PARTIAL,
            SupplyChangesComparisonState.PARTIAL,
        )
        self.assertEqual(
            tuple(value.identifier for value in price_partial.summary_counts[:3]),
            tuple(value.identifier for value in supply_partial.summary_counts[:3]),
        )

    def test_insufficient_data_projects_only_positive_authoritative_incomparable_count(self):
        previous_price, latest_price = _price_snapshots()
        incomparable_price = ReleasePriceChangeViewModel(
            7,
            ReleasePriceMetric.LOWEST_PRICE,
            ReleasePriceChangeKind.INCOMPARABLE,
            MarketplaceMoney(Decimal("10.00"), "GBP"),
            MarketplaceMoney(Decimal("12.00"), "USD"),
            None,
            previous_price.snapshot_id,
            latest_price.snapshot_id,
            ("Currencies differ.",),
        )
        price = PriceChangesDetailViewModel(
            PriceChangesDetailState.INSUFFICIENT_DATA,
            "No comparable facts.",
            PriceChangesComparisonState.INSUFFICIENT_DATA,
            previous_price,
            latest_price,
            "discogs",
            0,
            1,
            0,
            1,
            release_changes=(incomparable_price,),
        )
        previous_supply, latest_supply = _supply_snapshots()
        incomparable_supply = ReleaseSupplyChangeViewModel(
            7,
            None,
            3,
            None,
            SupplyChangeKind.INCOMPARABLE,
            previous_supply.snapshot_id,
            latest_supply.snapshot_id,
            ("Supply evidence is incomplete.",),
        )
        supply = SupplyChangesDetailViewModel(
            SupplyChangesDetailState.INSUFFICIENT_DATA,
            "No comparable facts.",
            SupplyChangesComparisonState.INSUFFICIENT_DATA,
            previous_supply,
            latest_supply,
            "discogs",
            1,
            0,
            1,
            (incomparable_supply,),
        )
        for detail, rendered in (
            (price, DesktopPriceChangesRenderer().render(price)),
            (supply, DesktopSupplyChangesRenderer().render(supply)),
        ):
            self.assertEqual(len(detail.summary_counts), 1)
            self.assertIs(
                detail.summary_counts[0].identifier,
                SummaryCountIdentifier.INCOMPARABLE,
            )
            self.assertEqual(detail.summary_counts[0].value, 1)
            self.assertIn("Incomparable", rendered.counts)
            self.assertNotIn("Release changes", rendered.counts)
            self.assertNotIn("Listing changes", rendered.counts)
            self.assertNotIn("Unchanged", rendered.counts)

        zero_price = _price(
            PriceChangesDetailState.INSUFFICIENT_DATA,
            PriceChangesComparisonState.INSUFFICIENT_DATA,
        )
        zero_supply = _supply(
            SupplyChangesDetailState.INSUFFICIENT_DATA,
            SupplyChangesComparisonState.INSUFFICIENT_DATA,
        )
        self.assertEqual(zero_price.summary_counts, ())
        self.assertEqual(zero_supply.summary_counts, ())

    def test_workspace_requires_complete_exact_context_window_identity(self):
        price = _price(
            PriceChangesDetailState.EMPTY,
            PriceChangesComparisonState.COMPLETE,
            unchanged=1,
        )
        supply = _supply(
            SupplyChangesDetailState.EMPTY,
            SupplyChangesComparisonState.COMPLETE,
            unchanged=1,
        )
        window = MarketplaceSnapshotWindow(
            MarketplaceSnapshotProvenance(
                "latest", NOW, "discogs", "v1", MarketplaceDataStatus.COMPLETE
            ),
            MarketplaceSnapshotProvenance(
                "previous",
                NOW - timedelta(days=1),
                "discogs",
                "v1",
                MarketplaceDataStatus.COMPLETE,
            ),
        )
        MarketplaceChangeWorkspace(
            MarketplaceChangeWorkspaceState.EMPTY,
            window,
            price,
            supply,
        )

        def changed_details(*, previous=None, latest=None, source=None):
            price_previous = replace(price.previous_snapshot, **(previous or {}))
            price_latest = replace(price.latest_snapshot, **(latest or {}))
            supply_previous = replace(supply.previous_snapshot, **(previous or {}))
            supply_latest = replace(supply.latest_snapshot, **(latest or {}))
            comparison_source = source or price_previous.source
            return (
                replace(
                    price,
                    previous_snapshot=price_previous,
                    latest_snapshot=price_latest,
                    source=comparison_source,
                ),
                replace(
                    supply,
                    previous_snapshot=supply_previous,
                    latest_snapshot=supply_latest,
                    source=comparison_source,
                ),
            )

        same_previous = (NOW - timedelta(days=1)).astimezone(
            timezone(timedelta(hours=1))
        )
        same_latest = NOW.astimezone(timezone(timedelta(hours=-4)))
        cases = (
            changed_details(previous={"snapshot_id": "different-previous"}),
            changed_details(latest={"snapshot_id": "different-latest"}),
            changed_details(previous={"captured_at": NOW - timedelta(days=2)}),
            changed_details(latest={"captured_at": NOW + timedelta(days=1)}),
            changed_details(previous={"captured_at": same_previous}),
            changed_details(latest={"captured_at": same_latest}),
            changed_details(
                previous={"source": "other"},
                latest={"source": "other"},
                source="other",
            ),
            changed_details(
                previous={"source_version": "v2"},
                latest={"source_version": "v2"},
            ),
            changed_details(
                previous={"source_version": None},
                latest={"source_version": None},
            ),
        )
        for changed_price, changed_supply in cases:
            with self.subTest(context=changed_price.comparison_context):
                with self.assertRaises(ValueError):
                    MarketplaceChangeWorkspace(
                        MarketplaceChangeWorkspaceState.EMPTY,
                        window,
                        changed_price,
                        changed_supply,
                    )

        unversioned_window = replace(
            window,
            baseline=replace(window.baseline, source_version=None),
            current=replace(window.current, source_version=None),
        )
        with self.assertRaises(ValueError):
            MarketplaceChangeWorkspace(
                MarketplaceChangeWorkspaceState.EMPTY,
                unversioned_window,
                price,
                supply,
            )

    def test_exact_non_utc_and_none_version_context_is_accepted(self):
        previous = datetime(2026, 8, 1, 13, tzinfo=timezone(timedelta(hours=1)))
        latest = datetime(2026, 8, 2, 8, tzinfo=timezone(timedelta(hours=-4)))
        price = _price(
            PriceChangesDetailState.EMPTY,
            PriceChangesComparisonState.COMPLETE,
            unchanged=1,
        )
        supply = _supply(
            SupplyChangesDetailState.EMPTY,
            SupplyChangesComparisonState.COMPLETE,
            unchanged=1,
        )
        price = replace(
            price,
            previous_snapshot=replace(
                price.previous_snapshot,
                captured_at=previous,
                source_version=None,
            ),
            latest_snapshot=replace(
                price.latest_snapshot,
                captured_at=latest,
                source_version=None,
            ),
        )
        supply = replace(
            supply,
            previous_snapshot=replace(
                supply.previous_snapshot,
                captured_at=previous,
                source_version=None,
            ),
            latest_snapshot=replace(
                supply.latest_snapshot,
                captured_at=latest,
                source_version=None,
            ),
        )
        window = MarketplaceSnapshotWindow(
            MarketplaceSnapshotProvenance(
                "latest", latest, "discogs", None, MarketplaceDataStatus.COMPLETE
            ),
            MarketplaceSnapshotProvenance(
                "previous", previous, "discogs", None, MarketplaceDataStatus.COMPLETE
            ),
        )
        workspace = MarketplaceChangeWorkspace(
            MarketplaceChangeWorkspaceState.EMPTY,
            window,
            price,
            supply,
        )
        self.assertIs(workspace.price_changes.comparison_context.previous_captured_at, previous)
        self.assertIs(workspace.supply_changes.comparison_context.latest_captured_at, latest)

    def test_workspace_without_selected_pair_rejects_retained_error_context(self):
        previous_price, latest_price = _price_snapshots()
        previous_supply, latest_supply = _supply_snapshots()
        with self.assertRaisesRegex(ValueError, "provenance"):
            PriceChangesDetailViewModel(
                PriceChangesDetailState.ERROR,
                "Safe failure.",
                PriceChangesComparisonState.FAILED,
                previous_snapshot=previous_price,
                latest_snapshot=latest_price,
                source="discogs",
                listing_change_count=0,
                release_change_count=0,
                unchanged_count=0,
                incomparable_count=0,
            )
        with self.assertRaisesRegex(ValueError, "provenance"):
            SupplyChangesDetailViewModel(
                SupplyChangesDetailState.ERROR,
                "Safe failure.",
                SupplyChangesComparisonState.FAILED,
                previous_snapshot=previous_supply,
                latest_snapshot=latest_supply,
                source="discogs",
                change_count=0,
                unchanged_count=0,
                incomparable_count=0,
            )

    def test_hostile_values_do_not_enter_canonical_or_renderer_state_copy(self):
        sentinels = (
            "TOKEN-secret",
            "SELECT personal_notes FROM private_table",
            "/private/live.sqlite",
            "provider-payload",
            "PERSONAL-NOTE",
        )
        for sentinel in sentinels:
            price = PriceChangesDetailViewModel(
                PriceChangesDetailState.ERROR,
                sentinel,
                PriceChangesComparisonState.FAILED,
                listing_change_count=0,
                release_change_count=0,
                unchanged_count=0,
                incomparable_count=0,
            )
            supply = SupplyChangesDetailViewModel(
                SupplyChangesDetailState.ERROR,
                sentinel,
                SupplyChangesComparisonState.FAILED,
                change_count=0,
                unchanged_count=0,
                incomparable_count=0,
            )
            rendered_price = DesktopPriceChangesRenderer().render(price)
            rendered_supply = DesktopSupplyChangesRenderer().render(supply)
            public = repr(
                (
                    price.state_copy,
                    supply.state_copy,
                    rendered_price.headline,
                    rendered_price.summary,
                    rendered_price.counts,
                    rendered_supply.headline,
                    rendered_supply.summary,
                    rendered_supply.counts,
                    marketplace_outcome_state_kind(
                        MarketplaceChangePresentationOutcome.COMPARISON_FAILED
                    ),
                    _marketplace_outcome_copy(
                        MarketplaceChangePresentationOutcome.COMPARISON_FAILED
                    ),
                )
            )
            self.assertNotIn(sentinel, public)
            diagnostic_price = replace(price, summary="Safe failure.", diagnostics=(sentinel,))
            diagnostic_supply = replace(supply, summary="Safe failure.", diagnostics=(sentinel,))
            self.assertNotIn(sentinel, repr(diagnostic_price.state_copy))
            self.assertNotIn(sentinel, repr(diagnostic_supply.state_copy))


if __name__ == "__main__":
    unittest.main()
