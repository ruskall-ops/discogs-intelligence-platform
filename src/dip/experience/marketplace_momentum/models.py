"""Immutable presentation values for Marketplace Momentum."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from dip.decision_intelligence import (
    ActivityIntensity,
    EvidenceCoverage,
    MarketplaceMomentumDiagnosticCode,
    MomentumAnalysisState,
    MomentumAssessment,
    MomentumDirection,
    MomentumReasonCode,
)
from dip.intelligence import IntelligenceStatus


class MarketplaceMomentumDetailConsistencyError(ValueError):
    """Raised when Marketplace Momentum presentation values are inconsistent."""


class MarketplaceMomentumDetailState(str, Enum):
    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class ActivityIntensityThresholdsViewModel:
    low_maximum: int
    moderate_maximum: int

    def __post_init__(self) -> None:
        _positive_integer(self.low_maximum, "low_maximum")
        _positive_integer(self.moderate_maximum, "moderate_maximum")
        if self.low_maximum >= self.moderate_maximum:
            raise MarketplaceMomentumDetailConsistencyError(
                "low_maximum must be less than moderate_maximum."
            )


@dataclass(frozen=True)
class PriceDirectionComponentViewModel:
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


@dataclass(frozen=True)
class SupplyDirectionComponentViewModel:
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


@dataclass(frozen=True)
class ActivityIntensityComponentViewModel:
    total_activity_count: int | None
    intensity: ActivityIntensity
    thresholds: ActivityIntensityThresholdsViewModel

    def __post_init__(self) -> None:
        if self.total_activity_count is not None:
            _non_negative_integer(
                self.total_activity_count,
                "total_activity_count",
            )
        if type(self.intensity) is not ActivityIntensity:
            raise TypeError("intensity must be an ActivityIntensity.")
        if type(self.thresholds) is not ActivityIntensityThresholdsViewModel:
            raise TypeError(
                "thresholds must be an ActivityIntensityThresholdsViewModel."
            )


@dataclass(frozen=True)
class EvidenceCoverageComponentViewModel:
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


@dataclass(frozen=True)
class AppearancePersistenceContextViewModel:
    appearance_count: int
    appearance_ratio: Decimal
    longest_absence: int
    source_module_id: str

    def __post_init__(self) -> None:
        _non_negative_integer(self.appearance_count, "appearance_count")
        if type(self.appearance_ratio) is not Decimal:
            raise TypeError("appearance_ratio must be a Decimal.")
        _non_negative_integer(self.longest_absence, "longest_absence")
        _text(self.source_module_id, "source_module_id")


@dataclass(frozen=True)
class ListingPersistenceContextViewModel:
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


@dataclass(frozen=True)
class FactualSupportingContextViewModel:
    appearance: AppearancePersistenceContextViewModel | None = None
    listing_persistence: ListingPersistenceContextViewModel | None = None

    def __post_init__(self) -> None:
        if self.appearance is not None and type(
            self.appearance
        ) is not AppearancePersistenceContextViewModel:
            raise TypeError(
                "appearance must be an AppearancePersistenceContextViewModel "
                "or None."
            )
        if self.listing_persistence is not None and type(
            self.listing_persistence
        ) is not ListingPersistenceContextViewModel:
            raise TypeError(
                "listing_persistence must be a "
                "ListingPersistenceContextViewModel or None."
            )


@dataclass(frozen=True)
class SourceProvenanceViewModel:
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
        _text(self.module_id, "module_id")
        if self.module_version is not None:
            _text(self.module_version, "module_version")
        if type(self.result_status) is not IntelligenceStatus:
            raise TypeError("result_status must be an IntelligenceStatus.")
        if type(self.compatible) is not bool:
            raise TypeError("compatible must be a boolean.")
        if type(self.partial) is not bool:
            raise TypeError("partial must be a boolean.")
        history_snapshot_ids = _strings(
            self.history_snapshot_ids,
            "history_snapshot_ids",
        )
        if self.source is not None:
            _text(self.source, "source")
        source_versions = _optional_strings(
            self.source_versions,
            "source_versions",
        )
        diagnostics = _strings(self.diagnostics, "diagnostics")
        object.__setattr__(self, "history_snapshot_ids", history_snapshot_ids)
        object.__setattr__(self, "source_versions", source_versions)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class MarketplaceMomentumDiagnosticViewModel:
    code: MarketplaceMomentumDiagnosticCode
    message: str
    source_module_id: str | None = None
    release_id: int | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not MarketplaceMomentumDiagnosticCode:
            raise TypeError(
                "code must be a MarketplaceMomentumDiagnosticCode."
            )
        _text(self.message, "message")
        if self.source_module_id is not None:
            _text(self.source_module_id, "source_module_id")
        if self.release_id is not None:
            _positive_integer(self.release_id, "release_id")


@dataclass(frozen=True)
class ReleaseMomentumViewModel:
    release_id: int
    assessment: MomentumAssessment
    price: PriceDirectionComponentViewModel
    supply: SupplyDirectionComponentViewModel
    activity: ActivityIntensityComponentViewModel
    evidence: EvidenceCoverageComponentViewModel
    supporting_context: FactualSupportingContextViewModel
    contributing_source_ids: tuple[str, ...]
    reason_codes: tuple[MomentumReasonCode, ...]

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        if type(self.assessment) is not MomentumAssessment:
            raise TypeError("assessment must be a MomentumAssessment.")
        expected_types = (
            ("price", self.price, PriceDirectionComponentViewModel),
            ("supply", self.supply, SupplyDirectionComponentViewModel),
            ("activity", self.activity, ActivityIntensityComponentViewModel),
            ("evidence", self.evidence, EvidenceCoverageComponentViewModel),
            (
                "supporting_context",
                self.supporting_context,
                FactualSupportingContextViewModel,
            ),
        )
        for name, value, value_type in expected_types:
            if type(value) is not value_type:
                raise TypeError(f"{name} must be a {value_type.__name__}.")
        contributing_source_ids = _strings(
            self.contributing_source_ids,
            "contributing_source_ids",
        )
        reason_codes = _typed_tuple(
            self.reason_codes,
            MomentumReasonCode,
            "reason_codes",
        )
        object.__setattr__(
            self,
            "contributing_source_ids",
            contributing_source_ids,
        )
        object.__setattr__(self, "reason_codes", reason_codes)

    @property
    def price_direction(self) -> MomentumDirection:
        return self.price.direction

    @property
    def price_increase_count(self) -> int:
        return self.price.increase_count

    @property
    def price_decrease_count(self) -> int:
        return self.price.decrease_count

    @property
    def net_price_direction(self) -> int:
        return self.price.net_price_direction

    @property
    def supply_direction(self) -> MomentumDirection:
        return self.supply.direction

    @property
    def supply_increase_count(self) -> int:
        return self.supply.increase_count

    @property
    def supply_decrease_count(self) -> int:
        return self.supply.decrease_count

    @property
    def net_supply_pressure(self) -> int:
        return self.supply.net_supply_pressure

    @property
    def activity_intensity(self) -> ActivityIntensity:
        return self.activity.intensity

    @property
    def total_activity_count(self) -> int | None:
        return self.activity.total_activity_count

    @property
    def evidence_coverage(self) -> EvidenceCoverage:
        return self.evidence.coverage


@dataclass(frozen=True)
class MarketplaceMomentumSummaryViewModel:
    release_count: int
    positive_count: int
    mixed_count: int
    neutral_count: int
    negative_count: int
    insufficient_count: int
    complete_evidence_count: int
    partial_evidence_count: int
    limited_evidence_count: int
    insufficient_evidence_count: int

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            _non_negative_integer(getattr(self, name), name)


@dataclass(frozen=True)
class MarketplaceMomentumDetailViewModel:
    state: MarketplaceMomentumDetailState
    summary: str
    analysis_state: MomentumAnalysisState | None = None
    rule_set_version: str | None = None
    activity_thresholds: ActivityIntensityThresholdsViewModel | None = None
    momentum_summary: MarketplaceMomentumSummaryViewModel | None = None
    source_provenance: tuple[SourceProvenanceViewModel, ...] = ()
    releases: tuple[ReleaseMomentumViewModel, ...] = ()
    output_diagnostics: tuple[MarketplaceMomentumDiagnosticViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Marketplace Momentum")

    def __post_init__(self) -> None:
        if type(self.state) is not MarketplaceMomentumDetailState:
            raise TypeError("state must be a MarketplaceMomentumDetailState.")
        _text(self.summary, "summary")
        source_provenance = _typed_tuple(
            self.source_provenance,
            SourceProvenanceViewModel,
            "source_provenance",
        )
        releases = _typed_tuple(
            self.releases,
            ReleaseMomentumViewModel,
            "releases",
        )
        output_diagnostics = _typed_tuple(
            self.output_diagnostics,
            MarketplaceMomentumDiagnosticViewModel,
            "output_diagnostics",
        )
        diagnostics = _strings(self.diagnostics, "diagnostics")
        unavailable = {
            MarketplaceMomentumDetailState.LOADING,
            MarketplaceMomentumDetailState.UNAVAILABLE,
        }
        if self.state in unavailable:
            if (
                self.analysis_state is not None
                or self.rule_set_version is not None
                or self.activity_thresholds is not None
                or self.momentum_summary is not None
                or source_provenance
                or releases
                or output_diagnostics
                or diagnostics
            ):
                raise MarketplaceMomentumDetailConsistencyError(
                    "Unavailable detail cannot contain Marketplace Momentum output."
                )
        else:
            if type(self.analysis_state) is not MomentumAnalysisState:
                raise TypeError(
                    "analysis_state must be a MomentumAnalysisState."
                )
            if self.rule_set_version is None:
                raise MarketplaceMomentumDetailConsistencyError(
                    "Supplied detail requires a rule-set version."
                )
            _text(self.rule_set_version, "rule_set_version")
            if type(
                self.activity_thresholds
            ) is not ActivityIntensityThresholdsViewModel:
                raise TypeError(
                    "activity_thresholds must be an "
                    "ActivityIntensityThresholdsViewModel."
                )
            if type(
                self.momentum_summary
            ) is not MarketplaceMomentumSummaryViewModel:
                raise TypeError(
                    "momentum_summary must be a "
                    "MarketplaceMomentumSummaryViewModel."
                )
        object.__setattr__(self, "source_provenance", source_provenance)
        object.__setattr__(self, "releases", releases)
        object.__setattr__(self, "output_diagnostics", output_diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def release_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.release_count

    @property
    def positive_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.positive_count

    @property
    def mixed_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.mixed_count

    @property
    def neutral_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.neutral_count

    @property
    def negative_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.negative_count

    @property
    def insufficient_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.insufficient_count

    @property
    def complete_evidence_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.complete_evidence_count

    @property
    def partial_evidence_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.partial_evidence_count

    @property
    def limited_evidence_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.limited_evidence_count

    @property
    def insufficient_evidence_count(self) -> int | None:
        if self.momentum_summary is None:
            return None
        return self.momentum_summary.insufficient_evidence_count

    @classmethod
    def loading(cls) -> "MarketplaceMomentumDetailViewModel":
        return cls(
            MarketplaceMomentumDetailState.LOADING,
            "Marketplace Momentum is loading.",
        )

    @classmethod
    def unavailable(cls) -> "MarketplaceMomentumDetailViewModel":
        return cls(
            MarketplaceMomentumDetailState.UNAVAILABLE,
            "Marketplace Momentum is unavailable.",
        )


def _integer(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")


def _positive_integer(value: object, name: str) -> None:
    _integer(value, name)
    if value <= 0:
        raise MarketplaceMomentumDetailConsistencyError(
            f"{name} must be positive."
        )


def _non_negative_integer(value: object, name: str) -> None:
    _integer(value, name)
    if value < 0:
        raise MarketplaceMomentumDetailConsistencyError(
            f"{name} must be non-negative."
        )


def _text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value.strip() != value:
        raise MarketplaceMomentumDetailConsistencyError(
            f"{name} must be non-empty and trimmed."
        )


def _strings(values: object, name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(
        values,
        (tuple, list),
    ):
        raise TypeError(f"{name} must be an ordered collection.")
    result = tuple(values)
    for value in result:
        _text(value, name)
    return result


def _optional_strings(
    values: object,
    name: str,
) -> tuple[str | None, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(
        values,
        (tuple, list),
    ):
        raise TypeError(f"{name} must be an ordered collection.")
    result = tuple(values)
    for value in result:
        if value is not None:
            _text(value, name)
    return result


def _typed_tuple(
    values: object,
    value_type: type[object],
    name: str,
) -> tuple[object, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(
        values,
        (tuple, list),
    ):
        raise TypeError(f"{name} must be an ordered collection.")
    result = tuple(values)
    if any(type(value) is not value_type for value in result):
        raise TypeError(f"{name} contains an invalid value.")
    return result
