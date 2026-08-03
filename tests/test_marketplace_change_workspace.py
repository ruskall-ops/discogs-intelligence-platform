from __future__ import annotations

import unittest
from unittest.mock import Mock, patch
from dataclasses import fields, is_dataclass
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from dip.app.current_release_metadata import CurrentReleaseMetadata
from dip.app.marketplace_change_workspace import (
    SOURCE_VERSION_MISMATCH_COPY,
    METADATA_FAILURE_COPY,
    MarketplaceChangeWorkspaceService,
    MarketplaceChangeOutcomeReason,
    MarketplaceChangeWorkspaceState,
    MarketplaceSnapshotExclusionReason,
    MarketplaceSnapshotWindowSelector,
)
from dip.app.marketplace_history import MarketplaceHistoryConsistencyError
from dip.marketplace_history import MarketplaceHistoryIntegrityError
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceMoney,
    MarketplaceDiagnostic,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    PriceChangesModule,
    PriceChangesDomainError,
    SupplyChangesModule,
    SupplyChangesDomainError,
    SupplyChangeKind,
)
from dip.experience.desktop.collection_explorer_renderer import (
    DesktopCollectionExplorerController,
    DesktopCollectionExplorerRenderer,
    _marketplace_outcome_copy,
)
from dip.experience.desktop.app import App
from dip.experience.desktop.price_changes_renderer import DesktopPriceChangesRenderer
from dip.experience.desktop.supply_changes_renderer import DesktopSupplyChangesRenderer
from dip.experience.explorer import (
    CollectionExplorerDestination,
    MarketplaceChangePresentationOutcome,
)
from dip.app.price_changes import PriceChangesExecutionService
from dip.app.supply_changes import SupplyChangesExecutionService
from dip.app.collector_run import CollectorRunStatus
from dip.intelligence import IntelligenceEngine
from dip.experience.price_changes import PriceChangesDetailViewModelBuilder
from dip.experience.supply_changes import SupplyChangesDetailViewModelBuilder
from tests.test_collection_explorer import available_homepage, explorer_service
from tests.test_collector_run_desktop import _result as collector_run_result


NOW = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)


class MarketplaceOutcomeCopyTest(unittest.TestCase):
    def test_every_typed_outcome_uses_fixed_canonical_state_copy(self):
        expected = {
            MarketplaceChangePresentationOutcome.NO_ELIGIBLE_CURRENT: "More history required",
            MarketplaceChangePresentationOutcome.NO_COMPATIBLE_BASELINE: "More history required",
            MarketplaceChangePresentationOutcome.NO_COMPARABLE_FACTS: "No comparable facts",
            MarketplaceChangePresentationOutcome.HISTORY_UNREADABLE: "Results could not be displayed",
            MarketplaceChangePresentationOutcome.HISTORY_INVALID: "Results could not be displayed",
            MarketplaceChangePresentationOutcome.COMPARISON_FAILED: "Results could not be displayed",
        }
        self.assertEqual(
            {value: _marketplace_outcome_copy(value) for value in expected},
            expected,
        )
        with self.assertRaises(TypeError):
            _marketplace_outcome_copy("no_eligible_current")  # type: ignore[arg-type]


