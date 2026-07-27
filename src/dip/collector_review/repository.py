"""Storage-independent collector-review repository contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import math
from typing import Protocol

from .models import (
    NewWeekendReviewQueueEntry,
    QueueAddResult,
    WeekendReviewQueueItem,
    WeekendReviewStatus,
)


class CollectorReviewPersistenceError(RuntimeError):
    """Raised when collector-review persistence cannot complete safely."""


class CollectorReviewIntegrityError(RuntimeError):
    """Raised when stored collector-review state is malformed."""


@dataclass(frozen=True)
class HotNowCalculatedState:
    """One exact stored Hot-now score and its optional legacy origin."""

    release_id: int
    artist: str
    title: str
    calculated_at: datetime
    value_score: float
    demand_score: float
    liquidity_score: float
    momentum_score: float
    opportunity_score: float
    sell_window: str
    priority: str
    explanation: str
    legacy_snapshot_id: int | None
    legacy_analysis_run_id: int | None
    legacy_analysis_run_status: str | None
    legacy_captured_at: datetime | None
    wants: int | None
    haves: int | None
    copies_for_sale: int | None
    lowest_price: Decimal | None
    currency: str | None
    discogs_uri: str | None

    def __post_init__(self) -> None:
        if type(self.release_id) is not int:
            raise TypeError("release_id must be an integer.")
        if self.release_id <= 0:
            raise ValueError("release_id must be positive.")
        if type(self.calculated_at) is not datetime:
            raise TypeError("calculated_at must be a datetime.")
        if (
            self.calculated_at.tzinfo is None
            or self.calculated_at.utcoffset() is None
        ):
            raise ValueError("calculated_at must be timezone-aware.")
        for name in (
            "value_score",
            "demand_score",
            "liquidity_score",
            "momentum_score",
            "opportunity_score",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric.")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite.")
        if self.sell_window != "Hot now":
            raise ValueError("Calculated state must be classified as Hot now.")
        for name in ("artist", "title", "priority", "explanation"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} must be a string.")
        for name in ("legacy_snapshot_id", "legacy_analysis_run_id"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive integer or None.")
        if self.legacy_analysis_run_status is not None and not isinstance(
            self.legacy_analysis_run_status, str
        ):
            raise TypeError(
                "legacy_analysis_run_status must be a string or None."
            )
        if self.legacy_captured_at is not None:
            if type(self.legacy_captured_at) is not datetime:
                raise TypeError("legacy_captured_at must be a datetime or None.")
            if (
                self.legacy_captured_at.tzinfo is None
                or self.legacy_captured_at.utcoffset() is None
            ):
                raise ValueError(
                    "legacy_captured_at must be timezone-aware."
                )
        for name in ("wants", "haves", "copies_for_sale"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a non-negative integer or None.")
        if self.lowest_price is not None:
            if type(self.lowest_price) is not Decimal:
                raise TypeError("lowest_price must be a Decimal or None.")
            if not self.lowest_price.is_finite() or self.lowest_price < 0:
                raise ValueError("lowest_price must be finite and non-negative.")
        for name in ("currency", "discogs_uri"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{name} must be a string or None.")


class HotNowCalculatedStateRepository(Protocol):
    """Read only the calculated rows already classified as Hot now."""

    def list_hot_now(self) -> tuple[HotNowCalculatedState, ...]: ...


class WeekendReviewQueueRepository(Protocol):
    """Narrow durable queue lifecycle operations."""

    def add_or_get_existing(
        self,
        entry: NewWeekendReviewQueueEntry,
    ) -> QueueAddResult: ...

    def get_by_id(
        self,
        queue_item_id: int,
    ) -> WeekendReviewQueueItem | None: ...

    def get_by_release_id(
        self,
        release_id: int,
    ) -> WeekendReviewQueueItem | None: ...

    def list_queue(
        self,
        statuses: tuple[WeekendReviewStatus, ...] | None = None,
    ) -> tuple[WeekendReviewQueueItem, ...]: ...

    def save(
        self,
        item: WeekendReviewQueueItem,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem: ...

    def delete(
        self,
        queue_item_id: int,
        *,
        expected_updated_at: datetime,
    ) -> WeekendReviewQueueItem: ...


__all__ = [
    "CollectorReviewIntegrityError",
    "CollectorReviewPersistenceError",
    "HotNowCalculatedState",
    "HotNowCalculatedStateRepository",
    "WeekendReviewQueueRepository",
]
