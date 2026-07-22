"""Desktop-neutral rendering for Supply Changes."""

from dataclasses import dataclass

from dip.experience.supply_changes import SupplyChangesDetailState, SupplyChangesDetailViewModel


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
        for label, snapshot in (("Previous", detail.previous_snapshot), ("Latest", detail.latest_snapshot)):
            if snapshot is not None:
                context.extend((f"{label} snapshot: {snapshot.snapshot_id}", f"{label} captured: {snapshot.captured_at.isoformat()}", f"{label} status: {snapshot.status.value.replace('_', ' ').title()}"))
        if context:
            context.append(f"Comparison source: {detail.source or 'Unavailable'}")
        changes = tuple(DesktopReleaseSupplyChange(index, value.release_id, f"Release {value.release_id} — {value.change_kind.value.replace('_', ' ').title()}", "\n".join((f"Previous supply: {_value(value.previous_supply)}", f"Latest supply: {_value(value.latest_supply)}", f"Delta: {_delta(value.delta)}", f"Previous snapshot: {value.previous_snapshot_id}", f"Latest snapshot: {value.latest_snapshot_id}", *(f"Evidence: {item}" for item in value.evidence)))) for index, value in enumerate(detail.changes, 1))
        counts = "" if detail.change_count is None else "\n".join((f"Release changes: {detail.change_count}", f"Unchanged releases: {detail.unchanged_count}", f"Incomparable releases: {detail.incomparable_count}"))
        return DesktopSupplyChangesView(detail.title, detail.state, detail.state.value.replace("_", " ").title(), detail.summary, "\n".join(context), counts, changes, "\n".join(f"• {item}" for item in detail.diagnostics))


def _value(value: int | None) -> str:
    return "Unavailable" if value is None else str(value)


def _delta(value: int | None) -> str:
    return "Unavailable" if value is None else f"{value:+d}"


__all__ = ["DesktopReleaseSupplyChange", "DesktopSupplyChangesRenderer", "DesktopSupplyChangesView"]