class History:
    def __init__(self, values=(), error=None):
        self.values = values
        self.error = error
        self.calls = 0

    def all_snapshots(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.values


class Metadata:
    def __init__(self, values=(), error=None):
        self.values = values
        self.error = error
        self.calls = []

    def metadata_for_release_ids(self, release_ids):
        self.calls.append(release_ids)
        if self.error:
            raise self.error
        return self.values


def observation(release_id, *, price="10.00", supply=1, status=MarketplaceDataStatus.COMPLETE, when=NOW):
    return MarketplaceReleaseObservation(
        release_id,
        when,
        status,
        lowest_price=None if price is None else MarketplaceMoney(Decimal(price), "GBP"),
        num_for_sale=supply,
        num_wanted=999,
    )


def snapshot(identifier, when, *, source="discogs", version="v1", status=MarketplaceDataStatus.COMPLETE, observations=()):
    observations = tuple(replace(value, observed_at=when) for value in observations)
    if not observations and status is MarketplaceDataStatus.COMPLETE:
        status = MarketplaceDataStatus.EMPTY
    diagnostics = ()
    if status in {MarketplaceDataStatus.FAILED, MarketplaceDataStatus.UNAVAILABLE}:
        diagnostics = (MarketplaceDiagnostic("source_unavailable", "Source unavailable."),)
    return MarketplaceSnapshot(identifier, when, source, status, observations, diagnostics=diagnostics, source_version=version)


def available_workspace():
    """Return one fully typed detached workspace for controller lifecycle tests."""

    history = History((
        snapshot("old", NOW - timedelta(days=1), observations=(observation(1, price="10", supply=1),)),
        snapshot("new", NOW, observations=(observation(1, price="11", supply=2),)),
    ))
    value = MarketplaceChangeWorkspaceService(history, Metadata()).build()
    assert value.state is MarketplaceChangeWorkspaceState.AVAILABLE
    return value


class WindowSelectorTest(unittest.TestCase):
    def test_selects_newest_compatible_strictly_earlier_pair(self):
        older = snapshot("a", NOW - timedelta(days=2))
        incompatible = snapshot("b", NOW - timedelta(days=1), version="v2")
        current = snapshot("c", NOW)
        result = MarketplaceSnapshotWindowSelector().select((older, incompatible, current))
        self.assertEqual(result.current.snapshot_id, current.snapshot_id)
        self.assertEqual(result.baseline.snapshot_id, older.snapshot_id)
        self.assertIn(SOURCE_VERSION_MISMATCH_COPY, result.diagnostics)
        self.assertIs(result.excluded[0].reason, MarketplaceSnapshotExclusionReason.SOURCE_VERSION_MISMATCH)

    def test_none_versions_compare_only_with_none(self):
        legacy = snapshot("a", NOW - timedelta(days=2), version=None)
        versioned = snapshot("b", NOW - timedelta(days=1), version="v1")
        current = snapshot("c", NOW, version=None)
        result = MarketplaceSnapshotWindowSelector().select((legacy, versioned, current))
        self.assertEqual(result.baseline.snapshot_id, legacy.snapshot_id)

    def test_equal_utc_instant_is_skipped_and_greatest_id_is_current(self):
        older = snapshot("a", NOW - timedelta(days=1))
        same_offset = snapshot("b", NOW.astimezone(timezone(timedelta(hours=1))))
        greatest = snapshot("c", NOW)
        result = MarketplaceSnapshotWindowSelector().select((older, same_offset, greatest))
        self.assertEqual(result.current.snapshot_id, greatest.snapshot_id)
        self.assertEqual(result.baseline.snapshot_id, older.snapshot_id)
        self.assertIs(result.excluded[0].reason, MarketplaceSnapshotExclusionReason.EQUAL_CAPTURE_INSTANT)

    def test_failed_and_unavailable_are_ineligible(self):
        older = snapshot("a", NOW - timedelta(days=2))
        failed = snapshot("b", NOW - timedelta(days=1), status=MarketplaceDataStatus.FAILED)
        unavailable = snapshot("c", NOW, status=MarketplaceDataStatus.UNAVAILABLE)
        self.assertEqual(MarketplaceSnapshotWindowSelector().select((older, failed, unavailable)).current.snapshot_id, older.snapshot_id)

    def test_source_and_version_exclusions_are_safe_and_deterministic(self):
        compatible = snapshot("a", NOW - timedelta(days=4), version="v2")
        source_mismatch = snapshot("b", NOW - timedelta(days=3), source="other", version="v2")
        unversioned = snapshot("c", NOW - timedelta(days=2), version=None)
        equal = snapshot("d", NOW.astimezone(timezone(timedelta(hours=2))), version="v2")
        current = snapshot("e", NOW, version="v2")
        window = MarketplaceSnapshotWindowSelector().select((compatible, source_mismatch, unversioned, equal, current))
        self.assertEqual(window.baseline.snapshot_id, "a")
        self.assertEqual(tuple(value.reason for value in window.excluded), (
            MarketplaceSnapshotExclusionReason.EQUAL_CAPTURE_INSTANT,
            MarketplaceSnapshotExclusionReason.SOURCE_VERSION_MISMATCH,
            MarketplaceSnapshotExclusionReason.SOURCE_MISMATCH,
        ))
        self.assertTrue(all("token" not in repr(value) for value in window.excluded))


class PairCalculatorContractTest(unittest.TestCase):
    def assert_builds(self, previous, latest):
        comparison = MarketplaceSnapshotComparisonInput(previous, latest)
        price = PriceChangesModule().calculate_pair(comparison)
        supply = SupplyChangesModule().calculate_pair(comparison)
        PriceChangesDetailViewModelBuilder().build(price)
        SupplyChangesDetailViewModelBuilder().build(supply)
        self.assertEqual((price.module_version, supply.module_version), ("2.0", "2.0"))

    def assert_pair_rejected(self, previous, latest):
        comparison = MarketplaceSnapshotComparisonInput(previous, latest)
        with self.assertRaises(PriceChangesDomainError):
            PriceChangesModule().calculate_pair(comparison)
        with self.assertRaises(SupplyChangesDomainError):
            SupplyChangesModule().calculate_pair(comparison)

    def test_valid_comparable_zero_fact_and_none_version_pairs_build(self):
        self.assert_builds(
            snapshot("old", NOW - timedelta(days=1), observations=(observation(1, price="10", supply=0),)),
            snapshot("new", NOW, observations=(observation(1, price="11", supply=2),)),
        )
        self.assert_builds(
            snapshot("old-zero", NOW - timedelta(days=1), observations=(observation(1, price=None, supply=None),)),
            snapshot("new-zero", NOW, observations=(observation(1, price=None, supply=None),)),
        )
        self.assert_builds(
            snapshot("old-none", NOW - timedelta(days=1), version=None),
            snapshot("new-none", NOW, version=None),
        )

    def test_source_version_and_equal_instant_pairs_are_rejected(self):
        self.assert_pair_rejected(
            snapshot("source-old", NOW - timedelta(days=1), source="discogs"),
            snapshot("source-new", NOW, source="other"),
        )
        for old_version, new_version in (("v1", "v2"), (None, "v1"), ("v1", None)):
            with self.subTest(old_version=old_version, new_version=new_version):
                self.assert_pair_rejected(
                    snapshot("version-old", NOW - timedelta(days=1), version=old_version),
                    snapshot("version-new", NOW, version=new_version),
                )
        self.assert_pair_rejected(snapshot("equal-a", NOW), snapshot("equal-b", NOW))
        self.assert_pair_rejected(
            snapshot("offset-a", NOW.astimezone(timezone(timedelta(hours=2)))),
            snapshot("offset-b", NOW),
        )

    def test_reversed_time_is_rejected_at_the_public_pair_input_boundary(self):
        with self.assertRaisesRegex(
            PriceChangesDomainError,
            "Previous snapshot capture time must not follow the latest snapshot.",
        ):
            MarketplaceSnapshotComparisonInput(
                snapshot("later", NOW),
                snapshot("earlier", NOW - timedelta(seconds=1)),
            )


class WorkspaceTest(unittest.TestCase):
    def build(self, old_observations, new_observations, metadata=()):
        history = History((
            snapshot("old", NOW - timedelta(days=1), observations=old_observations),
            snapshot("new", NOW, observations=new_observations),
        ))
        labels = Metadata(metadata)
        result = MarketplaceChangeWorkspaceService(history, labels).build()
        self.assertEqual(history.calls, 1)
        return result, labels

    def test_price_supply_and_metadata_use_one_shared_pair(self):
        result, labels = self.build(
            (observation(2, price="10.00", supply=0), observation(1, price="20.00", supply=5)),
            (observation(2, price="12.50", supply=3), observation(1, price="15.00", supply=0)),
            (CurrentReleaseMetadata(1, "Artist", "Title"),),
        )
        self.assertEqual(labels.calls, [(1, 2)])
        self.assertEqual(tuple(row.release_id for row in result.price_changes.release_changes), (1, 2))
        self.assertEqual(result.price_changes.release_changes[0].delta.amount, Decimal("-5.00"))
        self.assertEqual(result.price_changes.release_changes[1].delta.amount, Decimal("2.50"))
        self.assertEqual(result.supply_changes.changes[0].change_kind, SupplyChangeKind.NO_LONGER_AVAILABLE)
        self.assertEqual(result.supply_changes.changes[1].change_kind, SupplyChangeKind.NEWLY_AVAILABLE)
        self.assertEqual(result.price_changes.release_changes[0].display_label, "Artist — Title")
        self.assertEqual(result.supply_changes.changes[1].display_label, "Release 2")
        self.assertEqual(result.price_changes.previous_snapshot.snapshot_id, result.supply_changes.previous_snapshot.snapshot_id)
        self.assertEqual(result.price_changes.comparison_context, result.supply_changes.comparison_context)
        self.assertEqual(
            result.price_changes.comparison_context.previous_captured_at.isoformat(),
            result.window.baseline.captured_at.isoformat(),
        )
        self.assertEqual(
            result.price_changes.comparison_context.latest_captured_at.isoformat(),
            result.window.current.captured_at.isoformat(),
        )
        self.assertEqual(result.price_changes.comparison_context.source, result.window.current.source)
        self.assertEqual(
            result.price_changes.comparison_context.source_version,
            result.window.current.source_version,
        )
        headings = tuple(value.heading for value in DesktopSupplyChangesRenderer().render(result.supply_changes).changes)
        self.assertTrue(any("No copies observed for sale" in value for value in headings))
        self.assertTrue(any("Became available for sale" in value for value in headings))
        self.assertTrue(all("Newly Available" not in value and "No Longer Available" not in value for value in headings))

    def test_missing_release_and_values_are_incomparable_not_zero(self):
        result, _ = self.build(
            (observation(1, price=None, supply=None), observation(2)),
            (observation(1, price="1.00", supply=0), observation(3)),
        )
        self.assertIs(result.state, MarketplaceChangeWorkspaceState.INSUFFICIENT_DATA)
        self.assertEqual(result.price_changes.incomparable_count, 3)
        self.assertEqual(result.supply_changes.incomparable_count, 3)

    def test_mixed_comparable_and_incomparable_is_partial(self):
        result, _ = self.build(
            (observation(1, price="10", supply=1), observation(2, price=None, supply=None)),
            (observation(1, price="11", supply=2), observation(2, price="2", supply=0)),
        )
        self.assertIs(result.state, MarketplaceChangeWorkspaceState.PARTIAL)
        self.assertEqual(result.price_changes.incomparable_count, 1)
        self.assertEqual(result.supply_changes.incomparable_count, 1)

    def test_unchanged_pair_is_enabled_empty_and_metadata_not_queried(self):
        result, labels = self.build((observation(1),), (observation(1),))
        self.assertIs(result.state, MarketplaceChangeWorkspaceState.EMPTY)
        self.assertEqual(labels.calls, [])

    def test_two_empty_snapshots_are_enabled_empty(self):
        history = History((snapshot("old", NOW - timedelta(days=1)), snapshot("new", NOW)))
        result = MarketplaceChangeWorkspaceService(history, Metadata()).build()
        self.assertIs(result.state, MarketplaceChangeWorkspaceState.EMPTY)

    def test_metadata_failure_preserves_marketplace_results(self):
        history = History((snapshot("old", NOW - timedelta(days=1), observations=(observation(1),)), snapshot("new", NOW, observations=(observation(1, price="11"),))))
        expected = MarketplaceChangeWorkspaceService(history, Metadata()).build()
        history.calls = 0
        metadata = Metadata(error=RuntimeError("hostile secret"))
        result = MarketplaceChangeWorkspaceService(history, metadata).build()
        self.assertEqual(len(result.price_changes.release_changes), 1)
        self.assertEqual(result.price_changes.release_changes[0].display_label, "Release 1")
        self.assertIn(METADATA_FAILURE_COPY, result.warnings)
        self.assertNotIn("hostile", repr(result))
        self.assertIs(result.state, expected.state)
        self.assertIs(result.price_changes.state, expected.price_changes.state)
        self.assertIs(result.supply_changes.state, expected.supply_changes.state)
        self.assertEqual(result.window.current, expected.window.current)
        self.assertEqual(result.window.baseline, expected.window.baseline)

    def test_metadata_is_detached_and_changes_only_after_explicit_rebuild(self):
        history = History((
            snapshot("old", NOW - timedelta(days=1), observations=(observation(1, price="10", supply=1),)),
            snapshot("new", NOW, observations=(observation(1, price="11", supply=2),)),
        ))
        metadata = Metadata((CurrentReleaseMetadata(1, "Old Artist", "Old Title"),))
        service = MarketplaceChangeWorkspaceService(history, metadata)
        first = service.build()
        metadata.values = (CurrentReleaseMetadata(1, "New Artist", "New Title"),)
        self.assertEqual(first.price_changes.release_changes[0].display_label, "Old Artist — Old Title")
        second = service.build()
        self.assertEqual(second.price_changes.release_changes[0].display_label, "New Artist — New Title")
        self.assertEqual(second.supply_changes.changes[0].display_label, "New Artist — New Title")

    def test_partial_blank_missing_and_removed_metadata_have_deterministic_labels(self):
        history = History((
            snapshot("old", NOW - timedelta(days=1), observations=tuple(observation(value, price="10", supply=1) for value in range(1, 5))),
            snapshot("new", NOW, observations=tuple(observation(value, price="11", supply=2) for value in range(1, 5))),
        ))
        metadata = Metadata((
            CurrentReleaseMetadata(1, "Artist", None),
            CurrentReleaseMetadata(2, None, "Title"),
            CurrentReleaseMetadata(3, "  ", "\t"),
        ))
        service = MarketplaceChangeWorkspaceService(history, metadata)
        first = service.build()
        labels = tuple(value.display_label for value in first.price_changes.release_changes)
        self.assertEqual(labels, ("Artist", "Title", "Release 3", "Release 4"))
        self.assertEqual(labels, tuple(value.display_label for value in first.supply_changes.changes))
        metadata.values = ()
        self.assertEqual(first.price_changes.release_changes[0].display_label, "Artist")
        refreshed = service.build()
        self.assertTrue(all(value.display_label == f"Release {value.release_id}" for value in refreshed.price_changes.release_changes))

    def test_malformed_metadata_projection_degrades_to_fallback_without_changing_state(self):
        class Malformed:
            release_id = 1
            @property
            def artist(self): raise RuntimeError("hostile metadata payload")
            title = "Title"
        history = History((
            snapshot("old", NOW - timedelta(days=1), observations=(observation(1, price="10", supply=1),)),
            snapshot("new", NOW, observations=(observation(1, price="11", supply=2),)),
        ))
        result = MarketplaceChangeWorkspaceService(history, Metadata((Malformed(),))).build()
        self.assertIs(result.state, MarketplaceChangeWorkspaceState.AVAILABLE)
        self.assertEqual(result.price_changes.release_changes[0].display_label, "Release 1")
        self.assertEqual(result.supply_changes.changes[0].display_label, "Release 1")
        self.assertIn(METADATA_FAILURE_COPY, result.warnings)
        self.assertNotIn("hostile", repr(result))

    def test_no_compatible_baseline_is_insufficient_history(self):
        history = History((snapshot("only", NOW),))
        metadata = Metadata()
        result = MarketplaceChangeWorkspaceService(history, metadata).build()
        self.assertIs(result.state, MarketplaceChangeWorkspaceState.INSUFFICIENT_HISTORY)
        self.assertIs(result.outcome_reason, MarketplaceChangeOutcomeReason.NO_COMPATIBLE_BASELINE)
        self.assertEqual(metadata.calls, [])

    def test_no_eligible_current_has_distinct_typed_reason(self):
        failed = snapshot("failed", NOW, status=MarketplaceDataStatus.FAILED)
        result = MarketplaceChangeWorkspaceService(History((failed,)), Metadata()).build()
        self.assertIs(result.outcome_reason, MarketplaceChangeOutcomeReason.NO_ELIGIBLE_CURRENT)

    def test_history_failures_and_calculation_failure_have_distinct_safe_reasons(self):
        cases = (
            (RuntimeError("token=/secret"), MarketplaceChangeOutcomeReason.HISTORY_UNREADABLE),
            (MarketplaceHistoryIntegrityError("row payload"), MarketplaceChangeOutcomeReason.HISTORY_INVALID),
            (MarketplaceHistoryConsistencyError("SQL path"), MarketplaceChangeOutcomeReason.HISTORY_INVALID),
        )
        for failure, reason in cases:
            with self.subTest(reason=reason):
                result = MarketplaceChangeWorkspaceService(History(error=failure), Metadata()).build()
                self.assertIs(result.outcome_reason, reason)
                self.assertNotIn(str(failure), repr(result))

    def test_hostile_query_error_is_safe(self):
        result = MarketplaceChangeWorkspaceService(History(error=RuntimeError("token=/secret")), Metadata()).build()
        self.assertIs(result.state, MarketplaceChangeWorkspaceState.ERROR)
        self.assertNotIn("secret", repr(result))

    def test_core_calculation_and_projection_failures_are_safe(self):
        history = History((snapshot("old", NOW - timedelta(days=1), observations=(observation(1),)), snapshot("new", NOW, observations=(observation(1, price="11"),))))
        class Failure:
            def calculate_pair(self, *args, **kwargs): raise RuntimeError("token=/private.sqlite SQL payload")
            def build(self, *args, **kwargs): raise RuntimeError("personal note row value")
        for kwargs in (
            {"price_calculator": Failure()},
            {"supply_calculator": Failure()},
            {"price_builder": Failure()},
            {"supply_builder": Failure()},
        ):
            result = MarketplaceChangeWorkspaceService(history, Metadata(), **kwargs).build()
            self.assertIs(result.state, MarketplaceChangeWorkspaceState.ERROR)
            self.assertEqual(result.diagnostics, ("Marketplace changes could not be loaded.",))
            self.assertIs(result.outcome_reason, MarketplaceChangeOutcomeReason.COMPARISON_FAILED)
            self.assertNotIn("private", repr(result))

    def test_outcome_reason_state_invariants_reject_contradictions_and_raw_strings(self):
        insufficient = MarketplaceChangeWorkspaceService(History((snapshot("only", NOW),)), Metadata()).build()
        with self.assertRaises(TypeError):
            replace(insufficient, outcome_reason="no_compatible_baseline")
        with self.assertRaises(ValueError):
            replace(insufficient, outcome_reason=MarketplaceChangeOutcomeReason.NO_COMPARABLE_FACTS)
        available, _ = self.build((observation(1, price="10", supply=1),), (observation(1, price="11", supply=2),))
        with self.assertRaises(ValueError):
            replace(available, outcome_reason=MarketplaceChangeOutcomeReason.COMPARISON_FAILED)
        no_facts, _ = self.build((observation(1, price=None, supply=None),), (observation(1, price=None, supply=None),))
        self.assertIs(no_facts.outcome_reason, MarketplaceChangeOutcomeReason.NO_COMPARABLE_FACTS)
        with self.assertRaises(ValueError):
            replace(no_facts, outcome_reason=MarketplaceChangeOutcomeReason.NO_COMPATIBLE_BASELINE)

    def test_hostile_persisted_diagnostic_text_is_never_projected(self):
        hostile = "token provider response SQL /private/db snapshot payload row value personal note"
        diagnostic = MarketplaceDiagnostic("unknown_code", hostile, details={"path": hostile})
        old = replace(observation(1, price="10", supply=1), diagnostics=(diagnostic,))
        new = replace(observation(1, price="11", supply=2), diagnostics=(diagnostic,))
        result, _ = self.build((old,), (new,))
        rendered = repr(result)
        for sentinel in ("token", "/private/db", "personal note", "provider response"):
            self.assertNotIn(sentinel, rendered)
        self.assertIn("Marketplace evidence was incomplete", rendered)
        self.assertFalse(hasattr(result.window.current, "release_observations"))
        self.assertFalse(hasattr(result.window.baseline, "release_observations"))

        public_values = []
        def visit(value):
            public_values.append(value)
            if is_dataclass(value):
                for item in fields(value):
                    visit(getattr(value, item.name))
            elif isinstance(value, (tuple, list)):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                for item in value.items():
                    visit(item)
        visit(result)
        joined = " ".join(str(value) for value in public_values)
        for sentinel in ("token", "/private/db", "personal note", "unknown_code"):
            self.assertNotIn(sentinel, joined)

    def test_known_and_unknown_price_supply_diagnostics_drop_every_hostile_value(self):
        sentinels = (
            "access-token",
            "provider-response-body",
            "SELECT secret FROM private_table",
            "/private/live.sqlite",
            "/backup/destination",
            "serialized-row",
            "GBP 123.45",
            "supply=987",
            "personal-note",
        )
        hostile = " | ".join(sentinels)
        for code in ("source_unavailable", "partial_observation", "missing_field", "unknown-hostile-code"):
            diagnostic = MarketplaceDiagnostic(code, hostile, details={"hostile": hostile})
            old = replace(observation(1, price="10", supply=1), diagnostics=(diagnostic,))
            new = replace(observation(1, price="11", supply=2), diagnostics=(diagnostic,))
            with self.subTest(code=code):
                result, _ = self.build((old,), (new,))
                public = "\n".join((
                    repr(result),
                    repr(DesktopPriceChangesRenderer().render(result.price_changes)),
                    repr(DesktopSupplyChangesRenderer().render(result.supply_changes)),
                ))
                for sentinel in (*sentinels, "unknown-hostile-code"):
                    self.assertNotIn(sentinel, public)
                expected_code = code if code != "unknown-hostile-code" else "marketplace_evidence_incomplete"
                self.assertIn(expected_code, public)

    def test_every_hostile_sentinel_is_absent_from_actual_presentation_renderer_and_error_outputs(self):
        sentinels = (
            "TOKEN-secret-123",
            "PROVIDER-{private-body}",
            "SELECT * FROM private_records",
            "/private/live-collection.sqlite",
            "/Volumes/private/backup.sqlite3",
            '{"release_id":99,"private":true}',
            "GBP 9876.54",
            "num_for_sale=4321",
            "PERSONAL-NOTE-do-not-display",
        )
        class Failure:
            def __init__(self, value): self.value=value
            def calculate_pair(self, value): raise RuntimeError(self.value)
        for sentinel in sentinels:
            for code in ("source_unavailable", "unknown_private_identity"):
                with self.subTest(sentinel=sentinel, code=code):
                    diagnostic=MarketplaceDiagnostic(code,sentinel,details={"private":sentinel})
                    old=replace(observation(1,price="10",supply=1),diagnostics=(diagnostic,))
                    new=replace(observation(1,price="11",supply=2),diagnostics=(diagnostic,))
                    workspace,_=self.build((old,),(new,))
                    presentation=explorer_service().explorer_for_homepage(
                        available_homepage(),
                        selected_destination=CollectionExplorerDestination.PRICE_CHANGES,
                        price_changes_detail=workspace.price_changes,
                        supply_changes_detail=workspace.supply_changes,
                    )
                    explorer=DesktopCollectionExplorerRenderer().render(presentation)
                    outputs=(
                        repr(workspace), repr(presentation), repr(explorer),
                        repr(DesktopPriceChangesRenderer().render(workspace.price_changes)),
                        repr(DesktopSupplyChangesRenderer().render(workspace.supply_changes)),
                        "\n".join(section.body for section in explorer.sections),
                    )
                    self.assertTrue(all(value for value in outputs))
                    self.assertTrue(all(sentinel not in value for value in outputs))
                    if code == "unknown_private_identity":
                        self.assertIn("marketplace_evidence_incomplete",repr(workspace))
                        self.assertNotIn(code,repr(workspace))
                    self.assertFalse(hasattr(workspace.window.current,"release_observations"))
                    self.assertFalse(hasattr(workspace.window.baseline,"release_observations"))

            history_error=MarketplaceChangeWorkspaceService(History(error=RuntimeError(sentinel)),Metadata()).build()
            metadata_error=MarketplaceChangeWorkspaceService(
                History((snapshot("old",NOW-timedelta(days=1),observations=(observation(1),)),snapshot("new",NOW,observations=(observation(1,price="11",supply=2),)))),
                Metadata(error=RuntimeError(sentinel)),
            ).build()
            calculator_error=MarketplaceChangeWorkspaceService(
                History((snapshot("old",NOW-timedelta(days=1),observations=(observation(1),)),snapshot("new",NOW,observations=(observation(1,price="11",supply=2),)))),
                Metadata(), price_calculator=Failure(sentinel),
            ).build()
            class SelectorFailure:
                def _select(self, history): raise RuntimeError(sentinel)
            selector_error=MarketplaceChangeWorkspaceService(
                History(()),Metadata(),selector=SelectorFailure()
            ).build()
            for output in (history_error,metadata_error,calculator_error,selector_error):
                self.assertNotIn(sentinel,repr(output))

    def test_workspace_and_legacy_services_use_same_pair_and_answers(self):
        history = History((
            snapshot("old", NOW - timedelta(days=2), observations=(observation(1, price="10", supply=0),)),
            snapshot("wrong", NOW - timedelta(days=1), version="v2", observations=(observation(1, price="99", supply=99),)),
            snapshot("new", NOW, observations=(observation(1, price="12", supply=3),)),
        ))
        workspace = MarketplaceChangeWorkspaceService(history, Metadata()).build()
        price = PriceChangesExecutionService(history, IntelligenceEngine((PriceChangesModule(),))).execute().metrics["output"]
        supply = SupplyChangesExecutionService(history, IntelligenceEngine((SupplyChangesModule(),))).execute().metrics["output"]
        self.assertEqual((price.previous_snapshot.snapshot_id, price.latest_snapshot.snapshot_id), ("old", "new"))
        self.assertEqual((supply.previous_snapshot.snapshot_id, supply.latest_snapshot.snapshot_id), ("old", "new"))
        self.assertEqual(workspace.price_changes.release_changes[0].delta, price.release_changes[0].delta)
        self.assertEqual(workspace.supply_changes.changes[0].change_kind, supply.changes[0].change_kind)

    def test_process_control_exceptions_propagate(self):
        for failure in (KeyboardInterrupt(), SystemExit()):
            with self.subTest(failure=type(failure).__name__):
                with self.assertRaises(type(failure)):
                    MarketplaceChangeWorkspaceService(History(error=failure), Metadata()).build()


class ControllerCacheTest(unittest.TestCase):
    def test_controller_availability_boundary_blocks_direct_and_alternate_refresh_paths(self):
        allowed = False
        class Service:
            calls = 0
            def build(self):
                self.calls += 1
                raise AssertionError("blocked refresh queried History")
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs): return kwargs
        class Renderer:
            def render(self, value): return value
        service = Service()
        controller = DesktopCollectionExplorerController(
            Presentation(), Renderer(), service, lambda: allowed
        )
        self.assertIsNone(controller.refresh_marketplace_changes())
        controller.open(object(), refresh_marketplace=True)
        controller.open(object())
        self.assertEqual(service.calls, 0)
        allowed = True
        class SafeWorkspace:
            state = MarketplaceChangeWorkspaceState.AVAILABLE
            price_changes = "price"
            supply_changes = "supply"
        service.build = lambda: SafeWorkspace()
        controller.open(object())
        self.assertEqual(controller.open(object())["price_changes_detail"], "price")
    def test_open_caches_refresh_rebuilds_and_invalidation_does_not_query(self):
        class Service:
            def __init__(self):
                self.calls = 0
            def build(self):
                self.calls += 1
                return type("Workspace", (), {"price_changes": f"price-{self.calls}", "supply_changes": f"supply-{self.calls}"})()
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs):
                return kwargs
        class Renderer:
            def render(self, value):
                return value
        service = Service()
        controller = DesktopCollectionExplorerController(Presentation(), Renderer(), service)
        first = controller.open(object())
        second = controller.open(object())
        self.assertEqual(service.calls, 1)
        self.assertEqual(first["price_changes_detail"], second["price_changes_detail"])
        controller.open(object(), refresh_marketplace=True)
        self.assertEqual(service.calls, 2)
        controller.invalidate_marketplace_changes()
        self.assertEqual(service.calls, 2)
        controller.open(object())
        self.assertEqual(service.calls, 3)

    def test_presentation_failure_never_publishes_unseen_candidate(self):
        class Service:
            def __init__(self): self.values = []
            def build(self): return self.values.pop(0)
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs): return kwargs
        class Renderer:
            calls = 0
            def render(self, value):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("renderer failed midway")
                return value
        old = type("Workspace", (), {"price_changes": "old-price", "supply_changes": "old-supply"})()
        unseen = type("Workspace", (), {"price_changes": "unseen-price", "supply_changes": "unseen-supply"})()
        service = Service()
        service.values = [old, unseen]
        controller = DesktopCollectionExplorerController(Presentation(), Renderer(), service)
        controller.open(object())
        installed = controller._marketplace_cache
        with self.assertRaisesRegex(RuntimeError, "renderer failed midway"):
            controller.open(object(), refresh_marketplace=True)
        self.assertIs(controller._marketplace_cache, installed)
        self.assertEqual(controller.open(object())["price_changes_detail"], "old-price")

    def test_collector_run_blocks_first_build_and_refresh_but_retains_cache(self):
        class Service:
            calls = 0
            def build(self):
                self.calls += 1
                return type("Workspace", (), {"price_changes": "price", "supply_changes": "supply"})()
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs): return kwargs
        class Renderer:
            def render(self, value): return value
        service = Service()
        controller = DesktopCollectionExplorerController(Presentation(), Renderer(), service)
        blocked = controller.open(object(), collector_run_active=True, refresh_marketplace=True)
        self.assertEqual(service.calls, 0)
        self.assertNotIn("price_changes_detail", blocked)
        controller.open(object())
        self.assertEqual(service.calls, 1)
        cached = controller.open(object(), collector_run_active=True, refresh_marketplace=True)
        self.assertEqual(service.calls, 1)
        self.assertEqual(cached["price_changes_detail"], "price")

    def test_disabled_direct_destination_falls_back_without_workspace_query(self):
        class Service:
            def build(self): raise AssertionError("query must not run")
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs): return kwargs
        class Renderer:
            def render(self, value): return value
        controller = DesktopCollectionExplorerController(Presentation(), Renderer(), Service())
        result = controller.open(object(), selected_destination=CollectionExplorerDestination.RARE_APPEARANCES, collector_run_active=True)
        self.assertIs(result["selected_destination"], CollectionExplorerDestination.OVERVIEW)

    def test_failed_refresh_retains_previous_cache_for_later_retry(self):
        class Service:
            def __init__(self): self.values = []
            def build(self): return self.values.pop(0)
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs): return kwargs
        class Renderer:
            def render(self, value): return value
        good1 = type("Workspace", (), {"state": MarketplaceChangeWorkspaceState.AVAILABLE, "price_changes": "old-price", "supply_changes": "old-supply"})()
        failed = type("Workspace", (), {"state": MarketplaceChangeWorkspaceState.ERROR, "price_changes": "bad", "supply_changes": "bad"})()
        good2 = type("Workspace", (), {"state": MarketplaceChangeWorkspaceState.AVAILABLE, "price_changes": "new-price", "supply_changes": "new-supply"})()
        service = Service()
        service.values = [good1, failed, good2]
        controller = DesktopCollectionExplorerController(Presentation(), Renderer(), service)
        controller._validate_marketplace_candidate = lambda value: (
            None if value.state is MarketplaceChangeWorkspaceState.ERROR else value
        )
        self.assertEqual(controller.open(object())["price_changes_detail"], "old-price")
        self.assertFalse(controller.refresh_marketplace_changes())
        self.assertEqual(controller.open(object())["price_changes_detail"], "old-price")
        candidate = controller.refresh_marketplace_changes()
        self.assertIs(candidate, good2)
        self.assertEqual(controller.open(object())["price_changes_detail"], "old-price")


