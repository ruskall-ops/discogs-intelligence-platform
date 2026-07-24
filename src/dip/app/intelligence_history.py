"""Read-only application queries for complete historical intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRepository,
    IntelligenceHistoryRun,
)


class IntelligenceHistoryConsistencyError(RuntimeError):
    """Raised when persisted history cannot form a complete observation."""


@dataclass(frozen=True)
class HistoricalIntelligenceExecution:
    """One persisted run together with all of its ordered module records."""

    run: IntelligenceHistoryRun
    records: tuple[IntelligenceHistoryRecord, ...]

    def __post_init__(self) -> None:
        _validate_persisted_run(self.run)
        try:
            records = tuple(self.records)
        except TypeError as exc:
            raise TypeError("records must be a collection of history records.") from exc

        module_ids: set[str] = set()
        for record in records:
            _validate_persisted_record(record)
            if record.run_id != self.run.run_id:
                raise ValueError("Every record must belong to the execution run.")
            if record.module_id in module_ids:
                raise ValueError(
                    "Module IDs must be unique within a historical execution."
                )
            module_ids.add(record.module_id)

        if self.run.result_count != len(records):
            raise ValueError(
                "run.result_count must match the number of execution records."
            )

        object.__setattr__(self, "records", records)


@dataclass(frozen=True)
class HistoricalModuleResult:
    """One module record together with the persisted run that produced it."""

    run: IntelligenceHistoryRun
    record: IntelligenceHistoryRecord

    def __post_init__(self) -> None:
        _validate_persisted_run(self.run)
        _validate_persisted_record(self.record)
        if self.record.run_id != self.run.run_id:
            raise ValueError("The module record must belong to the supplied run.")


class IntelligenceHistoryQueryService:
    """Assemble validated Intelligence History through its repository boundary."""

    def __init__(self, repository: IntelligenceHistoryRepository) -> None:
        self._repository = repository

    def latest_execution(self) -> HistoricalIntelligenceExecution | None:
        """Return the newest complete execution, if history exists."""

        run = self._repository.latest_run()
        return None if run is None else self._execution_for_run(run)

    def previous_execution(self) -> HistoricalIntelligenceExecution | None:
        """Return the execution immediately before the newest execution."""

        run = self._repository.previous_run()
        return None if run is None else self._execution_for_run(run)

    def execution(
        self,
        run_id: int,
    ) -> HistoricalIntelligenceExecution | None:
        """Return one complete execution by its persisted run identifier."""

        _validate_positive_integer(run_id, "run_id")
        run = self._repository.run_by_id(run_id)
        if run is None:
            return None
        if run.run_id != run_id:
            raise IntelligenceHistoryConsistencyError(
                f"Repository returned run {run.run_id!r} for requested run {run_id}."
            )
        return self._execution_for_run(run)

    def recent_executions(
        self,
        limit: int,
    ) -> tuple[HistoricalIntelligenceExecution, ...]:
        """Return up to limit complete executions in newest-first order."""

        _validate_positive_integer(limit, "limit")
        return tuple(
            self._execution_for_run(run)
            for run in self._repository.recent_runs(limit)
        )

    def module_history(
        self,
        module_id: str,
        limit: int | None = None,
    ) -> tuple[HistoricalModuleResult, ...]:
        """Return one module's history in deterministic newest-first order."""

        _validate_module_id(module_id)
        if limit is not None:
            _validate_positive_integer(limit, "limit")

        chronological = tuple(self._repository.history_for_module(module_id))
        selected = chronological if limit is None else chronological[-limit:]
        return tuple(
            self._module_result(record, expected_module_id=module_id)
            for record in reversed(selected)
        )

    def latest_module_result(
        self,
        module_id: str,
    ) -> HistoricalModuleResult | None:
        """Return the newest result for one module, if it exists."""

        _validate_module_id(module_id)
        record = self._repository.latest_result(module_id)
        if record is None:
            return None
        return self._module_result(record, expected_module_id=module_id)

    def previous_module_result(
        self,
        module_id: str,
    ) -> HistoricalModuleResult | None:
        """Return the result immediately before a module's newest result."""

        _validate_module_id(module_id)
        record = self._repository.previous_result(module_id)
        if record is None:
            return None
        return self._module_result(record, expected_module_id=module_id)

    def _execution_for_run(
        self,
        run: IntelligenceHistoryRun,
    ) -> HistoricalIntelligenceExecution:
        run_id = _persisted_run_id(run)
        records = self._repository.records_for_run(run_id)
        try:
            return HistoricalIntelligenceExecution(run=run, records=records)
        except (TypeError, ValueError) as exc:
            raise IntelligenceHistoryConsistencyError(
                f"Stored Intelligence History execution {run_id} is inconsistent: "
                f"{exc}"
            ) from exc

    def _module_result(
        self,
        record: IntelligenceHistoryRecord,
        *,
        expected_module_id: str,
    ) -> HistoricalModuleResult:
        try:
            _validate_persisted_record(record)
        except (TypeError, ValueError) as exc:
            raise IntelligenceHistoryConsistencyError(
                f"Stored module history for {expected_module_id!r} is "
                f"inconsistent: {exc}"
            ) from exc

        if record.module_id != expected_module_id:
            raise IntelligenceHistoryConsistencyError(
                f"Repository returned module {record.module_id!r} for requested "
                f"module {expected_module_id!r}."
            )

        run_id = record.run_id
        if type(run_id) is not int:
            raise IntelligenceHistoryConsistencyError(
                f"Stored module result {record.record_id!r} has no persisted run."
            )
        run = self._repository.run_by_id(run_id)
        if run is None:
            raise IntelligenceHistoryConsistencyError(
                f"Stored module result {record.record_id!r} references missing "
                f"run {run_id}."
            )

        try:
            return HistoricalModuleResult(run=run, record=record)
        except (TypeError, ValueError) as exc:
            raise IntelligenceHistoryConsistencyError(
                f"Stored module result {record.record_id!r} is inconsistent: {exc}"
            ) from exc


def _persisted_run_id(run: Any) -> int:
    try:
        _validate_persisted_run(run)
    except (TypeError, ValueError) as exc:
        raise IntelligenceHistoryConsistencyError(
            f"Stored Intelligence History run is inconsistent: {exc}"
        ) from exc
    return run.run_id


def _validate_persisted_run(run: Any) -> None:
    if type(run) is not IntelligenceHistoryRun:
        raise TypeError("run must be an IntelligenceHistoryRun.")
    _validate_positive_integer(run.run_id, "run.run_id")


def _validate_persisted_record(record: Any) -> None:
    if type(record) is not IntelligenceHistoryRecord:
        raise TypeError("records must contain only IntelligenceHistoryRecord values.")
    _validate_positive_integer(record.record_id, "record.record_id")
    _validate_positive_integer(record.run_id, "record.run_id")
    _validate_module_id(record.module_id)


def _validate_positive_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _validate_module_id(module_id: Any) -> None:
    if not isinstance(module_id, str):
        raise TypeError("module_id must be a string.")
    if not module_id or not module_id.strip():
        raise ValueError("module_id must be non-empty.")
    if module_id != module_id.strip():
        raise ValueError("module_id must not contain surrounding whitespace.")


__all__ = [
    "HistoricalIntelligenceExecution",
    "HistoricalModuleResult",
    "IntelligenceHistoryConsistencyError",
    "IntelligenceHistoryQueryService",
]
