"""Desktop-neutral rendering for historical appearance frequency."""

from dataclasses import dataclass

from dip.experience.rare_appearances import RareAppearancesDetailState, RareAppearancesDetailViewModel


@dataclass(frozen=True)
class DesktopRareAppearance:
    position: int
    release_id: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopRareAppearancesView:
    title: str
    state: RareAppearancesDetailState
    headline: str
    summary: str
    context: str
    appearances: tuple[DesktopRareAppearance, ...] = ()
    diagnostics: str = ""


class DesktopRareAppearancesRenderer:
    def render(self, detail: RareAppearancesDetailViewModel) -> DesktopRareAppearancesView:
        if type(detail) is not RareAppearancesDetailViewModel:
            raise TypeError("detail must be a RareAppearancesDetailViewModel.")
        context = "" if detail.history_snapshot_count is None else "\n".join((f"Analyzed snapshots: {detail.history_snapshot_count}", f"Observed releases: {detail.release_count}", f"Appearance threshold: fewer than {detail.threshold} snapshots", f"Excluded snapshots: {detail.excluded_snapshot_count}"))
        appearances = tuple(DesktopRareAppearance(index, value.release_id, f"Release {value.release_id}", "\n".join((f"Appearances: {value.appearance_count} of {value.history_snapshot_count}", f"Appearance ratio: {value.appearance_ratio}", f"First observed: {value.first_observed_snapshot_id} ({value.first_observed_at.isoformat()})", f"Latest observed: {value.latest_observed_snapshot_id} ({value.latest_observed_at.isoformat()})", f"Longest absence: {value.longest_absence} snapshots", f"Observation snapshots: {', '.join(value.observation_snapshot_ids)}"))) for index, value in enumerate(detail.appearances, 1))
        return DesktopRareAppearancesView(detail.title, detail.state, detail.state.value.replace("_", " ").title(), detail.summary, context, appearances, "\n".join(f"• {value}" for value in detail.diagnostics))


__all__ = ["DesktopRareAppearance", "DesktopRareAppearancesRenderer", "DesktopRareAppearancesView"]
