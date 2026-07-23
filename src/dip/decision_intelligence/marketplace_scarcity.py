"""Deterministic assessment of limited observed Marketplace availability."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus


MODULE_ID = "marketplace_scarcity"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"
_SOURCE_ORDER = (
    "rare_appearances",
    "listing_lifecycle",
    "marketplace_activity",
    "supply_changes",
    "marketplace_stability",
    "marketplace_momentum",
)
_REQUIRED = _SOURCE_ORDER[:2]


class MarketplaceScarcityDomainError(ValueError):
    """Raised when Scarcity values contradict the explicit rule contract."""


def _positive(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise MarketplaceScarcityDomainError(f"{name} must be positive.")


def _non_negative(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise MarketplaceScarcityDomainError(f"{name} cannot be negative.")


def _ratio(value, name, *, allow_zero=True):
    if type(value) is not Decimal:
        raise TypeError(f"{name} must be a Decimal.")
    if not value.is_finite() or value > Decimal(1) or value < Decimal(0) or (not allow_zero and value == 0):
        raise MarketplaceScarcityDomainError(f"{name} must be a valid Decimal proportion.")


def _text(value, name):
    if type(value) is not str or not value.strip():
        raise TypeError(f"{name} must be non-empty text.")


class ScarcityAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class ScarcityComponentState(str, Enum):
    ABUNDANT = "abundant"
    COMMON = "common"
    LIMITED = "limited"
    SCARCE = "scarce"
    VERY_SCARCE = "very_scarce"
    INSUFFICIENT = "insufficient"


class ScarcityAssessment(str, Enum):
    ABUNDANT = "abundant"
    COMMON = "common"
    LIMITED = "limited"
    SCARCE = "scarce"
    VERY_SCARCE = "very_scarce"
    INSUFFICIENT = "insufficient"


class ScarcityEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class ScarcityReasonCode(str, Enum):
    NO_CURRENT_LISTINGS = "no_current_listings"
    ONE_CURRENT_LISTING = "one_current_listing"
    FEW_CURRENT_LISTINGS = "few_current_listings"
    SEVERAL_CURRENT_LISTINGS = "several_current_listings"
    MANY_CURRENT_LISTINGS = "many_current_listings"
    CONTINUOUS_MARKETPLACE_APPEARANCE = "continuous_marketplace_appearance"
    INTERMITTENT_MARKETPLACE_APPEARANCE = "intermittent_marketplace_appearance"
    LOW_APPEARANCE_RATIO = "low_appearance_ratio"
    EXTENDED_INTERNAL_ABSENCE = "extended_internal_absence"
    ALL_LISTINGS_ENDED = "all_listings_ended"
    HIGH_LISTING_DISRUPTION = "high_listing_disruption"
    PERSISTENT_LISTING_AVAILABILITY = "persistent_listing_availability"
    PARTIAL_REQUIRED_SOURCE = "partial_required_source"
    SPARSE_RELEASE_EVIDENCE = "sparse_release_evidence"
    INSUFFICIENT_CORE_COMPONENTS = "insufficient_core_components"
    OBSERVED_AVAILABILITY_VERY_SCARCE = "observed_availability_very_scarce"
    MULTIPLE_SCARCE_COMPONENTS = "multiple_scarce_components"
    BROAD_OBSERVED_AVAILABILITY = "broad_observed_availability"
    COMMON_OBSERVED_AVAILABILITY = "common_observed_availability"
    MIXED_SCARCITY_EVIDENCE = "mixed_scarcity_evidence"


class MarketplaceScarcityDiagnosticCode(str, Enum):
    MISSING_REQUIRED_SOURCE = "missing_required_source"
    DUPLICATE_SOURCE_RESULT = "duplicate_source_result"
    UNEXPECTED_SOURCE_RESULT = "unexpected_source_result"
    UNSUPPORTED_SOURCE_VERSION = "unsupported_source_version"
    MALFORMED_TYPED_OUTPUT = "malformed_typed_output"
    SOURCE_NOT_COMPLETED = "source_not_completed"
    INCOMPATIBLE_HISTORY = "incompatible_history"
    PARTIAL_SOURCE_DIAGNOSTICS = "partial_source_diagnostics"
    OPTIONAL_SOURCE_EXCLUDED = "optional_source_excluded"
    SPARSE_RELEASE_EVIDENCE = "sparse_release_evidence"
    COMPONENT_UNAVAILABLE = "component_unavailable"


class ScarcityListingState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    DISAPPEARED = "disappeared"
    REAPPEARED = "reappeared"
    INTERMITTENT = "intermittent"
    ENDED = "ended"


@dataclass(frozen=True)
class AvailabilityThresholds:
    abundant_minimum: int = 10
    common_minimum: int = 5
    limited_minimum: int = 2

    def __post_init__(self):
        for name in ("abundant_minimum", "common_minimum", "limited_minimum"):
            _positive(getattr(self, name), name)
        if not self.abundant_minimum > self.common_minimum > self.limited_minimum > 1:
            raise MarketplaceScarcityDomainError("Availability thresholds must be strictly descending and non-overlapping.")


@dataclass(frozen=True)
class AppearanceScarcityThresholds:
    common_minimum: Decimal = Decimal("0.75")
    limited_minimum: Decimal = Decimal("0.50")

    def __post_init__(self):
        _ratio(self.common_minimum, "common_minimum", allow_zero=False)
        _ratio(self.limited_minimum, "limited_minimum", allow_zero=False)
        if self.common_minimum <= self.limited_minimum:
            raise MarketplaceScarcityDomainError("Appearance thresholds must be strictly descending.")


@dataclass(frozen=True)
class ListingScarcityThresholds:
    persistent_ratio: Decimal = Decimal("0.75")
    disrupted_ratio: Decimal = Decimal("0.50")

    def __post_init__(self):
        _ratio(self.persistent_ratio, "persistent_ratio", allow_zero=False)
        _ratio(self.disrupted_ratio, "disrupted_ratio", allow_zero=False)


@dataclass(frozen=True)
class MarketplaceScarcityDiagnostic:
    code: MarketplaceScarcityDiagnosticCode
    message: str
    source_module_id: str | None = None
    release_id: int | None = None

    def __post_init__(self):
        if type(self.code) is not MarketplaceScarcityDiagnosticCode:
            raise TypeError("code must be a MarketplaceScarcityDiagnosticCode.")
        _text(self.message, "message")
        if self.source_module_id is not None:
            _text(self.source_module_id, "source_module_id")
        if self.release_id is not None:
            _positive(self.release_id, "release_id")


@dataclass(frozen=True)
class ScarcitySourceProvenance:
    module_id: str
    module_version: str | None
    result_status: IntelligenceStatus
    compatible: bool
    partial: bool
    history_snapshot_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self):
        if self.module_id not in _SOURCE_ORDER:
            raise MarketplaceScarcityDomainError("Unsupported Scarcity source.")
        if type(self.result_status) is not IntelligenceStatus:
            raise TypeError("result_status must be an IntelligenceStatus.")
        ids = tuple(self.history_snapshot_ids)
        diagnostics = tuple(self.diagnostics)
        if len(set(ids)) != len(ids) or any(type(value) is not str or not value for value in (*ids, *diagnostics)):
            raise MarketplaceScarcityDomainError("Provenance strings must be non-empty and snapshot IDs unique.")
        object.__setattr__(self, "history_snapshot_ids", ids)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class ScarcityAppearanceFact:
    release_id: int
    appearance_count: int
    history_snapshot_count: int
    appearance_ratio: Decimal
    longest_internal_absence: int

    def __post_init__(self):
        _positive(self.release_id, "release_id")
        _positive(self.appearance_count, "appearance_count")
        _positive(self.history_snapshot_count, "history_snapshot_count")
        _ratio(self.appearance_ratio, "appearance_ratio", allow_zero=False)
        _non_negative(self.longest_internal_absence, "longest_internal_absence")
        if self.appearance_ratio != Decimal(self.appearance_count) / Decimal(self.history_snapshot_count):
            raise MarketplaceScarcityDomainError("appearance_ratio must match appearance counts.")


@dataclass(frozen=True)
class ScarcityLifecycleFact:
    release_id: int
    listing_id: str
    state: ScarcityListingState
    currently_present: bool
    observation_ratio: Decimal
    disappearance_count: int
    reappearance_count: int
    longest_absence: int

    def __post_init__(self):
        _positive(self.release_id, "release_id")
        _text(self.listing_id, "listing_id")
        if type(self.state) is not ScarcityListingState or type(self.currently_present) is not bool:
            raise TypeError("Lifecycle state and presence must be typed.")
        _ratio(self.observation_ratio, "observation_ratio", allow_zero=False)
        _non_negative(self.disappearance_count, "disappearance_count")
        _non_negative(self.reappearance_count, "reappearance_count")
        _non_negative(self.longest_absence, "longest_absence")


@dataclass(frozen=True)
class ScarcitySupplyContext:
    release_id: int
    historical_supply_change_count: int | None = None
    supply_increase_count: int = 0
    supply_decrease_count: int = 0
    newly_available_count: int = 0
    no_longer_available_count: int = 0

    def __post_init__(self):
        _positive(self.release_id, "release_id")
        if self.historical_supply_change_count is not None:
            _non_negative(self.historical_supply_change_count, "historical_supply_change_count")
        for name in ("supply_increase_count", "supply_decrease_count", "newly_available_count", "no_longer_available_count"):
            _non_negative(getattr(self, name), name)


@dataclass(frozen=True)
class ScarcityDecisionContext:
    release_id: int
    stability_assessment: str | None = None
    momentum_assessment: str | None = None

    def __post_init__(self):
        _positive(self.release_id, "release_id")
        for name in ("stability_assessment", "momentum_assessment"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)


@dataclass(frozen=True)
class MarketplaceScarcityInput:
    source_provenance: tuple[ScarcitySourceProvenance, ...] = ()
    appearance_facts: tuple[ScarcityAppearanceFact, ...] = ()
    lifecycle_facts: tuple[ScarcityLifecycleFact, ...] = ()
    supply_context: tuple[ScarcitySupplyContext, ...] = ()
    decision_context: tuple[ScarcityDecisionContext, ...] = ()
    diagnostics: tuple[MarketplaceScarcityDiagnostic, ...] = ()

    def __post_init__(self):
        values = (
            (self.source_provenance, ScarcitySourceProvenance, lambda value: value.module_id),
            (self.appearance_facts, ScarcityAppearanceFact, lambda value: value.release_id),
            (self.lifecycle_facts, ScarcityLifecycleFact, lambda value: (value.release_id, value.listing_id)),
            (self.supply_context, ScarcitySupplyContext, lambda value: value.release_id),
            (self.decision_context, ScarcityDecisionContext, lambda value: value.release_id),
        )
        for collection, expected, identity in values:
            collection = tuple(collection)
            if any(type(value) is not expected for value in collection):
                raise TypeError("Scarcity input contains invalid typed facts.")
            identities = tuple(identity(value) for value in collection)
            if len(set(identities)) != len(identities):
                raise MarketplaceScarcityDomainError("Scarcity input contains duplicate identities.")
        if any(type(value) is not MarketplaceScarcityDiagnostic for value in self.diagnostics):
            raise TypeError("diagnostics contain invalid values.")
        for name in ("source_provenance", "appearance_facts", "lifecycle_facts", "supply_context", "decision_context", "diagnostics"):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    @property
    def required_sources_compatible(self):
        by_id = {value.module_id: value for value in self.source_provenance}
        return all(source in by_id and by_id[source].compatible for source in _REQUIRED)


@dataclass(frozen=True)
class ObservedAvailabilityComponent:
    state: ScarcityComponentState
    total_listing_count: int
    currently_present_count: int
    currently_present_ratio: Decimal
    active_count: int
    reappeared_count: int
    intermittent_count: int
    disappeared_count: int
    ended_count: int
    new_count: int
    thresholds: AvailabilityThresholds


@dataclass(frozen=True)
class AppearanceScarcityComponent:
    state: ScarcityComponentState
    appearance_count: int | None
    history_snapshot_count: int | None
    appearance_ratio: Decimal | None
    longest_internal_absence: int | None
    thresholds: AppearanceScarcityThresholds


@dataclass(frozen=True)
class ListingPersistenceScarcityComponent:
    state: ScarcityComponentState
    total_listing_count: int
    currently_present_count: int
    continuously_active_count: int
    disrupted_listing_count: int
    total_disappearance_count: int
    total_reappearance_count: int
    average_observation_ratio: Decimal | None
    longest_listing_absence: int
    disrupted_ratio: Decimal
    active_count: int
    reappeared_count: int
    intermittent_count: int
    disappeared_count: int
    ended_count: int
    new_count: int
    thresholds: ListingScarcityThresholds


@dataclass(frozen=True)
class ScarcityComponents:
    observed_availability: ObservedAvailabilityComponent
    appearance: AppearanceScarcityComponent
    listing_persistence: ListingPersistenceScarcityComponent
    evidence_coverage: ScarcityEvidenceCoverage

    def __post_init__(self):
        if type(self.observed_availability) is not ObservedAvailabilityComponent:
            raise TypeError("observed_availability has an invalid type.")
        if type(self.appearance) is not AppearanceScarcityComponent:
            raise TypeError("appearance has an invalid type.")
        if type(self.listing_persistence) is not ListingPersistenceScarcityComponent:
            raise TypeError("listing_persistence has an invalid type.")
        if type(self.evidence_coverage) is not ScarcityEvidenceCoverage:
            raise TypeError("evidence_coverage has an invalid type.")


@dataclass(frozen=True)
class ReleaseScarcity:
    release_id: int
    assessment: ScarcityAssessment
    components: ScarcityComponents
    supply_context: ScarcitySupplyContext | None
    stability_assessment: str | None
    momentum_assessment: str | None
    reason_codes: tuple[ScarcityReasonCode, ...]

    def __post_init__(self):
        _positive(self.release_id, "release_id")
        if type(self.assessment) is not ScarcityAssessment or type(self.components) is not ScarcityComponents:
            raise TypeError("Release Scarcity assessment and components must be typed.")
        reasons = tuple(self.reason_codes)
        if not reasons or any(type(value) is not ScarcityReasonCode for value in reasons):
            raise TypeError("reason_codes must contain ScarcityReasonCode values.")
        if len(set(reasons)) != len(reasons):
            raise MarketplaceScarcityDomainError("reason_codes must be unique.")
        if self.assessment is not _assessment(self.components):
            raise MarketplaceScarcityDomainError("Scarcity assessment is inconsistent with components.")
        object.__setattr__(self, "reason_codes", reasons)


@dataclass(frozen=True)
class MarketplaceScarcitySummary:
    release_count: int = 0
    abundant_count: int = 0
    common_count: int = 0
    limited_count: int = 0
    scarce_count: int = 0
    very_scarce_count: int = 0
    insufficient_count: int = 0
    complete_evidence_count: int = 0
    partial_evidence_count: int = 0
    limited_evidence_count: int = 0
    insufficient_evidence_count: int = 0
    zero_current_listing_count: int = 0
    one_current_listing_count: int = 0
    continuous_appearance_count: int = 0
    intermittent_appearance_count: int = 0
    high_disruption_count: int = 0


@dataclass(frozen=True)
class MarketplaceScarcityOutput:
    analysis_state: ScarcityAnalysisState
    rule_set_version: str
    availability_thresholds: AvailabilityThresholds
    appearance_thresholds: AppearanceScarcityThresholds
    listing_thresholds: ListingScarcityThresholds
    source_provenance: tuple[ScarcitySourceProvenance, ...]
    releases: tuple[ReleaseScarcity, ...]
    summary: MarketplaceScarcitySummary
    diagnostics: tuple[MarketplaceScarcityDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if type(self.analysis_state) is not ScarcityAnalysisState:
            raise TypeError("analysis_state must be a ScarcityAnalysisState.")
        if self.rule_set_version != RULE_SET_VERSION:
            raise MarketplaceScarcityDomainError("Unsupported Scarcity rule-set version.")
        for value, expected in (
            (self.availability_thresholds, AvailabilityThresholds),
            (self.appearance_thresholds, AppearanceScarcityThresholds),
            (self.listing_thresholds, ListingScarcityThresholds),
        ):
            if type(value) is not expected:
                raise TypeError("Scarcity output contains invalid thresholds.")
        releases = tuple(self.releases)
        if any(type(value) is not ReleaseScarcity for value in releases):
            raise TypeError("releases must contain ReleaseScarcity values.")
        if any(type(value) is not ScarcitySourceProvenance for value in self.source_provenance):
            raise TypeError("source_provenance contains invalid values.")
        if any(type(value) is not MarketplaceScarcityDiagnostic for value in self.diagnostics):
            raise TypeError("diagnostics contains invalid values.")
        if releases != tuple(sorted(releases, key=_release_order)):
            raise MarketplaceScarcityDomainError("Releases must use canonical Scarcity order.")
        if self.summary != _summary(releases):
            raise MarketplaceScarcityDomainError("Scarcity summary is inconsistent.")
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "source_provenance", tuple(self.source_provenance))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


class MarketplaceScarcityModule:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(self, *, availability_thresholds=AvailabilityThresholds(), appearance_thresholds=AppearanceScarcityThresholds(), listing_thresholds=ListingScarcityThresholds()):
        self._availability = availability_thresholds
        self._appearance = appearance_thresholds
        self._listing = listing_thresholds

    def analyse(self, context):
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        supplied = context.marketplace_scarcity_input
        if supplied is None:
            supplied = MarketplaceScarcityInput(diagnostics=(MarketplaceScarcityDiagnostic(MarketplaceScarcityDiagnosticCode.MISSING_REQUIRED_SOURCE, "Marketplace Scarcity input was not supplied."),))
        if type(supplied) is not MarketplaceScarcityInput:
            raise TypeError("marketplace_scarcity_input must be a MarketplaceScarcityInput.")
        if not supplied.required_sources_compatible:
            return self._result(supplied, (), ScarcityAnalysisState.INSUFFICIENT_DATA)
        appearances = {value.release_id: value for value in supplied.appearance_facts}
        lifecycles = {}
        for value in supplied.lifecycle_facts:
            lifecycles.setdefault(value.release_id, []).append(value)
        supply = {value.release_id: value for value in supplied.supply_context}
        contexts = {value.release_id: value for value in supplied.decision_context}
        release_ids = sorted(set(appearances) | set(lifecycles))
        releases = tuple(_release(
            release_id, appearances.get(release_id), tuple(lifecycles.get(release_id, ())),
            supply.get(release_id), contexts.get(release_id), supplied,
            self._availability, self._appearance, self._listing,
        ) for release_id in release_ids)
        releases = tuple(sorted(releases, key=_release_order))
        required = {value.module_id: value for value in supplied.source_provenance}
        partial = any(required[source].partial or required[source].diagnostics for source in _REQUIRED)
        state = ScarcityAnalysisState.PARTIAL if partial or any(value.components.evidence_coverage is not ScarcityEvidenceCoverage.COMPLETE for value in releases) else ScarcityAnalysisState.COMPLETE
        return self._result(supplied, releases, state)

    def _result(self, supplied, releases, state):
        output = MarketplaceScarcityOutput(
            state, RULE_SET_VERSION, self._availability, self._appearance,
            self._listing, supplied.source_provenance, releases, _summary(releases),
            supplied.diagnostics,
        )
        status = IntelligenceStatus.SKIPPED if state is ScarcityAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        return IntelligenceResult(
            MODULE_ID, status,
            "Marketplace Scarcity requires compatible Rare Appearances and Listing Lifecycle intelligence." if status is IntelligenceStatus.SKIPPED else f"Assessed observed Marketplace scarcity for {len(releases)} release{'s' if len(releases) != 1 else ''}.",
            metrics={"output": output}, module_version=MODULE_VERSION,
            diagnostics=tuple(f"{value.code.value}: {value.message}" for value in supplied.diagnostics),
            evidence=tuple(f"Release {value.release_id} has {value.assessment.value} observed Marketplace scarcity." for value in releases),
        )


def _release(release_id, appearance, lifecycle, supply, context, supplied, availability_thresholds, appearance_thresholds, listing_thresholds):
    availability = _availability(lifecycle, availability_thresholds)
    appearance_component = _appearance(appearance, appearance_thresholds)
    persistence = _persistence(lifecycle, listing_thresholds)
    required = {value.module_id: value for value in supplied.source_provenance}
    partial = any(required[source].partial or required[source].diagnostics for source in _REQUIRED)
    usable = sum(value.state is not ScarcityComponentState.INSUFFICIENT for value in (availability, appearance_component, persistence))
    if usable == 0:
        coverage = ScarcityEvidenceCoverage.INSUFFICIENT
    elif appearance is None or not lifecycle or usable == 1:
        coverage = ScarcityEvidenceCoverage.LIMITED
    elif partial:
        coverage = ScarcityEvidenceCoverage.PARTIAL
    else:
        coverage = ScarcityEvidenceCoverage.COMPLETE
    components = ScarcityComponents(availability, appearance_component, persistence, coverage)
    assessment = _assessment(components)
    return ReleaseScarcity(
        release_id, assessment, components, supply,
        None if context is None else context.stability_assessment,
        None if context is None else context.momentum_assessment,
        _reasons(availability, appearance_component, persistence, assessment, partial),
    )


def _availability(values, thresholds):
    if not values:
        return ObservedAvailabilityComponent(ScarcityComponentState.INSUFFICIENT, 0, 0, Decimal(0), 0, 0, 0, 0, 0, 0, thresholds)
    counts = Counter(value.state for value in values)
    current = sum(value.currently_present for value in values)
    state = (
        ScarcityComponentState.ABUNDANT if current >= thresholds.abundant_minimum else
        ScarcityComponentState.COMMON if current >= thresholds.common_minimum else
        ScarcityComponentState.LIMITED if current >= thresholds.limited_minimum else
        ScarcityComponentState.SCARCE if current == 1 else
        ScarcityComponentState.VERY_SCARCE
    )
    return ObservedAvailabilityComponent(
        state, len(values), current, Decimal(current) / Decimal(len(values)),
        counts[ScarcityListingState.ACTIVE], counts[ScarcityListingState.REAPPEARED],
        counts[ScarcityListingState.INTERMITTENT], counts[ScarcityListingState.DISAPPEARED],
        counts[ScarcityListingState.ENDED], counts[ScarcityListingState.NEW], thresholds,
    )


def _appearance(value, thresholds):
    if value is None:
        return AppearanceScarcityComponent(ScarcityComponentState.INSUFFICIENT, None, None, None, None, thresholds)
    ratio = value.appearance_ratio
    state = (
        ScarcityComponentState.ABUNDANT if ratio == Decimal(1) else
        ScarcityComponentState.COMMON if ratio >= thresholds.common_minimum else
        ScarcityComponentState.LIMITED if ratio >= thresholds.limited_minimum else
        ScarcityComponentState.SCARCE
    )
    return AppearanceScarcityComponent(state, value.appearance_count, value.history_snapshot_count, ratio, value.longest_internal_absence, thresholds)


def _persistence(values, thresholds):
    if not values:
        return ListingPersistenceScarcityComponent(ScarcityComponentState.INSUFFICIENT, 0, 0, 0, 0, 0, 0, None, 0, Decimal(0), 0, 0, 0, 0, 0, 0, thresholds)
    counts = Counter(value.state for value in values)
    total = len(values)
    current = sum(value.currently_present for value in values)
    active = counts[ScarcityListingState.ACTIVE]
    disrupted = sum(value.state in {ScarcityListingState.DISAPPEARED, ScarcityListingState.ENDED, ScarcityListingState.REAPPEARED, ScarcityListingState.INTERMITTENT} for value in values)
    disrupted_ratio = Decimal(disrupted) / Decimal(total)
    persistent_ratio = Decimal(active) / Decimal(total)
    if current == 0:
        state = ScarcityComponentState.VERY_SCARCE
    elif current == 1 or disrupted_ratio >= thresholds.disrupted_ratio:
        state = ScarcityComponentState.SCARCE
    elif current >= 10 and persistent_ratio >= thresholds.persistent_ratio:
        state = ScarcityComponentState.ABUNDANT
    elif current >= 5 and persistent_ratio >= thresholds.persistent_ratio:
        state = ScarcityComponentState.COMMON
    else:
        state = ScarcityComponentState.LIMITED
    return ListingPersistenceScarcityComponent(
        state, total, current, active, disrupted,
        sum(value.disappearance_count for value in values),
        sum(value.reappearance_count for value in values),
        sum((value.observation_ratio for value in values), Decimal(0)) / Decimal(total),
        max(value.longest_absence for value in values), disrupted_ratio,
        active, counts[ScarcityListingState.REAPPEARED], counts[ScarcityListingState.INTERMITTENT],
        counts[ScarcityListingState.DISAPPEARED], counts[ScarcityListingState.ENDED],
        counts[ScarcityListingState.NEW], thresholds,
    )


def _assessment(components):
    states = (components.observed_availability.state, components.appearance.state, components.listing_persistence.state)
    usable = tuple(value for value in states if value is not ScarcityComponentState.INSUFFICIENT)
    scarce = sum(value in {ScarcityComponentState.SCARCE, ScarcityComponentState.VERY_SCARCE} for value in usable)
    very = usable.count(ScarcityComponentState.VERY_SCARCE)
    if components.evidence_coverage is ScarcityEvidenceCoverage.INSUFFICIENT or len(usable) < 2:
        return ScarcityAssessment.INSUFFICIENT
    if (states[0] is ScarcityComponentState.VERY_SCARCE and states[1] in {ScarcityComponentState.SCARCE, ScarcityComponentState.VERY_SCARCE}) or very >= 2:
        return ScarcityAssessment.VERY_SCARCE
    if scarce >= 2 or (states[0] is ScarcityComponentState.SCARCE and states[1] in {ScarcityComponentState.LIMITED, ScarcityComponentState.SCARCE, ScarcityComponentState.VERY_SCARCE}):
        return ScarcityAssessment.SCARCE
    if states[0] is ScarcityComponentState.ABUNDANT and states[1] in {ScarcityComponentState.ABUNDANT, ScarcityComponentState.COMMON} and states[2] in {ScarcityComponentState.ABUNDANT, ScarcityComponentState.COMMON}:
        return ScarcityAssessment.ABUNDANT
    if scarce == 0 and sum(value in {ScarcityComponentState.COMMON, ScarcityComponentState.ABUNDANT} for value in usable) >= 2:
        return ScarcityAssessment.COMMON
    return ScarcityAssessment.LIMITED


def _reasons(availability, appearance, persistence, assessment, partial):
    values = [{
        ScarcityComponentState.VERY_SCARCE: ScarcityReasonCode.NO_CURRENT_LISTINGS,
        ScarcityComponentState.SCARCE: ScarcityReasonCode.ONE_CURRENT_LISTING,
        ScarcityComponentState.LIMITED: ScarcityReasonCode.FEW_CURRENT_LISTINGS,
        ScarcityComponentState.COMMON: ScarcityReasonCode.SEVERAL_CURRENT_LISTINGS,
        ScarcityComponentState.ABUNDANT: ScarcityReasonCode.MANY_CURRENT_LISTINGS,
    }.get(availability.state, ScarcityReasonCode.SPARSE_RELEASE_EVIDENCE)]
    values.append(
        ScarcityReasonCode.CONTINUOUS_MARKETPLACE_APPEARANCE
        if appearance.state is ScarcityComponentState.ABUNDANT
        else ScarcityReasonCode.LOW_APPEARANCE_RATIO
        if appearance.state in {ScarcityComponentState.SCARCE, ScarcityComponentState.VERY_SCARCE}
        else ScarcityReasonCode.INTERMITTENT_MARKETPLACE_APPEARANCE
    )
    values.append(
        ScarcityReasonCode.PERSISTENT_LISTING_AVAILABILITY
        if persistence.state in {ScarcityComponentState.ABUNDANT, ScarcityComponentState.COMMON}
        else ScarcityReasonCode.ALL_LISTINGS_ENDED
        if persistence.state is ScarcityComponentState.VERY_SCARCE
        else ScarcityReasonCode.HIGH_LISTING_DISRUPTION
        if persistence.state is ScarcityComponentState.SCARCE
        else ScarcityReasonCode.SPARSE_RELEASE_EVIDENCE
    )
    if appearance.longest_internal_absence and appearance.longest_internal_absence > 1:
        values.append(ScarcityReasonCode.EXTENDED_INTERNAL_ABSENCE)
    if partial:
        values.append(ScarcityReasonCode.PARTIAL_REQUIRED_SOURCE)
    values.append({
        ScarcityAssessment.VERY_SCARCE: ScarcityReasonCode.OBSERVED_AVAILABILITY_VERY_SCARCE,
        ScarcityAssessment.SCARCE: ScarcityReasonCode.MULTIPLE_SCARCE_COMPONENTS,
        ScarcityAssessment.ABUNDANT: ScarcityReasonCode.BROAD_OBSERVED_AVAILABILITY,
        ScarcityAssessment.COMMON: ScarcityReasonCode.COMMON_OBSERVED_AVAILABILITY,
        ScarcityAssessment.LIMITED: ScarcityReasonCode.MIXED_SCARCITY_EVIDENCE,
        ScarcityAssessment.INSUFFICIENT: ScarcityReasonCode.INSUFFICIENT_CORE_COMPONENTS,
    }[assessment])
    return tuple(dict.fromkeys(values))


_ASSESSMENT_ORDER = {value: index for index, value in enumerate((ScarcityAssessment.VERY_SCARCE, ScarcityAssessment.SCARCE, ScarcityAssessment.LIMITED, ScarcityAssessment.COMMON, ScarcityAssessment.ABUNDANT, ScarcityAssessment.INSUFFICIENT))}
_COVERAGE_ORDER = {value: index for index, value in enumerate(ScarcityEvidenceCoverage)}


def _release_order(value):
    availability = value.components.observed_availability
    appearance = value.components.appearance
    persistence = value.components.listing_persistence
    return (
        _ASSESSMENT_ORDER[value.assessment],
        _COVERAGE_ORDER[value.components.evidence_coverage],
        availability.currently_present_count,
        appearance.appearance_ratio if appearance.appearance_ratio is not None else Decimal(2),
        -persistence.disrupted_ratio,
        value.release_id,
    )


def _summary(values):
    assessments = Counter(value.assessment for value in values)
    coverage = Counter(value.components.evidence_coverage for value in values)
    return MarketplaceScarcitySummary(
        len(values), assessments[ScarcityAssessment.ABUNDANT], assessments[ScarcityAssessment.COMMON],
        assessments[ScarcityAssessment.LIMITED], assessments[ScarcityAssessment.SCARCE],
        assessments[ScarcityAssessment.VERY_SCARCE], assessments[ScarcityAssessment.INSUFFICIENT],
        coverage[ScarcityEvidenceCoverage.COMPLETE], coverage[ScarcityEvidenceCoverage.PARTIAL],
        coverage[ScarcityEvidenceCoverage.LIMITED], coverage[ScarcityEvidenceCoverage.INSUFFICIENT],
        sum(value.components.observed_availability.currently_present_count == 0 for value in values),
        sum(value.components.observed_availability.currently_present_count == 1 for value in values),
        sum(value.components.appearance.state is ScarcityComponentState.ABUNDANT for value in values),
        sum(value.components.appearance.state in {ScarcityComponentState.COMMON, ScarcityComponentState.LIMITED, ScarcityComponentState.SCARCE} for value in values),
        sum(value.components.listing_persistence.disrupted_ratio >= value.components.listing_persistence.thresholds.disrupted_ratio for value in values),
    )
