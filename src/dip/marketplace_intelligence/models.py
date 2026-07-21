"""Immutable foundational contracts for Marketplace Intelligence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Any

from dip.intelligence import IntelligenceResult, IntelligenceStatus


_STABLE_ID = re.compile(r"^[a-z][a-z0-9_-]*$")


class MarketplaceDomainError(ValueError):
    """Raised when Marketplace domain values contradict one another."""


class MarketplaceDataStatus(str, Enum):
    """Availability and completeness of one captured marketplace value set."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class MarketplaceDiagnosticSeverity(str, Enum):
    """Stable severity for a provider-neutral Marketplace diagnostic."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class MarketplaceMoney:
    """An exact non-negative amount in one explicit currency."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if type(self.amount) is not Decimal:
            raise TypeError("amount must be a Decimal.")
        if not self.amount.is_finite():
            raise MarketplaceDomainError("amount must be finite.")
        if self.amount < 0:
            raise MarketplaceDomainError("amount must not be negative.")
        _currency(self.currency)


@dataclass(frozen=True)
class MarketplaceDiagnostic:
    """A structured, provider-neutral explanation of capture quality."""

    code: str
    message: str
    severity: MarketplaceDiagnosticSeverity = MarketplaceDiagnosticSeverity.WARNING
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _stable_identifier(self.code, "code")
        _text(self.message, "message")
        if type(self.severity) is not MarketplaceDiagnosticSeverity:
            raise TypeError("severity must be a MarketplaceDiagnosticSeverity.")
        object.__setattr__(self, "details", _freeze_string_mapping(self.details))


@dataclass(frozen=True)
class MarketplaceListingObservation:
    """One marketplace offer observed at an explicitly supplied time."""

    listing_id: str
    release_id: int
    observed_at: datetime
    price: MarketplaceMoney
    shipping: MarketplaceMoney | None = None
    condition: str | None = None
    seller_region: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.listing_id, "listing_id")
        _positive_integer(self.release_id, "release_id")
        _aware_datetime(self.observed_at, "observed_at")
        if type(self.price) is not MarketplaceMoney:
            raise TypeError("price must be MarketplaceMoney.")
        if self.shipping is not None:
            if type(self.shipping) is not MarketplaceMoney:
                raise TypeError("shipping must be MarketplaceMoney or None.")
            if self.shipping.currency != self.price.currency:
                raise MarketplaceDomainError(
                    "Listing price and shipping must use the same currency."
                )
        _optional_text(self.condition, "condition")
        _optional_text(self.seller_region, "seller_region")