class DesktopMarketplaceLifecycleTest(unittest.TestCase):
    def test_every_real_entry_path_becomes_available_only_through_terminal_cleanup(self):
        stale_copy="Marketplace history has changed. Refresh Marketplace Changes to update these results."
        paths=(
            "button","keyboard","direct_refresh","programmatic_refresh",
            "alternate_open","alternate_rebuild","price_dispatch","supply_dispatch",
        )
        class Label:
            def __init__(self): self.text="old"
            def configure(self,*,text): self.text=text
        class Button:
            def state(self,value): pass
        class Window:
            def __init__(self): self.live=True; self._dip_marketplace_registration=(Label(),Button(),lambda:None)
            def winfo_exists(self): return self.live
            def protocol(self,*args): pass
            def bind(self,*args,**kwargs): pass
            def destroy(self): self.live=False
        class Presentation:
            def __init__(self): self.destinations=[]
            def explorer_for_homepage(self,homepage,**kwargs): self.destinations.append(kwargs["selected_destination"]); return kwargs
        class Renderer:
            def render(self,value): return value
        for status in CollectorRunStatus:
            for path in paths:
                with self.subTest(status=status,path=path):
                    operations={name:0 for name in ("history","metadata","workspace","provider","persistence","replacement")}
                    candidate=available_workspace()
                    class Service:
                        def build(self):
                            operations["workspace"]+=1; operations["history"]+=1; operations["metadata"]+=1
                            return candidate
                    presentation=Presentation()
                    app=App.__new__(App); app._collector_run_active=True; app._database_backup_active=False
                    app.refresh_discogs_button=Mock(); app.import_csv_button=Mock(); app.database_backup_button=Mock()
                    app.status_var=Mock(); app.refresh_dashboard=Mock(); app.load_table=Mock()
                    controller=DesktopCollectionExplorerController(presentation,Renderer(),Service(),lambda:not app._collector_run_active)
                    old_cache=available_workspace(); controller._marketplace_cache=old_cache
                    app.collection_explorer_controller=controller; app.current_dashboard_homepage=object()
                    old=Window(); label=old._dip_marketplace_registration[0]
                    app._marketplace_explorer_handles={old:(label,Button())}
                    replacement=Window(); replacement.live=False
                    def create(): operations["replacement"]+=1; replacement.live=True; return replacement
                    app._create_marketplace_replacement_toplevel=create
                    app._populate_marketplace_replacement=lambda window,value:window
                    notebook=type("Notebook",(),{"select":lambda self:"s","index":lambda self,value:0})()
                    rendered=type("Rendered",(),{"sections":(type("Section",(),{"destination":CollectionExplorerDestination.PRICE_CHANGES})(),)})()
                    with patch("dip.experience.desktop.app.messagebox.showinfo"),patch("dip.experience.desktop.app.messagebox.showwarning"),patch("dip.experience.desktop.app.messagebox.showerror"):
                        app.finish_refresh(collector_run_result(status))
                    self.assertFalse(app._collector_run_active); self.assertEqual(label.text,stale_copy)
                    self.assertEqual(operations,{key:0 for key in operations})
                    if path == "button": app._marketplace_refresh_callback(old,notebook,rendered)
                    elif path == "keyboard": self.assertEqual(app._marketplace_refresh_callback(old,notebook,rendered,object()),"break")
                    elif path == "direct_refresh": controller.refresh_marketplace_changes()
                    elif path == "programmatic_refresh": controller.open(object(),refresh_marketplace=True)
                    elif path == "alternate_open": controller.open(object())
                    elif path == "alternate_rebuild": controller.open(object(),refresh_marketplace=True)
                    elif path == "price_dispatch": controller.open(object(),selected_destination=CollectionExplorerDestination.PRICE_CHANGES)
                    else: controller.open(object(),selected_destination=CollectionExplorerDestination.SUPPLY_CHANGES)
                    self.assertEqual(operations["workspace"],1); self.assertEqual(operations["history"],1)
                    self.assertLessEqual(operations["metadata"],1); self.assertEqual(operations["provider"],0); self.assertEqual(operations["persistence"],0)
                    if path in {"button","keyboard"}:
                        self.assertEqual(operations["replacement"],1); self.assertFalse(old.live); self.assertTrue(replacement.live)
                        self.assertEqual(replacement._dip_marketplace_registration[0].text,"")
                    else:
                        self.assertEqual(operations["replacement"],0); self.assertTrue(old.live); self.assertEqual(label.text,stale_copy)
                    if path not in {"direct_refresh"}:
                        expected={
                            "button":CollectionExplorerDestination.PRICE_CHANGES,
                            "keyboard":CollectionExplorerDestination.PRICE_CHANGES,
                            "price_dispatch":CollectionExplorerDestination.PRICE_CHANGES,
                            "supply_dispatch":CollectionExplorerDestination.SUPPLY_CHANGES,
                        }.get(path,CollectionExplorerDestination.OVERVIEW)
                        self.assertIs(presentation.destinations[-1],expected)
    def test_hostile_exception_matrix_never_crosses_dialog_status_or_stale_boundaries(self):
        sentinels=(
            "TOKEN-secret-123", "PROVIDER-{private-body}", "SELECT private FROM rows",
            "/private/live.sqlite", "/backup/private.sqlite3", "serialized-private-row",
            "GBP 9876.54", "supply=4321", "PERSONAL-NOTE-private",
        )
        fixed_failure="Marketplace changes could not be refreshed. The previous results remain stale; retry is available."
        class Label:
            def __init__(self,fail=None): self.text="Marketplace history has changed. Refresh Marketplace Changes to update these results."; self.fail=fail
            def configure(self,*,text):
                if self.fail: raise RuntimeError(self.fail)
                self.text=text
        class Button:
            def state(self,value): pass
        class Window:
            def __init__(self,cleanup=None,label=None):
                self.live=True; self.cleanup=cleanup
                self._dip_marketplace_registration=(label or Label(),Button(),lambda:None)
            def protocol(self,*args): pass
            def bind(self,*args,**kwargs): pass
            def destroy(self):
                self.live=False
                if self.cleanup: raise RuntimeError(self.cleanup)
        class Service:
            def __init__(self,value): self.value=value
            def build(self): return self.value
        class Presentation:
            def explorer_for_homepage(self,homepage,**kwargs): return kwargs
        class Renderer:
            def render(self,value): return value
        notebook=type("Notebook",(),{"select":lambda self:"s","index":lambda self,value:0})()
        rendered=type("Rendered",(),{"sections":(type("Section",(),{"destination":CollectionExplorerDestination.PRICE_CHANGES})(),)})()
        for sentinel in sentinels:
            for stage in ("presentation","renderer_acquisition","renderer_invocation","population","cleanup","stale_clear"):
                with self.subTest(sentinel=sentinel,stage=stage):
                    old,candidate=available_workspace(),available_workspace()
                    presentation,renderer=Presentation(),Renderer()
                    controller=DesktopCollectionExplorerController(presentation,renderer,Service(candidate))
                    controller._marketplace_cache=old
                    app=App.__new__(App); app._collector_run_active=False; app.current_dashboard_homepage=object()
                    app.collection_explorer_controller=controller; app.status_var=type("Status",(),{"value":"Ready","set":lambda self,value:setattr(self,"value",value)})()
                    old_window=Window(); old_label=old_window._dip_marketplace_registration[0]
                    app._marketplace_explorer_handles={old_window:(old_label,Button())}
                    replacement=Window(
                        sentinel if stage == "cleanup" else None,
                        Label(sentinel if stage == "stale_clear" else None),
                    )
                    app._create_marketplace_replacement_toplevel=lambda:replacement
                    app._populate_marketplace_replacement=lambda window,value: (_ for _ in ()).throw(RuntimeError(sentinel)) if stage in {"population","cleanup"} else window
                    if stage == "presentation": presentation.explorer_for_homepage=Mock(side_effect=RuntimeError(sentinel))
                    if stage == "renderer_acquisition": controller._marketplace_renderer_for_refresh=Mock(side_effect=RuntimeError(sentinel))
                    if stage == "renderer_invocation": renderer.render=Mock(side_effect=RuntimeError(sentinel))
                    with patch("dip.experience.desktop.app.messagebox.showerror") as dialog:
                        app._refresh_marketplace_explorer(old_window,notebook,rendered)
                    outputs=(repr(dialog.call_args),old_label.text,app.status_var.value,fixed_failure)
                    self.assertTrue(all(value for value in outputs))
                    self.assertTrue(all(sentinel not in value for value in outputs))
                    if stage == "stale_clear":
                        self.assertIs(controller.marketplace_cache,candidate)
                        self.assertEqual(tuple(app._marketplace_explorer_handles),(replacement,))
                        self.assertEqual(replacement._dip_marketplace_registration[0].text,"Marketplace history has changed. Refresh Marketplace Changes to update these results.")
                    else:
                        self.assertIs(controller.marketplace_cache,old)
                        self.assertEqual(tuple(app._marketplace_explorer_handles),(old_window,))

    def test_actual_controller_and_app_prepublication_seams_are_independent_and_rollback(self):
        stale_copy = "Marketplace history has changed. Refresh Marketplace Changes to update these results."
        class Label:
            def __init__(self): self.text = stale_copy
            def configure(self, *, text): self.text = text
        class Button:
            def state(self, value): pass
        class Window:
            created = []
            def __init__(self, name, *, live=True):
                self.name=name; self.live=live; self.destroy_calls=0; self.registered=False
                self._dip_marketplace_registration=(Label(),Button(),lambda:None)
                self.__class__.created.append(self)
            def protocol(self, *args): pass
            def bind(self, *args, **kwargs): pass
            def destroy(self): self.destroy_calls += 1; self.live=False
        class Service:
            def __init__(self, value, log): self.value=value; self.log=log
            def build(self): self.log.append("construct"); return self.value
        class Presentation:
            def __init__(self, log): self.log=log; self.last=None
            def explorer_for_homepage(self, homepage, **kwargs): self.log.append("presentation"); self.last=kwargs; return kwargs
        class Renderer:
            def __init__(self, log): self.log=log
            def render(self, value): self.log.append("render"); return value

        for stage in (
            "construct", "validate", "presentation", "renderer_acquisition",
            "renderer_invocation", "toplevel", "population", "install", "registration",
        ):
            with self.subTest(stage=stage):
                Window.created=[]; log=[]
                old, candidate=available_workspace(), available_workspace()
                presentation, renderer=Presentation(log), Renderer(log)
                controller=DesktopCollectionExplorerController(presentation,renderer,Service(candidate,log))
                controller._marketplace_cache=old
                app=App.__new__(App); app._collector_run_active=False; app.current_dashboard_homepage=object()
                app.collection_explorer_controller=controller
                old_window=Window("old"); old_label=old_window._dip_marketplace_registration[0]
                app._marketplace_explorer_handles={old_window:(old_label,Button())}
                replacement=Window("replacement", live=False)
                def create_replacement():
                    log.append("toplevel"); replacement.live=True; return replacement
                app._create_marketplace_replacement_toplevel=create_replacement
                def populate(window, rendered):
                    log.append("population")
                    window.partially_populated=True
                    if stage == "population": raise RuntimeError("PRIVATE population")
                    return window
                app._populate_marketplace_replacement=populate
                original_register=app._register_marketplace_explorer_window
                def register(window):
                    log.append("registration")
                    if stage == "registration": raise RuntimeError("PRIVATE registration")
                    original_register(window); window.registered=True
                app._register_marketplace_explorer_window=register
                original_install=controller.install_marketplace_changes
                def install(value):
                    log.append("install")
                    if stage == "install": raise RuntimeError("PRIVATE install")
                    return original_install(value)
                controller.install_marketplace_changes=install
                original_construct=controller._construct_marketplace_candidate
                original_validate=controller._validate_marketplace_candidate
                original_acquire=controller._marketplace_renderer_for_refresh
                original_present=presentation.explorer_for_homepage
                original_render=renderer.render
                if stage == "construct":
                    controller._construct_marketplace_candidate=Mock(side_effect=RuntimeError("PRIVATE construct"))
                else:
                    controller._construct_marketplace_candidate=Mock(wraps=original_construct)
                if stage == "validate":
                    controller._validate_marketplace_candidate=Mock(side_effect=RuntimeError("PRIVATE validate"))
                else:
                    controller._validate_marketplace_candidate=Mock(wraps=original_validate)
                if stage == "presentation":
                    presentation.explorer_for_homepage=Mock(side_effect=RuntimeError("PRIVATE presentation"))
                if stage == "renderer_acquisition":
                    controller._marketplace_renderer_for_refresh=Mock(side_effect=RuntimeError("PRIVATE acquire"))
                else:
                    controller._marketplace_renderer_for_refresh=Mock(wraps=original_acquire)
                if stage == "renderer_invocation":
                    renderer.render=Mock(side_effect=RuntimeError("PRIVATE render"))
                if stage == "toplevel":
                    app._create_marketplace_replacement_toplevel=lambda: (_ for _ in ()).throw(RuntimeError("PRIVATE toplevel"))
                notebook=type("Notebook",(),{"select":lambda self:"s","index":lambda self,value:0})()
                rendered=type("Rendered",(),{"sections":(type("Section",(),{"destination":CollectionExplorerDestination.PRICE_CHANGES})(),)})()
                with patch("dip.experience.desktop.app.messagebox.showerror") as dialog:
                    app._refresh_marketplace_explorer(old_window,notebook,rendered)
                self.assertIs(controller.marketplace_cache,old)
                self.assertEqual(tuple(app._marketplace_explorer_handles),(old_window,))
                self.assertTrue(old_window.live); self.assertEqual(old_label.text, "Marketplace changes could not be refreshed. The previous results remain stale; retry is available.")
                self.assertNotIn("PRIVATE",repr(dialog.call_args))
                self.assertFalse(replacement.registered)
                if stage in {"population","install","registration"}: self.assertFalse(replacement.live)
                self.assertEqual(sum(value.live for value in Window.created), 1)
                if stage == "construct": controller._validate_marketplace_candidate.assert_not_called()
                if stage == "validate": self.assertNotIn("presentation",log)
                if stage == "presentation": self.assertNotIn("render",log)
                if stage == "renderer_acquisition": self.assertNotIn("render",log)
                if stage == "renderer_invocation": controller._marketplace_renderer_for_refresh.assert_called_once()
                controller._construct_marketplace_candidate=original_construct
                controller._validate_marketplace_candidate=original_validate
                controller._marketplace_renderer_for_refresh=original_acquire
                controller.install_marketplace_changes=original_install
                presentation.explorer_for_homepage=original_present
                renderer.render=original_render
                ordinary=controller.open(object())
                self.assertIs(ordinary["price_changes_detail"],old.price_changes)
                self.assertIsNot(ordinary["price_changes_detail"],candidate.price_changes)
                self.assertIsNot(controller.marketplace_cache,candidate)
                app._register_marketplace_explorer_window=original_register
                retry=Window("retry", live=False)
                def create_retry(): retry.live=True; return retry
                app._create_marketplace_replacement_toplevel=create_retry
                app._populate_marketplace_replacement=lambda window,value:window
                app._refresh_marketplace_explorer(old_window,notebook,rendered)
                self.assertIs(controller.marketplace_cache,candidate)
                self.assertEqual(tuple(app._marketplace_explorer_handles),(retry,))
                self.assertFalse(old_window.live); self.assertTrue(retry.live)
                self.assertIs(presentation.last["selected_destination"],CollectionExplorerDestination.PRICE_CHANGES)

    def test_each_active_run_entry_path_uses_its_real_boundary_without_operations(self):
        stale_copy = "Marketplace history has changed. Refresh Marketplace Changes to update these results."
        operations = {name: 0 for name in (
            "history", "metadata", "workspace", "provider", "persistence", "replacement"
        )}
        class Service:
            def build(self):
                operations["workspace"] += 1
                operations["history"] += 1
                operations["metadata"] += 1
                operations["provider"] += 1
                operations["persistence"] += 1
                raise AssertionError("an active Collector Run must block the build")
        class Presentation:
            def explorer_for_homepage(self, homepage, **kwargs): return kwargs
        class Renderer:
            def render(self, value): return value
        allowed = False
        controller = DesktopCollectionExplorerController(
            Presentation(), Renderer(), Service(), lambda: allowed
        )
        old_cache = type("CachedWorkspace", (), {
            "price_changes": object(), "supply_changes": object(),
            "outcome_reason": None,
        })()
        controller._marketplace_cache = old_cache
        app = App.__new__(App)
        app._collector_run_active = True
        app.collection_explorer_controller = controller
        app.current_dashboard_homepage = object()
        app.collector_run_service = Mock()
        app.db = Mock()
        class Label:
            def __init__(self): self.text = stale_copy
            def configure(self, *, text): self.text = text
        class Button:
            def __init__(self): self.states = []
            def state(self, value): self.states.append(value)
        class Window:
            def __init__(self):
                self.live = True
                self.registered = True
                self.stale = True
                self.selected_destination = CollectionExplorerDestination.PRICE_CHANGES
                self.destroyed = False
                self.replaced = False
            def winfo_exists(self): return self.live and not self.destroyed
            def destroy(self): self.destroyed = True; self.live = False
        old_window = Window()
        old_label, old_button = Label(), Button()
        old_handles = {old_window: (old_label, old_button)}
        app._marketplace_explorer_handles = dict(old_handles)
        app._create_marketplace_replacement_toplevel = lambda: (
            operations.__setitem__("replacement", operations["replacement"] + 1)
        )
        notebook = type("Notebook", (), {"select": lambda self: "selected", "index": lambda self, value: 0})()
        rendered = type("Rendered", (), {"sections": (type("Section", (), {"destination": CollectionExplorerDestination.PRICE_CHANGES})(),)})()
        paths = (
            ("refresh_button", lambda: app._marketplace_refresh_callback(old_window, notebook, rendered)),
            ("keyboard_binding_callback", lambda: app._marketplace_refresh_callback(old_window, notebook, rendered, object())),
            ("direct_controller_refresh", controller.refresh_marketplace_changes),
            ("programmatic_refresh", lambda: controller.open(object(), refresh_marketplace=True, collector_run_active=True)),
            ("alternate_explorer_open", lambda: controller.open(object(), collector_run_active=True)),
            ("alternate_rebuild", lambda: controller.open(object(), refresh_marketplace=True)),
            ("price_dispatch", lambda: controller.open(object(), selected_destination=CollectionExplorerDestination.PRICE_CHANGES, collector_run_active=True)),
            ("supply_dispatch", lambda: controller.open(object(), selected_destination=CollectionExplorerDestination.SUPPLY_CHANGES, collector_run_active=True)),
        )
        for name, invoke in paths:
            with self.subTest(path=name):
                before_handles = dict(app._marketplace_explorer_handles)
                result = invoke()
                if name == "keyboard_binding_callback": self.assertEqual(result, "break")
                self.assertEqual(operations, {key: 0 for key in operations})
                self.assertIs(controller.marketplace_cache, old_cache)
                self.assertEqual(app._marketplace_explorer_handles, before_handles)
                self.assertIs(rendered.sections[0].destination, CollectionExplorerDestination.PRICE_CHANGES)
                self.assertTrue(old_window.live)
                self.assertTrue(old_window.registered)
                self.assertTrue(old_window.stale)
                self.assertEqual(old_label.text, stale_copy)
                self.assertIs(old_window.selected_destination, CollectionExplorerDestination.PRICE_CHANGES)
                self.assertFalse(old_window.destroyed)
                self.assertFalse(old_window.replaced)
                self.assertEqual(app.collector_run_service.mock_calls, [])
                self.assertEqual(app.db.mock_calls, [])

        bindings = []
        class Window:
            def bind(self, sequence, callback, *, add): bindings.append((sequence, callback, add))
        callback = lambda event: app._marketplace_refresh_callback(old_window, notebook, rendered, event)
        App._bind_marketplace_refresh_shortcuts(Window(), callback)
        self.assertEqual([value[0] for value in bindings], ["<Command-r>", "<Control-r>"])
        self.assertTrue(all(value[1] is callback and value[2] == "+" for value in bindings))


    def test_cleanup_contains_ordinary_failures_and_propagates_process_control(self):
        for failure in (RuntimeError("ordinary"), KeyboardInterrupt(), SystemExit()):
            class Window:
                def destroy(self): raise failure
            with self.subTest(failure=type(failure).__name__):
                if isinstance(failure, RuntimeError):
                    self.assertIsNone(App._destroy_marketplace_window(Window()))
                else:
                    with self.assertRaises(type(failure)):
                        App._destroy_marketplace_window(Window())

    def test_prepublication_failures_restore_exact_cache_window_and_allow_retry(self):
        class Label:
            def __init__(self): self.text = "stale"
            def configure(self, *, text): self.text = text
        class Button:
            def __init__(self): self.states = []
            def state(self, value): self.states.append(value)
        class Window:
            def __init__(self, *, destroy_error=False):
                self.destroy_error = destroy_error
                self.destroy_calls = 0
                self._dip_marketplace_registration = (Label(), Button(), lambda: None)
            def protocol(self, *args): pass
            def bind(self, *args, **kwargs): pass
            def destroy(self):
                self.destroy_calls += 1
                if self.destroy_error: raise RuntimeError("HOSTILE cleanup")
        class Controller:
            def __init__(self, old): self.cache = old; self.failure = None
            def refresh_marketplace_changes(self):
                if self.failure == "workspace": raise RuntimeError("HOSTILE workspace")
                if self.failure == "final": return None
                return candidate
            def present_marketplace_candidate(self, homepage, supplied, *, selected_destination):
                if self.failure == "presentation": raise RuntimeError("HOSTILE presentation")
                return presentation_candidate
            def render_marketplace_presentation(self, supplied):
                if self.failure == "renderer_construction": raise RuntimeError("HOSTILE renderer construction")
                if self.failure == "renderer_invocation": raise RuntimeError("HOSTILE renderer")
                return rendered_candidate
            def install_marketplace_changes(self, supplied):
                if self.failure == "install": raise RuntimeError("HOSTILE install")
                previous = self.cache; self.cache = supplied; return previous
            def restore_marketplace_changes(self, previous): self.cache = previous
        old_cache, candidate, presentation_candidate, rendered_candidate = object(), object(), object(), object()
        for stage in ("workspace", "final", "presentation", "renderer_construction", "renderer_invocation", "toplevel", "widget", "install", "registration"):
            with self.subTest(stage=stage):
                app = App.__new__(App)
                app._collector_run_active = False
                app.current_dashboard_homepage = object()
                controller = Controller(old_cache)
                controller.failure = stage
                app.collection_explorer_controller = controller
                old_window, replacement = Window(), Window(destroy_error=stage == "widget")
                old_handle = (Label(), Button())
                app._marketplace_explorer_handles = {old_window: old_handle}
                app._create_marketplace_replacement_toplevel = lambda: (
                    (_ for _ in ()).throw(RuntimeError("HOSTILE toplevel"))
                    if stage == "toplevel" else replacement
                )
                app._populate_marketplace_replacement = lambda window, supplied: (
                    (_ for _ in ()).throw(RuntimeError("HOSTILE widget"))
                    if stage == "widget" else window
                )
                real_register = app._register_marketplace_explorer_window
                app._register_marketplace_explorer_window = (
                    (lambda window: (_ for _ in ()).throw(RuntimeError("HOSTILE registration")))
                    if stage == "registration" else real_register
                )
                notebook = type("Notebook", (), {"select": lambda self: "selected", "index": lambda self, value: 0})()
                rendered = type("Rendered", (), {"sections": (type("Section", (), {"destination": CollectionExplorerDestination.PRICE_CHANGES})(),)})()
                with patch("dip.experience.desktop.app.messagebox.showerror") as dialog:
                    app._refresh_marketplace_explorer(old_window, notebook, rendered)
                self.assertIs(controller.cache, old_cache)
                self.assertEqual(app._marketplace_explorer_handles, {old_window: old_handle})
                self.assertEqual(old_window.destroy_calls, 0)
                self.assertNotIn("HOSTILE", repr(dialog.call_args))
                if stage in {"widget", "install", "registration"}:
                    self.assertEqual(replacement.destroy_calls, 1)
                else:
                    self.assertEqual(replacement.destroy_calls, 0)
                controller.failure = None
                app._create_marketplace_replacement_toplevel = lambda: replacement
                app._populate_marketplace_replacement = lambda window, supplied: window
                app._register_marketplace_explorer_window = real_register
                app._refresh_marketplace_explorer(old_window, notebook, rendered)
                self.assertIs(controller.cache, candidate)
                self.assertIn(replacement, app._marketplace_explorer_handles)
                self.assertNotIn(old_window, app._marketplace_explorer_handles)
                self.assertEqual(replacement._dip_marketplace_registration[0].text, "")

    def test_postpublication_old_window_cleanup_failure_keeps_replacement_truthful(self):
        class Label:
            def __init__(self): self.text = "stale"
            def configure(self, *, text): self.text = text
        class Button:
            def state(self, value): pass
        class Window:
            def __init__(self, fail=False):
                self.fail = fail
                self._dip_marketplace_registration = (Label(), Button(), lambda: None)
            def protocol(self, *args): pass
            def bind(self, *args, **kwargs): pass
            def destroy(self):
                if self.fail: raise RuntimeError("ordinary cleanup failure")
        old_cache, candidate = object(), object()
        class Controller:
            cache = old_cache
            def refresh_marketplace_changes(self): return candidate
            def present_marketplace_candidate(self, *args, **kwargs): return object()
            def render_marketplace_presentation(self, supplied): return object()
            def install_marketplace_changes(self, supplied): previous=self.cache; self.cache=supplied; return previous
            def restore_marketplace_changes(self, previous): self.cache=previous
            def open(self, *args, **kwargs): return self.cache
        app = App.__new__(App); app._collector_run_active=False; app.current_dashboard_homepage=object()
        app.collection_explorer_controller=Controller()
        old, replacement = Window(True), Window()
        app._marketplace_explorer_handles={old:(Label(),Button())}
        app._create_marketplace_replacement_toplevel=lambda: replacement
        app._populate_marketplace_replacement=lambda window,supplied: window
        notebook=type("Notebook",(),{"select":lambda self:"s","index":lambda self,value:0})()
        rendered=type("Rendered",(),{"sections":(type("Section",(),{"destination":CollectionExplorerDestination.SUPPLY_CHANGES})(),)})()
        app._refresh_marketplace_explorer(old,notebook,rendered)
        self.assertIs(app.collection_explorer_controller.cache,candidate)
        self.assertEqual(tuple(app._marketplace_explorer_handles),(replacement,))
        self.assertEqual(replacement._dip_marketplace_registration[0].text,"")
        self.assertIs(app.collection_explorer_controller.open(object()),candidate)

    def test_postpublication_unregister_and_stale_clear_failures_keep_one_truthful_replacement(self):
        class Label:
            def __init__(self, fail=False): self.text = "stale"; self.fail = fail
            def configure(self, *, text):
                if self.fail: raise RuntimeError("HOSTILE stale state")
                self.text = text
        class Button:
            def state(self, value): pass
        class Window:
            def __init__(self, label):
                self._dip_marketplace_registration = (label, Button(), lambda: None)
            def protocol(self, *args): pass
            def bind(self, *args, **kwargs): pass
            def destroy(self): pass
        old_cache, candidate = object(), object()
        class Controller:
            cache = old_cache
            def refresh_marketplace_changes(self): return candidate
            def present_marketplace_candidate(self, *args, **kwargs): return object()
            def render_marketplace_presentation(self, value): return object()
            def install_marketplace_changes(self, value): previous=self.cache; self.cache=value; return previous
            def restore_marketplace_changes(self, previous): self.cache=previous
            def open(self, *args, **kwargs): return self.cache
        for failure in ("unregister", "stale_clear"):
            with self.subTest(failure=failure):
                app=App.__new__(App); app._collector_run_active=False; app.current_dashboard_homepage=object()
                app.collection_explorer_controller=Controller()
                old=Window(Label()); replacement=Window(Label(failure == "stale_clear"))
                app._marketplace_explorer_handles={old:(old._dip_marketplace_registration[0], Button())}
                app._create_marketplace_replacement_toplevel=lambda:replacement
                app._populate_marketplace_replacement=lambda window, supplied:window
                if failure == "unregister":
                    app._unregister_marketplace_window=lambda window: (_ for _ in ()).throw(RuntimeError("HOSTILE unregister"))
                notebook=type("Notebook",(),{"select":lambda self:"s","index":lambda self,value:0})()
                rendered=type("Rendered",(),{"sections":(type("Section",(),{"destination":CollectionExplorerDestination.PRICE_CHANGES})(),)})()
                with patch("dip.experience.desktop.app.messagebox.showerror") as dialog:
                    app._refresh_marketplace_explorer(old,notebook,rendered)
                self.assertIs(app.collection_explorer_controller.cache,candidate)
                self.assertEqual(tuple(app._marketplace_explorer_handles),(replacement,))
                self.assertIs(app.collection_explorer_controller.open(object()),candidate)
                self.assertNotIn("HOSTILE", repr(dialog.call_args))
                if failure == "stale_clear":
                    self.assertEqual(replacement._dip_marketplace_registration[0].text, "stale")
                    replacement._dip_marketplace_registration[0].fail=False
                    retry=Window(Label())
                    app._create_marketplace_replacement_toplevel=lambda:retry
                    app._refresh_marketplace_explorer(replacement,notebook,rendered)
                    self.assertEqual(tuple(app._marketplace_explorer_handles),(retry,))
                    self.assertEqual(retry._dip_marketplace_registration[0].text,"")

    def test_refresh_preserves_every_enabled_destination_and_falls_back_for_disabled(self):
        enabled = tuple(value for value in CollectionExplorerDestination if value not in {
            CollectionExplorerDestination.WEEKEND_LISTINGS,
            CollectionExplorerDestination.RARE_APPEARANCES,
            CollectionExplorerDestination.MARKETPLACE_ACTIVITY,
            CollectionExplorerDestination.LISTING_LIFECYCLE,
            CollectionExplorerDestination.MARKETPLACE_MOMENTUM,
            CollectionExplorerDestination.MARKETPLACE_STABILITY,
            CollectionExplorerDestination.MARKETPLACE_SCARCITY,
            CollectionExplorerDestination.MARKETPLACE_OPPORTUNITY,
        })
        for requested in (*enabled, CollectionExplorerDestination.RARE_APPEARANCES):
            app = App.__new__(App)
            app._collector_run_active = False
            app._marketplace_explorer_handles = {}
            app.current_dashboard_homepage = object()
            opened = []
            class Replacement:
                def __init__(self):
                    self._dip_marketplace_registration = (
                        object(), object(), lambda: None,
                    )
                def protocol(self, *args): pass
                def bind(self, *args, **kwargs): pass
                def destroy(self): pass
            replacement = Replacement()
            app._create_marketplace_replacement_toplevel = lambda: replacement
            app._populate_marketplace_replacement = lambda window, supplied: window
            class Controller:
                def refresh_marketplace_changes(self): return replacement
                def present_marketplace_candidate(self, homepage, candidate, *, selected_destination):
                    opened.append({"selected_destination": selected_destination})
                    return object()
                def render_marketplace_presentation(self, supplied): return object()
                def install_marketplace_changes(self, candidate):
                    previous = getattr(self, "installed", None)
                    self.installed = candidate
                    return previous
                def restore_marketplace_changes(self, previous): self.installed = previous
            app.collection_explorer_controller = Controller()
            class Window:
                def destroy(self): pass
            window = Window()
            app._marketplace_explorer_handles[window] = (type("Label", (), {"configure": lambda self, **kwargs: None})(), type("Button", (), {"state": lambda self, value: None})())
            notebook = type("Notebook", (), {"select": lambda self: "selected", "index": lambda self, value: 0})()
            rendered = type("Rendered", (), {"sections": (type("Section", (), {"destination": requested})(),)})()
            app._refresh_marketplace_explorer(window, notebook, rendered)
            expected = requested if requested in enabled else CollectionExplorerDestination.OVERVIEW
            self.assertIs(opened[0]["selected_destination"], expected)

    def test_stale_marks_two_live_windows_and_ignores_destroyed(self):
        app = App.__new__(App)
        class Window:
            def __init__(self, exists): self.exists = exists
            def winfo_exists(self): return self.exists
        class Label:
            def __init__(self): self.text = None
            def configure(self, *, text): self.text = text
        class Button:
            def __init__(self): self.states = []
            def state(self, value): self.states.append(value)
        live = [(Window(True), Label(), Button()), (Window(True), Label(), Button())]
        dead = Window(False)
        app._marketplace_explorer_handles = {window: (label, button) for window, label, button in live}
        app._marketplace_explorer_handles[dead] = (Label(), Button())
        app._mark_marketplace_explorers_stale()
        for _, label, button in live:
            self.assertEqual(label.text, "Marketplace history has changed. Refresh Marketplace Changes to update these results.")
            self.assertEqual(button.states, [["!disabled"]])
        self.assertNotIn(dead, app._marketplace_explorer_handles)


if __name__ == "__main__":
    unittest.main()
