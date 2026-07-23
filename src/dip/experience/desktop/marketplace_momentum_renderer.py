"""Desktop-neutral rendering for explainable Marketplace Momentum."""

from dataclasses import dataclass

from dip.decision_intelligence import (
    EvidenceCoverage,
    MomentumAssessment,
)
from dip.experience.marketplace_momentum import (
    AppearancePersistenceContextViewModel,
    ListingPersistenceContextViewModel,
    MarketplaceMomentumDetailState,
    MarketplaceMomentumDetailViewModel,
    MarketplaceMomentumDiagnosticViewModel,
    ReleaseMomentumViewModel,
    SourceProvenanceViewModel,
)


@dataclass(frozen=True)
class DesktopReleaseMomentum:
    position: int
    release_id: int
    assessment: MomentumAssessment
    evidence_coverage: EvidenceCoverage
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopMarketplaceMomentumView:
    title: str
    state: MarketplaceMomentumDetailState
    headline: str
    summary: str
    context: str
    releases: tuple[DesktopReleaseMomentum, ...] = ()
    source_provenance: str = ""
    diagnostics: str = ""


class DesktopMarketplaceMomentumRenderer:
    """Format mapped Momentum facts without changing their meaning or order."""

    def render(
        self,
        detail: MarketplaceMomentumDetailViewModel,
    ) -> DesktopMarketplaceMomentumView:
        if type(detail) is not MarketplaceMomentumDetailViewModel:
            raise TypeError(
                "detail must be a MarketplaceMomentumDetailViewModel."
            )
        releases = tuple(
            _release(index, value)
            for index, value in enumerate(detail.releases, 1)
        )
        return DesktopMarketplaceMomentumView(
            title=detail.title,
            state=detail.state,
            headline=detail.state.value.replace("_", " ").title(),
            summary=detail.summary,
            context=_context(detail),
            releases=releases,
            source_provenance=_provenance(detail.source_provenance),
            diagnostics=_diagnostics(
                detail.output_diagnostics,
                detail.diagnostics,
            ),
        )


def _context(detail: MarketplaceMomentumDetailViewModel) -> str:
    summary = detail.momentum_summary
    thresholds = detail.activity_thresholds
    if (
        summary is None
        or thresholds is None
        or detail.analysis_state is None
    ):
        return ""
    return "\n".join(
        (
            f"Analysis state: {_label(detail.analysis_state.value)}",
            f"Rule set: {detail.rule_set_version}",
            f"Observed releases: {summary.release_count}",
            (
                "Observed assessments — "
                f"positive: {summary.positive_count}; "
                f"mixed: {summary.mixed_count}; "
                f"neutral: {summary.neutral_count}; "
                f"negative: {summary.negative_count}; "
                f"insufficient: {summary.insufficient_count}"
            ),
            (
                "Evidence coverage — "
                f"complete: {summary.complete_evidence_count}; "
                f"partial: {summary.partial_evidence_count}; "
                f"limited: {summary.limited_evidence_count}; "
                f"insufficient: {summary.insufficient_evidence_count}"
            ),
            (
                "Activity threshold upper bounds — "
                f"low: {thresholds.low_maximum}; "
                f"moderate: {thresholds.moderate_maximum}"
            ),
        )
    )


def _release(
    position: int,
    value: ReleaseMomentumViewModel,
) -> DesktopReleaseMomentum:
    assessment = {
        MomentumAssessment.POSITIVE: "Positive observed momentum",
        MomentumAssessment.MIXED: "Mixed observed signals",
        MomentumAssessment.NEUTRAL: "Neutral observed momentum",
        MomentumAssessment.NEGATIVE: "Negative observed momentum",
        MomentumAssessment.INSUFFICIENT: "Insufficient evidence",
    }[value.assessment]
    activity_count = (
        "Unavailable"
        if value.total_activity_count is None
        else str(value.total_activity_count)
    )
    body = "\n".join(
        (
            f"Observed assessment: {assessment}",
            f"Evidence coverage: {_label(value.evidence_coverage.value)}",
            f"Observed price direction: {_label(value.price_direction.value)}",
            f"Price increases observed: {value.price.increase_count}",
            f"Price decreases observed: {value.price.decrease_count}",
            (
                "Price observations newly seen: "
                f"{value.price.newly_observed_count}"
            ),
            (
                "Price observations no longer seen: "
                f"{value.price.no_longer_observed_count}"
            ),
            (
                "Incomparable price observations: "
                f"{value.price.incomparable_count}"
            ),
            (
                "Comparable price changes observed: "
                f"{value.price.comparable_change_count}"
            ),
            f"Net observed price direction: {value.net_price_direction}",
            f"Observed supply pressure: {_label(value.supply_direction.value)}",
            f"Supply increases observed: {value.supply.increase_count}",
            f"Supply decreases observed: {value.supply.decrease_count}",
            (
                "Supply observations newly available: "
                f"{value.supply.newly_available_count}"
            ),
            (
                "Supply observations no longer available: "
                f"{value.supply.no_longer_available_count}"
            ),
            (
                "Incomparable supply observations: "
                f"{value.supply.incomparable_count}"
            ),
            (
                "Comparable supply changes observed: "
                f"{value.supply.comparable_change_count}"
            ),
            f"Net observed supply pressure: {value.net_supply_pressure}",
            f"Observed activity intensity: {_label(value.activity_intensity.value)}",
            f"Total activity observed: {activity_count}",
            (
                "Comparable price evidence: "
                f"{_yes_no(value.evidence.price_comparable)}"
            ),
            (
                "Comparable supply evidence: "
                f"{_yes_no(value.evidence.supply_comparable)}"
            ),
            (
                "Activity evidence available: "
                f"{_yes_no(value.evidence.activity_available)}"
            ),
            (
                "Required sources partial: "
                f"{_yes_no(value.evidence.required_sources_partial)}"
            ),
            (
                "Required-source diagnostics present: "
                f"{_yes_no(value.evidence.required_source_diagnostics)}"
            ),
            (
                "Assessment reasons: "
                + ", ".join(_label(item.value) for item in value.reason_codes)
            ),
            (
                "Contributing intelligence: "
                + (
                    ", ".join(value.contributing_source_ids)
                    if value.contributing_source_ids
                    else "None supplied"
                )
            ),
            *_appearance_context(value.supporting_context.appearance),
            *_listing_context(value.supporting_context.listing_persistence),
        )
    )
    return DesktopReleaseMomentum(
        position=position,
        release_id=value.release_id,
        assessment=value.assessment,
        evidence_coverage=value.evidence_coverage,
        heading=f"Release {value.release_id} · {assessment}",
        body=body,
    )


