"""Explicit deterministic serialization for Marketplace Intelligence roots."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import math
from typing import Any, NoReturn, TypeAlias

from dip.intelligence import IntelligenceResult, IntelligenceStatus

from .models import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceDiagnosticSeverity,
    MarketplaceExecutionContext,
    MarketplaceListingObservation,
    MarketplaceModuleResult,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)


JsonValue: TypeAlias = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)

MARKETPLACE_SCHEMA_VERSION = 1
_METRIC_TYPE = "__marketplace_type__"


class MarketplaceSerializationError(ValueError):
    """Raised when a Marketplace model cannot be represented without loss."""


class MarketplaceDeserializationError(MarketplaceSerializationError):
    """Raised when a Marketplace payload is malformed or unsupported."""


def marketplace_snapshot_to_dict(snapshot: MarketplaceSnapshot) -> dict[str, JsonValue]:
    """Return the versioned JSON-compatible tree for one snapshot."""

    if type(snapshot) is not MarketplaceSnapshot:
        raise TypeError("snapshot must be a MarketplaceSnapshot.")
    return {
        "schema_version": MARKETPLACE_SCHEMA_VERSION,
        "snapshot_id": snapshot.snapshot_id,
        "captured_at": snapshot.captured_at.isoformat(),
        "source": snapshot.source,
        "source_version": snapshot.source_version,
        "status": snapshot.status.value,
        "release_observations": [
            _release_to_dict(value) for value in snapshot.release_observations
        ],
        "listing_observations": [
            _listing_to_dict(value) for value in snapshot.listing_observations
        ],
        "diagnostics": [_diagnostic_to_dict(value) for value in snapshot.diagnostics],
    }


def marketplace_snapshot_from_dict(payload: Mapping[str, Any]) -> MarketplaceSnapshot:
    """Strictly reconstruct one immutable Marketplace snapshot."""

    root = _object(payload, "$")
    _keys(
        root,
        {
            "schema_version",
            "snapshot_id",
            "captured_at",
            "source",
            "source_version",
            "status",
            "release_observations",
            "listing_observations",
            "diagnostics",
        },
        "$",
    )
    _schema_version(root["schema_version"], "$.schema_version")
    releases = _list(root["release_observations"], "$.release_observations")
    listings = _list(root["listing_observations"], "$.listing_observations")
    diagnostics = _list(root["diagnostics"], "$.diagnostics")
    return _construct(
        MarketplaceSnapshot,
        "$",
        snapshot_id=_string(root["snapshot_id"], "$.snapshot_id"),
        captured_at=_datetime(root["captured_at"], "$.captured_at"),
        source=_string(root["source"], "$.source"),
        source_version=_optional_string(root["source_version"], "$.source_version"),
        status=_enum(MarketplaceDataStatus, root["status"], "$.status"),
        release_observations=tuple(
            _release_from_dict(value, f"$.release_observations[{index}]")
            for index, value in enumerate(releases)
        ),
        listing_observations=tuple(
            _listing_from_dict(value, f"$.listing_observations[{index}]")
            for index, value in enumerate(listings)
        ),
        diagnostics=tuple(
            _diagnostic_from_dict(value, f"$.diagnostics[{index}]")
            for index, value in enumerate(diagnostics)
        ),
    )


def marketplace_module_result_to_dict(
    module_result: MarketplaceModuleResult,
) -> dict[str, JsonValue]:
    """Return the versioned JSON-compatible tree for one module result envelope."""

    if type(module_result) is not MarketplaceModuleResult:
        raise TypeError("module_result must be a MarketplaceModuleResult.")
    context = module_result.context
    result = module_result.result
    return {
        "schema_version": MARKETPLACE_SCHEMA_VERSION,
        "context": {
            "execution_id": context.execution_id,
            "snapshot_ids": list(context.snapshot_ids),
            "executed_at": context.executed_at.isoformat(),
        },
        "result": {
            "module_id": result.module_id,
            "module_version": result.module_version,
            "status": result.status.value,
            "summary": result.summary,
            "insights": list(result.insights),
            "metrics": _metric_to_data(result.metrics, "$.result.metrics"),
            "evidence": list(result.evidence),
            "diagnostics": list(result.diagnostics),
        },
    }


def marketplace_module_result_from_dict(
    payload: Mapping[str, Any],
) -> MarketplaceModuleResult:
    """Strictly reconstruct one immutable module result envelope."""

    root = _object(payload, "$")
    _keys(root, {"schema_version", "context", "result"}, "$")
    _schema_version(root["schema_version"], "$.schema_version")
    raw_context = _object(root["context"], "$.context")
    _keys(raw_context, {"execution_id", "snapshot_ids", "executed_at"}, "$.context")
    snapshot_ids = _list(raw_context["snapshot_ids"], "$.context.snapshot_ids")
    context = _construct(
        MarketplaceExecutionContext,
        "$.context",
        execution_id=_string(raw_context["execution_id"], "$.context.execution_id"),
        snapshot_ids=tuple(
            _string(value, f"$.context.snapshot_ids[{index}]")
            for index, value in enumerate(snapshot_ids)
        ),
        executed_at=_datetime(raw_context["executed_at"], "$.context.executed_at"),
    )

    raw_result = _object(root["result"], "$.result")
    _keys(
        raw_result,
        {
            "module_id",
            "module_version",
            "status",
            "summary",
            "insights",
            "metrics",
            "evidence",
            "diagnostics",
        },
        "$.result",
    )
    result = IntelligenceResult(
        module_id=_string(raw_result["module_id"], "$.result.module_id"),
        module_version=_optional_string(
            raw_result["module_version"],
            "$.result.module_version",
        ),
        status=_enum(IntelligenceStatus, raw_result["status"], "$.result.status"),
        summary=_string(raw_result["summary"], "$.result.summary"),
        insights=_string_tuple(raw_result["insights"], "$.result.insights"),
        metrics=_metric_mapping_from_data(raw_result["metrics"], "$.result.metrics"),
        evidence=_string_tuple(raw_result["evidence"], "$.result.evidence"),
        diagnostics=_string_tuple(
            raw_result["diagnostics"],
            "$.result.diagnostics",
        ),
    )
    return _construct(
        MarketplaceModuleResult,
        "$",
        context=context,
        result=result,
    )


def dumps_marketplace_snapshot(snapshot: MarketplaceSnapshot) -> str:
    """Return canonical compact JSON for one Marketplace snapshot."""

    return _dumps(marketplace_snapshot_to_dict(snapshot))


def loads_marketplace_snapshot(payload: str) -> MarketplaceSnapshot:
    """Parse canonical-compatible JSON into one Marketplace snapshot."""

    return marketplace_snapshot_from_dict(_loads(payload))


def dumps_marketplace_module_result(module_result: MarketplaceModuleResult) -> str:
    """Return canonical compact JSON for one Marketplace module result."""

    return _dumps(marketplace_module_result_to_dict(module_result))


def loads_marketplace_module_result(payload: str) -> MarketplaceModuleResult:
    """Parse canonical-compatible JSON into one Marketplace module result."""

    return marketplace_module_result_from_dict(_loads(payload))


def _release_to_dict(value: MarketplaceReleaseObservation) -> dict[str, JsonValue]:
    return {
        "release_id": value.release_id,
        "observed_at": value.observed_at.isoformat(),
        "status": value.status.value,
        "lowest_price": _money_to_dict(value.lowest_price),
        "median_price": _money_to_dict(value.median_price),
        "highest_price": _money_to_dict(value.highest_price),
        "num_for_sale": value.num_for_sale,
        "num_wanted": value.num_wanted,
        "last_sold": value.last_sold.isoformat() if value.last_sold is not None else None,
        "diagnostics": [_diagnostic_to_dict(item) for item in value.diagnostics],
    }


def _release_from_dict(value: Any, path: str) -> MarketplaceReleaseObservation:
    raw = _object(value, path)
    _keys(
        raw,
        {
            "release_id",
            "observed_at",
            "status",
            "lowest_price",
            "median_price",
            "highest_price",
            "num_for_sale",
            "num_wanted",
            "last_sold",
            "diagnostics",
        },
        path,
    )
    raw_diagnostics = _list(raw["diagnostics"], f"{path}.diagnostics")
    return _construct(
        MarketplaceReleaseObservation,
        path,
        release_id=_integer(raw["release_id"], f"{path}.release_id"),
        observed_at=_datetime(raw["observed_at"], f"{path}.observed_at"),
        status=_enum(MarketplaceDataStatus, raw["status"], f"{path}.status"),
        lowest_price=_money_from_dict(raw["lowest_price"], f"{path}.lowest_price"),
        median_price=_money_from_dict(raw["median_price"], f"{path}.median_price"),
        highest_price=_money_from_dict(raw["highest_price"], f"{path}.highest_price"),
        num_for_sale=_optional_integer(raw["num_for_sale"], f"{path}.num_for_sale"),
        num_wanted=_optional_integer(raw["num_wanted"], f"{path}.num_wanted"),
        last_sold=_optional_date(raw["last_sold"], f"{path}.last_sold"),
        diagnostics=tuple(
            _diagnostic_from_dict(item, f"{path}.diagnostics[{index}]")
            for index, item in enumerate(raw_diagnostics)
        ),
    )


def _listing_to_dict(value: MarketplaceListingObservation) -> dict[str, JsonValue]:
    return {
        "listing_id": value.listing_id,
        "release_id": value.release_id,
        "observed_at": value.observed_at.isoformat(),
        "price": _money_to_dict(value.price),
        "shipping": _money_to_dict(value.shipping),
        "condition": value.condition,
        "seller_region": value.seller_region,
    }


def _listing_from_dict(value: Any, path: str) -> MarketplaceListingObservation:
    raw = _object(value, path)
    _keys(
        raw,
        {
            "listing_id",
            "release_id",
            "observed_at",
            "price",
            "shipping",
            "condition",
            "seller_region",
        },
        path,
    )
    return _construct(
        MarketplaceListingObservation,
        path,
        listing_id=_string(raw["listing_id"], f"{path}.listing_id"),
        release_id=_integer(raw["release_id"], f"{path}.release_id"),
        observed_at=_datetime(raw["observed_at"], f"{path}.observed_at"),
        price=_required_money(raw["price"], f"{path}.price"),
        shipping=_money_from_dict(raw["shipping"], f"{path}.shipping"),
        condition=_optional_string(raw["condition"], f"{path}.condition"),
        seller_region=_optional_string(
            raw["seller_region"],
            f"{path}.seller_region",
        ),
    )


def _money_to_dict(value: MarketplaceMoney | None) -> dict[str, JsonValue] | None:
    if value is None:
        return None
    return {"amount": str(value.amount), "currency": value.currency}


def _required_money(value: Any, path: str) -> MarketplaceMoney:
    result = _money_from_dict(value, path)
    if result is None:
        _error(path, "must not be null")
    return result


def _money_from_dict(value: Any, path: str) -> MarketplaceMoney | None:
    if value is None:
        return None
    raw = _object(value, path)
    _keys(raw, {"amount", "currency"}, path)
    amount = _decimal(raw["amount"], f"{path}.amount")
    return _construct(
        MarketplaceMoney,
        path,
        amount=amount,
        currency=_string(raw["currency"], f"{path}.currency"),
    )


def _diagnostic_to_dict(value: MarketplaceDiagnostic) -> dict[str, JsonValue]:
    return {
        "code": value.code,
        "message": value.message,
        "severity": value.severity.value,
        "details": {key: value.details[key] for key in sorted(value.details)},
    }


def _diagnostic_from_dict(value: Any, path: str) -> MarketplaceDiagnostic:
    raw = _object(value, path)
    _keys(raw, {"code", "message", "severity", "details"}, path)
    raw_details = _object(raw["details"], f"{path}.details")
    details = {
        _string(key, f"{path}.details key"): _string(
            item,
            f"{path}.details[{key!r}]",
        )
        for key, item in raw_details.items()
    }
    return _construct(
        MarketplaceDiagnostic,
        path,
        code=_string(raw["code"], f"{path}.code"),
        message=_string(raw["message"], f"{path}.message"),
        severity=_enum(
            MarketplaceDiagnosticSeverity,
            raw["severity"],
            f"{path}.severity",
        ),
        details=details,
    )


def _metric_to_data(value: Any, path: str) -> JsonValue:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise MarketplaceSerializationError(f"{path} must be finite.")
        return value
    if type(value) is Decimal:
        if not value.is_finite():
            raise MarketplaceSerializationError(f"{path} must be finite.")
        return {_METRIC_TYPE: "decimal", "value": str(value)}
    if type(value) is datetime:
        return {_METRIC_TYPE: "datetime", "value": value.isoformat()}
    if type(value) is date:
        return {_METRIC_TYPE: "date", "value": value.isoformat()}
    if type(value) is MarketplaceMoney:
        return {_METRIC_TYPE: "money", "value": _money_to_dict(value)}
    if type(value) is MarketplaceDiagnostic:
        return {_METRIC_TYPE: "diagnostic", "value": _diagnostic_to_dict(value)}
    if isinstance(value, tuple):
        return {
            _METRIC_TYPE: "tuple",
            "items": [
                _metric_to_data(item, f"{path}[{index}]")
                for index, item in enumerate(value)
            ],
        }
    if isinstance(value, Mapping):
        return {
            _METRIC_TYPE: "mapping",
            "items": [
                [key, _metric_to_data(value[key], f"{path}.{key}")]
                for key in sorted(value)
            ],
        }
    raise MarketplaceSerializationError(
        f"{path} contains unsupported type {type(value).__name__}."
    )


def _metric_mapping_from_data(value: Any, path: str) -> dict[str, Any]:
    result = _metric_from_data(value, path)
    if not isinstance(result, Mapping):
        _error(path, "must encode a mapping")
    return dict(result)


def _metric_from_data(value: Any, path: str) -> Any:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _error(path, "must be finite")
        return value
    if not isinstance(value, Mapping):
        _error(path, f"contains unsupported JSON type {type(value).__name__}")
    raw = _object(value, path)
    if _METRIC_TYPE not in raw:
        _error(path, f"must contain {_METRIC_TYPE!r}")
    tag = _string(raw[_METRIC_TYPE], f"{path}.{_METRIC_TYPE}")
    if tag in {"decimal", "datetime", "date", "money", "diagnostic"}:
        _keys(raw, {_METRIC_TYPE, "value"}, path)
        if tag == "decimal":
            return _decimal(raw["value"], f"{path}.value")
        if tag == "datetime":
            return _datetime(raw["value"], f"{path}.value")
        if tag == "date":
            return _date(raw["value"], f"{path}.value")
        if tag == "money":
            return _required_money(raw["value"], f"{path}.value")
        return _diagnostic_from_dict(raw["value"], f"{path}.value")
    if tag == "tuple":
        _keys(raw, {_METRIC_TYPE, "items"}, path)
        items = _list(raw["items"], f"{path}.items")
        return tuple(
            _metric_from_data(item, f"{path}.items[{index}]")
            for index, item in enumerate(items)
        )
    if tag == "mapping":
        _keys(raw, {_METRIC_TYPE, "items"}, path)
        items = _list(raw["items"], f"{path}.items")
        result: dict[str, Any] = {}
        previous: str | None = None
        for index, item in enumerate(items):
            item_path = f"{path}.items[{index}]"
            pair = _list(item, item_path)
            if len(pair) != 2:
                _error(item_path, "must be a key/value pair")
            key = _string(pair[0], f"{item_path}[0]")
            if key in result:
                _error(item_path, f"contains duplicate key {key!r}")
            if previous is not None and key <= previous:
                _error(item_path, "mapping keys must be strictly sorted")
            result[key] = _metric_from_data(pair[1], f"{path}.{key}")
            previous = key
        return result
    _error(path, f"contains unknown metric type {tag!r}")


def _dumps(value: Mapping[str, JsonValue]) -> str:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise MarketplaceSerializationError(f"Cannot serialize Marketplace data: {exc}") from exc


def _loads(payload: str) -> dict[str, Any]:
    if not isinstance(payload, str):
        raise MarketplaceDeserializationError(
            f"$ must be a JSON string, got {type(payload).__name__}."
        )
    try:
        value = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except MarketplaceDeserializationError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise MarketplaceDeserializationError(f"$ contains invalid JSON: {exc}") from exc
    return _object(value, "$")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MarketplaceDeserializationError(
                f"$ contains duplicate JSON key {key!r}."
            )
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise MarketplaceDeserializationError(
        f"$ contains unsupported non-finite JSON constant {value}."
    )


def _schema_version(value: Any, path: str) -> None:
    if type(value) is not int:
        _error(path, "must be an integer")
    if value != MARKETPLACE_SCHEMA_VERSION:
        _error(path, f"unsupported schema version {value!r}")


def _keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        detail = []
        if missing:
            detail.append(f"missing keys {missing!r}")
        if unknown:
            detail.append(f"unknown keys {unknown!r}")
        _error(path, "; ".join(detail))


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _error(path, "must be an object")
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            _error(path, "object keys must be strings")
        result[key] = item
    return result


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _error(path, "must be a list")
    return value


def _string_tuple(value: Any, path: str) -> tuple[str, ...]:
    items = _list(value, path)
    return tuple(
        _string(item, f"{path}[{index}]") for index, item in enumerate(items)
    )


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _error(path, "must be a string")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    return None if value is None else _string(value, path)


def _integer(value: Any, path: str) -> int:
    if type(value) is not int:
        _error(path, "must be an integer")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _decimal(value: Any, path: str) -> Decimal:
    raw = _string(value, path)
    try:
        result = Decimal(raw)
    except InvalidOperation as exc:
        raise MarketplaceDeserializationError(
            f"{path} is not a valid decimal: {raw!r}."
        ) from exc
    if not result.is_finite():
        _error(path, "must be finite")
    return result


def _datetime(value: Any, path: str) -> datetime:
    raw = _string(value, path)
    try:
        result = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise MarketplaceDeserializationError(
            f"{path} is not a valid ISO-8601 datetime: {raw!r}."
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        _error(path, "must be timezone-aware")
    return result


def _date(value: Any, path: str) -> date:
    raw = _string(value, path)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise MarketplaceDeserializationError(
            f"{path} is not a valid ISO date: {raw!r}."
        ) from exc


def _optional_date(value: Any, path: str) -> date | None:
    return None if value is None else _date(value, path)


def _enum(enum_type: type[Any], value: Any, path: str) -> Any:
    raw = _string(value, path)
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise MarketplaceDeserializationError(
            f"{path} contains unknown {enum_type.__name__} value {raw!r}."
        ) from exc


def _construct(model_type: type[Any], path: str, **values: Any) -> Any:
    try:
        return model_type(**values)
    except (TypeError, ValueError) as exc:
        raise MarketplaceDeserializationError(
            f"{path} is not a valid {model_type.__name__}: {exc}"
        ) from exc


def _error(path: str, message: str) -> NoReturn:
    raise MarketplaceDeserializationError(f"{path} {message}.")


__all__ = [
    "JsonValue",
    "MARKETPLACE_SCHEMA_VERSION",
    "MarketplaceDeserializationError",
    "MarketplaceSerializationError",
    "dumps_marketplace_module_result",
    "dumps_marketplace_snapshot",
    "loads_marketplace_module_result",
    "loads_marketplace_snapshot",
    "marketplace_module_result_from_dict",
    "marketplace_module_result_to_dict",
    "marketplace_snapshot_from_dict",
    "marketplace_snapshot_to_dict",
]