@dataclass(frozen=True)
class MarketplaceReleaseObservation:
    """Supplied release-level marketplace facts from one observation time."""

    release_id: int
    observed_at: datetime
    status: MarketplaceDataStatus
    lowest_price: MarketplaceMoney | None = None
    median_price: MarketplaceMoney | None = None
    highest_price: MarketplaceMoney | None = None
    num_for_sale: int | None = None
    num_wanted: int | None = None
    last_sold: date | None = None
    diagnostics: tuple[MarketplaceDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        _aware_datetime(self.observed_at, "observed_at")
        if type(self.status) is not MarketplaceDataStatus:
            raise TypeError("status must be a MarketplaceDataStatus.")
        prices = (self.lowest_price, self.median_price, self.highest_price)
        for name, value in zip(
            ("lowest_price", "median_price", "highest_price"),
            prices,
            strict=True,
        ):
            if value is not None and type(value) is not MarketplaceMoney:
                raise TypeError(f"{name} must be MarketplaceMoney or None.")
        _matching_price_currencies(prices)
        _ordered_prices(self.lowest_price, self.median_price, self.highest_price)
        _optional_non_negative_integer(self.num_for_sale, "num_for_sale")
        _optional_non_negative_integer(self.num_wanted, "num_wanted")
        if self.last_sold is not None:
            if type(self.last_sold) is not date:
                raise TypeError("last_sold must be a date or None.")
            if self.last_sold > self.observed_at.date():
                raise MarketplaceDomainError(
                    "last_sold cannot follow the observation date."
                )
        diagnostics = _diagnostic_tuple(self.diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)
        _validate_release_status(self, diagnostics)


@dataclass(frozen=True)
class MarketplaceSnapshot:
    """A canonical aggregate captured during one marketplace observation window."""

    snapshot_id: str
    captured_at: datetime
    source: str
    status: MarketplaceDataStatus
    release_observations: tuple[MarketplaceReleaseObservation, ...] = ()
    listing_observations: tuple[MarketplaceListingObservation, ...] = ()
    diagnostics: tuple[MarketplaceDiagnostic, ...] = ()
    source_version: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.snapshot_id, "snapshot_id")
        _aware_datetime(self.captured_at, "captured_at")
        _stable_identifier(self.source, "source")
        if type(self.status) is not MarketplaceDataStatus:
            raise TypeError("status must be a MarketplaceDataStatus.")
        _optional_text(self.source_version, "source_version")

        releases = _release_tuple(self.release_observations)
        listings = _listing_tuple(self.listing_observations)
        diagnostics = _diagnostic_tuple(self.diagnostics)
        object.__setattr__(self, "release_observations", releases)
        object.__setattr__(self, "listing_observations", listings)
        object.__setattr__(self, "diagnostics", diagnostics)

        release_by_id = {value.release_id: value for value in releases}
        captured_key = _datetime_key(self.captured_at)
        for observation in (*releases, *listings):
            if _datetime_key(observation.observed_at) > captured_key:
                raise MarketplaceDomainError(
                    "Snapshot observations cannot follow captured_at."
                )
        for listing in listings:
            release = release_by_id.get(listing.release_id)
            if release is None:
                raise MarketplaceDomainError(
                    "Every listing observation must reference a release observation."
                )
            if release.status not in {
                MarketplaceDataStatus.COMPLETE,
                MarketplaceDataStatus.PARTIAL,
            }:
                raise MarketplaceDomainError(
                    "Listings cannot reference an empty or unavailable release observation."
                )
        _validate_snapshot_status(self, releases, listings, diagnostics)


@dataclass(frozen=True)
class MarketplaceExecutionContext:
    """Stable snapshot references for one future Marketplace module execution."""

    execution_id: str
    snapshot_ids: tuple[str, ...]
    executed_at: datetime

    def __post_init__(self) -> None:
        _identifier(self.execution_id, "execution_id")
        snapshot_ids = _identifier_tuple(self.snapshot_ids, "snapshot_ids")
        if not snapshot_ids:
            raise MarketplaceDomainError(
                "Marketplace execution context requires at least one snapshot ID."
            )
        object.__setattr__(self, "snapshot_ids", snapshot_ids)
        _aware_datetime(self.executed_at, "executed_at")


@dataclass(frozen=True)
class MarketplaceModuleResult:
    """History-ready context paired with the platform's standard module result."""

    context: MarketplaceExecutionContext
    result: IntelligenceResult

    def __post_init__(self) -> None:
        if type(self.context) is not MarketplaceExecutionContext:
            raise TypeError("context must be a MarketplaceExecutionContext.")
        if type(self.result) is not IntelligenceResult:
            raise TypeError("result must be an IntelligenceResult.")
        object.__setattr__(self, "result", _freeze_intelligence_result(self.result))


def _freeze_intelligence_result(result: IntelligenceResult) -> IntelligenceResult:
    _stable_identifier(result.module_id, "result.module_id")
    _optional_text(result.module_version, "result.module_version")
    if type(result.status) is not IntelligenceStatus:
        raise TypeError("result.status must be an IntelligenceStatus.")
    _text(result.summary, "result.summary")
    insights = _string_tuple(result.insights, "result.insights")
    evidence = _string_tuple(result.evidence, "result.evidence")
    diagnostics = _string_tuple(result.diagnostics, "result.diagnostics")
    if not isinstance(result.metrics, Mapping):
        raise TypeError("result.metrics must be a mapping.")
    metrics = _freeze_metric_mapping(result.metrics)
    if result.status is IntelligenceStatus.FAILED:
        if insights or metrics:
            raise MarketplaceDomainError(
                "A failed Marketplace module result cannot contain successful outputs."
            )
        if not diagnostics:
            raise MarketplaceDomainError(
                "A failed Marketplace module result requires diagnostics."
            )
    return IntelligenceResult(
        module_id=result.module_id,
        module_version=result.module_version,
        status=result.status,
        summary=result.summary,
        insights=insights,
        metrics=metrics,
        evidence=evidence,
        diagnostics=diagnostics,
    )