def _appearance_context(
    value: AppearancePersistenceContextViewModel | None,
) -> tuple[str, ...]:
    if value is None:
        return ("Appearance context: Not supplied",)
    return (
        f"Appearance observations: {value.appearance_count}",
        f"Appearance ratio: {value.appearance_ratio}",
        f"Longest observed absence: {value.longest_absence} snapshots",
        f"Appearance context source: {value.source_module_id}",
    )


def _listing_context(
    value: ListingPersistenceContextViewModel | None,
) -> tuple[str, ...]:
    if value is None:
        return ("Listing persistence context: Not supplied",)
    return (
        f"Listings observed: {value.listing_count}",
        f"Listings currently present: {value.currently_present_count}",
        f"New listings observed: {value.new_count}",
        f"Active listings observed: {value.active_count}",
        f"Disappeared listings observed: {value.disappeared_count}",
        f"Reappeared listings observed: {value.reappeared_count}",
        f"Intermittent listings observed: {value.intermittent_count}",
        f"Ended listings observed: {value.ended_count}",
    )


def _provenance(values: tuple[SourceProvenanceViewModel, ...]) -> str:
    blocks = []
    for value in values:
        snapshots = (
            ", ".join(value.history_snapshot_ids)
            if value.history_snapshot_ids
            else "None supplied"
        )
        versions = (
            ", ".join(
                "Unknown" if item is None else item
                for item in value.source_versions
            )
            if value.source_versions
            else "None supplied"
        )
        source_diagnostics = (
            "; ".join(value.diagnostics)
            if value.diagnostics
            else "None"
        )
        blocks.append(
            "\n".join(
                (
                    f"Source intelligence: {value.module_id}",
                    (
                        "Module version: "
                        f"{value.module_version or 'Unknown'}"
                    ),
                    f"Result status: {_label(value.result_status.value)}",
                    f"Compatible: {_yes_no(value.compatible)}",
                    f"Partial: {_yes_no(value.partial)}",
                    f"History snapshots: {snapshots}",
                    f"Marketplace source: {value.source or 'Not supplied'}",
                    f"Marketplace source versions: {versions}",
                    f"Source diagnostics: {source_diagnostics}",
                )
            )
        )
    return "\n\n".join(blocks)


def _diagnostics(
    output_values: tuple[MarketplaceMomentumDiagnosticViewModel, ...],
    result_values: tuple[str, ...],
) -> str:
    output_lines = tuple(
        _diagnostic_line(value) for value in output_values
    )
    result_lines = tuple(
        f"Result diagnostic: {value}" for value in result_values
    )
    return "\n".join((*output_lines, *result_lines))


def _diagnostic_line(value: MarketplaceMomentumDiagnosticViewModel) -> str:
    qualifiers = tuple(
        item
        for item in (
            value.source_module_id,
            (
                None
                if value.release_id is None
                else f"release {value.release_id}"
            ),
        )
        if item is not None
    )
    scope = "" if not qualifiers else f" [{', '.join(qualifiers)}]"
    return f"Momentum diagnostic ({value.code.value}){scope}: {value.message}"


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


__all__ = [
    "DesktopMarketplaceMomentumRenderer",
    "DesktopMarketplaceMomentumView",
    "DesktopReleaseMomentum",
]
