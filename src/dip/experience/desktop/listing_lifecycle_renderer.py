"""Desktop-neutral Listing Lifecycle rendering."""

from dataclasses import dataclass

from dip.experience.listing_lifecycle import ListingLifecycleDetailState, ListingLifecycleDetailViewModel


@dataclass(frozen=True)
class DesktopListingLifecycle:
    position: int
    release_id: int
    listing_id: str
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopListingLifecycleView:
    title: str
    state: ListingLifecycleDetailState
    headline: str
    summary: str
    counts: str
    lifecycles: tuple[DesktopListingLifecycle, ...] = ()
    diagnostics: str = ""


class DesktopListingLifecycleRenderer:
    def render(self, detail: ListingLifecycleDetailViewModel) -> DesktopListingLifecycleView:
        if type(detail) is not ListingLifecycleDetailViewModel:
            raise TypeError("detail must be a ListingLifecycleDetailViewModel.")
        counts = "" if detail.listing_count is None else f"Analyzed snapshots: {detail.history_snapshot_count}\nListings: {detail.listing_count}\nCurrently present: {detail.currently_present_count}"
        values = tuple(DesktopListingLifecycle(index, value.release_id, value.listing_id, f"Release {value.release_id} · Listing {value.listing_id}", "\n".join((f"Lifecycle state: {value.lifecycle_state.value.title()}", f"Currently present: {'Yes' if value.currently_present else 'No'}", f"First observation: {value.first_observation_snapshot_id} ({value.first_observation_at.isoformat()})", f"Latest observation: {value.latest_observation_snapshot_id} ({value.latest_observation_at.isoformat()})", f"Observed snapshots: {value.snapshots_observed} of {value.history_snapshot_count}", f"Observation ratio: {value.observation_ratio}", f"Continuous lifetime: {value.continuous_lifetime} snapshots", f"Disappearances: {value.disappearance_count}", f"Reappearances: {value.reappearance_count}", f"Longest absence: {value.longest_absence} snapshots", *(f"Diagnostic: {item}" for item in value.diagnostics)))) for index, value in enumerate(detail.lifecycles, 1))
        return DesktopListingLifecycleView(detail.title, detail.state, detail.state.value.replace("_", " ").title(), detail.summary, counts, values, "\n".join(f"• {item}" for item in detail.diagnostics))


__all__ = ["DesktopListingLifecycle", "DesktopListingLifecycleRenderer", "DesktopListingLifecycleView"]
