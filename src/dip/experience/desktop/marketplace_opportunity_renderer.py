"""Desktop-neutral rendering for observed Marketplace Opportunity synthesis."""

from dataclasses import dataclass

from dip.experience.marketplace_opportunity import MarketplaceOpportunityDetailState, MarketplaceOpportunityDetailViewModel


@dataclass(frozen=True)
class DesktopReleaseOpportunity:
    release_id: int
    heading: str
    body: str


@dataclass(frozen=True)
class DesktopMarketplaceOpportunityView:
    title: str
    state: MarketplaceOpportunityDetailState
    headline: str
    summary: str
    context: str
    releases: tuple[DesktopReleaseOpportunity, ...] = ()
    source_provenance: str = ""
    diagnostics: str = ""


class DesktopMarketplaceOpportunityRenderer:
    def render(self, detail):
        if type(detail) is not MarketplaceOpportunityDetailViewModel:
            raise TypeError("detail must be a MarketplaceOpportunityDetailViewModel.")
        summary = detail.opportunity_summary
        context = "" if summary is None else "\n".join((
            f"Rule set: {detail.rule_set_version}",
            f"Observed releases: {summary.release_count}",
            f"Assessments — strong: {summary.strong_count}; developing: {summary.developing_count}; balanced: {summary.balanced_count}; constrained: {summary.constrained_count}; weak: {summary.weak_count}; insufficient: {summary.insufficient_count}",
        ))
        return DesktopMarketplaceOpportunityView(
            detail.title, detail.state, detail.state.value.replace("_", " ").title(),
            detail.summary, context, tuple(_release(value) for value in detail.releases),
            "\n".join(f"{value.module_id} {value.module_version or 'Unknown'} · rule set: {value.rule_set_version or 'Unknown'} · compatible: {'yes' if value.compatible else 'no'} · snapshots: {', '.join(value.history_snapshot_ids) or 'None supplied'}" for value in detail.source_provenance),
            "\n".join((*(f"{value.code.value}: {value.message}" for value in detail.output_diagnostics), *detail.diagnostics)),
        )


def _release(value):
    dimensions = value.dimensions
    body = "\n".join((
        f"Observed Marketplace Opportunity assessment: {_label(value.assessment.value)}",
        f"Opportunity evidence coverage: {_label(value.evidence_coverage.value)}",
        f"Momentum: {_dimension(dimensions.momentum)}",
        f"Stability: {_dimension(dimensions.stability)}",
        f"Scarcity: {_dimension(dimensions.scarcity)}",
        f"Supportive dimensions: {value.supportive_dimension_count}",
        f"Neutral dimensions: {value.neutral_dimension_count}",
        f"Limiting dimensions: {value.limiting_dimension_count}",
        f"Adverse dimensions: {value.adverse_dimension_count}",
        f"Usable dimensions: {value.usable_dimension_count}",
        "Synthesis reasons: " + ", ".join(_label(reason.value) for reason in value.reason_codes),
    ))
    return DesktopReleaseOpportunity(value.release_id, f"Release {value.release_id} · {_label(value.assessment.value)} observed Opportunity alignment", body)


def _dimension(value):
    return f"{_label(value.assessment) if value.assessment else 'Unavailable'} · evidence {_label(value.evidence_coverage.value)} · {_label(value.category.value)}"


def _label(value):
    return value.replace("_", " ").title()


__all__ = ["DesktopMarketplaceOpportunityRenderer", "DesktopMarketplaceOpportunityView", "DesktopReleaseOpportunity"]
