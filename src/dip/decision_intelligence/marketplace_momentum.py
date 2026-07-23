"""Deterministic release-level interpretation of supplied intelligence facts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus


MODULE_ID = "marketplace_momentum"
MODULE_VERSION = "1.0"
RULE_SET_VERSION = "1.0"
_SOURCE_ORDER = (
    "price_changes",
    "supply_changes",
    "marketplace_activity",
    "rare_appearances",
    "listing_lifecycle",
)
_REQUIRED_SOURCE_IDS = _SOURCE_ORDER[:3]


class MarketplaceMomentumDomainError(ValueError):
    """Raised when Marketplace Momentum values contradict the rule contract."""


class MomentumAnalysisState(str, Enum):
    """Overall outcome of applying the Momentum rule set."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


class MomentumDirection(str, Enum):
    """Direction derived from comparable supplied facts only."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    INSUFFICIENT = "insufficient"


class ActivityIntensity(str, Enum):
    """Activity bands in canonical high-to-unavailable ordering."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"
    INSUFFICIENT = "insufficient"


class EvidenceCoverage(str, Enum):
    """Non-probabilistic evidence coverage in canonical ordering."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    LIMITED = "limited"
    INSUFFICIENT = "insufficient"


class MomentumAssessment(str, Enum):
    """Observed Momentum classifications in canonical presentation order."""

    POSITIVE = "positive"
    MIXED = "mixed"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    INSUFFICIENT = "insufficient"


class MomentumReasonCode(str, Enum):
    """Stable facts that make each assessment and coverage state explainable."""

    ALIGNED_POSITIVE = "aligned_positive"
    PRICE_POSITIVE_SUPPLY_NEUTRAL = "price_positive_supply_neutral"
    ALIGNED_NEGATIVE = "aligned_negative"
    PRICE_NEGATIVE_SUPPLY_NEUTRAL = "price_negative_supply_neutral"
    CONFLICTING_DIRECTIONS = "conflicting_directions"
    DIRECTION_WITH_MISSING_COUNTERPART = "direction_with_missing_counterpart"
    NEUTRAL_WITH_DIRECTIONAL_SIGNAL = "neutral_with_directional_signal"
    BALANCED_COMPARABLE_EVIDENCE = "balanced_comparable_evidence"
    NO_COMPARABLE_DIRECTION = "no_comparable_direction"
    NO_COMPARABLE_PRICE = "no_comparable_price"
    NO_COMPARABLE_SUPPLY = "no_comparable_supply"
    NO_ACTIVITY_PROFILE = "no_activity_profile"
    PARTIAL_REQUIRED_SOURCE = "partial_required_source"
    REQUIRED_SOURCE_DIAGNOSTICS = "required_source_diagnostics"


class MarketplaceMomentumDiagnosticCode(str, Enum):
    """Stable diagnostic categories produced while coordinating source results."""

    MISSING_REQUIRED_SOURCE = "missing_required_source"
    DUPLICATE_SOURCE_RESULT = "duplicate_source_result"
    UNEXPECTED_SOURCE_RESULT = "unexpected_source_result"
    UNSUPPORTED_SOURCE_VERSION = "unsupported_source_version"
    MALFORMED_TYPED_OUTPUT = "malformed_typed_output"
    SOURCE_NOT_COMPLETED = "source_not_completed"
    INCOMPATIBLE_HISTORY = "incompatible_history"
    CONFLICTING_PROVENANCE = "conflicting_provenance"
    PARTIAL_SOURCE_DIAGNOSTICS = "partial_source_diagnostics"
    OPTIONAL_SOURCE_UNAVAILABLE = "optional_source_unavailable"
    SPARSE_RELEASE_SOURCE = "sparse_release_source"
    SOURCE_ACTIVITY_MISMATCH = "source_activity_mismatch"


class MarketplaceMomentumPriceFactKind(str, Enum):
    """Normalised Price Changes classifications consumed by Momentum."""

    INCREASED = "increased"
    DECREASED = "decreased"
    NEWLY_OBSERVED = "newly_observed"
    NO_LONGER_OBSERVED = "no_longer_observed"
    INCOMPARABLE = "incomparable"


class MarketplaceMomentumSupplyFactKind(str, Enum):
    """Normalised Supply Changes classifications consumed by Momentum."""

    INCREASED = "increased"
    DECREASED = "decreased"
    NEWLY_AVAILABLE = "newly_available"
    NO_LONGER_AVAILABLE = "no_longer_available"
    INCOMPARABLE = "incomparable"


class MarketplaceMomentumListingState(str, Enum):
    """Factual Listing Lifecycle states accepted as optional context."""

    NEW = "new"
    ACTIVE = "active"
    DISAPPEARED = "disappeared"
    REAPPEARED = "reappeared"
    INTERMITTENT = "intermittent"
    ENDED = "ended"


@dataclass(frozen=True)
class ActivityIntensityThresholds:
    """Inclusive upper bounds for low and moderate factual activity."""

    low_maximum: int = 2
    moderate_maximum: int = 5

    def __post_init__(self) -> None:
        _positive_integer(self.low_maximum, "low_maximum")
        _positive_integer(self.moderate_maximum, "moderate_maximum")
        if self.low_maximum >= self.moderate_maximum:
            raise MarketplaceMomentumDomainError(
                "low_maximum must be less than moderate_maximum."
            )


@dataclass(frozen=True)
class MarketplaceMomentumDiagnostic:
    """One deterministic domain-facing source or sparse-evidence diagnostic."""

    code: MarketplaceMomentumDiagnosticCode
    message: str
    source_module_id: str | None = None
    release_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not MarketplaceMomentumDiagnosticCode:
            raise TypeError("code must be a MarketplaceMomentumDiagnosticCode.")
        _text(self.message, "message")
        if self.source_module_id is not None:
            _source_id(self.source_module_id, "source_module_id")
        if self.release_id is not None:
            _positive_integer(self.release_id, "release_id")


@dataclass(frozen=True)
class SourceProvenance:
    """Versioned identity and diagnostic context for one supplied result."""

    module_id: str
    module_version: str | None
    result_status: IntelligenceStatus
    compatible: bool
    partial: bool
    history_snapshot_ids: tuple[str, ...] = ()
    source: str | None = None
    source_versions: tuple[str | None, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _source_id(self.module_id, "module_id")
        if self.module_id not in _SOURCE_ORDER:
            raise MarketplaceMomentumDomainError(
                f"Unsupported Momentum source module {self.module_id!r}."
            )
        if self.module_version is not None:
            _text(self.module_version, "module_version")
        if type(self.result_status) is not IntelligenceStatus:
            raise TypeError("result_status must be an IntelligenceStatus.")
        if type(self.compatible) is not bool:
            raise TypeError("compatible must be a boolean.")
        if type(self.partial) is not bool:
            raise TypeError("partial must be a boolean.")
        snapshot_ids = _strings(
            self.history_snapshot_ids,
            "history_snapshot_ids",
            allow_empty=True,
        )
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise MarketplaceMomentumDomainError(
                "Source history snapshot IDs must be unique."
            )
        if self.source is not None:
            _text(self.source, "source")
        versions = _optional_strings(self.source_versions, "source_versions")
        if len(versions) != len(snapshot_ids):
            raise MarketplaceMomentumDomainError(
                "source_versions must align with history_snapshot_ids."
            )
        if self.compatible and self.module_id in {
            "price_changes",
            "supply_changes",
        }:
            if len(snapshot_ids) != 2 or self.source is None:
                raise MarketplaceMomentumDomainError(
                    "Compatible comparison provenance requires two snapshots and a source."
                )
        if (
            self.compatible
            and self.module_id == "marketplace_activity"
            and len(snapshot_ids) < 2
        ):
            raise MarketplaceMomentumDomainError(
                "Compatible Activity provenance must contain the comparison history."
            )
        diagnostics = _strings(
            self.diagnostics,
            "diagnostics",
            allow_empty=True,
        )
        if self.compatible and self.result_status is not IntelligenceStatus.COMPLETED:
            raise MarketplaceMomentumDomainError(
                "A compatible source must have completed status."
            )
        if self.compatible and self.module_version != MODULE_VERSION:
            raise MarketplaceMomentumDomainError(
                "A compatible source must use supported version 1.0."
            )
        object.__setattr__(self, "history_snapshot_ids", snapshot_ids)
        object.__setattr__(self, "source_versions", versions)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class MarketplaceMomentumPriceFact:
    """One identity-bearing Price Changes classification, without price values."""

    release_id: int
    fact_id: str
    kind: MarketplaceMomentumPriceFactKind

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        _text(self.fact_id, "fact_id")
        if type(self.kind) is not MarketplaceMomentumPriceFactKind:
            raise TypeError("kind must be a MarketplaceMomentumPriceFactKind.")


@dataclass(frozen=True)
class MarketplaceMomentumSupplyFact:
    """One identity-bearing Supply Changes classification, without listing data."""

    release_id: int
    kind: MarketplaceMomentumSupplyFactKind

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        if type(self.kind) is not MarketplaceMomentumSupplyFactKind:
            raise TypeError("kind must be a MarketplaceMomentumSupplyFactKind.")


@dataclass(frozen=True)
class MarketplaceMomentumActivityFact:
    """One already-aggregated Marketplace Activity profile."""

    release_id: int
    total_activity_count: int
    historical_price_change_count: int
    historical_supply_change_count: int
    appearance_count: int
    appearance_ratio: Decimal
    longest_absence: int

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        _non_negative_integer(self.total_activity_count, "total_activity_count")
        _non_negative_integer(
            self.historical_price_change_count,
            "historical_price_change_count",
        )
        _non_negative_integer(
            self.historical_supply_change_count,
            "historical_supply_change_count",
        )
        _non_negative_integer(self.appearance_count, "appearance_count")
        _ratio(self.appearance_ratio, "appearance_ratio", allow_zero=True)
        _non_negative_integer(self.longest_absence, "longest_absence")
        expected = (
            self.historical_price_change_count
            + self.historical_supply_change_count
            + self.appearance_count
        )
        if self.total_activity_count != expected:
            raise MarketplaceMomentumDomainError(
                "total_activity_count must equal the supplied activity components."
            )


@dataclass(frozen=True)
class MarketplaceMomentumAppearanceFact:
    """Optional factual appearance persistence copied from Rare Appearances."""

    release_id: int
    appearance_count: int
    appearance_ratio: Decimal
    longest_absence: int

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        _positive_integer(self.appearance_count, "appearance_count")
        _ratio(self.appearance_ratio, "appearance_ratio")
        _non_negative_integer(self.longest_absence, "longest_absence")


@dataclass(frozen=True)
class MarketplaceMomentumLifecycleFact:
    """Optional factual listing state copied without lifecycle reconstruction."""

    release_id: int
    listing_id: str
    state: MarketplaceMomentumListingState
    currently_present: bool

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        _text(self.listing_id, "listing_id")
        if type(self.state) is not MarketplaceMomentumListingState:
            raise TypeError("state must be a MarketplaceMomentumListingState.")
        if type(self.currently_present) is not bool:
            raise TypeError("currently_present must be a boolean.")
        expected_current = self.state in {
            MarketplaceMomentumListingState.NEW,
            MarketplaceMomentumListingState.ACTIVE,
            MarketplaceMomentumListingState.REAPPEARED,
            MarketplaceMomentumListingState.INTERMITTENT,
        }
        if self.currently_present is not expected_current:
            raise MarketplaceMomentumDomainError(
                "Listing current presence contradicts its supplied lifecycle state."
            )


@dataclass(frozen=True)
class MarketplaceMomentumInput:
    """Immutable, source-normalised input constructed by application orchestration."""

    source_provenance: tuple[SourceProvenance, ...] = ()
    price_facts: tuple[MarketplaceMomentumPriceFact, ...] = ()
    supply_facts: tuple[MarketplaceMomentumSupplyFact, ...] = ()
    activity_facts: tuple[MarketplaceMomentumActivityFact, ...] = ()
    appearance_facts: tuple[MarketplaceMomentumAppearanceFact, ...] = ()
    lifecycle_facts: tuple[MarketplaceMomentumLifecycleFact, ...] = ()
    diagnostics: tuple[MarketplaceMomentumDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        provenance = _typed_tuple(
            self.source_provenance,
            SourceProvenance,
            "source_provenance",
        )
        module_ids = tuple(value.module_id for value in provenance)
        if len(set(module_ids)) != len(module_ids):
            raise MarketplaceMomentumDomainError(
                "Momentum source provenance module IDs must be unique."
            )
        if module_ids != tuple(
            source_id for source_id in _SOURCE_ORDER if source_id in module_ids
        ):
            raise MarketplaceMomentumDomainError(
                "Momentum source provenance must use canonical source order."
            )
        price_facts = _typed_tuple(
            self.price_facts,
            MarketplaceMomentumPriceFact,
            "price_facts",
        )
        if price_facts != tuple(
            sorted(price_facts, key=lambda value: (value.release_id, value.fact_id))
        ):
            raise MarketplaceMomentumDomainError(
                "Price facts must use canonical release and fact identity order."
            )
        if len({value.fact_id for value in price_facts}) != len(price_facts):
            raise MarketplaceMomentumDomainError("Price fact IDs must be unique.")
        supply_facts = _typed_tuple(
            self.supply_facts,
            MarketplaceMomentumSupplyFact,
            "supply_facts",
        )
        if supply_facts != tuple(
            sorted(supply_facts, key=lambda value: value.release_id)
        ) or len({value.release_id for value in supply_facts}) != len(supply_facts):
            raise MarketplaceMomentumDomainError(
                "Supply facts must have unique release IDs in canonical order."
            )
        activity_facts = _unique_release_facts(
            self.activity_facts,
            MarketplaceMomentumActivityFact,
            "activity_facts",
        )
        appearance_facts = _unique_release_facts(
            self.appearance_facts,
            MarketplaceMomentumAppearanceFact,
            "appearance_facts",
        )
        lifecycle_facts = _typed_tuple(
            self.lifecycle_facts,
            MarketplaceMomentumLifecycleFact,
            "lifecycle_facts",
        )
        lifecycle_identities = tuple(
            (value.release_id, value.listing_id) for value in lifecycle_facts
        )
        if lifecycle_facts != tuple(
            sorted(
                lifecycle_facts,
                key=lambda value: (value.release_id, value.listing_id),
            )
        ) or len(set(lifecycle_identities)) != len(lifecycle_identities):
            raise MarketplaceMomentumDomainError(
                "Lifecycle facts must have unique identities in canonical order."
            )
        diagnostics = _typed_tuple(
            self.diagnostics,
            MarketplaceMomentumDiagnostic,
            "diagnostics",
        )
        compatible_ids = {
            value.module_id for value in provenance if value.compatible
        }
        _validate_compatible_provenance(provenance)
        if price_facts and "price_changes" not in compatible_ids:
            raise MarketplaceMomentumDomainError(
                "Price facts require compatible Price Changes provenance."
            )
        if supply_facts and "supply_changes" not in compatible_ids:
            raise MarketplaceMomentumDomainError(
                "Supply facts require compatible Supply Changes provenance."
            )
        if activity_facts and "marketplace_activity" not in compatible_ids:
            raise MarketplaceMomentumDomainError(
                "Activity facts require compatible Marketplace Activity provenance."
            )
        if appearance_facts and "rare_appearances" not in compatible_ids:
            raise MarketplaceMomentumDomainError(
                "Appearance facts require compatible Rare Appearances provenance."
            )
        if lifecycle_facts and "listing_lifecycle" not in compatible_ids:
            raise MarketplaceMomentumDomainError(
                "Lifecycle facts require compatible Listing Lifecycle provenance."
            )
        if not self.required_sources_compatible and (
            price_facts or supply_facts or activity_facts
        ):
            raise MarketplaceMomentumDomainError(
                "Incompatible required sources cannot supply assessment facts."
            )
        object.__setattr__(self, "source_provenance", provenance)
        object.__setattr__(self, "price_facts", price_facts)
        object.__setattr__(self, "supply_facts", supply_facts)
        object.__setattr__(self, "activity_facts", activity_facts)
        object.__setattr__(self, "appearance_facts", appearance_facts)
        object.__setattr__(self, "lifecycle_facts", lifecycle_facts)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def required_sources_compatible(self) -> bool:
        """Return whether all required results were supplied and validated."""

        by_module = {value.module_id: value for value in self.source_provenance}
        return all(
            source_id in by_module and by_module[source_id].compatible
            for source_id in _REQUIRED_SOURCE_IDS
        )


@dataclass(frozen=True)
class PriceDirectionComponent:
    """Transparent price fact counts and their direction."""

    increase_count: int
    decrease_count: int
    newly_observed_count: int
    no_longer_observed_count: int
    incomparable_count: int
    comparable_change_count: int
    net_price_direction: int
    direction: MomentumDirection

    def __post_init__(self) -> None:
        for name in (
            "increase_count",
            "decrease_count",
            "newly_observed_count",
            "no_longer_observed_count",
            "incomparable_count",
            "comparable_change_count",
        ):
            _non_negative_integer(getattr(self, name), name)
        _integer(self.net_price_direction, "net_price_direction")
        if type(self.direction) is not MomentumDirection:
            raise TypeError("direction must be a MomentumDirection.")
        comparable = self.increase_count + self.decrease_count
        if self.comparable_change_count != comparable:
            raise MarketplaceMomentumDomainError(
                "comparable_change_count must equal price increases plus decreases."
            )
        if self.net_price_direction != self.increase_count - self.decrease_count:
            raise MarketplaceMomentumDomainError(
                "net_price_direction must equal increases minus decreases."
            )
        if self.direction is not _direction(
            self.comparable_change_count,
            self.net_price_direction,
        ):
            raise MarketplaceMomentumDomainError(
                "Price direction contradicts its comparable fact counts."
            )


@dataclass(frozen=True)
class SupplyDirectionComponent:
    """Transparent supply facts with decreasing supply oriented positively."""

    increase_count: int
    decrease_count: int
    newly_available_count: int
    no_longer_available_count: int
    incomparable_count: int
    comparable_change_count: int
    net_supply_pressure: int
    direction: MomentumDirection

    def __post_init__(self) -> None:
        for name in (
            "increase_count",
            "decrease_count",
            "newly_available_count",
            "no_longer_available_count",
            "incomparable_count",
            "comparable_change_count",
        ):
            _non_negative_integer(getattr(self, name), name)
        _integer(self.net_supply_pressure, "net_supply_pressure")
        if type(self.direction) is not MomentumDirection:
            raise TypeError("direction must be a MomentumDirection.")
        comparable = self.increase_count + self.decrease_count
        if self.comparable_change_count != comparable:
            raise MarketplaceMomentumDomainError(
                "comparable_change_count must equal supply increases plus decreases."
            )
        if self.net_supply_pressure != self.decrease_count - self.increase_count:
            raise MarketplaceMomentumDomainError(
                "net_supply_pressure must equal decreases minus increases."
            )
        if self.direction is not _direction(
            self.comparable_change_count,
            self.net_supply_pressure,
        ):
            raise MarketplaceMomentumDomainError(
                "Supply direction contradicts its comparable fact counts."
            )


@dataclass(frozen=True)
class ActivityIntensityComponent:
    """Copied activity total and its explicit deterministic band."""

    total_activity_count: int | None
    intensity: ActivityIntensity
    thresholds: ActivityIntensityThresholds

    def __post_init__(self) -> None:
        if self.total_activity_count is not None:
            _non_negative_integer(
                self.total_activity_count,
                "total_activity_count",
            )
        if type(self.intensity) is not ActivityIntensity:
            raise TypeError("intensity must be an ActivityIntensity.")
        if type(self.thresholds) is not ActivityIntensityThresholds:
            raise TypeError("thresholds must be ActivityIntensityThresholds.")
        if self.intensity is not _activity_intensity(
            self.total_activity_count,
            self.thresholds,
        ):
            raise MarketplaceMomentumDomainError(
                "Activity intensity contradicts its supplied total and thresholds."
            )


@dataclass(frozen=True)
class EvidenceCoverageComponent:
    """Visible facts used to classify non-probabilistic evidence coverage."""

    coverage: EvidenceCoverage
    price_comparable: bool
    supply_comparable: bool
    activity_available: bool
    required_sources_partial: bool
    required_source_diagnostics: bool

    def __post_init__(self) -> None:
        if type(self.coverage) is not EvidenceCoverage:
            raise TypeError("coverage must be an EvidenceCoverage.")
        for name in (
            "price_comparable",
            "supply_comparable",
            "activity_available",
            "required_sources_partial",
            "required_source_diagnostics",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a boolean.")
        expected = _evidence_coverage(
            self.price_comparable,
            self.supply_comparable,
            self.activity_available,
            self.required_sources_partial,
            self.required_source_diagnostics,
        )
        if self.coverage is not expected:
            raise MarketplaceMomentumDomainError(
                "Evidence coverage contradicts its visible evidence facts."
            )


@dataclass(frozen=True)
class MomentumComponents:
    """Independently visible measures used by the rule set."""

    price: PriceDirectionComponent
    supply: SupplyDirectionComponent
    activity: ActivityIntensityComponent
    evidence: EvidenceCoverageComponent

    def __post_init__(self) -> None:
        if type(self.price) is not PriceDirectionComponent:
            raise TypeError("price must be a PriceDirectionComponent.")
        if type(self.supply) is not SupplyDirectionComponent:
            raise TypeError("supply must be a SupplyDirectionComponent.")
        if type(self.activity) is not ActivityIntensityComponent:
            raise TypeError("activity must be an ActivityIntensityComponent.")
        if type(self.evidence) is not EvidenceCoverageComponent:
            raise TypeError("evidence must be an EvidenceCoverageComponent.")
        expected = (
            self.price.comparable_change_count > 0,
            self.supply.comparable_change_count > 0,
            self.activity.total_activity_count is not None,
        )
        actual = (
            self.evidence.price_comparable,
            self.evidence.supply_comparable,
            self.evidence.activity_available,
        )
        if actual != expected:
            raise MarketplaceMomentumDomainError(
                "Evidence flags must match the visible component values."
            )


@dataclass(frozen=True)
class AppearancePersistenceContext:
    """Optional factual appearance context copied from one compatible source."""

    appearance_count: int
    appearance_ratio: Decimal
    longest_absence: int
    source_module_id: str

    def __post_init__(self) -> None:
        _non_negative_integer(self.appearance_count, "appearance_count")
        _ratio(self.appearance_ratio, "appearance_ratio", allow_zero=True)
        _non_negative_integer(self.longest_absence, "longest_absence")
        if self.source_module_id not in {
            "marketplace_activity",
            "rare_appearances",
        }:
            raise MarketplaceMomentumDomainError(
                "Appearance context requires an approved factual source."
            )
        if (self.appearance_count == 0) != (self.appearance_ratio == 0):
            raise MarketplaceMomentumDomainError(
                "Zero appearance count and ratio must agree."
            )


@dataclass(frozen=True)
class ListingPersistenceContext:
    """Optional release-level counts copied from supplied lifecycle states."""

    listing_count: int
    currently_present_count: int
    new_count: int
    active_count: int
    disappeared_count: int
    reappeared_count: int
    intermittent_count: int
    ended_count: int

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            _non_negative_integer(getattr(self, name), name)
        state_count = (
            self.new_count
            + self.active_count
            + self.disappeared_count
            + self.reappeared_count
            + self.intermittent_count
            + self.ended_count
        )
        if self.listing_count != state_count:
            raise MarketplaceMomentumDomainError(
                "Listing state counts must equal listing_count."
            )
        expected_current = (
            self.new_count
            + self.active_count
            + self.reappeared_count
            + self.intermittent_count
        )
        if self.currently_present_count != expected_current:
            raise MarketplaceMomentumDomainError(
                "currently_present_count must match current lifecycle states."
            )


@dataclass(frozen=True)
class FactualSupportingContext:
    """Optional context that never changes the core assessment."""

    appearance: AppearancePersistenceContext | None = None
    listing_persistence: ListingPersistenceContext | None = None

    def __post_init__(self) -> None:
        if self.appearance is not None and type(
            self.appearance
        ) is not AppearancePersistenceContext:
            raise TypeError(
                "appearance must be an AppearancePersistenceContext or None."
            )
        if self.listing_persistence is not None and type(
            self.listing_persistence
        ) is not ListingPersistenceContext:
            raise TypeError(
                "listing_persistence must be a ListingPersistenceContext or None."
            )


@dataclass(frozen=True)
class ReleaseMomentum:
    """One fully reconstructable release-level Momentum assessment."""

    release_id: int
    assessment: MomentumAssessment
    components: MomentumComponents
    supporting_context: FactualSupportingContext
    contributing_source_ids: tuple[str, ...]
    reason_codes: tuple[MomentumReasonCode, ...]

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        if type(self.assessment) is not MomentumAssessment:
            raise TypeError("assessment must be a MomentumAssessment.")
        if type(self.components) is not MomentumComponents:
            raise TypeError("components must be MomentumComponents.")
        if type(self.supporting_context) is not FactualSupportingContext:
            raise TypeError("supporting_context must be FactualSupportingContext.")
        source_ids = _strings(
            self.contributing_source_ids,
            "contributing_source_ids",
            allow_empty=True,
        )
        if len(set(source_ids)) != len(source_ids):
            raise MarketplaceMomentumDomainError(
                "Contributing source IDs must be unique."
            )
        if source_ids != tuple(
            source_id for source_id in _SOURCE_ORDER if source_id in source_ids
        ):
            raise MarketplaceMomentumDomainError(
                "Contributing source IDs must use canonical source order."
            )
        reasons = _typed_tuple(
            self.reason_codes,
            MomentumReasonCode,
            "reason_codes",
        )
        expected_assessment, assessment_reason = _assessment(
            self.components.price.direction,
            self.components.supply.direction,
        )
        if self.assessment is not expected_assessment:
            raise MarketplaceMomentumDomainError(
                "Momentum assessment contradicts its visible directions."
            )
        expected_reasons = (
            assessment_reason,
            *_coverage_reasons(self.components.evidence),
        )
        if reasons != expected_reasons:
            raise MarketplaceMomentumDomainError(
                "Momentum reason codes contradict the visible components."
            )
        appearance = self.supporting_context.appearance
        if appearance is not None and appearance.source_module_id not in source_ids:
            raise MarketplaceMomentumDomainError(
                "Appearance context source must be a contributing source."
            )
        if (
            self.supporting_context.listing_persistence is not None
            and "listing_lifecycle" not in source_ids
        ):
            raise MarketplaceMomentumDomainError(
                "Listing context requires Listing Lifecycle contribution."
            )
        object.__setattr__(self, "contributing_source_ids", source_ids)
        object.__setattr__(self, "reason_codes", reasons)


@dataclass(frozen=True)
class MarketplaceMomentumSummary:
    """Accountable totals for assessments and evidence coverage."""

    release_count: int = 0
    positive_count: int = 0
    mixed_count: int = 0
    neutral_count: int = 0
    negative_count: int = 0
    insufficient_count: int = 0
    complete_evidence_count: int = 0
    partial_evidence_count: int = 0
    limited_evidence_count: int = 0
    insufficient_evidence_count: int = 0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            _non_negative_integer(getattr(self, name), name)
        assessment_count = (
            self.positive_count
            + self.mixed_count
            + self.neutral_count
            + self.negative_count
            + self.insufficient_count
        )
        coverage_count = (
            self.complete_evidence_count
            + self.partial_evidence_count
            + self.limited_evidence_count
            + self.insufficient_evidence_count
        )
        if assessment_count != self.release_count:
            raise MarketplaceMomentumDomainError(
                "Assessment summary counts must equal release_count."
            )
        if coverage_count != self.release_count:
            raise MarketplaceMomentumDomainError(
                "Evidence summary counts must equal release_count."
            )


@dataclass(frozen=True)
class MarketplaceMomentumOutput:
    """Typed, immutable and history-ready Momentum output."""

    analysis_state: MomentumAnalysisState
    rule_set_version: str
    activity_thresholds: ActivityIntensityThresholds
    source_provenance: tuple[SourceProvenance, ...]
    releases: tuple[ReleaseMomentum, ...]
    summary: MarketplaceMomentumSummary
    diagnostics: tuple[MarketplaceMomentumDiagnostic, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if type(self.analysis_state) is not MomentumAnalysisState:
            raise TypeError("analysis_state must be a MomentumAnalysisState.")
        _text(self.rule_set_version, "rule_set_version")
        if type(self.activity_thresholds) is not ActivityIntensityThresholds:
            raise TypeError(
                "activity_thresholds must be ActivityIntensityThresholds."
            )
        provenance = _typed_tuple(
            self.source_provenance,
            SourceProvenance,
            "source_provenance",
        )
        module_ids = tuple(value.module_id for value in provenance)
        if len(set(module_ids)) != len(module_ids) or module_ids != tuple(
            source_id for source_id in _SOURCE_ORDER if source_id in module_ids
        ):
            raise MarketplaceMomentumDomainError(
                "Source provenance must be unique and canonically ordered."
            )
        releases = _typed_tuple(self.releases, ReleaseMomentum, "releases")
        identities = tuple(value.release_id for value in releases)
        if len(set(identities)) != len(identities):
            raise MarketplaceMomentumDomainError(
                "Release Momentum identities must be unique."
            )
        if releases != tuple(sorted(releases, key=_release_order)):
            raise MarketplaceMomentumDomainError(
                "Release Momentum must use canonical assessment order."
            )
        if any(
            value.components.activity.thresholds != self.activity_thresholds
            for value in releases
        ):
            raise MarketplaceMomentumDomainError(
                "Release activity thresholds must match the output rule context."
            )
        if type(self.summary) is not MarketplaceMomentumSummary:
            raise TypeError("summary must be a MarketplaceMomentumSummary.")
        expected_summary = _summary(releases)
        if self.summary != expected_summary:
            raise MarketplaceMomentumDomainError(
                "Momentum summary must match release detail."
            )
        diagnostics = _typed_tuple(
            self.diagnostics,
            MarketplaceMomentumDiagnostic,
            "diagnostics",
        )
        required_compatible = _required_provenance_compatible(provenance)
        _validate_compatible_provenance(provenance)
        if not required_compatible:
            if (
                self.analysis_state is not MomentumAnalysisState.INSUFFICIENT_DATA
                or releases
            ):
                raise MarketplaceMomentumDomainError(
                    "Incompatible required sources require empty insufficient output."
                )
        else:
            expected_state = _analysis_state(provenance, releases, diagnostics)
            if self.analysis_state is not expected_state:
                raise MarketplaceMomentumDomainError(
                    "Analysis state contradicts source and release coverage."
                )
        object.__setattr__(self, "source_provenance", provenance)
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "diagnostics", diagnostics)


class MarketplaceMomentumModule:
    """Apply versioned Decision Intelligence rules to normalised source facts."""

    module_id = MODULE_ID
    module_version = MODULE_VERSION
    rule_set_version = RULE_SET_VERSION

    def __init__(
        self,
        activity_thresholds: ActivityIntensityThresholds | None = None,
    ) -> None:
        if activity_thresholds is not None and type(
            activity_thresholds
        ) is not ActivityIntensityThresholds:
            raise TypeError(
                "activity_thresholds must be ActivityIntensityThresholds or None."
            )
        self.activity_thresholds = (
            activity_thresholds or ActivityIntensityThresholds()
        )

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        """Return observed Momentum without reading history or source snapshots."""

        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        supplied = context.marketplace_momentum_input
        if supplied is None:
            diagnostic = MarketplaceMomentumDiagnostic(
                MarketplaceMomentumDiagnosticCode.MISSING_REQUIRED_SOURCE,
                "Marketplace Momentum input was not supplied.",
            )
            return self._insufficient((), (diagnostic,))
        if type(supplied) is not MarketplaceMomentumInput:
            raise TypeError(
                "marketplace_momentum_input must be a MarketplaceMomentumInput or None."
            )
        if not supplied.required_sources_compatible:
            return self._insufficient(
                supplied.source_provenance,
                supplied.diagnostics,
            )

        required = {
            value.module_id: value
            for value in supplied.source_provenance
            if value.module_id in _REQUIRED_SOURCE_IDS
        }
        required_partial = any(value.partial for value in required.values())
        required_diagnostics = any(value.diagnostics for value in required.values())
        price_by_release: dict[int, list[MarketplaceMomentumPriceFact]] = {}
        for value in supplied.price_facts:
            price_by_release.setdefault(value.release_id, []).append(value)
        supply_by_release = {
            value.release_id: value for value in supplied.supply_facts
        }
        activity_by_release = {
            value.release_id: value for value in supplied.activity_facts
        }
        appearance_by_release = {
            value.release_id: value for value in supplied.appearance_facts
        }
        lifecycle_by_release: dict[int, list[MarketplaceMomentumLifecycleFact]] = {}
        for value in supplied.lifecycle_facts:
            lifecycle_by_release.setdefault(value.release_id, []).append(value)

        release_ids = sorted(
            set(price_by_release)
            | set(supply_by_release)
            | set(activity_by_release)
        )
        diagnostics = list(supplied.diagnostics)
        releases: list[ReleaseMomentum] = []
        for release_id in release_ids:
            price_facts = tuple(price_by_release.get(release_id, ()))
            supply_fact = supply_by_release.get(release_id)
            activity_fact = activity_by_release.get(release_id)
            price = _price_component(price_facts)
            supply = _supply_component(supply_fact)
            activity = _activity_component(
                activity_fact,
                self.activity_thresholds,
            )
            evidence = EvidenceCoverageComponent(
                coverage=_evidence_coverage(
                    price.comparable_change_count > 0,
                    supply.comparable_change_count > 0,
                    activity.total_activity_count is not None,
                    required_partial,
                    required_diagnostics,
                ),
                price_comparable=price.comparable_change_count > 0,
                supply_comparable=supply.comparable_change_count > 0,
                activity_available=activity.total_activity_count is not None,
                required_sources_partial=required_partial,
                required_source_diagnostics=required_diagnostics,
            )
            components = MomentumComponents(price, supply, activity, evidence)
            assessment, assessment_reason = _assessment(
                price.direction,
                supply.direction,
            )
            appearance = _appearance_context(
                activity_fact,
                appearance_by_release.get(release_id),
            )
            listing_persistence = _listing_context(
                tuple(lifecycle_by_release.get(release_id, ()))
            )
            context_sources: set[str] = set()
            if price_facts:
                context_sources.add("price_changes")
            else:
                diagnostics.append(
                    _sparse_diagnostic(release_id, "price_changes")
                )
            if supply_fact is not None:
                context_sources.add("supply_changes")
            else:
                diagnostics.append(
                    _sparse_diagnostic(release_id, "supply_changes")
                )
            if activity_fact is not None:
                context_sources.add("marketplace_activity")
            else:
                diagnostics.append(
                    _sparse_diagnostic(release_id, "marketplace_activity")
                )
            if (
                appearance is not None
                and appearance.source_module_id == "rare_appearances"
            ):
                context_sources.add("rare_appearances")
            if listing_persistence is not None:
                context_sources.add("listing_lifecycle")
            source_ids = tuple(
                source_id
                for source_id in _SOURCE_ORDER
                if source_id in context_sources
            )
            releases.append(
                ReleaseMomentum(
                    release_id=release_id,
                    assessment=assessment,
                    components=components,
                    supporting_context=FactualSupportingContext(
                        appearance=appearance,
                        listing_persistence=listing_persistence,
                    ),
                    contributing_source_ids=source_ids,
                    reason_codes=(
                        assessment_reason,
                        *_coverage_reasons(evidence),
                    ),
                )
            )
        ordered = tuple(sorted(releases, key=_release_order))
        output = MarketplaceMomentumOutput(
            analysis_state=_analysis_state(
                supplied.source_provenance,
                ordered,
                tuple(diagnostics),
            ),
            rule_set_version=self.rule_set_version,
            activity_thresholds=self.activity_thresholds,
            source_provenance=supplied.source_provenance,
            releases=ordered,
            summary=_summary(ordered),
            diagnostics=tuple(diagnostics),
        )
        summary = (
            f"Assessed observed Marketplace momentum for {len(ordered)} "
            f"release{'s' if len(ordered) != 1 else ''}."
        )
        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=IntelligenceStatus.COMPLETED,
            summary=summary,
            metrics=MappingProxyType({"output": output}),
            evidence=tuple(
                f"Release {value.release_id} uses {value.components.price.comparable_change_count} "
                "comparable price fact(s) and "
                f"{value.components.supply.comparable_change_count} comparable supply fact(s)."
                for value in ordered
            ),
            diagnostics=_result_diagnostics(output),
        )

    def _insufficient(
        self,
        provenance: tuple[SourceProvenance, ...],
        diagnostics: tuple[MarketplaceMomentumDiagnostic, ...],
    ) -> IntelligenceResult:
        output = MarketplaceMomentumOutput(
            analysis_state=MomentumAnalysisState.INSUFFICIENT_DATA,
            rule_set_version=self.rule_set_version,
            activity_thresholds=self.activity_thresholds,
            source_provenance=provenance,
            releases=(),
            summary=MarketplaceMomentumSummary(),
            diagnostics=diagnostics,
        )
        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=IntelligenceStatus.SKIPPED,
            summary=(
                "Marketplace Momentum requires compatible Price Changes, Supply "
                "Changes, and Marketplace Activity results."
            ),
            metrics=MappingProxyType({"output": output}),
            diagnostics=_result_diagnostics(output),
        )


def _price_component(
    facts: tuple[MarketplaceMomentumPriceFact, ...],
) -> PriceDirectionComponent:
    counts = Counter(value.kind for value in facts)
    increases = counts[MarketplaceMomentumPriceFactKind.INCREASED]
    decreases = counts[MarketplaceMomentumPriceFactKind.DECREASED]
    comparable = increases + decreases
    net = increases - decreases
    return PriceDirectionComponent(
        increase_count=increases,
        decrease_count=decreases,
        newly_observed_count=counts[
            MarketplaceMomentumPriceFactKind.NEWLY_OBSERVED
        ],
        no_longer_observed_count=counts[
            MarketplaceMomentumPriceFactKind.NO_LONGER_OBSERVED
        ],
        incomparable_count=counts[
            MarketplaceMomentumPriceFactKind.INCOMPARABLE
        ],
        comparable_change_count=comparable,
        net_price_direction=net,
        direction=_direction(comparable, net),
    )


def _supply_component(
    fact: MarketplaceMomentumSupplyFact | None,
) -> SupplyDirectionComponent:
    counts = Counter(() if fact is None else (fact.kind,))
    increases = counts[MarketplaceMomentumSupplyFactKind.INCREASED]
    decreases = counts[MarketplaceMomentumSupplyFactKind.DECREASED]
    comparable = increases + decreases
    net = decreases - increases
    return SupplyDirectionComponent(
        increase_count=increases,
        decrease_count=decreases,
        newly_available_count=counts[
            MarketplaceMomentumSupplyFactKind.NEWLY_AVAILABLE
        ],
        no_longer_available_count=counts[
            MarketplaceMomentumSupplyFactKind.NO_LONGER_AVAILABLE
        ],
        incomparable_count=counts[
            MarketplaceMomentumSupplyFactKind.INCOMPARABLE
        ],
        comparable_change_count=comparable,
        net_supply_pressure=net,
        direction=_direction(comparable, net),
    )


def _activity_component(
    fact: MarketplaceMomentumActivityFact | None,
    thresholds: ActivityIntensityThresholds,
) -> ActivityIntensityComponent:
    count = None if fact is None else fact.total_activity_count
    return ActivityIntensityComponent(
        total_activity_count=count,
        intensity=_activity_intensity(count, thresholds),
        thresholds=thresholds,
    )


def _appearance_context(
    activity: MarketplaceMomentumActivityFact | None,
    appearance: MarketplaceMomentumAppearanceFact | None,
) -> AppearancePersistenceContext | None:
    if activity is not None:
        return AppearancePersistenceContext(
            activity.appearance_count,
            activity.appearance_ratio,
            activity.longest_absence,
            "marketplace_activity",
        )
    if appearance is not None:
        return AppearancePersistenceContext(
            appearance.appearance_count,
            appearance.appearance_ratio,
            appearance.longest_absence,
            "rare_appearances",
        )
    return None


def _listing_context(
    facts: tuple[MarketplaceMomentumLifecycleFact, ...],
) -> ListingPersistenceContext | None:
    if not facts:
        return None
    counts = Counter(value.state for value in facts)
    return ListingPersistenceContext(
        listing_count=len(facts),
        currently_present_count=sum(value.currently_present for value in facts),
        new_count=counts[MarketplaceMomentumListingState.NEW],
        active_count=counts[MarketplaceMomentumListingState.ACTIVE],
        disappeared_count=counts[MarketplaceMomentumListingState.DISAPPEARED],
        reappeared_count=counts[MarketplaceMomentumListingState.REAPPEARED],
        intermittent_count=counts[MarketplaceMomentumListingState.INTERMITTENT],
        ended_count=counts[MarketplaceMomentumListingState.ENDED],
    )


def _direction(comparable_count: int, net: int) -> MomentumDirection:
    if comparable_count == 0:
        return MomentumDirection.INSUFFICIENT
    if net > 0:
        return MomentumDirection.POSITIVE
    if net < 0:
        return MomentumDirection.NEGATIVE
    return MomentumDirection.NEUTRAL


def _activity_intensity(
    total: int | None,
    thresholds: ActivityIntensityThresholds,
) -> ActivityIntensity:
    if total is None:
        return ActivityIntensity.INSUFFICIENT
    if total == 0:
        return ActivityIntensity.NONE
    if total <= thresholds.low_maximum:
        return ActivityIntensity.LOW
    if total <= thresholds.moderate_maximum:
        return ActivityIntensity.MODERATE
    return ActivityIntensity.HIGH


def _evidence_coverage(
    price_comparable: bool,
    supply_comparable: bool,
    activity_available: bool,
    required_sources_partial: bool,
    required_source_diagnostics: bool,
) -> EvidenceCoverage:
    if not price_comparable and not supply_comparable:
        return EvidenceCoverage.INSUFFICIENT
    if price_comparable is not supply_comparable or not activity_available:
        return EvidenceCoverage.LIMITED
    if required_sources_partial or required_source_diagnostics:
        return EvidenceCoverage.PARTIAL
    return EvidenceCoverage.COMPLETE


def _assessment(
    price: MomentumDirection,
    supply: MomentumDirection,
) -> tuple[MomentumAssessment, MomentumReasonCode]:
    if (
        price is MomentumDirection.INSUFFICIENT
        and supply is MomentumDirection.INSUFFICIENT
    ):
        return (
            MomentumAssessment.INSUFFICIENT,
            MomentumReasonCode.NO_COMPARABLE_DIRECTION,
        )
    if price is MomentumDirection.POSITIVE and supply in {
        MomentumDirection.POSITIVE,
        MomentumDirection.NEUTRAL,
    }:
        reason = (
            MomentumReasonCode.ALIGNED_POSITIVE
            if supply is MomentumDirection.POSITIVE
            else MomentumReasonCode.PRICE_POSITIVE_SUPPLY_NEUTRAL
        )
        return MomentumAssessment.POSITIVE, reason
    if price is MomentumDirection.NEGATIVE and supply in {
        MomentumDirection.NEGATIVE,
        MomentumDirection.NEUTRAL,
    }:
        reason = (
            MomentumReasonCode.ALIGNED_NEGATIVE
            if supply is MomentumDirection.NEGATIVE
            else MomentumReasonCode.PRICE_NEGATIVE_SUPPLY_NEUTRAL
        )
        return MomentumAssessment.NEGATIVE, reason
    if {price, supply} == {
        MomentumDirection.POSITIVE,
        MomentumDirection.NEGATIVE,
    }:
        return (
            MomentumAssessment.MIXED,
            MomentumReasonCode.CONFLICTING_DIRECTIONS,
        )
    directional = {MomentumDirection.POSITIVE, MomentumDirection.NEGATIVE}
    if (
        price in directional
        and supply is MomentumDirection.INSUFFICIENT
    ) or (
        supply in directional
        and price is MomentumDirection.INSUFFICIENT
    ):
        return (
            MomentumAssessment.MIXED,
            MomentumReasonCode.DIRECTION_WITH_MISSING_COUNTERPART,
        )
    if (
        price is MomentumDirection.NEUTRAL and supply in directional
    ) or (
        supply is MomentumDirection.NEUTRAL and price in directional
    ):
        return (
            MomentumAssessment.MIXED,
            MomentumReasonCode.NEUTRAL_WITH_DIRECTIONAL_SIGNAL,
        )
    return (
        MomentumAssessment.NEUTRAL,
        MomentumReasonCode.BALANCED_COMPARABLE_EVIDENCE,
    )


def _coverage_reasons(
    evidence: EvidenceCoverageComponent,
) -> tuple[MomentumReasonCode, ...]:
    reasons: list[MomentumReasonCode] = []
    if not evidence.price_comparable:
        reasons.append(MomentumReasonCode.NO_COMPARABLE_PRICE)
    if not evidence.supply_comparable:
        reasons.append(MomentumReasonCode.NO_COMPARABLE_SUPPLY)
    if not evidence.activity_available:
        reasons.append(MomentumReasonCode.NO_ACTIVITY_PROFILE)
    if evidence.required_sources_partial:
        reasons.append(MomentumReasonCode.PARTIAL_REQUIRED_SOURCE)
    if evidence.required_source_diagnostics:
        reasons.append(MomentumReasonCode.REQUIRED_SOURCE_DIAGNOSTICS)
    return tuple(reasons)


def _summary(
    releases: tuple[ReleaseMomentum, ...],
) -> MarketplaceMomentumSummary:
    assessments = Counter(value.assessment for value in releases)
    coverage = Counter(value.components.evidence.coverage for value in releases)
    return MarketplaceMomentumSummary(
        release_count=len(releases),
        positive_count=assessments[MomentumAssessment.POSITIVE],
        mixed_count=assessments[MomentumAssessment.MIXED],
        neutral_count=assessments[MomentumAssessment.NEUTRAL],
        negative_count=assessments[MomentumAssessment.NEGATIVE],
        insufficient_count=assessments[MomentumAssessment.INSUFFICIENT],
        complete_evidence_count=coverage[EvidenceCoverage.COMPLETE],
        partial_evidence_count=coverage[EvidenceCoverage.PARTIAL],
        limited_evidence_count=coverage[EvidenceCoverage.LIMITED],
        insufficient_evidence_count=coverage[EvidenceCoverage.INSUFFICIENT],
    )


def _analysis_state(
    provenance: tuple[SourceProvenance, ...],
    releases: tuple[ReleaseMomentum, ...],
    diagnostics: tuple[MarketplaceMomentumDiagnostic, ...],
) -> MomentumAnalysisState:
    if not _required_provenance_compatible(provenance):
        return MomentumAnalysisState.INSUFFICIENT_DATA
    required = tuple(
        value for value in provenance if value.module_id in _REQUIRED_SOURCE_IDS
    )
    optional = tuple(
        value for value in provenance if value.module_id not in _REQUIRED_SOURCE_IDS
    )
    partial = (
        any(value.partial or value.diagnostics for value in required)
        or any(
            not value.compatible or value.partial or value.diagnostics
            for value in optional
        )
        or any(
            value.components.evidence.coverage is not EvidenceCoverage.COMPLETE
            for value in releases
        )
        or any(
            value.code is not MarketplaceMomentumDiagnosticCode.SPARSE_RELEASE_SOURCE
            for value in diagnostics
        )
    )
    return (
        MomentumAnalysisState.PARTIAL
        if partial
        else MomentumAnalysisState.COMPLETE
    )


def _required_provenance_compatible(
    provenance: tuple[SourceProvenance, ...],
) -> bool:
    by_module = {value.module_id: value for value in provenance}
    return all(
        source_id in by_module and by_module[source_id].compatible
        for source_id in _REQUIRED_SOURCE_IDS
    )


def _validate_compatible_provenance(
    provenance: tuple[SourceProvenance, ...],
) -> None:
    if not _required_provenance_compatible(provenance):
        return
    by_module = {value.module_id: value for value in provenance}
    price = by_module["price_changes"]
    supply = by_module["supply_changes"]
    activity = by_module["marketplace_activity"]
    if price.history_snapshot_ids != supply.history_snapshot_ids:
        raise MarketplaceMomentumDomainError(
            "Compatible Price and Supply provenance must share a snapshot pair."
        )
    if (
        price.source is None
        or price.source != supply.source
        or price.source_versions != supply.source_versions
    ):
        raise MarketplaceMomentumDomainError(
            "Compatible Price and Supply provenance metadata must agree."
        )
    if activity.history_snapshot_ids[-2:] != price.history_snapshot_ids:
        raise MarketplaceMomentumDomainError(
            "Compatible Activity provenance must end with the comparison pair."
        )


def _release_order(value: ReleaseMomentum) -> tuple[int, int, int, int, int]:
    assessment_order = {
        item: index for index, item in enumerate(MomentumAssessment)
    }
    coverage_order = {
        item: index for index, item in enumerate(EvidenceCoverage)
    }
    intensity_order = {
        item: index for index, item in enumerate(ActivityIntensity)
    }
    total = value.components.activity.total_activity_count
    return (
        assessment_order[value.assessment],
        coverage_order[value.components.evidence.coverage],
        intensity_order[value.components.activity.intensity],
        -(total if total is not None else -1),
        value.release_id,
    )


def _sparse_diagnostic(
    release_id: int,
    source_module_id: str,
) -> MarketplaceMomentumDiagnostic:
    return MarketplaceMomentumDiagnostic(
        code=MarketplaceMomentumDiagnosticCode.SPARSE_RELEASE_SOURCE,
        message=(
            f"Release {release_id} has no identity-bearing "
            f"{source_module_id} detail in the supplied compatible result."
        ),
        source_module_id=source_module_id,
        release_id=release_id,
    )


def _result_diagnostics(output: MarketplaceMomentumOutput) -> tuple[str, ...]:
    source_diagnostics = tuple(
        f"{value.module_id}: {diagnostic}"
        for value in output.source_provenance
        for diagnostic in value.diagnostics
    )
    momentum_diagnostics = tuple(
        (
            f"{value.code.value}: {value.message}"
            if value.source_module_id is None
            else f"{value.code.value} [{value.source_module_id}]: {value.message}"
        )
        for value in output.diagnostics
    )
    return (*source_diagnostics, *momentum_diagnostics)


def _unique_release_facts(
    values: object,
    value_type: type[Any],
    name: str,
) -> tuple[Any, ...]:
    result = _typed_tuple(values, value_type, name)
    release_ids = tuple(value.release_id for value in result)
    if result != tuple(sorted(result, key=lambda value: value.release_id)):
        raise MarketplaceMomentumDomainError(
            f"{name} must use canonical release order."
        )
    if len(set(release_ids)) != len(release_ids):
        raise MarketplaceMomentumDomainError(
            f"{name} must contain unique release IDs."
        )
    return result


def _typed_tuple(
    values: object,
    value_type: type[Any],
    name: str,
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection.")
    try:
        result = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    if any(type(value) is not value_type for value in result):
        raise TypeError(f"{name} contains an unsupported value.")
    return result


def _strings(
    values: object,
    name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    result = _typed_tuple(values, str, name)
    for value in result:
        _text(value, f"{name} item")
    if not allow_empty and not result:
        raise MarketplaceMomentumDomainError(f"{name} must not be empty.")
    return result


def _optional_strings(
    values: object,
    name: str,
) -> tuple[str | None, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection.")
    try:
        result = tuple(values)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    for value in result:
        if value is not None:
            _text(value, f"{name} item")
    return result


def _source_id(value: object, name: str) -> None:
    _text(value, name)
    if not all(
        character.islower() or character.isdigit() or character == "_"
        for character in value  # type: ignore[union-attr]
    ):
        raise MarketplaceMomentumDomainError(
            f"{name} must use lowercase stable identifier syntax."
        )


def _text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value.strip() != value:
        raise MarketplaceMomentumDomainError(
            f"{name} must be non-empty and trimmed."
        )


def _integer(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")


def _non_negative_integer(value: object, name: str) -> None:
    _integer(value, name)
    if value < 0:  # type: ignore[operator]
        raise MarketplaceMomentumDomainError(f"{name} must be non-negative.")


def _positive_integer(value: object, name: str) -> None:
    _integer(value, name)
    if value <= 0:  # type: ignore[operator]
        raise MarketplaceMomentumDomainError(f"{name} must be positive.")


def _ratio(value: object, name: str, *, allow_zero: bool = False) -> None:
    if type(value) is not Decimal:
        raise TypeError(f"{name} must be a Decimal.")
    lower_bound = Decimal(0)
    valid_lower = value >= lower_bound if allow_zero else value > lower_bound
    if not value.is_finite() or not valid_lower or value > Decimal(1):
        qualifier = "between zero and one inclusive" if allow_zero else "above zero and at most one"
        raise MarketplaceMomentumDomainError(f"{name} must be finite and {qualifier}.")


__all__ = [
    "ActivityIntensity",
    "ActivityIntensityComponent",
    "ActivityIntensityThresholds",
    "AppearancePersistenceContext",
    "EvidenceCoverage",
    "EvidenceCoverageComponent",
    "FactualSupportingContext",
    "ListingPersistenceContext",
    "MarketplaceMomentumActivityFact",
    "MarketplaceMomentumAppearanceFact",
    "MarketplaceMomentumDiagnostic",
    "MarketplaceMomentumDiagnosticCode",
    "MarketplaceMomentumDomainError",
    "MarketplaceMomentumInput",
    "MarketplaceMomentumLifecycleFact",
    "MarketplaceMomentumListingState",
    "MarketplaceMomentumModule",
    "MarketplaceMomentumOutput",
    "MarketplaceMomentumPriceFact",
    "MarketplaceMomentumPriceFactKind",
    "MarketplaceMomentumSummary",
    "MarketplaceMomentumSupplyFact",
    "MarketplaceMomentumSupplyFactKind",
    "MomentumAnalysisState",
    "MomentumAssessment",
    "MomentumComponents",
    "MomentumDirection",
    "MomentumReasonCode",
    "PriceDirectionComponent",
    "ReleaseMomentum",
    "SourceProvenance",
    "SupplyDirectionComponent",
]
