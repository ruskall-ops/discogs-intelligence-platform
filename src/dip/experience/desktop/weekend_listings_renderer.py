"""Desktop-neutral rendering for Weekend Listings detail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from dip.experience.weekend_listings import (
    WeekendListingViewModel,
    WeekendListingsDetailState,
    WeekendListingsDetailViewModel,
)
from dip.marketplace_intelligence import MarketplaceMoney


@dataclass(frozen=True)
class DesktopWeekendListing:
    position: int
    listing_id: str
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopWeekendListingsView:
    title: str
    state: WeekendListingsDetailState
    headline: str
    summary: str
    context: str
    candidates: tuple[DesktopWeekendListing, ...] = ()
    diagnostics: str = ""


class DesktopWeekendListingsRenderer:
    """Format factual listing values without qualification or calculations."""

    def render(
        self,
        detail: WeekendListingsDetailViewModel,
    ) -> DesktopWeekendListingsView:
        if type(detail) is not WeekendListingsDetailViewModel:
            raise TypeError("detail must be a WeekendListingsDetailViewModel.")
        context = ""
        if detail.window is not None:
            lines = [
                f"Window: {_timestamp(detail.window.start)} → {_timestamp(detail.window.end)}"
            ]
            if detail.snapshot_id is not None:
                lines.extend(
                    (
                        f"Snapshot: {detail.snapshot_id}",
                        f"Source status: {detail.snapshot_status.value.title()}",
                    )
                )
            context = "\n".join(lines)
        return DesktopWeekendListingsView(
            title=detail.title,
            state=detail.state,
            headline=_headline(detail),
            summary=detail.summary,
            context=context,
            candidates=tuple(
                _candidate(position, candidate)
                for position, candidate in enumerate(detail.candidates, start=1)
            ),
            diagnostics="\n".join(
                f"• {diagnostic}" for diagnostic in detail.diagnostics
            ),
        )


def _candidate(
    position: int,
    candidate: WeekendListingViewModel,
) -> DesktopWeekendListing:
    identity = (
        f"{candidate.artist or 'Unknown artist'} — {candidate.title or 'Unknown title'}"
    )
    body = "\n".join(
        (
            f"Listing ID: {candidate.listing_id}",
            f"Release ID: {candidate.release_id}",
            f"Observed: {_timestamp(candidate.observed_at)}",
            f"Price: {_money(candidate.price)}",
            f"Shipping: {_optional_money(candidate.shipping)}",
            f"Condition: {candidate.condition or 'Unavailable'}",
            f"Seller region: {candidate.seller_region or 'Unavailable'}",
            "Why included:",
            *(f"• {value}" for value in candidate.inclusion_evidence),
        )
    )
    return DesktopWeekendListing(position, candidate.listing_id, identity, body)


def _headline(detail: WeekendListingsDetailViewModel) -> str:
    labels = {
        WeekendListingsDetailState.LOADING: "Loading Weekend Listings",
        WeekendListingsDetailState.AVAILABLE: (
            f"{detail.candidate_count} Weekend Listings"
        ),
        WeekendListingsDetailState.PARTIAL: (
            f"{detail.candidate_count} Weekend Listings · partial evidence"
        ),
        WeekendListingsDetailState.EMPTY: "No qualifying Weekend Listings",
        WeekendListingsDetailState.UNAVAILABLE: "Weekend Listings unavailable",
        WeekendListingsDetailState.ERROR: "Weekend Listings could not be evaluated",
        WeekendListingsDetailState.INSUFFICIENT_DATA: (
            "Insufficient data for Weekend Listings"
        ),
    }
    return labels[detail.state]


def _money(value: MarketplaceMoney) -> str:
    return f"{value.currency} {_decimal(value.amount)}"


def _optional_money(value: MarketplaceMoney | None) -> str:
    return "Unavailable" if value is None else _money(value)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _timestamp(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


__all__ = [
    "DesktopWeekendListing",
    "DesktopWeekendListingsRenderer",
    "DesktopWeekendListingsView",
]
