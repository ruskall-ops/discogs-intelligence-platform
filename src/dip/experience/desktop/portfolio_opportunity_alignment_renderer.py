"""Neutral desktop rendering of already-produced Alignment intelligence."""

from dataclasses import dataclass

from dip.experience.portfolio_opportunity_alignment import PortfolioOpportunityAlignmentViewModel


@dataclass(frozen=True)
class DesktopPortfolioOpportunityAlignmentSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopPortfolioOpportunityAlignmentView:
    title: str
    state: object
    headline: str
    summary: str
    sections: tuple[DesktopPortfolioOpportunityAlignmentSection, ...] = ()


class DesktopPortfolioOpportunityAlignmentRenderer:
    def render(self, detail):
        if type(detail) is not PortfolioOpportunityAlignmentViewModel:
            raise TypeError("detail must be PortfolioOpportunityAlignmentViewModel.")
        if detail.summary is None or detail.breadth is None:
            return DesktopPortfolioOpportunityAlignmentView(
                detail.title, detail.state, _label(detail.state.value), detail.summary_text,
            )
        summary, breadth = detail.summary, detail.breadth
        mapped = tuple(
            f"{_label(value.category.value)}: releases {value.release_count}/{value.release_denominator} ({value.release_share}); "
            f"copies {value.copy_count}/{value.copy_denominator} ({value.copy_share}); IDs {_ids(value.release_ids)}"
            for value in breadth.mapping_entries
        )
        sections = (
            DesktopPortfolioOpportunityAlignmentSection(
                "Portfolio and evidence",
                "\n".join((
                    f"Alignment evidence: {_label(summary.evidence_coverage.value)}",
                    f"Portfolio Overview evidence: {_enum(summary.overview_evidence)}",
                    f"Portfolio Distribution evidence: {_enum(summary.distribution_evidence)}",
                    f"Portfolio Concentration evidence: {_enum(summary.concentration_evidence)}",
                    f"Valid owned releases: {breadth.valid_owned_releases}",
                    f"Owned copies: {breadth.total_owned_copies}",
                    f"Matched releases: {breadth.matched_releases}",
                    f"Unmatched releases: {breadth.unmatched_releases}",
                    "Original Opportunity assessments: " + (
                        ", ".join(
                            f"{value.state} {value.count}/{breadth.source_opportunity_distribution.all_owned_denominator}"
                            for value in breadth.source_opportunity_distribution.entries
                        ) if breadth.source_opportunity_distribution else "unavailable"
                    ),
                    *mapped,
                )),
            ),
            *(DesktopPortfolioOpportunityAlignmentSection(
                f"{_label(value.dimension)} observed alignment",
                "\n".join((
                    f"Metadata coverage — releases: {value.metadata_release_coverage}; copies: {value.metadata_copy_coverage}",
                    f"Concentration context — releases: {_label(value.release_concentration_context.value)} ({_label(value.release_concentration_state.value)}); copies: {_label(value.copy_concentration_context.value)} ({_label(value.copy_concentration_state.value)})",
                    f"Observed normalized HHI — releases: {value.release_concentration.normalized_hhi}; copies: {value.copy_concentration.normalized_hhi}",
                    f"Observed effective category count — releases: {value.release_concentration.effective_category_count}; copies: {value.copy_concentration.effective_category_count}",
                    "Dominant categories: " + ", ".join(item.display_name for item in value.largest_categories),
                    "Top three categories: " + ", ".join(item.display_name for item in value.top_three_categories),
                    "Top five categories: " + ", ".join(item.display_name for item in value.top_five_categories),
                    *(f"{item.display_name}: {_label(item.alignment_category.value)}; releases {_ids(item.release_ids)}" for item in value.categories),
                )),
            ) for value in detail.dimensions),
            DesktopPortfolioOpportunityAlignmentSection("Rules and provenance", _provenance(detail)),
            DesktopPortfolioOpportunityAlignmentSection("Reasons", "\n".join(_label(value.value) for value in detail.reason_codes)),
            DesktopPortfolioOpportunityAlignmentSection(
                "Diagnostics",
                "\n".join((*(f"{value.code.value}: {value.message}" for value in detail.output_diagnostics), *detail.diagnostics)) or "No diagnostics.",
            ),
        )
        return DesktopPortfolioOpportunityAlignmentView(
            detail.title, detail.state, f"Observed alignment: {_label(summary.assessment.value)}",
            detail.summary_text, sections,
        )


class DesktopPortfolioOpportunityAlignmentController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopPortfolioOpportunityAlignmentRenderer()

    def open(self, result):
        return self._renderer.render(self._presentation.alignment_for_result(result))


def _provenance(detail):
    p, r = detail.provenance, detail.rule_configuration
    return "\n".join((
        f"Alignment rule set: {detail.rule_set_version}",
        f"Thresholds — broad usable: {r.broad_usable_coverage_minimum}; limited usable: {r.limited_usable_coverage_boundary}; meaningful support: {r.meaningful_supportive_share_minimum}; broad support: {r.broad_supportive_share_minimum}; limiting plus adverse: {r.constraining_limiting_adverse_share}; adverse: {r.strongly_adverse_share}; unusable: {r.constraining_unusable_share}",
        f"Sources — Overview {p.overview_module_version}; Distribution {p.distribution_module_version}; Concentration {p.concentration_module_version}",
        f"Collection snapshot identity: {p.collection_snapshot_id if p.collection_snapshot_id is not None else 'Not supplied'}",
        f"Supported dimensions: {', '.join(_label(value) for value in p.supported_dimensions) or 'none'}",
        f"Unusable dimensions: {', '.join(_label(value) for value in p.unusable_dimensions) or 'none'}",
    ))


def _ids(values): return ", ".join(str(value) for value in values) or "none"
def _enum(value): return "Unavailable" if value is None else _label(value.value)
def _label(value): return value.replace("_", " ").title()


__all__ = [
    "DesktopPortfolioOpportunityAlignmentController",
    "DesktopPortfolioOpportunityAlignmentRenderer",
    "DesktopPortfolioOpportunityAlignmentView",
]
