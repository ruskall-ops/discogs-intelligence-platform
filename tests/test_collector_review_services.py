from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from unittest.mock import patch

from dip.app.collector_review import (
    WeekendReviewApplicationError,
    WeekendObservationService,
    WeekendReviewService,
)
from dip.app.intelligence_history import HistoricalIntelligenceExecution
from dip.app.intelligence_history import IntelligenceHistoryQueryService
from dip.app.marketplace_history import MarketplaceHistoryQueryService
from dip.collector_review import (
    HotNowCalculatedState,
    ObservationIdentity,
    ObservationSectionStatus,
    QueueAddOutcome,
    QueueMembership,
    WeekendObservationSource,
    WeekendReviewConflictError,
    WeekendReviewStatus,
    WeekendReviewTransitionError,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence.modules.hidden_gems import HiddenGemCandidate
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)
from dip.persistence.sqlite import (
    Database,
    SQLiteHotNowCalculatedStateRepository,
    SQLiteIntelligenceHistoryRepository,
    SQLiteMarketplaceHistoryRepository,
    SQLiteWeekendReviewQueueRepository,
)


UTC = timezone.utc


class _HotNowRepository:
    def __init__(self, rows: tuple[HotNowCalculatedState, ...]) -> None:
        self.rows = rows
        self.calls = 0

    def list_hot_now(self) -> tuple[HotNowCalculatedState, ...]:
        self.calls += 1
        return self.rows


class _HistoryQueries:
    def __init__(
        self,
        executions: tuple[HistoricalIntelligenceExecution, ...],
    ) -> None:
        self.executions = executions
        self.latest_calls = 0

    def latest_execution(self) -> HistoricalIntelligenceExecution | None:
        self.latest_calls += 1
        return self.executions[0] if self.executions else None

    def recent_executions(
        self,
        limit: int,
    ) -> tuple[HistoricalIntelligenceExecution, ...]:
        return self.executions[:limit]


class _MarketplaceQueries:
    def __init__(self, snapshots: tuple[MarketplaceSnapshot, ...]) -> None:
        self.snapshots = {value.snapshot_id: value for value in snapshots}

    def get_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None:
        return self.snapshots.get(snapshot_id)


class _QueueReader:
    def __init__(self, items: tuple[object, ...] = ()) -> None:
        self.items = items
        self.calls = 0

    def list_queue(self, statuses=None):
        self.calls += 1
        return self.items


class WeekendObservationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.observed = datetime(2026, 7, 25, 9, tzinfo=UTC)

    def test_projects_current_hot_now_and_hidden_gems_without_execution(self) -> None:
        snapshot = self._snapshot(
            run_id=10,
            releases=(
                self._release(1),
                self._release(2),
            ),
        )
        execution = self._execution(snapshot, (self._candidate(2),))
        hot_repository = _HotNowRepository((self._hot_state(1, 10),))
        queue = _QueueReader()
        history = _HistoryQueries((execution,))
        service = WeekendObservationService(
            hot_repository,
            history,
            _MarketplaceQueries((snapshot,)),
            queue,
        )

        workspace = service.workspace()

        self.assertEqual(len(workspace.hot_now), 1)
        self.assertEqual(len(workspace.hidden_gems), 1)
        self.assertEqual(
            workspace.hot_now[0].source_marketplace_snapshot_id,
            "collector-run-10",
        )
        self.assertEqual(workspace.hot_now[0].warnings, ())
        self.assertEqual(
            workspace.hidden_gems[0].source_intelligence_run_id,
            100,
        )
        self.assertEqual(hot_repository.calls, 1)
        self.assertEqual(queue.calls, 1)
        self.assertEqual(history.latest_calls, 1)

    def test_retained_stale_failed_and_partial_warnings_are_explicit(self) -> None:
        latest = self._snapshot(
            run_id=12,
            releases=(
                self._release(
                    1,
                    status=MarketplaceDataStatus.UNAVAILABLE,
                    diagnostic=True,
                ),
                self._release(2),
                self._release(3),
            ),
            status=MarketplaceDataStatus.PARTIAL,
        )
        older_partial = self._snapshot(
            run_id=10,
            releases=(self._release(1, partial=True),),
            status=MarketplaceDataStatus.PARTIAL,
        )
        older = self._snapshot(
            run_id=9,
            releases=(self._release(2),),
        )
        failed = self._snapshot(
            run_id=13,
            releases=(self._release(3),),
        )
        execution = self._execution(latest, ())
        rows = (
            self._hot_state(1, 10),
            self._hot_state(2, 9),
            self._hot_state(3, 13, analysis_status="failed"),
            self._hot_state(4, None),
        )
        workspace = WeekendObservationService(
            _HotNowRepository(rows),
            _HistoryQueries((execution,)),
            _MarketplaceQueries((latest, older_partial, older, failed)),
            _QueueReader(),
        ).workspace()
        warnings = {
            value.release_id: {warning.code for warning in value.warnings}
            for value in workspace.hot_now
        }

        self.assertIn("hot_now_retained", warnings[1])
        self.assertIn("marketplace_evidence_partial", warnings[1])
        self.assertIn("hot_now_score_stale", warnings[2])
        self.assertIn("hot_now_failed_run", warnings[3])
        self.assertIn("hot_now_provenance_unavailable", warnings[4])
        self.assertEqual(
            next(value for value in workspace.hot_now if value.release_id == 1)
            .evidence.wants,
            100,
        )

    def test_no_history_preserves_hot_now_and_reports_hidden_gems_state(self) -> None:
        workspace = WeekendObservationService(
            _HotNowRepository((self._hot_state(1, None),)),
            _HistoryQueries(()),
            _MarketplaceQueries(()),
            _QueueReader(),
        ).workspace()

        self.assertEqual(len(workspace.hot_now), 1)
        self.assertEqual(
            workspace.hidden_gems_section.status,
            ObservationSectionStatus.NO_HISTORY,
        )

    def test_skipped_hidden_gems_is_available_and_empty(self) -> None:
        record = self._record(
            candidates=(),
            status=IntelligenceStatus.SKIPPED,
        )
        execution = HistoricalIntelligenceExecution(
            IntelligenceHistoryRun(
                100,
                self.observed,
                result_count=1,
                marketplace_snapshot_id=None,
            ),
            (record,),
        )
        workspace = WeekendObservationService(
            _HotNowRepository(()),
            _HistoryQueries((execution,)),
            _MarketplaceQueries(()),
            _QueueReader(),
        ).workspace()
        self.assertEqual(
            workspace.hidden_gems_section.status,
            ObservationSectionStatus.AVAILABLE,
        )
        self.assertEqual(workspace.hidden_gems, ())

    def test_contradictory_persisted_candidate_order_is_unavailable(self) -> None:
        snapshot = self._snapshot(
            run_id=10,
            releases=(self._release(1), self._release(2)),
        )
        execution = self._execution(
            snapshot,
            (
                self._candidate(1, score=60.0),
                self._candidate(2, score=80.0),
            ),
        )
        workspace = WeekendObservationService(
            _HotNowRepository(()),
            _HistoryQueries((execution,)),
            _MarketplaceQueries((snapshot,)),
            _QueueReader(),
        ).workspace()
        self.assertEqual(
            workspace.hidden_gems_section.status,
            ObservationSectionStatus.UNAVAILABLE,
        )

    def test_coherent_window_skips_newest_ineligible_execution(self) -> None:
        older_snapshot = self._snapshot(
            run_id=10,
            releases=(self._release(1),),
        )
        older = self._execution(older_snapshot, ())
        newest_record = IntelligenceHistoryRecord(
            record_id=201,
            run_id=101,
            module_id="hidden_gems",
            module_version="1.0",
            status=IntelligenceStatus.SKIPPED,
            summary="Newest result was skipped.",
        )
        newest_null = HistoricalIntelligenceExecution(
            IntelligenceHistoryRun(
                run_id=101,
                executed_at=self.observed,
                result_count=1,
                marketplace_snapshot_id=None,
            ),
            (newest_record,),
        )
        missing_record = replace(newest_record, record_id=202, run_id=102)
        newest_missing = HistoricalIntelligenceExecution(
            IntelligenceHistoryRun(
                run_id=102,
                executed_at=self.observed,
                result_count=1,
                marketplace_snapshot_id="collector-run-99",
            ),
            (missing_record,),
        )

        for executions in (
            (newest_null, older),
            (newest_missing, older),
        ):
            with self.subTest(newest=executions[0].run.run_id):
                workspace = WeekendObservationService(
                    _HotNowRepository((self._hot_state(1, 10),)),
                    _HistoryQueries(executions),
                    _MarketplaceQueries((older_snapshot,)),
                    _QueueReader(),
                ).workspace()
                self.assertEqual(
                    workspace.hot_now[0].source_marketplace_snapshot_id,
                    "collector-run-10",
                )
                self.assertEqual(workspace.hot_now[0].warnings, ())

        unavailable = WeekendObservationService(
            _HotNowRepository((self._hot_state(1, 10),)),
            _HistoryQueries((newest_null, newest_missing)),
            _MarketplaceQueries((older_snapshot,)),
            _QueueReader(),
        ).workspace()
        self.assertIn(
            "hot_now_provenance_unavailable",
            {warning.code for warning in unavailable.hot_now[0].warnings},
        )

    def _hot_state(
        self,
        release_id: int,
        run_id: int | None,
        *,
        analysis_status: str = "completed",
    ) -> HotNowCalculatedState:
        return HotNowCalculatedState(
            release_id=release_id,
            artist=f"Artist {release_id}",
            title=f"Title {release_id}",
            calculated_at=self.observed,
            value_score=50.0,
            demand_score=60.0,
            liquidity_score=70.0,
            momentum_score=40.0,
            opportunity_score=75.0 - release_id,
            sell_window="Hot now",
            priority="Worth reviewing",
            explanation="Stored explanation.",
            legacy_snapshot_id=None if run_id is None else release_id,
            legacy_analysis_run_id=run_id,
            legacy_analysis_run_status=(
                None if run_id is None else analysis_status
            ),
            legacy_captured_at=None if run_id is None else self.observed,
            wants=None if run_id is None else 100,
            haves=None if run_id is None else 10,
            copies_for_sale=None if run_id is None else 2,
            lowest_price=None if run_id is None else Decimal("12.50"),
            currency=None if run_id is None else "GBP",
            discogs_uri=None,
        )

    def _snapshot(
        self,
        *,
        run_id: int,
        releases: tuple[MarketplaceReleaseObservation, ...],
        status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
    ) -> MarketplaceSnapshot:
        diagnostics = (
            ()
            if status is MarketplaceDataStatus.COMPLETE
            else (
                MarketplaceDiagnostic(
                    "partial_capture",
                    "Some release evidence was unavailable.",
                ),
            )
        )
        return MarketplaceSnapshot(
            snapshot_id=f"collector-run-{run_id}",
            captured_at=self.observed,
            source="discogs",
            status=status,
            release_observations=releases,
            diagnostics=diagnostics,
        )

    def _release(
        self,
        release_id: int,
        *,
        status: MarketplaceDataStatus = MarketplaceDataStatus.COMPLETE,
        partial: bool = False,
        diagnostic: bool = False,
    ) -> MarketplaceReleaseObservation:
        if partial:
            status = MarketplaceDataStatus.PARTIAL
            diagnostic = True
        diagnostics = (
            (
                MarketplaceDiagnostic(
                    "marketplace_fact_missing",
                    "An expected marketplace fact was not supplied.",
                ),
            )
            if diagnostic
            else ()
        )
        if status in {
            MarketplaceDataStatus.UNAVAILABLE,
            MarketplaceDataStatus.FAILED,
            MarketplaceDataStatus.EMPTY,
        }:
            return MarketplaceReleaseObservation(
                release_id,
                self.observed,
                status,
                diagnostics=diagnostics,
            )
        return MarketplaceReleaseObservation(
            release_id,
            self.observed,
            status,
            lowest_price=MarketplaceMoney(Decimal("12.50"), "GBP"),
            num_for_sale=2,
            num_wanted=100,
            diagnostics=diagnostics,
        )

    def _execution(
        self,
        snapshot: MarketplaceSnapshot,
        candidates: tuple[HiddenGemCandidate, ...],
    ) -> HistoricalIntelligenceExecution:
        return HistoricalIntelligenceExecution(
            IntelligenceHistoryRun(
                run_id=100,
                executed_at=self.observed,
                result_count=1,
                marketplace_snapshot_id=snapshot.snapshot_id,
            ),
            (self._record(candidates),),
        )

    def _record(
        self,
        candidates: tuple[HiddenGemCandidate, ...],
        *,
        status: IntelligenceStatus = IntelligenceStatus.COMPLETED,
    ) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=200,
            run_id=100,
            module_id="hidden_gems",
            module_version="1.0",
            status=status,
            summary="Persisted Hidden Gems result.",
            metrics={"ranked_candidates": candidates},
            diagnostics=("Persisted diagnostic.",),
        )

    @staticmethod
    def _candidate(
        release_id: int,
        *,
        score: float = 80.0,
    ) -> HiddenGemCandidate:
        return HiddenGemCandidate(
            release_id=release_id,
            artist=f"Artist {release_id}",
            title=f"Title {release_id}",
            hidden_gem_score=score,
            evidence=("Persisted candidate evidence.",),
            supporting_metrics=MappingProxyType({"wants": 100.0}),
            factor_scores=MappingProxyType({"demand": 80.0}),
        )


class WeekendReviewServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.directory.name) / "queue.db")
        self.database.conn.execute(
            "INSERT INTO releases(release_id, artist, title) VALUES (1, 'Artist', 'Title')"
        )
        self.database.conn.commit()
        self.repository = SQLiteWeekendReviewQueueRepository(self.database)
        self.times = [
            datetime(2026, 7, 25, 10, tzinfo=UTC),
            datetime(2026, 7, 25, 11, tzinfo=UTC),
            datetime(2026, 7, 25, 12, tzinfo=UTC),
            datetime(2026, 7, 25, 13, tzinfo=UTC),
            datetime(2026, 7, 25, 14, tzinfo=UTC),
        ]
        self.clock_calls = 0

        def clock() -> datetime:
            value = self.times[self.clock_calls]
            self.clock_calls += 1
            return value

        self.service = WeekendReviewService(self.repository, clock=clock)
        self.observation = self._observation()

    def tearDown(self) -> None:
        self.database.close()
        self.directory.cleanup()

    def test_add_duplicate_and_frozen_summary_clock_semantics(self) -> None:
        added = self.service.add_from_observation(self.observation)
        duplicate = self.service.add_from_observation(self.observation)

        self.assertEqual(added.outcome, QueueAddOutcome.ADDED)
        self.assertEqual(duplicate.outcome, QueueAddOutcome.EXISTING_ACTIVE)
        self.assertEqual(self.clock_calls, 1)
        self.assertEqual(
            added.item.source_summary,
            (
                "Hot now research signal — opportunity 75.0, momentum 40.0. "
                "Stored explanation."
            ),
        )

    def test_note_status_resolve_reopen_and_no_ops(self) -> None:
        item = self.service.add_from_observation(self.observation).item
        unchanged = self.service.save_note(
            item.queue_item_id,
            "",
            expected_updated_at=item.updated_at,
        )
        self.assertIs(unchanged.status, WeekendReviewStatus.TO_REVIEW)
        self.assertEqual(self.clock_calls, 1)

        reviewing = self.service.set_active_status(
            item.queue_item_id,
            WeekendReviewStatus.REVIEWING,
            expected_updated_at=item.updated_at,
        )
        noted = self.service.save_note(
            item.queue_item_id,
            "  inspect\r\nevidence  ",
            expected_updated_at=reviewing.updated_at,
        )
        resolved = self.service.resolve(
            item.queue_item_id,
            expected_updated_at=noted.updated_at,
        )
        resolved_noop = self.service.resolve(
            item.queue_item_id,
            expected_updated_at=resolved.updated_at,
        )
        reopened = self.service.reopen(
            item.queue_item_id,
            expected_updated_at=resolved.updated_at,
        )

        self.assertEqual(noted.review_note, "inspect\nevidence")
        self.assertEqual(resolved.resolved_at, resolved.updated_at)
        self.assertEqual(resolved_noop, resolved)
        self.assertEqual(reopened.queue_item_id, item.queue_item_id)
        self.assertEqual(reopened.added_at, item.added_at)
        self.assertEqual(reopened.review_note, "inspect\nevidence")
        self.assertEqual(reopened.source_summary, item.source_summary)
        self.assertIsNone(reopened.resolved_at)
        self.assertEqual(self.clock_calls, 5)

    def test_invalid_reopen_and_confirmed_remove_boundary(self) -> None:
        item = self.service.add_from_observation(self.observation).item
        with self.assertRaises(WeekendReviewTransitionError):
            self.service.reopen(
                item.queue_item_id,
                expected_updated_at=item.updated_at,
            )
        deleted = self.service.remove(
            item.queue_item_id,
            expected_updated_at=item.updated_at,
        )
        self.assertEqual(deleted.release_id, 1)
        self.assertIsNone(self.service.get(item.queue_item_id))

    def test_mutation_tokens_advance_for_equal_backward_and_offset_clocks(
        self,
    ) -> None:
        added = self.service.add_from_observation(self.observation).item
        equal_clock_calls = 0

        def equal_clock() -> datetime:
            nonlocal equal_clock_calls
            equal_clock_calls += 1
            return added.updated_at.astimezone(
                timezone(timedelta(hours=-4))
            )

        service = WeekendReviewService(self.repository, clock=equal_clock)
        noted = service.save_note(
            added.queue_item_id,
            "First",
            expected_updated_at=added.updated_at,
        )
        self.assertEqual(
            noted.updated_at,
            added.updated_at.astimezone(UTC) + timedelta(microseconds=1),
        )
        self.assertEqual(equal_clock_calls, 1)

        backward = WeekendReviewService(
            self.repository,
            clock=lambda: added.updated_at - timedelta(days=1),
        ).set_active_status(
            added.queue_item_id,
            WeekendReviewStatus.REVIEWING,
            expected_updated_at=noted.updated_at,
        )
        self.assertEqual(
            backward.updated_at,
            noted.updated_at.astimezone(UTC) + timedelta(microseconds=1),
        )

        later_clock = backward.updated_at.astimezone(
            timezone(timedelta(hours=5))
        ) + timedelta(hours=2)
        later = WeekendReviewService(
            self.repository,
            clock=lambda: later_clock,
        ).save_note(
            added.queue_item_id,
            "Second",
            expected_updated_at=backward.updated_at,
        )
        self.assertEqual(later.updated_at, later_clock)

        resolved = WeekendReviewService(
            self.repository,
            clock=lambda: later.updated_at,
        ).resolve(
            added.queue_item_id,
            expected_updated_at=later.updated_at,
        )
        self.assertEqual(
            resolved.updated_at,
            later.updated_at.astimezone(UTC) + timedelta(microseconds=1),
        )
        self.assertEqual(resolved.resolved_at, resolved.updated_at)

        reopened = WeekendReviewService(
            self.repository,
            clock=lambda: resolved.updated_at,
        ).reopen(
            added.queue_item_id,
            expected_updated_at=resolved.updated_at,
        )
        self.assertEqual(
            reopened.updated_at,
            resolved.updated_at + timedelta(microseconds=1),
        )
        self.assertIsNone(reopened.resolved_at)

    def test_same_clock_write_invalidates_stale_writer_and_fresh_token_succeeds(
        self,
    ) -> None:
        added = self.service.add_from_observation(self.observation).item
        service = WeekendReviewService(
            self.repository,
            clock=lambda: added.updated_at,
        )
        winner = service.save_note(
            added.queue_item_id,
            "Winner",
            expected_updated_at=added.updated_at,
        )
        with self.assertRaises(WeekendReviewConflictError):
            service.save_note(
                added.queue_item_id,
                "Stale",
                expected_updated_at=added.updated_at,
            )
        fresh = service.save_note(
            added.queue_item_id,
            "Fresh",
            expected_updated_at=winner.updated_at,
        )
        self.assertEqual(fresh.review_note, "Fresh")
        self.assertGreater(fresh.updated_at, winner.updated_at)

    def test_no_ops_do_not_call_clock_and_overflow_is_safe(self) -> None:
        added = self.service.add_from_observation(self.observation).item
        calls = 0

        def clock() -> datetime:
            nonlocal calls
            calls += 1
            return added.updated_at

        service = WeekendReviewService(self.repository, clock=clock)
        self.assertEqual(
            service.save_note(
                added.queue_item_id,
                "",
                expected_updated_at=added.updated_at,
            ),
            added,
        )
        self.assertEqual(
            service.set_active_status(
                added.queue_item_id,
                WeekendReviewStatus.TO_REVIEW,
                expected_updated_at=added.updated_at,
            ),
            added,
        )
        self.assertEqual(calls, 0)

        maximum = datetime.max.replace(tzinfo=UTC)
        before = self.repository.get_by_id(added.queue_item_id)
        overflow_item = replace(added, updated_at=maximum)
        with patch.object(
            self.repository,
            "get_by_id",
            return_value=overflow_item,
        ):
            with self.assertRaisesRegex(
                WeekendReviewApplicationError,
                "could not be updated safely",
            ):
                WeekendReviewService(
                    self.repository,
                    clock=lambda: maximum,
                ).save_note(
                    added.queue_item_id,
                    "Overflow",
                    expected_updated_at=maximum,
                )
        self.assertEqual(self.repository.get_by_id(added.queue_item_id), before)

    def test_real_sqlite_hot_now_freshness_preserves_score_origin_evidence(
        self,
    ) -> None:
        old_time = datetime(2026, 7, 25, 9, tzinfo=UTC)
        run_id = self.database.start_analysis_run()
        captured = old_time.isoformat(timespec="seconds")
        self.database.add_snapshot(
            run_id,
            1,
            captured,
            {
                "wants": 111,
                "haves": 11,
                "copies_for_sale": 2,
                "lowest_price": 12.5,
                "currency": "GBP",
            },
        )
        self.database.upsert_score(
            1,
            captured,
            {
                "value_score": 10.0,
                "demand_score": 20.0,
                "liquidity_score": 30.0,
                "momentum_score": 40.0,
                "opportunity_score": 80.0,
                "sell_window": "Hot now",
                "priority": "Worth reviewing",
                "explanation": "Original score evidence.",
            },
        )
        self.database.complete_analysis_run(run_id, 1, 1, 0)
        marketplace_repository = SQLiteMarketplaceHistoryRepository(
            self.database
        )
        intelligence_repository = SQLiteIntelligenceHistoryRepository(
            self.database
        )

        def snapshot(
            identity: int,
            instant: datetime,
            status: MarketplaceDataStatus,
            release_status: MarketplaceDataStatus,
            wants: int | None,
        ) -> MarketplaceSnapshot:
            diagnostics = (
                ()
                if status is MarketplaceDataStatus.COMPLETE
                else (
                    MarketplaceDiagnostic(
                        "partial_capture",
                        "Some Marketplace facts were unavailable.",
                    ),
                )
            )
            release_diagnostics = (
                ()
                if release_status is MarketplaceDataStatus.COMPLETE
                else (
                    MarketplaceDiagnostic(
                        "release_unavailable",
                        "Release evidence was unavailable.",
                    ),
                )
            )
            release = MarketplaceReleaseObservation(
                1,
                instant,
                release_status,
                num_wanted=wants,
                diagnostics=release_diagnostics,
            )
            return MarketplaceSnapshot(
                f"collector-run-{identity}",
                instant,
                "discogs",
                status,
                (release,),
                diagnostics=diagnostics,
            )

        def persist_window(value: MarketplaceSnapshot) -> None:
            marketplace_repository.save_snapshot(value)
            intelligence_repository.save_execution(
                IntelligenceHistoryRun(
                    None,
                    value.captured_at,
                    "0.2",
                    None,
                    0,
                    value.snapshot_id,
                ),
                (),
            )

        origin = snapshot(
            run_id,
            old_time,
            MarketplaceDataStatus.COMPLETE,
            MarketplaceDataStatus.COMPLETE,
            111,
        )
        persist_window(origin)
        partial = snapshot(
            run_id + 1,
            old_time + timedelta(days=1),
            MarketplaceDataStatus.PARTIAL,
            MarketplaceDataStatus.UNAVAILABLE,
            None,
        )
        persist_window(partial)
        observation_service = WeekendObservationService(
            SQLiteHotNowCalculatedStateRepository(self.database),
            IntelligenceHistoryQueryService(intelligence_repository),
            MarketplaceHistoryQueryService(marketplace_repository),
            self.repository,
        )
        retained = observation_service.workspace().hot_now[0]
        self.assertIn(
            "hot_now_retained",
            {warning.code for warning in retained.warnings},
        )
        self.assertEqual(retained.evidence.wants, 111)
        self.assertEqual(
            retained.source_marketplace_snapshot_id,
            f"collector-run-{run_id}",
        )

        newer = snapshot(
            run_id + 2,
            old_time + timedelta(days=2),
            MarketplaceDataStatus.COMPLETE,
            MarketplaceDataStatus.COMPLETE,
            999,
        )
        persist_window(newer)
        stale = observation_service.workspace().hot_now[0]
        self.assertIn(
            "hot_now_score_stale",
            {warning.code for warning in stale.warnings},
        )
        self.assertEqual(stale.evidence.wants, 111)

        self.database.conn.execute(
            "UPDATE analysis_runs SET status='failed' WHERE id=?",
            (run_id,),
        )
        self.database.conn.commit()
        failed = observation_service.workspace().hot_now[0]
        self.assertIn(
            "hot_now_failed_run",
            {warning.code for warning in failed.warnings},
        )
        self.assertEqual(failed.evidence.wants, 111)

        fatal_time = old_time + timedelta(days=3)
        self.database.conn.execute(
            """
            INSERT INTO analysis_runs(id, run_type, source, status)
            VALUES (50, 'market_refresh', 'discogs', 'running')
            """
        )
        self.database.conn.commit()
        fatal_captured = fatal_time.isoformat(timespec="seconds")
        self.database.add_snapshot(
            50,
            1,
            fatal_captured,
            {
                "wants": 333,
                "haves": 33,
                "copies_for_sale": 3,
                "lowest_price": 33.0,
                "currency": "GBP",
            },
        )
        self.database.upsert_score(
            1,
            fatal_captured,
            {
                "value_score": 11.0,
                "demand_score": 22.0,
                "liquidity_score": 33.0,
                "momentum_score": 44.0,
                "opportunity_score": 88.0,
                "sell_window": "Hot now",
                "priority": "Worth reviewing",
                "explanation": "Pre-canonical fatal evidence.",
            },
        )
        self.database.fail_analysis_run(50, "safe failure", 1, 1, 0)
        pre_capture_fatal = observation_service.workspace().hot_now[0]
        self.assertIn(
            "hot_now_failed_run",
            {warning.code for warning in pre_capture_fatal.warnings},
        )
        self.assertIsNone(
            pre_capture_fatal.source_marketplace_snapshot_id
        )
        self.assertEqual(pre_capture_fatal.evidence.wants, 333)

        self.database.conn.execute(
            """
            INSERT INTO analysis_runs(
                id, run_type, source, status, releases_attempted,
                releases_succeeded, releases_failed
            ) VALUES (51, 'market_refresh', 'discogs', 'failed', 1, 0, 1)
            """
        )
        self.database.conn.commit()
        after_zero_success = observation_service.workspace().hot_now[0]
        self.assertEqual(
            after_zero_success.calculated_at,
            pre_capture_fatal.calculated_at,
        )
        self.assertEqual(after_zero_success.evidence.wants, 333)

    def _observation(self):
        from dip.collector_review import HotNowObservation

        observed = datetime(2026, 7, 25, 9, tzinfo=UTC)
        return HotNowObservation(
            observation_id=ObservationIdentity(
                WeekendObservationSource.HOT_NOW,
                1,
            ),
            release_id=1,
            artist="Artist",
            title="Title",
            calculated_at=observed,
            source_observed_at=observed,
            value_score=50.0,
            demand_score=60.0,
            liquidity_score=70.0,
            momentum_score=40.0,
            opportunity_score=75.0,
            sell_window="Hot now",
            priority="Worth reviewing",
            explanation="Stored explanation.",
            evidence=None,
            queue_membership=QueueMembership(),
        )


if __name__ == "__main__":
    unittest.main()
