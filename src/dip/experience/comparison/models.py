"""Immutable, presentation-neutral view models for execution comparisons."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Mapping


class ComparisonViewModelConsistencyError(ValueError):
    """Raised when comparison presentation data is internally inconsistent."""


class ComparisonValueAvailability(str, Enum):
    """Whether one side of a field comparison has a value."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ModuleComparisonState(str, Enum):
    """Presentation classification for one compared module."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class FieldChangeViewModel:
    """One generic field change with explicit per-side availability."""

    field_id: str
    label: str
    previous_value: Any
    current_value: Any
    previous_availability: ComparisonValueAvailability
    current_availability: ComparisonValueAvailability
    changed: bool

    def __post_init__(self) -> None:
        _validate_identifier(self.field_id, "field_id")
        _validate_label(self.label, "field label")
        if type(self.previous_availability) is not ComparisonValueAvailability:
            raise TypeError(
                "previous_availability must be a ComparisonValueAvailability."
            )
        if type(self.current_availability) is not ComparisonValueAvailability:
            raise TypeError(
                "current_availability must be a ComparisonValueAvailability."
            )
        if type(self.changed) is not bool:
            raise TypeError("changed must be a boolean.")
        if (
            self.previous_availability is ComparisonValueAvailability.UNAVAILABLE
            and self.previous_value is not None
        ):
            raise ComparisonViewModelConsistencyError(
                "An unavailable previous field value must be None."
            )
        if (
            self.current_availability is ComparisonValueAvailability.UNAVAILABLE
            and self.current_value is not None
        ):
            raise ComparisonViewModelConsistencyError(
                "An unavailable current field value must be None."
            )
        if (
            self.previous_availability is ComparisonValueAvailability.UNAVAILABLE
            and self.current_availability
            is ComparisonValueAvailability.UNAVAILABLE
        ):
            raise ComparisonViewModelConsistencyError(
                "A field cannot be unavailable in both executions."
            )
        if (
            self.previous_availability is not self.current_availability
            and not self.changed
        ):
            raise ComparisonViewModelConsistencyError(
                "A field with different availability must be marked changed."
            )

        if self.previous_availability is ComparisonValueAvailability.AVAILABLE:
            object.__setattr__(
                self,
                "previous_value",
                _freeze_value(self.previous_value),
            )
        if self.current_availability is ComparisonValueAvailability.AVAILABLE:
            object.__setattr__(
                self,
                "current_value",
                _freeze_value(self.current_value),
            )


@dataclass(frozen=True)
class ModuleComparisonViewModel:
    """Presentation summary and ordered fields for one compared module."""

    module_id: str
    label: str
    state: ModuleComparisonState
    has_changes: bool
    fields: tuple[FieldChangeViewModel, ...]
    changed_field_count: int
    unchanged_field_count: int
    previous_module_version: str | None = None
    current_module_version: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier(self.module_id, "module_id")
        _validate_label(self.label, "module label")
        if type(self.state) is not ModuleComparisonState:
            raise TypeError("state must be a ModuleComparisonState.")
        if type(self.has_changes) is not bool:
            raise TypeError("has_changes must be a boolean.")
        _validate_optional_string(
            self.previous_module_version,
            "previous_module_version",
        )
        _validate_optional_string(
            self.current_module_version,
            "current_module_version",
        )

        fields_value = _freeze_fields(self.fields)
        if not fields_value:
            raise ComparisonViewModelConsistencyError(
                "A module comparison requires at least one field."
            )
        field_ids = tuple(field.field_id for field in fields_value)
        if len(set(field_ids)) != len(field_ids):
            raise ComparisonViewModelConsistencyError(
                "Module comparison fields require unique field IDs."
            )

        _validate_count(self.changed_field_count, "changed_field_count")
        _validate_count(self.unchanged_field_count, "unchanged_field_count")
        actual_changed = sum(field.changed for field in fields_value)
        if self.changed_field_count != actual_changed:
            raise ComparisonViewModelConsistencyError(
                "changed_field_count does not match the contained fields."
            )
        if self.unchanged_field_count != len(fields_value) - actual_changed:
            raise ComparisonViewModelConsistencyError(
                "unchanged_field_count does not match the contained fields."
            )

        expected_has_changes = self.state is not ModuleComparisonState.UNCHANGED
        if self.has_changes != expected_has_changes:
            raise ComparisonViewModelConsistencyError(
                "has_changes does not match the module state."
            )
        if self.state is ModuleComparisonState.UNCHANGED and actual_changed:
            raise ComparisonViewModelConsistencyError(
                "An unchanged module cannot contain changed fields."
            )
        if self.state is ModuleComparisonState.CHANGED and not actual_changed:
            raise ComparisonViewModelConsistencyError(
                "A changed module must contain at least one changed field."
            )
        if (
            self.state is ModuleComparisonState.ADDED
            and self.previous_module_version is not None
        ):
            raise ComparisonViewModelConsistencyError(
                "An added module cannot have a previous module version."
            )
        if (
            self.state is ModuleComparisonState.REMOVED
            and self.current_module_version is not None
        ):
            raise ComparisonViewModelConsistencyError(
                "A removed module cannot have a current module version."
            )

        self._validate_availability(fields_value)
        object.__setattr__(self, "fields", fields_value)

    def _validate_availability(
        self,
        fields_value: tuple[FieldChangeViewModel, ...],
    ) -> None:
        for field in fields_value:
            previous = field.previous_availability
            current = field.current_availability
            if self.state is ModuleComparisonState.ADDED:
                if not (
                    previous is ComparisonValueAvailability.UNAVAILABLE
                    and current is ComparisonValueAvailability.AVAILABLE
                ):
                    raise ComparisonViewModelConsistencyError(
                        "Added module fields require unavailable previous values."
                    )
            elif self.state is ModuleComparisonState.REMOVED:
                if not (
                    previous is ComparisonValueAvailability.AVAILABLE
                    and current is ComparisonValueAvailability.UNAVAILABLE
                ):
                    raise ComparisonViewModelConsistencyError(
                        "Removed module fields require unavailable current values."
                    )
            elif not (
                previous is ComparisonValueAvailability.AVAILABLE
                and current is ComparisonValueAvailability.AVAILABLE
            ):
                raise ComparisonViewModelConsistencyError(
                    "Shared module fields must be available in both executions."
                )


@dataclass(frozen=True)
class ExecutionComparisonViewModel:
    """Presentation-ready summary of one current-versus-previous comparison."""

    current_run_id: int
    previous_run_id: int
    current_executed_at: datetime
    previous_executed_at: datetime
    has_changes: bool
    total_module_count: int
    changed_module_count: int
    unchanged_module_count: int
    added_module_count: int
    removed_module_count: int
    modules: tuple[ModuleComparisonViewModel, ...]

    def __post_init__(self) -> None:
        _validate_positive_integer(self.current_run_id, "current_run_id")
        _validate_positive_integer(self.previous_run_id, "previous_run_id")
        if self.current_run_id == self.previous_run_id:
            raise ComparisonViewModelConsistencyError(
                "Current and previous run IDs must differ."
            )
        if type(self.current_executed_at) is not datetime:
            raise TypeError("current_executed_at must be a datetime.")
        if type(self.previous_executed_at) is not datetime:
            raise TypeError("previous_executed_at must be a datetime.")
        if type(self.has_changes) is not bool:
            raise TypeError("has_changes must be a boolean.")

        modules_value = _freeze_modules(self.modules)
        module_ids = tuple(module.module_id for module in modules_value)
        if len(set(module_ids)) != len(module_ids):
            raise ComparisonViewModelConsistencyError(
                "Execution comparison modules require unique module IDs."
            )

        counts = {
            ModuleComparisonState.CHANGED: self.changed_module_count,
            ModuleComparisonState.UNCHANGED: self.unchanged_module_count,
            ModuleComparisonState.ADDED: self.added_module_count,
            ModuleComparisonState.REMOVED: self.removed_module_count,
        }
        _validate_count(self.total_module_count, "total_module_count")
        for state, count in counts.items():
            _validate_count(count, f"{state.value}_module_count")
            actual = sum(module.state is state for module in modules_value)
            if count != actual:
                raise ComparisonViewModelConsistencyError(
                    f"{state.value}_module_count does not match the modules."
                )
        if self.total_module_count != len(modules_value):
            raise ComparisonViewModelConsistencyError(
                "total_module_count does not match the modules."
            )
        if self.total_module_count != sum(counts.values()):
            raise ComparisonViewModelConsistencyError(
                "Module state counts do not sum to total_module_count."
            )

        expected_has_changes = any(module.has_changes for module in modules_value)
        if self.has_changes != expected_has_changes:
            raise ComparisonViewModelConsistencyError(
                "has_changes does not match the contained modules."
            )
        object.__setattr__(self, "modules", modules_value)


def _freeze_fields(value: Any) -> tuple[FieldChangeViewModel, ...]:
    try:
        frozen = tuple(value)
    except TypeError as exc:
        raise TypeError("fields must be a collection of field view models.") from exc
    if any(type(item) is not FieldChangeViewModel for item in frozen):
        raise TypeError("fields must contain only FieldChangeViewModel values.")
    return frozen


def _freeze_modules(value: Any) -> tuple[ModuleComparisonViewModel, ...]:
    try:
        frozen = tuple(value)
    except TypeError as exc:
        raise TypeError("modules must be a collection of module view models.") from exc
    if any(type(item) is not ModuleComparisonViewModel for item in frozen):
        raise TypeError("modules must contain only ModuleComparisonViewModel values.")
    return frozen


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key in value:
            if not isinstance(key, str):
                raise TypeError("Comparison ViewModel mapping keys must be strings.")
        for key in sorted(value):
            frozen[key] = _freeze_value(value[key])
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if type(value) is tuple:
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        parameters = getattr(type(value), "__dataclass_params__", None)
        if parameters is None or not parameters.frozen:
            raise TypeError("Comparison ViewModel dataclass values must be frozen.")
        return type(value)(
            **{
                item.name: _freeze_value(getattr(value, item.name))
                for item in fields(value)
            }
        )
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise TypeError("Comparison ViewModel decimals must be finite.")
        return value
    if value is None or isinstance(
        value,
        (bool, int, str, date, datetime, timedelta, Enum),
    ):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("Comparison ViewModel floats must be finite.")
        return value
    raise TypeError(
        f"Unsupported Comparison ViewModel value type {type(value).__name__}."
    )


def _validate_identifier(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or not value.strip():
        raise ValueError(f"{name} must be non-empty.")
    if value != value.strip():
        raise ValueError(f"{name} must not contain surrounding whitespace.")


def _validate_label(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value.strip():
        raise ValueError(f"{name} must be non-empty.")


def _validate_optional_string(value: Any, name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None.")


def _validate_positive_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def _validate_count(value: Any, name: str) -> None:
    if type(value) is not int or value < 0:
        raise TypeError(f"{name} must be a non-negative integer.")
