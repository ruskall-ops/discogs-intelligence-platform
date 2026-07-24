"""Immutable, presentation-independent Intelligence comparison models."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
    dumps_intelligence_value,
)


class ComparisonResult(str, Enum):
    """Structural outcome for one compared module."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    ADDED = "added"
    REMOVED = "removed"


@dataclass(frozen=True)
class ValueChange:
    """Previous and current values with their deterministic equality result."""

    previous: Any
    current: Any
    changed: bool = field(init=False)

    def __post_init__(self) -> None:
        previous_payload = dumps_intelligence_value(self.previous)
        current_payload = dumps_intelligence_value(self.current)
        previous = _freeze_comparison_value(self.previous)
        current = _freeze_comparison_value(self.current)
        object.__setattr__(self, "previous", previous)
        object.__setattr__(self, "current", current)
        object.__setattr__(
            self,
            "changed",
            previous_payload != current_payload,
        )


@dataclass(frozen=True)
class ModuleComparison:
    """Generic structural changes for one module across two executions."""

    module_id: str
    previous_record: IntelligenceHistoryRecord | None
    current_record: IntelligenceHistoryRecord | None
    status: ValueChange
    summary: ValueChange
    metrics: ValueChange
    evidence: ValueChange
    diagnostics: ValueChange
    result: ComparisonResult

    def __post_init__(self) -> None:
        _validate_module_id(self.module_id)
        if self.previous_record is None and self.current_record is None:
            raise ValueError("A module comparison requires at least one record.")

        for name, record in (
            ("previous_record", self.previous_record),
            ("current_record", self.current_record),
        ):
            if record is None:
                continue
            if type(record) is not IntelligenceHistoryRecord:
                raise TypeError(
                    f"{name} must be an IntelligenceHistoryRecord or None."
                )
            if record.module_id != self.module_id:
                raise ValueError(f"{name} must match module_id.")

        changes = (
            self.status,
            self.summary,
            self.metrics,
            self.evidence,
            self.diagnostics,
        )
        if any(type(change) is not ValueChange for change in changes):
            raise TypeError("Module comparison fields must be ValueChange values.")
        if type(self.result) is not ComparisonResult:
            raise TypeError("result must be a ComparisonResult.")

        expected = self._expected_result(changes)
        if self.result is not expected:
            raise ValueError(
                f"result must be {expected.value!r} for the supplied records "
                "and changes."
            )

    def _expected_result(
        self,
        changes: tuple[ValueChange, ...],
    ) -> ComparisonResult:
        if self.previous_record is None:
            return ComparisonResult.ADDED
        if self.current_record is None:
            return ComparisonResult.REMOVED
        if any(change.changed for change in changes):
            return ComparisonResult.CHANGED
        return ComparisonResult.UNCHANGED


@dataclass(frozen=True)
class ExecutionComparison:
    """Deterministic module comparisons between two persisted runs."""

    previous_run: IntelligenceHistoryRun
    current_run: IntelligenceHistoryRun
    modules: tuple[ModuleComparison, ...]

    def __post_init__(self) -> None:
        _validate_persisted_run(self.previous_run, "previous_run")
        _validate_persisted_run(self.current_run, "current_run")
        if self.previous_run.run_id == self.current_run.run_id:
            raise ValueError("Cannot compare an Intelligence History run with itself.")

        try:
            modules = tuple(self.modules)
        except TypeError as exc:
            raise TypeError(
                "modules must be a collection of ModuleComparison values."
            ) from exc

        seen: set[str] = set()
        for module in modules:
            if type(module) is not ModuleComparison:
                raise TypeError("modules must contain only ModuleComparison values.")
            if module.module_id in seen:
                raise ValueError("Execution comparisons require unique module IDs.")
            seen.add(module.module_id)
            if (
                module.previous_record is not None
                and module.previous_record.run_id != self.previous_run.run_id
            ):
                raise ValueError("A previous record belongs to the wrong run.")
            if (
                module.current_record is not None
                and module.current_record.run_id != self.current_run.run_id
            ):
                raise ValueError("A current record belongs to the wrong run.")

        object.__setattr__(self, "modules", modules)

    @property
    def changed(self) -> bool:
        """Return whether any module was changed, added, or removed."""

        return any(
            module.result is not ComparisonResult.UNCHANGED
            for module in self.modules
        )


def _freeze_comparison_value(value: Any) -> Any:
    return _freeze_validated_value(value)


def _freeze_validated_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                key: _freeze_validated_value(value[key])
                for key in sorted(value)
            }
        )
    if isinstance(value, list):
        return tuple(_freeze_validated_value(item) for item in value)
    if type(value) is tuple:
        return tuple(_freeze_validated_value(item) for item in value)
    if isinstance(value, tuple):
        # Intelligence History uses an immutable tuple subclass to preserve
        # serialized list semantics. It is already recursively frozen.
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return type(value)(
            **{
                item.name: _freeze_validated_value(getattr(value, item.name))
                for item in fields(value)
            }
        )
    return value


def _validate_persisted_run(run: Any, name: str) -> None:
    if type(run) is not IntelligenceHistoryRun:
        raise TypeError(f"{name} must be an IntelligenceHistoryRun.")
    if type(run.run_id) is not int or run.run_id <= 0:
        raise ValueError(f"{name}.run_id must be a positive integer.")


def _validate_module_id(module_id: Any) -> None:
    if not isinstance(module_id, str):
        raise TypeError("module_id must be a string.")
    if not module_id or not module_id.strip():
        raise ValueError("module_id must be non-empty.")
    if module_id != module_id.strip():
        raise ValueError("module_id must not contain surrounding whitespace.")
