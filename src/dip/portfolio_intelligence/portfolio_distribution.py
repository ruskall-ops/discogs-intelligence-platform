"""Descriptive aggregation of canonical owned-release metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus


MODULE_ID = "portfolio_distribution"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"


class PortfolioDistributionDomainError(ValueError):
    """Raised when distribution values contradict their visible facts."""


class PortfolioDistributionDimension(str, Enum):
    ARTIST = "artist"
    LABEL = "label"
    FORMAT = "format"
    RELEASE_YEAR = "release_year"
    DECADE = "decade"


class PortfolioDistributionCountingMode(str, Enum):
    SINGLE_VALUE_MEMBERSHIP = "single_value_membership"


class PortfolioDistributionEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class PortfolioDistributionAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class PortfolioDistributionReasonCode(str, Enum):
    COMPLETE_DISTRIBUTION_METADATA = "complete_distribution_metadata"
    PARTIAL_DISTRIBUTION_METADATA = "partial_distribution_metadata"
    LIMITED_DISTRIBUTION_METADATA = "limited_distribution_metadata"
    EMPTY_PORTFOLIO = "empty_portfolio"
    MALFORMED_OWNERSHIP_INPUT = "malformed_ownership_input"
    DUPLICATE_OWNED_RELEASE_NORMALIZED = "duplicate_owned_release_normalized"
    MULTIPLE_OWNED_COPIES = "multiple_owned_copies"
    ARTIST_METADATA_MISSING = "artist_metadata_missing"
    LABEL_METADATA_MISSING = "label_metadata_missing"
    FORMAT_METADATA_MISSING = "format_metadata_missing"
    RELEASE_YEAR_METADATA_MISSING = "release_year_metadata_missing"
    CATEGORY_TIE_PRESENT = "category_tie_present"
    CATEGORY_CONCENTRATION_PRESENT = "category_concentration_present"
    NO_SUPPORTED_METADATA_AVAILABLE = "no_supported_metadata_available"


class PortfolioDistributionDiagnosticCode(str, Enum):
    MALFORMED_RELEASE_IDENTITY = "malformed_release_identity"
    INVALID_OWNERSHIP_QUANTITY = "invalid_ownership_quantity"
    DUPLICATE_OWNERSHIP_ROW_NORMALIZED = "duplicate_ownership_row_normalized"
    CONFLICTING_DUPLICATE_METADATA = "conflicting_duplicate_metadata"
    INVALID_RELEASE_YEAR = "invalid_release_year"
    MISSING_DIMENSION_METADATA = "missing_dimension_metadata"
    DUPLICATE_CATEGORY_VALUE_REMOVED = "duplicate_category_value_removed"
    CONCENTRATION_TIE_RESOLVED = "concentration_tie_resolved"
    NO_USABLE_DISTRIBUTION_METADATA = "no_usable_distribution_metadata"
    EMPTY_PORTFOLIO = "empty_portfolio"


@dataclass(frozen=True)
class PortfolioDistributionRuleConfiguration:
    minimum_release_year: int = 1
    maximum_release_year: int = 9999

    def __post_init__(self) -> None:
        for name in ("minimum_release_year", "maximum_release_year"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer.")
            if value <= 0:
                raise ValueError(f"{name} must be positive.")
        if self.minimum_release_year > self.maximum_release_year:
            raise ValueError("minimum_release_year must not exceed maximum_release_year.")


@dataclass(frozen=True)
class PortfolioReleaseMetadataFact:
    release_id: int
    quantity: int
    artist: str | None = None
    label: str | None = None
    format: str | None = None
    release_year: int | None = None

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _positive(self.quantity, "quantity")
        for name in ("artist", "label", "format"):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value or value != value.strip()):
                raise TypeError(f"{name} must be None or a canonical non-empty string.")
        if self.release_year is not None:
            _positive(self.release_year, "release_year")


@dataclass(frozen=True)
class PortfolioDistributionDiagnostic:
    code: PortfolioDistributionDiagnosticCode
    message: str
    release_id: int | None = None
    dimension: PortfolioDistributionDimension | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not PortfolioDistributionDiagnosticCode:
            raise TypeError("code must be a PortfolioDistributionDiagnosticCode.")
        if type(self.message) is not str or not self.message:
            raise TypeError("message must be a non-empty string.")
        if self.release_id is not None:
            _positive(self.release_id, "release_id")
        if self.dimension is not None and type(self.dimension) is not PortfolioDistributionDimension:
            raise TypeError("dimension must be a PortfolioDistributionDimension.")


@dataclass(frozen=True)
class PortfolioDistributionProvenance:
    collection_snapshot_id: int | None = None
    source_query_id: str = "owned_portfolio_metadata_rows"
    ownership_data_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.collection_snapshot_id is not None:
            _positive(self.collection_snapshot_id, "collection_snapshot_id")
        for name in ("source_query_id", "ownership_data_version"):
            value = getattr(self, name)
            if type(value) is not str or not value:
                raise TypeError(f"{name} must be a non-empty string.")


@dataclass(frozen=True)
class PortfolioDistributionInput:
    releases: tuple[PortfolioReleaseMetadataFact, ...] = ()
    malformed_owned_release_count: int = 0
    provenance: PortfolioDistributionProvenance = PortfolioDistributionProvenance()
    diagnostics: tuple[PortfolioDistributionDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        releases = tuple(self.releases)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not PortfolioReleaseMetadataFact for value in releases):
            raise TypeError("releases contains invalid values.")
        if len({value.release_id for value in releases}) != len(releases):
            raise PortfolioDistributionDomainError("Release facts must be normalized by release_id.")
        if releases != tuple(sorted(releases, key=lambda value: value.release_id)):
            raise PortfolioDistributionDomainError("Release facts must use ascending release order.")
        _non_negative(self.malformed_owned_release_count, "malformed_owned_release_count")
        if type(self.provenance) is not PortfolioDistributionProvenance:
            raise TypeError("provenance must be PortfolioDistributionProvenance.")
        if any(type(value) is not PortfolioDistributionDiagnostic for value in diagnostics):
            raise TypeError("diagnostics contains invalid values.")
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class PortfolioCategoryDistributionEntry:
    category_id: str
    display_name: str
    unique_release_count: int
    owned_copy_count: int
    release_denominator: int
    copy_denominator: int
    release_ratio: Decimal
    copy_ratio: Decimal
    release_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        for name in ("category_id", "display_name"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise TypeError(f"{name} must be a non-empty string.")
        for name in ("unique_release_count", "owned_copy_count", "release_denominator", "copy_denominator"):
            _non_negative(getattr(self, name), name)
        ids = tuple(self.release_ids)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise PortfolioDistributionDomainError("Category release IDs must be unique and ascending.")
        if self.unique_release_count != len(ids):
            raise PortfolioDistributionDomainError("Category release count must equal its release IDs.")
        if self.release_ratio != _ratio(self.unique_release_count, self.release_denominator):
            raise PortfolioDistributionDomainError("Category release ratio is inconsistent.")
        if self.copy_ratio != _ratio(self.owned_copy_count, self.copy_denominator):
            raise PortfolioDistributionDomainError("Category copy ratio is inconsistent.")
        object.__setattr__(self, "release_ids", ids)


@dataclass(frozen=True)
class PortfolioDistributionConcentration:
    largest_category_id: str | None
    largest_category_display_name: str | None
    largest_release_count: int
    largest_copy_count: int
    largest_release_ratio: Decimal
    largest_copy_ratio: Decimal
    tied_largest_category_count: int

    def __post_init__(self) -> None:
        for name in ("largest_release_count", "largest_copy_count", "tied_largest_category_count"):
            _non_negative(getattr(self, name), name)
        for name in ("largest_release_ratio", "largest_copy_ratio"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or value < 0 or value > 1:
                raise ValueError(f"{name} must be a finite Decimal from zero to one.")
        if self.largest_category_id is None:
            if self.largest_category_display_name is not None or any((
                self.largest_release_count, self.largest_copy_count,
                self.tied_largest_category_count,
            )):
                raise PortfolioDistributionDomainError("Empty concentration facts are inconsistent.")


@dataclass(frozen=True)
class PortfolioDimensionDistribution:
    dimension: PortfolioDistributionDimension
    counting_mode: PortfolioDistributionCountingMode
    represented_category_count: int
    releases_with_metadata: int
    releases_missing_metadata: int
    copies_with_metadata: int
    copies_missing_metadata: int
    release_denominator: int
    copy_denominator: int
    release_metadata_coverage_ratio: Decimal
    copy_metadata_coverage_ratio: Decimal
    entries: tuple[PortfolioCategoryDistributionEntry, ...]
    missing_release_ids: tuple[int, ...]
    concentration: PortfolioDistributionConcentration

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        missing = tuple(self.missing_release_ids)
        if type(self.dimension) is not PortfolioDistributionDimension:
            raise TypeError("dimension must be a PortfolioDistributionDimension.")
        if self.counting_mode is not PortfolioDistributionCountingMode.SINGLE_VALUE_MEMBERSHIP:
            raise TypeError("Unsupported counting mode.")
        if entries != tuple(sorted(entries, key=lambda value: _dimension_entry_order(self.dimension, value))):
            raise PortfolioDistributionDomainError("Distribution entries must use canonical order.")
        if missing != tuple(sorted(missing)) or len(set(missing)) != len(missing):
            raise PortfolioDistributionDomainError("Missing release IDs must be unique and ascending.")
        if self.releases_with_metadata + self.releases_missing_metadata != self.release_denominator:
            raise PortfolioDistributionDomainError("Release metadata totals are inconsistent.")
        if self.copies_with_metadata + self.copies_missing_metadata != self.copy_denominator:
            raise PortfolioDistributionDomainError("Copy metadata totals are inconsistent.")
        if sum(value.unique_release_count for value in entries) != self.releases_with_metadata:
            raise PortfolioDistributionDomainError("Single-value release membership total is inconsistent.")
        if sum(value.owned_copy_count for value in entries) != self.copies_with_metadata:
            raise PortfolioDistributionDomainError("Single-value copy membership total is inconsistent.")
        if len(missing) != self.releases_missing_metadata:
            raise PortfolioDistributionDomainError("Missing metadata count is inconsistent.")
        if self.represented_category_count != len(entries):
            raise PortfolioDistributionDomainError("Represented category count is inconsistent.")
        if self.release_metadata_coverage_ratio != _ratio(self.releases_with_metadata, self.release_denominator):
            raise PortfolioDistributionDomainError("Release metadata coverage ratio is inconsistent.")
        if self.copy_metadata_coverage_ratio != _ratio(self.copies_with_metadata, self.copy_denominator):
            raise PortfolioDistributionDomainError("Copy metadata coverage ratio is inconsistent.")
        if self.concentration != _concentration(entries):
            raise PortfolioDistributionDomainError("Concentration facts are inconsistent.")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "missing_release_ids", missing)


@dataclass(frozen=True)
class PortfolioReleaseDistributionDetail:
    release_id: int
    quantity: int
    artist: str | None
    label: str | None
    format: str | None
    release_year: int | None
    decade_start: int | None
    missing_dimensions: tuple[PortfolioDistributionDimension, ...]

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _positive(self.quantity, "quantity")
        missing = tuple(self.missing_dimensions)
        if len(set(missing)) != len(missing) or any(type(value) is not PortfolioDistributionDimension for value in missing):
            raise PortfolioDistributionDomainError("Missing dimensions must be typed and unique.")
        object.__setattr__(self, "missing_dimensions", missing)


@dataclass(frozen=True)
class PortfolioDistributionOwnershipSummary:
    total_owned_copies: int
    unique_owned_releases: int
    duplicate_copy_count: int
    valid_owned_releases: int
    malformed_owned_releases: int

    def __post_init__(self) -> None:
        for name in (
            "total_owned_copies", "unique_owned_releases", "duplicate_copy_count",
            "valid_owned_releases", "malformed_owned_releases",
        ):
            _non_negative(getattr(self, name), name)
        if self.valid_owned_releases != self.unique_owned_releases:
            raise PortfolioDistributionDomainError("Valid and unique release counts are inconsistent.")
        if self.total_owned_copies != self.unique_owned_releases + self.duplicate_copy_count:
            raise PortfolioDistributionDomainError("Owned-copy totals are inconsistent.")


@dataclass(frozen=True)
class PortfolioDistributionSummary:
    ownership: PortfolioDistributionOwnershipSummary
    supported_dimensions: tuple[PortfolioDistributionDimension, ...]
    unavailable_dimensions: tuple[str, ...]
    evidence_coverage: PortfolioDistributionEvidenceCoverage
    total_release_detail_count: int

    def __post_init__(self) -> None:
        if type(self.ownership) is not PortfolioDistributionOwnershipSummary:
            raise TypeError("ownership must be PortfolioDistributionOwnershipSummary.")
        dimensions = tuple(self.supported_dimensions)
        unavailable = tuple(self.unavailable_dimensions)
        if len(set(dimensions)) != len(dimensions) or any(type(value) is not PortfolioDistributionDimension for value in dimensions):
            raise PortfolioDistributionDomainError("Supported dimensions must be typed and unique.")
        if any(type(value) is not str or not value for value in unavailable):
            raise TypeError("Unavailable dimensions must be non-empty strings.")
        if type(self.evidence_coverage) is not PortfolioDistributionEvidenceCoverage:
            raise TypeError("evidence_coverage must be PortfolioDistributionEvidenceCoverage.")
        _non_negative(self.total_release_detail_count, "total_release_detail_count")
        object.__setattr__(self, "supported_dimensions", dimensions)
        object.__setattr__(self, "unavailable_dimensions", unavailable)


@dataclass(frozen=True)
class PortfolioDistributionOutput:
    analysis_state: PortfolioDistributionAnalysisState
    rule_set_version: str
    rule_configuration: PortfolioDistributionRuleConfiguration
    summary: PortfolioDistributionSummary
    dimensions: tuple[PortfolioDimensionDistribution, ...]
    releases: tuple[PortfolioReleaseDistributionDetail, ...]
    reason_codes: tuple[PortfolioDistributionReasonCode, ...]
    provenance: PortfolioDistributionProvenance
    diagnostics: tuple[PortfolioDistributionDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        dimensions = tuple(self.dimensions)
        releases = tuple(self.releases)
        if self.rule_set_version != RULE_SET_VERSION:
            raise PortfolioDistributionDomainError("Unsupported rule-set version.")
        if tuple(value.dimension for value in dimensions) != self.summary.supported_dimensions:
            raise PortfolioDistributionDomainError("Supported dimensions are inconsistent.")
        if releases != tuple(sorted(releases, key=lambda value: value.release_id)):
            raise PortfolioDistributionDomainError("Release details must use ascending release order.")
        if len(releases) != self.summary.total_release_detail_count:
            raise PortfolioDistributionDomainError("Release detail count is inconsistent.")
        if len(releases) != self.summary.ownership.unique_owned_releases:
            raise PortfolioDistributionDomainError("Ownership and release detail counts are inconsistent.")
        expected_denominators = (
            self.summary.ownership.unique_owned_releases,
            self.summary.ownership.total_owned_copies,
        )
        if any(
            (value.release_denominator, value.copy_denominator) != expected_denominators
            for value in dimensions
        ):
            raise PortfolioDistributionDomainError("Distribution denominators are inconsistent.")
        reasons = tuple(self.reason_codes)
        diagnostics = tuple(self.diagnostics)
        if len(set(reasons)) != len(reasons) or any(type(value) is not PortfolioDistributionReasonCode for value in reasons):
            raise PortfolioDistributionDomainError("Reason codes must be typed and unique.")
        if diagnostics != tuple(sorted(diagnostics, key=_diagnostic_order)):
            raise PortfolioDistributionDomainError("Diagnostics must use canonical order.")
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "diagnostics", diagnostics)


_DIMENSIONS = tuple(PortfolioDistributionDimension)
_UNAVAILABLE = ("country", "genre", "style")


class PortfolioDistributionModule:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, rules: PortfolioDistributionRuleConfiguration = PortfolioDistributionRuleConfiguration()):
        if type(rules) is not PortfolioDistributionRuleConfiguration:
            raise TypeError("rules must be PortfolioDistributionRuleConfiguration.")
        self._rules = rules

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        supplied = context.portfolio_distribution_input or PortfolioDistributionInput()
        if type(supplied) is not PortfolioDistributionInput:
            raise TypeError("portfolio_distribution_input must be PortfolioDistributionInput.")
        if any(
            value.release_year is not None
            and not self._rules.minimum_release_year <= value.release_year <= self._rules.maximum_release_year
            for value in supplied.releases
        ):
            raise PortfolioDistributionDomainError(
                "A normalized release year is outside the configured range."
            )
        output = _output(supplied, self._rules)
        status = IntelligenceStatus.SKIPPED if output.analysis_state is PortfolioDistributionAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        return IntelligenceResult(
            MODULE_ID, status,
            "Portfolio Distribution has insufficient canonical ownership metadata."
            if status is IntelligenceStatus.SKIPPED
            else f"Described ownership distribution for {output.summary.ownership.unique_owned_releases} release"
            f"{'' if output.summary.ownership.unique_owned_releases == 1 else 's'}.",
            metrics={"output": output},
            evidence=tuple(f"Release {value.release_id} contributes canonical ownership metadata." for value in output.releases),
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in output.diagnostics),
            module_version=MODULE_VERSION,
        )


def _output(supplied, rules):
    releases = tuple(_detail(value) for value in supplied.releases)
    dimensions = tuple(_dimension(dimension, supplied.releases) for dimension in _DIMENSIONS)
    usable = tuple(value for value in dimensions if value.releases_with_metadata)
    complete = all(value.releases_missing_metadata == 0 for value in dimensions) and bool(releases)
    if complete:
        coverage = PortfolioDistributionEvidenceCoverage.COMPLETE
    elif len(usable) == len(dimensions):
        coverage = PortfolioDistributionEvidenceCoverage.PARTIAL
    elif usable:
        coverage = PortfolioDistributionEvidenceCoverage.LIMITED
    else:
        coverage = PortfolioDistributionEvidenceCoverage.INSUFFICIENT
    ownership = PortfolioDistributionOwnershipSummary(
        sum(value.quantity for value in supplied.releases), len(releases),
        sum(value.quantity - 1 for value in supplied.releases), len(releases),
        supplied.malformed_owned_release_count,
    )
    summary = PortfolioDistributionSummary(ownership, _DIMENSIONS, _UNAVAILABLE, coverage, len(releases))
    diagnostics = _diagnostics(supplied, dimensions, releases)
    reasons = _reasons(summary, dimensions, supplied)
    state = (
        PortfolioDistributionAnalysisState.INSUFFICIENT_DATA
        if coverage is PortfolioDistributionEvidenceCoverage.INSUFFICIENT
        else PortfolioDistributionAnalysisState.COMPLETE
        if coverage is PortfolioDistributionEvidenceCoverage.COMPLETE and not supplied.diagnostics
        else PortfolioDistributionAnalysisState.PARTIAL
    )
    return PortfolioDistributionOutput(
        state, RULE_SET_VERSION, rules, summary, dimensions, releases,
        reasons, supplied.provenance, diagnostics,
    )


def _detail(value):
    decade = None if value.release_year is None else (value.release_year // 10) * 10
    missing = tuple(
        dimension for dimension in _DIMENSIONS
        if _value(value, dimension) is None
    )
    return PortfolioReleaseDistributionDetail(
        value.release_id, value.quantity, value.artist, value.label, value.format,
        value.release_year, decade, missing,
    )


def _dimension(dimension, releases):
    categories = {}
    missing = []
    for release in releases:
        category = _value(release, dimension)
        if category is None:
            missing.append(release)
            continue
        category_id, display = category
        categories.setdefault((category_id, display), []).append(release)
    total_copies = sum(value.quantity for value in releases)
    entries = tuple(sorted((
        PortfolioCategoryDistributionEntry(
            category_id, display, len(values), sum(value.quantity for value in values),
            len(releases), total_copies,
            _ratio(len(values), len(releases)),
            _ratio(sum(value.quantity for value in values), total_copies),
            tuple(value.release_id for value in values),
        )
        for (category_id, display), values in categories.items()
    ), key=lambda value: _dimension_entry_order(dimension, value)))
    return PortfolioDimensionDistribution(
        dimension, PortfolioDistributionCountingMode.SINGLE_VALUE_MEMBERSHIP,
        len(entries), len(releases) - len(missing), len(missing),
        total_copies - sum(value.quantity for value in missing),
        sum(value.quantity for value in missing), len(releases), total_copies,
        _ratio(len(releases) - len(missing), len(releases)),
        _ratio(total_copies - sum(value.quantity for value in missing), total_copies),
        entries, tuple(value.release_id for value in missing), _concentration(entries),
    )


def _value(release, dimension):
    if dimension is PortfolioDistributionDimension.ARTIST:
        return None if release.artist is None else (release.artist, release.artist)
    if dimension is PortfolioDistributionDimension.LABEL:
        return None if release.label is None else (release.label, release.label)
    if dimension is PortfolioDistributionDimension.FORMAT:
        return None if release.format is None else (release.format, release.format)
    if dimension is PortfolioDistributionDimension.RELEASE_YEAR:
        return None if release.release_year is None else (str(release.release_year), str(release.release_year))
    if dimension is PortfolioDistributionDimension.DECADE:
        if release.release_year is None:
            return None
        decade = (release.release_year // 10) * 10
        return str(decade), f"{decade}s"
    raise PortfolioDistributionDomainError("Unsupported distribution dimension.")


def _concentration(entries):
    if not entries:
        return PortfolioDistributionConcentration(None, None, 0, 0, Decimal("0"), Decimal("0"), 0)
    largest = sorted(entries, key=_entry_order)[0]
    tied = sum(
        value.unique_release_count == largest.unique_release_count
        and value.owned_copy_count == largest.owned_copy_count
        for value in entries
    )
    return PortfolioDistributionConcentration(
        largest.category_id, largest.display_name, largest.unique_release_count,
        largest.owned_copy_count, largest.release_ratio, largest.copy_ratio, tied,
    )


def _diagnostics(supplied, dimensions, releases):
    values = list(supplied.diagnostics)
    if not releases:
        values.append(PortfolioDistributionDiagnostic(
            PortfolioDistributionDiagnosticCode.EMPTY_PORTFOLIO,
            "No valid owned releases were supplied.",
        ))
    for dimension in dimensions:
        for release_id in dimension.missing_release_ids:
            values.append(PortfolioDistributionDiagnostic(
                PortfolioDistributionDiagnosticCode.MISSING_DIMENSION_METADATA,
                f"Release {release_id} has no usable {dimension.dimension.value} metadata.",
                release_id, dimension.dimension,
            ))
        if dimension.concentration.tied_largest_category_count > 1:
            values.append(PortfolioDistributionDiagnostic(
                PortfolioDistributionDiagnosticCode.CONCENTRATION_TIE_RESOLVED,
                f"{dimension.dimension.value} has a canonically resolved largest-category tie.",
                dimension=dimension.dimension,
            ))
    if releases and not any(value.releases_with_metadata for value in dimensions):
        values.append(PortfolioDistributionDiagnostic(
            PortfolioDistributionDiagnosticCode.NO_USABLE_DISTRIBUTION_METADATA,
            "No supported dimension contains usable metadata.",
        ))
    return tuple(sorted(values, key=_diagnostic_order))


def _reasons(summary, dimensions, supplied):
    values = []
    coverage = summary.evidence_coverage
    values.append({
        PortfolioDistributionEvidenceCoverage.COMPLETE: PortfolioDistributionReasonCode.COMPLETE_DISTRIBUTION_METADATA,
        PortfolioDistributionEvidenceCoverage.PARTIAL: PortfolioDistributionReasonCode.PARTIAL_DISTRIBUTION_METADATA,
        PortfolioDistributionEvidenceCoverage.LIMITED: PortfolioDistributionReasonCode.LIMITED_DISTRIBUTION_METADATA,
        PortfolioDistributionEvidenceCoverage.INSUFFICIENT: PortfolioDistributionReasonCode.NO_SUPPORTED_METADATA_AVAILABLE,
    }[coverage])
    if summary.ownership.unique_owned_releases == 0:
        values.append(PortfolioDistributionReasonCode.EMPTY_PORTFOLIO)
    if supplied.malformed_owned_release_count:
        values.append(PortfolioDistributionReasonCode.MALFORMED_OWNERSHIP_INPUT)
    if any(value.code is PortfolioDistributionDiagnosticCode.DUPLICATE_OWNERSHIP_ROW_NORMALIZED for value in supplied.diagnostics):
        values.append(PortfolioDistributionReasonCode.DUPLICATE_OWNED_RELEASE_NORMALIZED)
    if summary.ownership.duplicate_copy_count:
        values.append(PortfolioDistributionReasonCode.MULTIPLE_OWNED_COPIES)
    missing_codes = {
        PortfolioDistributionDimension.ARTIST: PortfolioDistributionReasonCode.ARTIST_METADATA_MISSING,
        PortfolioDistributionDimension.LABEL: PortfolioDistributionReasonCode.LABEL_METADATA_MISSING,
        PortfolioDistributionDimension.FORMAT: PortfolioDistributionReasonCode.FORMAT_METADATA_MISSING,
        PortfolioDistributionDimension.RELEASE_YEAR: PortfolioDistributionReasonCode.RELEASE_YEAR_METADATA_MISSING,
        PortfolioDistributionDimension.DECADE: PortfolioDistributionReasonCode.RELEASE_YEAR_METADATA_MISSING,
    }
    for dimension in dimensions:
        code = missing_codes[dimension.dimension]
        if dimension.releases_missing_metadata and code not in values:
            values.append(code)
        if dimension.concentration.tied_largest_category_count > 1 and PortfolioDistributionReasonCode.CATEGORY_TIE_PRESENT not in values:
            values.append(PortfolioDistributionReasonCode.CATEGORY_TIE_PRESENT)
        if any(value.unique_release_count > 1 for value in dimension.entries) and PortfolioDistributionReasonCode.CATEGORY_CONCENTRATION_PRESENT not in values:
            values.append(PortfolioDistributionReasonCode.CATEGORY_CONCENTRATION_PRESENT)
    return tuple(values)


def _entry_order(value):
    return (-value.unique_release_count, -value.owned_copy_count, value.display_name.casefold(), value.category_id)


def _dimension_entry_order(dimension, value):
    if dimension is PortfolioDistributionDimension.DECADE:
        return (int(value.category_id),)
    return _entry_order(value)


def _diagnostic_order(value):
    return (
        tuple(PortfolioDistributionDiagnosticCode).index(value.code),
        -1 if value.release_id is None else value.release_id,
        -1 if value.dimension is None else tuple(PortfolioDistributionDimension).index(value.dimension),
        value.message,
    )


def _ratio(numerator, denominator):
    return Decimal("0") if denominator == 0 else Decimal(numerator) / Decimal(denominator)


def _positive(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _non_negative(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must not be negative.")
