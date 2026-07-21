"""Immutable presentation models for the Weekend Listings experience."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceMoney,
    WeekendWindow,
)


class WeekendListingsDetailConsistencyError(ValueError):
    """Raised when Weekend Listings presentation values contradict one another."""


class WeekendListingsDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class WeekendListingViewModel:
    """One factual listing copied from typed module output."""

    listing_id: str
    release_id: int
    observed_at: datetime
    price: MarketplaceMoney
    shipping: MarketplaceMoney | None
    artist: str | None
    title: str | None
    condition: str | None
    seller_region: str | None
    inclusion_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.listing_id, "listing_id")
        _positive_integer(self.release_id, "release_id")
        _aware_datetime(self.observed_at, "observed_at")
        if type(self.price) is not MarketplaceMoney:
            raise TypeError("price must be MarketplaceMoney.")
        if self.shipping is not None and type(self.shipping) is not MarketplaceMoney:
            raise TypeError("shipping must be MarketplaceMoney or None.")
        for name, value in (
            ("artist", self.artist),
            ("title", self.title),
            ("condition", self.condition),
            ("seller_region", self.seller_region),
        ):
            if value is not None:
                _text(value, name)
        evidence = _string_tuple(self.inclusion_evidence, "inclusion_evidence")
        if not evidence:
            raise WeekendListingsDetailConsistencyError(
                "A Weekend Listing requires inclusion evidence."
            )
        object.__setattr__(self, "inclusion_evidence", evidence)

    @property
    def has_missing_optional_evidence(self) -> bool:
        return any(
            value is None
            for value in (
                self.shipping,
                self.artist,
                self.title,
                self.condition,
                self.seller_region,
            )
        )


@dataclass(frozen=True)
class WeekendListingsDetailViewModel:
    """Complete read-only detail state for the Explorer destination."""

    state: WeekendListingsDetailState
    summary: str
    window: WeekendWindow | None = None
    snapshot_id: str | None = None
    snapshot_status: MarketplaceDataStatus | None = None
    candidate_count: int | None = None
    candidates: tuple[WeekendListingViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Weekend Listings")

    def __post_init__(self) -> None:
        if type(self.state) is not WeekendListingsDetailState:
            raise TypeError("state must be a WeekendListingsDetailState.")
        _text(self.summary, "summary")
        if self.window is not None and type(self.window) is not WeekendWindow:
            raise TypeError("window must be WeekendWindow or None.")
        if (self.snapshot_id is None) != (self.snapshot_status is None):
            raise WeekendListingsDetailConsistencyError(
                "Snapshot ID and status must be available together."
            )
        if self.snapshot_id is not None:
            _text(self.snapshot_id, "snapshot_id")
        if self.snapshot_status is not None and type(
            self.snapshot_status
        ) is not MarketplaceDataStatus:
            raise TypeError("snapshot_status must be MarketplaceDataStatus or None.")
        count = _optional_count(self.candidate_count)
        candidates = _candidate_tuple(self.candidates)
        diagnostics = _string_tuple(self.diagnostics, "diagnostics")

        if self.state is WeekendListingsDetailState.LOADING:
            if (
                self.window is not None
                or self.snapshot_id is not None
                or count is not None
                or candidates
            ):
                raise WeekendListingsDetailConsistencyError(
                    "Loading detail cannot contain result context."
                )
        elif self.state is WeekendListingsDetailState.UNAVAILABLE:
            if candidates or count not in {None, 0}:
                raise WeekendListingsDetailConsistencyError(
                    "Unavailable detail cannot contain candidates."
                )
            if self.window is None and (
                self.snapshot_id is not None or count is not None
            ):
                raise WeekendListingsDetailConsistencyError(
                    "Unavailable result context requires its weekend window."
                )
            if self.window is not None and count != 0:
                raise WeekendListingsDetailConsistencyError(
                    "An unavailable result requires a zero candidate count."
                )
        elif self.state in {
            WeekendListingsDetailState.ERROR,
            WeekendListingsDetailState.INSUFFICIENT_DATA,
        }:
            if self.window is None or count != 0 or candidates:
                raise WeekendListingsDetailConsistencyError(
                    "Error or insufficient detail requires a window and no candidates."
                )
        elif self.state is WeekendListingsDetailState.EMPTY:
            if (
                self.window is None
                or self.snapshot_id is None
                or count != 0
                or candidates
            ):
                raise WeekendListingsDetailConsistencyError(
                    "Empty detail requires source context and a zero candidate count."
                )
        else:
            if (
                self.window is None
                or self.snapshot_id is None
                or count is None
                or count <= 0
                or count != len(candidates)
            ):
                raise WeekendListingsDetailConsistencyError(
                    "Available detail requires context and its complete candidate list."
                )
            has_missing = any(
                candidate.has_missing_optional_evidence for candidate in candidates
            )
            source_partial = self.snapshot_status is MarketplaceDataStatus.PARTIAL
            expected_partial = has_missing or source_partial or bool(diagnostics)
            if expected_partial != (self.state is WeekendListingsDetailState.PARTIAL):
                raise WeekendListingsDetailConsistencyError(
                    "Partial state does not match source or evidence completeness."
                )

        object.__setattr__(self, "candidate_count", count)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "diagnostics", diagnostics)

    @classmethod
    def loading(cls) -> "WeekendListingsDetailViewModel":
        return cls(
            WeekendListingsDetailState.LOADING,
            "Weekend Listings are loading.",
        )

    @classmethod
    def unavailable(cls) -> "WeekendListingsDetailViewModel":
        return cls(
            WeekendListingsDetailState.UNAVAILABLE,
            "No Weekend Listings result was supplied to this Explorer workspace.",
        )


def _candidate_tuple(values: Any) -> tuple[WeekendListingViewModel, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("candidates must be a collection.")
    try:
        candidates = tuple(values)
    except TypeError as exc:
        raise TypeError("candidates must be a collection.") from exc
    if any(type(value) is not WeekendListingViewModel for value in candidates):
        raise TypeError("candidates contain an unsupported value.")
    identifiers = tuple(value.listing_id for value in candidates)
    if len(set(identifiers)) != len(identifiers):
        raise WeekendListingsDetailConsistencyError(
            "Weekend Listing identifiers must be unique."
        )
    if candidates != _ordered_candidates(candidates):
        raise WeekendListingsDetailConsistencyError(
            "Weekend Listings must preserve canonical module order."
        )
    return candidates


def _ordered_candidates(
    values: tuple[WeekendListingViewModel, ...],
) -> tuple[WeekendListingViewModel, ...]:
    by_identity = sorted(values, key=lambda value: (value.release_id, value.listing_id))
    return tuple(
        sorted(
            by_identity,
            key=lambda value: value.observed_at.astimezone(timezone.utc),
            reverse=True,
        )
    )


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


def _optional_count(value: Any) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError("candidate_count must be an integer or None.")
    if value < 0:
        raise ValueError("candidate_count must not be negative.")
    return value


def _positive_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


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
    "WeekendListingViewModel",
    "WeekendListingsDetailConsistencyError",
    "WeekendListingsDetailState",
    "WeekendListingsDetailViewModel",
]
