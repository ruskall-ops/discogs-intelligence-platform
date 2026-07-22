"""Desktop-neutral rendering for Price Changes detail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from dip.experience.price_changes import (
    ListingPriceChangeViewModel,
    PriceChangesDetailState,
    PriceChangesDetailViewModel,
    PriceChangesSnapshotViewModel,
    ReleasePriceChangeViewModel,
)
from dip.marketplace_intelligence import (
    MarketplaceMoney,
    PriceChangeDelta,
)


@dataclass(frozen=True)
class DesktopListingPriceChange:
    position: int
    listing_id: str
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopReleasePriceChange:
    position: int
    release_id: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopPriceChangesView:
    title: str
    state: PriceChangesDetailState
    headline: str
    summary: str
    context: str
    counts: str
    listing_changes: tuple[DesktopListingPriceChange, ...] = ()
    release_changes: tuple[DesktopReleasePriceChange, ...] = ()
    diagnostics: str = ""


class DesktopPriceChangesRenderer:
    """Format supplied price facts without comparison or qualification."""

    def render(
        self,
        detail: PriceChangesDetailViewModel,
    ) -> DesktopPriceChangesView:
        if type(detail) is not PriceChangesDetailViewModel:
            raise TypeError("detail must be a PriceChangesDetailViewModel.")
        return DesktopPriceChangesView(
            title=detail.title,
            state=detail.state,
            headline=_headline(detail),
            summary=detail.summary,
            context=_context(detail),
            counts=_counts(detail),
            listing_changes=tuple(
                _listing_change(position, change)
                for position, change in enumerate(detail.listing_changes, start=1)
            ),
            release_changes=tuple(
                _release_change(position, change)
                for position, change in enumerate(detail.release_changes, start=1)
            ),
            diagnostics="\n".join(
                f"• {diagnostic}" for diagnostic in detail.diagnostics
            ),
        )


def _context(detail: PriceChangesDetailViewModel) -> str:
    if detail.previous_snapshot is None and detail.latest_snapshot is None:
        return ""
    lines: list[str] = []
    if detail.previous_snapshot is not None:
        lines.extend(_snapshot_lines("Previous snapshot", detail.previous_snapshot))
    if detail.latest_snapshot is not None:
        lines.extend(_snapshot_lines("Latest snapshot", detail.latest_snapshot))
    lines.append(f"Comparison source: {detail.source or 'Unavailable'}")
    if detail.comparison_state is not None:
        lines.append(
            "Comparison state: "
            f"{_label(detail.comparison_state.value)}"
        )
    return "\n".join(lines)


def _snapshot_lines(
    heading: str,
    snapshot: PriceChangesSnapshotViewModel,
) -> tuple[str, ...]:
    return (
        f"{heading}: {snapshot.snapshot_id}",
        f"{heading} captured: {_timestamp(snapshot.captured_at)}",
        f"{heading} source: {snapshot.source}",
        f"{heading} status: {_label(snapshot.status.value)}",
        f"{heading} source version: {snapshot.source_version or 'Unavailable'}",
    )


def _counts(detail: PriceChangesDetailViewModel) -> str:
    if detail.listing_change_count is None:
        return ""
    return "\n".join(
        (
            f"Listing changes: {detail.listing_change_count}",
            f"Release-level changes: {detail.release_change_count}",
            f"Unchanged supplied values: {detail.unchanged_count}",
            f"Incomparable changes: {detail.incomparable_count}",
        )
    )


def _listing_change(
    position: int,
    change: ListingPriceChangeViewModel,
) -> DesktopListingPriceChange:
    body = "\n".join(
        (
            f"Release ID: {change.release_id}",
            f"Change: {_label(change.change_kind.value)}",
            f"Previous price: {_optional_money(change.previous_price)}",
            f"Latest price: {_optional_money(change.latest_price)}",
            f"Delta: {_optional_delta(change.delta)}",
            (
                "Previous observed: "
                f"{_optional_timestamp(change.previous_observed_at)}"
            ),
            f"Latest observed: {_optional_timestamp(change.latest_observed_at)}",
            f"Previous snapshot: {change.previous_snapshot_id}",
            f"Latest snapshot: {change.latest_snapshot_id}",
            "Evidence:",
            *(f"• {value}" for value in change.evidence),
        )
    )
    return DesktopListingPriceChange(
        position=position,
        listing_id=change.listing_id,
        heading=f"Listing {change.listing_id} · {_label(change.change_kind.value)}",
        body=body,
    )


def _release_change(
    position: int,
    change: ReleasePriceChangeViewModel,
) -> DesktopReleasePriceChange:
    body = "\n".join(
        (
            f"Metric: {_label(change.metric.value)}",
            f"Change: {_label(change.change_kind.value)}",
            f"Previous value: {_optional_money(change.previous_value)}",
            f"Latest value: {_optional_money(change.latest_value)}",
            f"Delta: {_optional_delta(change.delta)}",
            f"Previous snapshot: {change.previous_snapshot_id}",
            f"Latest snapshot: {change.latest_snapshot_id}",
            "Evidence:",
            *(f"• {value}" for value in change.evidence),
        )
    )
    return DesktopReleasePriceChange(
        position=position,
        release_id=change.release_id,
        heading=(
            f"Release {change.release_id} · {_label(change.metric.value)}"
        ),
        body=body,
    )


def _headline(detail: PriceChangesDetailViewModel) -> str:
    labels = {
        PriceChangesDetailState.LOADING: "Loading Price Changes",
        PriceChangesDetailState.AVAILABLE: (
            f"{detail.listing_change_count} listing changes · "
            f"{detail.release_change_count} release-level changes"
        ),
        PriceChangesDetailState.PARTIAL: (
            f"{detail.listing_change_count} listing changes · "
            f"{detail.release_change_count} release-level changes · partial evidence"
        ),
        PriceChangesDetailState.EMPTY: "No price changes detected",
        PriceChangesDetailState.UNAVAILABLE: "Price Changes unavailable",
        PriceChangesDetailState.ERROR: "Price Changes could not be evaluated",
        PriceChangesDetailState.INSUFFICIENT_HISTORY: (
            "Insufficient Marketplace history for Price Changes"
        ),
        PriceChangesDetailState.INSUFFICIENT_DATA: (
            "Insufficient data for Price Changes"
        ),
    }
    return labels[detail.state]


def _optional_money(value: MarketplaceMoney | None) -> str:
    return "Unavailable" if value is None else _money(value)


def _money(value: MarketplaceMoney) -> str:
    return f"{value.currency} {_decimal(value.amount)}"


def _optional_delta(value: PriceChangeDelta | None) -> str:
    if value is None:
        return "Unavailable"
    return f"{value.currency} {format(value.amount, '+f')}"


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _optional_timestamp(value: datetime | None) -> str:
    return "Unavailable" if value is None else _timestamp(value)


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


def _label(value: str) -> str:
    return value.replace("_", " ").title()


__all__ = [
    "DesktopListingPriceChange",
    "DesktopPriceChangesRenderer",
    "DesktopPriceChangesView",
    "DesktopReleasePriceChange",
]