def _freeze_metric_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen: dict[str, Any] = {}
    for key in value:
        if not isinstance(key, str):
            raise TypeError("Marketplace result metric keys must be strings.")
        _identifier(key, "result metric key")
    for key in sorted(value):
        frozen[key] = _freeze_metric_value(value[key])
    return MappingProxyType(frozen)


def _freeze_metric_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_metric_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_metric_value(item) for item in value)
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise MarketplaceDomainError(
                "Marketplace result metrics cannot contain non-finite floats."
            )
        return value
    if type(value) is Decimal:
        if not value.is_finite():
            raise MarketplaceDomainError(
                "Marketplace result metrics cannot contain non-finite decimals."
            )
        return value
    if type(value) is date:
        return value
    if type(value) is datetime:
        _aware_datetime(value, "Marketplace result metric datetime")
        return value
    if type(value) in {MarketplaceMoney, MarketplaceDiagnostic}:
        return value
    raise TypeError(
        "Marketplace result metrics contain unsupported type "
        f"{type(value).__name__}."
    )


def _validate_release_status(
    observation: MarketplaceReleaseObservation,
    diagnostics: tuple[MarketplaceDiagnostic, ...],
) -> None:
    has_facts = any(
        value is not None
        for value in (
            observation.lowest_price,
            observation.median_price,
            observation.highest_price,
            observation.num_for_sale,
            observation.num_wanted,
            observation.last_sold,
        )
    )
    if observation.status is MarketplaceDataStatus.COMPLETE and not has_facts:
        raise MarketplaceDomainError(
            "A complete release observation requires at least one supplied fact."
        )
    if observation.status is MarketplaceDataStatus.PARTIAL:
        if not has_facts or not diagnostics:
            raise MarketplaceDomainError(
                "A partial release observation requires facts and diagnostics."
            )
    if observation.status in {
        MarketplaceDataStatus.EMPTY,
        MarketplaceDataStatus.UNAVAILABLE,
        MarketplaceDataStatus.FAILED,
    } and has_facts:
        raise MarketplaceDomainError(
            f"A {observation.status.value} release observation cannot contain facts."
        )
    if observation.status in {
        MarketplaceDataStatus.UNAVAILABLE,
        MarketplaceDataStatus.FAILED,
    } and not diagnostics:
        raise MarketplaceDomainError(
            f"A {observation.status.value} release observation requires diagnostics."
        )


def _validate_snapshot_status(
    snapshot: MarketplaceSnapshot,
    releases: tuple[MarketplaceReleaseObservation, ...],
    listings: tuple[MarketplaceListingObservation, ...],
    diagnostics: tuple[MarketplaceDiagnostic, ...],
) -> None:
    has_observations = bool(releases or listings)
    if snapshot.status is MarketplaceDataStatus.COMPLETE:
        if not releases:
            raise MarketplaceDomainError(
                "A complete Marketplace snapshot requires release observations."
            )
        invalid = {
            MarketplaceDataStatus.PARTIAL,
            MarketplaceDataStatus.UNAVAILABLE,
            MarketplaceDataStatus.FAILED,
        }
        if any(value.status in invalid for value in releases):
            raise MarketplaceDomainError(
                "A complete snapshot cannot contain incomplete release observations."
            )
    elif snapshot.status is MarketplaceDataStatus.PARTIAL:
        if not has_observations or not diagnostics:
            raise MarketplaceDomainError(
                "A partial Marketplace snapshot requires observations and diagnostics."
            )
    elif snapshot.status in {
        MarketplaceDataStatus.EMPTY,
        MarketplaceDataStatus.UNAVAILABLE,
        MarketplaceDataStatus.FAILED,
    }:
        if has_observations:
            raise MarketplaceDomainError(
                f"A {snapshot.status.value} Marketplace snapshot cannot contain observations."
            )
        if snapshot.status in {
            MarketplaceDataStatus.UNAVAILABLE,
            MarketplaceDataStatus.FAILED,
        } and not diagnostics:
            raise MarketplaceDomainError(
                f"A {snapshot.status.value} Marketplace snapshot requires diagnostics."
            )


