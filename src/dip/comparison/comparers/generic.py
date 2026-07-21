"""Generic structural comparison for one Intelligence module."""

from __future__ import annotations

from dip.intelligence_history import IntelligenceHistoryRecord

from ..models import ComparisonResult, ModuleComparison, ValueChange


class GenericModuleComparer:
    """Compare stored fields without interpreting their domain meaning."""

    def __init__(self, module_id: str) -> None:
        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError("Generic comparers require a non-empty module_id.")
        if module_id != module_id.strip():
            raise ValueError("module_id must not contain surrounding whitespace.")
        self.module_id = module_id

    def compare(
        self,
        previous: IntelligenceHistoryRecord | None,
        current: IntelligenceHistoryRecord | None,
    ) -> ModuleComparison:
        """Return field-level equality without scores, deltas, or narrative."""

        self._validate_record(previous, "previous")
        self._validate_record(current, "current")
        if previous is None and current is None:
            raise ValueError("A generic comparison requires at least one record.")

        status = ValueChange(
            previous=None if previous is None else previous.status,
            current=None if current is None else current.status,
        )
        summary = ValueChange(
            previous=None if previous is None else previous.summary,
            current=None if current is None else current.summary,
        )
        metrics = ValueChange(
            previous=None if previous is None else previous.metrics,
            current=None if current is None else current.metrics,
        )
        evidence = ValueChange(
            previous=None if previous is None else previous.evidence,
            current=None if current is None else current.evidence,
        )
        diagnostics = ValueChange(
            previous=None if previous is None else previous.diagnostics,
            current=None if current is None else current.diagnostics,
        )

        return ModuleComparison(
            module_id=self.module_id,
            previous_record=previous,
            current_record=current,
            status=status,
            summary=summary,
            metrics=metrics,
            evidence=evidence,
            diagnostics=diagnostics,
            result=self._result(
                previous,
                current,
                (status, summary, metrics, evidence, diagnostics),
            ),
        )

    def _validate_record(
        self,
        record: IntelligenceHistoryRecord | None,
        name: str,
    ) -> None:
        if record is None:
            return
        if type(record) is not IntelligenceHistoryRecord:
            raise TypeError(f"{name} must be an IntelligenceHistoryRecord or None.")
        if record.module_id != self.module_id:
            raise ValueError(f"{name} record does not match the comparer module_id.")

    @staticmethod
    def _result(
        previous: IntelligenceHistoryRecord | None,
        current: IntelligenceHistoryRecord | None,
        changes: tuple[ValueChange, ...],
    ) -> ComparisonResult:
        if previous is None:
            return ComparisonResult.ADDED
        if current is None:
            return ComparisonResult.REMOVED
        if any(change.changed for change in changes):
            return ComparisonResult.CHANGED
        return ComparisonResult.UNCHANGED
