"""Desktop-neutral rendering for descriptive Portfolio Distribution."""

from dataclasses import dataclass
from typing import Protocol

from dip.experience.portfolio_distribution import (
    PortfolioDistributionDetailState,
    PortfolioDistributionViewModel,
)
from dip.intelligence import IntelligenceResult


@dataclass(frozen=True)
class DesktopPortfolioDistributionSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopPortfolioDistributionView:
    title: str
    state: PortfolioDistributionDetailState
    headline: str
    summary: str
    sections: tuple[DesktopPortfolioDistributionSection, ...] = ()


class _Presentation(Protocol):
    def distribution_for_result(self, result: IntelligenceResult | None) -> PortfolioDistributionViewModel: ...


class DesktopPortfolioDistributionRenderer:
    def render(self, detail):
        if type(detail) is not PortfolioDistributionViewModel:
            raise TypeError("detail must be PortfolioDistributionViewModel.")
        if detail.summary is None:
            return DesktopPortfolioDistributionView(
                detail.title, detail.state, _label(detail.state.value), detail.summary_text,
            )
        ownership = detail.summary.ownership
        sections = (
            DesktopPortfolioDistributionSection(
                "Ownership and metadata coverage",
                "\n".join((
                    f"Metadata coverage: {_label(detail.evidence_coverage.value)}",
                    f"Unique owned releases: {ownership.unique_owned_releases}",
                    f"Owned copies: {ownership.total_owned_copies}",
                    f"Duplicate copies: {ownership.duplicate_copy_count}",
                    "Supported dimensions: " + ", ".join(_label(value.value) for value in detail.summary.supported_dimensions),
                    "Unavailable dimensions: " + ", ".join(_label(value) for value in detail.summary.unavailable_dimensions),
                )),
            ),
            *(DesktopPortfolioDistributionSection(
                f"{_label(value.dimension.value)} distribution",
                _dimension(value),
            ) for value in detail.dimensions),
            DesktopPortfolioDistributionSection(
                "Owned release metadata",
                "\n".join(
                    f"Release {value.release_id} · copies {value.quantity} · "
                    f"artist {value.artist or 'missing'} · label {value.label or 'missing'} · "
                    f"format {value.format or 'missing'} · year {value.release_year or 'missing'} · "
                    f"decade {str(value.decade_start) + 's' if value.decade_start is not None else 'missing'}"
                    for value in detail.releases
                ) or "No valid owned releases.",
            ),
            DesktopPortfolioDistributionSection(
                "Reasons",
                "\n".join(_label(value.value) for value in detail.reason_codes) or "No reason codes.",
            ),
            DesktopPortfolioDistributionSection(
                "Provenance and rule set",
                "\n".join((
                    f"Portfolio Distribution rule set: {detail.rule_set_version}",
                    f"Collection snapshot identity: {detail.provenance.collection_snapshot_id if detail.provenance and detail.provenance.collection_snapshot_id is not None else 'Not supplied'}",
                    f"Source query: {detail.provenance.source_query_id if detail.provenance else 'Not supplied'}",
                    f"Ownership data version: {detail.provenance.ownership_data_version if detail.provenance else 'Not supplied'}",
                )),
            ),
            DesktopPortfolioDistributionSection(
                "Diagnostics",
                "\n".join((
                    *(f"{value.code.value}: {value.message}" for value in detail.output_diagnostics),
                    *detail.diagnostics,
                )) or "No diagnostics.",
            ),
        )
        return DesktopPortfolioDistributionView(
            detail.title, detail.state,
            f"Portfolio distribution metadata: {_label(detail.evidence_coverage.value)}",
            detail.summary_text, sections,
        )


class DesktopPortfolioDistributionController:
    def __init__(self, presentation: _Presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopPortfolioDistributionRenderer()

    def open(self, result):
        return self._renderer.render(self._presentation.distribution_for_result(result))


def _dimension(value):
    concentration = value.concentration
    lines = [
        f"Counting mode: {_label(value.counting_mode.value)}",
        f"Represented categories: {value.represented_category_count}",
        f"Releases with metadata: {value.releases_with_metadata}/{value.release_denominator} ({value.release_metadata_coverage_ratio})",
        f"Copies with metadata: {value.copies_with_metadata}/{value.copy_denominator} ({value.copy_metadata_coverage_ratio})",
        f"Releases without metadata: {value.releases_missing_metadata}; IDs: {', '.join(str(item) for item in value.missing_release_ids) or 'none'}",
        f"Largest represented category: {concentration.largest_category_display_name or 'None'}; tied categories: {concentration.tied_largest_category_count}",
    ]
    lines.extend(
        f"{entry.display_name}: releases {entry.unique_release_count}/{entry.release_denominator} ({entry.release_ratio}); "
        f"copies {entry.owned_copy_count}/{entry.copy_denominator} ({entry.copy_ratio}); "
        f"release IDs {', '.join(str(item) for item in entry.release_ids)}"
        for entry in value.entries
    )
    return "\n".join(lines)


def _label(value):
    return value.replace("_", " ").title()


__all__ = [
    "DesktopPortfolioDistributionController",
    "DesktopPortfolioDistributionRenderer",
    "DesktopPortfolioDistributionSection",
    "DesktopPortfolioDistributionView",
]
