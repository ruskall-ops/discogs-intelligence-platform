"""Desktop-neutral rendering for observed Marketplace Scarcity."""

from dataclasses import dataclass

from dip.experience.marketplace_scarcity import MarketplaceScarcityDetailState, MarketplaceScarcityDetailViewModel


@dataclass(frozen=True)
class DesktopReleaseScarcity:
    release_id: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopMarketplaceScarcityView:
    title: str
    state: MarketplaceScarcityDetailState
    headline: str
    summary: str
    context: str
    releases: tuple[DesktopReleaseScarcity, ...] = ()
    source_provenance: str = ""
    diagnostics: str = ""


class DesktopMarketplaceScarcityRenderer:
    def render(self, detail):
        if type(detail) is not MarketplaceScarcityDetailViewModel:
            raise TypeError("detail must be a MarketplaceScarcityDetailViewModel.")
        summary = detail.scarcity_summary
        context = "" if summary is None else "\n".join((
            f"Rule set: {detail.rule_set_version}",
            f"Observed releases: {summary.release_count}",
            f"Assessments — very scarce: {summary.very_scarce_count}; scarce: {summary.scarce_count}; limited: {summary.limited_count}; common: {summary.common_count}; abundant: {summary.abundant_count}; insufficient: {summary.insufficient_count}",
        ))
        return DesktopMarketplaceScarcityView(
            detail.title, detail.state, detail.state.value.replace("_", " ").title(),
            detail.summary, context, tuple(_release(value) for value in detail.releases),
            "\n".join(f"{value.module_id} {value.module_version or 'Unknown'} · compatible: {'yes' if value.compatible else 'no'} · snapshots: {', '.join(value.history_snapshot_ids) or 'None supplied'}" for value in detail.source_provenance),
            "\n".join((*(f"{value.code.value}: {value.message}" for value in detail.output_diagnostics), *detail.diagnostics)),
        )


def _release(value):
    availability = value.components.observed_availability
    appearance = value.components.appearance
    persistence = value.components.listing_persistence
    supply = value.supply_context
    body = "\n".join((
        f"Observed Marketplace scarcity assessment: {_label(value.assessment.value)}",
        f"Evidence coverage: {_label(value.components.evidence_coverage.value)}",
        f"Observed availability: {_label(availability.state.value)}",
        f"Listings observed: {availability.total_listing_count}",
        f"Currently present listings: {availability.currently_present_count} ({availability.currently_present_ratio})",
        f"Appearance scarcity: {_label(appearance.state.value)}",
        f"Appearance count: {_optional(appearance.appearance_count)}",
        f"Appearance ratio: {_optional(appearance.appearance_ratio)}",
        f"Analyzed history snapshots: {_optional(appearance.history_snapshot_count)}",
        f"Longest internal release absence: {_optional(appearance.longest_internal_absence)}",
        f"Listing persistence scarcity: {_label(persistence.state.value)}",
        f"Continuously active listings: {persistence.continuously_active_count}",
        f"Disrupted listings: {persistence.disrupted_listing_count} ({persistence.disrupted_ratio})",
        f"Observed disappearance transitions: {persistence.total_disappearance_count}",
        f"Observed reappearance transitions: {persistence.total_reappearance_count}",
        f"Longest listing absence: {persistence.longest_listing_absence}",
        f"Lifecycle states — active: {persistence.active_count}; reappeared: {persistence.reappeared_count}; intermittent: {persistence.intermittent_count}; disappeared: {persistence.disappeared_count}; ended: {persistence.ended_count}; new: {persistence.new_count}",
        f"Historical supply changes: {'Not supplied' if supply is None or supply.historical_supply_change_count is None else supply.historical_supply_change_count}",
        f"Stability context: {value.stability_assessment or 'Not supplied'}",
        f"Momentum context: {value.momentum_assessment or 'Not supplied'}",
        "Assessment reasons: " + ", ".join(_label(reason.value) for reason in value.reason_codes),
    ))
    return DesktopReleaseScarcity(value.release_id, f"Release {value.release_id} · {_label(value.assessment.value)} observed Marketplace availability", body)


def _label(value):
    return value.replace("_", " ").title()


def _optional(value):
    return "Unavailable" if value is None else str(value)


__all__ = ["DesktopMarketplaceScarcityRenderer", "DesktopMarketplaceScarcityView", "DesktopReleaseScarcity"]
