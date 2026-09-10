"""Transparent concentration analysis over Portfolio Distribution facts."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from .portfolio_distribution import (
    MODULE_ID as DISTRIBUTION_MODULE_ID,
    MODULE_VERSION as DISTRIBUTION_MODULE_VERSION,
    PortfolioCategoryDistributionEntry,
    PortfolioDimensionDistribution,
    PortfolioDistributionEvidenceCoverage,
    PortfolioDistributionOutput,
    PortfolioDistributionProvenance,
    validate_portfolio_distribution_output,
)


MODULE_ID = "portfolio_concentration"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"


class PortfolioConcentrationDomainError(ValueError):
    """Raised when concentration facts are internally inconsistent."""


class PortfolioConcentrationAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class PortfolioConcentrationBasis(str, Enum):
    RELEASE_MEMBERSHIP = "release_membership"
    COPY_MEMBERSHIP = "copy_membership"


class PortfolioConcentrationState(str, Enum):
    DISPERSED = "dispersed"
    MODERATE = "moderate"
    CONCENTRATED = "concentrated"
    HIGHLY_CONCENTRATED = "highly_concentrated"
    INSUFFICIENT = "insufficient"


class PortfolioConcentrationEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class PortfolioConcentrationReasonCode(str, Enum):
    COMPLETE_CONCENTRATION_EVIDENCE = "complete_concentration_evidence"
    PARTIAL_CONCENTRATION_EVIDENCE = "partial_concentration_evidence"
    LIMITED_CONCENTRATION_EVIDENCE = "limited_concentration_evidence"
    EMPTY_PORTFOLIO = "empty_portfolio"
    MISSING_DISTRIBUTION_SOURCE = "missing_distribution_source"
    UNSUPPORTED_DISTRIBUTION_VERSION = "unsupported_distribution_version"
    UNSUPPORTED_DISTRIBUTION_RULE_SET = "unsupported_distribution_rule_set"
    MALFORMED_DISTRIBUTION_OUTPUT = "malformed_distribution_output"
    DIMENSION_ANALYSED = "dimension_analysed"
    DIMENSION_WITHOUT_CATEGORIES = "dimension_without_categories"
    DIMENSION_METADATA_INCOMPLETE = "dimension_metadata_incomplete"
    SINGLE_CATEGORY_DISTRIBUTION = "single_category_distribution"
    MULTIPLE_CATEGORY_DISTRIBUTION = "multiple_category_distribution"
    LARGEST_CATEGORY_TIE = "largest_category_tie"
    TOP_THREE_COVERS_ALL_CATEGORIES = "top_three_covers_all_categories"
    TOP_FIVE_COVERS_ALL_CATEGORIES = "top_five_covers_all_categories"
    RELEASE_COPY_CONCENTRATION_EQUAL = "release_copy_concentration_equal"
    COPY_CONCENTRATION_EXCEEDS_RELEASE_CONCENTRATION = "copy_concentration_exceeds_release_concentration"
    RELEASE_CONCENTRATION_EXCEEDS_COPY_CONCENTRATION = "release_concentration_exceeds_copy_concentration"
    NORMALIZED_HHI_AVAILABLE = "normalized_hhi_available"
    NORMALIZED_HHI_SINGLE_CATEGORY = "normalized_hhi_single_category"
    CONCENTRATION_STATE_DISPERSED = "concentration_state_dispersed"
    CONCENTRATION_STATE_MODERATE = "concentration_state_moderate"
    CONCENTRATION_STATE_CONCENTRATED = "concentration_state_concentrated"
    CONCENTRATION_STATE_HIGHLY_CONCENTRATED = "concentration_state_highly_concentrated"
    NO_USABLE_CONCENTRATION_DIMENSIONS = "no_usable_concentration_dimensions"


class PortfolioConcentrationDiagnosticCode(str, Enum):
    MISSING_DISTRIBUTION_SOURCE = "missing_distribution_source"
    SOURCE_MODULE_MISMATCH = "source_module_mismatch"
    UNSUPPORTED_SOURCE_VERSION = "unsupported_source_version"
    UNSUPPORTED_SOURCE_RULE_SET = "unsupported_source_rule_set"
    MALFORMED_SOURCE_OUTPUT = "malformed_source_output"
    SOURCE_NOT_COMPLETED = "source_not_completed"
    SOURCE_DIAGNOSTIC_PRESERVED = "source_diagnostic_preserved"
    ZERO_MEMBERSHIP_DENOMINATOR = "zero_membership_denominator"
    NO_USABLE_CATEGORIES = "no_usable_categories"


@dataclass(frozen=True)
class PortfolioConcentrationRuleConfiguration:
    dispersed_upper_bound: Decimal = Decimal("0.20")
    moderate_upper_bound: Decimal = Decimal("0.40")
    concentrated_upper_bound: Decimal = Decimal("0.65")
    top_three_count: int = 3
    top_five_count: int = 5

    def __post_init__(self) -> None:
        bounds = (
            self.dispersed_upper_bound,
            self.moderate_upper_bound,
            self.concentrated_upper_bound,
        )
        if any(type(value) is not Decimal for value in bounds):
            raise TypeError("Concentration bounds must be Decimals.")
        if not Decimal("0") <= bounds[0] < bounds[1] < bounds[2] <= Decimal("1"):
            raise ValueError("Concentration bounds must be increasing from zero through one.")
        for name in ("top_three_count", "top_five_count"):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer.")
            if value <= 0:
                raise ValueError(f"{name} must be positive.")
        if self.top_three_count >= self.top_five_count:
            raise ValueError("top_three_count must be less than top_five_count.")


@dataclass(frozen=True)
class PortfolioConcentrationDiagnostic:
    code: PortfolioConcentrationDiagnosticCode
    message: str

    def __post_init__(self) -> None:
        if type(self.code) is not PortfolioConcentrationDiagnosticCode:
            raise TypeError("code must be PortfolioConcentrationDiagnosticCode.")
        if type(self.message) is not str or not self.message:
            raise TypeError("message must be a non-empty string.")


@dataclass(frozen=True)
class PortfolioConcentrationProvenance:
    source_module_id: str
    source_module_version: str | None
    source_rule_set_version: str | None
    source_evidence_coverage: PortfolioDistributionEvidenceCoverage | None
    distribution_provenance: PortfolioDistributionProvenance | None
    supported_dimensions: tuple[str, ...] = ()
    analysed_dimensions: tuple[str, ...] = ()
    unusable_dimensions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("source_module_id",):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise TypeError(f"{name} must be a non-empty string.")
        for name in ("supported_dimensions", "analysed_dimensions", "unusable_dimensions"):
            values = tuple(getattr(self, name))
            if any(type(value) is not str or not value for value in values):
                raise TypeError(f"{name} must contain non-empty strings.")
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class PortfolioConcentrationInput:
    source_compatible: bool
    source_provenance: PortfolioConcentrationProvenance
    dimensions: tuple[PortfolioDimensionDistribution, ...] = ()
    unique_owned_releases: int = 0
    total_owned_copies: int = 0
    duplicate_copy_count: int = 0
    diagnostics: tuple[PortfolioConcentrationDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        dimensions = tuple(self.dimensions)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not PortfolioDimensionDistribution for value in dimensions):
            raise TypeError("dimensions contains invalid values.")
        if len({value.dimension for value in dimensions}) != len(dimensions):
            raise PortfolioConcentrationDomainError("Concentration input dimensions must be unique.")
        for name in ("unique_owned_releases", "total_owned_copies", "duplicate_copy_count"):
            _non_negative(getattr(self, name), name)
        if self.total_owned_copies != self.unique_owned_releases + self.duplicate_copy_count:
            raise PortfolioConcentrationDomainError("Concentration ownership totals are inconsistent.")
        if any(type(value) is not PortfolioConcentrationDiagnostic for value in diagnostics):
            raise TypeError("diagnostics contains invalid values.")
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class PortfolioCategoryContribution:
    category_id: str
    display_name: str
    membership_count: int
    membership_denominator: int
    membership_share: Decimal
    release_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.category_id) is not str or not self.category_id:
            raise TypeError("category_id must be a non-empty string.")
        if type(self.display_name) is not str or not self.display_name:
            raise TypeError("display_name must be a non-empty string.")
        _non_negative(self.membership_count, "membership_count")
        _non_negative(self.membership_denominator, "membership_denominator")
        if self.membership_share != _ratio(self.membership_count, self.membership_denominator):
            raise PortfolioConcentrationDomainError("Category membership share is inconsistent.")
        ids = tuple(self.release_ids)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise PortfolioConcentrationDomainError("Contribution release IDs must be unique and ascending.")
        object.__setattr__(self, "release_ids", ids)


@dataclass(frozen=True)
class PortfolioTopNConcentration:
    requested_count: int
    included_category_count: int
    membership_numerator: int
    membership_denominator: int
    share: Decimal
    contributions: tuple[PortfolioCategoryContribution, ...]

    def __post_init__(self) -> None:
        for name in ("requested_count", "included_category_count"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer.")
        _non_negative(self.membership_numerator, "membership_numerator")
        _non_negative(self.membership_denominator, "membership_denominator")
        contributions = tuple(self.contributions)
        if self.included_category_count != len(contributions):
            raise PortfolioConcentrationDomainError("Top-N included count is inconsistent.")
        if self.membership_numerator != sum(value.membership_count for value in contributions):
            raise PortfolioConcentrationDomainError("Top-N numerator is inconsistent.")
        if self.share != _ratio(self.membership_numerator, self.membership_denominator):
            raise PortfolioConcentrationDomainError("Top-N share is inconsistent.")
        object.__setattr__(self, "contributions", contributions)


@dataclass(frozen=True)
class PortfolioConcentrationMetricSet:
    basis: PortfolioConcentrationBasis
    membership_total: int
    represented_category_count: int
    largest_membership_count: int
    largest_membership_denominator: int
    largest_category_share: Decimal | None
    largest_categories: tuple[PortfolioCategoryContribution, ...]
    top_three: PortfolioTopNConcentration | None
    top_five: PortfolioTopNConcentration | None
    hhi: Decimal | None
    normalized_hhi: Decimal | None
    effective_category_count: Decimal | None
    state: PortfolioConcentrationState

    def __post_init__(self) -> None:
        if type(self.basis) is not PortfolioConcentrationBasis:
            raise TypeError("basis must be PortfolioConcentrationBasis.")
        for name in (
            "membership_total", "represented_category_count",
            "largest_membership_count", "largest_membership_denominator",
        ):
            _non_negative(getattr(self, name), name)
        for name in ("largest_category_share", "hhi", "normalized_hhi"):
            _optional_unit_decimal(getattr(self, name), name)
        if self.effective_category_count is not None:
            if type(self.effective_category_count) is not Decimal or self.effective_category_count < 1:
                raise ValueError("effective_category_count must be None or a Decimal of at least one.")
        if type(self.state) is not PortfolioConcentrationState:
            raise TypeError("state must be PortfolioConcentrationState.")
        largest = tuple(self.largest_categories)
        if self.largest_category_share != (
            None if self.membership_total == 0
            else _ratio(self.largest_membership_count, self.membership_total)
        ):
            raise PortfolioConcentrationDomainError("Largest-category share is inconsistent.")
        object.__setattr__(self, "largest_categories", largest)


@dataclass(frozen=True)
class PortfolioConcentrationDifference:
    largest_category_share_delta: Decimal | None
    top_three_share_delta: Decimal | None
    top_five_share_delta: Decimal | None
    hhi_delta: Decimal | None
    normalized_hhi_delta: Decimal | None
    effective_category_count_delta: Decimal | None

    def __post_init__(self) -> None:
        for name in (
            "largest_category_share_delta", "top_three_share_delta",
            "top_five_share_delta", "hhi_delta", "normalized_hhi_delta",
            "effective_category_count_delta",
        ):
            value = getattr(self, name)
            if value is not None and type(value) is not Decimal:
                raise TypeError(f"{name} must be None or a Decimal.")


@dataclass(frozen=True)
class PortfolioDimensionConcentration:
    dimension: str
    represented_category_count: int
    releases_with_metadata: int
    releases_missing_metadata: int
    copies_with_metadata: int
    copies_missing_metadata: int
    release_metadata_coverage_ratio: Decimal
    copy_metadata_coverage_ratio: Decimal
    missing_release_ids: tuple[int, ...]
    source_entries: tuple[PortfolioCategoryDistributionEntry, ...]
    release_concentration: PortfolioConcentrationMetricSet
    copy_concentration: PortfolioConcentrationMetricSet
    difference: PortfolioConcentrationDifference
    reason_codes: tuple[PortfolioConcentrationReasonCode, ...]

    def __post_init__(self) -> None:
        entries = tuple(self.source_entries)
        reasons = tuple(self.reason_codes)
        missing = tuple(self.missing_release_ids)
        if self.represented_category_count != len(entries):
            raise PortfolioConcentrationDomainError("Represented category count is inconsistent.")
        if len(set(reasons)) != len(reasons) or any(type(value) is not PortfolioConcentrationReasonCode for value in reasons):
            raise PortfolioConcentrationDomainError("Dimension reason codes must be typed and unique.")
        if missing != tuple(sorted(missing)) or len(set(missing)) != len(missing):
            raise PortfolioConcentrationDomainError("Missing release IDs must be unique and ascending.")
        object.__setattr__(self, "source_entries", entries)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "missing_release_ids", missing)


@dataclass(frozen=True)
class PortfolioConcentrationSummary:
    unique_owned_releases: int
    total_owned_copies: int
    duplicate_copy_count: int
    source_evidence_coverage: PortfolioDistributionEvidenceCoverage | None
    evidence_coverage: PortfolioConcentrationEvidenceCoverage
    supported_dimensions: tuple[str, ...]
    analysed_dimensions: tuple[str, ...]
    unusable_dimensions: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("unique_owned_releases", "total_owned_copies", "duplicate_copy_count"):
            _non_negative(getattr(self, name), name)
        if self.total_owned_copies != self.unique_owned_releases + self.duplicate_copy_count:
            raise PortfolioConcentrationDomainError("Summary ownership totals are inconsistent.")
        for name in ("supported_dimensions", "analysed_dimensions", "unusable_dimensions"):
            values = tuple(getattr(self, name))
            if len(set(values)) != len(values) or any(type(value) is not str or not value for value in values):
                raise PortfolioConcentrationDomainError(f"{name} must contain unique non-empty strings.")
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class PortfolioConcentrationOutput:
    analysis_state: PortfolioConcentrationAnalysisState
    rule_set_version: str
    rule_configuration: PortfolioConcentrationRuleConfiguration
    summary: PortfolioConcentrationSummary
    dimensions: tuple[PortfolioDimensionConcentration, ...]
    reason_codes: tuple[PortfolioConcentrationReasonCode, ...]
    provenance: PortfolioConcentrationProvenance
    diagnostics: tuple[PortfolioConcentrationDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.rule_set_version != RULE_SET_VERSION:
            raise PortfolioConcentrationDomainError("Unsupported concentration rule-set version.")
        dimensions = tuple(self.dimensions)
        if tuple(value.dimension for value in dimensions) != self.summary.analysed_dimensions:
            raise PortfolioConcentrationDomainError("Analysed dimensions are inconsistent.")
        reasons = tuple(self.reason_codes)
        diagnostics = tuple(self.diagnostics)
        if len(set(reasons)) != len(reasons) or any(type(value) is not PortfolioConcentrationReasonCode for value in reasons):
            raise PortfolioConcentrationDomainError("Concentration reason codes must be typed and unique.")
        if diagnostics != tuple(sorted(diagnostics, key=_diagnostic_order)):
            raise PortfolioConcentrationDomainError("Concentration diagnostics must use canonical order.")
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "diagnostics", diagnostics)


def validate_portfolio_concentration_output(value: object) -> PortfolioConcentrationOutput:
    """Reconstruct and validate the concrete version-1 Concentration graph."""

    _exact(value, PortfolioConcentrationOutput, "output")
    _exact(value.analysis_state, PortfolioConcentrationAnalysisState, "analysis_state")
    _exact(value.rule_configuration, PortfolioConcentrationRuleConfiguration, "rule_configuration")
    _exact(value.summary, PortfolioConcentrationSummary, "summary")
    if value.summary.source_evidence_coverage is not None:
        _exact(
            value.summary.source_evidence_coverage,
            PortfolioDistributionEvidenceCoverage,
            "summary.source_evidence_coverage",
        )
    _exact(
        value.summary.evidence_coverage,
        PortfolioConcentrationEvidenceCoverage,
        "summary.evidence_coverage",
    )
    _typed_items(value.dimensions, PortfolioDimensionConcentration, "dimensions")
    _typed_items(value.reason_codes, PortfolioConcentrationReasonCode, "reason_codes")
    _exact(value.provenance, PortfolioConcentrationProvenance, "provenance")
    if value.provenance.source_evidence_coverage is not None:
        _exact(
            value.provenance.source_evidence_coverage,
            PortfolioDistributionEvidenceCoverage,
            "provenance.source_evidence_coverage",
        )
    if value.provenance.distribution_provenance is not None:
        _exact(
            value.provenance.distribution_provenance,
            PortfolioDistributionProvenance,
            "provenance.distribution_provenance",
        )
    _typed_items(value.diagnostics, PortfolioConcentrationDiagnostic, "diagnostics")
    return replace(
        value,
        rule_configuration=replace(value.rule_configuration),
        summary=replace(
            value.summary,
            supported_dimensions=tuple(value.summary.supported_dimensions),
            analysed_dimensions=tuple(value.summary.analysed_dimensions),
            unusable_dimensions=tuple(value.summary.unusable_dimensions),
        ),
        dimensions=tuple(_rebuild_concentration_dimension(item) for item in value.dimensions),
        reason_codes=tuple(value.reason_codes),
        provenance=replace(
            value.provenance,
            distribution_provenance=(
                None
                if value.provenance.distribution_provenance is None
                else replace(value.provenance.distribution_provenance)
            ),
            supported_dimensions=tuple(value.provenance.supported_dimensions),
            analysed_dimensions=tuple(value.provenance.analysed_dimensions),
            unusable_dimensions=tuple(value.provenance.unusable_dimensions),
        ),
        diagnostics=tuple(_rebuild_concentration_diagnostic(item) for item in value.diagnostics),
    )


def validate_portfolio_concentration_source(
    distribution: PortfolioDistributionOutput,
    concentration: PortfolioConcentrationOutput,
) -> None:
    """Validate version-1 Concentration linkage to its Distribution source."""

    distribution = validate_portfolio_distribution_output(distribution)
    concentration = validate_portfolio_concentration_output(concentration)
    distribution_summary = distribution.summary
    concentration_summary = concentration.summary
    supported = tuple(value.value for value in distribution_summary.supported_dimensions)
    analysed = tuple(value.dimension.value for value in distribution.dimensions if value.entries)
    unusable = tuple(value.dimension.value for value in distribution.dimensions if not value.entries)
    expected_coverage, expected_state = _coverage_and_state(
        source_compatible=True,
        unique_owned_releases=distribution_summary.ownership.unique_owned_releases,
        source_dimensions=distribution.dimensions,
        analysed_dimensions=analysed,
        has_source_diagnostics=bool(distribution.diagnostics),
    )
    expected_provenance = PortfolioConcentrationProvenance(
        source_module_id=DISTRIBUTION_MODULE_ID,
        source_module_version=DISTRIBUTION_MODULE_VERSION,
        source_rule_set_version=distribution.rule_set_version,
        source_evidence_coverage=distribution_summary.evidence_coverage,
        distribution_provenance=distribution.provenance,
        supported_dimensions=supported,
        analysed_dimensions=analysed,
        unusable_dimensions=unusable,
    )
    if concentration.provenance != expected_provenance:
        raise PortfolioConcentrationDomainError(
            "Concentration provenance does not match its Distribution source."
        )
    if (
        concentration_summary.unique_owned_releases,
        concentration_summary.total_owned_copies,
        concentration_summary.duplicate_copy_count,
        concentration_summary.source_evidence_coverage,
        concentration_summary.evidence_coverage,
        concentration_summary.supported_dimensions,
        concentration_summary.analysed_dimensions,
        concentration_summary.unusable_dimensions,
    ) != (
        distribution_summary.ownership.unique_owned_releases,
        distribution_summary.ownership.total_owned_copies,
        distribution_summary.ownership.duplicate_copy_count,
        distribution_summary.evidence_coverage,
        expected_coverage,
        supported,
        analysed,
        unusable,
    ):
        raise PortfolioConcentrationDomainError(
            "Concentration summary does not match its Distribution source."
        )
    if concentration.analysis_state is not expected_state:
        raise PortfolioConcentrationDomainError(
            "Concentration analysis state does not match its Distribution source."
        )
    source_dimensions = {value.dimension.value: value for value in distribution.dimensions}
    for dimension in concentration.dimensions:
        source = source_dimensions.get(dimension.dimension)
        if source is None or (
            dimension.represented_category_count,
            dimension.releases_with_metadata,
            dimension.releases_missing_metadata,
            dimension.copies_with_metadata,
            dimension.copies_missing_metadata,
            dimension.release_metadata_coverage_ratio,
            dimension.copy_metadata_coverage_ratio,
            dimension.missing_release_ids,
            dimension.source_entries,
        ) != (
            source.represented_category_count,
            source.releases_with_metadata,
            source.releases_missing_metadata,
            source.copies_with_metadata,
            source.copies_missing_metadata,
            source.release_metadata_coverage_ratio,
            source.copy_metadata_coverage_ratio,
            source.missing_release_ids,
            source.entries,
        ):
            raise PortfolioConcentrationDomainError(
                "Concentration dimension does not match its Distribution source."
            )


def _rebuild_concentration_dimension(value):
    if type(value.dimension) is not str:
        raise TypeError("dimension.dimension must be a string.")
    _typed_items(value.source_entries, PortfolioCategoryDistributionEntry, "dimension.source_entries")
    _exact(value.release_concentration, PortfolioConcentrationMetricSet, "release_concentration")
    _exact(value.copy_concentration, PortfolioConcentrationMetricSet, "copy_concentration")
    _exact(value.difference, PortfolioConcentrationDifference, "difference")
    return replace(
        value,
        missing_release_ids=tuple(value.missing_release_ids),
        source_entries=tuple(
            replace(item, release_ids=tuple(item.release_ids)) for item in value.source_entries
        ),
        release_concentration=_rebuild_metric_set(value.release_concentration),
        copy_concentration=_rebuild_metric_set(value.copy_concentration),
        difference=replace(value.difference),
        reason_codes=tuple(value.reason_codes),
    )


def _rebuild_metric_set(value):
    _typed_items(value.largest_categories, PortfolioCategoryContribution, "largest_categories")
    for name in ("top_three", "top_five"):
        item = getattr(value, name)
        if item is not None:
            _exact(item, PortfolioTopNConcentration, name)
    return replace(
        value,
        largest_categories=tuple(_rebuild_contribution(item) for item in value.largest_categories),
        top_three=_rebuild_top_n(value.top_three),
        top_five=_rebuild_top_n(value.top_five),
    )


def _rebuild_top_n(value):
    if value is None:
        return None
    _typed_items(value.contributions, PortfolioCategoryContribution, "contributions")
    return replace(
        value,
        contributions=tuple(_rebuild_contribution(item) for item in value.contributions),
    )


def _rebuild_contribution(value):
    return replace(value, release_ids=tuple(value.release_ids))


def _rebuild_concentration_diagnostic(value):
    _exact(value.code, PortfolioConcentrationDiagnosticCode, "diagnostic.code")
    return replace(value)


def _typed_items(values, expected, name):
    if type(values) is not tuple or any(type(item) is not expected for item in values):
        raise TypeError(f"{name} must be a tuple of {expected.__name__} values.")


def _exact(value, expected, name):
    if type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__}.")


class PortfolioConcentrationModule:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, rules: PortfolioConcentrationRuleConfiguration = PortfolioConcentrationRuleConfiguration()):
        if type(rules) is not PortfolioConcentrationRuleConfiguration:
            raise TypeError("rules must be PortfolioConcentrationRuleConfiguration.")
        self._rules = rules

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be IntelligenceContext.")
        supplied = context.portfolio_concentration_input
        if supplied is None:
            supplied = PortfolioConcentrationInput(
                False,
                PortfolioConcentrationProvenance("portfolio_distribution", None, None, None, None),
                diagnostics=(PortfolioConcentrationDiagnostic(
                    PortfolioConcentrationDiagnosticCode.MISSING_DISTRIBUTION_SOURCE,
                    "Portfolio Distribution result was not supplied.",
                ),),
            )
        if type(supplied) is not PortfolioConcentrationInput:
            raise TypeError("portfolio_concentration_input must be PortfolioConcentrationInput.")
        output = _output(supplied, self._rules)
        status = IntelligenceStatus.SKIPPED if output.analysis_state is PortfolioConcentrationAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        return IntelligenceResult(
            MODULE_ID, status,
            "Portfolio Concentration has insufficient Portfolio Distribution evidence."
            if status is IntelligenceStatus.SKIPPED
            else f"Measured observed concentration across {len(output.dimensions)} portfolio dimension"
            f"{'' if len(output.dimensions) == 1 else 's'}.",
            metrics={"output": output},
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in output.diagnostics),
            evidence=tuple(f"{value.dimension} concentration uses represented category memberships." for value in output.dimensions),
            module_version=MODULE_VERSION,
        )


def _output(supplied, rules):
    if not supplied.source_compatible or supplied.unique_owned_releases == 0:
        dimensions = ()
    else:
        dimensions = tuple(
            _dimension(value, rules) for value in supplied.dimensions if value.entries
        )
    supported = supplied.source_provenance.supported_dimensions
    analysed = tuple(value.dimension for value in dimensions)
    unusable = tuple(value for value in supported if value not in analysed)
    coverage, state = _coverage_and_state(
        source_compatible=supplied.source_compatible,
        unique_owned_releases=supplied.unique_owned_releases,
        source_dimensions=supplied.dimensions,
        analysed_dimensions=analysed,
        has_source_diagnostics=bool(supplied.diagnostics),
    )
    provenance = PortfolioConcentrationProvenance(
        supplied.source_provenance.source_module_id,
        supplied.source_provenance.source_module_version,
        supplied.source_provenance.source_rule_set_version,
        supplied.source_provenance.source_evidence_coverage,
        supplied.source_provenance.distribution_provenance,
        supported, analysed, unusable,
    )
    summary = PortfolioConcentrationSummary(
        supplied.unique_owned_releases, supplied.total_owned_copies,
        supplied.duplicate_copy_count, supplied.source_provenance.source_evidence_coverage,
        coverage, supported, analysed, unusable,
    )
    reasons = _output_reasons(coverage, supplied, dimensions)
    diagnostics = list(supplied.diagnostics)
    for value in supplied.dimensions:
        if not value.entries:
            diagnostics.append(PortfolioConcentrationDiagnostic(
                PortfolioConcentrationDiagnosticCode.NO_USABLE_CATEGORIES,
                f"{value.dimension.value} contains no usable categories.",
            ))
    diagnostics = tuple(sorted(diagnostics, key=_diagnostic_order))
    return PortfolioConcentrationOutput(
        state, RULE_SET_VERSION, rules, summary, dimensions, reasons, provenance, diagnostics,
    )


def _coverage_and_state(
    *,
    source_compatible,
    unique_owned_releases,
    source_dimensions,
    analysed_dimensions,
    has_source_diagnostics,
):
    if not source_compatible or unique_owned_releases == 0 or not analysed_dimensions:
        coverage = PortfolioConcentrationEvidenceCoverage.INSUFFICIENT
    elif len(analysed_dimensions) < len(source_dimensions):
        coverage = PortfolioConcentrationEvidenceCoverage.LIMITED
    elif all(
        value.releases_missing_metadata == 0 and value.copies_missing_metadata == 0
        for value in source_dimensions
    ):
        coverage = PortfolioConcentrationEvidenceCoverage.COMPLETE
    else:
        coverage = PortfolioConcentrationEvidenceCoverage.PARTIAL
    state = (
        PortfolioConcentrationAnalysisState.INSUFFICIENT_DATA
        if coverage is PortfolioConcentrationEvidenceCoverage.INSUFFICIENT
        else PortfolioConcentrationAnalysisState.COMPLETE
        if coverage is PortfolioConcentrationEvidenceCoverage.COMPLETE
        and not has_source_diagnostics
        else PortfolioConcentrationAnalysisState.PARTIAL
    )
    return coverage, state


def _dimension(source, rules):
    release = _metrics(source.entries, PortfolioConcentrationBasis.RELEASE_MEMBERSHIP, rules)
    copies = _metrics(source.entries, PortfolioConcentrationBasis.COPY_MEMBERSHIP, rules)
    reasons = [
        PortfolioConcentrationReasonCode.DIMENSION_ANALYSED,
        PortfolioConcentrationReasonCode.SINGLE_CATEGORY_DISTRIBUTION
        if len(source.entries) == 1 else PortfolioConcentrationReasonCode.MULTIPLE_CATEGORY_DISTRIBUTION,
    ]
    if source.releases_missing_metadata:
        reasons.append(PortfolioConcentrationReasonCode.DIMENSION_METADATA_INCOMPLETE)
    if len(release.largest_categories) > 1:
        reasons.append(PortfolioConcentrationReasonCode.LARGEST_CATEGORY_TIE)
    if len(source.entries) <= rules.top_three_count:
        reasons.append(PortfolioConcentrationReasonCode.TOP_THREE_COVERS_ALL_CATEGORIES)
    if len(source.entries) <= rules.top_five_count:
        reasons.append(PortfolioConcentrationReasonCode.TOP_FIVE_COVERS_ALL_CATEGORIES)
    difference = _difference(release, copies)
    if difference.hhi_delta == 0:
        reasons.append(PortfolioConcentrationReasonCode.RELEASE_COPY_CONCENTRATION_EQUAL)
    elif difference.hhi_delta is not None and difference.hhi_delta > 0:
        reasons.append(PortfolioConcentrationReasonCode.COPY_CONCENTRATION_EXCEEDS_RELEASE_CONCENTRATION)
    else:
        reasons.append(PortfolioConcentrationReasonCode.RELEASE_CONCENTRATION_EXCEEDS_COPY_CONCENTRATION)
    reasons.append(
        PortfolioConcentrationReasonCode.NORMALIZED_HHI_SINGLE_CATEGORY
        if len(source.entries) == 1 else PortfolioConcentrationReasonCode.NORMALIZED_HHI_AVAILABLE
    )
    for metric in (release, copies):
        state_reason = {
            PortfolioConcentrationState.DISPERSED: PortfolioConcentrationReasonCode.CONCENTRATION_STATE_DISPERSED,
            PortfolioConcentrationState.MODERATE: PortfolioConcentrationReasonCode.CONCENTRATION_STATE_MODERATE,
            PortfolioConcentrationState.CONCENTRATED: PortfolioConcentrationReasonCode.CONCENTRATION_STATE_CONCENTRATED,
            PortfolioConcentrationState.HIGHLY_CONCENTRATED: PortfolioConcentrationReasonCode.CONCENTRATION_STATE_HIGHLY_CONCENTRATED,
            PortfolioConcentrationState.INSUFFICIENT: PortfolioConcentrationReasonCode.NO_USABLE_CONCENTRATION_DIMENSIONS,
        }[metric.state]
        if state_reason not in reasons:
            reasons.append(state_reason)
    return PortfolioDimensionConcentration(
        source.dimension.value, source.represented_category_count,
        source.releases_with_metadata, source.releases_missing_metadata,
        source.copies_with_metadata, source.copies_missing_metadata,
        source.release_metadata_coverage_ratio, source.copy_metadata_coverage_ratio,
        source.missing_release_ids, source.entries, release, copies, difference,
        tuple(reasons),
    )


def _metrics(entries, basis, rules):
    counts = tuple(
        value.unique_release_count
        if basis is PortfolioConcentrationBasis.RELEASE_MEMBERSHIP
        else value.owned_copy_count
        for value in entries
    )
    total = sum(counts)
    if not entries or total == 0:
        return PortfolioConcentrationMetricSet(
            basis, total, len(entries), 0, total, None, (), None, None,
            None, None, None, PortfolioConcentrationState.INSUFFICIENT,
        )
    contributions = tuple(
        _contribution(value, count, total) for value, count in zip(entries, counts, strict=True)
    )
    largest_count = max(counts)
    largest = tuple(value for value in contributions if value.membership_count == largest_count)
    hhi = Decimal(sum(value * value for value in counts)) / Decimal(total * total)
    category_count = len(entries)
    if category_count == 1:
        normalized = Decimal("1")
    else:
        floor = Decimal("1") / Decimal(category_count)
        normalized = (hhi - floor) / (Decimal("1") - floor)
    effective = Decimal("1") / hhi
    return PortfolioConcentrationMetricSet(
        basis, total, category_count, largest_count, total,
        Decimal(largest_count) / Decimal(total), largest,
        _top_n(contributions, rules.top_three_count, total),
        _top_n(contributions, rules.top_five_count, total),
        hhi, normalized, effective, _state(normalized, category_count, rules),
    )


def _contribution(entry, count, total):
    return PortfolioCategoryContribution(
        entry.category_id, entry.display_name, count, total,
        Decimal(count) / Decimal(total), entry.release_ids,
    )


def _top_n(contributions, requested, total):
    included = contributions[:requested]
    numerator = sum(value.membership_count for value in included)
    return PortfolioTopNConcentration(
        requested, len(included), numerator, total,
        Decimal(numerator) / Decimal(total), included,
    )


def _state(normalized, category_count, rules):
    if category_count == 1:
        return PortfolioConcentrationState.HIGHLY_CONCENTRATED
    if normalized < rules.dispersed_upper_bound:
        return PortfolioConcentrationState.DISPERSED
    if normalized < rules.moderate_upper_bound:
        return PortfolioConcentrationState.MODERATE
    if normalized < rules.concentrated_upper_bound:
        return PortfolioConcentrationState.CONCENTRATED
    return PortfolioConcentrationState.HIGHLY_CONCENTRATED


def _difference(release, copies):
    return PortfolioConcentrationDifference(
        _delta(copies.largest_category_share, release.largest_category_share),
        _delta(_share(copies.top_three), _share(release.top_three)),
        _delta(_share(copies.top_five), _share(release.top_five)),
        _delta(copies.hhi, release.hhi),
        _delta(copies.normalized_hhi, release.normalized_hhi),
        _delta(copies.effective_category_count, release.effective_category_count),
    )


def _share(value):
    return None if value is None else value.share


def _delta(left, right):
    return None if left is None or right is None else left - right


def _ratio(numerator, denominator):
    return Decimal("0") if denominator == 0 else Decimal(numerator) / Decimal(denominator)


def _optional_unit_decimal(value, name):
    if value is None:
        return
    if type(value) is not Decimal or not value.is_finite() or not Decimal("0") <= value <= Decimal("1"):
        raise ValueError(f"{name} must be None or a finite Decimal from zero through one.")


def _output_reasons(coverage, supplied, dimensions):
    values = [{
        PortfolioConcentrationEvidenceCoverage.COMPLETE: PortfolioConcentrationReasonCode.COMPLETE_CONCENTRATION_EVIDENCE,
        PortfolioConcentrationEvidenceCoverage.PARTIAL: PortfolioConcentrationReasonCode.PARTIAL_CONCENTRATION_EVIDENCE,
        PortfolioConcentrationEvidenceCoverage.LIMITED: PortfolioConcentrationReasonCode.LIMITED_CONCENTRATION_EVIDENCE,
        PortfolioConcentrationEvidenceCoverage.INSUFFICIENT: PortfolioConcentrationReasonCode.NO_USABLE_CONCENTRATION_DIMENSIONS,
    }[coverage]]
    if supplied.unique_owned_releases == 0:
        values.append(PortfolioConcentrationReasonCode.EMPTY_PORTFOLIO)
    diagnostic_reasons = {
        PortfolioConcentrationDiagnosticCode.MISSING_DISTRIBUTION_SOURCE: PortfolioConcentrationReasonCode.MISSING_DISTRIBUTION_SOURCE,
        PortfolioConcentrationDiagnosticCode.UNSUPPORTED_SOURCE_VERSION: PortfolioConcentrationReasonCode.UNSUPPORTED_DISTRIBUTION_VERSION,
        PortfolioConcentrationDiagnosticCode.UNSUPPORTED_SOURCE_RULE_SET: PortfolioConcentrationReasonCode.UNSUPPORTED_DISTRIBUTION_RULE_SET,
        PortfolioConcentrationDiagnosticCode.MALFORMED_SOURCE_OUTPUT: PortfolioConcentrationReasonCode.MALFORMED_DISTRIBUTION_OUTPUT,
    }
    for diagnostic in supplied.diagnostics:
        reason = diagnostic_reasons.get(diagnostic.code)
        if reason is not None and reason not in values:
            values.append(reason)
    return tuple(values)


def _diagnostic_order(value):
    return tuple(PortfolioConcentrationDiagnosticCode).index(value.code), value.message


def _non_negative(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must not be negative.")
