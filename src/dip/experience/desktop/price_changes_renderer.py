"""Desktop-neutral summary-first rendering for Price Changes detail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from dip.experience.price_changes import (
    ListingPriceChangeViewModel,
    PriceChangesDetailState,
    PriceChangesDetailViewModel,
    PriceResultGroup,
    ReleasePriceChangeViewModel,
)
from dip.marketplace_intelligence import MarketplaceMoney, PriceChangeDelta, ReleasePriceChangeKind
from dip.experience.results_presentation import PresentationTerm, presentation_label


_LEGACY_METADATA_COPY = (
    "Artist and title are current catalogue metadata provided for identification. "
    "They were not captured with the Marketplace snapshots."
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
class DesktopPriceResultGroup:
    heading: str
    count: int
    rows: tuple[DesktopReleasePriceChange, ...]


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
    groups: tuple[DesktopPriceResultGroup, ...] = ()
    metadata_explanation: str = ""
    limitations: str = ""
    provenance: str = ""


class DesktopPriceChangesRenderer:
    """Format supplied Price projections without comparison or classification."""

    def render(self, detail: PriceChangesDetailViewModel) -> DesktopPriceChangesView:
        if type(detail) is not PriceChangesDetailViewModel:
            raise TypeError("detail must be a PriceChangesDetailViewModel.")
        release_rows = tuple(
            _release_change(position, change)
            for position, change in enumerate(detail.release_changes, start=1)
        )
        row_positions = {id(value): position for position, value in enumerate(detail.release_changes, start=1)}
        groups = tuple(_group(group, row_positions) for group in detail.result_groups)
        limitations = tuple(
            value for value in detail.diagnostics if value != _LEGACY_METADATA_COPY
        )
        return DesktopPriceChangesView(
            title=detail.title,
            state=detail.state,
            headline=detail.state_copy.heading if detail.state_copy else _legacy_headline(detail),
            summary=detail.state_copy.body if detail.state_copy else detail.summary,
            context=_context(detail),
            counts="\n".join(f"{count.label}: {count.value}" for count in detail.summary_counts),
            listing_changes=tuple(
                _listing_change(position, change)
                for position, change in enumerate(detail.listing_changes, start=1)
            ),
            release_changes=release_rows,
            diagnostics="\n".join(f"• {value}" for value in limitations),
            groups=groups,
            metadata_explanation=detail.metadata_explanation,
            limitations="\n".join(f"• {value}" for value in limitations),
            provenance=_provenance(detail),
        )


def _group(
    group: PriceResultGroup,
    row_positions: dict[int, int],
) -> DesktopPriceResultGroup:
    return DesktopPriceResultGroup(
        group.heading,
        group.count,
        tuple(_release_change(row_positions[id(row)], row) for row in group.rows),
    )


def _context(detail: PriceChangesDetailViewModel) -> str:
    if detail.state is PriceChangesDetailState.ERROR:
        return ""
    context = detail.comparison_context
    if context is None:
        return ""
    lines = (
        f"{presentation_label(PresentationTerm.PREVIOUS_SNAPSHOT)} capture time: "
        f"{_timestamp(context.previous_captured_at)}",
        f"{presentation_label(PresentationTerm.LATEST_SNAPSHOT)} capture time: "
        f"{_timestamp(context.latest_captured_at)}",
        f"Source: {context.source}",
    )
    if context.source_version is not None:
        lines = (*lines, f"Source version: {context.source_version}")
    return "\n".join(lines)


def _provenance(detail: PriceChangesDetailViewModel) -> str:
    if detail.state is PriceChangesDetailState.ERROR:
        return ""
    if detail.previous_snapshot is None or detail.latest_snapshot is None:
        return ""
    return "\n".join(
        (
            f"{presentation_label(PresentationTerm.PREVIOUS_SNAPSHOT)} ID: {detail.previous_snapshot.snapshot_id}",
            f"Previous status: {_label(detail.previous_snapshot.status.value)}",
            f"{presentation_label(PresentationTerm.LATEST_SNAPSHOT)} ID: {detail.latest_snapshot.snapshot_id}",
            f"Latest status: {_label(detail.latest_snapshot.status.value)}",
            f"Comparison state: {_label(detail.comparison_state.value)}",
        )
    )


def _listing_change(position: int, change: ListingPriceChangeViewModel) -> DesktopListingPriceChange:
    return DesktopListingPriceChange(
        position,
        change.listing_id,
        f"Listing {change.listing_id} · {_label(change.change_kind.value)}",
        "\n".join(
            (
                f"Release ID: {change.release_id}",
                f"Change: {_label(change.change_kind.value)}",
                f"Previous price: {_optional_money(change.previous_price)}",
                f"Latest price: {_optional_money(change.latest_price)}",
                f"Delta: {_optional_delta(change.delta)}",
                f"Previous observed: {_optional_timestamp(change.previous_observed_at)}",
                f"Latest observed: {_optional_timestamp(change.latest_observed_at)}",
                f"{presentation_label(PresentationTerm.PREVIOUS_SNAPSHOT)}: {change.previous_snapshot_id}",
                f"{presentation_label(PresentationTerm.LATEST_SNAPSHOT)}: {change.latest_snapshot_id}",
                "Evidence:",
                *(f"• {value}" for value in change.evidence),
            )
        ),
    )


def _release_change(position: int, change: ReleasePriceChangeViewModel) -> DesktopReleasePriceChange:
    return DesktopReleasePriceChange(
        position,
        change.release_id,
        f"{change.display_label or f'Release {change.release_id}'} · {_label(change.metric.value)}",
        "\n".join(
            (
                f"Release ID: {change.release_id}",
                f"Classification: {_release_kind_copy(change.change_kind)}",
                f"Previous value: {_optional_money(change.previous_value)}",
                f"Latest value: {_optional_money(change.latest_value)}",
                f"Delta: {_optional_delta(change.delta)}",
                "Evidence:",
                *(f"• {value}" for value in change.evidence),
                *(f"• {value}" for value in change.observation_diagnostics),
            )
        ),
    )


def _release_kind_copy(value: ReleasePriceChangeKind) -> str:
    return {
        ReleasePriceChangeKind.INCREASED: "Increased",
        ReleasePriceChangeKind.DECREASED: "Decreased",
        ReleasePriceChangeKind.NEWLY_AVAILABLE: "Price observation became available",
        ReleasePriceChangeKind.NO_LONGER_AVAILABLE: "Price observation no longer available",
        ReleasePriceChangeKind.INCOMPARABLE: "Incomparable",
    }[value]


def _legacy_headline(detail: PriceChangesDetailViewModel) -> str:
    return {
        PriceChangesDetailState.LOADING: "Loading Price Changes",
        PriceChangesDetailState.UNAVAILABLE: "Price Changes unavailable",
    }[detail.state]


def _optional_money(value: MarketplaceMoney | None) -> str:
    return "Unavailable" if value is None else f"{value.currency} {_decimal(value.amount)}"


def _optional_delta(value: PriceChangeDelta | None) -> str:
    return "Unavailable" if value is None else f"{value.currency} {format(value.amount, '+f')}"


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
    "DesktopPriceResultGroup",
    "DesktopReleasePriceChange",
]
