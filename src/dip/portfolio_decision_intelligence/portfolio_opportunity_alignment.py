"""Explainable synthesis across established Portfolio Intelligence outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus
from dip.portfolio_intelligence import (
    PortfolioConcentrationEvidenceCoverage,
    PortfolioConcentrationOutput,
    PortfolioConcentrationMetricSet,
    PortfolioConcentrationState,
    PortfolioDistributionEvidenceCoverage,
    PortfolioDistributionOutput,
    PortfolioEvidenceCoverage,
    PortfolioDistribution,
    PortfolioOverviewOutput,
    PortfolioReleaseMatchState,
)


MODULE_ID = "portfolio_opportunity_alignment"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"


class PortfolioOpportunityAlignmentDomainError(ValueError):
    """Raised when Alignment facts contradict their visible source evidence."""


class PortfolioOpportunityAlignmentAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class PortfolioOpportunityAlignmentAssessment(str, Enum):
    BROADLY_ALIGNED = "broadly_aligned"
    SELECTIVELY_ALIGNED = "selectively_aligned"
    MIXED = "mixed"
    CONSTRAINED = "constrained"
    INSUFFICIENT = "insufficient"


class PortfolioOpportunityAlignmentEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class PortfolioOpportunityMappingCategory(str, Enum):
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    LIMITING = "limiting"
    ADVERSE = "adverse"
    INSUFFICIENT = "insufficient"


class PortfolioConcentrationContextCategory(str, Enum):
    BROAD = "broad"
    INTERMEDIATE = "intermediate"
    NARROW = "narrow"
    UNUSABLE = "unusable"


class PortfolioCategoryAlignmentCategory(str, Enum):
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    LIMITING = "limiting"
    ADVERSE = "adverse"
    INSUFFICIENT = "insufficient"


class PortfolioOpportunityAlignmentReasonCode(str, Enum):
    COMPLETE_ALIGNMENT_EVIDENCE = "complete_alignment_evidence"
    PARTIAL_ALIGNMENT_EVIDENCE = "partial_alignment_evidence"
    LIMITED_ALIGNMENT_EVIDENCE = "limited_alignment_evidence"
    INSUFFICIENT_ALIGNMENT_EVIDENCE = "insufficient_alignment_evidence"
    MISSING_REQUIRED_SOURCE = "missing_required_source"
    UNSUPPORTED_SOURCE_VERSION = "unsupported_source_version"
    UNSUPPORTED_SOURCE_RULE_SET = "unsupported_source_rule_set"
    MALFORMED_SOURCE_OUTPUT = "malformed_source_output"
    INCOMPATIBLE_SOURCE_PROVENANCE = "incompatible_source_provenance"
    EMPTY_PORTFOLIO = "empty_portfolio"
    NO_USABLE_OPPORTUNITY_EVIDENCE = "no_usable_opportunity_evidence"
    NO_USABLE_ALIGNMENT_DIMENSIONS = "no_usable_alignment_dimensions"
    HIGH_OPPORTUNITY_COVERAGE = "high_opportunity_coverage"
    PARTIAL_OPPORTUNITY_COVERAGE = "partial_opportunity_coverage"
    LOW_OPPORTUNITY_COVERAGE = "low_opportunity_coverage"
    SUPPORTIVE_OPPORTUNITY_BROADLY_REPRESENTED = "supportive_opportunity_broadly_represented"
    SUPPORTIVE_OPPORTUNITY_SELECTIVELY_REPRESENTED = "supportive_opportunity_selectively_represented"
    MIXED_OPPORTUNITY_REPRESENTATION = "mixed_opportunity_representation"
    LIMITING_OPPORTUNITY_REPRESENTATION = "limiting_opportunity_representation"
    ADVERSE_OPPORTUNITY_REPRESENTATION = "adverse_opportunity_representation"
    UNMATCHED_HOLDINGS_PRESENT = "unmatched_holdings_present"
    INSUFFICIENT_OPPORTUNITY_RESULTS_PRESENT = "insufficient_opportunity_results_present"
    DISTRIBUTION_METADATA_INCOMPLETE = "distribution_metadata_incomplete"
    CONCENTRATION_DIMENSION_UNUSABLE = "concentration_dimension_unusable"
    SOURCE_DIAGNOSTICS_PRESENT = "source_diagnostics_present"
    ALIGNMENT_BROADLY_ALIGNED = "alignment_broadly_aligned"
    ALIGNMENT_SELECTIVELY_ALIGNED = "alignment_selectively_aligned"
    ALIGNMENT_MIXED = "alignment_mixed"
    ALIGNMENT_CONSTRAINED = "alignment_constrained"
    ALIGNMENT_INSUFFICIENT = "alignment_insufficient"


class PortfolioOpportunityAlignmentDiagnosticCode(str, Enum):
    MISSING_REQUIRED_SOURCE = "missing_required_source"
    SOURCE_MODULE_MISMATCH = "source_module_mismatch"
    UNSUPPORTED_SOURCE_VERSION = "unsupported_source_version"
    UNSUPPORTED_SOURCE_RULE_SET = "unsupported_source_rule_set"
    MALFORMED_SOURCE_OUTPUT = "malformed_source_output"
    SOURCE_STATUS_INCOMPATIBLE = "source_status_incompatible"
    INCOMPATIBLE_COLLECTION_SNAPSHOT = "incompatible_collection_snapshot"
    INCOMPATIBLE_DISTRIBUTION_REFERENCE = "incompatible_distribution_reference"
    INCONSISTENT_OWNED_RELEASE_TOTAL = "inconsistent_owned_release_total"
    INCONSISTENT_OWNED_COPY_TOTAL = "inconsistent_owned_copy_total"
    INCONSISTENT_RELEASE_POPULATION = "inconsistent_release_population"
    SOURCE_DIAGNOSTIC_PRESERVED = "source_diagnostic_preserved"
    NO_USABLE_OPPORTUNITY_EVIDENCE = "no_usable_opportunity_evidence"
    NO_USABLE_CATEGORY_ALIGNMENT = "no_usable_category_alignment"


@dataclass(frozen=True)
class PortfolioOpportunityAlignmentRuleConfiguration:
    broad_usable_coverage_minimum: Decimal = Decimal("0.75")
    limited_usable_coverage_boundary: Decimal = Decimal("0.50")
    meaningful_supportive_share_minimum: Decimal = Decimal("0.40")
    broad_supportive_share_minimum: Decimal = Decimal("0.60")
    constraining_limiting_adverse_share: Decimal = Decimal("0.50")
    strongly_adverse_share: Decimal = Decimal("0.40")
    constraining_unusable_share: Decimal = Decimal("0.50")

    def __post_init__(self) -> None:
        values = tuple(getattr(self, item.name) for item in self.__dataclass_fields__.values())
        if any(type(value) is not Decimal for value in values):
            raise TypeError("Alignment thresholds must be Decimals.")
        if any(not Decimal("0") <= value <= Decimal("1") for value in values):
            raise ValueError("Alignment thresholds must be from zero through one.")
        if self.limited_usable_coverage_boundary > self.broad_usable_coverage_minimum:
            raise ValueError("Limited coverage boundary must not exceed broad coverage minimum.")
        if self.meaningful_supportive_share_minimum > self.broad_supportive_share_minimum:
            raise ValueError("Meaningful supportive share must not exceed broad supportive share.")


@dataclass(frozen=True)
class PortfolioOpportunityAlignmentDiagnostic:
    code: PortfolioOpportunityAlignmentDiagnosticCode
    message: str
    source_module_id: str | None = None

    def __post_init__(self):
        if type(self.code) is not PortfolioOpportunityAlignmentDiagnosticCode:
            raise TypeError("code must be PortfolioOpportunityAlignmentDiagnosticCode.")
        if type(self.message) is not str or not self.message:
            raise TypeError("message must be a non-empty string.")


@dataclass(frozen=True)
class PortfolioOpportunityAlignmentProvenance:
    overview_module_version: str | None
    overview_rule_set_version: str | None
    distribution_module_version: str | None
    distribution_rule_set_version: str | None
    concentration_module_version: str | None
    concentration_rule_set_version: str | None
    collection_snapshot_id: int | None
    supported_dimensions: tuple[str, ...]
    analysed_dimensions: tuple[str, ...]
    unusable_dimensions: tuple[str, ...]
    overview_evidence: PortfolioEvidenceCoverage | None
    distribution_evidence: PortfolioDistributionEvidenceCoverage | None
    concentration_evidence: PortfolioConcentrationEvidenceCoverage | None

    def __post_init__(self):
        for name in ("supported_dimensions", "analysed_dimensions", "unusable_dimensions"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class PortfolioOpportunityAlignmentInput:
    source_compatible: bool
    overview: PortfolioOverviewOutput | None
    distribution: PortfolioDistributionOutput | None
    concentration: PortfolioConcentrationOutput | None
    provenance: PortfolioOpportunityAlignmentProvenance
    diagnostics: tuple[PortfolioOpportunityAlignmentDiagnostic, ...] = ()

    def __post_init__(self):
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not PortfolioOpportunityAlignmentDiagnostic for value in diagnostics):
            raise TypeError("diagnostics contains invalid values.")
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class PortfolioOpportunityMappingEntry:
    category: PortfolioOpportunityMappingCategory
    release_count: int
    copy_count: int
    release_denominator: int
    copy_denominator: int
    release_share: Decimal
    copy_share: Decimal
    release_ids: tuple[int, ...]


@dataclass(frozen=True)
class PortfolioOpportunityBreadth:
    valid_owned_releases: int
    total_owned_copies: int
    matched_releases: int
    unmatched_releases: int
    usable_releases: int
    insufficient_releases: int
    mapping_entries: tuple[PortfolioOpportunityMappingEntry, ...]
    source_opportunity_distribution: PortfolioDistribution | None


@dataclass(frozen=True)
class PortfolioCategoryAlignment:
    category_id: str
    display_name: str
    source_position: int
    release_membership_count: int
    copy_membership_count: int
    mapping_entries: tuple[PortfolioOpportunityMappingEntry, ...]
    alignment_category: PortfolioCategoryAlignmentCategory
    tied_mapping_categories: tuple[PortfolioOpportunityMappingCategory, ...]
    source_release_share: Decimal
    source_copy_share: Decimal
    release_ids: tuple[int, ...]


@dataclass(frozen=True)
class PortfolioDimensionAlignment:
    dimension: str
    metadata_release_coverage: Decimal
    metadata_copy_coverage: Decimal
    release_concentration_state: PortfolioConcentrationState
    copy_concentration_state: PortfolioConcentrationState
    release_concentration_context: PortfolioConcentrationContextCategory
    copy_concentration_context: PortfolioConcentrationContextCategory
    release_concentration: PortfolioConcentrationMetricSet
    copy_concentration: PortfolioConcentrationMetricSet
    categories: tuple[PortfolioCategoryAlignment, ...]
    largest_categories: tuple[PortfolioCategoryAlignment, ...]
    top_three_categories: tuple[PortfolioCategoryAlignment, ...]
    top_five_categories: tuple[PortfolioCategoryAlignment, ...]
    supportive_category_count: int
    neutral_category_count: int
    limiting_category_count: int
    adverse_category_count: int
    unusable_category_count: int


@dataclass(frozen=True)
class PortfolioOpportunityAlignmentSummary:
    assessment: PortfolioOpportunityAlignmentAssessment
    evidence_coverage: PortfolioOpportunityAlignmentEvidenceCoverage
    overview_evidence: PortfolioEvidenceCoverage | None
    distribution_evidence: PortfolioDistributionEvidenceCoverage | None
    concentration_evidence: PortfolioConcentrationEvidenceCoverage | None
    supportive_dimension_count: int
    mixed_dimension_count: int
    limiting_dimension_count: int
    unusable_dimension_count: int


@dataclass(frozen=True)
class PortfolioOpportunityAlignmentOutput:
    analysis_state: PortfolioOpportunityAlignmentAnalysisState
    rule_set_version: str
    rule_configuration: PortfolioOpportunityAlignmentRuleConfiguration
    summary: PortfolioOpportunityAlignmentSummary
    breadth: PortfolioOpportunityBreadth
    dimensions: tuple[PortfolioDimensionAlignment, ...]
    reason_codes: tuple[PortfolioOpportunityAlignmentReasonCode, ...]
    provenance: PortfolioOpportunityAlignmentProvenance
    diagnostics: tuple[PortfolioOpportunityAlignmentDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.rule_set_version != RULE_SET_VERSION:
            raise PortfolioOpportunityAlignmentDomainError("Unsupported Alignment rule-set version.")
        dimensions = tuple(self.dimensions)
        if (
            self.analysis_state is not PortfolioOpportunityAlignmentAnalysisState.INSUFFICIENT_DATA
            and tuple(value.dimension for value in dimensions) != self.provenance.analysed_dimensions
        ):
            raise PortfolioOpportunityAlignmentDomainError("Alignment dimension order is inconsistent.")
        reasons = tuple(self.reason_codes)
        diagnostics = tuple(self.diagnostics)
        if len(set(reasons)) != len(reasons):
            raise PortfolioOpportunityAlignmentDomainError("Alignment reason codes must be unique.")
        if diagnostics != tuple(sorted(diagnostics, key=_diagnostic_order)):
            raise PortfolioOpportunityAlignmentDomainError("Alignment diagnostics must use canonical order.")
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "diagnostics", diagnostics)


_MAPPING_ORDER = tuple(PortfolioOpportunityMappingCategory)


class PortfolioOpportunityAlignmentModule:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, rules: PortfolioOpportunityAlignmentRuleConfiguration = PortfolioOpportunityAlignmentRuleConfiguration()):
        if type(rules) is not PortfolioOpportunityAlignmentRuleConfiguration:
            raise TypeError("rules must be PortfolioOpportunityAlignmentRuleConfiguration.")
        self._rules = rules

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be IntelligenceContext.")
        supplied = context.portfolio_opportunity_alignment_input
        if supplied is None:
            supplied = _missing_input()
        if type(supplied) is not PortfolioOpportunityAlignmentInput:
            raise TypeError("portfolio_opportunity_alignment_input must be PortfolioOpportunityAlignmentInput.")
        output = _output(supplied, self._rules)
        status = IntelligenceStatus.SKIPPED if output.analysis_state is PortfolioOpportunityAlignmentAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        return IntelligenceResult(
            MODULE_ID, status,
            "Portfolio Opportunity Alignment has insufficient compatible Portfolio Intelligence."
            if status is IntelligenceStatus.SKIPPED
            else f"Portfolio Opportunity Alignment is {output.summary.assessment.value.replace('_', ' ')}.",
            metrics={"output": output},
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in output.diagnostics),
            evidence=tuple(f"{value.dimension} preserves category-level Opportunity composition." for value in output.dimensions),
            module_version=MODULE_VERSION,
        )


def _output(supplied, rules):
    overview = supplied.overview
    distribution = supplied.distribution
    concentration = supplied.concentration
    compatible = supplied.source_compatible and overview is not None and distribution is not None and concentration is not None
    if compatible:
        breadth, release_mapping = _breadth(overview, distribution)
        quantities = {value.release_id: value.quantity for value in distribution.releases}
        dimensions = _dimensions(distribution, concentration, release_mapping, quantities)
    else:
        breadth = PortfolioOpportunityBreadth(0, 0, 0, 0, 0, 0, (), None)
        release_mapping, dimensions = {}, ()
    evidence = _evidence(supplied, breadth, dimensions)
    assessment = _assessment(evidence, breadth, dimensions, rules)
    summary = _summary(assessment, evidence, supplied.provenance, dimensions)
    reasons = _reasons(summary, breadth, dimensions, supplied, rules)
    diagnostics = list(supplied.diagnostics)
    if compatible and breadth.usable_releases == 0:
        diagnostics.append(PortfolioOpportunityAlignmentDiagnostic(
            PortfolioOpportunityAlignmentDiagnosticCode.NO_USABLE_OPPORTUNITY_EVIDENCE,
            "No owned release has usable Opportunity evidence.",
        ))
    if compatible and not dimensions:
        diagnostics.append(PortfolioOpportunityAlignmentDiagnostic(
            PortfolioOpportunityAlignmentDiagnosticCode.NO_USABLE_CATEGORY_ALIGNMENT,
            "No compatible category alignment dimension is available.",
        ))
    diagnostics = tuple(sorted(diagnostics, key=_diagnostic_order))
    state = (
        PortfolioOpportunityAlignmentAnalysisState.INSUFFICIENT_DATA
        if evidence is PortfolioOpportunityAlignmentEvidenceCoverage.INSUFFICIENT
        else PortfolioOpportunityAlignmentAnalysisState.COMPLETE
        if evidence is PortfolioOpportunityAlignmentEvidenceCoverage.COMPLETE
        else PortfolioOpportunityAlignmentAnalysisState.PARTIAL
    )
    return PortfolioOpportunityAlignmentOutput(
        state, RULE_SET_VERSION, rules, summary, breadth, dimensions,
        reasons, supplied.provenance, diagnostics,
    )


def _breadth(overview, distribution):
    release_by_id = {value.release_id: value for value in overview.releases}
    quantities = {value.release_id: value.quantity for value in distribution.releases}
    ids = tuple(sorted(release_by_id))
    grouped = {value: [] for value in _MAPPING_ORDER}
    for release_id in ids:
        grouped[_mapping(release_by_id[release_id])].append(release_id)
    release_total = len(ids)
    copy_total = sum(quantities[value] for value in ids)
    entries = tuple(
        PortfolioOpportunityMappingEntry(
            category, len(grouped[category]),
            sum(quantities[value] for value in grouped[category]),
            release_total, copy_total,
            _ratio(len(grouped[category]), release_total),
            _ratio(sum(quantities[value] for value in grouped[category]), copy_total),
            tuple(grouped[category]),
        )
        for category in _MAPPING_ORDER
    )
    matched = overview.summary.matched_owned_release_count
    usable = overview.summary.usable_opportunity_release_count
    return PortfolioOpportunityBreadth(
        release_total, copy_total, matched, release_total - matched, usable,
        release_total - usable, entries,
        overview.opportunity_distribution,
    ), {release_id: category for category, values in grouped.items() for release_id in values}


def _mapping(release):
    if release.match_state is PortfolioReleaseMatchState.UNMATCHED or release.opportunity_assessment is None:
        return PortfolioOpportunityMappingCategory.INSUFFICIENT
    return {
        "strong": PortfolioOpportunityMappingCategory.SUPPORTIVE,
        "developing": PortfolioOpportunityMappingCategory.SUPPORTIVE,
        "balanced": PortfolioOpportunityMappingCategory.NEUTRAL,
        "constrained": PortfolioOpportunityMappingCategory.LIMITING,
        "weak": PortfolioOpportunityMappingCategory.ADVERSE,
        "insufficient": PortfolioOpportunityMappingCategory.INSUFFICIENT,
    }[release.opportunity_assessment.value]


def _dimensions(distribution, concentration, release_mapping, quantities):
    concentration_by_id = {value.dimension: value for value in concentration.dimensions}
    values = []
    for source in distribution.dimensions:
        context = concentration_by_id.get(source.dimension.value)
        if context is None:
            continue
        categories = tuple(
            _category(entry, position, release_mapping, quantities)
            for position, entry in enumerate(source.entries)
        )
        by_id = {value.category_id: value for value in categories}
        largest_ids = tuple(value.category_id for value in context.release_concentration.largest_categories)
        top_three_ids = () if context.release_concentration.top_three is None else tuple(value.category_id for value in context.release_concentration.top_three.contributions)
        top_five_ids = () if context.release_concentration.top_five is None else tuple(value.category_id for value in context.release_concentration.top_five.contributions)
        counts = {value: sum(item.alignment_category is value for item in categories) for value in PortfolioCategoryAlignmentCategory}
        values.append(PortfolioDimensionAlignment(
            source.dimension.value, source.release_metadata_coverage_ratio,
            source.copy_metadata_coverage_ratio,
            context.release_concentration.state, context.copy_concentration.state,
            _concentration_mapping(context.release_concentration.state),
            _concentration_mapping(context.copy_concentration.state),
            context.release_concentration, context.copy_concentration,
            categories,
            tuple(by_id[value] for value in largest_ids if value in by_id),
            tuple(by_id[value] for value in top_three_ids if value in by_id),
            tuple(by_id[value] for value in top_five_ids if value in by_id),
            counts[PortfolioCategoryAlignmentCategory.SUPPORTIVE],
            counts[PortfolioCategoryAlignmentCategory.NEUTRAL],
            counts[PortfolioCategoryAlignmentCategory.LIMITING],
            counts[PortfolioCategoryAlignmentCategory.ADVERSE],
            counts[PortfolioCategoryAlignmentCategory.INSUFFICIENT],
        ))
    return tuple(values)


def _category(entry, position, release_mapping, quantities):
    grouped = {value: [] for value in _MAPPING_ORDER}
    for release_id in entry.release_ids:
        grouped[release_mapping[release_id]].append(release_id)
    mapping_entries = tuple(
        PortfolioOpportunityMappingEntry(
            category, len(grouped[category]),
            sum(quantities[value] for value in grouped[category]),
            entry.unique_release_count, entry.owned_copy_count,
            _ratio(len(grouped[category]), entry.unique_release_count),
            _ratio(sum(quantities[value] for value in grouped[category]), entry.owned_copy_count),
            tuple(grouped[category]),
        )
        for category in _MAPPING_ORDER
    )
    usable = tuple(value for value in mapping_entries if value.category is not PortfolioOpportunityMappingCategory.INSUFFICIENT)
    maximum = max((value.release_count for value in usable), default=0)
    tied = tuple(value.category for value in usable if value.release_count == maximum and maximum)
    category = _category_assessment(mapping_entries)
    return PortfolioCategoryAlignment(
        entry.category_id, entry.display_name, position,
        entry.unique_release_count, entry.owned_copy_count,
        mapping_entries, category, tied, entry.release_ratio, entry.copy_ratio,
        entry.release_ids,
    )


def _category_assessment(entries):
    counts = {value.category: value.release_count for value in entries}
    usable = sum(counts[value] for value in _MAPPING_ORDER[:-1])
    if usable == 0:
        return PortfolioCategoryAlignmentCategory.INSUFFICIENT
    supportive, neutral, limiting, adverse = (counts[value] for value in _MAPPING_ORDER[:-1])
    if adverse > max(supportive, neutral, limiting):
        return PortfolioCategoryAlignmentCategory.ADVERSE
    if limiting >= supportive and limiting > max(neutral, adverse):
        return PortfolioCategoryAlignmentCategory.LIMITING
    if supportive > max(neutral, limiting, adverse):
        return PortfolioCategoryAlignmentCategory.SUPPORTIVE
    return PortfolioCategoryAlignmentCategory.NEUTRAL


def _concentration_mapping(state):
    return {
        PortfolioConcentrationState.DISPERSED: PortfolioConcentrationContextCategory.BROAD,
        PortfolioConcentrationState.MODERATE: PortfolioConcentrationContextCategory.INTERMEDIATE,
        PortfolioConcentrationState.CONCENTRATED: PortfolioConcentrationContextCategory.NARROW,
        PortfolioConcentrationState.HIGHLY_CONCENTRATED: PortfolioConcentrationContextCategory.NARROW,
        PortfolioConcentrationState.INSUFFICIENT: PortfolioConcentrationContextCategory.UNUSABLE,
    }[state]


def _evidence(supplied, breadth, dimensions):
    if not supplied.source_compatible or breadth.valid_owned_releases == 0 or breadth.usable_releases == 0 or not dimensions:
        return PortfolioOpportunityAlignmentEvidenceCoverage.INSUFFICIENT
    provenance = supplied.provenance
    all_dimensions = len(dimensions) == len(provenance.supported_dimensions)
    if (
        provenance.overview_evidence is PortfolioEvidenceCoverage.COMPLETE
        and provenance.distribution_evidence is PortfolioDistributionEvidenceCoverage.COMPLETE
        and provenance.concentration_evidence is PortfolioConcentrationEvidenceCoverage.COMPLETE
        and all_dimensions and not supplied.diagnostics
    ):
        return PortfolioOpportunityAlignmentEvidenceCoverage.COMPLETE
    if all_dimensions and (
        provenance.concentration_evidence in {
            PortfolioConcentrationEvidenceCoverage.COMPLETE,
            PortfolioConcentrationEvidenceCoverage.PARTIAL,
        }
    ) and breadth.usable_releases == breadth.valid_owned_releases:
        return PortfolioOpportunityAlignmentEvidenceCoverage.PARTIAL
    return PortfolioOpportunityAlignmentEvidenceCoverage.LIMITED


def _assessment(evidence, breadth, dimensions, rules):
    if evidence is PortfolioOpportunityAlignmentEvidenceCoverage.INSUFFICIENT:
        return PortfolioOpportunityAlignmentAssessment.INSUFFICIENT
    entries = {value.category: value for value in breadth.mapping_entries}
    total = breadth.valid_owned_releases
    usable_share = _ratio(breadth.usable_releases, total)
    supportive = entries[PortfolioOpportunityMappingCategory.SUPPORTIVE].release_share
    limiting = entries[PortfolioOpportunityMappingCategory.LIMITING].release_share
    adverse = entries[PortfolioOpportunityMappingCategory.ADVERSE].release_share
    unusable = entries[PortfolioOpportunityMappingCategory.INSUFFICIENT].release_share
    narrow = sum(
        value.release_concentration_context is PortfolioConcentrationContextCategory.NARROW
        for value in dimensions
    )
    materially_narrow = narrow * 2 >= len(dimensions)
    if (
        usable_share < rules.limited_usable_coverage_boundary
        or limiting + adverse >= rules.constraining_limiting_adverse_share
        or adverse >= rules.strongly_adverse_share
        or unusable >= rules.constraining_unusable_share
    ):
        return PortfolioOpportunityAlignmentAssessment.CONSTRAINED
    if (
        evidence in {PortfolioOpportunityAlignmentEvidenceCoverage.COMPLETE, PortfolioOpportunityAlignmentEvidenceCoverage.PARTIAL}
        and usable_share >= rules.broad_usable_coverage_minimum
        and supportive >= rules.broad_supportive_share_minimum
        and not materially_narrow
    ):
        return PortfolioOpportunityAlignmentAssessment.BROADLY_ALIGNED
    if supportive >= rules.meaningful_supportive_share_minimum:
        return PortfolioOpportunityAlignmentAssessment.SELECTIVELY_ALIGNED
    return PortfolioOpportunityAlignmentAssessment.MIXED


def _summary(assessment, evidence, provenance, dimensions):
    states = tuple(_dimension_state(value) for value in dimensions)
    supportive = states.count(PortfolioCategoryAlignmentCategory.SUPPORTIVE)
    limiting = sum(value in {PortfolioCategoryAlignmentCategory.LIMITING, PortfolioCategoryAlignmentCategory.ADVERSE} for value in states)
    mixed = sum(value is PortfolioCategoryAlignmentCategory.NEUTRAL for value in states)
    unusable = len(provenance.supported_dimensions) - len(dimensions)
    return PortfolioOpportunityAlignmentSummary(
        assessment, evidence, provenance.overview_evidence,
        provenance.distribution_evidence, provenance.concentration_evidence,
        supportive, mixed, limiting, unusable,
    )


def _dimension_state(value):
    states = {item.alignment_category for item in value.categories}
    if states and states <= {PortfolioCategoryAlignmentCategory.INSUFFICIENT}:
        return PortfolioCategoryAlignmentCategory.INSUFFICIENT
    if PortfolioCategoryAlignmentCategory.ADVERSE in states:
        return PortfolioCategoryAlignmentCategory.ADVERSE
    if PortfolioCategoryAlignmentCategory.LIMITING in states:
        return PortfolioCategoryAlignmentCategory.LIMITING
    if PortfolioCategoryAlignmentCategory.SUPPORTIVE in states and PortfolioCategoryAlignmentCategory.NEUTRAL not in states:
        return PortfolioCategoryAlignmentCategory.SUPPORTIVE
    return PortfolioCategoryAlignmentCategory.NEUTRAL


def _reasons(summary, breadth, dimensions, supplied, rules):
    values = [{
        PortfolioOpportunityAlignmentEvidenceCoverage.COMPLETE: PortfolioOpportunityAlignmentReasonCode.COMPLETE_ALIGNMENT_EVIDENCE,
        PortfolioOpportunityAlignmentEvidenceCoverage.PARTIAL: PortfolioOpportunityAlignmentReasonCode.PARTIAL_ALIGNMENT_EVIDENCE,
        PortfolioOpportunityAlignmentEvidenceCoverage.LIMITED: PortfolioOpportunityAlignmentReasonCode.LIMITED_ALIGNMENT_EVIDENCE,
        PortfolioOpportunityAlignmentEvidenceCoverage.INSUFFICIENT: PortfolioOpportunityAlignmentReasonCode.INSUFFICIENT_ALIGNMENT_EVIDENCE,
    }[summary.evidence_coverage]]
    usable_share = _ratio(breadth.usable_releases, breadth.valid_owned_releases)
    values.append(
        PortfolioOpportunityAlignmentReasonCode.HIGH_OPPORTUNITY_COVERAGE
        if usable_share >= rules.broad_usable_coverage_minimum
        else PortfolioOpportunityAlignmentReasonCode.PARTIAL_OPPORTUNITY_COVERAGE
        if usable_share >= rules.limited_usable_coverage_boundary
        else PortfolioOpportunityAlignmentReasonCode.LOW_OPPORTUNITY_COVERAGE
    )
    mapped = {value.category: value for value in breadth.mapping_entries}
    supportive = mapped.get(PortfolioOpportunityMappingCategory.SUPPORTIVE)
    limiting = mapped.get(PortfolioOpportunityMappingCategory.LIMITING)
    adverse = mapped.get(PortfolioOpportunityMappingCategory.ADVERSE)
    if supportive and supportive.release_share >= rules.broad_supportive_share_minimum:
        values.append(PortfolioOpportunityAlignmentReasonCode.SUPPORTIVE_OPPORTUNITY_BROADLY_REPRESENTED)
    elif supportive and supportive.release_share >= rules.meaningful_supportive_share_minimum:
        values.append(PortfolioOpportunityAlignmentReasonCode.SUPPORTIVE_OPPORTUNITY_SELECTIVELY_REPRESENTED)
    else:
        values.append(PortfolioOpportunityAlignmentReasonCode.MIXED_OPPORTUNITY_REPRESENTATION)
    if limiting and limiting.release_count:
        values.append(PortfolioOpportunityAlignmentReasonCode.LIMITING_OPPORTUNITY_REPRESENTATION)
    if adverse and adverse.release_count:
        values.append(PortfolioOpportunityAlignmentReasonCode.ADVERSE_OPPORTUNITY_REPRESENTATION)
    if breadth.unmatched_releases:
        values.append(PortfolioOpportunityAlignmentReasonCode.UNMATCHED_HOLDINGS_PRESENT)
    if breadth.insufficient_releases:
        values.append(PortfolioOpportunityAlignmentReasonCode.INSUFFICIENT_OPPORTUNITY_RESULTS_PRESENT)
    if supplied.provenance.distribution_evidence is not PortfolioDistributionEvidenceCoverage.COMPLETE:
        values.append(PortfolioOpportunityAlignmentReasonCode.DISTRIBUTION_METADATA_INCOMPLETE)
    if supplied.provenance.unusable_dimensions:
        values.append(PortfolioOpportunityAlignmentReasonCode.CONCENTRATION_DIMENSION_UNUSABLE)
    if supplied.diagnostics:
        values.append(PortfolioOpportunityAlignmentReasonCode.SOURCE_DIAGNOSTICS_PRESENT)
    values.append({
        PortfolioOpportunityAlignmentAssessment.BROADLY_ALIGNED: PortfolioOpportunityAlignmentReasonCode.ALIGNMENT_BROADLY_ALIGNED,
        PortfolioOpportunityAlignmentAssessment.SELECTIVELY_ALIGNED: PortfolioOpportunityAlignmentReasonCode.ALIGNMENT_SELECTIVELY_ALIGNED,
        PortfolioOpportunityAlignmentAssessment.MIXED: PortfolioOpportunityAlignmentReasonCode.ALIGNMENT_MIXED,
        PortfolioOpportunityAlignmentAssessment.CONSTRAINED: PortfolioOpportunityAlignmentReasonCode.ALIGNMENT_CONSTRAINED,
        PortfolioOpportunityAlignmentAssessment.INSUFFICIENT: PortfolioOpportunityAlignmentReasonCode.ALIGNMENT_INSUFFICIENT,
    }[summary.assessment])
    return tuple(dict.fromkeys(values))


def _ratio(numerator, denominator):
    return Decimal("0") if denominator == 0 else Decimal(numerator) / Decimal(denominator)


def _diagnostic_order(value):
    return tuple(PortfolioOpportunityAlignmentDiagnosticCode).index(value.code), value.source_module_id or "", value.message


def _missing_input():
    provenance = PortfolioOpportunityAlignmentProvenance(
        None, None, None, None, None, None, None, (), (), (),
        None, None, None,
    )
    return PortfolioOpportunityAlignmentInput(
        False, None, None, None, provenance,
        (PortfolioOpportunityAlignmentDiagnostic(
            PortfolioOpportunityAlignmentDiagnosticCode.MISSING_REQUIRED_SOURCE,
            "Required Portfolio Intelligence sources were not supplied.",
        ),),
    )
