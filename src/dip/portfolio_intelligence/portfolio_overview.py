"""Deterministic Portfolio Overview aggregation over owned-release facts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from dip.decision_intelligence import (
    OpportunityAssessment,
    OpportunityEvidenceCoverage,
    OpportunityMomentumAssessment,
    OpportunityScarcityAssessment,
    OpportunityStabilityAssessment,
    ReleaseOpportunity,
)
from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus


MODULE_ID = "portfolio_overview"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"


class PortfolioOverviewDomainError(ValueError):
    """Raised when Portfolio Overview values contradict their aggregate."""


class PortfolioAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class PortfolioEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class PortfolioReleaseMatchState(str, Enum):
    MATCHED_USABLE = "matched_usable"
    MATCHED_INSUFFICIENT = "matched_insufficient"
    UNMATCHED = "unmatched"


class PortfolioOverviewReasonCode(str, Enum):
    ALL_OWNED_RELEASES_MATCHED = "all_owned_releases_matched"
    SOME_OWNED_RELEASES_UNMATCHED = "some_owned_releases_unmatched"
    NO_OWNED_RELEASES_MATCHED = "no_owned_releases_matched"
    ALL_MATCHED_RELEASES_USABLE = "all_matched_releases_usable"
    PARTIAL_OPPORTUNITY_COVERAGE = "partial_opportunity_coverage"
    LIMITED_OPPORTUNITY_COVERAGE = "limited_opportunity_coverage"
    OPPORTUNITY_SOURCE_MISSING = "opportunity_source_missing"
    OPPORTUNITY_SOURCE_INCOMPATIBLE = "opportunity_source_incompatible"
    EMPTY_PORTFOLIO = "empty_portfolio"
    MALFORMED_OWNERSHIP_INPUT = "malformed_ownership_input"
    MULTIPLE_OWNED_COPIES = "multiple_owned_copies"
    STRONG_OPPORTUNITY_CATEGORY_PRESENT = "strong_opportunity_category_present"
    CONSTRAINED_OPPORTUNITY_CATEGORY_PRESENT = "constrained_opportunity_category_present"
    INSUFFICIENT_RELEASE_EVIDENCE_PRESENT = "insufficient_release_evidence_present"
    CATEGORY_CONCENTRATION_PRESENT = "category_concentration_present"


class PortfolioOverviewDiagnosticCode(str, Enum):
    OPPORTUNITY_SOURCE_MISSING = "opportunity_source_missing"
    OPPORTUNITY_SOURCE_INCOMPATIBLE = "opportunity_source_incompatible"
    MALFORMED_OWNED_RELEASE_IDENTITY = "malformed_owned_release_identity"
    DUPLICATE_OWNED_RELEASE_IDENTITY = "duplicate_owned_release_identity"
    MULTIPLE_OWNED_COPIES_NORMALIZED = "multiple_owned_copies_normalized"
    OWNED_RELEASE_MISSING_FROM_OPPORTUNITY = "owned_release_missing_from_opportunity"
    OPPORTUNITY_RELEASE_NOT_OWNED = "opportunity_release_not_owned"
    INSUFFICIENT_RELEASE_EVIDENCE = "insufficient_release_evidence"
    EMPTY_PORTFOLIO = "empty_portfolio"
    NO_USABLE_MATCHED_INTELLIGENCE = "no_usable_matched_intelligence"


@dataclass(frozen=True)
class PortfolioOverviewRuleConfiguration:
    partial_coverage_threshold: Decimal = Decimal("0.75")

    def __post_init__(self) -> None:
        if type(self.partial_coverage_threshold) is not Decimal:
            raise TypeError("partial_coverage_threshold must be a Decimal.")
        if not self.partial_coverage_threshold.is_finite():
            raise ValueError("partial_coverage_threshold must be finite.")
        if not Decimal("0") < self.partial_coverage_threshold < Decimal("1"):
            raise ValueError("partial_coverage_threshold must be between zero and one.")


@dataclass(frozen=True)
class OwnedReleaseFact:
    release_id: int
    quantity: int = 1

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _positive(self.quantity, "quantity")


@dataclass(frozen=True)
class PortfolioOverviewDiagnostic:
    code: PortfolioOverviewDiagnosticCode
    message: str
    release_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not PortfolioOverviewDiagnosticCode:
            raise TypeError("code must be a PortfolioOverviewDiagnosticCode.")
        if type(self.message) is not str or not self.message:
            raise TypeError("message must be a non-empty string.")
        if self.release_id is not None:
            _positive(self.release_id, "release_id")


@dataclass(frozen=True)
class PortfolioSourceProvenance:
    collection_snapshot_id: int | None
    opportunity_module_id: str
    opportunity_module_version: str | None
    opportunity_rule_set_version: str | None
    opportunity_history_snapshot_ids: tuple[str, ...] = ()
    compatible: bool = True
    opportunity_diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.collection_snapshot_id is not None:
            _positive(self.collection_snapshot_id, "collection_snapshot_id")
        if type(self.opportunity_module_id) is not str or not self.opportunity_module_id:
            raise TypeError("opportunity_module_id must be a non-empty string.")
        ids = tuple(self.opportunity_history_snapshot_ids)
        diagnostics = tuple(self.opportunity_diagnostics)
        if any(type(value) is not str or not value for value in ids):
            raise TypeError("opportunity_history_snapshot_ids must contain non-empty strings.")
        if len(set(ids)) != len(ids):
            raise PortfolioOverviewDomainError("Opportunity history snapshot IDs must be unique.")
        if any(type(value) is not str or not value for value in diagnostics):
            raise TypeError("opportunity_diagnostics must contain non-empty strings.")
        object.__setattr__(self, "opportunity_history_snapshot_ids", ids)
        object.__setattr__(self, "opportunity_diagnostics", diagnostics)


@dataclass(frozen=True)
class PortfolioOverviewInput:
    owned_releases: tuple[OwnedReleaseFact, ...] = ()
    opportunity_releases: tuple[ReleaseOpportunity, ...] = ()
    source_provenance: PortfolioSourceProvenance | None = None
    malformed_owned_entry_count: int = 0
    diagnostics: tuple[PortfolioOverviewDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        owned = tuple(self.owned_releases)
        releases = tuple(self.opportunity_releases)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not OwnedReleaseFact for value in owned):
            raise TypeError("owned_releases contains invalid values.")
        if any(type(value) is not ReleaseOpportunity for value in releases):
            raise TypeError("opportunity_releases contains invalid values.")
        if len({value.release_id for value in owned}) != len(owned):
            raise PortfolioOverviewDomainError("Owned release facts must be normalized by release_id.")
        if len({value.release_id for value in releases}) != len(releases):
            raise PortfolioOverviewDomainError("Opportunity release identities must be unique.")
        _non_negative(self.malformed_owned_entry_count, "malformed_owned_entry_count")
        if any(type(value) is not PortfolioOverviewDiagnostic for value in diagnostics):
            raise TypeError("diagnostics contains invalid values.")
        object.__setattr__(self, "owned_releases", tuple(sorted(owned, key=lambda value: value.release_id)))
        object.__setattr__(self, "opportunity_releases", releases)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class PortfolioDistributionEntry:
    state: str
    count: int
    all_owned_ratio: Decimal
    matched_ratio: Decimal
    usable_ratio: Decimal
    release_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.state) is not str or not self.state:
            raise TypeError("state must be a non-empty string.")
        _non_negative(self.count, "count")
        ids = tuple(self.release_ids)
        if ids != tuple(sorted(ids)) or len(set(ids)) != len(ids):
            raise PortfolioOverviewDomainError("Distribution release IDs must be unique and ascending.")
        if self.count != len(ids):
            raise PortfolioOverviewDomainError("Distribution count must equal release ID count.")
        for value in (self.all_owned_ratio, self.matched_ratio, self.usable_ratio):
            if type(value) is not Decimal:
                raise TypeError("Distribution ratios must be Decimals.")
            if not value.is_finite() or value < 0 or value > 1:
                raise ValueError("Distribution ratios must be finite values from zero to one.")
        object.__setattr__(self, "release_ids", ids)


@dataclass(frozen=True)
class PortfolioDistribution:
    dimension: str
    all_owned_denominator: int
    matched_denominator: int
    usable_denominator: int
    entries: tuple[PortfolioDistributionEntry, ...]

    def __post_init__(self) -> None:
        for value in (self.all_owned_denominator, self.matched_denominator, self.usable_denominator):
            _non_negative(value, "distribution denominator")
        entries = tuple(self.entries)
        if any(type(value) is not PortfolioDistributionEntry for value in entries):
            raise TypeError("entries contains invalid values.")
        if sum(value.count for value in entries) != self.matched_denominator:
            raise PortfolioOverviewDomainError("Distribution counts must equal matched denominator.")
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class PortfolioConcentrationFacts:
    dimension: str
    largest_category: str | None
    largest_category_count: int
    largest_category_ratio: Decimal
    represented_category_count: int


@dataclass(frozen=True)
class PortfolioReleaseOverview:
    release_id: int
    quantity: int
    match_state: PortfolioReleaseMatchState
    opportunity_assessment: OpportunityAssessment | None
    opportunity_evidence_coverage: OpportunityEvidenceCoverage | None
    momentum_assessment: OpportunityMomentumAssessment | None
    momentum_evidence_coverage: OpportunityEvidenceCoverage | None
    stability_assessment: OpportunityStabilityAssessment | None
    stability_evidence_coverage: OpportunityEvidenceCoverage | None
    scarcity_assessment: OpportunityScarcityAssessment | None
    scarcity_evidence_coverage: OpportunityEvidenceCoverage | None
    opportunity_reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _positive(self.quantity, "quantity")
        if type(self.match_state) is not PortfolioReleaseMatchState:
            raise TypeError("match_state must be a PortfolioReleaseMatchState.")
        reasons = tuple(self.opportunity_reason_codes)
        if any(type(value) is not str or not value for value in reasons):
            raise TypeError("opportunity_reason_codes must contain non-empty strings.")
        if self.match_state is PortfolioReleaseMatchState.UNMATCHED:
            dimension_values = (
                self.opportunity_assessment, self.opportunity_evidence_coverage,
                self.momentum_assessment, self.momentum_evidence_coverage,
                self.stability_assessment, self.stability_evidence_coverage,
                self.scarcity_assessment, self.scarcity_evidence_coverage,
            )
            if any(value is not None for value in dimension_values) or reasons:
                raise PortfolioOverviewDomainError("Unmatched releases cannot contain fabricated intelligence.")
        object.__setattr__(self, "opportunity_reason_codes", reasons)


@dataclass(frozen=True)
class PortfolioOwnershipSummary:
    total_owned_entry_count: int
    unique_owned_release_count: int
    duplicate_copy_count: int
    valid_owned_release_count: int
    malformed_owned_entry_count: int

    def __post_init__(self) -> None:
        for name in (
            "total_owned_entry_count", "unique_owned_release_count",
            "duplicate_copy_count", "valid_owned_release_count",
            "malformed_owned_entry_count",
        ):
            _non_negative(getattr(self, name), name)
        if self.valid_owned_release_count != self.unique_owned_release_count:
            raise PortfolioOverviewDomainError("Valid and unique owned release counts must agree.")
        if self.total_owned_entry_count != self.unique_owned_release_count + self.duplicate_copy_count:
            raise PortfolioOverviewDomainError("Owned entry and duplicate-copy counts are inconsistent.")


@dataclass(frozen=True)
class PortfolioOverviewSummary:
    ownership: PortfolioOwnershipSummary
    matched_owned_release_count: int
    unmatched_owned_release_count: int
    usable_opportunity_release_count: int
    insufficient_opportunity_release_count: int
    evidence_coverage: PortfolioEvidenceCoverage
    coverage_numerator: int
    coverage_denominator: int
    coverage_ratio: Decimal
    total_release_detail_count: int

    def __post_init__(self) -> None:
        if type(self.ownership) is not PortfolioOwnershipSummary:
            raise TypeError("ownership must be a PortfolioOwnershipSummary.")
        for name in (
            "matched_owned_release_count", "unmatched_owned_release_count",
            "usable_opportunity_release_count", "insufficient_opportunity_release_count",
            "coverage_numerator", "coverage_denominator", "total_release_detail_count",
        ):
            _non_negative(getattr(self, name), name)
        if type(self.evidence_coverage) is not PortfolioEvidenceCoverage:
            raise TypeError("evidence_coverage must be a PortfolioEvidenceCoverage.")
        if type(self.coverage_ratio) is not Decimal:
            raise TypeError("coverage_ratio must be a Decimal.")
        if self.coverage_ratio != _ratio(self.coverage_numerator, self.coverage_denominator):
            raise PortfolioOverviewDomainError("Portfolio coverage ratio is inconsistent.")
        if self.coverage_denominator != self.ownership.unique_owned_release_count:
            raise PortfolioOverviewDomainError("Portfolio coverage denominator is inconsistent.")
        if self.coverage_numerator != self.usable_opportunity_release_count:
            raise PortfolioOverviewDomainError("Portfolio coverage numerator is inconsistent.")
        if self.matched_owned_release_count + self.unmatched_owned_release_count != self.coverage_denominator:
            raise PortfolioOverviewDomainError("Portfolio matching totals are inconsistent.")
        if self.usable_opportunity_release_count + self.insufficient_opportunity_release_count != self.matched_owned_release_count:
            raise PortfolioOverviewDomainError("Portfolio Opportunity totals are inconsistent.")


@dataclass(frozen=True)
class PortfolioOverviewOutput:
    analysis_state: PortfolioAnalysisState
    rule_set_version: str
    rule_configuration: PortfolioOverviewRuleConfiguration
    source_provenance: PortfolioSourceProvenance | None
    summary: PortfolioOverviewSummary
    opportunity_distribution: PortfolioDistribution
    momentum_distribution: PortfolioDistribution
    stability_distribution: PortfolioDistribution
    scarcity_distribution: PortfolioDistribution
    concentration_facts: tuple[PortfolioConcentrationFacts, ...]
    releases: tuple[PortfolioReleaseOverview, ...]
    reason_codes: tuple[PortfolioOverviewReasonCode, ...]
    diagnostics: tuple[PortfolioOverviewDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.rule_set_version != RULE_SET_VERSION:
            raise PortfolioOverviewDomainError("Unsupported Portfolio Overview rule-set version.")
        releases = tuple(self.releases)
        if releases != tuple(sorted(releases, key=_release_order)):
            raise PortfolioOverviewDomainError("Portfolio releases must use canonical order.")
        if self.summary.total_release_detail_count != len(releases):
            raise PortfolioOverviewDomainError("Portfolio detail count is inconsistent.")
        if self.summary.ownership.unique_owned_release_count != len(releases):
            raise PortfolioOverviewDomainError("Portfolio ownership and detail counts are inconsistent.")
        distributions = (
            self.opportunity_distribution,
            self.momentum_distribution,
            self.stability_distribution,
            self.scarcity_distribution,
        )
        expected_denominators = (
            self.summary.ownership.unique_owned_release_count,
            self.summary.matched_owned_release_count,
            self.summary.usable_opportunity_release_count,
        )
        if any(
            (value.all_owned_denominator, value.matched_denominator, value.usable_denominator)
            != expected_denominators
            for value in distributions
        ):
            raise PortfolioOverviewDomainError("Distribution denominators are inconsistent.")
        concentrations = tuple(self.concentration_facts)
        if concentrations != tuple(_concentration(value) for value in distributions):
            raise PortfolioOverviewDomainError("Portfolio concentration facts are inconsistent.")
        object.__setattr__(self, "concentration_facts", tuple(self.concentration_facts))
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


_OPPORTUNITY_ORDER = tuple(value.value for value in OpportunityAssessment)
_MOMENTUM_ORDER = tuple(value.value for value in OpportunityMomentumAssessment)
_STABILITY_ORDER = tuple(value.value for value in OpportunityStabilityAssessment)
_SCARCITY_ORDER = tuple(value.value for value in OpportunityScarcityAssessment)


class PortfolioOverviewModule:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, rule_configuration: PortfolioOverviewRuleConfiguration = PortfolioOverviewRuleConfiguration()):
        if type(rule_configuration) is not PortfolioOverviewRuleConfiguration:
            raise TypeError("rule_configuration must be a PortfolioOverviewRuleConfiguration.")
        self._rules = rule_configuration

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        supplied = context.portfolio_overview_input
        if supplied is None:
            supplied = PortfolioOverviewInput(
                diagnostics=(PortfolioOverviewDiagnostic(
                    PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_MISSING,
                    "Marketplace Opportunity input was not supplied.",
                ),)
            )
        if type(supplied) is not PortfolioOverviewInput:
            raise TypeError("portfolio_overview_input must be a PortfolioOverviewInput.")
        output = _overview(supplied, self._rules)
        status = (
            IntelligenceStatus.SKIPPED
            if output.analysis_state is PortfolioAnalysisState.INSUFFICIENT_DATA
            else IntelligenceStatus.COMPLETED
        )
        return IntelligenceResult(
            module_id=MODULE_ID,
            status=status,
            summary=(
                "Portfolio Overview has insufficient compatible owned-portfolio and Marketplace Opportunity evidence."
                if status is IntelligenceStatus.SKIPPED
                else f"Aggregated Marketplace Opportunity evidence for {output.summary.ownership.unique_owned_release_count} owned release"
                f"{'' if output.summary.ownership.unique_owned_release_count == 1 else 's'}."
            ),
            metrics={"output": output},
            evidence=tuple(
                f"Release {value.release_id} is {value.match_state.value}."
                for value in output.releases
            ),
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in output.diagnostics),
            module_version=MODULE_VERSION,
        )


def _overview(supplied: PortfolioOverviewInput, rules: PortfolioOverviewRuleConfiguration) -> PortfolioOverviewOutput:
    owned = {value.release_id: value for value in supplied.owned_releases}
    opportunity = {value.release_id: value for value in supplied.opportunity_releases}
    source_compatible = supplied.source_provenance is not None and supplied.source_provenance.compatible
    releases = []
    for release_id, holding in owned.items():
        detail = opportunity.get(release_id) if source_compatible else None
        if detail is None:
            releases.append(_unmatched(holding))
        else:
            releases.append(_matched(holding, detail))
    releases = tuple(sorted(releases, key=_release_order))
    matched = tuple(value for value in releases if value.match_state is not PortfolioReleaseMatchState.UNMATCHED)
    usable = tuple(value for value in matched if value.match_state is PortfolioReleaseMatchState.MATCHED_USABLE)
    denominator = len(owned)
    ratio = _ratio(len(usable), denominator)
    coverage = _coverage(source_compatible, denominator, len(usable), ratio, rules)
    ownership = PortfolioOwnershipSummary(
        sum(value.quantity for value in owned.values()),
        len(owned),
        sum(value.quantity - 1 for value in owned.values()),
        len(owned),
        supplied.malformed_owned_entry_count,
    )
    summary = PortfolioOverviewSummary(
        ownership, len(matched), denominator - len(matched), len(usable),
        len(matched) - len(usable), coverage, len(usable), denominator, ratio, len(releases),
    )
    distributions = (
        _distribution("opportunity", _OPPORTUNITY_ORDER, releases, "opportunity_assessment"),
        _distribution("momentum", _MOMENTUM_ORDER, releases, "momentum_assessment"),
        _distribution("stability", _STABILITY_ORDER, releases, "stability_assessment"),
        _distribution("scarcity", _SCARCITY_ORDER, releases, "scarcity_assessment"),
    )
    concentrations = tuple(_concentration(value) for value in distributions)
    diagnostics = _diagnostics(supplied, owned, opportunity, releases, source_compatible)
    reasons = _reasons(summary, distributions, source_compatible, diagnostics)
    state = (
        PortfolioAnalysisState.INSUFFICIENT_DATA
        if coverage is PortfolioEvidenceCoverage.INSUFFICIENT
        else PortfolioAnalysisState.COMPLETE
        if coverage is PortfolioEvidenceCoverage.COMPLETE and not diagnostics
        else PortfolioAnalysisState.PARTIAL
    )
    return PortfolioOverviewOutput(
        state, RULE_SET_VERSION, rules, supplied.source_provenance, summary,
        *distributions, concentrations, releases, reasons, diagnostics,
    )


def _matched(holding: OwnedReleaseFact, detail: ReleaseOpportunity) -> PortfolioReleaseOverview:
    usable = (
        detail.assessment is not OpportunityAssessment.INSUFFICIENT
        and detail.evidence_coverage is not OpportunityEvidenceCoverage.INSUFFICIENT
    )
    dimensions = detail.dimensions
    return PortfolioReleaseOverview(
        holding.release_id, holding.quantity,
        PortfolioReleaseMatchState.MATCHED_USABLE if usable else PortfolioReleaseMatchState.MATCHED_INSUFFICIENT,
        detail.assessment, detail.evidence_coverage,
        _enum_or_none(OpportunityMomentumAssessment, dimensions.momentum.assessment),
        dimensions.momentum.evidence_coverage,
        _enum_or_none(OpportunityStabilityAssessment, dimensions.stability.assessment),
        dimensions.stability.evidence_coverage,
        _enum_or_none(OpportunityScarcityAssessment, dimensions.scarcity.assessment),
        dimensions.scarcity.evidence_coverage,
        tuple(value.value for value in detail.reason_codes),
    )


def _unmatched(holding: OwnedReleaseFact) -> PortfolioReleaseOverview:
    return PortfolioReleaseOverview(
        holding.release_id, holding.quantity, PortfolioReleaseMatchState.UNMATCHED,
        None, None, None, None, None, None, None, None,
    )


def _distribution(dimension: str, order: tuple[str, ...], releases: tuple[PortfolioReleaseOverview, ...], attribute: str) -> PortfolioDistribution:
    matched = tuple(value for value in releases if value.match_state is not PortfolioReleaseMatchState.UNMATCHED)
    usable = tuple(value for value in releases if value.match_state is PortfolioReleaseMatchState.MATCHED_USABLE)
    values = {state: [] for state in order}
    for release in matched:
        state = getattr(release, attribute)
        values[state.value if state is not None else "insufficient"].append(release.release_id)
    usable_values = Counter(
        getattr(release, attribute).value
        for release in usable
        if getattr(release, attribute) is not None
    )
    entries = tuple(
        PortfolioDistributionEntry(
            state, len(values[state]), _ratio(len(values[state]), len(releases)),
            _ratio(len(values[state]), len(matched)), _ratio(usable_values[state], len(usable)),
            tuple(sorted(values[state])),
        )
        for state in order
    )
    return PortfolioDistribution(dimension, len(releases), len(matched), len(usable), entries)


def _concentration(distribution: PortfolioDistribution) -> PortfolioConcentrationFacts:
    represented = tuple(value for value in distribution.entries if value.count)
    if not represented:
        return PortfolioConcentrationFacts(distribution.dimension, None, 0, Decimal("0"), 0)
    largest = max(represented, key=lambda value: value.count)
    return PortfolioConcentrationFacts(
        distribution.dimension, largest.state, largest.count,
        _ratio(largest.count, distribution.matched_denominator), len(represented),
    )


def _coverage(compatible: bool, denominator: int, usable: int, ratio: Decimal, rules: PortfolioOverviewRuleConfiguration) -> PortfolioEvidenceCoverage:
    if not compatible or denominator == 0 or usable == 0:
        return PortfolioEvidenceCoverage.INSUFFICIENT
    if usable == denominator:
        return PortfolioEvidenceCoverage.COMPLETE
    if ratio >= rules.partial_coverage_threshold:
        return PortfolioEvidenceCoverage.PARTIAL
    return PortfolioEvidenceCoverage.LIMITED


def _diagnostics(supplied, owned, opportunity, releases, compatible):
    values = list(supplied.diagnostics)
    if supplied.source_provenance is None:
        if not any(value.code is PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_MISSING for value in values):
            values.append(PortfolioOverviewDiagnostic(PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_MISSING, "Marketplace Opportunity result was not supplied."))
    elif not compatible:
        values.append(PortfolioOverviewDiagnostic(PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_INCOMPATIBLE, "Marketplace Opportunity result is incompatible."))
    if not owned:
        values.append(PortfolioOverviewDiagnostic(PortfolioOverviewDiagnosticCode.EMPTY_PORTFOLIO, "No valid owned releases were supplied."))
    for value in releases:
        if value.match_state is PortfolioReleaseMatchState.UNMATCHED and compatible:
            values.append(PortfolioOverviewDiagnostic(PortfolioOverviewDiagnosticCode.OWNED_RELEASE_MISSING_FROM_OPPORTUNITY, f"Owned release {value.release_id} is absent from Marketplace Opportunity.", value.release_id))
        elif value.match_state is PortfolioReleaseMatchState.MATCHED_INSUFFICIENT:
            values.append(PortfolioOverviewDiagnostic(PortfolioOverviewDiagnosticCode.INSUFFICIENT_RELEASE_EVIDENCE, f"Owned release {value.release_id} has insufficient Marketplace Opportunity evidence.", value.release_id))
    for release_id in sorted(set(opportunity) - set(owned)):
        values.append(PortfolioOverviewDiagnostic(PortfolioOverviewDiagnosticCode.OPPORTUNITY_RELEASE_NOT_OWNED, f"Marketplace Opportunity release {release_id} is not owned.", release_id))
    if owned and not any(value.match_state is PortfolioReleaseMatchState.MATCHED_USABLE for value in releases):
        values.append(PortfolioOverviewDiagnostic(PortfolioOverviewDiagnosticCode.NO_USABLE_MATCHED_INTELLIGENCE, "No owned release has usable Marketplace Opportunity evidence."))
    return tuple(sorted(
        values,
        key=lambda value: (
            tuple(PortfolioOverviewDiagnosticCode).index(value.code),
            value.release_id is None,
            value.release_id or 0,
            value.message,
        ),
    ))


def _reasons(summary, distributions, compatible, diagnostics):
    values = []
    if not compatible:
        values.append(
            PortfolioOverviewReasonCode.OPPORTUNITY_SOURCE_MISSING
            if any(
                value.code is PortfolioOverviewDiagnosticCode.OPPORTUNITY_SOURCE_MISSING
                for value in diagnostics
            )
            else PortfolioOverviewReasonCode.OPPORTUNITY_SOURCE_INCOMPATIBLE
        )
    if summary.ownership.unique_owned_release_count == 0:
        values.append(PortfolioOverviewReasonCode.EMPTY_PORTFOLIO)
    elif summary.matched_owned_release_count == summary.ownership.unique_owned_release_count:
        values.append(PortfolioOverviewReasonCode.ALL_OWNED_RELEASES_MATCHED)
    elif summary.matched_owned_release_count:
        values.append(PortfolioOverviewReasonCode.SOME_OWNED_RELEASES_UNMATCHED)
    else:
        values.append(PortfolioOverviewReasonCode.NO_OWNED_RELEASES_MATCHED)
    if summary.matched_owned_release_count and summary.usable_opportunity_release_count == summary.matched_owned_release_count:
        values.append(PortfolioOverviewReasonCode.ALL_MATCHED_RELEASES_USABLE)
    if summary.evidence_coverage is PortfolioEvidenceCoverage.PARTIAL:
        values.append(PortfolioOverviewReasonCode.PARTIAL_OPPORTUNITY_COVERAGE)
    elif summary.evidence_coverage is PortfolioEvidenceCoverage.LIMITED:
        values.append(PortfolioOverviewReasonCode.LIMITED_OPPORTUNITY_COVERAGE)
    if summary.ownership.malformed_owned_entry_count:
        values.append(PortfolioOverviewReasonCode.MALFORMED_OWNERSHIP_INPUT)
    if summary.ownership.duplicate_copy_count:
        values.append(PortfolioOverviewReasonCode.MULTIPLE_OWNED_COPIES)
    opportunity = distributions[0]
    present = {value.state for value in opportunity.entries if value.count}
    if OpportunityAssessment.STRONG.value in present:
        values.append(PortfolioOverviewReasonCode.STRONG_OPPORTUNITY_CATEGORY_PRESENT)
    if OpportunityAssessment.CONSTRAINED.value in present:
        values.append(PortfolioOverviewReasonCode.CONSTRAINED_OPPORTUNITY_CATEGORY_PRESENT)
    if summary.insufficient_opportunity_release_count:
        values.append(PortfolioOverviewReasonCode.INSUFFICIENT_RELEASE_EVIDENCE_PRESENT)
    if any(value.count > 1 for value in opportunity.entries):
        values.append(PortfolioOverviewReasonCode.CATEGORY_CONCENTRATION_PRESENT)
    return tuple(values)


def _release_order(value):
    states = {
        PortfolioReleaseMatchState.MATCHED_USABLE: 0,
        PortfolioReleaseMatchState.MATCHED_INSUFFICIENT: 1,
        PortfolioReleaseMatchState.UNMATCHED: 2,
    }
    assessment = len(_OPPORTUNITY_ORDER) if value.opportunity_assessment is None else _OPPORTUNITY_ORDER.index(value.opportunity_assessment.value)
    return states[value.match_state], assessment, value.release_id


def _ratio(numerator: int, denominator: int) -> Decimal:
    return Decimal("0") if denominator == 0 else Decimal(numerator) / Decimal(denominator)


def _enum_or_none(enum_type, value):
    return None if value is None else enum_type(value)


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
