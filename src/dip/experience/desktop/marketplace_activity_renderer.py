"""Desktop-neutral Marketplace Activity rendering."""

from dataclasses import dataclass

from dip.experience.marketplace_activity import MarketplaceActivityDetailState, MarketplaceActivityDetailViewModel


@dataclass(frozen=True)
class DesktopReleaseActivity:
    position: int
    release_id: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopMarketplaceActivityView:
    title: str
    state: MarketplaceActivityDetailState
    headline: str
    summary: str
    counts: str
    activities: tuple[DesktopReleaseActivity, ...] = ()
    diagnostics: str = ""


class DesktopMarketplaceActivityRenderer:
    def render(self, detail: MarketplaceActivityDetailViewModel) -> DesktopMarketplaceActivityView:
        if type(detail) is not MarketplaceActivityDetailViewModel:
            raise TypeError("detail must be a MarketplaceActivityDetailViewModel.")
        counts = "" if detail.release_count is None else f"Releases: {detail.release_count}\nHistorical activity events: {detail.total_activity_count}"
        activities = tuple(DesktopReleaseActivity(index, value.release_id, f"Release {value.release_id}", "\n".join((f"Historical activity count: {value.total_activity_count}", f"Price changes: {value.historical_price_change_count}", f"Supply changes: {value.historical_supply_change_count}", f"Appearances: {value.appearance_count}", f"Appearance ratio: {value.appearance_ratio}", f"First observation: {value.first_observation_snapshot_id} ({value.first_observation_at.isoformat()})", f"Latest observation: {value.latest_observation_snapshot_id} ({value.latest_observation_at.isoformat()})", f"Longest absence: {value.longest_absence} snapshots"))) for index, value in enumerate(detail.activities, 1))
        return DesktopMarketplaceActivityView(detail.title, detail.state, detail.state.value.replace("_", " ").title(), detail.summary, counts, activities, "\n".join(f"• {value}" for value in detail.diagnostics))


__all__ = ["DesktopMarketplaceActivityRenderer", "DesktopMarketplaceActivityView", "DesktopReleaseActivity"]
