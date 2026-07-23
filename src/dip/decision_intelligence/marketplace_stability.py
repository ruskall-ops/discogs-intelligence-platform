"""Deterministic release-level interpretation of observed Marketplace consistency."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus


MODULE_ID = "marketplace_stability"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"
_SOURCE_ORDER = (
    "marketplace_activity",
    "listing_lifecycle",
    "price_changes",
    "supply_changes",
    "rare_appearances",
    "marketplace_momentum",
)
_REQUIRED_SOURCE_IDS = _SOURCE_ORDER[:2]


class MarketplaceStabilityDomainError(ValueError):
    """Raised when Stability values contradict the rule contract."""


def _positive(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise MarketplaceStabilityDomainError(f"{name} must be positive.")


def _non_negative(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise MarketplaceStabilityDomainError(f"{name} cannot be negative.")


def _ratio(value, name, allow_zero=False):
    if type(value) is not Decimal:
        raise TypeError(f"{name} must be a Decimal.")
    lower = Decimal(0)
    if not value.is_finite() or value > Decimal(1) or (value < lower if allow_zero else value <= lower):
        raise MarketplaceStabilityDomainError(f"{name} must be a valid proportion.")


class StabilityAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class StabilityComponentState(str, Enum):
    STABLE = "stable"
    MIXED = "mixed"
    VOLATILE = "volatile"
    INSUFFICIENT = "insufficient"


class StabilityAssessment(str, Enum):
    STABLE = "stable"
    MIXED = "mixed"
    VOLATILE = "volatile"
    INSUFFICIENT = "insufficient"


class StabilityEvidenceCoverage(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class StabilityReasonCode(str, Enum):
    NO_RECORDED_PRICE_CHANGES = "no_recorded_price_changes"
    SOME_RECORDED_PRICE_CHANGES = "some_recorded_price_changes"
    REPEATED_PRICE_CHANGES = "repeated_price_changes"
    NO_RECORDED_SUPPLY_CHANGES = "no_recorded_supply_changes"
    SOME_RECORDED_SUPPLY_CHANGES = "some_recorded_supply_changes"
    REPEATED_SUPPLY_CHANGES = "repeated_supply_changes"
    CONTINUOUS_RELEASE_APPEARANCE = "continuous_release_appearance"
    INTERNAL_RELEASE_ABSENCE = "internal_release_absence"
    EXTENDED_RELEASE_ABSENCE = "extended_release_absence"
    ALL_LISTINGS_PERSISTENT = "all_listings_persistent"
    MIXED_LISTING_LIFECYCLES = "mixed_listing_lifecycles"
    REPEATED_LISTING_TRANSITIONS = "repeated_listing_transitions"
    PARTIAL_REQUIRED_SOURCE = "partial_required_source"
    SPARSE_RELEASE_EVIDENCE = "sparse_release_evidence"
    INSUFFICIENT_CORE_COMPONENTS = "insufficient_core_components"
    MULTIPLE_VOLATILE_COMPONENTS = "multiple_volatile_components"
    PREDOMINANTLY_STABLE_COMPONENTS = "predominantly_stable_components"
    MIXED_COMPONENT_EVIDENCE = "mixed_component_evidence"


class MarketplaceStabilityDiagnosticCode(str, Enum):
    MISSING_REQUIRED_SOURCE = "missing_required_source"
    DUPLICATE_SOURCE_RESULT = "duplicate_source_result"
    UNEXPECTED_SOURCE_RESULT = "unexpected_source_result"
    UNSUPPORTED_SOURCE_VERSION = "unsupported_source_version"
    MALFORMED_TYPED_OUTPUT = "malformed_typed_output"
    SOURCE_NOT_COMPLETED = "source_not_completed"
    INCOMPATIBLE_HISTORY = "incompatible_history"
    CONFLICTING_PROVENANCE = "conflicting_provenance"
    PARTIAL_SOURCE_DIAGNOSTICS = "partial_source_diagnostics"
    OPTIONAL_SOURCE_EXCLUDED = "optional_source_excluded"
    SPARSE_RELEASE_EVIDENCE = "sparse_release_evidence"
    COMPONENT_UNAVAILABLE = "component_unavailable"


class StabilityListingState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    DISAPPEARED = "disappeared"
    REAPPEARED = "reappeared"
    INTERMITTENT = "intermittent"
    ENDED = "ended"


@dataclass(frozen=True)
class ChangeStabilityThresholds:
    mixed_maximum: int = 2

    def __post_init__(self) -> None:
        _positive(self.mixed_maximum, "mixed_maximum")


@dataclass(frozen=True)
class AppearanceContinuityThresholds:
    mixed_absence_maximum: int = 1

    def __post_init__(self) -> None:
        _non_negative(self.mixed_absence_maximum, "mixed_absence_maximum")


@dataclass(frozen=True)
class ListingPersistenceThresholds:
    volatile_disrupted_ratio: Decimal = Decimal("0.5")
    repeated_transition_count: int = 2

    def __post_init__(self) -> None:
        _ratio(self.volatile_disrupted_ratio, "volatile_disrupted_ratio")
        _positive(self.repeated_transition_count, "repeated_transition_count")


@dataclass(frozen=True)
class MarketplaceStabilityDiagnostic:
    code: MarketplaceStabilityDiagnosticCode
    message: str
    source_module_id: str | None = None
    release_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not MarketplaceStabilityDiagnosticCode:
            raise TypeError("code must be a MarketplaceStabilityDiagnosticCode.")
        _text(self.message, "message")
        if self.source_module_id is not None:
            _text(self.source_module_id, "source_module_id")
        if self.release_id is not None:
            _positive(self.release_id, "release_id")


@dataclass(frozen=True)
class StabilitySourceProvenance:
    module_id: str
    module_version: str | None
    result_status: IntelligenceStatus
    compatible: bool
    partial: bool
    history_snapshot_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.module_id not in _SOURCE_ORDER:
            raise MarketplaceStabilityDomainError("Unsupported Stability source.")
        if self.module_version is not None:
            _text(self.module_version, "module_version")
        if type(self.result_status) is not IntelligenceStatus:
            raise TypeError("result_status must be an IntelligenceStatus.")
        if type(self.compatible) is not bool or type(self.partial) is not bool:
            raise TypeError("compatible and partial must be booleans.")
        ids = _strings(self.history_snapshot_ids, "history_snapshot_ids")
        diagnostics = _strings(self.diagnostics, "diagnostics")
        if len(set(ids)) != len(ids):
            raise MarketplaceStabilityDomainError("History snapshot IDs must be unique.")
        object.__setattr__(self, "history_snapshot_ids", ids)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class StabilityActivityFact:
    release_id: int
    historical_price_change_count: int
    historical_supply_change_count: int
    appearance_count: int
    appearance_ratio: Decimal
    longest_absence: int
    total_activity_count: int

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        for name in (
            "historical_price_change_count",
            "historical_supply_change_count",
            "appearance_count",
            "longest_absence",
            "total_activity_count",
        ):
            _non_negative(getattr(self, name), name)
        _ratio(self.appearance_ratio, "appearance_ratio", allow_zero=True)
        if self.total_activity_count != (
            self.historical_price_change_count
            + self.historical_supply_change_count
            + self.appearance_count
        ):
            raise MarketplaceStabilityDomainError("Activity total is inconsistent.")


@dataclass(frozen=True)
class StabilityLifecycleFact:
    release_id: int
    listing_id: str
    state: StabilityListingState
    currently_present: bool
    disappearance_count: int
    reappearance_count: int

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _text(self.listing_id, "listing_id")
        if type(self.state) is not StabilityListingState:
            raise TypeError("state must be a StabilityListingState.")
        if type(self.currently_present) is not bool:
            raise TypeError("currently_present must be a boolean.")
        _non_negative(self.disappearance_count, "disappearance_count")
        _non_negative(self.reappearance_count, "reappearance_count")


@dataclass(frozen=True)
class StabilityMomentumContext:
    release_id: int
    assessment: str

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _text(self.assessment, "assessment")


@dataclass(frozen=True)
class MarketplaceStabilityInput:
    source_provenance: tuple[StabilitySourceProvenance, ...] = ()
    activity_facts: tuple[StabilityActivityFact, ...] = ()
    lifecycle_facts: tuple[StabilityLifecycleFact, ...] = ()
    momentum_context: tuple[StabilityMomentumContext, ...] = ()
    diagnostics: tuple[MarketplaceStabilityDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        provenance = tuple(self.source_provenance)
        activities = tuple(self.activity_facts)
        lifecycles = tuple(self.lifecycle_facts)
        momentum = tuple(self.momentum_context)
        diagnostics = tuple(self.diagnostics)
        _typed_unique(provenance, StabilitySourceProvenance, lambda value: value.module_id, "source provenance")
        _typed_unique(activities, StabilityActivityFact, lambda value: value.release_id, "activity releases")
        _typed_unique(lifecycles, StabilityLifecycleFact, lambda value: (value.release_id, value.listing_id), "lifecycle identities")
        _typed_unique(momentum, StabilityMomentumContext, lambda value: value.release_id, "Momentum releases")
        if any(type(value) is not MarketplaceStabilityDiagnostic for value in diagnostics):
            raise TypeError("diagnostics must contain MarketplaceStabilityDiagnostic values.")
        if tuple(value.module_id for value in provenance) != tuple(
            source for source in _SOURCE_ORDER if any(item.module_id == source for item in provenance)
        ):
            raise MarketplaceStabilityDomainError("Source provenance must use canonical order.")
        object.__setattr__(self, "source_provenance", provenance)
        object.__setattr__(self, "activity_facts", activities)
        object.__setattr__(self, "lifecycle_facts", lifecycles)
        object.__setattr__(self, "momentum_context", momentum)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def required_sources_compatible(self) -> bool:
        by_id = {value.module_id: value for value in self.source_provenance}
        return all(source in by_id and by_id[source].compatible for source in _REQUIRED_SOURCE_IDS)


@dataclass(frozen=True)
class ChangeStabilityComponent:
    state: StabilityComponentState
    historical_change_count: int | None
    thresholds: ChangeStabilityThresholds

    def __post_init__(self) -> None:
        if type(self.state) is not StabilityComponentState:
            raise TypeError("state must be a StabilityComponentState.")
        if self.historical_change_count is not None:
            _non_negative(self.historical_change_count, "historical_change_count")
        if type(self.thresholds) is not ChangeStabilityThresholds:
            raise TypeError("thresholds must be ChangeStabilityThresholds.")
        if self.state is StabilityComponentState.INSUFFICIENT and self.historical_change_count is not None:
            raise MarketplaceStabilityDomainError("Insufficient change stability cannot contain a count.")


@dataclass(frozen=True)
class AppearanceContinuityComponent:
    state: StabilityComponentState
    appearance_count: int | None
    appearance_ratio: Decimal | None
    longest_internal_absence: int | None
    thresholds: AppearanceContinuityThresholds

    def __post_init__(self) -> None:
        if type(self.state) is not StabilityComponentState:
            raise TypeError("state must be a StabilityComponentState.")
        facts = (self.appearance_count, self.appearance_ratio, self.longest_internal_absence)
        if self.state is StabilityComponentState.INSUFFICIENT:
            if any(value is not None for value in facts):
                raise MarketplaceStabilityDomainError("Insufficient appearance continuity cannot contain facts.")
        elif any(value is None for value in facts):
            raise MarketplaceStabilityDomainError("Usable appearance continuity requires all facts.")


@dataclass(frozen=True)
class ListingPersistenceFacts:
    total_listing_count: int
    currently_present_count: int
    continuously_active_count: int
    disappeared_count: int
    ended_count: int
    reappeared_count: int
    intermittent_count: int
    new_count: int
    total_disappearance_count: int
    total_reappearance_count: int
    currently_present_ratio: Decimal
    continuously_active_ratio: Decimal
    disrupted_ratio: Decimal

    def __post_init__(self) -> None:
        for name in (
            "total_listing_count", "currently_present_count",
            "continuously_active_count", "disappeared_count", "ended_count",
            "reappeared_count", "intermittent_count", "new_count",
            "total_disappearance_count", "total_reappearance_count",
        ):
            _non_negative(getattr(self, name), name)
        if self.total_listing_count == 0:
            raise MarketplaceStabilityDomainError("Listing persistence facts require listings.")
        for name in ("currently_present_ratio", "continuously_active_ratio", "disrupted_ratio"):
            _ratio(getattr(self, name), name, allow_zero=True)


@dataclass(frozen=True)
class ListingPersistenceComponent:
    state: StabilityComponentState
    facts: ListingPersistenceFacts | None
    thresholds: ListingPersistenceThresholds

    def __post_init__(self) -> None:
        if type(self.state) is not StabilityComponentState:
            raise TypeError("state must be a StabilityComponentState.")
        if self.state is StabilityComponentState.INSUFFICIENT:
            if self.facts is not None:
                raise MarketplaceStabilityDomainError("Insufficient listing persistence cannot contain facts.")
        elif type(self.facts) is not ListingPersistenceFacts:
            raise TypeError("Usable listing persistence requires ListingPersistenceFacts.")


@dataclass(frozen=True)
class StabilityComponents:
    price: ChangeStabilityComponent
    supply: ChangeStabilityComponent
    appearance: AppearanceContinuityComponent
    listing: ListingPersistenceComponent
    evidence_coverage: StabilityEvidenceCoverage

    def __post_init__(self) -> None:
        for name, value, expected in (
            ("price", self.price, ChangeStabilityComponent),
            ("supply", self.supply, ChangeStabilityComponent),
            ("appearance", self.appearance, AppearanceContinuityComponent),
            ("listing", self.listing, ListingPersistenceComponent),
        ):
            if type(value) is not expected:
                raise TypeError(f"{name} has an invalid component type.")
        if type(self.evidence_coverage) is not StabilityEvidenceCoverage:
            raise TypeError("evidence_coverage must be a StabilityEvidenceCoverage.")


@dataclass(frozen=True)
class ReleaseStability:
    release_id: int
    assessment: StabilityAssessment
    components: StabilityComponents
    stable_component_count: int
    mixed_component_count: int
    volatile_component_count: int
    usable_component_count: int
    total_activity_count: int | None
    momentum_assessment: str | None
    reason_codes: tuple[StabilityReasonCode, ...]

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        if type(self.assessment) is not StabilityAssessment:
            raise TypeError("assessment must be a StabilityAssessment.")
        if type(self.components) is not StabilityComponents:
            raise TypeError("components must be StabilityComponents.")
        if self.total_activity_count is not None:
            _non_negative(self.total_activity_count, "total_activity_count")
        if self.momentum_assessment is not None:
            _text(self.momentum_assessment, "momentum_assessment")
        reasons = tuple(self.reason_codes)
        if not reasons or any(type(value) is not StabilityReasonCode for value in reasons):
            raise TypeError("reason_codes must contain StabilityReasonCode values.")
        if len(set(reasons)) != len(reasons):
            raise MarketplaceStabilityDomainError("reason_codes must be unique.")
        object.__setattr__(self, "reason_codes", reasons)
        states = (
            self.components.price.state,
            self.components.supply.state,
            self.components.appearance.state,
            self.components.listing.state,
        )
        counts = Counter(states)
        expected = (
            counts[StabilityComponentState.STABLE],
            counts[StabilityComponentState.MIXED],
            counts[StabilityComponentState.VOLATILE],
            4 - counts[StabilityComponentState.INSUFFICIENT],
        )
        actual = (
            self.stable_component_count,
            self.mixed_component_count,
            self.volatile_component_count,
            self.usable_component_count,
        )
        if actual != expected:
            raise MarketplaceStabilityDomainError("Component counts are inconsistent.")
        if self.assessment is not _assessment(states, self.components.evidence_coverage):
            raise MarketplaceStabilityDomainError("Assessment is inconsistent.")


@dataclass(frozen=True)
class MarketplaceStabilitySummary:
    release_count: int = 0
    stable_count: int = 0
    mixed_count: int = 0
    volatile_count: int = 0
    insufficient_count: int = 0
    complete_evidence_count: int = 0
    partial_evidence_count: int = 0
    limited_evidence_count: int = 0
    insufficient_evidence_count: int = 0
    stable_price_count: int = 0
    stable_supply_count: int = 0
    stable_appearance_count: int = 0
    stable_listing_count: int = 0


@dataclass(frozen=True)
class MarketplaceStabilityOutput:
    analysis_state: StabilityAnalysisState
    rule_set_version: str
    price_thresholds: ChangeStabilityThresholds
    supply_thresholds: ChangeStabilityThresholds
    appearance_thresholds: AppearanceContinuityThresholds
    listing_thresholds: ListingPersistenceThresholds
    source_provenance: tuple[StabilitySourceProvenance, ...]
    releases: tuple[ReleaseStability, ...]
    summary: MarketplaceStabilitySummary
    diagnostics: tuple[MarketplaceStabilityDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if type(self.analysis_state) is not StabilityAnalysisState:
            raise TypeError("analysis_state must be a StabilityAnalysisState.")
        if self.rule_set_version != RULE_SET_VERSION:
            raise MarketplaceStabilityDomainError("Unsupported rule-set version.")
        for value, expected in (
            (self.price_thresholds, ChangeStabilityThresholds),
            (self.supply_thresholds, ChangeStabilityThresholds),
            (self.appearance_thresholds, AppearanceContinuityThresholds),
            (self.listing_thresholds, ListingPersistenceThresholds),
        ):
            if type(value) is not expected:
                raise TypeError("Stability output contains invalid thresholds.")
        releases = tuple(self.releases)
        if any(type(value) is not ReleaseStability for value in releases):
            raise TypeError("releases must contain ReleaseStability values.")
        if any(type(value) is not StabilitySourceProvenance for value in self.source_provenance):
            raise TypeError("source_provenance contains invalid values.")
        if any(type(value) is not MarketplaceStabilityDiagnostic for value in self.diagnostics):
            raise TypeError("diagnostics contains invalid values.")
        if releases != tuple(sorted(releases, key=_release_order)):
            raise MarketplaceStabilityDomainError("Releases must use canonical Stability order.")
        if self.summary != _summary(releases):
            raise MarketplaceStabilityDomainError("Summary is inconsistent with releases.")
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "source_provenance", tuple(self.source_provenance))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


class MarketplaceStabilityModule:
    module_id = MODULE_ID
    module_version = MODULE_VERSION

    def __init__(
        self,
        *,
        price_thresholds: ChangeStabilityThresholds = ChangeStabilityThresholds(),
        supply_thresholds: ChangeStabilityThresholds = ChangeStabilityThresholds(),
        appearance_thresholds: AppearanceContinuityThresholds = AppearanceContinuityThresholds(),
        listing_thresholds: ListingPersistenceThresholds = ListingPersistenceThresholds(),
    ) -> None:
        self._price = price_thresholds
        self._supply = supply_thresholds
        self._appearance = appearance_thresholds
        self._listing = listing_thresholds

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        supplied = context.marketplace_stability_input
        if supplied is None:
            supplied = MarketplaceStabilityInput(
                diagnostics=(MarketplaceStabilityDiagnostic(
                    MarketplaceStabilityDiagnosticCode.MISSING_REQUIRED_SOURCE,
                    "Marketplace Stability input was not supplied.",
                ),)
            )
        if type(supplied) is not MarketplaceStabilityInput:
            raise TypeError("marketplace_stability_input must be a MarketplaceStabilityInput.")
        if not supplied.required_sources_compatible:
            return self._result(supplied, (), StabilityAnalysisState.INSUFFICIENT_DATA)
        activities = {value.release_id: value for value in supplied.activity_facts}
        lifecycle_groups: dict[int, list[StabilityLifecycleFact]] = {}
        for value in supplied.lifecycle_facts:
            lifecycle_groups.setdefault(value.release_id, []).append(value)
        momentum = {value.release_id: value.assessment for value in supplied.momentum_context}
        release_ids = sorted(set(activities) | set(lifecycle_groups))
        releases = tuple(
            _release(
                release_id,
                activities.get(release_id),
                tuple(lifecycle_groups.get(release_id, ())),
                momentum.get(release_id),
                supplied,
                self._price,
                self._supply,
                self._appearance,
                self._listing,
            )
            for release_id in release_ids
        )
        releases = tuple(sorted(releases, key=_release_order))
        partial = any(value.partial or value.diagnostics for value in supplied.source_provenance if value.module_id in _REQUIRED_SOURCE_IDS)
        state = StabilityAnalysisState.PARTIAL if partial or any(value.components.evidence_coverage is not StabilityEvidenceCoverage.COMPLETE for value in releases) else StabilityAnalysisState.COMPLETE
        return self._result(supplied, releases, state)

    def _result(self, supplied: MarketplaceStabilityInput, releases: tuple[ReleaseStability, ...], state: StabilityAnalysisState) -> IntelligenceResult:
        output = MarketplaceStabilityOutput(
            state, RULE_SET_VERSION, self._price, self._supply, self._appearance,
            self._listing, supplied.source_provenance, releases, _summary(releases),
            supplied.diagnostics,
        )
        status = IntelligenceStatus.SKIPPED if state is StabilityAnalysisState.INSUFFICIENT_DATA else IntelligenceStatus.COMPLETED
        diagnostics = tuple(
            f"{value.code.value}: {value.message}" for value in supplied.diagnostics
        )
        return IntelligenceResult(
            MODULE_ID, status,
            "Marketplace Stability requires compatible Activity and Listing Lifecycle intelligence." if status is IntelligenceStatus.SKIPPED else f"Assessed observed Marketplace stability for {len(releases)} release{'s' if len(releases) != 1 else ''}.",
            metrics={"output": output}, diagnostics=diagnostics,
            evidence=tuple(f"Release {value.release_id} has {value.assessment.value} observed stability." for value in releases),
            module_version=MODULE_VERSION,
        )


def _release(release_id, activity, lifecycles, momentum, supplied, price_thresholds, supply_thresholds, appearance_thresholds, listing_thresholds):
    price = _change(activity.historical_price_change_count if activity else None, price_thresholds)
    supply = _change(activity.historical_supply_change_count if activity else None, supply_thresholds)
    appearance = _appearance(activity, appearance_thresholds)
    listing = _listing(lifecycles, listing_thresholds)
    required = {value.module_id: value for value in supplied.source_provenance}
    partial = any(required[source].partial or required[source].diagnostics for source in _REQUIRED_SOURCE_IDS)
    usable = sum(value is not StabilityComponentState.INSUFFICIENT for value in (price.state, supply.state, appearance.state, listing.state))
    if usable == 0:
        coverage = StabilityEvidenceCoverage.INSUFFICIENT
    elif activity is None or not lifecycles or usable <= 2:
        coverage = StabilityEvidenceCoverage.LIMITED
    elif partial or usable == 3:
        coverage = StabilityEvidenceCoverage.PARTIAL
    else:
        coverage = StabilityEvidenceCoverage.COMPLETE
    components = StabilityComponents(price, supply, appearance, listing, coverage)
    states = (price.state, supply.state, appearance.state, listing.state)
    assessment = _assessment(states, coverage)
    reasons = _reasons(price, supply, appearance, listing, assessment, partial)
    counts = Counter(states)
    return ReleaseStability(
        release_id, assessment, components,
        counts[StabilityComponentState.STABLE],
        counts[StabilityComponentState.MIXED],
        counts[StabilityComponentState.VOLATILE],
        usable, activity.total_activity_count if activity else None,
        momentum, reasons,
    )


def _change(count, thresholds):
    if count is None:
        state = StabilityComponentState.INSUFFICIENT
    elif count == 0:
        state = StabilityComponentState.STABLE
    elif count <= thresholds.mixed_maximum:
        state = StabilityComponentState.MIXED
    else:
        state = StabilityComponentState.VOLATILE
    return ChangeStabilityComponent(state, count, thresholds)


def _appearance(activity, thresholds):
    if activity is None or activity.appearance_count == 0:
        return AppearanceContinuityComponent(StabilityComponentState.INSUFFICIENT, None, None, None, thresholds)
    if activity.appearance_ratio == Decimal(1) and activity.longest_absence == 0:
        state = StabilityComponentState.STABLE
    elif activity.longest_absence <= thresholds.mixed_absence_maximum:
        state = StabilityComponentState.MIXED
    else:
        state = StabilityComponentState.VOLATILE
    return AppearanceContinuityComponent(state, activity.appearance_count, activity.appearance_ratio, activity.longest_absence, thresholds)


def _listing(values, thresholds):
    if not values:
        return ListingPersistenceComponent(StabilityComponentState.INSUFFICIENT, None, thresholds)
    counts = Counter(value.state for value in values)
    total = len(values)
    current = sum(value.currently_present for value in values)
    disappearances = sum(value.disappearance_count for value in values)
    reappearances = sum(value.reappearance_count for value in values)
    disrupted_count = sum(value.state in {StabilityListingState.DISAPPEARED, StabilityListingState.ENDED, StabilityListingState.REAPPEARED, StabilityListingState.INTERMITTENT} for value in values)
    facts = ListingPersistenceFacts(
        total, current, counts[StabilityListingState.ACTIVE],
        counts[StabilityListingState.DISAPPEARED], counts[StabilityListingState.ENDED],
        counts[StabilityListingState.REAPPEARED], counts[StabilityListingState.INTERMITTENT],
        counts[StabilityListingState.NEW], disappearances, reappearances,
        Decimal(current) / Decimal(total),
        Decimal(counts[StabilityListingState.ACTIVE]) / Decimal(total),
        Decimal(disrupted_count) / Decimal(total),
    )
    repeated = disappearances + reappearances >= thresholds.repeated_transition_count
    if facts.disrupted_ratio >= thresholds.volatile_disrupted_ratio or repeated:
        state = StabilityComponentState.VOLATILE
    elif disrupted_count:
        state = StabilityComponentState.MIXED
    else:
        state = StabilityComponentState.STABLE
    return ListingPersistenceComponent(state, facts, thresholds)


def _assessment(states, coverage):
    usable = [value for value in states if value is not StabilityComponentState.INSUFFICIENT]
    volatile = usable.count(StabilityComponentState.VOLATILE)
    stable = usable.count(StabilityComponentState.STABLE)
    listing = states[3]
    if coverage is StabilityEvidenceCoverage.INSUFFICIENT or len(usable) < 2:
        return StabilityAssessment.INSUFFICIENT
    if volatile >= 2 or (listing is StabilityComponentState.VOLATILE and volatile >= 2):
        return StabilityAssessment.VOLATILE
    if volatile == 0 and stable >= 3:
        return StabilityAssessment.STABLE
    return StabilityAssessment.MIXED


def _reasons(price, supply, appearance, listing, assessment, partial):
    values = []
    values.append({
        StabilityComponentState.STABLE: StabilityReasonCode.NO_RECORDED_PRICE_CHANGES,
        StabilityComponentState.MIXED: StabilityReasonCode.SOME_RECORDED_PRICE_CHANGES,
        StabilityComponentState.VOLATILE: StabilityReasonCode.REPEATED_PRICE_CHANGES,
    }.get(price.state, StabilityReasonCode.SPARSE_RELEASE_EVIDENCE))
    values.append({
        StabilityComponentState.STABLE: StabilityReasonCode.NO_RECORDED_SUPPLY_CHANGES,
        StabilityComponentState.MIXED: StabilityReasonCode.SOME_RECORDED_SUPPLY_CHANGES,
        StabilityComponentState.VOLATILE: StabilityReasonCode.REPEATED_SUPPLY_CHANGES,
    }.get(supply.state, StabilityReasonCode.SPARSE_RELEASE_EVIDENCE))
    values.append({
        StabilityComponentState.STABLE: StabilityReasonCode.CONTINUOUS_RELEASE_APPEARANCE,
        StabilityComponentState.MIXED: StabilityReasonCode.INTERNAL_RELEASE_ABSENCE,
        StabilityComponentState.VOLATILE: StabilityReasonCode.EXTENDED_RELEASE_ABSENCE,
    }.get(appearance.state, StabilityReasonCode.SPARSE_RELEASE_EVIDENCE))
    values.append({
        StabilityComponentState.STABLE: StabilityReasonCode.ALL_LISTINGS_PERSISTENT,
        StabilityComponentState.MIXED: StabilityReasonCode.MIXED_LISTING_LIFECYCLES,
        StabilityComponentState.VOLATILE: StabilityReasonCode.REPEATED_LISTING_TRANSITIONS,
    }.get(listing.state, StabilityReasonCode.SPARSE_RELEASE_EVIDENCE))
    if partial:
        values.append(StabilityReasonCode.PARTIAL_REQUIRED_SOURCE)
    values.append({
        StabilityAssessment.STABLE: StabilityReasonCode.PREDOMINANTLY_STABLE_COMPONENTS,
        StabilityAssessment.MIXED: StabilityReasonCode.MIXED_COMPONENT_EVIDENCE,
        StabilityAssessment.VOLATILE: StabilityReasonCode.MULTIPLE_VOLATILE_COMPONENTS,
        StabilityAssessment.INSUFFICIENT: StabilityReasonCode.INSUFFICIENT_CORE_COMPONENTS,
    }[assessment])
    return tuple(dict.fromkeys(values))


_ASSESSMENT_ORDER = {value: index for index, value in enumerate(StabilityAssessment)}
_COVERAGE_ORDER = {value: index for index, value in enumerate(StabilityEvidenceCoverage)}


def _release_order(value):
    return (
        _ASSESSMENT_ORDER[value.assessment],
        _COVERAGE_ORDER[value.components.evidence_coverage],
        -value.volatile_component_count,
        -value.stable_component_count,
        -(value.total_activity_count if value.total_activity_count is not None else -1),
        value.release_id,
    )


def _summary(values):
    assessments = Counter(value.assessment for value in values)
    coverage = Counter(value.components.evidence_coverage for value in values)
    return MarketplaceStabilitySummary(
        len(values), assessments[StabilityAssessment.STABLE],
        assessments[StabilityAssessment.MIXED], assessments[StabilityAssessment.VOLATILE],
        assessments[StabilityAssessment.INSUFFICIENT],
        coverage[StabilityEvidenceCoverage.COMPLETE],
        coverage[StabilityEvidenceCoverage.PARTIAL],
        coverage[StabilityEvidenceCoverage.LIMITED],
        coverage[StabilityEvidenceCoverage.INSUFFICIENT],
        sum(value.components.price.state is StabilityComponentState.STABLE for value in values),
        sum(value.components.supply.state is StabilityComponentState.STABLE for value in values),
        sum(value.components.appearance.state is StabilityComponentState.STABLE for value in values),
        sum(value.components.listing.state is StabilityComponentState.STABLE for value in values),
    )


def _typed_unique(values, value_type, identity, label):
    if any(type(value) is not value_type for value in values):
        raise TypeError(f"{label} contain invalid values.")
    identities = tuple(identity(value) for value in values)
    if len(set(identities)) != len(identities):
        raise MarketplaceStabilityDomainError(f"Duplicate {label}.")


def _text(value, name):
    if type(value) is not str or not value.strip():
        raise TypeError(f"{name} must be non-empty text.")


def _positive(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise MarketplaceStabilityDomainError(f"{name} must be positive.")


def _non_negative(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise MarketplaceStabilityDomainError(f"{name} cannot be negative.")


def _ratio(value, name, allow_zero=False):
    if type(value) is not Decimal:
        raise TypeError(f"{name} must be a Decimal.")
    lower = Decimal(0)
    if not value.is_finite() or value > Decimal(1) or (value < lower if allow_zero else value <= lower):
        raise MarketplaceStabilityDomainError(f"{name} must be a valid proportion.")


def _strings(values, name):
    values = tuple(values)
    if any(type(value) is not str or not value.strip() for value in values):
        raise TypeError(f"{name} must contain non-empty strings.")
    return values
