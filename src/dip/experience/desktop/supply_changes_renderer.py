"""Desktop-neutral rendering for Supply Changes."""

from dataclasses import dataclass

from dip.experience.supply_changes import SupplyChangesDetailState, SupplyChangesDetailViewModel
from dip.marketplace_intelligence import SupplyChangeKind


@dataclass(frozen=True)
class DesktopReleaseSupplyChange:
    position: int
    release_id: int
    heading: str
    body: str


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


class DesktopSupplyChangesRenderer:
    def render(self, detail: SupplyChangesDetailViewModel) -> DesktopSupplyChangesView:
        if type(detail) is not SupplyChangesDetailViewModel:
            raise TypeError("detail must be a SupplyChangesDetailViewModel.")
        context: list[str] = []
        comparison = detail.comparison_context
        for label, snapshot in (("Previous", detail.previous_snapshot), ("Latest", detail.latest_snapshot)):
            if snapshot is not None:
                context.extend((f"{label} snapshot: {snapshot.snapshot_id}", f"{label} captured: {snapshot.captured_at.isoformat()}", f"{label} status: {snapshot.status.value.replace('_', ' ').title()}"))
        if comparison is not None:
            context.append(f"Comparison source: {comparison.source}")
        changes = tuple(DesktopReleaseSupplyChange(index, value.release_id, f"{value.display_label or f'Release {value.release_id}'} — {_kind_copy(value.change_kind)}", "\n".join((f"Release ID: {value.release_id}", f"Previous supply: {_value(value.previous_supply)}", f"Latest supply: {_value(value.latest_supply)}", f"Delta: {_delta(value.delta)}", f"Previous snapshot: {value.previous_snapshot_id}", f"Latest snapshot: {value.latest_snapshot_id}", f"Previous observed: {_timestamp(value.previous_observed_at)}", f"Current observed: {_timestamp(value.latest_observed_at)}", *(f"Evidence: {item}" for item in value.evidence), *(f"Diagnostic: {item}" for item in value.observation_diagnostics)))) for index, value in enumerate(detail.changes, 1))
        counts = "\n".join(f"{count.label}: {count.value}" for count in detail.summary_counts)
        headline = (
            detail.state_copy.heading
            if detail.state_copy is not None
            else {
                SupplyChangesDetailState.LOADING: "Loading Supply Changes",
                SupplyChangesDetailState.UNAVAILABLE: "Supply Changes unavailable",
            }[detail.state]
        )
        summary = detail.state_copy.body if detail.state_copy is not None else detail.summary
        return DesktopSupplyChangesView(detail.title, detail.state, headline, summary, "\n".join(context), counts, changes, "\n".join(f"• {item}" for item in detail.diagnostics))


def _value(value: int | None) -> str:
    return "Unavailable" if value is None else str(value)


def _delta(value: int | None) -> str:
    return "Unavailable" if value is None else f"{value:+d}"


def _timestamp(value) -> str:
    return "Unavailable" if value is None else value.isoformat()


def _kind_copy(value: SupplyChangeKind) -> str:
    return {
        SupplyChangeKind.INCREASED: "Increased",
        SupplyChangeKind.DECREASED: "Decreased",
        SupplyChangeKind.NEWLY_AVAILABLE: "Became available for sale",
        SupplyChangeKind.NO_LONGER_AVAILABLE: "No copies observed for sale",
        SupplyChangeKind.INCOMPARABLE: "Incomparable",
    }[value]


__all__ = ["DesktopReleaseSupplyChange", "DesktopSupplyChangesRenderer", "DesktopSupplyChangesView"]
