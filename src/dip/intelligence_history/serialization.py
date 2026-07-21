"""Deterministic serialization for Intelligence History values."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from typing import Any, NoReturn, TypeAlias

from dip.intelligence.models import IntelligenceStatus

from .models import IntelligenceHistoryRecord, IntelligenceHistoryRun, _FrozenList

JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

_TYPE_KEY = "__dip_type__"
_TUPLE_TYPE = "tuple"
_DATE_TYPE = "date"
_DATETIME_TYPE = "datetime"
_ENUM_TYPE = "enum"
_MAPPING_TYPE = "mapping"
_RUN_TYPE = "intelligence_history_run"
_RECORD_TYPE = "intelligence_history_record"


_ENUM_TYPES: dict[str, type[Enum]] = {
    "dip.intelligence.models.IntelligenceStatus": IntelligenceStatus,
}


class IntelligenceSerializationError(ValueError):
    """Raised when a value cannot be represented without losing meaning."""


class IntelligenceDeserializationError(IntelligenceSerializationError):
    """Raised when serialized intelligence data is malformed or unsupported."""


def serialize_intelligence_value(value: Any) -> JsonValue:
    """Convert a supported value into a deterministic JSON value tree."""

    return _serialize(value, path="$", approved_model=False)


def deserialize_intelligence_value(value: JsonValue) -> Any:
    """Restore a supported value from a validated JSON value tree."""

    return _deserialize(value, path="$", approved_model=False)


def dumps_intelligence_value(value: Any) -> str:
    """Return the canonical JSON representation of a supported value."""

    serialized = serialize_intelligence_value(value)
    return json.dumps(
        serialized,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def loads_intelligence_value(payload: str) -> Any:
    """Parse and restore a canonical Intelligence History JSON payload."""

    if not isinstance(payload, str):
        raise IntelligenceDeserializationError(
            f"$ must be a JSON string, got {type(payload).__name__}."
        )

    try:
        value = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except IntelligenceDeserializationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise IntelligenceDeserializationError(f"$ contains invalid JSON: {exc}") from exc

    return deserialize_intelligence_value(value)


def _serialize(value: Any, *, path: str, approved_model: bool) -> JsonValue:
    if isinstance(value, Enum):
        enum_name = f"{type(value).__module__}.{type(value).__qualname__}"
        if _ENUM_TYPES.get(enum_name) is not type(value):
            _serialization_error(path, value, "enum type is not registered")
        return {
            _TYPE_KEY: _ENUM_TYPE,
            "enum": enum_name,
            "value": _serialize(value.value, path=f"{path}.value", approved_model=False),
        }

    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            _serialization_error(path, value, "non-finite floats are unsupported")
        return value

    if isinstance(value, datetime):
        return {_TYPE_KEY: _DATETIME_TYPE, "value": value.isoformat()}

    if isinstance(value, date):
        return {_TYPE_KEY: _DATE_TYPE, "value": value.isoformat()}

    if isinstance(value, IntelligenceHistoryRun):
        return {
            _TYPE_KEY: _RUN_TYPE,
            "collection_snapshot_id": _serialize(
                value.collection_snapshot_id,
                path=f"{path}.collection_snapshot_id",
                approved_model=True,
            ),
            "engine_version": _serialize(
                value.engine_version,
                path=f"{path}.engine_version",
                approved_model=True,
            ),
            "executed_at": _serialize(
                value.executed_at,
                path=f"{path}.executed_at",
                approved_model=True,
            ),
            "result_count": _serialize(
                value.result_count,
                path=f"{path}.result_count",
                approved_model=True,
            ),
            "run_id": _serialize(
                value.run_id,
                path=f"{path}.run_id",
                approved_model=True,
            ),
        }

    if isinstance(value, IntelligenceHistoryRecord):
        return {
            _TYPE_KEY: _RECORD_TYPE,
            "diagnostics": _serialize(
                value.diagnostics,
                path=f"{path}.diagnostics",
                approved_model=True,
            ),
            "evidence": _serialize(
                value.evidence,
                path=f"{path}.evidence",
                approved_model=True,
            ),
            "insights": _serialize(
                value.insights,
                path=f"{path}.insights",
                approved_model=True,
            ),
            "metrics": _serialize(
                value.metrics,
                path=f"{path}.metrics",
                approved_model=True,
            ),
            "module_id": _serialize(
                value.module_id,
                path=f"{path}.module_id",
                approved_model=True,
            ),
            "module_version": _serialize(
                value.module_version,
                path=f"{path}.module_version",
                approved_model=True,
            ),
            "record_id": _serialize(
                value.record_id,
                path=f"{path}.record_id",
                approved_model=True,
            ),
            "run_id": _serialize(
                value.run_id,
                path=f"{path}.run_id",
                approved_model=True,
            ),
            "status": _serialize(
                value.status,
                path=f"{path}.status",
                approved_model=True,
            ),
            "summary": _serialize(
                value.summary,
                path=f"{path}.summary",
                approved_model=True,
            ),
        }

    if isinstance(value, (list, _FrozenList)):
        return [
            _serialize(item, path=f"{path}[{index}]", approved_model=approved_model)
            for index, item in enumerate(value)
        ]

    if isinstance(value, tuple):
        return {
            _TYPE_KEY: _TUPLE_TYPE,
            "items": [
                _serialize(
                    item,
                    path=f"{path}[{index}]",
                    approved_model=approved_model,
                )
                for index, item in enumerate(value)
            ],
        }

    if isinstance(value, Mapping):
        items: list[JsonValue] = []
        for key in value:
            if not isinstance(key, str):
                raise IntelligenceSerializationError(
                    f"{path} contains unsupported mapping key type "
                    f"{type(key).__name__}; keys must be strings."
                )
        for key in sorted(value):
            items.append(
                [
                    key,
                    _serialize(
                        value[key],
                        path=_mapping_path(path, key),
                        approved_model=approved_model,
                    ),
                ]
            )
        return {_TYPE_KEY: _MAPPING_TYPE, "items": items}

    qualifier = "approved model field" if approved_model else "value"
    _serialization_error(path, value, f"unsupported {qualifier}")


def _deserialize(value: Any, *, path: str, approved_model: bool) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            _deserialization_error(path, "non-finite floats are unsupported")
        return value

    if isinstance(value, list):
        return [
            _deserialize(item, path=f"{path}[{index}]", approved_model=approved_model)
            for index, item in enumerate(value)
        ]

    if not isinstance(value, dict):
        _deserialization_error(path, f"unsupported JSON value type {type(value).__name__}")

    if _TYPE_KEY not in value:
        for key in value:
            if not isinstance(key, str):
                _deserialization_error(
                    path,
                    f"mapping key type {type(key).__name__} is unsupported",
                )
        return {
            key: _deserialize(
                item,
                path=_mapping_path(path, key),
                approved_model=approved_model,
            )
            for key, item in value.items()
        }

    tag = value[_TYPE_KEY]
    if not isinstance(tag, str):
        _deserialization_error(path, f"{_TYPE_KEY} must be a string")

    if tag == _TUPLE_TYPE:
        _require_keys(value, {_TYPE_KEY, "items"}, path)
        items = value["items"]
        if not isinstance(items, list):
            _deserialization_error(f"{path}.items", "must be a list")
        return tuple(
            _deserialize(item, path=f"{path}[{index}]", approved_model=approved_model)
            for index, item in enumerate(items)
        )

    if tag == _MAPPING_TYPE:
        _require_keys(value, {_TYPE_KEY, "items"}, path)
        items = value["items"]
        if not isinstance(items, list):
            _deserialization_error(f"{path}.items", "must be a list")
        result: dict[str, Any] = {}
        previous_key: str | None = None
        for index, item in enumerate(items):
            item_path = f"{path}.items[{index}]"
            if not isinstance(item, list) or len(item) != 2:
                _deserialization_error(item_path, "must be a two-item list")
            key = _require_string(item[0], f"{item_path}[0]")
            if key in result:
                _deserialization_error(item_path, f"duplicate mapping key {key!r}")
            if previous_key is not None and key <= previous_key:
                _deserialization_error(
                    item_path,
                    "mapping keys must be in strictly sorted order",
                )
            result[key] = _deserialize(
                item[1],
                path=_mapping_path(path, key),
                approved_model=approved_model,
            )
            previous_key = key
        return result

    if tag == _DATE_TYPE:
        _require_keys(value, {_TYPE_KEY, "value"}, path)
        raw_value = _require_string(value["value"], f"{path}.value")
        try:
            return date.fromisoformat(raw_value)
        except ValueError as exc:
            raise IntelligenceDeserializationError(
                f"{path}.value is not a valid ISO date: {raw_value!r}."
            ) from exc

    if tag == _DATETIME_TYPE:
        _require_keys(value, {_TYPE_KEY, "value"}, path)
        raw_value = _require_string(value["value"], f"{path}.value")
        try:
            return datetime.fromisoformat(raw_value)
        except ValueError as exc:
            raise IntelligenceDeserializationError(
                f"{path}.value is not a valid ISO datetime: {raw_value!r}."
            ) from exc

    if tag == _ENUM_TYPE:
        _require_keys(value, {_TYPE_KEY, "enum", "value"}, path)
        enum_name = _require_string(value["enum"], f"{path}.enum")
        enum_type = _ENUM_TYPES.get(enum_name)
        if enum_type is None:
            _deserialization_error(path, f"unsupported enum type {enum_name!r}")
        enum_value = _deserialize(
            value["value"],
            path=f"{path}.value",
            approved_model=False,
        )
        try:
            return enum_type(enum_value)
        except (TypeError, ValueError) as exc:
            raise IntelligenceDeserializationError(
                f"{path}.value is invalid for enum {enum_name!r}: {enum_value!r}."
            ) from exc

    if tag == _RUN_TYPE:
        _require_keys(
            value,
            {
                _TYPE_KEY,
                "run_id",
                "executed_at",
                "engine_version",
                "collection_snapshot_id",
                "result_count",
            },
            path,
        )
        fields = _deserialize_model_fields(value, path)
        _validate_run_fields(fields, path)
        try:
            return IntelligenceHistoryRun(**fields)
        except (TypeError, ValueError) as exc:
            raise IntelligenceDeserializationError(
                f"{path} is not a valid IntelligenceHistoryRun: {exc}"
            ) from exc

    if tag == _RECORD_TYPE:
        _require_keys(
            value,
            {
                _TYPE_KEY,
                "record_id",
                "run_id",
                "module_id",
                "module_version",
                "status",
                "summary",
                "insights",
                "metrics",
                "evidence",
                "diagnostics",
            },
            path,
        )
        fields = _deserialize_model_fields(value, path)
        _validate_record_fields(fields, path)
        try:
            return IntelligenceHistoryRecord(**fields)
        except (TypeError, ValueError) as exc:
            raise IntelligenceDeserializationError(
                f"{path} is not a valid IntelligenceHistoryRecord: {exc}"
            ) from exc

    _deserialization_error(path, f"unknown tagged value type {tag!r}")


def _deserialize_model_fields(value: dict[str, Any], path: str) -> dict[str, Any]:
    return {
        key: _deserialize(
            item,
            path=_mapping_path(path, key),
            approved_model=True,
        )
        for key, item in value.items()
        if key != _TYPE_KEY
    }


def _validate_run_fields(fields: dict[str, Any], path: str) -> None:
    _require_optional_int(fields["run_id"], f"{path}.run_id")
    if type(fields["executed_at"]) is not datetime:
        _deserialization_error(f"{path}.executed_at", "must be a datetime")
    _require_optional_string(fields["engine_version"], f"{path}.engine_version")
    _require_optional_int(
        fields["collection_snapshot_id"],
        f"{path}.collection_snapshot_id",
    )
    result_count = _require_int(fields["result_count"], f"{path}.result_count")
    if result_count < 0:
        _deserialization_error(f"{path}.result_count", "must not be negative")


def _validate_record_fields(fields: dict[str, Any], path: str) -> None:
    _require_optional_int(fields["record_id"], f"{path}.record_id")
    _require_int(fields["run_id"], f"{path}.run_id")
    _require_string(fields["module_id"], f"{path}.module_id")
    _require_optional_string(fields["module_version"], f"{path}.module_version")
    if type(fields["status"]) is not IntelligenceStatus:
        _deserialization_error(
            f"{path}.status",
            "must be an IntelligenceStatus",
        )
    _require_string(fields["summary"], f"{path}.summary")
    _require_string_tuple(fields["insights"], f"{path}.insights")
    if not isinstance(fields["metrics"], dict):
        _deserialization_error(f"{path}.metrics", "must be a mapping")
    _require_string_tuple(fields["evidence"], f"{path}.evidence")
    _require_string_tuple(fields["diagnostics"], f"{path}.diagnostics")


def _require_int(value: Any, path: str) -> int:
    if type(value) is not int:
        _deserialization_error(path, "must be an integer")
    return value


def _require_optional_int(value: Any, path: str) -> int | None:
    if value is not None:
        return _require_int(value, path)
    return None


def _require_optional_string(value: Any, path: str) -> str | None:
    if value is not None:
        return _require_string(value, path)
    return None


def _require_string_tuple(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        _deserialization_error(path, "must be a tuple")
    for index, item in enumerate(value):
        _require_string(item, f"{path}[{index}]")
    return value


def _require_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    for key in value:
        if not isinstance(key, str):
            _deserialization_error(
                path,
                f"mapping key type {type(key).__name__} is unsupported",
            )
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing keys {missing}")
        if unexpected:
            details.append(f"unexpected keys {unexpected}")
        _deserialization_error(path, "; ".join(details))


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _deserialization_error(path, "must be a string")
    return value


def _mapping_path(path: str, key: str) -> str:
    return f"{path}.{key}" if key.isidentifier() else f"{path}[{key!r}]"


def _serialization_error(path: str, value: Any, reason: str) -> NoReturn:
    raise IntelligenceSerializationError(
        f"{path} contains unsupported type {type(value).__name__}: {reason}."
    )


def _deserialization_error(path: str, reason: str) -> NoReturn:
    raise IntelligenceDeserializationError(f"{path} is invalid: {reason}.")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IntelligenceDeserializationError(
                f"$ contains duplicate JSON key {key!r}."
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise IntelligenceDeserializationError(
        f"$ contains unsupported non-finite number {value}."
    )
