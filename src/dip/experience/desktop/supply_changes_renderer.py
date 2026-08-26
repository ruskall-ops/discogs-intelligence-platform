"""Desktop-neutral summary-first rendering for Supply Changes."""

from dataclasses import dataclass

from dip.experience.supply_changes import (
    SupplyChangesDetailState,
    SupplyChangesDetailViewModel,
    SupplyResultGroup,
)
from dip.marketplace_intelligence import SupplyChangeKind
from dip.experience.results_presentation import PresentationTerm, presentation_label


_LEGACY_METADATA_COPY = (
    "Artist and title are current catalogue metadata provided for identification. "
    "They were not captured with the Marketplace snapshots."
)


@dataclass(frozen=True)
class DesktopReleaseSupplyChange:
    position: int
    release_id: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopSupplyResultGroup:
    heading: str
    count: int
    rows: tuple[DesktopReleaseSupplyChange, ...]


@dataclass(frozen=True)
class DesktopSupplyChangesView:
    title: str
    state: SupplyChangesDetailState
    headline: str
    summary: str
    context: str
    counts: str
    changes: tuple[DesktopReleaseSupplyChange, ...] = ()
    diagnostics: str = ""
    groups: tuple[DesktopSupplyResultGroup, ...] = ()
    metadata_explanation: str = ""
    limitations: str = ""
    provenance: str = ""


class DesktopSupplyChangesRenderer:
    def render(self, detail: SupplyChangesDetailViewModel) -> DesktopSupplyChangesView:
        if type(detail) is not SupplyChangesDetailViewModel:
            raise TypeError("detail must be a SupplyChangesDetailViewModel.")
        rows = tuple(_change(index, value) for index, value in enumerate(detail.changes, 1))
        rows_by_identity = {row.release_id: row for row in rows}
        limitations = tuple(value for value in detail.diagnostics if value != _LEGACY_METADATA_COPY)
        return DesktopSupplyChangesView(
            detail.title,
            detail.state,
            detail.state_copy.heading if detail.state_copy else _legacy_headline(detail),
            detail.state_copy.body if detail.state_copy else detail.summary,
            _context(detail),
            "\n".join(f"{count.label}: {count.value}" for count in detail.summary_counts),
            rows,
            "\n".join(f"• {value}" for value in limitations),
            tuple(_group(group, rows_by_identity) for group in detail.result_groups),
            detail.metadata_explanation,
            "\n".join(f"• {value}" for value in limitations),
            _provenance(detail),
        )


def _group(group: SupplyResultGroup, rows_by_identity: dict[int, DesktopReleaseSupplyChange]) -> DesktopSupplyResultGroup:
    return DesktopSupplyResultGroup(
        group.heading,
        group.count,
        tuple(rows_by_identity[row.release_id] for row in group.rows),
    )


def _context(detail: SupplyChangesDetailViewModel) -> str:
    if detail.state is SupplyChangesDetailState.ERROR:
        return ""
    context = detail.comparison_context
    if context is None:
        return ""
    lines = (
        f"{presentation_label(PresentationTerm.PREVIOUS_SNAPSHOT)} capture time: "
        f"{context.previous_captured_at.isoformat(timespec='minutes')}",
        f"{presentation_label(PresentationTerm.LATEST_SNAPSHOT)} capture time: "
        f"{context.latest_captured_at.isoformat(timespec='minutes')}",
        f"Source: {context.source}",
    )
    if context.source_version is not None:
        lines = (*lines, f"Source version: {context.source_version}")
    return "\n".join(lines)


def _provenance(detail: SupplyChangesDetailViewModel) -> str:
    if detail.state is SupplyChangesDetailState.ERROR:
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


def _change(index, value) -> DesktopReleaseSupplyChange:
    return DesktopReleaseSupplyChange(
        index,
        value.release_id,
        f"{value.display_label or f'Release {value.release_id}'} — {_kind_copy(value.change_kind)}",
        "\n".join(
            (
                f"Release ID: {value.release_id}",
                f"Classification: {_kind_copy(value.change_kind)}",
                f"Previous supply: {_value(value.previous_supply)}",
                f"Latest supply: {_value(value.latest_supply)}",
                f"Delta: {_delta(value.delta)}",
                "Evidence:",
                *(f"• {item}" for item in value.evidence),
                *(f"• {item}" for item in value.observation_diagnostics),
            )
        ),
    )


def _value(value: int | None) -> str:
    return "Unavailable" if value is None else str(value)


def _delta(value: int | None) -> str:
    return "Unavailable" if value is None else f"{value:+d}"


def _kind_copy(value: SupplyChangeKind) -> str:
    return {
        SupplyChangeKind.INCREASED: "Increased",
        SupplyChangeKind.DECREASED: "Decreased",
        SupplyChangeKind.NEWLY_AVAILABLE: "Became available for sale",
        SupplyChangeKind.NO_LONGER_AVAILABLE: "No copies observed for sale",
        SupplyChangeKind.INCOMPARABLE: "Incomparable",
    }[value]


def _legacy_headline(detail: SupplyChangesDetailViewModel) -> str:
    return {
        SupplyChangesDetailState.LOADING: "Loading Supply Changes",
        SupplyChangesDetailState.UNAVAILABLE: "Supply Changes unavailable",
    }[detail.state]


def _label(value: str) -> str:
    return value.replace("_", " ").title()


__all__ = [
    "DesktopReleaseSupplyChange",
    "DesktopSupplyChangesRenderer",
    "DesktopSupplyChangesView",
    "DesktopSupplyResultGroup",
]
