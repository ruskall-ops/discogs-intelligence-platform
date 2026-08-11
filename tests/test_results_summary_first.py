from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from dip.app.current_release_metadata import CurrentReleaseMetadata
from dip.app.marketplace_change_workspace import MarketplaceChangeWorkspaceService
from dip.experience.desktop.app import App
from dip.experience.desktop.collection_explorer_renderer import DesktopCollectionExplorerRenderer
from dip.experience.desktop.price_changes_renderer import DesktopPriceChangesRenderer
from dip.experience.desktop.supply_changes_renderer import DesktopSupplyChangesRenderer
from dip.experience.explorer import (
    CollectionExplorerDestination,
    CollectionExplorerViewModelBuilder,
)
from dip.experience.price_changes import (
    PriceChangesDetailConsistencyError,
    PriceChangesDetailState,
    PriceChangesDetailViewModel,
    PriceChangesSnapshotViewModel,
    PriceResultGroupIdentifier,
    ReleasePriceChangeViewModel,
)
from dip.experience.results_presentation import (
    CURRENT_METADATA_EXPLANATION,
    EvidenceLimitationState,
    INCOMPLETE_EVIDENCE_LIMITATION,
    SAFE_ERROR_SUMMARY,
    SummaryCountIdentifier,
    safe_evidence_limitations,
)
from dip.experience.supply_changes import (
    SupplyChangesDetailConsistencyError,
    SupplyChangesDetailState,
    SupplyChangesDetailViewModel,
    SupplyChangesSnapshotViewModel,
    ReleaseSupplyChangeViewModel,
    SupplyResultGroupIdentifier,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    PriceChangeDelta,
    PriceChangesComparisonState,
    ReleasePriceChangeKind,
    ReleasePriceMetric,
    SupplyChangeKind,
    SupplyChangesComparisonState,
)
from tests.test_collection_explorer import available_homepage, health_service, hidden_service


NOW = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)


class _TextProbe:
    def __init__(self):
        self.insertions = []
        self.styles = {}

    def insert(self, index, value, tags=()):
        self.insertions.append((value, tags))

    def tag_configure(self, name, **values):
        self.styles[name] = values


class _History:
    def __init__(self, values):
        self.values = values
        self.calls = 0

    def all_snapshots(self):
        self.calls += 1
        return self.values


class _Metadata:
    def __init__(self, values=()):
        self.values = values
        self.calls = 0

    def metadata_for_release_ids(self, release_ids):
        self.calls += 1
        return self.values


def _observation(release_id, *, price, supply, currency="GBP", when=NOW):
    return MarketplaceReleaseObservation(
        release_id,
        when,
        MarketplaceDataStatus.COMPLETE,
        lowest_price=(
            None if price is None else MarketplaceMoney(Decimal(price), currency)
        ),
        num_for_sale=supply,
    )


def _snapshot(identifier, when, observations):
    return MarketplaceSnapshot(
        identifier,
        when,
        "discogs",
        MarketplaceDataStatus.COMPLETE,
        tuple(replace(value, observed_at=when) for value in observations),
        source_version="v1",
    )


def _workspace():
    previous = (
        _observation(1, price="10.00", supply=1),
        _observation(2, price="12.00", supply=3),
        _observation(3, price="7.00", supply=4),
        _observation(5, price="8.00", supply=2),
        _observation(6, price="9.00", supply=None, currency="GBP"),
        _observation(7, price="7.00", supply=0),
        _observation(8, price="8.00", supply=2),
    )
    latest = (
        _observation(1, price="12.50", supply=4),
        _observation(2, price="10.00", supply=1),
        _observation(3, price="7.00", supply=4),
        _observation(4, price="5.00", supply=2),
        _observation(6, price="9.00", supply=1, currency="USD"),
        _observation(7, price="7.00", supply=2),
        _observation(8, price="8.00", supply=0),
    )
    history = _History(
        (
            _snapshot("previous", NOW - timedelta(days=2), previous),
            _snapshot("latest", NOW, latest),
        )
    )
    metadata = _Metadata((CurrentReleaseMetadata(1, "Artist", "Title"),))
    return MarketplaceChangeWorkspaceService(history, metadata).build(), history, metadata


