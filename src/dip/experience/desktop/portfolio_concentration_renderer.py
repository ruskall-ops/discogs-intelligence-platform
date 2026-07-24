"""Desktop-neutral rendering for observed Portfolio Concentration."""

from dataclasses import dataclass
from typing import Protocol

from dip.experience.portfolio_concentration import (
    PortfolioConcentrationDetailState,
    PortfolioConcentrationViewModel,
)
from dip.intelligence import IntelligenceResult


@dataclass(frozen=True)
class DesktopPortfolioConcentrationSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopPortfolioConcentrationView:
    title: str
    state: PortfolioConcentrationDetailState
    headline: str
    summary: str
    sections: tuple[DesktopPortfolioConcentrationSection, ...] = ()


class _Presentation(Protocol):
    def concentration_for_result(self, result: IntelligenceResult | None) -> PortfolioConcentrationViewModel: ...


class DesktopPortfolioConcentrationRenderer:
    def render(self, detail):
        if type(detail) is not PortfolioConcentrationViewModel:
            raise TypeError("detail must be PortfolioConcentrationViewModel.")
        if detail.summary is None:
            return DesktopPortfolioConcentrationView(
                detail.title, detail.state, _label(detail.state.value), detail.summary_text,
            )
        summary = detail.summary
        sections = (
            DesktopPortfolioConcentrationSection(
                "Portfolio and evidence",
                "\n".join((
                    f"Unique owned releases: {summary.unique_owned_releases}",
                    f"Owned copies: {summary.total_owned_copies}",
                    f"Portfolio Distribution evidence: {_enum(summary.source_evidence_coverage)}",
                    f"Portfolio Concentration evidence: {_label(summary.evidence_coverage.value)}",
                    f"Analysed dimensions: {', '.join(_label(value) for value in summary.analysed_dimensions) or 'none'}",
                    f"Unusable dimensions: {', '.join(_label(value) for value in summary.unusable_dimensions) or 'none'}",
                )),
            ),
            *(DesktopPortfolioConcentrationSection(
                f"{_label(value.dimension)} observed concentration",
                _dimension(value),
            ) for value in detail.dimensions),
            DesktopPortfolioConcentrationSection(
                "Rules and provenance",
                _provenance(detail),
            ),
            DesktopPortfolioConcentrationSection(
                "Reasons",
                "\n".join(_label(value.value) for value in detail.reason_codes) or "No reason codes.",
            ),
            DesktopPortfolioConcentrationSection(
                "Diagnostics",
                "\n".join((
                    *(f"{value.code.value}: {value.message}" for value in detail.output_diagnostics),
                    *detail.diagnostics,
                )) or "No diagnostics.",
            ),
        )
        return DesktopPortfolioConcentrationView(
            detail.title, detail.state,
            f"Observed concentration evidence: {_label(detail.evidence_coverage.value)}",
            detail.summary_text, sections,
        )


class DesktopPortfolioConcentrationController:
    def __init__(self, presentation: _Presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopPortfolioConcentrationRenderer()

    def open(self, result):
        return self._renderer.render(self._presentation.concentration_for_result(result))


def _dimension(value):
    release = value.release_concentration
    copies = value.copy_concentration
    delta = value.difference
    return "\n".join((
        f"Represented categories: {value.represented_category_count}",
        f"Metadata coverage — releases: {value.release_metadata_coverage_ratio}; copies: {value.copy_metadata_coverage_ratio}",
        f"Largest-category share — releases: {_decimal(release.largest_category_share)}; copies: {_decimal(copies.largest_category_share)}",
        f"Top-three share — releases: {_top(release.top_three)}; copies: {_top(copies.top_three)}",
        f"Top-five share — releases: {_top(release.top_five)}; copies: {_top(copies.top_five)}",
        f"HHI — releases: {_decimal(release.hhi)}; copies: {_decimal(copies.hhi)}",
        f"Normalized HHI — releases: {_decimal(release.normalized_hhi)}; copies: {_decimal(copies.normalized_hhi)}",
        f"Effective category count — releases: {_decimal(release.effective_category_count)}; copies: {_decimal(copies.effective_category_count)}",
        f"Concentration state — releases: {_label(release.state.value)}; copies: {_label(copies.state.value)}",
        f"Release/copy deltas — largest share: {_decimal(delta.largest_category_share_delta)}; top three: {_decimal(delta.top_three_share_delta)}; top five: {_decimal(delta.top_five_share_delta)}; HHI: {_decimal(delta.hhi_delta)}; normalized HHI: {_decimal(delta.normalized_hhi_delta)}; effective categories: {_decimal(delta.effective_category_count_delta)}",
        "Release contributors: " + _contributors(release.top_five),
        "Copy contributors: " + _contributors(copies.top_five),
    ))


def _provenance(detail):
    provenance = detail.provenance
    rules = detail.rule_configuration
    if provenance is None or rules is None:
        return "Concentration provenance is unavailable."
    source = provenance.distribution_provenance
    return "\n".join((
        f"Portfolio Concentration rule set: {detail.rule_set_version}",
        f"Thresholds: dispersed < {rules.dispersed_upper_bound}; moderate < {rules.moderate_upper_bound}; concentrated < {rules.concentrated_upper_bound}",
        f"Top-N values: {rules.top_three_count}, {rules.top_five_count}",
        f"Source: {provenance.source_module_id} {provenance.source_module_version or 'Unknown'}; rule set {provenance.source_rule_set_version or 'Unknown'}",
        f"Collection snapshot identity: {source.collection_snapshot_id if source and source.collection_snapshot_id is not None else 'Not supplied'}",
    ))


def _contributors(value):
    if value is None:
        return "unavailable"
    return ", ".join(
        f"{item.display_name} {item.membership_count}/{item.membership_denominator} ({item.membership_share})"
        for item in value.contributions
    ) or "none"


def _top(value):
    return "Unavailable" if value is None else f"{value.membership_numerator}/{value.membership_denominator} ({value.share})"


def _decimal(value):
    return "Unavailable" if value is None else str(value)


def _enum(value):
    return "Unavailable" if value is None else _label(value.value)


def _label(value):
    return value.replace("_", " ").title()


__all__ = [
    "DesktopPortfolioConcentrationController",
    "DesktopPortfolioConcentrationRenderer",
    "DesktopPortfolioConcentrationSection",
    "DesktopPortfolioConcentrationView",
]
