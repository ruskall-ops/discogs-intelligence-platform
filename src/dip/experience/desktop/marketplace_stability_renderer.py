"""Desktop-neutral rendering for Marketplace Stability."""

from dataclasses import dataclass

from dip.experience.marketplace_stability import MarketplaceStabilityDetailState, MarketplaceStabilityDetailViewModel


@dataclass(frozen=True)
class DesktopReleaseStability:
    release_id: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopMarketplaceStabilityView:
    title: str
    state: MarketplaceStabilityDetailState
    headline: str
    summary: str
    context: str
    releases: tuple[DesktopReleaseStability, ...] = ()
    source_provenance: str = ""
    diagnostics: str = ""


class DesktopMarketplaceStabilityRenderer:
    def render(self, detail: MarketplaceStabilityDetailViewModel) -> DesktopMarketplaceStabilityView:
        if type(detail) is not MarketplaceStabilityDetailViewModel:
            raise TypeError("detail must be a MarketplaceStabilityDetailViewModel.")
        return DesktopMarketplaceStabilityView(
            detail.title, detail.state, detail.state.value.replace("_", " ").title(),
            detail.summary, _context(detail),
            tuple(_release(value) for value in detail.releases),
            _provenance(detail), _diagnostics(detail),
        )


def _context(detail):
    summary = detail.stability_summary
    if summary is None:
        return ""
    return "\n".join((
        f"Rule set: {detail.rule_set_version}",
        f"Observed releases: {summary.release_count}",
        f"Assessments — stable: {summary.stable_count}; mixed: {summary.mixed_count}; volatile: {summary.volatile_count}; insufficient: {summary.insufficient_count}",
        f"Evidence — complete: {summary.complete_evidence_count}; partial: {summary.partial_evidence_count}; limited: {summary.limited_evidence_count}; insufficient: {summary.insufficient_evidence_count}",
    ))


def _release(value):
    listing = value.components.listing.facts
    listing_lines = ("Listing persistence evidence: Unavailable",) if listing is None else (
        f"Listings observed: {listing.total_listing_count}",
        f"Currently present listings: {listing.currently_present_count} ({listing.currently_present_ratio})",
        f"Continuously active listings: {listing.continuously_active_count} ({listing.continuously_active_ratio})",
        f"Disappeared listings: {listing.disappeared_count}",
        f"Ended listings: {listing.ended_count}",
        f"Reappeared listings: {listing.reappeared_count}",
        f"Intermittent listings: {listing.intermittent_count}",
        f"Observed disappearance transitions: {listing.total_disappearance_count}",
        f"Observed reappearance transitions: {listing.total_reappearance_count}",
    )
    appearance = value.components.appearance
    body = "\n".join((
        f"Observed stability assessment: {_label(value.assessment.value)}",
        f"Evidence coverage: {_label(value.components.evidence_coverage.value)}",
        f"Price-change stability: {_label(value.components.price.state.value)}",
        f"Historical price changes: {_optional(value.components.price.historical_change_count)}",
        f"Supply-change stability: {_label(value.components.supply.state.value)}",
        f"Historical supply changes: {_optional(value.components.supply.historical_change_count)}",
        f"Appearance continuity: {_label(appearance.state.value)}",
        f"Appearance count: {_optional(appearance.appearance_count)}",
        f"Appearance ratio: {_optional(appearance.appearance_ratio)}",
        f"Longest internal absence: {_optional(appearance.longest_internal_absence)}",
        f"Listing persistence: {_label(value.components.listing.state.value)}",
        *listing_lines,
        f"Stable components: {value.stable_component_count}",
        f"Mixed components: {value.mixed_component_count}",
        f"Volatile components: {value.volatile_component_count}",
        f"Momentum context: {value.momentum_assessment or 'Not supplied'}",
        "Assessment reasons: " + ", ".join(_label(item.value) for item in value.reason_codes),
    ))
    return DesktopReleaseStability(value.release_id, f"Release {value.release_id} · {_label(value.assessment.value)} observed conditions", body)


def _provenance(detail):
    return "\n".join(
        f"{value.module_id} {value.module_version or 'Unknown'} · compatible: {'yes' if value.compatible else 'no'} · snapshots: {', '.join(value.history_snapshot_ids) or 'None supplied'}"
        for value in detail.source_provenance
    )


def _diagnostics(detail):
    return "\n".join((
        *(f"{value.code.value}: {value.message}" for value in detail.output_diagnostics),
        *detail.diagnostics,
    ))


def _label(value):
    return value.replace("_", " ").title()


def _optional(value):
    return "Unavailable" if value is None else str(value)


__all__ = [
    "DesktopMarketplaceStabilityRenderer",
    "DesktopMarketplaceStabilityView",
    "DesktopReleaseStability",
]
