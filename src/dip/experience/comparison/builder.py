"""Deterministic transformation from comparison results to view models."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from dip.comparison import (
    ComparisonResult,
    ExecutionComparison,
    ModuleComparison,
    ValueChange,
)
from dip.intelligence_history import (
    IntelligenceHistoryRecord,
    IntelligenceHistoryRun,
)

from .models import (
    ComparisonValueAvailability,
    ComparisonViewModelConsistencyError,
    ExecutionComparisonViewModel,
    FieldChangeViewModel,
    ModuleComparisonState,
    ModuleComparisonViewModel,
)


_GENERIC_FIELD_ORDER = (
    "status",
    "summary",
    "metrics",
    "evidence",
    "diagnostics",
)

_DEFAULT_MODULE_LABELS = MappingProxyType(
    {
        "collection_health": "Collection Health",
        "hidden_gems": "Hidden Gems",
        "historical_intelligence": "Historical Intelligence",
    }
)

_DEFAULT_FIELD_LABELS = MappingProxyType(
    {
        "status": "Status",
        "summary": "Summary",
        "metrics": "Metrics",
        "evidence": "Evidence",
        "diagnostics": "Diagnostics",
    }
)

_STATE_BY_RESULT = MappingProxyType(
    {
        ComparisonResult.ADDED: ModuleComparisonState.ADDED,
        ComparisonResult.REMOVED: ModuleComparisonState.REMOVED,
        ComparisonResult.CHANGED: ModuleComparisonState.CHANGED,
        ComparisonResult.UNCHANGED: ModuleComparisonState.UNCHANGED,
    }
)


class ComparisonViewModelBuilder:
    """Build immutable presentation models without recalculating comparisons."""

    def __init__(
        self,
        *,
        module_labels: Mapping[str, str] | None = None,
        field_labels: Mapping[str, str] | None = None,
    ) -> None:
        self._module_labels = _label_registry(
            _DEFAULT_MODULE_LABELS,
            module_labels,
            "module",
        )
        self._field_labels = _label_registry(
            _DEFAULT_FIELD_LABELS,
            field_labels,
            "field",
        )

    def build(
        self,
        comparison: ExecutionComparison,
    ) -> ExecutionComparisonViewModel:
        """Transform one validated comparison while preserving its order."""

        self._validate_execution(comparison)
        seen: set[str] = set()
        modules: list[ModuleComparisonViewModel] = []
        for module in comparison.modules:
            if module.module_id in seen:
                raise ComparisonViewModelConsistencyError(
                    f"Duplicate comparison module ID {module.module_id!r}."
                )
            seen.add(module.module_id)
            modules.append(self._module_view_model(comparison, module))

        modules_value = tuple(modules)
        state_counts = {
            state: sum(module.state is state for module in modules_value)
            for state in ModuleComparisonState
        }
        try:
            return ExecutionComparisonViewModel(
                current_run_id=comparison.current_run.run_id,
                previous_run_id=comparison.previous_run.run_id,
                current_executed_at=comparison.current_run.executed_at,
                previous_executed_at=comparison.previous_run.executed_at,
                has_changes=any(module.has_changes for module in modules_value),
                total_module_count=len(modules_value),
                changed_module_count=state_counts[
                    ModuleComparisonState.CHANGED
                ],
                unchanged_module_count=state_counts[
                    ModuleComparisonState.UNCHANGED
                ],
                added_module_count=state_counts[ModuleComparisonState.ADDED],
                removed_module_count=state_counts[
                    ModuleComparisonState.REMOVED
                ],
                modules=modules_value,
            )
        except ComparisonViewModelConsistencyError:
            raise
        except (TypeError, ValueError) as exc:
            raise ComparisonViewModelConsistencyError(
                f"Unable to build the execution comparison ViewModel: {exc}"
            ) from exc

    def _module_view_model(
        self,
        comparison: ExecutionComparison,
        module: ModuleComparison,
    ) -> ModuleComparisonViewModel:
        self._validate_module(comparison, module)
        state = _STATE_BY_RESULT[module.result]
        previous_available = module.previous_record is not None
        current_available = module.current_record is not None

        fields_value = tuple(
            self._field_view_model(
                field_id,
                getattr(module, field_id),
                previous_available=previous_available,
                current_available=current_available,
            )
            for field_id in _GENERIC_FIELD_ORDER
        )
        changed_count = sum(field.changed for field in fields_value)
        if state is ModuleComparisonState.UNCHANGED and changed_count:
            raise ComparisonViewModelConsistencyError(
                f"Module {module.module_id!r} is unchanged but has changed fields."
            )
        if state is ModuleComparisonState.CHANGED and not changed_count:
            raise ComparisonViewModelConsistencyError(
                f"Module {module.module_id!r} is changed but has no changed fields."
            )

        try:
            return ModuleComparisonViewModel(
                module_id=module.module_id,
                label=self._module_label(module.module_id),
                state=state,
                has_changes=state is not ModuleComparisonState.UNCHANGED,
                fields=fields_value,
                changed_field_count=changed_count,
                unchanged_field_count=len(fields_value) - changed_count,
                previous_module_version=(
                    None
                    if module.previous_record is None
                    else module.previous_record.module_version
                ),
                current_module_version=(
                    None
                    if module.current_record is None
                    else module.current_record.module_version
                ),
            )
        except ComparisonViewModelConsistencyError:
            raise
        except (TypeError, ValueError) as exc:
            raise ComparisonViewModelConsistencyError(
                f"Unable to build ViewModel for module {module.module_id!r}: {exc}"
            ) from exc

    def _field_view_model(
        self,
        field_id: str,
        change: ValueChange,
        *,
        previous_available: bool,
        current_available: bool,
    ) -> FieldChangeViewModel:
        if type(change) is not ValueChange:
            raise ComparisonViewModelConsistencyError(
                f"Comparison field {field_id!r} is not a ValueChange."
            )
        if not previous_available and change.previous is not None:
            raise ComparisonViewModelConsistencyError(
                f"Unavailable previous field {field_id!r} contains a value."
            )
        if not current_available and change.current is not None:
            raise ComparisonViewModelConsistencyError(
                f"Unavailable current field {field_id!r} contains a value."
            )

        try:
            return FieldChangeViewModel(
                field_id=field_id,
                label=self._field_labels[field_id],
                previous_value=(change.previous if previous_available else None),
                current_value=(change.current if current_available else None),
                previous_availability=(
                    ComparisonValueAvailability.AVAILABLE
                    if previous_available
                    else ComparisonValueAvailability.UNAVAILABLE
                ),
                current_availability=(
                    ComparisonValueAvailability.AVAILABLE
                    if current_available
                    else ComparisonValueAvailability.UNAVAILABLE
                ),
                changed=change.changed,
            )
        except ComparisonViewModelConsistencyError:
            raise
        except (TypeError, ValueError) as exc:
            raise ComparisonViewModelConsistencyError(
                f"Unable to build ViewModel field {field_id!r}: {exc}"
            ) from exc

    @staticmethod
    def _validate_execution(comparison: Any) -> None:
        if type(comparison) is not ExecutionComparison:
            raise ComparisonViewModelConsistencyError(
                "ComparisonViewModelBuilder requires an ExecutionComparison."
            )
        for name, run in (
            ("current", comparison.current_run),
            ("previous", comparison.previous_run),
        ):
            if type(run) is not IntelligenceHistoryRun:
                raise ComparisonViewModelConsistencyError(
                    f"The {name} run is not an IntelligenceHistoryRun."
                )
            if type(run.run_id) is not int or run.run_id <= 0:
                raise ComparisonViewModelConsistencyError(
                    f"The {name} run ID must be a positive integer."
                )
        if comparison.current_run.run_id == comparison.previous_run.run_id:
            raise ComparisonViewModelConsistencyError(
                "Current and previous comparison runs must differ."
            )
        if type(comparison.modules) is not tuple:
            raise ComparisonViewModelConsistencyError(
                "Comparison modules must be an immutable tuple."
            )
        if any(type(module) is not ModuleComparison for module in comparison.modules):
            raise ComparisonViewModelConsistencyError(
                "Comparison modules must contain only ModuleComparison values."
            )

    @staticmethod
    def _validate_module(
        comparison: ExecutionComparison,
        module: ModuleComparison,
    ) -> None:
        if type(module.result) is not ComparisonResult:
            raise ComparisonViewModelConsistencyError(
                f"Module {module.module_id!r} has an unsupported comparison state."
            )
        previous = module.previous_record
        current = module.current_record
        for name, record in (("previous", previous), ("current", current)):
            if record is None:
                continue
            if type(record) is not IntelligenceHistoryRecord:
                raise ComparisonViewModelConsistencyError(
                    f"Module {module.module_id!r} has an invalid {name} record."
                )
            if record.module_id != module.module_id:
                raise ComparisonViewModelConsistencyError(
                    f"Module {module.module_id!r} has a mismatched {name} record."
                )
        if module.result is ComparisonResult.ADDED:
            if previous is not None or current is None:
                raise ComparisonViewModelConsistencyError(
                    f"Added module {module.module_id!r} has malformed records."
                )
        elif module.result is ComparisonResult.REMOVED:
            if previous is None or current is not None:
                raise ComparisonViewModelConsistencyError(
                    f"Removed module {module.module_id!r} has malformed records."
                )
        elif previous is None or current is None:
            raise ComparisonViewModelConsistencyError(
                f"Shared module {module.module_id!r} requires both records."
            )

        if (
            previous is not None
            and previous.run_id != comparison.previous_run.run_id
        ):
            raise ComparisonViewModelConsistencyError(
                f"Module {module.module_id!r} has the wrong previous run."
            )
        if current is not None and current.run_id != comparison.current_run.run_id:
            raise ComparisonViewModelConsistencyError(
                f"Module {module.module_id!r} has the wrong current run."
            )

    def _module_label(self, module_id: str) -> str:
        known = self._module_labels.get(module_id)
        if known is not None:
            return known
        fallback = module_id.replace("_", " ").strip().title()
        return fallback or module_id


def _label_registry(
    defaults: Mapping[str, str],
    overrides: Mapping[str, str] | None,
    name: str,
) -> Mapping[str, str]:
    labels = dict(defaults)
    if overrides is not None:
        if not isinstance(overrides, Mapping):
            raise TypeError(f"{name}_labels must be a mapping.")
        for identifier, label in overrides.items():
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError(f"{name} label IDs must be non-empty strings.")
            if identifier != identifier.strip():
                raise ValueError(
                    f"{name} label IDs must not contain surrounding whitespace."
                )
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"{name} labels must be non-empty strings.")
            labels[identifier] = label
    return MappingProxyType(
        {
            identifier: labels[identifier]
            for identifier in sorted(labels)
        }
    )
