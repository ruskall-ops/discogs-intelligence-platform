"""Deterministic synthesis of independent Marketplace Decision Intelligence."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus


MODULE_ID = "marketplace_opportunity"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"
_SOURCE_ORDER = ("marketplace_momentum", "marketplace_stability", "marketplace_scarcity")


class MarketplaceOpportunityDomainError(ValueError):
    """Raised when Opportunity values contradict the synthesis contract."""


class OpportunityAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class OpportunityAssessment(str, Enum):
    STRONG = "strong"
    DEVELOPING = "developing"
    BALANCED = "balanced"
    CONSTRAINED = "constrained"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class OpportunityEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class OpportunityDimensionCategory(str, Enum):
    SUPPORTIVE = "supportive"
    NEUTRAL = "neutral"
    LIMITING = "limiting"
    ADVERSE = "adverse"
    UNUSABLE = "unusable"


class OpportunityMomentumAssessment(str, Enum):
    POSITIVE = "positive"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    INSUFFICIENT = "insufficient"


class OpportunityStabilityAssessment(str, Enum):
    STABLE = "stable"
    MIXED = "mixed"
    VOLATILE = "volatile"
    INSUFFICIENT = "insufficient"


class OpportunityScarcityAssessment(str, Enum):
    ABUNDANT = "abundant"
    COMMON = "common"
    LIMITED = "limited"
    SCARCE = "scarce"
    VERY_SCARCE = "very_scarce"
    INSUFFICIENT = "insufficient"


class OpportunityReasonCode(str, Enum):
    POSITIVE_MOMENTUM = "positive_momentum"
    MIXED_MOMENTUM = "mixed_momentum"
    NEUTRAL_MOMENTUM = "neutral_momentum"
    NEGATIVE_MOMENTUM = "negative_momentum"
    STABLE_CONDITIONS = "stable_conditions"
    MIXED_STABILITY = "mixed_stability"
    VOLATILE_CONDITIONS = "volatile_conditions"
    LIMITED_OBSERVED_AVAILABILITY = "limited_observed_availability"
    SCARCE_OBSERVED_AVAILABILITY = "scarce_observed_availability"
    VERY_SCARCE_OBSERVED_AVAILABILITY = "very_scarce_observed_availability"
    COMMON_OBSERVED_AVAILABILITY = "common_observed_availability"
    ABUNDANT_OBSERVED_AVAILABILITY = "abundant_observed_availability"
    SUPPORTIVE_DIMENSIONS_ALIGNED = "supportive_dimensions_aligned"
    SUPPORTIVE_AND_LIMITING_SIGNALS = "supportive_and_limiting_signals"
    VOLATILITY_LIMITS_SYNTHESIS = "volatility_limits_synthesis"
    AVAILABILITY_LIMITS_SYNTHESIS = "availability_limits_synthesis"
    NEGATIVE_DIRECTION_LIMITS_SYNTHESIS = "negative_direction_limits_synthesis"
    PARTIAL_SOURCE_EVIDENCE = "partial_source_evidence"
    LIMITED_SOURCE_EVIDENCE = "limited_source_evidence"
    INSUFFICIENT_DIMENSIONS = "insufficient_dimensions"


class MarketplaceOpportunityDiagnosticCode(str, Enum):
    MISSING_REQUIRED_SOURCE = "missing_required_source"
    DUPLICATE_SOURCE_RESULT = "duplicate_source_result"
    UNEXPECTED_SOURCE_RESULT = "unexpected_source_result"
    UNSUPPORTED_SOURCE_VERSION = "unsupported_source_version"
    UNSUPPORTED_RULE_SET_VERSION = "unsupported_rule_set_version"
    MALFORMED_TYPED_OUTPUT = "malformed_typed_output"
    SOURCE_NOT_COMPLETED = "source_not_completed"
    INCOMPATIBLE_PROVENANCE = "incompatible_provenance"
    PARTIAL_SOURCE_DIAGNOSTICS = "partial_source_diagnostics"
    RELEASE_MISSING_FROM_SOURCE = "release_missing_from_source"
    SOURCE_EVIDENCE_LIMITED = "source_evidence_limited"


@dataclass(frozen=True)
class OpportunityRuleConfiguration:
    """Explicit versioned source-state mappings used by synthesis."""

    momentum_positive: OpportunityDimensionCategory = OpportunityDimensionCategory.SUPPORTIVE
    momentum_mixed: OpportunityDimensionCategory = OpportunityDimensionCategory.NEUTRAL
    momentum_neutral: OpportunityDimensionCategory = OpportunityDimensionCategory.NEUTRAL
    momentum_negative: OpportunityDimensionCategory = OpportunityDimensionCategory.ADVERSE
    stability_stable: OpportunityDimensionCategory = OpportunityDimensionCategory.SUPPORTIVE
    stability_mixed: OpportunityDimensionCategory = OpportunityDimensionCategory.NEUTRAL
    stability_volatile: OpportunityDimensionCategory = OpportunityDimensionCategory.LIMITING
    scarcity_very_scarce: OpportunityDimensionCategory = OpportunityDimensionCategory.SUPPORTIVE
    scarcity_scarce: OpportunityDimensionCategory = OpportunityDimensionCategory.SUPPORTIVE
    scarcity_limited: OpportunityDimensionCategory = OpportunityDimensionCategory.NEUTRAL
    scarcity_common: OpportunityDimensionCategory = OpportunityDimensionCategory.LIMITING
    scarcity_abundant: OpportunityDimensionCategory = OpportunityDimensionCategory.LIMITING


@dataclass(frozen=True)
class MarketplaceOpportunityDiagnostic:
    code: MarketplaceOpportunityDiagnosticCode
    message: str
    source_module_id: str | None = None
    release_id: int | None = None

    def __post_init__(self):
        if type(self.code) is not MarketplaceOpportunityDiagnosticCode:
            raise TypeError("code must be a MarketplaceOpportunityDiagnosticCode.")
        _text(self.message, "message")
        if self.source_module_id is not None:
            _text(self.source_module_id, "source_module_id")
        if self.release_id is not None:
            _positive(self.release_id, "release_id")


@dataclass(frozen=True)
class OpportunitySourceProvenance:
    module_id: str
    module_version: str | None
    rule_set_version: str | None
    result_status: IntelligenceStatus
    compatible: bool
    history_snapshot_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self):
        if self.module_id not in _SOURCE_ORDER:
            raise MarketplaceOpportunityDomainError("Unsupported Opportunity source.")
        ids = tuple(self.history_snapshot_ids)
        diagnostics = tuple(self.diagnostics)
        if len(set(ids)) != len(ids):
            raise MarketplaceOpportunityDomainError("Provenance snapshot IDs must be unique.")
        if any(type(value) is not str or not value for value in (*ids, *diagnostics)):
            raise TypeError("Provenance values must be non-empty strings.")
        object.__setattr__(self, "history_snapshot_ids", ids)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class OpportunityDimensionFact:
    release_id: int
    source_module_id: str
    assessment: str
    evidence_coverage: OpportunityEvidenceCoverage

    def __post_init__(self):
        _positive(self.release_id, "release_id")
        if self.source_module_id not in _SOURCE_ORDER:
            raise MarketplaceOpportunityDomainError("Unsupported Opportunity dimension.")
        _text(self.assessment, "assessment")
        if type(self.evidence_coverage) is not OpportunityEvidenceCoverage:
            raise TypeError("evidence_coverage must be an OpportunityEvidenceCoverage.")


@dataclass(frozen=True)
class MarketplaceOpportunityInput:
    source_provenance: tuple[OpportunitySourceProvenance, ...] = ()
    dimension_facts: tuple[OpportunityDimensionFact, ...] = ()
    diagnostics: tuple[MarketplaceOpportunityDiagnostic, ...] = ()

    def __post_init__(self):
        provenance = tuple(self.source_provenance)
        facts = tuple(self.dimension_facts)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not OpportunitySourceProvenance for value in provenance):
            raise TypeError("source_provenance contains invalid values.")
        if any(type(value) is not OpportunityDimensionFact for value in facts):
            raise TypeError("dimension_facts contains invalid values.")
        if any(type(value) is not MarketplaceOpportunityDiagnostic for value in diagnostics):
            raise TypeError("diagnostics contains invalid values.")
        if len({value.module_id for value in provenance}) != len(provenance):
            raise MarketplaceOpportunityDomainError("Duplicate Opportunity source provenance.")
        if len({(value.release_id, value.source_module_id) for value in facts}) != len(facts):
            raise MarketplaceOpportunityDomainError("Duplicate Opportunity release dimension.")
        object.__setattr__(self, "source_provenance", provenance)
        object.__setattr__(self, "dimension_facts", facts)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def required_sources_compatible(self):
        by_id = {value.module_id: value for value in self.source_provenance}
        return all(source in by_id and by_id[source].compatible for source in _SOURCE_ORDER)


@dataclass(frozen=True)
class OpportunityDimension:
    assessment: str | None
    evidence_coverage: OpportunityEvidenceCoverage
    category: OpportunityDimensionCategory


@dataclass(frozen=True)
class OpportunityDimensions:
    momentum: OpportunityDimension
    stability: OpportunityDimension
    scarcity: OpportunityDimension


@dataclass(frozen=True)
class ReleaseOpportunity:
    release_id: int
    assessment: OpportunityAssessment
    evidence_coverage: OpportunityEvidenceCoverage
    dimensions: OpportunityDimensions
    supportive_dimension_count: int
    neutral_dimension_count: int
    limiting_dimension_count: int
    adverse_dimension_count: int
    usable_dimension_count: int
    reason_codes: tuple[OpportunityReasonCode, ...]

    def __post_init__(self):
        _positive(self.release_id, "release_id")
        categories = tuple(getattr(self.dimensions, name).category for name in ("momentum", "stability", "scarcity"))
        counts = Counter(categories)
        expected = (
            counts[OpportunityDimensionCategory.SUPPORTIVE],
            counts[OpportunityDimensionCategory.NEUTRAL],
            counts[OpportunityDimensionCategory.LIMITING],
            counts[OpportunityDimensionCategory.ADVERSE],
            3 - counts[OpportunityDimensionCategory.UNUSABLE],
        )
        actual = (
            self.supportive_dimension_count, self.neutral_dimension_count,
            self.limiting_dimension_count, self.adverse_dimension_count,
            self.usable_dimension_count,
        )
        if actual != expected:
            raise MarketplaceOpportunityDomainError("Opportunity dimension counts are inconsistent.")
        if self.assessment is not _assessment(self.dimensions, self.evidence_coverage):
            raise MarketplaceOpportunityDomainError("Opportunity assessment is inconsistent.")
        reasons = tuple(self.reason_codes)
        if len(set(reasons)) != len(reasons) or any(type(value) is not OpportunityReasonCode for value in reasons):
            raise MarketplaceOpportunityDomainError("Opportunity reason codes must be typed and unique.")
        object.__setattr__(self, "reason_codes", reasons)


@dataclass(frozen=True)
class MarketplaceOpportunitySummary:
    release_count: int = 0
    strong_count: int = 0
    developing_count: int = 0
    balanced_count: int = 0
    constrained_count: int = 0
    weak_count: int = 0
    insufficient_count: int = 0
    complete_evidence_count: int = 0
    partial_evidence_count: int = 0
    limited_evidence_count: int = 0
    insufficient_evidence_count: int = 0
    positive_momentum_count: int = 0
    stable_condition_count: int = 0
    scarce_availability_count: int = 0
    aligned_supportive_count: int = 0
    volatility_limited_count: int = 0
    availability_limited_count: int = 0
    negative_direction_limited_count: int = 0


@dataclass(frozen=True)
class MarketplaceOpportunityOutput:
    analysis_state: OpportunityAnalysisState
    rule_set_version: str
    rule_configuration: OpportunityRuleConfiguration
    source_provenance: tuple[OpportunitySourceProvenance, ...]
    releases: tuple[ReleaseOpportunity, ...]
    summary: MarketplaceOpportunitySummary
    diagnostics: tuple[MarketplaceOpportunityDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.rule_set_version != RULE_SET_VERSION:
            raise MarketplaceOpportunityDomainError("Unsupported Opportunity rule-set version.")
        releases = tuple(self.releases)
        if releases != tuple(sorted(releases, key=_release_order)):
            raise MarketplaceOpportunityDomainError("Opportunity releases must use canonical order.")
        if self.summary != _summary(releases):
            raise MarketplaceOpportunityDomainError("Opportunity summary is inconsistent.")
        object.__setattr__(self, "source_provenance", tuple(self.source_provenance))
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


class MarketplaceOpportunityModule:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, rule_configuration=OpportunityRuleConfiguration()):
        if type(rule_configuration) is not OpportunityRuleConfiguration:
            raise TypeError("rule_configuration must be an OpportunityRuleConfiguration.")
        self._rules = rule_configuration

    def analyse(self, context):
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        supplied = context.marketplace_opportunity_input
        if supplied is None:
            supplied = MarketplaceOpportunityInput(diagnostics=(MarketplaceOpportunityDiagnostic(MarketplaceOpportunityDiagnosticCode.MISSING_REQUIRED_SOURCE, "Marketplace Opportunity input was not supplied."),))
        if type(supplied) is not MarketplaceOpportunityInput:
            raise TypeError("marketplace_opportunity_input must be a MarketplaceOpportunityInput.")
        if not supplied.required_sources_compatible:
            return self._result(supplied, (), OpportunityAnalysisState.INSUFFICIENT_DATA)
        grouped = {}
        for fact in supplied.dimension_facts:
            grouped.setdefault(fact.release_id, {})[fact.source_module_id] = fact
        releases = tuple(_release(release_id, grouped[release_id], self._rules) for release_id in sorted(grouped))
        releases = tuple(sorted(releases, key=_release_order))
        state = OpportunityAnalysisState.PARTIAL if any(value.evidence_coverage is not OpportunityEvidenceCoverage.COMPLETE for value in releases) or supplied.diagnostics else OpportunityAnalysisState.COMPLETE
        return self._result(supplied, releases, state)

    def _result(self, supplied, releases, state):
        output = MarketplaceOpportunityOutput(
            state, RULE_SET_VERSION, self._rules, supplied.source_provenance,
            releases, _summary(releases), supplied.diagnostics,
        )
        status = IntelligenceStatus.SKIPPED if state is OpportunityAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        return IntelligenceResult(
            MODULE_ID, status,
            "Marketplace Opportunity requires compatible Momentum, Stability, and Scarcity intelligence." if status is IntelligenceStatus.SKIPPED else f"Synthesized observed Marketplace Opportunity for {len(releases)} release{'s' if len(releases) != 1 else ''}.",
            metrics={"output": output}, module_version=MODULE_VERSION,
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in supplied.diagnostics),
            evidence=tuple(f"Release {value.release_id} has {value.assessment.value} observed Opportunity alignment." for value in releases),
        )


def _release(release_id, facts, rules):
    momentum = _dimension(facts.get("marketplace_momentum"), "marketplace_momentum", rules)
    stability = _dimension(facts.get("marketplace_stability"), "marketplace_stability", rules)
    scarcity = _dimension(facts.get("marketplace_scarcity"), "marketplace_scarcity", rules)
    dimensions = OpportunityDimensions(momentum, stability, scarcity)
    coverages = tuple(value.evidence_coverage for value in (momentum, stability, scarcity))
    if any(value is OpportunityEvidenceCoverage.INSUFFICIENT for value in coverages) or any(value.category is OpportunityDimensionCategory.UNUSABLE for value in (momentum, stability, scarcity)):
        coverage = OpportunityEvidenceCoverage.INSUFFICIENT
    elif OpportunityEvidenceCoverage.LIMITED in coverages:
        coverage = OpportunityEvidenceCoverage.LIMITED
    elif OpportunityEvidenceCoverage.PARTIAL in coverages:
        coverage = OpportunityEvidenceCoverage.PARTIAL
    else:
        coverage = OpportunityEvidenceCoverage.COMPLETE
    categories = tuple(value.category for value in (momentum, stability, scarcity))
    counts = Counter(categories)
    assessment = _assessment(dimensions, coverage)
    return ReleaseOpportunity(
        release_id, assessment, coverage, dimensions,
        counts[OpportunityDimensionCategory.SUPPORTIVE],
        counts[OpportunityDimensionCategory.NEUTRAL],
        counts[OpportunityDimensionCategory.LIMITING],
        counts[OpportunityDimensionCategory.ADVERSE],
        3 - counts[OpportunityDimensionCategory.UNUSABLE],
        _reasons(dimensions, coverage, assessment),
    )


def _dimension(fact, source, rules):
    if fact is None:
        return OpportunityDimension(None, OpportunityEvidenceCoverage.INSUFFICIENT, OpportunityDimensionCategory.UNUSABLE)
    mappings = {
        "marketplace_momentum": {
            "positive": rules.momentum_positive, "mixed": rules.momentum_mixed,
            "neutral": rules.momentum_neutral, "negative": rules.momentum_negative,
            "insufficient": OpportunityDimensionCategory.UNUSABLE,
        },
        "marketplace_stability": {
            "stable": rules.stability_stable, "mixed": rules.stability_mixed,
            "volatile": rules.stability_volatile,
            "insufficient": OpportunityDimensionCategory.UNUSABLE,
        },
        "marketplace_scarcity": {
            "very_scarce": rules.scarcity_very_scarce, "scarce": rules.scarcity_scarce,
            "limited": rules.scarcity_limited, "common": rules.scarcity_common,
            "abundant": rules.scarcity_abundant,
            "insufficient": OpportunityDimensionCategory.UNUSABLE,
        },
    }
    if fact.assessment not in mappings[source]:
        raise MarketplaceOpportunityDomainError("Unknown normalized source assessment.")
    return OpportunityDimension(fact.assessment, fact.evidence_coverage, mappings[source][fact.assessment])


def _assessment(dimensions, coverage):
    momentum = dimensions.momentum.assessment
    stability = dimensions.stability.assessment
    scarcity = dimensions.scarcity.assessment
    if coverage is OpportunityEvidenceCoverage.INSUFFICIENT:
        return OpportunityAssessment.INSUFFICIENT
    if coverage is OpportunityEvidenceCoverage.COMPLETE and momentum == "positive" and stability == "stable" and scarcity in {"scarce", "very_scarce"}:
        return OpportunityAssessment.STRONG
    categories = tuple(getattr(dimensions, name).category for name in ("momentum", "stability", "scarcity"))
    adverse_or_limiting = sum(value in {OpportunityDimensionCategory.ADVERSE, OpportunityDimensionCategory.LIMITING} for value in categories)
    if momentum == "negative" and stability in {"volatile", "mixed"} and scarcity in {"abundant", "common", "limited"}:
        return OpportunityAssessment.WEAK
    if adverse_or_limiting >= 2 and OpportunityDimensionCategory.ADVERSE in categories:
        return OpportunityAssessment.WEAK
    if coverage is OpportunityEvidenceCoverage.LIMITED or stability == "volatile" or scarcity in {"abundant", "common"}:
        return OpportunityAssessment.CONSTRAINED
    if momentum == "positive" and stability in {"stable", "mixed"} and scarcity in {"limited", "scarce", "very_scarce"}:
        return OpportunityAssessment.DEVELOPING
    return OpportunityAssessment.BALANCED


def _reasons(dimensions, coverage, assessment):
    momentum, stability, scarcity = dimensions.momentum, dimensions.stability, dimensions.scarcity
    values = []
    values.append({
        "positive": OpportunityReasonCode.POSITIVE_MOMENTUM,
        "mixed": OpportunityReasonCode.MIXED_MOMENTUM,
        "neutral": OpportunityReasonCode.NEUTRAL_MOMENTUM,
        "negative": OpportunityReasonCode.NEGATIVE_MOMENTUM,
    }.get(momentum.assessment, OpportunityReasonCode.INSUFFICIENT_DIMENSIONS))
    values.append({
        "stable": OpportunityReasonCode.STABLE_CONDITIONS,
        "mixed": OpportunityReasonCode.MIXED_STABILITY,
        "volatile": OpportunityReasonCode.VOLATILE_CONDITIONS,
    }.get(stability.assessment, OpportunityReasonCode.INSUFFICIENT_DIMENSIONS))
    values.append({
        "limited": OpportunityReasonCode.LIMITED_OBSERVED_AVAILABILITY,
        "scarce": OpportunityReasonCode.SCARCE_OBSERVED_AVAILABILITY,
        "very_scarce": OpportunityReasonCode.VERY_SCARCE_OBSERVED_AVAILABILITY,
        "common": OpportunityReasonCode.COMMON_OBSERVED_AVAILABILITY,
        "abundant": OpportunityReasonCode.ABUNDANT_OBSERVED_AVAILABILITY,
    }.get(scarcity.assessment, OpportunityReasonCode.INSUFFICIENT_DIMENSIONS))
    if coverage is OpportunityEvidenceCoverage.PARTIAL:
        values.append(OpportunityReasonCode.PARTIAL_SOURCE_EVIDENCE)
    elif coverage is OpportunityEvidenceCoverage.LIMITED:
        values.append(OpportunityReasonCode.LIMITED_SOURCE_EVIDENCE)
    if stability.assessment == "volatile":
        values.append(OpportunityReasonCode.VOLATILITY_LIMITS_SYNTHESIS)
    if scarcity.assessment in {"abundant", "common"}:
        values.append(OpportunityReasonCode.AVAILABILITY_LIMITS_SYNTHESIS)
    if momentum.assessment == "negative":
        values.append(OpportunityReasonCode.NEGATIVE_DIRECTION_LIMITS_SYNTHESIS)
    values.append(
        OpportunityReasonCode.SUPPORTIVE_DIMENSIONS_ALIGNED
        if assessment is OpportunityAssessment.STRONG
        else OpportunityReasonCode.INSUFFICIENT_DIMENSIONS
        if assessment is OpportunityAssessment.INSUFFICIENT
        else OpportunityReasonCode.SUPPORTIVE_AND_LIMITING_SIGNALS
    )
    return tuple(dict.fromkeys(values))


_ASSESSMENT_ORDER = {value: index for index, value in enumerate(OpportunityAssessment)}
_COVERAGE_ORDER = {value: index for index, value in enumerate(OpportunityEvidenceCoverage)}


def _release_order(value):
    return (
        _ASSESSMENT_ORDER[value.assessment], _COVERAGE_ORDER[value.evidence_coverage],
        -value.supportive_dimension_count, value.adverse_dimension_count,
        value.limiting_dimension_count, value.release_id,
    )


def _summary(values):
    assessments = Counter(value.assessment for value in values)
    coverage = Counter(value.evidence_coverage for value in values)
    return MarketplaceOpportunitySummary(
        len(values), assessments[OpportunityAssessment.STRONG],
        assessments[OpportunityAssessment.DEVELOPING], assessments[OpportunityAssessment.BALANCED],
        assessments[OpportunityAssessment.CONSTRAINED], assessments[OpportunityAssessment.WEAK],
        assessments[OpportunityAssessment.INSUFFICIENT], coverage[OpportunityEvidenceCoverage.COMPLETE],
        coverage[OpportunityEvidenceCoverage.PARTIAL], coverage[OpportunityEvidenceCoverage.LIMITED],
        coverage[OpportunityEvidenceCoverage.INSUFFICIENT],
        sum(value.dimensions.momentum.assessment == "positive" for value in values),
        sum(value.dimensions.stability.assessment == "stable" for value in values),
        sum(value.dimensions.scarcity.assessment in {"scarce", "very_scarce"} for value in values),
        sum(value.supportive_dimension_count == 3 for value in values),
        sum(value.dimensions.stability.assessment == "volatile" for value in values),
        sum(value.dimensions.scarcity.assessment in {"common", "abundant"} for value in values),
        sum(value.dimensions.momentum.assessment == "negative" for value in values),
    )


def _positive(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise MarketplaceOpportunityDomainError(f"{name} must be positive.")


def _text(value, name):
    if type(value) is not str or not value.strip():
        raise TypeError(f"{name} must be non-empty text.")