def _release_tuple(values: Any) -> tuple[MarketplaceReleaseObservation, ...]:
    result = _typed_tuple(values, MarketplaceReleaseObservation, "release_observations")
    identifiers = tuple(value.release_id for value in result)
    _unique(identifiers, "release observation IDs")
    return tuple(sorted(result, key=lambda value: value.release_id))


def _listing_tuple(values: Any) -> tuple[MarketplaceListingObservation, ...]:
    result = _typed_tuple(values, MarketplaceListingObservation, "listing_observations")
    identifiers = tuple(value.listing_id for value in result)
    _unique(identifiers, "listing observation IDs")
    return tuple(sorted(result, key=lambda value: (value.release_id, value.listing_id)))


def _diagnostic_tuple(values: Any) -> tuple[MarketplaceDiagnostic, ...]:
    return _typed_tuple(values, MarketplaceDiagnostic, "diagnostics")


def _typed_tuple(values: Any, value_type: type[Any], name: str) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    if any(type(value) is not value_type for value in result):
        raise TypeError(f"{name} contains an unsupported value.")
    return result


def _identifier_tuple(values: Any, name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection of identifiers.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection of identifiers.") from exc
    for value in result:
        _identifier(value, f"{name} item")
    _unique(result, name)
    return result


def _string_tuple(values: Any, name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection of strings.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection of strings.") from exc
    for value in result:
        _text(value, f"{name} item")
    return result


def _freeze_string_mapping(value: Any) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise TypeError("details must be a mapping of strings.")
    frozen: dict[str, str] = {}
    for key in value:
        _stable_identifier(key, "details key")
        _text(value[key], f"details[{key!r}]")
    for key in sorted(value):
        frozen[key] = value[key]
    return MappingProxyType(frozen)


def _matching_price_currencies(
    values: tuple[MarketplaceMoney | None, ...],
) -> None:
    currencies = {value.currency for value in values if value is not None}
    if len(currencies) > 1:
        raise MarketplaceDomainError(
            "Release-level prices must use one currency; no conversion is implicit."
        )


def _ordered_prices(
    lowest: MarketplaceMoney | None,
    median: MarketplaceMoney | None,
    highest: MarketplaceMoney | None,
) -> None:
    pairs = ((lowest, median), (median, highest), (lowest, highest))
    if any(
        left is not None and right is not None and left.amount > right.amount
        for left, right in pairs
    ):
        raise MarketplaceDomainError(
            "Supplied lowest, median and highest prices must be ordered."
        )


def _aware_datetime(value: Any, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarketplaceDomainError(f"{name} must be timezone-aware.")


def _datetime_key(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _currency(value: Any) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 3
        or not value.isascii()
        or not value.isalpha()
        or value != value.upper()
    ):
        raise MarketplaceDomainError(
            "currency must be an uppercase three-letter identifier."
        )


def _positive_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise MarketplaceDomainError(f"{name} must be positive.")


def _optional_non_negative_integer(value: Any, name: str) -> None:
    if value is None:
        return
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer or None.")
    if value < 0:
        raise MarketplaceDomainError(f"{name} must not be negative.")


def _identifier(value: Any, name: str) -> None:
    _text(value, name)


def _stable_identifier(value: Any, name: str) -> None:
    _text(value, name)
    if _STABLE_ID.fullmatch(value) is None:
        raise MarketplaceDomainError(
            f"{name} must be a lowercase stable identifier."
        )


def _optional_text(value: Any, name: str) -> None:
    if value is not None:
        _text(value, name)


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise MarketplaceDomainError(f"{name} must be non-empty and trimmed.")


def _unique(values: tuple[Any, ...], name: str) -> None:
    if len(set(values)) != len(values):
        raise MarketplaceDomainError(f"{name} must be unique.")


__all__ = [
    "MarketplaceDataStatus",
    "MarketplaceDiagnostic",
    "MarketplaceDiagnosticSeverity",
    "MarketplaceDomainError",
    "MarketplaceExecutionContext",
    "MarketplaceListingObservation",
    "MarketplaceModuleResult",
    "MarketplaceMoney",
    "MarketplaceReleaseObservation",
    "MarketplaceSnapshot",
]
