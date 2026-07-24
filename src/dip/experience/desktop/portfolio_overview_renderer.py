"""Desktop rendering and navigation for Portfolio Overview."""

from dataclasses import dataclass
from typing import Protocol

from dip.experience.portfolio_overview import (
    PortfolioOverviewDetailState,
    PortfolioOverviewViewModel,
)
from dip.intelligence import IntelligenceResult


@dataclass(frozen=True)
class DesktopPortfolioOverviewSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopPortfolioOverviewView:
    title: str
    state: PortfolioOverviewDetailState
    headline: str
    summary: str
    sections: tuple[DesktopPortfolioOverviewSection, ...] = ()


class _Presentation(Protocol):
    def overview_for_result(self, result: IntelligenceResult | None) -> PortfolioOverviewViewModel: ...


class DesktopPortfolioOverviewRenderer:
    """Format supplied portfolio facts without executing or aggregating them."""

    def render(self, detail: PortfolioOverviewViewModel) -> DesktopPortfolioOverviewView:
        if type(detail) is not PortfolioOverviewViewModel:
            raise TypeError("detail must be a PortfolioOverviewViewModel.")
        if detail.summary is None:
            return DesktopPortfolioOverviewView(
                detail.title, detail.state, _label(detail.state.value), detail.summary_text,
            )
        summary = detail.summary
        ownership = summary.ownership
        sections = (
            DesktopPortfolioOverviewSection(
                "Ownership and Marketplace intelligence coverage",
                "\n".join((
                    f"Portfolio intelligence coverage: {_label(summary.evidence_coverage.value)}",
                    f"Owned entries or copies: {ownership.total_owned_entry_count}",
                    f"Unique owned releases: {ownership.unique_owned_release_count}",
                    f"Matched owned releases: {summary.matched_owned_release_count}",
                    f"Unmatched owned releases: {summary.unmatched_owned_release_count}",
                    f"Usable Marketplace Opportunity releases: {summary.usable_opportunity_release_count}",
                    f"Insufficient Marketplace Opportunity releases: {summary.insufficient_opportunity_release_count}",
                    f"Coverage: {summary.coverage_numerator}/{summary.coverage_denominator} ({summary.coverage_ratio})",
                )),
            ),
            *tuple(_distribution(value) for value in (
                detail.opportunity_distribution,
                detail.momentum_distribution,
                detail.stability_distribution,
                detail.scarcity_distribution,
            ) if value is not None),
            DesktopPortfolioOverviewSection(
                "Largest represented categories",
                "\n".join(
                    f"{_label(value.dimension)}: {_label(value.largest_category) if value.largest_category else 'None'}"
                    f" — {value.largest_category_count} of its {summary.matched_owned_release_count} matched denominator"
                    f" ({value.largest_category_ratio}); {value.represented_category_count} categories represented"
                    for value in detail.concentration_facts
                ) or "No represented categories.",
            ),
            DesktopPortfolioOverviewSection(
                "Owned release detail",
                "\n\n".join(_release(value) for value in detail.releases) or "No valid owned releases.",
            ),
            DesktopPortfolioOverviewSection(
                "Reasons",
                "\n".join(_label(value.value) for value in detail.reason_codes) or "No reason codes.",
            ),
            DesktopPortfolioOverviewSection(
                "Provenance and rule set",
                _provenance(detail),
            ),
            DesktopPortfolioOverviewSection(
                "Diagnostics",
                "\n".join((
                    *(f"{value.code.value}: {value.message}" for value in detail.output_diagnostics),
                    *detail.diagnostics,
                )) or "No diagnostics.",
            ),
        )
        return DesktopPortfolioOverviewView(
            detail.title, detail.state,
            f"Portfolio intelligence coverage: {_label(summary.evidence_coverage.value)}",
            detail.summary_text, sections,
        )


class DesktopPortfolioOverviewController:
    def __init__(self, presentation: _Presentation, renderer: DesktopPortfolioOverviewRenderer | None = None):
        self._presentation = presentation
        self._renderer = renderer or DesktopPortfolioOverviewRenderer()

    def open(self, result: IntelligenceResult | None) -> DesktopPortfolioOverviewView:
        """Render only the already-produced result supplied by the caller."""
        return self._renderer.render(self._presentation.overview_for_result(result))


def _distribution(value):
    wording = "Observed Marketplace Scarcity distribution" if value.dimension == "scarcity" else f"Observed {_label(value.dimension)} distribution"
    body = [
        f"Denominators — all unique owned: {value.all_owned_denominator}; matched: {value.matched_denominator}; usable Opportunity: {value.usable_denominator}"
    ]
    body.extend(
        f"{_label(entry.state)}: {entry.count}; all-owned ratio {entry.all_owned_ratio}; "
        f"matched ratio {entry.matched_ratio}; usable ratio {entry.usable_ratio}; "
        f"release IDs {', '.join(str(item) for item in entry.release_ids) or 'none'}"
        for entry in value.entries
    )
    return DesktopPortfolioOverviewSection(wording, "\n".join(body))


def _release(value):
    return "\n".join((
        f"Release {value.release_id} · {_label(value.match_state.value)} · owned copies {value.quantity}",
        f"Opportunity: {_enum(value.opportunity_assessment)} · evidence {_enum(value.opportunity_evidence_coverage)}",
        f"Momentum: {_enum(value.momentum_assessment)} · evidence {_enum(value.momentum_evidence_coverage)}",
        f"Stability: {_enum(value.stability_assessment)} · evidence {_enum(value.stability_evidence_coverage)}",
        f"Observed Marketplace Scarcity: {_enum(value.scarcity_assessment)} · evidence {_enum(value.scarcity_evidence_coverage)}",
        "Opportunity reasons: " + (", ".join(_label(item) for item in value.opportunity_reason_codes) or "none"),
    ))


def _provenance(detail):
    value = detail.source_provenance
    if value is None:
        return f"Rule set: {detail.rule_set_version or 'Unavailable'}\nNo source provenance supplied."
    return "\n".join((
        f"Portfolio Overview rule set: {detail.rule_set_version}",
        f"Collection snapshot identity: {value.collection_snapshot_id if value.collection_snapshot_id is not None else 'Not supplied'}",
        f"Marketplace Opportunity: {value.opportunity_module_id} {value.opportunity_module_version or 'Unknown'}",
        f"Marketplace Opportunity rule set: {value.opportunity_rule_set_version or 'Unknown'}",
        f"Compatible: {'yes' if value.compatible else 'no'}",
        f"Evidence-window snapshots: {', '.join(value.opportunity_history_snapshot_ids) or 'None supplied'}",
        f"Marketplace Opportunity diagnostics: {'; '.join(value.opportunity_diagnostics) or 'None'}",
    ))


def _enum(value):
    return "Unavailable" if value is None else _label(value.value)


def _label(value):
    return value.replace("_", " ").title()


__all__ = [
    "DesktopPortfolioOverviewController",
    "DesktopPortfolioOverviewRenderer",
    "DesktopPortfolioOverviewSection",
    "DesktopPortfolioOverviewView",
]
