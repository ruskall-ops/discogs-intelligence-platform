"""Deterministic Weekend Listings intelligence over a supplied snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from types import MappingProxyType
from typing import Any, ClassVar

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from .models import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceMoney,
    MarketplaceSnapshot,
)


_COLLECTION_EVIDENCE = "Release is present in the supplied collection."
_WINDOW_EVIDENCE = "Listing was observed within the supplied weekend window."
_SOURCE_EVIDENCE = "Source snapshot permitted listing evaluation."
_INCLUSION_EVIDENCE = (
    _COLLECTION_EVIDENCE,
    _WINDOW_EVIDENCE,
    _SOURCE_EVIDENCE,
)


class WeekendListingsDomainError(ValueError):
    """Raised when Weekend Listings values contradict the defined contract."""


@dataclass(frozen=True)
class WeekendWindow:
    """A strict local Saturday-to-Monday observation window."""

    start: datetime
    end: datetime
    maximum_duration: ClassVar[timedelta] = timedelta(hours=49)

    def __post_init__(self) -> None:
        _aware_datetime(self.start, "start")
        _aware_datetime(self.end, "end")
        if self.start.tzinfo != self.end.tzinfo:
            raise WeekendListingsDomainError(
                "Weekend window boundaries must use the same timezone."
            )
        if _utc(self.end) <= _utc(self.start):
            raise WeekendListingsDomainError("Weekend window end must follow start.")
        if self.start.weekday() != 5 or self.start.timetz().replace(tzinfo=None) != time():
            raise WeekendListingsDomainError(
                "Weekend window start must be Saturday at 00:00."
            )
        if self.end.weekday() != 0 or self.end.timetz().replace(tzinfo=None) != time():
            raise WeekendListingsDomainError(
                "Weekend window end must be Monday at 00:00."
            )
        if self.end.date() != self.start.date() + timedelta(days=2):
            raise WeekendListingsDomainError(
                "Weekend window must span one Saturday-to-Monday calendar interval."
            )
        if _utc(self.end) - _utc(self.start) > self.maximum_duration:
            raise WeekendListingsDomainError(
                "Weekend window exceeds the maximum duration of 49 hours."
            )

    def contains(self, observed_at: datetime) -> bool:
        """Return inclusive-start, exclusive-end membership in absolute time."""

        _aware_datetime(observed_at, "observed_at")
        observed = _utc(observed_at)
        return _utc(self.start) <= observed < _utc(self.end)


@dataclass(frozen=True)
class WeekendListingCandidate:
    """One factual collection-relevant listing observed inside the window."""

    listing_id: str
    release_id: int
    observed_at: datetime
    price: MarketplaceMoney
    snapshot_id: str
    source_status: MarketplaceDataStatus
    inclusion_evidence: tuple[str, ...]
    shipping: MarketplaceMoney | None = None
    artist: str | None = None
    title: str | None = None
    condition: str | None = None
    seller_region: str | None = None

    def __post_init__(self) -> None:
        _text(self.listing_id, "listing_id")
        _positive_integer(self.release_id, "release_id")
        _aware_datetime(self.observed_at, "observed_at")
        if type(self.price) is not MarketplaceMoney:
            raise TypeError("price must be MarketplaceMoney.")
        if self.shipping is not None and type(self.shipping) is not MarketplaceMoney:
            raise TypeError("shipping must be MarketplaceMoney or None.")
        _text(self.snapshot_id, "snapshot_id")
        if self.source_status not in {
            MarketplaceDataStatus.COMPLETE,
            MarketplaceDataStatus.PARTIAL,
        }:
            raise WeekendListingsDomainError(
                "A candidate requires a processable source status."
            )
        evidence = _string_tuple(self.inclusion_evidence, "inclusion_evidence")
        if evidence != _INCLUSION_EVIDENCE:
            raise WeekendListingsDomainError(
                "Candidate inclusion evidence must use the canonical factual rules."
            )
        object.__setattr__(self, "inclusion_evidence", evidence)
        for name, value in (
            ("artist", self.artist),
            ("title", self.title),
            ("condition", self.condition),
            ("seller_region", self.seller_region),
        ):
            if value is not None:
                _text(value, name)


@dataclass(frozen=True)
class WeekendListingsOutput:
    """Typed output and source context carried by the standard result."""

    window: WeekendWindow
    snapshot_id: str | None
    snapshot_status: MarketplaceDataStatus | None
    candidates: tuple[WeekendListingCandidate, ...] = ()
    source_diagnostics: tuple[MarketplaceDiagnostic, ...] = ()
    collection_context_complete: bool = True

    def __post_init__(self) -> None:
        if type(self.window) is not WeekendWindow:
            raise TypeError("window must be a WeekendWindow.")
        if (self.snapshot_id is None) != (self.snapshot_status is None):
            raise WeekendListingsDomainError(
                "Snapshot ID and status must be available together."
            )
        if self.snapshot_id is not None:
            _text(self.snapshot_id, "snapshot_id")
        if self.snapshot_status is not None and type(
            self.snapshot_status
        ) is not MarketplaceDataStatus:
            raise TypeError("snapshot_status must be MarketplaceDataStatus or None.")
        if type(self.collection_context_complete) is not bool:
            raise TypeError("collection_context_complete must be a boolean.")
        candidates = _candidate_tuple(self.candidates)
        diagnostics = _diagnostic_tuple(self.source_diagnostics)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "source_diagnostics", diagnostics)

        if self.snapshot_id is None and (candidates or diagnostics):
            raise WeekendListingsDomainError(
                "Absent snapshot context cannot contain candidates or diagnostics."
            )
        if self.snapshot_status in {
            MarketplaceDataStatus.EMPTY,
            MarketplaceDataStatus.UNAVAILABLE,
            MarketplaceDataStatus.FAILED,
        } and candidates:
            raise WeekendListingsDomainError(
                "An unusable or empty source cannot contain candidates."
            )
        if self.snapshot_status in {
            MarketplaceDataStatus.PARTIAL,
            MarketplaceDataStatus.UNAVAILABLE,
            MarketplaceDataStatus.FAILED,
        } and not diagnostics:
            raise WeekendListingsDomainError(
                f"A {self.snapshot_status.value} source requires diagnostics."
            )
        for candidate in candidates:
            if candidate.snapshot_id != self.snapshot_id:
                raise WeekendListingsDomainError(
                    "Candidate snapshot IDs must match their output context."
                )
            if candidate.source_status is not self.snapshot_status:
                raise WeekendListingsDomainError(
                    "Candidate source status must match its output context."
                )
            if not self.window.contains(candidate.observed_at):
                raise WeekendListingsDomainError(
                    "Candidates must fall inside the supplied weekend window."
                )


class WeekendListingsModule:
    """Identify collection-relevant offers observed during one weekend window."""

    module_id = "weekend_listings"
    module_version = "1.0"

    def __init__(self, window: WeekendWindow) -> None:
        if type(window) is not WeekendWindow:
            raise TypeError("window must be a WeekendWindow.")
        self.window = window

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        """Return factual candidates from supplied immutable context only."""

        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        snapshot = context.marketplace_snapshot
        if snapshot is None:
            return self._result(
                IntelligenceStatus.SKIPPED,
                "Weekend Listings requires a supplied Marketplace snapshot.",
                WeekendListingsOutput(self.window, None, None),
                diagnostics=("No Marketplace snapshot was supplied.",),
            )
        if type(snapshot) is not MarketplaceSnapshot:
            raise TypeError("marketplace_snapshot must be a MarketplaceSnapshot or None.")

        source_diagnostics = tuple(snapshot.diagnostics)
        output = WeekendListingsOutput(
            self.window,
            snapshot.snapshot_id,
            snapshot.status,
            source_diagnostics=source_diagnostics,
        )
        diagnostic_text = tuple(_diagnostic_text(value) for value in source_diagnostics)
        if snapshot.status is MarketplaceDataStatus.UNAVAILABLE:
            return self._result(
                IntelligenceStatus.SKIPPED,
                "Weekend Listings could not evaluate an unavailable Marketplace snapshot.",
                output,
                diagnostics=diagnostic_text,
            )
        if snapshot.status is MarketplaceDataStatus.FAILED:
            return self._result(
                IntelligenceStatus.FAILED,
                "Weekend Listings could not evaluate a failed Marketplace snapshot.",
                output,
                diagnostics=diagnostic_text,
            )
        if snapshot.status is MarketplaceDataStatus.EMPTY:
            return self._result(
                IntelligenceStatus.COMPLETED,
                "No marketplace observations were present in the supplied snapshot.",
                output,
            )

        collection, invalid_collection_rows = _collection_index(context.collection)
        if context.collection and not collection:
            output = WeekendListingsOutput(
                self.window,
                snapshot.snapshot_id,
                snapshot.status,
                source_diagnostics=source_diagnostics,
                collection_context_complete=False,
            )
            return self._result(
                IntelligenceStatus.SKIPPED,
                "Weekend Listings requires valid collection release identifiers.",
                output,
                diagnostics=(
                    *diagnostic_text,
                    "Collection context contained no valid release identifiers.",
                ),
            )

        candidates = tuple(
            WeekendListingCandidate(
                listing_id=listing.listing_id,
                release_id=listing.release_id,
                observed_at=listing.observed_at,
                price=listing.price,
                shipping=listing.shipping,
                artist=collection[listing.release_id][0],
                title=collection[listing.release_id][1],
                condition=listing.condition,
                seller_region=listing.seller_region,
                snapshot_id=snapshot.snapshot_id,
                source_status=snapshot.status,
                inclusion_evidence=_INCLUSION_EVIDENCE,
            )
            for listing in snapshot.listing_observations
            if listing.release_id in collection
            and self.window.contains(listing.observed_at)
        )
        candidates = _ordered_candidates(candidates)
        output = WeekendListingsOutput(
            self.window,
            snapshot.snapshot_id,
            snapshot.status,
            candidates,
            source_diagnostics,
            collection_context_complete=invalid_collection_rows == 0,
        )
        diagnostics = diagnostic_text
        if invalid_collection_rows:
            diagnostics = (
                *diagnostics,
                f"Ignored {invalid_collection_rows} collection rows without a valid release ID.",
            )
        count = len(candidates)
        return self._result(
            IntelligenceStatus.COMPLETED,
            (
                f"{count} collection-relevant marketplace listing"
                f"{' was' if count == 1 else 's were'} observed within the supplied "
                "weekend window."
            ),
            output,
            evidence=tuple(
                f"Listing {candidate.listing_id} for release {candidate.release_id} "
                f"was observed at {candidate.observed_at.isoformat()}."
                for candidate in candidates
            ),
            diagnostics=diagnostics,
        )

    def _result(
        self,
        status: IntelligenceStatus,
        summary: str,
        output: WeekendListingsOutput,
        *,
        evidence: tuple[str, ...] = (),
        diagnostics: tuple[str, ...] = (),
    ) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=status,
            summary=summary,
            metrics=MappingProxyType({"output": output}),
            evidence=evidence,
            diagnostics=diagnostics,
        )


def _collection_index(
    rows: Any,
) -> tuple[dict[int, tuple[str | None, str | None]], int]:
    result: dict[int, tuple[str | None, str | None]] = {}
    invalid = 0
    for row in rows:
        if not isinstance(row, Mapping):
            invalid += 1
            continue
        release_id = row.get("release_id")
        if type(release_id) is not int or release_id <= 0:
            invalid += 1
            continue
        if release_id not in result:
            result[release_id] = (
                _optional_metadata(row.get("artist")),
                _optional_metadata(row.get("title")),
            )
    return result, invalid


def _optional_metadata(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _ordered_candidates(
    values: tuple[WeekendListingCandidate, ...],
) -> tuple[WeekendListingCandidate, ...]:
    by_identity = sorted(values, key=lambda value: (value.release_id, value.listing_id))
    return tuple(
        sorted(
            by_identity,
            key=lambda value: _utc(value.observed_at),
            reverse=True,
        )
    )


def _candidate_tuple(values: Any) -> tuple[WeekendListingCandidate, ...]:
    result = _typed_tuple(values, WeekendListingCandidate, "candidates")
    listing_ids = tuple(value.listing_id for value in result)
    if len(set(listing_ids)) != len(listing_ids):
        raise WeekendListingsDomainError("Candidate listing IDs must be unique.")
    if result != _ordered_candidates(result):
        raise WeekendListingsDomainError(
            "Candidates must use canonical Weekend Listings order."
        )
    return result


def _diagnostic_tuple(values: Any) -> tuple[MarketplaceDiagnostic, ...]:
    return _typed_tuple(values, MarketplaceDiagnostic, "source_diagnostics")


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


def _string_tuple(values: Any, name: str) -> tuple[str, ...]:
    result = _typed_tuple(values, str, name)
    for value in result:
        _text(value, f"{name} item")
    return result


def _diagnostic_text(value: MarketplaceDiagnostic) -> str:
    details = "".join(
        f"; {key}={value.details[key]}" for key in sorted(value.details)
    )
    return f"{value.severity.value}:{value.code}: {value.message}{details}"


def _aware_datetime(value: Any, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise WeekendListingsDomainError(f"{name} must be timezone-aware.")


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _positive_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise WeekendListingsDomainError(f"{name} must be positive.")


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise WeekendListingsDomainError(f"{name} must be non-empty and trimmed.")


__all__ = [
    "WeekendListingCandidate",
    "WeekendListingsDomainError",
    "WeekendListingsModule",
    "WeekendListingsOutput",
    "WeekendWindow",
]
