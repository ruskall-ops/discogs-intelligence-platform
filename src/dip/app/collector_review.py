"""Application boundaries for calculated observations and collector review."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, Protocol

from dip.collector_review import (
    CollectorReviewIntegrityError,
    CollectorReviewPersistenceError,
    HiddenGemObservation,
    HotNowCalculatedState,
    HotNowCalculatedStateRepository,
    HotNowObservation,
    MarketplaceEvidenceDetail,
    NewWeekendReviewQueueEntry,
    ObservationIdentity,
    ObservationSectionStatus,
    ObservationSourceSection,
    ObservationWarning,
    QueueAddOutcome,
    QueueAddResult,
    QueueMembership,
    WeekendObservation,
    WeekendObservationSource,
    WeekendObservationWorkspace,
    WeekendReviewConflictError,
    WeekendReviewItemNotFoundError,
    WeekendReviewQueueItem,
    WeekendReviewQueueRepository,
    WeekendReviewStatus,
    WeekendReviewTransitionError,
    normalize_review_note,
    normalize_source_summary,
)
from dip.intelligence import IntelligenceStatus
from dip.intelligence.modules.hidden_gems import HiddenGemCandidate
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)

from .intelligence_history import (
    HistoricalIntelligenceExecution,
    IntelligenceHistoryConsistencyError,
)
from .marketplace_history import MarketplaceHistoryConsistencyError


_COLLECTOR_RUN_SNAPSHOT = re.compile(r"^collector-run-([1-9]\d*)$")
_ALL_EXECUTIONS_LIMIT = 2_147_483_647
_OBSERVATION_UNAVAILABLE = "Collector Review observations are unavailable."


class WeekendReviewApplicationError(RuntimeError):
    """Fixed safe failure raised by Weekend Review application orchestration."""


class _IntelligenceHistoryQueries(Protocol):
    def latest_execution(self) -> HistoricalIntelligenceExecution | None: ...

    def recent_executions(
        self,
        limit: int,
    ) -> tuple[HistoricalIntelligenceExecution, ...]: ...


class _MarketplaceHistoryQueries(Protocol):
    def get_snapshot(self, snapshot_id: str) -> MarketplaceSnapshot | None: ...


def utc_now() -> datetime:
    """Return the production queue clock value."""

    return datetime.now(timezone.utc)


class WeekendObservationService:
    """Project persisted calculated evidence into one immutable workspace."""

    def __init__(
        self,
        hot_now_repository: HotNowCalculatedStateRepository,
        intelligence_history: _IntelligenceHistoryQueries,
        marketplace_history: _MarketplaceHistoryQueries,
        queue_repository: WeekendReviewQueueRepository,
    ) -> None:
        self._hot_now_repository = hot_now_repository
        self._intelligence_history = intelligence_history
        self._marketplace_history = marketplace_history
        self._queue_repository = queue_repository

    def workspace(self) -> WeekendObservationWorkspace:
        """Load observations once without calculation, execution, or mutation."""

        try:
            queue_by_release = {
                item.release_id: item
                for item in self._queue_repository.list_queue()
            }
            executions = self._intelligence_history.recent_executions(
                _ALL_EXECUTIONS_LIMIT
            )
            latest_execution = self._intelligence_history.latest_execution()
            coherent = self._latest_coherent(executions)
            hot_now = tuple(
                self._hot_now_observation(value, coherent, queue_by_release)
                for value in self._hot_now_repository.list_hot_now()
            )
            hidden_section = self._hidden_gems_section(
                latest_execution,
                queue_by_release,
            )
            return WeekendObservationWorkspace(
                hot_now_section=ObservationSourceSection(
                    WeekendObservationSource.HOT_NOW,
                    ObservationSectionStatus.AVAILABLE,
                    (
                        f"{len(hot_now)} stored Hot now research "
                        f"{'signal' if len(hot_now) == 1 else 'signals'}."
                    ),
                    hot_now,
                ),
                hidden_gems_section=hidden_section,
            )
        except (
            CollectorReviewIntegrityError,
            CollectorReviewPersistenceError,
            IntelligenceHistoryConsistencyError,
            MarketplaceHistoryConsistencyError,
        ):
            return WeekendObservationWorkspace.unavailable(
                _OBSERVATION_UNAVAILABLE
            )

    def _latest_coherent(
        self,
        executions: tuple[HistoricalIntelligenceExecution, ...],
    ) -> tuple[HistoricalIntelligenceExecution, MarketplaceSnapshot] | None:
        for execution in executions:
            snapshot_id = execution.run.marketplace_snapshot_id
            if snapshot_id is None:
                continue
            snapshot = self._marketplace_history.get_snapshot(snapshot_id)
            if snapshot is None:
                continue
            if self._coherent_snapshot(execution, snapshot):
                return execution, snapshot
        return None

    @staticmethod
    def _coherent_snapshot(
        execution: HistoricalIntelligenceExecution,
        snapshot: MarketplaceSnapshot,
    ) -> bool:
        run_id = execution.run.run_id
        snapshot_id = execution.run.marketplace_snapshot_id
        if type(run_id) is not int or snapshot_id != snapshot.snapshot_id:
            return False
        match = _COLLECTOR_RUN_SNAPSHOT.fullmatch(snapshot.snapshot_id)
        return (
            match is not None
            and int(match.group(1)) > 0
            and _same_instant(execution.run.executed_at, snapshot.captured_at)
            and snapshot.status
            in {MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.PARTIAL}
        )

    def _hot_now_observation(
        self,
        value: HotNowCalculatedState,
        coherent: tuple[
            HistoricalIntelligenceExecution,
            MarketplaceSnapshot,
        ]
        | None,
        queue_by_release: Mapping[int, WeekendReviewQueueItem],
    ) -> HotNowObservation:
        source_snapshot: MarketplaceSnapshot | None = None
        source_release: MarketplaceReleaseObservation | None = None
        warnings: list[ObservationWarning] = []
        source_snapshot_id: str | None = None

        if value.legacy_analysis_run_id is not None:
            candidate_id = f"collector-run-{value.legacy_analysis_run_id}"
            candidate = self._marketplace_history.get_snapshot(candidate_id)
            if (
                candidate is not None
                and candidate.snapshot_id == candidate_id
                and value.legacy_captured_at is not None
                and _same_instant(
                    candidate.captured_at,
                    value.legacy_captured_at,
                )
            ):
                release = _release_observation(candidate, value.release_id)
                if (
                    release is not None
                    and _same_instant(
                        release.observed_at,
                        value.legacy_captured_at,
                    )
                    and release.status
                    in {
                        MarketplaceDataStatus.COMPLETE,
                        MarketplaceDataStatus.PARTIAL,
                    }
                ):
                    source_snapshot = candidate
                    source_release = release
                    source_snapshot_id = candidate.snapshot_id

        if value.legacy_analysis_run_status == "failed":
            warnings.append(
                ObservationWarning(
                    "hot_now_failed_run",
                    (
                        "This stored score was updated during a Collector Run "
                        "that later failed."
                    ),
                )
            )
        elif source_snapshot is None:
            warnings.append(
                ObservationWarning(
                    "hot_now_provenance_unavailable",
                    (
                        "Canonical Marketplace provenance is unavailable for "
                        "this stored score."
                    ),
                )
            )
        elif coherent is None:
            warnings.append(
                ObservationWarning(
                    "hot_now_provenance_unavailable",
                    (
                        "No coherent Intelligence evidence window confirms "
                        "this stored score."
                    ),
                )
            )
        elif coherent is not None:
            latest_execution, latest_snapshot = coherent
            if source_snapshot.snapshot_id != latest_snapshot.snapshot_id:
                latest_release = _release_observation(
                    latest_snapshot,
                    value.release_id,
                )
                if (
                    latest_release is None
                    or latest_release.status
                    in {
                        MarketplaceDataStatus.EMPTY,
                        MarketplaceDataStatus.UNAVAILABLE,
                        MarketplaceDataStatus.FAILED,
                    }
                ):
                    warnings.append(
                        ObservationWarning(
                            "hot_now_retained",
                            (
                                "This signal was retained because the latest "
                                "coherent evidence window did not provide usable "
                                "evidence for this release."
                            ),
                        )
                    )
                else:
                    warnings.append(
                        ObservationWarning(
                            "hot_now_score_stale",
                            (
                                "Newer usable Marketplace evidence exists, but "
                                "this stored Hot now score is older."
                            ),
                        )
                    )
            elif (
                latest_execution.run.marketplace_snapshot_id
                != source_snapshot.snapshot_id
            ):
                warnings.append(
                    ObservationWarning(
                        "hot_now_provenance_unavailable",
                        (
                            "The stored score does not match the latest coherent "
                            "Intelligence evidence."
                        ),
                    )
                )

        if (
            source_release is not None
            and source_release.status is MarketplaceDataStatus.PARTIAL
        ):
            warnings.append(
                ObservationWarning(
                    "marketplace_evidence_partial",
                    "The score-origin Marketplace evidence is partial.",
                )
            )
            warnings.extend(_diagnostic_warnings(source_release))

        membership = _membership(queue_by_release.get(value.release_id))
        evidence = (
            None
            if value.legacy_captured_at is None
            else MarketplaceEvidenceDetail(
                release_id=value.release_id,
                observed_at=value.legacy_captured_at,
                status=(
                    None if source_release is None else source_release.status
                ),
                wants=value.wants,
                haves=value.haves,
                copies_for_sale=value.copies_for_sale,
                lowest_price=value.lowest_price,
                currency=value.currency,
                discogs_uri=value.discogs_uri,
                diagnostics=(
                    ()
                    if source_release is None
                    else _diagnostic_warnings(source_release)
                ),
            )
        )
        return HotNowObservation(
            observation_id=ObservationIdentity(
                WeekendObservationSource.HOT_NOW,
                value.release_id,
            ),
            release_id=value.release_id,
            artist=_one_line(value.artist),
            title=_one_line(value.title),
            calculated_at=value.calculated_at,
            source_observed_at=(
                value.legacy_captured_at or value.calculated_at
            ),
            value_score=float(value.value_score),
            demand_score=float(value.demand_score),
            liquidity_score=float(value.liquidity_score),
            momentum_score=float(value.momentum_score),
            opportunity_score=float(value.opportunity_score),
            sell_window=value.sell_window,
            priority=_one_line(value.priority),
            explanation=_one_line(value.explanation),
            evidence=evidence,
            warnings=_deduplicate_warnings(tuple(warnings)),
            queue_membership=membership,
            source_marketplace_snapshot_id=source_snapshot_id,
        )

    def _hidden_gems_section(
        self,
        execution: HistoricalIntelligenceExecution | None,
        queue_by_release: Mapping[int, WeekendReviewQueueItem],
    ) -> ObservationSourceSection:
        if execution is None:
            return ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.NO_HISTORY,
                "No persisted Collection Intelligence execution is available.",
            )
        record = next(
            (
                value
                for value in execution.records
                if value.module_id == "hidden_gems"
            ),
            None,
        )
        if record is None:
            return ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.UNAVAILABLE,
                "Hidden Gems is unavailable in the latest Intelligence execution.",
            )
        if record.status not in {
            IntelligenceStatus.COMPLETED,
            IntelligenceStatus.SKIPPED,
        }:
            return ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.UNAVAILABLE,
                "The latest Hidden Gems result is unavailable.",
            )
        if record.status is IntelligenceStatus.SKIPPED:
            return ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.AVAILABLE,
                _required_line(record.summary, "Hidden Gems was skipped."),
                diagnostics=tuple(_one_line(value) for value in record.diagnostics),
            )

        run_id = execution.run.run_id
        if type(run_id) is not int or run_id <= 0:
            return ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.UNAVAILABLE,
                "The latest Hidden Gems provenance is unavailable.",
            )
        snapshot: MarketplaceSnapshot | None = None
        snapshot_id = execution.run.marketplace_snapshot_id
        legacy_warning = snapshot_id is None
        if snapshot_id is not None:
            snapshot = self._marketplace_history.get_snapshot(snapshot_id)
            if snapshot is None or not self._coherent_snapshot(execution, snapshot):
                return ObservationSourceSection(
                    WeekendObservationSource.HIDDEN_GEM,
                    ObservationSectionStatus.UNAVAILABLE,
                    "The latest Hidden Gems Marketplace provenance is unavailable.",
                )

        candidates = record.metrics.get("ranked_candidates")
        if type(candidates) is not tuple or any(
            type(value) is not HiddenGemCandidate for value in candidates
        ):
            return ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.UNAVAILABLE,
                "The persisted Hidden Gems candidate data is unavailable.",
            )
        if not _canonical_hidden_gem_order(candidates):
            return ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.UNAVAILABLE,
                "The persisted Hidden Gems candidate order is inconsistent.",
            )

        observations: list[HiddenGemObservation] = []
        for rank, candidate in enumerate(candidates, start=1):
            warnings: list[ObservationWarning] = []
            marketplace_evidence = None
            if legacy_warning:
                warnings.append(
                    ObservationWarning(
                        "hidden_gem_marketplace_provenance_unavailable",
                        (
                            "Marketplace provenance is unavailable for this "
                            "legacy Hidden Gems result."
                        ),
                    )
                )
            elif snapshot is not None:
                release = _release_observation(snapshot, candidate.release_id)
                if release is None:
                    warnings.append(
                        ObservationWarning(
                            "hidden_gem_marketplace_evidence_unavailable",
                            (
                                "Matching Marketplace evidence is unavailable "
                                "for this persisted candidate."
                            ),
                        )
                    )
                else:
                    diagnostic_warnings = _diagnostic_warnings(release)
                    if release.status is MarketplaceDataStatus.PARTIAL:
                        warnings.append(
                            ObservationWarning(
                                "marketplace_evidence_partial",
                                "The persisted candidate used partial Marketplace evidence.",
                            )
                        )
                    warnings.extend(diagnostic_warnings)
                    marketplace_evidence = _canonical_evidence(
                        release,
                        diagnostic_warnings,
                    )

            observations.append(
                HiddenGemObservation(
                    observation_id=ObservationIdentity(
                        WeekendObservationSource.HIDDEN_GEM,
                        candidate.release_id,
                    ),
                    release_id=candidate.release_id,
                    artist=_one_line(candidate.artist),
                    title=_one_line(candidate.title),
                    rank=rank,
                    hidden_gem_score=float(candidate.hidden_gem_score),
                    factor_scores=candidate.factor_scores,
                    supporting_metrics=candidate.supporting_metrics,
                    summary=_required_line(
                        record.summary,
                        "Persisted Hidden Gems result.",
                    ),
                    evidence=tuple(
                        _one_line(value)
                        for value in candidate.evidence
                        if _one_line(value)
                    ),
                    execution_timestamp=execution.run.executed_at,
                    source_intelligence_run_id=run_id,
                    source_marketplace_snapshot_id=snapshot_id,
                    marketplace_evidence=marketplace_evidence,
                    warnings=_deduplicate_warnings(tuple(warnings)),
                    queue_membership=_membership(
                        queue_by_release.get(candidate.release_id)
                    ),
                )
            )
        return ObservationSourceSection(
            WeekendObservationSource.HIDDEN_GEM,
            ObservationSectionStatus.AVAILABLE,
            _required_line(record.summary, "Persisted Hidden Gems result."),
            tuple(observations),
            tuple(_one_line(value) for value in record.diagnostics),
        )


class WeekendReviewService:
    """Coordinate explicit collector-owned queue mutations."""

    def __init__(
        self,
        repository: WeekendReviewQueueRepository,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not callable(clock):
            raise TypeError("clock must be callable.")
        self._repository = repository
        self._clock = clock

    def add_from_observation(
        self,
        observation: WeekendObservation,
    ) -> QueueAddResult:
        if type(observation) not in {HotNowObservation, HiddenGemObservation}:
            raise TypeError(
                "observation must be a HotNowObservation or HiddenGemObservation."
            )
        existing = self._repository.get_by_release_id(observation.release_id)
        if existing is not None:
            return QueueAddResult(
                (
                    QueueAddOutcome.EXISTING_RESOLVED
                    if existing.status is WeekendReviewStatus.RESOLVED
                    else QueueAddOutcome.EXISTING_ACTIVE
                ),
                existing,
            )
        now = self._now()
        entry = NewWeekendReviewQueueEntry(
            release_id=observation.release_id,
            added_at=now,
            status=WeekendReviewStatus.TO_REVIEW,
            review_note="",
            updated_at=now,
            resolved_at=None,
            source_type=observation.observation_id.source,
            source_observed_at=_source_observed_at(observation),
            source_summary=_source_summary(observation),
            source_intelligence_run_id=(
                None
                if type(observation) is HotNowObservation
                else observation.source_intelligence_run_id
            ),
            source_marketplace_snapshot_id=(
                observation.source_marketplace_snapshot_id
            ),
        )
        return self._repository.add_or_get_existing(entry)

    def list_queue(
        self,
        statuses: tuple[WeekendReviewStatus, ...] | None = None,
    ) -> tuple[WeekendReviewQueueItem, ...]:
        return self._repository.list_queue(statuses)

    def get(self, queue_item_id: int) -> WeekendReviewQueueItem | None:
        return self._repository.get_by_id(queue_item_id)

    def save_note(
        self,
        queue_item_id: int,
        note: str,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        current = self._current(queue_item_id, expected_updated_at)
        normalized = normalize_review_note(note)
        if normalized == current.review_note:
            return current
        updated = replace(
            current,
            review_note=normalized,
            updated_at=self._mutation_time(current),
        )
        return self._repository.save(
            updated,
            expected_updated_at=expected_updated_at,
        )

    def set_active_status(
        self,
        queue_item_id: int,
        status: WeekendReviewStatus,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        if type(status) is not WeekendReviewStatus:
            raise TypeError("status must be a WeekendReviewStatus.")
        if status is WeekendReviewStatus.RESOLVED:
            raise WeekendReviewTransitionError(
                "Resolve must use the explicit resolve operation."
            )
        current = self._current(queue_item_id, expected_updated_at)
        if current.status is WeekendReviewStatus.RESOLVED:
            raise WeekendReviewTransitionError(
                "A resolved item must be reopened explicitly."
            )
        if current.status is status:
            return current
        permitted = {
            (
                WeekendReviewStatus.TO_REVIEW,
                WeekendReviewStatus.REVIEWING,
            ),
            (
                WeekendReviewStatus.REVIEWING,
                WeekendReviewStatus.TO_REVIEW,
            ),
        }
        if (current.status, status) not in permitted:
            raise WeekendReviewTransitionError(
                "The requested queue status transition is not permitted."
            )
        updated = replace(
            current,
            status=status,
            updated_at=self._mutation_time(current),
        )
        return self._repository.save(
            updated,
            expected_updated_at=expected_updated_at,
        )

    def resolve(
        self,
        queue_item_id: int,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        current = self._current(queue_item_id, expected_updated_at)
        if current.status is WeekendReviewStatus.RESOLVED:
            return current
        now = self._mutation_time(current)
        updated = replace(
            current,
            status=WeekendReviewStatus.RESOLVED,
            updated_at=now,
            resolved_at=now,
        )
        return self._repository.save(
            updated,
            expected_updated_at=expected_updated_at,
        )

    def reopen(
        self,
        queue_item_id: int,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        current = self._current(queue_item_id, expected_updated_at)
        if current.status is not WeekendReviewStatus.RESOLVED:
            raise WeekendReviewTransitionError(
                "Only a resolved queue item can be reopened."
            )
        updated = replace(
            current,
            status=WeekendReviewStatus.TO_REVIEW,
            updated_at=self._mutation_time(current),
            resolved_at=None,
        )
        return self._repository.save(
            updated,
            expected_updated_at=expected_updated_at,
        )

    def remove(
        self,
        queue_item_id: int,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        self._current(queue_item_id, expected_updated_at)
        return self._repository.delete(
            queue_item_id,
            expected_updated_at=expected_updated_at,
        )

    def _current(
        self,
        queue_item_id: int,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem:
        current = self._repository.get_by_id(queue_item_id)
        if current is None:
            raise WeekendReviewItemNotFoundError(
                "The Weekend Review Queue item no longer exists."
            )
        if not _same_instant(current.updated_at, expected_updated_at):
            raise WeekendReviewConflictError(
                "The Weekend Review Queue item changed after it was loaded."
            )
        return current

    def _now(self) -> datetime:
        value = self._clock()
        if type(value) is not datetime:
            raise TypeError("Weekend Review clock must return a datetime.")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Weekend Review clock must be timezone-aware.")
        return value

    def _mutation_time(
        self,
        current: WeekendReviewQueueItem,
    ) -> datetime:
        """Return one clock-derived token strictly after the persisted token."""

        observed = self._now()
        try:
            current_utc = current.updated_at.astimezone(timezone.utc)
            observed_utc = observed.astimezone(timezone.utc)
            if observed_utc > current_utc:
                return observed
            return current_utc + timedelta(microseconds=1)
        except OverflowError:
            raise WeekendReviewApplicationError(
                "The Weekend Review Queue item could not be updated safely."
            ) from None


def _source_summary(observation: WeekendObservation) -> str:
    if type(observation) is HotNowObservation:
        explanation = normalize_source_summary(observation.explanation)
        suffix = f" {explanation}" if explanation else ""
        return normalize_source_summary(
            "Hot now research signal — "
            f"opportunity {observation.opportunity_score:.1f}, "
            f"momentum {observation.momentum_score:.1f}.{suffix}"
        )
    evidence = next(
        (
            normalize_source_summary(value)
            for value in observation.evidence
            if normalize_source_summary(value)
        ),
        "Persisted Collection Intelligence candidate.",
    )
    return normalize_source_summary(
        f"Hidden Gem #{observation.rank} research signal — "
        f"score {observation.hidden_gem_score:.1f}. {evidence}"
    )


def _source_observed_at(observation: WeekendObservation) -> datetime:
    return (
        observation.source_observed_at
        if type(observation) is HotNowObservation
        else observation.execution_timestamp
    )


def _canonical_hidden_gem_order(
    candidates: tuple[HiddenGemCandidate, ...],
) -> bool:
    scores = []
    for candidate in candidates:
        if (
            isinstance(candidate.hidden_gem_score, bool)
            or not isinstance(candidate.hidden_gem_score, (int, float))
            or not math.isfinite(float(candidate.hidden_gem_score))
        ):
            return False
        scores.append(candidate)
    return tuple(scores) == tuple(
        sorted(
            scores,
            key=lambda value: (
                -float(value.hidden_gem_score),
                value.release_id,
            ),
        )
    )


def _release_observation(
    snapshot: MarketplaceSnapshot,
    release_id: int,
) -> MarketplaceReleaseObservation | None:
    return next(
        (
            value
            for value in snapshot.release_observations
            if value.release_id == release_id
        ),
        None,
    )


def _canonical_evidence(
    release: MarketplaceReleaseObservation,
    diagnostics: tuple[ObservationWarning, ...],
) -> MarketplaceEvidenceDetail:
    money = release.lowest_price
    return MarketplaceEvidenceDetail(
        release_id=release.release_id,
        observed_at=release.observed_at,
        status=release.status,
        wants=release.num_wanted,
        copies_for_sale=release.num_for_sale,
        lowest_price=None if money is None else money.amount,
        currency=None if money is None else money.currency,
        diagnostics=diagnostics,
    )


def _diagnostic_warnings(
    release: MarketplaceReleaseObservation,
) -> tuple[ObservationWarning, ...]:
    return tuple(
        ObservationWarning(
            value.code,
            _required_line(value.message, "Marketplace evidence is incomplete."),
        )
        for value in release.diagnostics
    )


def _deduplicate_warnings(
    warnings: tuple[ObservationWarning, ...],
) -> tuple[ObservationWarning, ...]:
    result: list[ObservationWarning] = []
    seen: set[tuple[str, str]] = set()
    for warning in warnings:
        key = (warning.code, warning.message)
        if key not in seen:
            seen.add(key)
            result.append(warning)
    return tuple(result)


def _membership(item: WeekendReviewQueueItem | None) -> QueueMembership:
    return (
        QueueMembership()
        if item is None
        else QueueMembership(item.queue_item_id, item.status)
    )


def _same_instant(left: datetime, right: datetime) -> bool:
    if type(left) is not datetime or type(right) is not datetime:
        return False
    if (
        left.tzinfo is None
        or left.utcoffset() is None
        or right.tzinfo is None
        or right.utcoffset() is None
    ):
        return False
    return left.astimezone(timezone.utc) == right.astimezone(timezone.utc)


def _one_line(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _required_line(value: Any, fallback: str) -> str:
    normalized = _one_line(value)
    return normalized or fallback


__all__ = [
    "WeekendObservationService",
    "WeekendReviewService",
]
