"""Immutable presentation models for the Dashboard homepage."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from dip.experience.comparison import ModuleComparisonState
from dip.intelligence import IntelligenceStatus

from .models import (
    DashboardCardState,
    DashboardCardViewModel,
    DashboardHiddenGemViewModel,
    HiddenGemsCardViewModel,
)


class DashboardHomepageConsistencyError(ValueError):
    """Raised when Dashboard homepage sections contradict one another."""


class DashboardSectionId(str, Enum):
    """Stable identifiers for the first Dashboard homepage sections."""

    COLLECTION_OVERVIEW = "collection_overview"
    COLLECTION_HEALTH = "collection_health"
    HIDDEN_GEMS = "hidden_gems"
    WHAT_CHANGED = "what_changed"
    LATEST_EXECUTION = "latest_execution"


class DashboardSectionState(str, Enum):
    """Explicit availability states understood by Dashboard interfaces."""

    LOADING = "loading"
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INSUFFICIENT_HISTORY = "insufficient_history"


@dataclass(frozen=True)
class DashboardCollectionOverviewViewModel:
    """Latest high-level collection context already present in history."""

    state: DashboardSectionState
    summary: str
    collection_size: int | None = None
    latest_executed_at: datetime | None = None
    current_status: IntelligenceStatus | None = None
    completed_module_count: int = 0
    total_module_count: int = 0
    section_id: DashboardSectionId = field(
        init=False,
        default=DashboardSectionId.COLLECTION_OVERVIEW,
    )
    title: str = field(init=False, default="Collection overview")

    def __post_init__(self) -> None:
        _validate_state(self.state)
        _validate_summary(self.summary)
        _validate_optional_count(self.collection_size, "collection_size")
        _validate_count(self.completed_module_count, "completed_module_count")
        _validate_count(self.total_module_count, "total_module_count")
        if self.completed_module_count > self.total_module_count:
            raise DashboardHomepageConsistencyError(
                "completed_module_count cannot exceed total_module_count."
            )

        if self.state is DashboardSectionState.AVAILABLE:
            if type(self.latest_executed_at) is not datetime:
                raise DashboardHomepageConsistencyError(
                    "An available overview requires latest_executed_at."
                )
            if type(self.current_status) is not IntelligenceStatus:
                raise DashboardHomepageConsistencyError(
                    "An available overview requires current_status."
                )
        elif (
            self.latest_executed_at is not None
            or self.current_status is not None
            or self.collection_size is not None
            or self.completed_module_count
            or self.total_module_count
        ):
            raise DashboardHomepageConsistencyError(
                "An unavailable overview must not contain execution values."
            )


@dataclass(frozen=True)
class DashboardCollectionHealthViewModel:
    """Homepage wrapper around the established Collection Health card."""

    state: DashboardSectionState
    card: DashboardCardViewModel | None
    section_id: DashboardSectionId = field(
        init=False,
        default=DashboardSectionId.COLLECTION_HEALTH,
    )
    title: str = field(init=False, default="Collection Health")

    def __post_init__(self) -> None:
        _validate_state(self.state)
        if self.state is DashboardSectionState.LOADING:
            if self.card is not None:
                raise DashboardHomepageConsistencyError(
                    "A loading Collection Health section cannot contain a card."
                )
            return
        if type(self.card) is not DashboardCardViewModel:
            raise DashboardHomepageConsistencyError(
                "Collection Health requires its established card ViewModel."
            )
        if self.card.module_id != DashboardSectionId.COLLECTION_HEALTH.value:
            raise DashboardHomepageConsistencyError(
                "Collection Health received a card for another module."
            )
        expected_state = _section_state_for_card(self.card.state)
        if self.state is not expected_state:
            raise DashboardHomepageConsistencyError(
                "Collection Health section state contradicts its card state."
            )


@dataclass(frozen=True)
class DashboardHiddenGemsViewModel:
    """Homepage Hidden Gems state plus a bounded ranked preview."""

    state: DashboardSectionState
    card: HiddenGemsCardViewModel | None
    preview: tuple[DashboardHiddenGemViewModel, ...] = ()
    preview_limit: int = 3
    section_id: DashboardSectionId = field(
        init=False,
        default=DashboardSectionId.HIDDEN_GEMS,
    )
    title: str = field(init=False, default="Hidden Gems")

    def __post_init__(self) -> None:
        _validate_state(self.state)
        _validate_positive_count(self.preview_limit, "preview_limit")
        preview = _freeze_preview(self.preview)
        object.__setattr__(self, "preview", preview)

        if self.state is DashboardSectionState.LOADING:
            if self.card is not None or preview:
                raise DashboardHomepageConsistencyError(
                    "A loading Hidden Gems section cannot contain result data."
                )
            return
        if type(self.card) is not HiddenGemsCardViewModel:
            raise DashboardHomepageConsistencyError(
                "Hidden Gems requires its established card ViewModel."
            )
        if self.card.module_id != DashboardSectionId.HIDDEN_GEMS.value:
            raise DashboardHomepageConsistencyError(
                "Hidden Gems received a card for another module."
            )
        expected_state = _section_state_for_card(self.card.state)
        if (
            expected_state is DashboardSectionState.AVAILABLE
            and self.card.total_hidden_gems == 0
        ):
            expected_state = DashboardSectionState.EMPTY
        if self.state is not expected_state:
            raise DashboardHomepageConsistencyError(
                "Hidden Gems section state contradicts its card state."
            )
        if self.card.state is DashboardCardState.READY and (
            self.card.total_hidden_gems != len(self.card.ranked_gems)
        ):
            raise DashboardHomepageConsistencyError(
                "Hidden Gems candidate count does not match ranked candidates."
            )
        if len(preview) > self.preview_limit:
            raise DashboardHomepageConsistencyError(
                "Hidden Gems preview exceeds preview_limit."
            )
        expected = self.card.ranked_gems[: len(preview)]
        if preview != expected:
            raise DashboardHomepageConsistencyError(
                "Hidden Gems preview must preserve ranked candidate order."
            )
        if self.state is DashboardSectionState.EMPTY and (
            self.card.total_hidden_gems != 0 or preview
        ):
            raise DashboardHomepageConsistencyError(
                "An empty Hidden Gems section must contain zero candidates."
            )


@dataclass(frozen=True)
class DashboardChangedModuleViewModel:
    """One non-unchanged module copied from a comparison ViewModel."""

    module_id: str
    label: str
    state: ModuleComparisonState

    def __post_init__(self) -> None:
        _validate_identifier(self.module_id, "module_id")
        _validate_summary(self.label, "label")
        if type(self.state) is not ModuleComparisonState:
            raise TypeError("state must be a ModuleComparisonState.")
        if self.state is ModuleComparisonState.UNCHANGED:
            raise DashboardHomepageConsistencyError(
                "The changed-module list cannot contain unchanged modules."
            )


@dataclass(frozen=True)
class DashboardChangeSummaryViewModel:
    """Presentation-ready summary of the latest two executions."""

    state: DashboardSectionState
    summary: str
    has_changes: bool | None = None
    total_module_count: int = 0
    changed_module_count: int = 0
    unchanged_module_count: int = 0
    added_module_count: int = 0
    removed_module_count: int = 0
    changed_modules: tuple[DashboardChangedModuleViewModel, ...] = ()
    section_id: DashboardSectionId = field(
        init=False,
        default=DashboardSectionId.WHAT_CHANGED,
    )
    title: str = field(init=False, default="What Changed")

    def __post_init__(self) -> None:
        _validate_state(self.state)
        _validate_summary(self.summary)
        changed_modules = _freeze_changed_modules(self.changed_modules)
        object.__setattr__(self, "changed_modules", changed_modules)
        counts = (
            self.changed_module_count,
            self.unchanged_module_count,
            self.added_module_count,
            self.removed_module_count,
        )
        for name, value in zip(
            (
                "changed_module_count",
                "unchanged_module_count",
                "added_module_count",
                "removed_module_count",
            ),
            counts,
            strict=True,
        ):
            _validate_count(value, name)
        _validate_count(self.total_module_count, "total_module_count")

        if self.state is DashboardSectionState.AVAILABLE:
            if type(self.has_changes) is not bool:
                raise DashboardHomepageConsistencyError(
                    "An available change summary requires has_changes."
                )
            if self.total_module_count != sum(counts):
                raise DashboardHomepageConsistencyError(
                    "Change counts must sum to total_module_count."
                )
            expected_changed = sum(
                (
                    self.changed_module_count,
                    self.added_module_count,
                    self.removed_module_count,
                )
            )
            if len(changed_modules) != expected_changed:
                raise DashboardHomepageConsistencyError(
                    "Changed-module entries do not match the change counts."
                )
            if self.has_changes != bool(expected_changed):
                raise DashboardHomepageConsistencyError(
                    "has_changes does not match the change counts."
                )
            actual_states = {
                state: sum(module.state is state for module in changed_modules)
                for state in (
                    ModuleComparisonState.CHANGED,
                    ModuleComparisonState.ADDED,
                    ModuleComparisonState.REMOVED,
                )
            }
            if actual_states[ModuleComparisonState.CHANGED] != self.changed_module_count:
                raise DashboardHomepageConsistencyError(
                    "Changed modules do not match changed_module_count."
                )
            if actual_states[ModuleComparisonState.ADDED] != self.added_module_count:
                raise DashboardHomepageConsistencyError(
                    "Added modules do not match added_module_count."
                )
            if actual_states[ModuleComparisonState.REMOVED] != self.removed_module_count:
                raise DashboardHomepageConsistencyError(
                    "Removed modules do not match removed_module_count."
                )
        elif self.has_changes is not None or any(counts) or self.total_module_count or changed_modules:
            raise DashboardHomepageConsistencyError(
                "A non-available change summary cannot contain comparison values."
            )


@dataclass(frozen=True)
class DashboardExecutionViewModel:
    """Diagnostics-light metadata for the latest historical execution."""

    state: DashboardSectionState
    summary: str
    run_id: int | None = None
    executed_at: datetime | None = None
    module_count: int = 0
    engine_version: str | None = None
    successful: bool | None = None
    section_id: DashboardSectionId = field(
        init=False,
        default=DashboardSectionId.LATEST_EXECUTION,
    )
    title: str = field(init=False, default="Latest execution")

    def __post_init__(self) -> None:
        _validate_state(self.state)
        _validate_summary(self.summary)
        _validate_count(self.module_count, "module_count")
        if self.engine_version is not None and not isinstance(self.engine_version, str):
            raise TypeError("engine_version must be a string or None.")

        if self.state is DashboardSectionState.AVAILABLE:
            _validate_positive_count(self.run_id, "run_id")
            if type(self.executed_at) is not datetime:
                raise DashboardHomepageConsistencyError(
                    "An available execution requires executed_at."
                )
            if type(self.successful) is not bool:
                raise DashboardHomepageConsistencyError(
                    "An available execution requires successful."
                )
        elif (
            self.run_id is not None
            or self.executed_at is not None
            or self.module_count
            or self.engine_version is not None
            or self.successful is not None
        ):
            raise DashboardHomepageConsistencyError(
                "A non-available execution cannot contain execution values."
            )


DashboardHomepageSection = (
    DashboardCollectionOverviewViewModel
    | DashboardCollectionHealthViewModel
    | DashboardHiddenGemsViewModel
    | DashboardChangeSummaryViewModel
    | DashboardExecutionViewModel
)

_SECTION_ORDER = tuple(DashboardSectionId)


@dataclass(frozen=True)
class DashboardHomepageViewModel:
    """Exactly five explicitly ordered Dashboard homepage sections."""

    sections: tuple[DashboardHomepageSection, ...]

    def __post_init__(self) -> None:
        try:
            sections = tuple(self.sections)
        except TypeError as exc:
            raise TypeError("sections must be a collection of Dashboard sections.") from exc
        if any(not _is_section(section) for section in sections):
            raise TypeError("sections contain an unsupported Dashboard section.")
        identifiers = tuple(section.section_id for section in sections)
        if len(set(identifiers)) != len(identifiers):
            raise DashboardHomepageConsistencyError(
                "Dashboard homepage section identifiers must be unique."
            )
        if identifiers != _SECTION_ORDER:
            raise DashboardHomepageConsistencyError(
                "Dashboard homepage sections must use the documented order."
            )
        overview = sections[0]
        execution = sections[4]
        if overview.state is not execution.state:
            raise DashboardHomepageConsistencyError(
                "Collection overview and latest execution states must agree."
            )
        if overview.state is DashboardSectionState.AVAILABLE:
            if overview.latest_executed_at != execution.executed_at:
                raise DashboardHomepageConsistencyError(
                    "Homepage execution timestamps must agree."
                )
            if overview.total_module_count != execution.module_count:
                raise DashboardHomepageConsistencyError(
                    "Homepage module counts must agree."
                )
            if (
                overview.current_status is IntelligenceStatus.FAILED
            ) == execution.successful:
                raise DashboardHomepageConsistencyError(
                    "Homepage execution status values contradict one another."
                )
        object.__setattr__(self, "sections", sections)

    def section_for(
        self,
        section_id: DashboardSectionId | str,
    ) -> DashboardHomepageSection | None:
        """Return one section by its stable identifier."""

        try:
            identifier = DashboardSectionId(section_id)
        except (TypeError, ValueError):
            return None
        return next(
            (section for section in self.sections if section.section_id is identifier),
            None,
        )

    @classmethod
    def loading(cls) -> "DashboardHomepageViewModel":
        """Create the deterministic initial state used before desktop loading."""

        return cls(
            sections=(
                DashboardCollectionOverviewViewModel(
                    state=DashboardSectionState.LOADING,
                    summary="Collection intelligence is loading.",
                ),
                DashboardCollectionHealthViewModel(
                    state=DashboardSectionState.LOADING,
                    card=None,
                ),
                DashboardHiddenGemsViewModel(
                    state=DashboardSectionState.LOADING,
                    card=None,
                ),
                DashboardChangeSummaryViewModel(
                    state=DashboardSectionState.LOADING,
                    summary="Recent changes are loading.",
                ),
                DashboardExecutionViewModel(
                    state=DashboardSectionState.LOADING,
                    summary="Latest execution is loading.",
                ),
            )
        )


def _is_section(value: Any) -> bool:
    return type(value) in {
        DashboardCollectionOverviewViewModel,
        DashboardCollectionHealthViewModel,
        DashboardHiddenGemsViewModel,
        DashboardChangeSummaryViewModel,
        DashboardExecutionViewModel,
    }


def _section_state_for_card(state: DashboardCardState) -> DashboardSectionState:
    return {
        DashboardCardState.READY: DashboardSectionState.AVAILABLE,
        DashboardCardState.SKIPPED: DashboardSectionState.EMPTY,
        DashboardCardState.FAILED: DashboardSectionState.ERROR,
        DashboardCardState.INCOMPLETE: DashboardSectionState.ERROR,
        DashboardCardState.UNAVAILABLE: DashboardSectionState.UNAVAILABLE,
        DashboardCardState.INSUFFICIENT_HISTORY: (
            DashboardSectionState.INSUFFICIENT_HISTORY
        ),
    }[state]


def _freeze_preview(value: Any) -> tuple[DashboardHiddenGemViewModel, ...]:
    try:
        preview = tuple(value)
    except TypeError as exc:
        raise TypeError("preview must be a collection of release ViewModels.") from exc
    if any(type(item) is not DashboardHiddenGemViewModel for item in preview):
        raise TypeError("preview must contain DashboardHiddenGemViewModel values.")
    return preview


def _freeze_changed_modules(
    value: Any,
) -> tuple[DashboardChangedModuleViewModel, ...]:
    try:
        modules = tuple(value)
    except TypeError as exc:
        raise TypeError("changed_modules must be a collection.") from exc
    if any(type(item) is not DashboardChangedModuleViewModel for item in modules):
        raise TypeError(
            "changed_modules must contain DashboardChangedModuleViewModel values."
        )
    module_ids = tuple(module.module_id for module in modules)
    if len(set(module_ids)) != len(module_ids):
        raise DashboardHomepageConsistencyError(
            "Changed Dashboard modules require unique module IDs."
        )
    return modules


def _validate_state(value: Any) -> None:
    if type(value) is not DashboardSectionState:
        raise TypeError("state must be a DashboardSectionState.")


def _validate_identifier(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string.")


def _validate_summary(value: Any, name: str = "summary") -> None:
    _validate_identifier(value, name)


def _validate_count(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must be non-negative.")


def _validate_positive_count(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _validate_optional_count(value: Any, name: str) -> None:
    if value is not None:
        _validate_count(value, name)


__all__ = [
    "DashboardChangeSummaryViewModel",
    "DashboardChangedModuleViewModel",
    "DashboardCollectionHealthViewModel",
    "DashboardCollectionOverviewViewModel",
    "DashboardExecutionViewModel",
    "DashboardHiddenGemsViewModel",
    "DashboardHomepageConsistencyError",
    "DashboardHomepageSection",
    "DashboardHomepageViewModel",
    "DashboardSectionId",
    "DashboardSectionState",
]