class SummaryFirstProjectionTest(unittest.TestCase):
    def test_state_aware_diagnostic_policy_is_exact_deterministic_and_immutable(self):
        allowlisted = (
            "Newer historical snapshots were skipped because they were not compatible with the current snapshot’s source contract.",
            "No earlier compatible Marketplace snapshot is available for comparison.",
            "Current collection metadata could not be loaded. Marketplace changes remain available and are identified by release ID.",
            "Failed or unavailable Marketplace snapshots were skipped.",
            "Equal-time Marketplace snapshots were skipped because they cannot establish direction.",
            "Marketplace snapshots from a different source were skipped.",
            "Marketplace snapshots with a different source version were skipped.",
        )
        metadata = (
            "Artist and title are current collection metadata provided for identification. "
            "They were not captured with the Marketplace snapshots."
        )
        unknown = "TOKEN provider SQL /private/db destination serialized-row GBP supply personal-note"
        cases = (
            (EvidenceLimitationState.ERROR, (unknown, *allowlisted), ()),
            (EvidenceLimitationState.INSUFFICIENT_HISTORY, (unknown, metadata), ()),
            (EvidenceLimitationState.INSUFFICIENT_HISTORY, allowlisted, (allowlisted[0], allowlisted[1], *allowlisted[3:])),
            (EvidenceLimitationState.PARTIAL, (), ()),
            (EvidenceLimitationState.PARTIAL, (unknown, unknown), (INCOMPLETE_EVIDENCE_LIMITATION,)),
            (EvidenceLimitationState.PARTIAL, (allowlisted[3], unknown, allowlisted[0]), (INCOMPLETE_EVIDENCE_LIMITATION, allowlisted[0], allowlisted[3])),
            (EvidenceLimitationState.INSUFFICIENT_DATA, (metadata, unknown), (INCOMPLETE_EVIDENCE_LIMITATION,)),
            (EvidenceLimitationState.SUCCESSFUL, (unknown, metadata), ()),
            (EvidenceLimitationState.SUCCESSFUL, (allowlisted[2], allowlisted[2]), (allowlisted[2],)),
            (EvidenceLimitationState.SUCCESSFUL, (allowlisted[1],), ()),
        )
        for state, diagnostics, expected in cases:
            with self.subTest(state=state, diagnostics=diagnostics):
                actual = safe_evidence_limitations(diagnostics, state=state)
                self.assertIsInstance(actual, tuple)
                self.assertEqual(actual, expected)
        for warning in allowlisted:
            expected = () if warning == allowlisted[1] else (warning,)
            self.assertEqual(
                safe_evidence_limitations((warning,), state=EvidenceLimitationState.PARTIAL),
                expected,
            )

    def test_price_groups_preserve_typed_values_order_and_safe_availability_copy(self):
        workspace, history, metadata = _workspace()
        detail = workspace.price_changes
        rendered = DesktopPriceChangesRenderer().render(detail)

        self.assertEqual(history.calls, 1)
        self.assertEqual(metadata.calls, 1)
        self.assertEqual(
            tuple(group.identifier for group in detail.result_groups),
            (
                PriceResultGroupIdentifier.INCREASED,
                PriceResultGroupIdentifier.DECREASED,
                PriceResultGroupIdentifier.UNCHANGED,
                PriceResultGroupIdentifier.INCOMPARABLE,
            ),
        )
        self.assertEqual(
            tuple(tuple(row.release_id for row in group.rows) for group in detail.result_groups),
            ((1,), (2,), (), (4, 5, 6)),
        )
        self.assertEqual(detail.release_changes[0].previous_value.amount, Decimal("10.00"))
        self.assertEqual(detail.release_changes[0].latest_value.amount, Decimal("12.50"))
        self.assertEqual(detail.release_changes[0].delta.amount, Decimal("2.50"))
        self.assertEqual(rendered.groups[0].rows[0].heading, "Artist — Title · Lowest Price")
        public = repr(rendered)
        self.assertNotIn("Newly Available", public)
        self.assertNotIn("No Longer Available", public)
        self.assertNotIn("entered the Marketplace", public)
        self.assertNotIn("left the Marketplace", public)
        self.assertNotIn("Listing changes", rendered.counts)

    def test_supply_groups_preserve_zero_transitions_missing_evidence_and_delta(self):
        workspace, _, _ = _workspace()
        detail = workspace.supply_changes
        rendered = DesktopSupplyChangesRenderer().render(detail)

        self.assertEqual(
            tuple(group.identifier for group in detail.result_groups),
            (
                SupplyResultGroupIdentifier.INCREASED,
                SupplyResultGroupIdentifier.DECREASED,
                SupplyResultGroupIdentifier.UNCHANGED,
                SupplyResultGroupIdentifier.BECAME_AVAILABLE,
                SupplyResultGroupIdentifier.NO_COPIES_OBSERVED,
                SupplyResultGroupIdentifier.INCOMPARABLE,
            ),
        )
        self.assertEqual(detail.changes[0].delta, 3)
        self.assertEqual(detail.changes[1].delta, -2)
        incomparable = next(
            group for group in detail.result_groups
            if group.identifier is SupplyResultGroupIdentifier.INCOMPARABLE
        )
        self.assertIsNone(incomparable.rows[-1].previous_supply)
        self.assertIsNone(incomparable.rows[-1].delta)
        self.assertIn("Became available for sale", repr(rendered.groups))
        self.assertIn("No copies observed for sale", repr(rendered.groups))

    def test_context_metadata_provenance_and_immutability_are_separate(self):
        workspace, _, _ = _workspace()
        price = workspace.price_changes
        supply = workspace.supply_changes
        rendered_price = DesktopPriceChangesRenderer().render(price)
        rendered_supply = DesktopSupplyChangesRenderer().render(supply)

        self.assertEqual(price.comparison_context, supply.comparison_context)
        self.assertEqual(rendered_price.context, rendered_supply.context)
        self.assertIn("Previous snapshot capture time", rendered_price.context)
        self.assertNotIn("snapshot ID", rendered_price.context.lower())
        self.assertIn("Previous snapshot ID: previous", rendered_price.provenance)
        self.assertEqual(price.metadata_explanation, CURRENT_METADATA_EXPLANATION)
        self.assertEqual(supply.metadata_explanation, CURRENT_METADATA_EXPLANATION)
        self.assertEqual(price.release_changes[-1].display_label, "Release 6")
        with self.assertRaises(FrozenInstanceError):
            price.result_groups[0].count = 99  # type: ignore[misc]
        detached = tuple(price.result_groups[0].rows)
        self.assertEqual(detached, price.result_groups[0].rows)

    def test_projection_is_deterministic_for_realistic_volume(self):
        previous = tuple(
            _observation(value, price="10.00", supply=1)
            for value in range(1, 501)
        )
        latest = tuple(
            _observation(value, price="11.00", supply=2)
            for value in range(1, 501)
        )
        service = MarketplaceChangeWorkspaceService(
            _History(
                (
                    _snapshot("previous", NOW - timedelta(days=1), previous),
                    _snapshot("latest", NOW, latest),
                )
            ),
            _Metadata(),
        )
        first = service.build()
        second = service.build()
        self.assertEqual(first.price_changes.result_groups, second.price_changes.result_groups)
        self.assertEqual(first.supply_changes.result_groups, second.supply_changes.result_groups)
        self.assertEqual(len(first.price_changes.result_groups[0].rows), 500)
        self.assertEqual(len(first.supply_changes.result_groups[0].rows), 500)

    def test_price_observation_transition_groups_are_typed_and_exclusive(self):
        previous = PriceChangesSnapshotViewModel(
            "previous", NOW - timedelta(days=1), "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        latest = PriceChangesSnapshotViewModel(
            "latest", NOW, "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        available = ReleasePriceChangeViewModel(
            1, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.NEWLY_AVAILABLE,
            None, MarketplaceMoney(Decimal("10.00"), "GBP"), None,
            "previous", "latest", ("A typed latest observation is available.",),
        )
        unavailable = ReleasePriceChangeViewModel(
            2, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.NO_LONGER_AVAILABLE,
            MarketplaceMoney(Decimal("12.00"), "GBP"), None, None,
            "previous", "latest", ("A typed previous observation is available.",),
        )
        detail = PriceChangesDetailViewModel(
            PriceChangesDetailState.AVAILABLE, "Typed transitions.", PriceChangesComparisonState.COMPLETE,
            previous, latest, "discogs", 0, 2, 0, 0,
            release_changes=(available, unavailable),
        )
        self.assertEqual(
            tuple(group.identifier for group in detail.result_groups),
            (
                PriceResultGroupIdentifier.OBSERVATION_AVAILABLE,
                PriceResultGroupIdentifier.OBSERVATION_UNAVAILABLE,
            ),
        )
        grouped = tuple(row for group in detail.result_groups for row in group.rows)
        self.assertEqual(grouped, detail.release_changes)
        self.assertEqual(len({id(row) for row in grouped}), len(detail.release_changes))
        self.assertEqual(sum(group.count for group in detail.result_groups), 2)

    def test_every_supply_row_is_grouped_once_and_counts_reconcile(self):
        workspace, _, _ = _workspace()
        detail = workspace.supply_changes
        grouped = tuple(row for group in detail.result_groups for row in group.rows)
        self.assertEqual(
            sorted(row.release_id for row in grouped),
            sorted(row.release_id for row in detail.changes),
        )
        self.assertEqual(len({id(row) for row in grouped}), len(detail.changes))
        self.assertEqual(
            sum(group.count for group in detail.result_groups),
            detail.change_count + detail.unchanged_count,
        )

    def test_error_models_reject_all_provenance_and_sanitize_diagnostics(self):
        price_previous = PriceChangesSnapshotViewModel(
            "previous", NOW - timedelta(days=1), "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        price_latest = PriceChangesSnapshotViewModel(
            "latest", NOW, "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        supply_previous = SupplyChangesSnapshotViewModel(
            "previous", NOW - timedelta(days=1), "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        supply_latest = SupplyChangesSnapshotViewModel(
            "latest", NOW, "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        price_args = dict(
            state=PriceChangesDetailState.ERROR, summary="Safe failure.",
            comparison_state=PriceChangesComparisonState.FAILED,
            listing_change_count=0, release_change_count=0, unchanged_count=0,
            incomparable_count=0,
        )
        supply_args = dict(
            state=SupplyChangesDetailState.ERROR, summary="Safe failure.",
            comparison_state=SupplyChangesComparisonState.FAILED,
            change_count=0, unchanged_count=0, incomparable_count=0,
        )
        for retained in (
            {"previous_snapshot": price_previous},
            {"latest_snapshot": price_latest},
            {"previous_snapshot": price_previous, "latest_snapshot": price_latest},
            {"source": "discogs"},
        ):
            with self.assertRaises(PriceChangesDetailConsistencyError):
                PriceChangesDetailViewModel(**price_args, **retained)
        for retained in (
            {"previous_snapshot": supply_previous},
            {"latest_snapshot": supply_latest},
            {"previous_snapshot": supply_previous, "latest_snapshot": supply_latest},
            {"source": "discogs"},
        ):
            with self.assertRaises(SupplyChangesDetailConsistencyError):
                SupplyChangesDetailViewModel(**supply_args, **retained)

        sentinels = (
            "TOKEN-secret", "provider-body", "SELECT * FROM private_table",
            "/private/live.sqlite", "/Users/private/export.csv", '{"row":"secret"}',
            "unknown-diagnostic-id", "arbitrary message details", "GBP 123.45",
            "supply=987", "personal note",
        )
        price = PriceChangesDetailViewModel(**price_args, diagnostics=sentinels)
        supply = SupplyChangesDetailViewModel(**supply_args, diagnostics=sentinels)
        self.assertEqual(price.diagnostics, ())
        self.assertEqual(supply.diagnostics, ())
        rendered_price = DesktopPriceChangesRenderer().render(price)
        rendered_supply = DesktopSupplyChangesRenderer().render(supply)
        renderer = DesktopCollectionExplorerRenderer()
        price_section = renderer._price(SimpleNamespace(
            price_changes=price, marketplace_change_outcome=None
        ))
        supply_section = renderer._supply(SimpleNamespace(
            supply_changes=supply, marketplace_change_outcome=None
        ))
        public = repr((price, supply, rendered_price, rendered_supply, price_section, supply_section))
        for sentinel in sentinels:
            self.assertNotIn(sentinel, public)

        def recursive_values(value):
            yield value
            if is_dataclass(value):
                for item in fields(value):
                    yield from recursive_values(getattr(value, item.name))
            elif isinstance(value, (tuple, list)):
                for item in value:
                    yield from recursive_values(item)

        for sentinel in sentinels:
            hostile_price = PriceChangesDetailViewModel(
                **{**price_args, "summary": sentinel}, diagnostics=(sentinel,)
            )
            hostile_supply = SupplyChangesDetailViewModel(
                **{**supply_args, "summary": sentinel}, diagnostics=(sentinel,)
            )
            self.assertEqual(hostile_price.summary, SAFE_ERROR_SUMMARY)
            self.assertEqual(hostile_supply.summary, SAFE_ERROR_SUMMARY)
            self.assertNotIn(sentinel, repr((hostile_price, hostile_supply)))
            self.assertNotIn(
                sentinel,
                " ".join(str(value) for value in recursive_values((hostile_price, hostile_supply))),
            )
            self.assertEqual(replace(hostile_price, summary=sentinel).summary, SAFE_ERROR_SUMMARY)
            self.assertEqual(replace(hostile_supply, summary=sentinel).summary, SAFE_ERROR_SUMMARY)

    def test_final_explorer_price_and_supply_state_matrix(self):
        price_previous = PriceChangesSnapshotViewModel(
            "previous", NOW - timedelta(days=1), "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        price_latest = PriceChangesSnapshotViewModel(
            "latest", NOW, "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        supply_previous = SupplyChangesSnapshotViewModel(
            "previous", NOW - timedelta(days=1), "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        supply_latest = SupplyChangesSnapshotViewModel(
            "latest", NOW, "discogs", MarketplaceDataStatus.COMPLETE, "v1"
        )
        price_increased = ReleasePriceChangeViewModel(
            1, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.INCREASED,
            MarketplaceMoney(Decimal("10"), "GBP"), MarketplaceMoney(Decimal("11"), "GBP"),
            PriceChangeDelta(Decimal("1"), "GBP"),
            "previous", "latest", ("Observed price evidence.",), display_label="Release 1",
        )
        price_incomparable = ReleasePriceChangeViewModel(
            2, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.INCOMPARABLE,
            None, MarketplaceMoney(Decimal("12"), "GBP"), None,
            "previous", "latest", ("Observed incomplete price evidence.",), display_label="Release 2",
        )
        price_observation_available = ReleasePriceChangeViewModel(
            3, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.NEWLY_AVAILABLE,
            None, MarketplaceMoney(Decimal("9"), "GBP"), None,
            "previous", "latest", ("A latest price observation is available.",), display_label="Release 3",
        )
        price_observation_unavailable = ReleasePriceChangeViewModel(
            4, ReleasePriceMetric.LOWEST_PRICE, ReleasePriceChangeKind.NO_LONGER_AVAILABLE,
            MarketplaceMoney(Decimal("8"), "GBP"), None, None,
            "previous", "latest", ("A previous price observation is available.",), display_label="Release 4",
        )
        supply_increased = ReleaseSupplyChangeViewModel(
            1, 1, 3, 2, SupplyChangeKind.INCREASED,
            "previous", "latest", ("Observed supply evidence.",), display_label="Release 1",
        )
        supply_incomparable = ReleaseSupplyChangeViewModel(
            2, None, 0, None, SupplyChangeKind.INCOMPARABLE,
            "previous", "latest", ("Observed incomplete supply evidence.",), display_label="Release 2",
        )
        supply_became_available = ReleaseSupplyChangeViewModel(
            3, 0, 2, 2, SupplyChangeKind.NEWLY_AVAILABLE,
            "previous", "latest", ("Explicit zero-to-positive supply evidence.",), display_label="Release 3",
        )
        supply_no_copies = ReleaseSupplyChangeViewModel(
            4, 2, 0, -2, SupplyChangeKind.NO_LONGER_AVAILABLE,
            "previous", "latest", ("Explicit positive-to-zero supply evidence.",), display_label="Release 4",
        )
        hostile = "TOKEN-private-summary"

        def price(state, comparison, *, rows=(), unchanged=0, diagnostics=()):
            paired = state not in {PriceChangesDetailState.INSUFFICIENT_HISTORY, PriceChangesDetailState.ERROR}
            return PriceChangesDetailViewModel(
                state, hostile if state is PriceChangesDetailState.ERROR else "Factual summary.", comparison,
                price_previous if paired else None, price_latest if paired else None,
                "discogs" if paired else None, 0, len(rows), unchanged,
                sum(row.change_kind is ReleasePriceChangeKind.INCOMPARABLE for row in rows),
                release_changes=rows, diagnostics=diagnostics,
            )

        def supply(state, comparison, *, rows=(), unchanged=0, diagnostics=()):
            paired = state not in {SupplyChangesDetailState.INSUFFICIENT_HISTORY, SupplyChangesDetailState.ERROR}
            return SupplyChangesDetailViewModel(
                state, hostile if state is SupplyChangesDetailState.ERROR else "Factual summary.", comparison,
                supply_previous if paired else None, supply_latest if paired else None,
                "discogs" if paired else None, len(rows), unchanged,
                sum(row.change_kind.name == "INCOMPARABLE" for row in rows), rows, diagnostics,
            )

        price_cases = (
            (price(PriceChangesDetailState.AVAILABLE, PriceChangesComparisonState.COMPLETE, rows=(price_increased, price_observation_available, price_observation_unavailable), diagnostics=(hostile,)), "Results available", True, True, False),
            (price(PriceChangesDetailState.PARTIAL, PriceChangesComparisonState.PARTIAL, rows=(price_incomparable,), diagnostics=(hostile,)), "Partial evidence", True, True, True),
            (price(PriceChangesDetailState.EMPTY, PriceChangesComparisonState.COMPLETE, unchanged=1, diagnostics=(hostile,)), "No changes observed", True, True, False),
            (price(PriceChangesDetailState.EMPTY, PriceChangesComparisonState.COMPLETE, diagnostics=(hostile,)), "No matching results", True, False, False),
            (price(PriceChangesDetailState.INSUFFICIENT_HISTORY, PriceChangesComparisonState.INSUFFICIENT_HISTORY, diagnostics=(hostile,)), "More history required", False, False, False),
            (price(PriceChangesDetailState.INSUFFICIENT_DATA, PriceChangesComparisonState.INSUFFICIENT_DATA, rows=(price_incomparable,), diagnostics=(hostile,)), "No comparable facts", True, True, True),
            (price(PriceChangesDetailState.INSUFFICIENT_DATA, PriceChangesComparisonState.INSUFFICIENT_DATA), "No comparable facts", True, False, False),
            (price(PriceChangesDetailState.ERROR, PriceChangesComparisonState.FAILED, diagnostics=(hostile,)), "Results could not be displayed", False, False, False),
        )
        supply_cases = (
            (supply(SupplyChangesDetailState.AVAILABLE, SupplyChangesComparisonState.COMPLETE, rows=(supply_increased, supply_became_available, supply_no_copies), diagnostics=(hostile,)), "Results available", True, True, False),
            (supply(SupplyChangesDetailState.PARTIAL, SupplyChangesComparisonState.PARTIAL, rows=(supply_incomparable,), diagnostics=(hostile,)), "Partial evidence", True, True, True),
            (supply(SupplyChangesDetailState.EMPTY, SupplyChangesComparisonState.COMPLETE, unchanged=1, diagnostics=(hostile,)), "No changes observed", True, True, False),
            (supply(SupplyChangesDetailState.EMPTY, SupplyChangesComparisonState.COMPLETE, diagnostics=(hostile,)), "No matching results", True, False, False),
            (supply(SupplyChangesDetailState.INSUFFICIENT_HISTORY, SupplyChangesComparisonState.INSUFFICIENT_HISTORY, diagnostics=(hostile,)), "More history required", False, False, False),
            (supply(SupplyChangesDetailState.INSUFFICIENT_DATA, SupplyChangesComparisonState.INSUFFICIENT_DATA, rows=(supply_incomparable,), diagnostics=(hostile,)), "No comparable facts", True, True, True),
            (supply(SupplyChangesDetailState.INSUFFICIENT_DATA, SupplyChangesComparisonState.INSUFFICIENT_DATA), "No comparable facts", True, False, False),
            (supply(SupplyChangesDetailState.ERROR, SupplyChangesComparisonState.FAILED, diagnostics=(hostile,)), "Results could not be displayed", False, False, False),
        )
        expected_context = (
            "Previous snapshot capture time: 2026-08-02T12:00+00:00\n"
            "Latest snapshot capture time: 2026-08-03T12:00+00:00\n"
            "Source: discogs\nSource version: v1"
        )
        expected_provenance = (
            "Previous snapshot ID: previous\nPrevious status: Complete\n"
            "Latest snapshot ID: latest\nLatest status: Complete\n"
        )
        canonical_bodies = {
            "available": "Results use the comparison shown below.",
            "partial": "Some supplied evidence was incomplete; available comparisons remain shown.",
            "no_changes": "Comparable values were unchanged between these snapshots.",
            "empty": "The calculation completed, but no detail rows met this result’s criteria.",
            "insufficient_history": "Two compatible snapshots captured at different times are required.",
            "insufficient_data_rows": "A compatible snapshot pair exists, but it contains no comparable facts for this result.",
            "insufficient_data_empty": "A compatible snapshot pair exists, but it contains no comparable facts for this result.",
            "error": "Saved data was not changed. Previous results remain available where shown.",
        }
        expected_sections = {
            "available": ("state", "context", "counts", "groups", "metadata", "provenance"),
            "partial": ("state", "context", "counts", "limitations", "groups", "metadata", "provenance"),
            "no_changes": ("state", "context", "counts", "groups", "provenance"),
            "empty": ("state", "context", "counts", "provenance"),
            "insufficient_history": ("state",),
            "insufficient_data_rows": ("state", "context", "counts", "limitations", "groups", "metadata", "provenance"),
            "insufficient_data_empty": ("state", "context", "provenance"),
            "error": ("state",),
        }
        keys = tuple(expected_sections)
        price_count_lines = {
            "available": ("Increased: 1", "Decreased: 0", "Unchanged: 0", "Price observation became available: 1", "Price observation no longer available: 1", "Incomparable: 0"),
            "partial": ("Increased: 0", "Decreased: 0", "Unchanged: 0", "Price observation became available: 0", "Price observation no longer available: 0", "Incomparable: 1"),
            "no_changes": ("Increased: 0", "Decreased: 0", "Unchanged: 1", "Price observation became available: 0", "Price observation no longer available: 0", "Incomparable: 0"),
            "empty": ("Increased: 0", "Decreased: 0", "Unchanged: 0", "Price observation became available: 0", "Price observation no longer available: 0", "Incomparable: 0"),
            "insufficient_history": (),
            "insufficient_data_rows": ("Incomparable changes: 1",),
            "insufficient_data_empty": (),
            "error": (),
        }
        supply_count_lines = {
            "available": ("Increased: 1", "Decreased: 0", "Unchanged: 0", "Became available for sale: 1", "No copies observed for sale: 1", "Incomparable: 0"),
            "partial": ("Increased: 0", "Decreased: 0", "Unchanged: 0", "Became available for sale: 0", "No copies observed for sale: 0", "Incomparable: 1"),
            "no_changes": ("Increased: 0", "Decreased: 0", "Unchanged: 1", "Became available for sale: 0", "No copies observed for sale: 0", "Incomparable: 0"),
            "empty": ("Increased: 0", "Decreased: 0", "Unchanged: 0", "Became available for sale: 0", "No copies observed for sale: 0", "Incomparable: 0"),
            "insufficient_history": (),
            "insufficient_data_rows": ("Incomparable releases: 1",),
            "insufficient_data_empty": (),
            "error": (),
        }
        price_expected_groups = {
            "available": (("Increased", 1, (1,)), ("Price observation became available", 1, (3,)), ("Price observation no longer available", 1, (4,))),
            "partial": (("Incomparable", 1, (2,)),),
            "no_changes": (("Unchanged", 1, ()),),
            "empty": (),
            "insufficient_history": (),
            "insufficient_data_rows": (("Incomparable", 1, (2,)),),
            "insufficient_data_empty": (),
            "error": (),
        }
        supply_expected_groups = {
            **price_expected_groups,
            "available": (("Increased", 1, (1,)), ("Became available for sale", 1, (3,)), ("No copies observed for sale", 1, (4,))),
        }
        limitation_block = "Evidence limitations\n• " + INCOMPLETE_EVIDENCE_LIMITATION
        metadata_block = "Current catalogue metadata\n" + CURRENT_METADATA_EXPLANATION
        context_block = "Comparison period\n" + expected_context

        def final_body(*blocks):
            return "\n\n".join(blocks)

        state_blocks = {
            key: f"{heading}\n{canonical_bodies[key]}"
            for key, heading in (
                ("available", "Results available"), ("partial", "Partial evidence"),
                ("no_changes", "No changes observed"), ("empty", "No matching results"),
                ("insufficient_history", "More history required"),
                ("insufficient_data_rows", "No comparable facts"),
                ("insufficient_data_empty", "No comparable facts"),
                ("error", "Results could not be displayed"),
            )
        }
        provenance_blocks = {
            "complete": "Detailed provenance\n" + expected_provenance + "Comparison state: Complete",
            "partial": "Detailed provenance\n" + expected_provenance + "Comparison state: Partial",
            "insufficient": "Detailed provenance\n" + expected_provenance + "Comparison state: Insufficient Data",
        }
        price_increased_block = "\n".join((
            "Increased (1)", "", "Release 1 · Lowest Price", "Release ID: 1",
            "Classification: Increased", "Previous value: GBP 10", "Latest value: GBP 11",
            "Delta: GBP +1", "Evidence:", "• Observed price evidence.",
        ))
        price_available_block = "\n".join((
            "Price observation became available (1)", "", "Release 3 · Lowest Price",
            "Release ID: 3", "Classification: Price observation became available",
            "Previous value: Unavailable", "Latest value: GBP 9", "Delta: Unavailable",
            "Evidence:", "• A latest price observation is available.",
        ))
        price_unavailable_block = "\n".join((
            "Price observation no longer available (1)", "", "Release 4 · Lowest Price",
            "Release ID: 4", "Classification: Price observation no longer available",
            "Previous value: GBP 8", "Latest value: Unavailable", "Delta: Unavailable",
            "Evidence:", "• A previous price observation is available.",
        ))
        price_incomparable_block = "\n".join((
            "Incomparable (1)", "", "Release 2 · Lowest Price", "Release ID: 2",
            "Classification: Incomparable", "Previous value: Unavailable", "Latest value: GBP 12",
            "Delta: Unavailable", "Evidence:", "• Observed incomplete price evidence.",
        ))
        supply_increased_block = "\n".join((
            "Increased (1)", "", "Release 1 — Increased", "Release ID: 1",
            "Classification: Increased", "Previous supply: 1", "Latest supply: 3",
            "Delta: +2", "Evidence:", "• Observed supply evidence.",
        ))
        supply_available_block = "\n".join((
            "Became available for sale (1)", "", "Release 3 — Became available for sale",
            "Release ID: 3", "Classification: Became available for sale", "Previous supply: 0",
            "Latest supply: 2", "Delta: +2", "Evidence:",
            "• Explicit zero-to-positive supply evidence.",
        ))
        supply_unavailable_block = "\n".join((
            "No copies observed for sale (1)", "", "Release 4 — No copies observed for sale",
            "Release ID: 4", "Classification: No copies observed for sale", "Previous supply: 2",
            "Latest supply: 0", "Delta: -2", "Evidence:",
            "• Explicit positive-to-zero supply evidence.",
        ))
        supply_incomparable_block = "\n".join((
            "Incomparable (1)", "", "Release 2 — Incomparable", "Release ID: 2",
            "Classification: Incomparable", "Previous supply: Unavailable", "Latest supply: 0",
            "Delta: Unavailable", "Evidence:", "• Observed incomplete supply evidence.",
        ))
        price_expected_bodies = {
            "available": final_body(state_blocks["available"], context_block, "Summary\n" + "\n".join(price_count_lines["available"]), price_increased_block, price_available_block, price_unavailable_block, metadata_block, provenance_blocks["complete"]),
            "partial": final_body(state_blocks["partial"], context_block, "Summary\n" + "\n".join(price_count_lines["partial"]), limitation_block, price_incomparable_block, metadata_block, provenance_blocks["partial"]),
            "no_changes": final_body(state_blocks["no_changes"], context_block, "Summary\n" + "\n".join(price_count_lines["no_changes"]), "Unchanged (1)", provenance_blocks["complete"]),
            "empty": final_body(state_blocks["empty"], context_block, "Summary\n" + "\n".join(price_count_lines["empty"]), provenance_blocks["complete"]),
            "insufficient_history": state_blocks["insufficient_history"],
            "insufficient_data_rows": final_body(state_blocks["insufficient_data_rows"], context_block, "Summary\nIncomparable changes: 1", limitation_block, price_incomparable_block, metadata_block, provenance_blocks["insufficient"]),
            "insufficient_data_empty": final_body(state_blocks["insufficient_data_empty"], context_block, provenance_blocks["insufficient"]),
            "error": state_blocks["error"],
        }
        supply_expected_bodies = {
            "available": final_body(state_blocks["available"], context_block, "Summary\n" + "\n".join(supply_count_lines["available"]), supply_increased_block, supply_available_block, supply_unavailable_block, metadata_block, provenance_blocks["complete"]),
            "partial": final_body(state_blocks["partial"], context_block, "Summary\n" + "\n".join(supply_count_lines["partial"]), limitation_block, supply_incomparable_block, metadata_block, provenance_blocks["partial"]),
            "no_changes": final_body(state_blocks["no_changes"], context_block, "Summary\n" + "\n".join(supply_count_lines["no_changes"]), "Unchanged (1)", provenance_blocks["complete"]),
            "empty": final_body(state_blocks["empty"], context_block, "Summary\n" + "\n".join(supply_count_lines["empty"]), provenance_blocks["complete"]),
            "insufficient_history": state_blocks["insufficient_history"],
            "insufficient_data_rows": final_body(state_blocks["insufficient_data_rows"], context_block, "Summary\nIncomparable releases: 1", limitation_block, supply_incomparable_block, metadata_block, provenance_blocks["insufficient"]),
            "insufficient_data_empty": final_body(state_blocks["insufficient_data_empty"], context_block, provenance_blocks["insufficient"]),
            "error": state_blocks["error"],
        }
        price_count_ids = {
            key: value for key, value in zip(keys, (
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.PRICE_OBSERVATION_AVAILABLE, SummaryCountIdentifier.PRICE_OBSERVATION_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.PRICE_OBSERVATION_AVAILABLE, SummaryCountIdentifier.PRICE_OBSERVATION_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.PRICE_OBSERVATION_AVAILABLE, SummaryCountIdentifier.PRICE_OBSERVATION_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.PRICE_OBSERVATION_AVAILABLE, SummaryCountIdentifier.PRICE_OBSERVATION_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (), (SummaryCountIdentifier.INCOMPARABLE,), (), (),
            ))
        }
        supply_count_ids = {
            key: value for key, value in zip(keys, (
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.SUPPLY_AVAILABLE, SummaryCountIdentifier.SUPPLY_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.SUPPLY_AVAILABLE, SummaryCountIdentifier.SUPPLY_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.SUPPLY_AVAILABLE, SummaryCountIdentifier.SUPPLY_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (SummaryCountIdentifier.INCREASED, SummaryCountIdentifier.DECREASED, SummaryCountIdentifier.UNCHANGED, SummaryCountIdentifier.SUPPLY_AVAILABLE, SummaryCountIdentifier.SUPPLY_UNAVAILABLE, SummaryCountIdentifier.INCOMPARABLE),
                (), (SummaryCountIdentifier.INCOMPARABLE,), (), (),
            ))
        }
        renderer = DesktopCollectionExplorerRenderer()
        homepage = available_homepage()
        health = health_service().detail_for_homepage(homepage)
        hidden = hidden_service().detail_for_homepage(homepage)

        def section_names(body):
            names = ["state"]
            markers = (
                ("Comparison period", "context"), ("Summary", "counts"),
                ("Evidence limitations", "limitations"),
                ("Increased (", "groups"), ("Decreased (", "groups"),
                ("Unchanged (", "groups"),
                ("Incomparable (", "groups"),
                ("Price observation became available (", "groups"),
                ("Price observation no longer available (", "groups"),
                ("Became available for sale (", "groups"),
                ("No copies observed for sale (", "groups"),
                ("Current catalogue metadata", "metadata"),
                ("Detailed provenance", "provenance"),
            )
            found = sorted(
                (body.index(marker), name) for marker, name in markers if marker in body
            )
            names.extend(name for _, name in found if name not in names)
            return tuple(names)

        for destination, cases, selected in (
            ("price", price_cases, CollectionExplorerDestination.PRICE_CHANGES),
            ("supply", supply_cases, CollectionExplorerDestination.SUPPLY_CHANGES),
        ):
            for key, (detail, heading, has_context, has_group, has_limitation) in zip(keys, cases):
                with self.subTest(destination=destination, case=key):
                    other = supply_cases[3][0] if destination == "price" else price_cases[3][0]
                    explorer = CollectionExplorerViewModelBuilder().build(
                        homepage, health, hidden,
                        price_changes=detail if destination == "price" else other,
                        supply_changes=detail if destination == "supply" else other,
                        selected_destination=selected,
                    )
                    target_rows = detail.release_changes if destination == "price" else detail.changes
                    target_identity = target_rows
                    target_before = tuple(target_rows)
                    price_identity = explorer.price_changes.release_changes
                    supply_identity = explorer.supply_changes.changes
                    explorer_before = replace(explorer)

                    with (
                        patch("dip.app.marketplace_change_workspace.MarketplaceChangeWorkspaceService.build", side_effect=AssertionError("render queried Marketplace workspace")),
                        patch("dip.app.marketplace_history.MarketplaceHistoryQueryService.all_snapshots", side_effect=AssertionError("render queried Marketplace History")),
                        patch("dip.intelligence.engine.IntelligenceEngine.execute", side_effect=AssertionError("render executed intelligence")),
                        patch("dip.marketplace_intelligence.price_changes.PriceChangesModule.calculate_pair", side_effect=AssertionError("render calculated Price changes")),
                        patch("dip.marketplace_intelligence.supply_changes.SupplyChangesModule.calculate_pair", side_effect=AssertionError("render calculated Supply changes")),
                    ):
                        rendered = renderer.render(explorer)
                    section = next(value for value in rendered.sections if value.destination is selected)
                    body = section.body
                    expected_body = price_expected_bodies[key] if destination == "price" else supply_expected_bodies[key]
                    self.assertEqual(body, expected_body)
                    self.assertEqual(explorer, explorer_before)
                    self.assertIs(target_rows, target_identity)
                    self.assertIs(explorer.price_changes.release_changes, price_identity)
                    self.assertIs(explorer.supply_changes.changes, supply_identity)
                    self.assertEqual(target_rows, target_before)
                    self.assertEqual(section_names(body), expected_sections[key])
                    self.assertEqual(body.count(heading), 1)
                    self.assertEqual(detail.state_copy.body, canonical_bodies[key])
                    self.assertEqual(body.count(canonical_bodies[key]), 1)
                    self.assertNotIn(f"\n{detail.state.value}\n", f"\n{body}\n")
                    for legacy in ("Available Price Changes", "Available Supply Changes", "No Price Changes", "No Supply Changes"):
                        self.assertNotIn(legacy, body)
                    self.assertEqual("Comparison period" in body, has_context)
                    self.assertEqual(expected_context in body, has_context)
                    self.assertEqual(body.count(expected_context), 1 if has_context else 0)
                    self.assertEqual("Evidence limitations" in body, has_limitation)
                    self.assertEqual("Some releases could not be compared because Marketplace evidence was incomplete." in body, has_limitation)
                    self.assertEqual(
                        detail.diagnostics,
                        (INCOMPLETE_EVIDENCE_LIMITATION,) if has_limitation else (),
                    )
                    self.assertEqual("Detailed provenance" in body, has_context)
                    if has_context:
                        self.assertIn(expected_provenance, body)
                        self.assertIn(f"Comparison state: {detail.comparison_state.value.replace('_', ' ').title()}", body)
                        complete_provenance = expected_provenance + f"Comparison state: {detail.comparison_state.value.replace('_', ' ').title()}"
                        self.assertEqual(body.count(complete_provenance), 1)
                    self.assertEqual("Current catalogue metadata" in body, bool(target_rows))
                    self.assertEqual(body.count(CURRENT_METADATA_EXPLANATION), 1 if target_rows else 0)
                    self.assertEqual("Release ID: 1" in body or "Release ID: 2" in body, bool(target_rows))
                    self.assertEqual(any(f"{name} (" in body for name in ("Increased", "Unchanged", "Incomparable")), has_group)
                    count_lines = price_count_lines[key] if destination == "price" else supply_count_lines[key]
                    count_ids = price_count_ids[key] if destination == "price" else supply_count_ids[key]
                    group_expectation = price_expected_groups[key] if destination == "price" else supply_expected_groups[key]
                    self.assertEqual(tuple(value.identifier for value in detail.summary_counts), count_ids)
                    self.assertEqual(
                        tuple(f"{value.label}: {value.value}" for value in detail.summary_counts),
                        count_lines,
                    )
                    if count_lines:
                        self.assertEqual(
                            body.split("Summary\n", 1)[1].split("\n\n", 1)[0],
                            "\n".join(count_lines),
                        )
                    self.assertEqual(
                        tuple((group.heading, group.count, tuple(row.release_id for row in group.rows)) for group in detail.result_groups),
                        group_expectation,
                    )
                    for group_heading, group_count, row_ids in group_expectation:
                        self.assertEqual(body.count(f"{group_heading} ({group_count})"), 1)
                        for row_id in row_ids:
                            self.assertEqual(body.count(f"Release ID: {row_id}"), 1)
                    all_group_headings = (
                        "Increased", "Decreased", "Unchanged", "Incomparable",
                        "Price observation became available", "Price observation no longer available",
                        "Became available for sale", "No copies observed for sale",
                    )
                    expected_group_headings = {value[0] for value in group_expectation}
                    for group_heading in all_group_headings:
                        occurrences = sum(
                            body.count(f"{group_heading} ({number})") for number in range(0, 3)
                        )
                        self.assertEqual(occurrences, 1 if group_heading in expected_group_headings else 0)
                    self.assertEqual(
                        tuple(row.release_id for group in detail.result_groups for row in group.rows),
                        tuple(row.release_id for row in target_rows),
                    )
                    self.assertNotIn(hostile, repr(explorer))
                    self.assertNotIn(hostile, body)
                    marketplace_sections = tuple(
                        value.body for value in rendered.sections
                        if value.destination in {
                            CollectionExplorerDestination.PRICE_CHANGES,
                            CollectionExplorerDestination.SUPPLY_CHANGES,
                        }
                    )
                    self.assertNotIn(hostile, repr(marketplace_sections))

                    def recursive_strings(value):
                        if isinstance(value, str):
                            yield value
                        elif is_dataclass(value):
                            for item in fields(value):
                                yield from recursive_strings(getattr(value, item.name))
                        elif isinstance(value, (tuple, list)):
                            for item in value:
                                yield from recursive_strings(item)

                    self.assertNotIn(hostile, tuple(recursive_strings(explorer)))

                    probe = _TextProbe()
                    App._insert_marketplace_summary_first(probe, body)
                    self.assertEqual("".join(value for value, _ in probe.insertions), body)
                    tagged = {value.rstrip("\n"): tags for value, tags in probe.insertions}
                    if has_context:
                        self.assertEqual(tagged["Detailed provenance"], "provenance_heading")
                        for line in (*expected_provenance.splitlines(), f"Comparison state: {detail.comparison_state.value.replace('_', ' ').title()}"):
                            self.assertEqual(tagged[line], "provenance_body")
                    self.assertNotIn(hostile, "".join(value for value, _ in probe.insertions))

    def test_marketplace_architecture_documents_state_aware_diagnostic_presentation(self):
        text = Path("docs/MarketplaceArchitecture.md").read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        required = (
            "Internal categorization maps known structured codes to fixed application-owned categories",
            "maps an unknown code to the internal `marketplace_evidence_incomplete` category",
            "This categorization is distinct from final state-aware public presentation",
            "raw diagnostic identity, message, and details never enter public presentation",
            "The legacy current-metadata diagnostic is omitted from limitations",
            "ERROR suppresses diagnostics and limitations",
            "INSUFFICIENT_HISTORY suppresses unknown diagnostics and relies on canonical state copy, while independently truthful fixed exclusions may remain",
            "PARTIAL and INSUFFICIENT_DATA map unknown diagnostics once to fixed `marketplace_evidence_incomplete` copy",
            "AVAILABLE, NO_CHANGES, and completed EMPTY suppress unknown diagnostics",
            "Allowlisted fixed warnings appear only in states where they remain semantically compatible",
            "Duplicate warnings collapse deterministically",
            "Factual row evidence remains separate and unchanged",
        )
        for statement in required:
            self.assertIn(statement, normalized)
        policy = normalized.split("Internal categorization maps", 1)[1].split("Supply presents explicit", 1)[0]
        self.assertNotIn("every unknown code uses", policy)

    def test_rendering_does_not_mutate_authoritative_cached_tuples(self):
        workspace, _, _ = _workspace()
        price_rows = workspace.price_changes.release_changes
        supply_rows = workspace.supply_changes.changes
        price_before = tuple(price_rows)
        supply_before = tuple(supply_rows)
        DesktopPriceChangesRenderer().render(workspace.price_changes)
        DesktopSupplyChangesRenderer().render(workspace.supply_changes)
        self.assertIs(workspace.price_changes.release_changes, price_rows)
        self.assertIs(workspace.supply_changes.changes, supply_rows)
        self.assertEqual(workspace.price_changes.release_changes, price_before)
        self.assertEqual(workspace.supply_changes.changes, supply_before)

    def test_tk_provenance_styles_are_distinct_and_applied(self):
        class TextProbe:
            def __init__(self):
                self.insertions = []
                self.styles = {}

            def insert(self, index, value, tags=()):
                self.insertions.append((value, tags))

            def tag_configure(self, name, **values):
                self.styles[name] = values

        body = "\n".join((
            "Results available", "Results use the comparison shown below.", "",
            "Summary", "Increased: 1", "", "Detailed provenance",
            "Previous snapshot ID: previous", "Latest snapshot ID: latest",
        ))
        probe = TextProbe()
        App._insert_marketplace_summary_first(probe, body)
        tags = {value.rstrip("\n"): tag for value, tag in probe.insertions}
        self.assertEqual(tags["Summary"], "section_heading")
        self.assertEqual(tags["Detailed provenance"], "provenance_heading")
        self.assertEqual(tags["Previous snapshot ID: previous"], "provenance_body")
        self.assertNotEqual(
            probe.styles["section_heading"]["font"],
            probe.styles["provenance_heading"]["font"],
        )
        self.assertNotEqual(
            probe.styles["group_heading"]["font"],
            probe.styles["provenance_body"]["font"],
        )
        self.assertNotIn("foreground", probe.styles["provenance_heading"])
        self.assertNotIn("foreground", probe.styles["provenance_body"])
        self.assertEqual("".join(value for value, _ in probe.insertions), body)


if __name__ == "__main__":
    unittest.main()
