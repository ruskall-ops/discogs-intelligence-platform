"""Deterministic coordination of registered Intelligence module comparers."""

from __future__ import annotations

from typing import Any, Protocol

from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)

from .defaults import build_default_comparison_registry
from .models import ExecutionComparison, ModuleComparison
from .registry import ComparisonRegistry


class _HistoricalExecution(Protocol):
    run: IntelligenceHistoryRun
    records: tuple[IntelligenceHistoryRecord, ...]


class ComparisonEngine:
    """Align historical modules and dispatch comparisons without interpretation."""

    def __init__(self, registry: ComparisonRegistry | None = None) -> None:
        self.registry = (
            registry
            if registry is not None
            else build_default_comparison_registry()
        )

    def compare(
        self,
        current: _HistoricalExecution,
        previous: _HistoricalExecution,
    ) -> ExecutionComparison:
        """Compare two distinct complete executions in deterministic order."""

        current_run, current_records = self._validate_execution(
            current,
            "current",
        )
        previous_run, previous_records = self._validate_execution(
            previous,
            "previous",
        )
        if current_run.run_id == previous_run.run_id:
            raise ValueError("Cannot compare an Intelligence History run with itself.")

        current_by_module = {
            record.module_id: record
            for record in current_records
        }
        previous_by_module = {
            record.module_id: record
            for record in previous_records
        }
        module_ids = tuple(current_by_module) + tuple(
            module_id
            for module_id in previous_by_module
            if module_id not in current_by_module
        )
        modules = tuple(
            self._compare_module(
                module_id,
                previous_by_module.get(module_id),
                current_by_module.get(module_id),
            )
            for module_id in module_ids
        )

        return ExecutionComparison(
            previous_run=previous_run,
            current_run=current_run,
            modules=modules,
        )

    def _compare_module(
        self,
        module_id: str,
        previous: IntelligenceHistoryRecord | None,
        current: IntelligenceHistoryRecord | None,
    ) -> ModuleComparison:
        comparison = self.registry.get(module_id).compare(previous, current)
        if type(comparison) is not ModuleComparison:
            raise TypeError("Module comparers must return a ModuleComparison.")
        if comparison.module_id != module_id:
            raise ValueError(
                "A module comparison must match its registered module_id."
            )
        return comparison

    @staticmethod
    def _validate_execution(
        execution: Any,
        name: str,
    ) -> tuple[
        IntelligenceHistoryRun,
        tuple[IntelligenceHistoryRecord, ...],
    ]:
        run = getattr(execution, "run", None)
        records = getattr(execution, "records", None)
        if type(run) is not IntelligenceHistoryRun:
            raise TypeError(f"{name} must provide an IntelligenceHistoryRun.")
        if type(run.run_id) is not int or run.run_id <= 0:
            raise ValueError(f"{name}.run.run_id must be a positive integer.")
        if type(records) is not tuple:
            raise TypeError(f"{name}.records must be an immutable tuple.")
        if run.result_count != len(records):
            raise ValueError(
                f"{name}.run.result_count must match its number of records."
            )

        module_ids: set[str] = set()
        for record in records:
            if type(record) is not IntelligenceHistoryRecord:
                raise TypeError(
                    f"{name}.records must contain IntelligenceHistoryRecord values."
                )
            if type(record.record_id) is not int or record.record_id <= 0:
                raise ValueError(
                    f"{name} records require positive persisted record IDs."
                )
            if record.run_id != run.run_id:
                raise ValueError(f"A {name} record belongs to the wrong run.")
            if not record.module_id or record.module_id != record.module_id.strip():
                raise ValueError(f"A {name} record has an invalid module_id.")
            if record.module_id in module_ids:
                raise ValueError(f"The {name} execution has duplicate module IDs.")
            module_ids.add(record.module_id)

        return run, records
