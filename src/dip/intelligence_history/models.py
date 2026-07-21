"""Immutable domain models for Intelligence History."""

from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Any, Mapping

from dip.intelligence.models import IntelligenceStatus


class _FrozenList(tuple[Any, ...]):
    """Immutable list representation that preserves list serialization."""

    __slots__ = ()

    def __new__(cls, values: list[Any]) -> "_FrozenList":
        return super().__new__(cls, (_freeze_value(value) for value in values))

    def __repr__(self) -> str:
        return repr(list(self))


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key in value:
            if not isinstance(key, str):
                raise TypeError("Intelligence History mapping keys must be strings.")
        for key in sorted(value):
            frozen[key] = _freeze_value(value[key])
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return _FrozenList(value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if value is None or isinstance(
        value,
        (bool, int, float, str, date, datetime, IntelligenceStatus),
    ):
        return value
    raise TypeError(
        f"Intelligence History values cannot contain mutable or unsupported "
        f"type {type(value).__name__}."
    )


@dataclass(frozen=True)
class IntelligenceHistoryRun:
    """Metadata for one completed Intelligence Engine execution."""

    run_id: int | None
    executed_at: datetime
    engine_version: str | None = None
    collection_snapshot_id: int | None = None
    result_count: int = 0

    def __post_init__(self) -> None:
        """Validate immutable execution metadata."""

        if self.run_id is not None and type(self.run_id) is not int:
            raise TypeError("run_id must be an integer or None.")
        if type(self.executed_at) is not datetime:
            raise TypeError("executed_at must be a datetime.")
        if self.engine_version is not None and not isinstance(
            self.engine_version,
            str,
        ):
            raise TypeError("engine_version must be a string or None.")
        if self.collection_snapshot_id is not None and type(
            self.collection_snapshot_id
        ) is not int:
            raise TypeError("collection_snapshot_id must be an integer or None.")
        if type(self.result_count) is not int or self.result_count < 0:
            raise TypeError("result_count must be a non-negative integer.")


@dataclass(frozen=True)
class IntelligenceHistoryRecord:
    """A preserved module result belonging to one historical run."""

    record_id: int | None
    run_id: int | None
    module_id: str
    module_version: str | None
    status: IntelligenceStatus
    summary: str
    insights: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Recursively detach and freeze collection fields."""

        if self.record_id is not None and type(self.record_id) is not int:
            raise TypeError("record_id must be an integer or None.")
        if self.run_id is not None and type(self.run_id) is not int:
            raise TypeError("run_id must be an integer or None.")
        if not isinstance(self.module_id, str):
            raise TypeError("module_id must be a string.")
        if self.module_version is not None and not isinstance(
            self.module_version,
            str,
        ):
            raise TypeError("module_version must be a string or None.")
        if type(self.status) is not IntelligenceStatus:
            raise TypeError("status must be an IntelligenceStatus.")
        if not isinstance(self.summary, str):
            raise TypeError("summary must be a string.")
        if not isinstance(self.metrics, Mapping):
            raise TypeError("metrics must be a mapping.")

        object.__setattr__(
            self,
            "insights",
            _freeze_string_tuple(self.insights, "insights"),
        )
        object.__setattr__(self, "metrics", _freeze_value(self.metrics))
        object.__setattr__(
            self,
            "evidence",
            _freeze_string_tuple(self.evidence, "evidence"),
        )
        object.__setattr__(
            self,
            "diagnostics",
            _freeze_string_tuple(self.diagnostics, "diagnostics"),
        )


def _freeze_string_tuple(values: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{field_name} must be a collection of strings.")
    try:
        frozen = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{field_name} must be a collection of strings.") from exc
    if any(not isinstance(value, str) for value in frozen):
        raise TypeError(f"{field_name} must contain only strings.")
    return frozen
