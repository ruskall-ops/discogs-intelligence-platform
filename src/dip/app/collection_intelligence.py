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


class _IntelligenceEngine(Protocol):
    def execute(self, context: IntelligenceContext) -> IntelligenceExecution: ...


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
        *,
        engine_version: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._engine = engine
        self._history_repository = history_repository
        self._engine_version = engine_version
        self._clock = clock or _utc_now

    def execute(
        self,
        context: IntelligenceContext,
        *,
        collection_snapshot_id: int | None = None,
    ) -> RecordedIntelligenceExecution:
        """Run modules in registry order and record only complete results."""

        execution = self._engine.execute(context)
        statuses = tuple(
            self._status(result)
            for result in execution.results
        )

        if any(status is not IntelligenceStatus.COMPLETED for status in statuses):
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
            executed_at=self._clock(),
            engine_version=self._engine_version,
            collection_snapshot_id=collection_snapshot_id,
            result_count=len(records),
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
