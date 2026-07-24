"""Build the Dashboard homepage from existing presentation boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from dip.experience.comparison import (
    ExecutionComparisonViewModel,
    ModuleComparisonState,
)
from dip.intelligence import IntelligenceResult, IntelligenceStatus
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)

from .homepage_models import (
    DashboardChangeSummaryViewModel,
    DashboardChangedModuleViewModel,
    DashboardCollectionHealthViewModel,
    DashboardCollectionOverviewViewModel,
    DashboardExecutionViewModel,
    DashboardHiddenGemsViewModel,
    DashboardHomepageConsistencyError,
    DashboardHomepageViewModel,
    DashboardSectionState,
)
from .models import DashboardCardState
from .presenter import CollectionHealthCardPresenter, HiddenGemsCardPresenter


class DashboardHomepageViewModelBuilder:
    """Assemble presentation-ready homepage sections without calculating intelligence."""

    def __init__(
        self,
        collection_health: CollectionHealthCardPresenter | None = None,
        hidden_gems: HiddenGemsCardPresenter | None = None,
        *,
        hidden_gems_preview_limit: int = 3,
    ) -> None:
        if type(hidden_gems_preview_limit) is not int:
            raise TypeError("hidden_gems_preview_limit must be an integer.")
        if hidden_gems_preview_limit <= 0:
            raise ValueError("hidden_gems_preview_limit must be positive.")
        self._collection_health = collection_health or CollectionHealthCardPresenter()
        self._hidden_gems = hidden_gems or HiddenGemsCardPresenter()
        self._hidden_gems_preview_limit = hidden_gems_preview_limit

    def build(
        self,
        latest_execution: Any,
        comparison: ExecutionComparisonViewModel | None = None,
        *,
        comparison_state: DashboardSectionState = (
            DashboardSectionState.INSUFFICIENT_HISTORY
        ),
    ) -> DashboardHomepageViewModel:
        """Build the five ordered sections from latest history and comparison data."""

        if latest_execution is None:
            if comparison is not None:
                raise DashboardHomepageConsistencyError(
                    "A comparison cannot exist when Intelligence History is empty."
                )
            return self._empty_homepage(comparison_state)

        run, records = self._validate_execution(latest_execution)
        by_module = {record.module_id: record for record in records}
        health_record = by_module.get(self._collection_health.module_id)
        hidden_gems_record = by_module.get(self._hidden_gems.module_id)

        health_card = (
            self._collection_health.unavailable()
            if health_record is None
            else self._collection_health.present(self._result(health_record))
        )
        hidden_gems_card = (
            self._hidden_gems.unavailable()
            if hidden_gems_record is None
            else self._hidden_gems.present(self._result(hidden_gems_record))
        )
        hidden_gems_state = self._hidden_gems_state(hidden_gems_card)
        preview = (
            hidden_gems_card.ranked_gems[: self._hidden_gems_preview_limit]
            if hidden_gems_state is DashboardSectionState.AVAILABLE
            else ()
        )

        return DashboardHomepageViewModel(
            sections=(
                self._overview(run, records, health_record, hidden_gems_record),
                DashboardCollectionHealthViewModel(
                    state=self._section_state(health_card.state),
                    card=health_card,
                ),
                DashboardHiddenGemsViewModel(
                    state=hidden_gems_state,
                    card=hidden_gems_card,
                    preview=preview,
                    preview_limit=self._hidden_gems_preview_limit,
                ),
                self._changes(run, comparison, comparison_state),
                self._execution(run, records),
            )
        )

    def _empty_homepage(
        self,
        comparison_state: DashboardSectionState,
    ) -> DashboardHomepageViewModel:
        self._validate_absent_comparison_state(comparison_state)
        return DashboardHomepageViewModel(
            sections=(
                DashboardCollectionOverviewViewModel(
                    state=DashboardSectionState.EMPTY,
                    summary=(
                        "No completed intelligence execution is available yet."
                    ),
                ),
                DashboardCollectionHealthViewModel(
                    state=DashboardSectionState.UNAVAILABLE,
                    card=self._collection_health.unavailable(),
                ),
                DashboardHiddenGemsViewModel(
                    state=DashboardSectionState.UNAVAILABLE,
                    card=self._hidden_gems.unavailable(),
                    preview_limit=self._hidden_gems_preview_limit,
                ),
                self._unavailable_changes(comparison_state),
                DashboardExecutionViewModel(
                    state=DashboardSectionState.EMPTY,
                    summary="No completed intelligence execution is available yet.",
                ),
            )
        )

    def _overview(
        self,
        run: IntelligenceHistoryRun,
        records: tuple[IntelligenceHistoryRecord, ...],
        health_record: IntelligenceHistoryRecord | None,
        hidden_gems_record: IntelligenceHistoryRecord | None,
    ) -> DashboardCollectionOverviewViewModel:
        completed_count = sum(
            record.status is IntelligenceStatus.COMPLETED for record in records
        )
        status = self._execution_status(records)
        collection_size = self._collection_size(health_record, hidden_gems_record)
        return DashboardCollectionOverviewViewModel(
            state=DashboardSectionState.AVAILABLE,
            summary=(
                f"{completed_count} of {len(records)} intelligence modules completed."
            ),
            collection_size=collection_size,
            latest_executed_at=run.executed_at,
            current_status=status,
            completed_module_count=completed_count,
            total_module_count=len(records),
        )

    @staticmethod
    def _changes(
        run: IntelligenceHistoryRun,
        comparison: ExecutionComparisonViewModel | None,
        comparison_state: DashboardSectionState,
    ) -> DashboardChangeSummaryViewModel:
        if comparison is None:
            return DashboardHomepageViewModelBuilder._unavailable_changes(
                comparison_state
            )
        if comparison.current_run_id != run.run_id:
            raise DashboardHomepageConsistencyError(
                "The latest comparison does not describe the latest execution."
            )
        modules = tuple(
            DashboardChangedModuleViewModel(
                module_id=module.module_id,
                label=module.label,
                state=module.state,
            )
            for module in comparison.modules
            if module.state is not ModuleComparisonState.UNCHANGED
        )
        summary = (
            "The latest execution differs from the previous execution."
            if comparison.has_changes
            else "The latest execution matches the previous execution."
        )
        return DashboardChangeSummaryViewModel(
            state=DashboardSectionState.AVAILABLE,
            summary=summary,
            has_changes=comparison.has_changes,
            total_module_count=comparison.total_module_count,
            changed_module_count=comparison.changed_module_count,
            unchanged_module_count=comparison.unchanged_module_count,
            added_module_count=comparison.added_module_count,
            removed_module_count=comparison.removed_module_count,
            changed_modules=modules,
        )

    @staticmethod
    def _unavailable_changes(
        state: DashboardSectionState,
    ) -> DashboardChangeSummaryViewModel:
        DashboardHomepageViewModelBuilder._validate_absent_comparison_state(state)
        summaries = {
            DashboardSectionState.INSUFFICIENT_HISTORY: (
                "At least two completed executions are needed to show changes."
            ),
            DashboardSectionState.UNAVAILABLE: (
                "Comparison data is currently unavailable."
            ),
            DashboardSectionState.ERROR: (
                "The latest comparison could not be displayed."
            ),
        }
        return DashboardChangeSummaryViewModel(
            state=state,
            summary=summaries[state],
        )

    @staticmethod
    def _execution(
        run: IntelligenceHistoryRun,
        records: tuple[IntelligenceHistoryRecord, ...],
    ) -> DashboardExecutionViewModel:
        return DashboardExecutionViewModel(
            state=DashboardSectionState.AVAILABLE,
            summary="Latest completed Intelligence History execution.",
            run_id=run.run_id,
            executed_at=run.executed_at,
            module_count=len(records),
            engine_version=run.engine_version,
            successful=all(
                record.status is not IntelligenceStatus.FAILED for record in records
            ),
        )

    @staticmethod
    def _result(record: IntelligenceHistoryRecord) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=record.module_id,
            module_version=record.module_version,
            status=record.status,
            summary=record.summary,
            insights=record.insights,
            metrics=record.metrics,
            evidence=record.evidence,
            diagnostics=record.diagnostics,
        )

    @staticmethod
    def _validate_execution(
        execution: Any,
    ) -> tuple[IntelligenceHistoryRun, tuple[IntelligenceHistoryRecord, ...]]:
        run = getattr(execution, "run", None)
        records = getattr(execution, "records", None)
        if type(run) is not IntelligenceHistoryRun:
            raise TypeError("latest_execution must provide an IntelligenceHistoryRun.")
        if type(run.run_id) is not int or run.run_id <= 0:
            raise DashboardHomepageConsistencyError(
                "The latest execution requires a positive persisted run ID."
            )
        if type(records) is not tuple:
            raise TypeError("latest_execution.records must be an immutable tuple.")
        if run.result_count != len(records):
            raise DashboardHomepageConsistencyError(
                "The latest execution result count is inconsistent."
            )
        module_ids: set[str] = set()
        for record in records:
            if type(record) is not IntelligenceHistoryRecord:
                raise TypeError(
                    "latest_execution.records must contain history records."
                )
            if record.run_id != run.run_id:
                raise DashboardHomepageConsistencyError(
                    "A latest execution record belongs to another run."
                )
            if record.module_id in module_ids:
                raise DashboardHomepageConsistencyError(
                    "The latest execution contains duplicate modules."
                )
            module_ids.add(record.module_id)
        return run, records

    @staticmethod
    def _section_state(state: DashboardCardState) -> DashboardSectionState:
        if type(state) is not DashboardCardState:
            raise DashboardHomepageConsistencyError(
                "A Dashboard card contains an unsupported state."
            )
        states = {
            DashboardCardState.READY: DashboardSectionState.AVAILABLE,
            DashboardCardState.SKIPPED: DashboardSectionState.EMPTY,
            DashboardCardState.FAILED: DashboardSectionState.ERROR,
            DashboardCardState.INCOMPLETE: DashboardSectionState.ERROR,
            DashboardCardState.UNAVAILABLE: DashboardSectionState.UNAVAILABLE,
            DashboardCardState.INSUFFICIENT_HISTORY: (
                DashboardSectionState.INSUFFICIENT_HISTORY
            ),
        }
        return states[state]

    @classmethod
    def _hidden_gems_state(cls, card: Any) -> DashboardSectionState:
        state = cls._section_state(card.state)
        if state is DashboardSectionState.AVAILABLE and card.total_hidden_gems == 0:
            return DashboardSectionState.EMPTY
        return state

    @staticmethod
    def _execution_status(
        records: tuple[IntelligenceHistoryRecord, ...],
    ) -> IntelligenceStatus:
        if any(record.status is IntelligenceStatus.FAILED for record in records):
            return IntelligenceStatus.FAILED
        if any(record.status is IntelligenceStatus.SKIPPED for record in records):
            return IntelligenceStatus.SKIPPED
        return IntelligenceStatus.COMPLETED

    @staticmethod
    def _collection_size(
        health_record: IntelligenceHistoryRecord | None,
        hidden_gems_record: IntelligenceHistoryRecord | None,
    ) -> int | None:
        for record in (health_record, hidden_gems_record):
            if record is None or not isinstance(record.metrics, Mapping):
                continue
            value = record.metrics.get("collection_release_count")
            if type(value) is int and value >= 0:
                return value
        return None

    @staticmethod
    def _validate_absent_comparison_state(state: Any) -> None:
        if type(state) is not DashboardSectionState:
            raise TypeError("comparison_state must be a DashboardSectionState.")
        if state not in {
            DashboardSectionState.INSUFFICIENT_HISTORY,
            DashboardSectionState.UNAVAILABLE,
            DashboardSectionState.ERROR,
        }:
            raise DashboardHomepageConsistencyError(
                "An absent comparison requires an explicit unavailable state."
            )


__all__ = ["DashboardHomepageViewModelBuilder"]
