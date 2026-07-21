"""SQLite adapter for the Intelligence History repository boundary."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol

from dip.intelligence_history.models import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)
from dip.intelligence_history.repository import IntelligenceHistoryRepository
from dip.intelligence_history.serialization import (
    IntelligenceDeserializationError,
    dumps_intelligence_value,
    loads_intelligence_value,
)


class _SQLiteDatabaseBoundary(Protocol):
    def locked_connection(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...

    def transaction(
        self,
    ) -> AbstractContextManager[sqlite3.Connection]: ...


class SQLiteIntelligenceHistoryRepository(IntelligenceHistoryRepository):
    """Append-only SQLite storage for historical intelligence executions."""

    def __init__(self, database: _SQLiteDatabaseBoundary) -> None:
        self._database = database

    def save_execution(
        self,
        run: IntelligenceHistoryRun,
        records: Sequence[IntelligenceHistoryRecord],
    ) -> IntelligenceHistoryRun:
        """Insert one execution atomically without replacing existing history."""

        if run.run_id is not None:
            raise ValueError("A new Intelligence History run must not have a run_id.")
        if run.result_count != len(records):
            raise ValueError("run.result_count must match the number of records.")
        for record in records:
            if record.record_id is not None:
                raise ValueError(
                    "A new Intelligence History record must not have a record_id."
                )
            if record.run_id is not None:
                raise ValueError(
                    "A new Intelligence History record must have run_id=None."
                )

        executed_at_json = dumps_intelligence_value(run.executed_at)
        serialized_records = tuple(
            self._serialize_record(record)
            for record in records
        )

        with self._database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO intelligence_runs (
                    executed_at,
                    executed_at_json,
                    engine_version,
                    collection_snapshot_id,
                    result_count
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self._execution_sort_value(run.executed_at),
                    executed_at_json,
                    run.engine_version,
                    run.collection_snapshot_id,
                    run.result_count,
                ),
            )
            run_id = int(cursor.lastrowid)

            for record, payloads in zip(
                records,
                serialized_records,
                strict=True,
            ):
                connection.execute(
                    """
                    INSERT INTO intelligence_results (
                        run_id,
                        module_id,
                        module_version,
                        status_json,
                        summary,
                        insights_json,
                        metrics_json,
                        evidence_json,
                        diagnostics_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        record.module_id,
                        record.module_version,
                        payloads["status_json"],
                        record.summary,
                        payloads["insights_json"],
                        payloads["metrics_json"],
                        payloads["evidence_json"],
                        payloads["diagnostics_json"],
                    ),
                )

        return replace(run, run_id=run_id)

    @staticmethod
    def _execution_sort_value(executed_at: datetime) -> str:
        """Return a stable UTC key while preserving the original JSON value."""

        if executed_at.utcoffset() is None:
            # Naive values are preserved as naive in executed_at_json. UTC is
            # used only as their deterministic repository ordering policy.
            executed_at = executed_at.replace(tzinfo=timezone.utc)
        else:
            executed_at = executed_at.astimezone(timezone.utc)
        return executed_at.isoformat(timespec="microseconds")

    def latest_run(self) -> IntelligenceHistoryRun | None:
        return self._run_at_offset(0)

    def previous_run(self) -> IntelligenceHistoryRun | None:
        return self._run_at_offset(1)

    def run_by_id(self, run_id: int) -> IntelligenceHistoryRun | None:
        with self._database.locked_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM intelligence_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()

        return None if row is None else self._run_from_row(row)

    def recent_runs(
        self,
        limit: int,
    ) -> tuple[IntelligenceHistoryRun, ...]:
        with self._database.locked_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM intelligence_runs
                ORDER BY executed_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return tuple(self._run_from_row(row) for row in rows)

    def records_for_run(
        self,
        run_id: int,
    ) -> tuple[IntelligenceHistoryRecord, ...]:
        with self._database.locked_connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM intelligence_results
                WHERE run_id = ?
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()

        return tuple(self._record_from_row(row) for row in rows)

    def latest_result(
        self,
        module_id: str,
    ) -> IntelligenceHistoryRecord | None:
        return self._result_at_offset(module_id, 0)

    def previous_result(
        self,
        module_id: str,
    ) -> IntelligenceHistoryRecord | None:
        return self._result_at_offset(module_id, 1)

    def history_for_module(
        self,
        module_id: str,
    ) -> tuple[IntelligenceHistoryRecord, ...]:
        with self._database.locked_connection() as connection:
            rows = connection.execute(
                """
                SELECT ir.*
                FROM intelligence_results ir
                JOIN intelligence_runs run ON run.id = ir.run_id
                WHERE ir.module_id = ?
                ORDER BY run.executed_at ASC, run.id ASC, ir.id ASC
                """,
                (module_id,),
            ).fetchall()

        return tuple(self._record_from_row(row) for row in rows)

    def _run_at_offset(
        self,
        offset: int,
    ) -> IntelligenceHistoryRun | None:
        with self._database.locked_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM intelligence_runs
                ORDER BY executed_at DESC, id DESC
                LIMIT 1 OFFSET ?
                """,
                (offset,),
            ).fetchone()

        return None if row is None else self._run_from_row(row)

    def _result_at_offset(
        self,
        module_id: str,
        offset: int,
    ) -> IntelligenceHistoryRecord | None:
        with self._database.locked_connection() as connection:
            row = connection.execute(
                """
                SELECT ir.*
                FROM intelligence_results ir
                JOIN intelligence_runs run ON run.id = ir.run_id
                WHERE ir.module_id = ?
                ORDER BY run.executed_at DESC, run.id DESC, ir.id DESC
                LIMIT 1 OFFSET ?
                """,
                (module_id, offset),
            ).fetchone()

        return None if row is None else self._record_from_row(row)

    @staticmethod
    def _serialize_record(
        record: IntelligenceHistoryRecord,
    ) -> dict[str, str]:
        return {
            "status_json": dumps_intelligence_value(record.status),
            "insights_json": dumps_intelligence_value(record.insights),
            "metrics_json": dumps_intelligence_value(record.metrics),
            "evidence_json": dumps_intelligence_value(record.evidence),
            "diagnostics_json": dumps_intelligence_value(record.diagnostics),
        }

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> IntelligenceHistoryRun:
        executed_at = loads_intelligence_value(row["executed_at_json"])
        try:
            return IntelligenceHistoryRun(
                run_id=row["id"],
                executed_at=executed_at,
                engine_version=row["engine_version"],
                collection_snapshot_id=row["collection_snapshot_id"],
                result_count=row["result_count"],
            )
        except (TypeError, ValueError) as exc:
            raise IntelligenceDeserializationError(
                f"Stored IntelligenceHistoryRun {row['id']} is invalid: {exc}"
            ) from exc

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> IntelligenceHistoryRecord:
        try:
            return IntelligenceHistoryRecord(
                record_id=row["id"],
                run_id=row["run_id"],
                module_id=row["module_id"],
                module_version=row["module_version"],
                status=loads_intelligence_value(row["status_json"]),
                summary=row["summary"],
                insights=loads_intelligence_value(row["insights_json"]),
                metrics=loads_intelligence_value(row["metrics_json"]),
                evidence=loads_intelligence_value(row["evidence_json"]),
                diagnostics=loads_intelligence_value(row["diagnostics_json"]),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, IntelligenceDeserializationError):
                raise
            raise IntelligenceDeserializationError(
                f"Stored IntelligenceHistoryRecord {row['id']} is invalid: {exc}"
            ) from exc
