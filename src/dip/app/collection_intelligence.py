"""Application orchestration for executing and recording intelligence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from dip.intelligence import (
    IntelligenceContext,
    IntelligenceExecution,
    IntelligenceResult,
    IntelligenceStatus,
)
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRepository,
    IntelligenceHistoryRun,
)
from dip.marketplace_intelligence import MarketplaceSnapshot


class _IntelligenceEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


class _IntelligenceContextFactory(Protocol):
    def build_collector_run(
        self,
        *,
        analysis_run_id: int,
        marketplace_snapshot: MarketplaceSnapshot,
        release_ids: tuple[int, ...],
        captured_at: datetime,
    ) -> IntelligenceContext: ...


@dataclass(frozen=True)
class RecordedIntelligenceExecution:
    """Current intelligence together with its persisted historical run."""

    execution: IntelligenceExecution
    history_run: IntelligenceHistoryRun


class IntelligenceExecutionIncompleteError(RuntimeError):
    """Raised when one or more intended modules did not complete."""

    def __init__(self, execution: IntelligenceExecution) -> None:
        self.execution = execution
        incomplete = tuple(
            result.module_id
            for result in execution.results
            if result.status != IntelligenceStatus.COMPLETED
        )
        modules = ", ".join(incomplete) or "unknown modules"
        super().__init__(f"Intelligence execution did not complete: {modules}.")


class CollectionIntelligenceExecutionService:
    """Execute Collection Intelligence and persist one complete observation."""

    def __init__(
        self,
        engine: _IntelligenceEngine,
        history_repository: IntelligenceHistoryRepository,
        context_factory: _IntelligenceContextFactory | None = None,
        *,
        engine_version: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._engine = engine
        self._history_repository = history_repository
        self._context_factory = context_factory
        self._engine_version = engine_version
        self._clock = clock or _utc_now

    def execute(
        self,
        context: IntelligenceContext,
        *,
        collection_snapshot_id: int | None = None,
    ) -> RecordedIntelligenceExecution:
        """Run modules in registry order and record only complete results."""

        return self._execute_and_record(
            context,
            executed_at=self._clock(),
            collection_snapshot_id=collection_snapshot_id,
            marketplace_snapshot_id=None,
            allow_skipped=False,
        )

    def execute_collector_run(
        self,
        *,
        analysis_run_id: int,
        marketplace_snapshot: MarketplaceSnapshot,
        release_ids: tuple[int, ...],
        executed_at: datetime,
    ) -> RecordedIntelligenceExecution:
        """Execute and record one explicit canonical Collector Run context."""

        if self._context_factory is None:
            raise RuntimeError(
                "Collector Run Intelligence context construction is unavailable."
            )
        if type(executed_at) is not datetime:
            raise TypeError("executed_at must be a datetime.")
        if executed_at.tzinfo is None or executed_at.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware.")
        if type(marketplace_snapshot) is not MarketplaceSnapshot:
            raise TypeError("marketplace_snapshot must be a MarketplaceSnapshot.")
        if executed_at.isoformat() != marketplace_snapshot.captured_at.isoformat():
            raise ValueError(
                "executed_at must exactly match marketplace_snapshot.captured_at."
            )
        context = self._context_factory.build_collector_run(
            analysis_run_id=analysis_run_id,
            marketplace_snapshot=marketplace_snapshot,
            release_ids=release_ids,
            captured_at=executed_at,
        )
        return self._execute_and_record(
            context,
            executed_at=executed_at,
            collection_snapshot_id=None,
            marketplace_snapshot_id=marketplace_snapshot.snapshot_id,
            allow_skipped=True,
        )

    def _execute_and_record(
        self,
        context: IntelligenceContext,
        *,
        executed_at: datetime,
        collection_snapshot_id: int | None,
        marketplace_snapshot_id: str | None,
        allow_skipped: bool,
    ) -> RecordedIntelligenceExecution:
        execution = self._engine.execute(context)
        statuses = tuple(
            self._status(result)
            for result in execution.results
        )

        accepted = (
            {IntelligenceStatus.COMPLETED, IntelligenceStatus.SKIPPED}
            if allow_skipped
            else {IntelligenceStatus.COMPLETED}
        )
        if any(status not in accepted for status in statuses):
            raise IntelligenceExecutionIncompleteError(execution)

        records = tuple(
            self._history_record(result, status)
            for result, status in zip(
                execution.results,
                statuses,
                strict=True,
            )
        )
        run = IntelligenceHistoryRun(
            run_id=None,
            executed_at=executed_at,
            engine_version=self._engine_version,
            collection_snapshot_id=collection_snapshot_id,
            result_count=len(records),
            marketplace_snapshot_id=marketplace_snapshot_id,
        )
        persisted_run = self._history_repository.save_execution(run, records)
        return RecordedIntelligenceExecution(
            execution=execution,
            history_run=persisted_run,
        )

    @staticmethod
    def _status(result: IntelligenceResult) -> IntelligenceStatus:
        if type(result.status) is IntelligenceStatus:
            return result.status
        return IntelligenceStatus(result.status)

    @staticmethod
    def _history_record(
        result: IntelligenceResult,
        status: IntelligenceStatus,
    ) -> IntelligenceHistoryRecord:
        return IntelligenceHistoryRecord(
            record_id=None,
            run_id=None,
            module_id=result.module_id,
            module_version=result.module_version,
            status=status,
            summary=result.summary,
            insights=result.insights,
            metrics=result.metrics,
            evidence=result.evidence,
            diagnostics=result.diagnostics,
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
