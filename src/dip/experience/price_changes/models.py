"""Immutable presentation models for the Price Changes experience."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from dip.marketplace_intelligence import (
    ListingPriceChangeKind,
    MarketplaceDataStatus,
    MarketplaceMoney,
    PriceChangeDelta,
    PriceChangesComparisonState,
    ReleasePriceChangeKind,
    ReleasePriceMetric,
)


class PriceChangesDetailConsistencyError(ValueError):
    """Raised when Price Changes presentation values contradict one another."""


class PriceChangesDetailState(str, Enum):
    """Explicit availability state for the Price Changes destination."""

    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class PriceChangesSnapshotViewModel:
    """One immutable snapshot reference copied from typed module output."""

    snapshot_id: str
    captured_at: datetime
    source: str
    status: MarketplaceDataStatus
    source_version: str | None = None

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        _aware_datetime(self.captured_at, "captured_at")
        _text(self.source, "source")
        if type(self.status) is not MarketplaceDataStatus:
            raise TypeError("status must be a MarketplaceDataStatus.")
        if self.source_version is not None:
            _text(self.source_version, "source_version")


@dataclass(frozen=True)
class ListingPriceChangeViewModel:
    """One factual listing-price change copied without reclassification."""

    listing_id: str
    release_id: int
    change_kind: ListingPriceChangeKind
    previous_price: MarketplaceMoney | None
    latest_price: MarketplaceMoney | None
    delta: PriceChangeDelta | None
    previous_observed_at: datetime | None
    latest_observed_at: datetime | None
    previous_snapshot_id: str
    latest_snapshot_id: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.listing_id, "listing_id")
        _positive_integer(self.release_id, "release_id")
        if type(self.change_kind) is not ListingPriceChangeKind:
            raise TypeError("change_kind must be a ListingPriceChangeKind.")
        _optional_money(self.previous_price, "previous_price")
        _optional_money(self.latest_price, "latest_price")
        _optional_delta(self.delta)
        _optional_aware_datetime(self.previous_observed_at, "previous_observed_at")
        _optional_aware_datetime(self.latest_observed_at, "latest_observed_at")
        if self.previous_observed_at is None and self.latest_observed_at is None:
            raise PriceChangesDetailConsistencyError(
                "A listing change requires an observation timestamp."
            )
        _text(self.previous_snapshot_id, "previous_snapshot_id")
        _text(self.latest_snapshot_id, "latest_snapshot_id")
        evidence = _string_tuple(self.evidence, "evidence")
        if not evidence:
            raise PriceChangesDetailConsistencyError(
                "A listing change requires factual evidence."
            )
        object.__setattr__(self, "evidence", evidence)
        _validate_listing_change_shape(self)

    @property
    def relevant_observed_at(self) -> datetime:
        """Return the timestamp already selected by the documented ordering rule."""

        return self.latest_observed_at or self.previous_observed_at  # type: ignore[return-value]


@dataclass(frozen=True)
class ReleasePriceChangeViewModel:
    """One supplied release-level monetary fact copied from module output."""

    release_id: int
    metric: ReleasePriceMetric
    change_kind: ReleasePriceChangeKind
    previous_value: MarketplaceMoney | None
    latest_value: MarketplaceMoney | None
    delta: PriceChangeDelta | None
    previous_snapshot_id: str
    latest_snapshot_id: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        if type(self.metric) is not ReleasePriceMetric:
            raise TypeError("metric must be a ReleasePriceMetric.")
        if type(self.change_kind) is not ReleasePriceChangeKind:
            raise TypeError("change_kind must be a ReleasePriceChangeKind.")
        _optional_money(self.previous_value, "previous_value")
        _optional_money(self.latest_value, "latest_value")
        _optional_delta(self.delta)
        _text(self.previous_snapshot_id, "previous_snapshot_id")
        _text(self.latest_snapshot_id, "latest_snapshot_id")
        evidence = _string_tuple(self.evidence, "evidence")
        if not evidence:
            raise PriceChangesDetailConsistencyError(
                "A release change requires factual evidence."
            )
        object.__setattr__(self, "evidence", evidence)
        _validate_release_change_shape(self)


@dataclass(frozen=True)
class PriceChangesDetailViewModel:
    """Complete read-only detail state for the Price Changes destination."""

    state: PriceChangesDetailState
    summary: str
    comparison_state: PriceChangesComparisonState | None = None
    previous_snapshot: PriceChangesSnapshotViewModel | None = None
    latest_snapshot: PriceChangesSnapshotViewModel | None = None
    source: str | None = None
    listing_change_count: int | None = None
    release_change_count: int | None = None
    unchanged_count: int | None = None
    incomparable_count: int | None = None
    listing_changes: tuple[ListingPriceChangeViewModel, ...] = ()
    release_changes: tuple[ReleasePriceChangeViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Price Changes")

    def __post_init__(self) -> None:
        if type(self.state) is not PriceChangesDetailState:
            raise TypeError("state must be a PriceChangesDetailState.")
        _text(self.summary, "summary")
        if self.comparison_state is not None and type(
            self.comparison_state
        ) is not PriceChangesComparisonState:
            raise TypeError(
                "comparison_state must be a PriceChangesComparisonState or None."
            )
        for name, snapshot in (
            ("previous_snapshot", self.previous_snapshot),
            ("latest_snapshot", self.latest_snapshot),
        ):
            if snapshot is not None and type(snapshot) is not PriceChangesSnapshotViewModel:
                raise TypeError(f"{name} must be a PriceChangesSnapshotViewModel or None.")
        if self.source is not None:
            _text(self.source, "source")

        listing_count = _optional_count(
            self.listing_change_count,
            "listing_change_count",
        )
        release_count = _optional_count(
            self.release_change_count,
            "release_change_count",
        )
        unchanged_count = _optional_count(self.unchanged_count, "unchanged_count")
        incomparable_count = _optional_count(
            self.incomparable_count,
            "incomparable_count",
        )
        listing_changes = _listing_change_tuple(self.listing_changes)
        release_changes = _release_change_tuple(self.release_changes)
        diagnostics = _string_tuple(self.diagnostics, "diagnostics")

        if self.state in {
            PriceChangesDetailState.LOADING,
            PriceChangesDetailState.UNAVAILABLE,
        }:
            if (
                self.comparison_state is not None
                or self.previous_snapshot is not None
                or self.latest_snapshot is not None
                or self.source is not None
                or any(
                    value is not None
                    for value in (
                        listing_count,
                        release_count,
                        unchanged_count,
                        incomparable_count,
                    )
                )
                or listing_changes
                or release_changes
            ):
                raise PriceChangesDetailConsistencyError(
                    "Loading or unavailable detail cannot contain result context."
                )
        else:
            if self.comparison_state is None or any(
                value is None
                for value in (
                    listing_count,
                    release_count,
                    unchanged_count,
                    incomparable_count,
                )
            ):
                raise PriceChangesDetailConsistencyError(
                    "A supplied result requires comparison state and summary counts."
                )
            if listing_count != len(listing_changes):
                raise PriceChangesDetailConsistencyError(
                    "listing_change_count must match the complete listing-change list."
                )
            if release_count != len(release_changes):
                raise PriceChangesDetailConsistencyError(
                    "release_change_count must match the complete release-change list."
                )
            actual_incomparable_count = sum(
                value.change_kind is ListingPriceChangeKind.INCOMPARABLE
                for value in listing_changes
            ) + sum(
                value.change_kind is ReleasePriceChangeKind.INCOMPARABLE
                for value in release_changes
            )
            if incomparable_count != actual_incomparable_count:
                raise PriceChangesDetailConsistencyError(
                    "incomparable_count must match the detailed incomparable changes."
                )
            _validate_result_state(self)

        object.__setattr__(self, "listing_change_count", listing_count)
        object.__setattr__(self, "release_change_count", release_count)
        object.__setattr__(self, "unchanged_count", unchanged_count)
        object.__setattr__(self, "incomparable_count", incomparable_count)
        object.__setattr__(self, "listing_changes", listing_changes)
        object.__setattr__(self, "release_changes", release_changes)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def message(self) -> str:
        """Expose the factual result explanation used by the renderer."""

        return self.summary

    @property
    def previous_captured_at(self) -> datetime | None:
        return (
            None
            if self.previous_snapshot is None
            else self.previous_snapshot.captured_at
        )

    @property
    def latest_captured_at(self) -> datetime | None:
        return (
            None if self.latest_snapshot is None else self.latest_snapshot.captured_at
        )

    @classmethod
    def loading(cls) -> "PriceChangesDetailViewModel":
        return cls(
            PriceChangesDetailState.LOADING,
            "Price Changes are loading.",
        )

    @classmethod
    def unavailable(cls) -> "PriceChangesDetailViewModel":
        return cls(
            PriceChangesDetailState.UNAVAILABLE,
            "No Price Changes result was supplied to this Explorer workspace.",
        )


def _validate_result_state(detail: PriceChangesDetailViewModel) -> None:
    expected = {
        PriceChangesComparisonState.COMPLETE: (
            PriceChangesDetailState.AVAILABLE
            if (detail.listing_changes or detail.release_changes)
            else PriceChangesDetailState.EMPTY
        ),
        PriceChangesComparisonState.PARTIAL: PriceChangesDetailState.PARTIAL,
        PriceChangesComparisonState.INSUFFICIENT_HISTORY: (
            PriceChangesDetailState.INSUFFICIENT_HISTORY
        ),
        PriceChangesComparisonState.INSUFFICIENT_DATA: (
            PriceChangesDetailState.INSUFFICIENT_DATA
        ),
        PriceChangesComparisonState.FAILED: PriceChangesDetailState.ERROR,
    }[detail.comparison_state]
    if detail.state is not expected:
        raise PriceChangesDetailConsistencyError(
            "Price Changes state contradicts the typed comparison state."
        )

    if detail.state in {
        PriceChangesDetailState.INSUFFICIENT_HISTORY,
        PriceChangesDetailState.INSUFFICIENT_DATA,
        PriceChangesDetailState.ERROR,
    } and any(
        value != 0
        for value in (
            detail.listing_change_count,
            detail.release_change_count,
            detail.unchanged_count,
            detail.incomparable_count,
        )
    ):
        raise PriceChangesDetailConsistencyError(
            "An unsuccessful comparison requires zero summary counts."
        )

    has_both_snapshots = (
        detail.previous_snapshot is not None and detail.latest_snapshot is not None
    )
    if has_both_snapshots:
        if detail.previous_snapshot.snapshot_id == detail.latest_snapshot.snapshot_id:
            raise PriceChangesDetailConsistencyError(
                "Previous and latest snapshot IDs must differ."
            )
        if detail.previous_snapshot.captured_at.astimezone(timezone.utc) > (
            detail.latest_snapshot.captured_at.astimezone(timezone.utc)
        ):
            raise PriceChangesDetailConsistencyError(
                "Previous snapshot capture time cannot follow the latest snapshot."
            )
    if detail.state in {
        PriceChangesDetailState.AVAILABLE,
        PriceChangesDetailState.PARTIAL,
        PriceChangesDetailState.EMPTY,
    }:
        if not has_both_snapshots or detail.source is None:
            raise PriceChangesDetailConsistencyError(
                "A comparable Price Changes result requires both snapshot contexts and source."
            )
        if (
            detail.previous_snapshot.source != detail.source
            or detail.latest_snapshot.source != detail.source
        ):
            raise PriceChangesDetailConsistencyError(
                "Successful snapshot contexts must match the comparison source."
            )
        if detail.previous_snapshot.captured_at.astimezone(timezone.utc) >= (
            detail.latest_snapshot.captured_at.astimezone(timezone.utc)
        ):
            raise PriceChangesDetailConsistencyError(
                "A successful comparison requires an earlier previous snapshot."
            )
    if detail.state is PriceChangesDetailState.INSUFFICIENT_HISTORY:
        if (
            detail.previous_snapshot is not None
            or detail.listing_changes
            or detail.release_changes
        ):
            raise PriceChangesDetailConsistencyError(
                "Insufficient history cannot contain a previous snapshot or changes."
            )
        expected_source = (
            None
            if detail.latest_snapshot is None
            else detail.latest_snapshot.source
        )
        if detail.source != expected_source:
            raise PriceChangesDetailConsistencyError(
                "Insufficient-history source must match its latest snapshot."
            )
    if detail.state in {
        PriceChangesDetailState.INSUFFICIENT_DATA,
        PriceChangesDetailState.ERROR,
    }:
        if not has_both_snapshots:
            raise PriceChangesDetailConsistencyError(
                "An unsuccessful comparison requires both supplied snapshot contexts."
            )
        if detail.listing_changes or detail.release_changes:
            raise PriceChangesDetailConsistencyError(
                "An unsuccessful comparison cannot contain price changes."
            )
        previous_source = detail.previous_snapshot.source
        latest_source = detail.latest_snapshot.source
        expected_source = previous_source if previous_source == latest_source else None
        if detail.source != expected_source:
            raise PriceChangesDetailConsistencyError(
                "Comparison source must match both supplied snapshot contexts."
            )

    if has_both_snapshots:
        previous_id = detail.previous_snapshot.snapshot_id
        latest_id = detail.latest_snapshot.snapshot_id
        for change in (*detail.listing_changes, *detail.release_changes):
            if (
                change.previous_snapshot_id != previous_id
                or change.latest_snapshot_id != latest_id
            ):
                raise PriceChangesDetailConsistencyError(
                    "Price change snapshot references must match the comparison context."
                )


def _validate_listing_change_shape(value: ListingPriceChangeViewModel) -> None:
    if value.change_kind is ListingPriceChangeKind.NEWLY_OBSERVED:
        if (
            value.previous_price is not None
            or value.previous_observed_at is not None
            or value.latest_price is None
            or value.latest_observed_at is None
            or value.delta is not None
        ):
            raise PriceChangesDetailConsistencyError(
                "A newly observed listing requires only latest price evidence."
            )
        return
    if value.change_kind is ListingPriceChangeKind.NO_LONGER_OBSERVED:
        if (
            value.previous_price is None
            or value.previous_observed_at is None
            or value.latest_price is not None
            or value.latest_observed_at is not None
            or value.delta is not None
        ):
            raise PriceChangesDetailConsistencyError(
                "A no-longer-observed listing requires only previous price evidence."
            )
        return
    if (
        value.previous_price is None
        or value.latest_price is None
        or value.previous_observed_at is None
        or value.latest_observed_at is None
    ):
        raise PriceChangesDetailConsistencyError(
            "A continuing listing change requires previous and latest evidence."
        )
    if value.change_kind is ListingPriceChangeKind.INCOMPARABLE:
        if value.delta is not None:
            raise PriceChangesDetailConsistencyError(
                "An incomparable listing cannot contain a delta."
            )
        if value.previous_price.currency == value.latest_price.currency:
            raise PriceChangesDetailConsistencyError(
                "An incomparable listing requires differing currencies."
            )
        return
    _validate_direction_delta(
        value.previous_price,
        value.latest_price,
        value.delta,
        increased=value.change_kind is ListingPriceChangeKind.INCREASED,
    )


def _validate_release_change_shape(value: ReleasePriceChangeViewModel) -> None:
    if value.change_kind is ReleasePriceChangeKind.NEWLY_AVAILABLE:
        if (
            value.previous_value is not None
            or value.latest_value is None
            or value.delta is not None
        ):
            raise PriceChangesDetailConsistencyError(
                "A newly available release price requires only a latest value."
            )
        return
    if value.change_kind is ReleasePriceChangeKind.NO_LONGER_AVAILABLE:
        if (
            value.previous_value is None
            or value.latest_value is not None
            or value.delta is not None
        ):
            raise PriceChangesDetailConsistencyError(
                "A no-longer-available release price requires only a previous value."
            )
        return
    if value.previous_value is None or value.latest_value is None:
        raise PriceChangesDetailConsistencyError(
            "A continuing release price change requires previous and latest values."
        )
    if value.change_kind is ReleasePriceChangeKind.INCOMPARABLE:
        if value.delta is not None:
            raise PriceChangesDetailConsistencyError(
                "An incomparable release price cannot contain a delta."
            )
        if value.previous_value.currency == value.latest_value.currency:
            raise PriceChangesDetailConsistencyError(
                "An incomparable release price requires differing currencies."
            )
        return
    _validate_direction_delta(
        value.previous_value,
        value.latest_value,
        value.delta,
        increased=value.change_kind is ReleasePriceChangeKind.INCREASED,
    )


def _validate_direction_delta(
    previous: MarketplaceMoney,
    latest: MarketplaceMoney,
    delta: PriceChangeDelta | None,
    *,
    increased: bool,
) -> None:
    if previous.currency != latest.currency:
        raise PriceChangesDetailConsistencyError(
            "A comparable price change requires matching currencies."
        )
    if delta is None or delta.currency != latest.currency:
        raise PriceChangesDetailConsistencyError(
            "A comparable price change requires a same-currency delta."
        )
    if (increased and delta.amount <= 0) or (
        not increased and delta.amount >= 0
    ):
        raise PriceChangesDetailConsistencyError(
            "Delta sign contradicts the supplied price-change direction."
        )


def _listing_change_tuple(values: Any) -> tuple[ListingPriceChangeViewModel, ...]:
    changes = _typed_tuple(values, ListingPriceChangeViewModel, "listing_changes")
    identities = tuple((value.release_id, value.listing_id) for value in changes)
    if len(set(identities)) != len(identities):
        raise PriceChangesDetailConsistencyError(
            "Listing price-change identities must be unique."
        )
    for previous, latest in zip(changes, changes[1:]):
        previous_time = previous.relevant_observed_at.astimezone(timezone.utc)
        latest_time = latest.relevant_observed_at.astimezone(timezone.utc)
        if previous_time < latest_time or (
            previous_time == latest_time
            and (previous.release_id, previous.listing_id)
            > (latest.release_id, latest.listing_id)
        ):
            raise PriceChangesDetailConsistencyError(
                "Listing price changes must preserve canonical module order."
            )
    return changes


def _release_change_tuple(values: Any) -> tuple[ReleasePriceChangeViewModel, ...]:
    changes = _typed_tuple(values, ReleasePriceChangeViewModel, "release_changes")
    identities = tuple((value.release_id, value.metric) for value in changes)
    if len(set(identities)) != len(identities):
        raise PriceChangesDetailConsistencyError(
            "Release price-change identities must be unique."
        )
    metric_order = {value: position for position, value in enumerate(ReleasePriceMetric)}
    for previous, latest in zip(changes, changes[1:]):
        if (previous.release_id, metric_order[previous.metric]) > (
            latest.release_id,
            metric_order[latest.metric],
        ):
            raise PriceChangesDetailConsistencyError(
                "Release price changes must preserve canonical module order."
            )
    return changes


def _typed_tuple(values: Any, expected: type[Any], name: str) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    if any(type(value) is not expected for value in result):
        raise TypeError(f"{name} contain an unsupported value.")
    return result


def _string_tuple(values: Any, name: str) -> tuple[str, ...]:
    result = _typed_tuple(values, str, name)
    for value in result:
        _text(value, f"{name} item")
    return result


def _optional_count(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer or None.")
    if value < 0:
        raise ValueError(f"{name} must not be negative.")
    return value


def _positive_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _optional_money(value: Any, name: str) -> None:
    if value is not None and type(value) is not MarketplaceMoney:
        raise TypeError(f"{name} must be MarketplaceMoney or None.")


def _optional_delta(value: Any) -> None:
    if value is not None and type(value) is not PriceChangeDelta:
        raise TypeError("delta must be PriceChangeDelta or None.")


def _optional_aware_datetime(value: Any, name: str) -> None:
    if value is not None:
        _aware_datetime(value, name)


def _aware_datetime(value: Any, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and trimmed.")


__all__ = [
    "ListingPriceChangeViewModel",
    "PriceChangesDetailConsistencyError",
    "PriceChangesDetailState",
    "PriceChangesDetailViewModel",
    "PriceChangesSnapshotViewModel",
    "ReleasePriceChangeViewModel",
]
