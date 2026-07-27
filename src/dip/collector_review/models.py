"""Immutable domain contracts for the collector review workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import math
from types import MappingProxyType
from typing import Any

from dip.marketplace_intelligence import MarketplaceDataStatus


class CollectorReviewDomainError(ValueError):
    """Raised when collector-review values contradict the domain contract."""


class WeekendReviewTransitionError(CollectorReviewDomainError):
    """Raised when a queue status transition is not permitted."""


class WeekendReviewConflictError(RuntimeError):
    """Raised when a queue item changed after it was loaded."""


class WeekendReviewItemNotFoundError(RuntimeError):
    """Raised when a requested queue item no longer exists."""


class WeekendObservationSource(str, Enum):
    """Stable calculated observation sources."""

    HOT_NOW = "hot_now"
    HIDDEN_GEM = "hidden_gem"


class ObservationSectionStatus(str, Enum):
    """Availability of one calculated observation section."""

    AVAILABLE = "available"
    SKIPPED = "skipped"
    NO_HISTORY = "no_history"
    UNAVAILABLE = "unavailable"


class WeekendReviewStatus(str, Enum):
    """Collector-owned queue lifecycle states."""

    TO_REVIEW = "to_review"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"


class QueueAddOutcome(str, Enum):
    """Explicit result of attempting to add one release."""

    ADDED = "added"
    EXISTING_ACTIVE = "existing_active"
    EXISTING_RESOLVED = "existing_resolved"


@dataclass(frozen=True)
class ObservationIdentity:
    """Stable source/release identity preserved across refreshes."""

    source: WeekendObservationSource
    release_id: int

    def __post_init__(self) -> None:
        _enum(self.source, WeekendObservationSource, "source")
        _positive_integer(self.release_id, "release_id")


@dataclass(frozen=True)
class ObservationWarning:
    """Safe provider-neutral warning suitable for presentation."""

    code: str
    message: str

    def __post_init__(self) -> None:
        _identifier(self.code, "code")
        _normalized_line(self.message, "message")


@dataclass(frozen=True)
class MarketplaceEvidenceDetail:
    """Exact score-origin or Intelligence-origin Marketplace evidence."""

    release_id: int
    observed_at: datetime
    status: MarketplaceDataStatus | None = None
    wants: int | None = None
    haves: int | None = None
    copies_for_sale: int | None = None
    lowest_price: Decimal | None = None
    currency: str | None = None
    discogs_uri: str | None = None
    diagnostics: tuple[ObservationWarning, ...] = ()

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        _aware_datetime(self.observed_at, "observed_at")
        if self.status is not None:
            _enum(self.status, MarketplaceDataStatus, "status")
        for name, value in (
            ("wants", self.wants),
            ("haves", self.haves),
            ("copies_for_sale", self.copies_for_sale),
        ):
            _optional_non_negative_integer(value, name)
        if self.lowest_price is not None:
            if type(self.lowest_price) is not Decimal:
                raise TypeError("lowest_price must be a Decimal or None.")
            if not self.lowest_price.is_finite() or self.lowest_price < 0:
                raise CollectorReviewDomainError(
                    "lowest_price must be finite and non-negative."
                )
        _optional_trimmed_text(self.currency, "currency")
        _optional_trimmed_text(self.discogs_uri, "discogs_uri")
        object.__setattr__(
            self,
            "diagnostics",
            _typed_tuple(self.diagnostics, ObservationWarning, "diagnostics"),
        )


@dataclass(frozen=True)
class QueueMembership:
    """Release-based membership shared by every observation source."""

    queue_item_id: int | None = None
    status: WeekendReviewStatus | None = None

    def __post_init__(self) -> None:
        if self.queue_item_id is None:
            if self.status is not None:
                raise CollectorReviewDomainError(
                    "A missing queue identity cannot have a queue status."
                )
            return
        _positive_integer(self.queue_item_id, "queue_item_id")
        if self.status is None:
            raise CollectorReviewDomainError(
                "A queue identity requires a queue status."
            )
        _enum(self.status, WeekendReviewStatus, "status")

    @property
    def is_queued(self) -> bool:
        return self.queue_item_id is not None


@dataclass(frozen=True)
class HotNowObservation:
    """One stored Hot-now score projected without recalculation."""

    observation_id: ObservationIdentity
    release_id: int
    artist: str
    title: str
    calculated_at: datetime
    source_observed_at: datetime
    value_score: float
    demand_score: float
    liquidity_score: float
    momentum_score: float
    opportunity_score: float
    sell_window: str
    priority: str
    explanation: str
    evidence: MarketplaceEvidenceDetail | None
    warnings: tuple[ObservationWarning, ...] = ()
    queue_membership: QueueMembership = field(default_factory=QueueMembership)
    source_marketplace_snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.observation_id) is not ObservationIdentity:
            raise TypeError("observation_id must be an ObservationIdentity.")
        _positive_integer(self.release_id, "release_id")
        if (
            self.observation_id.source is not WeekendObservationSource.HOT_NOW
            or self.observation_id.release_id != self.release_id
        ):
            raise CollectorReviewDomainError(
                "Hot-now identity must match its source and release."
            )
        _normalized_line(self.artist, "artist", allow_empty=True)
        _normalized_line(self.title, "title", allow_empty=True)
        _aware_datetime(self.calculated_at, "calculated_at")
        _aware_datetime(self.source_observed_at, "source_observed_at")
        for name in (
            "value_score",
            "demand_score",
            "liquidity_score",
            "momentum_score",
            "opportunity_score",
        ):
            _finite_number(getattr(self, name), name)
        if self.sell_window != "Hot now":
            raise CollectorReviewDomainError(
                "A HotNowObservation must retain the 'Hot now' classification."
            )
        _normalized_line(self.priority, "priority", allow_empty=True)
        _normalized_line(self.explanation, "explanation", allow_empty=True)
        if self.evidence is not None:
            if type(self.evidence) is not MarketplaceEvidenceDetail:
                raise TypeError(
                    "evidence must be a MarketplaceEvidenceDetail or None."
                )
            if self.evidence.release_id != self.release_id:
                raise CollectorReviewDomainError(
                    "Hot-now evidence must belong to the observed release."
                )
        object.__setattr__(
            self,
            "warnings",
            _typed_tuple(self.warnings, ObservationWarning, "warnings"),
        )
        if type(self.queue_membership) is not QueueMembership:
            raise TypeError("queue_membership must be a QueueMembership.")
        _optional_trimmed_text(
            self.source_marketplace_snapshot_id,
            "source_marketplace_snapshot_id",
        )


@dataclass(frozen=True)
class HiddenGemObservation:
    """One candidate reconstructed from persisted Hidden Gems intelligence."""

    observation_id: ObservationIdentity
    release_id: int
    artist: str
    title: str
    rank: int
    hidden_gem_score: float
    factor_scores: Mapping[str, float | None]
    supporting_metrics: Mapping[str, Any]
    summary: str
    evidence: tuple[str, ...]
    execution_timestamp: datetime
    source_intelligence_run_id: int
    source_marketplace_snapshot_id: str | None
    marketplace_evidence: MarketplaceEvidenceDetail | None
    warnings: tuple[ObservationWarning, ...] = ()
    queue_membership: QueueMembership = field(default_factory=QueueMembership)

    def __post_init__(self) -> None:
        if type(self.observation_id) is not ObservationIdentity:
            raise TypeError("observation_id must be an ObservationIdentity.")
        _positive_integer(self.release_id, "release_id")
        if (
            self.observation_id.source is not WeekendObservationSource.HIDDEN_GEM
            or self.observation_id.release_id != self.release_id
        ):
            raise CollectorReviewDomainError(
                "Hidden Gem identity must match its source and release."
            )
        _normalized_line(self.artist, "artist", allow_empty=True)
        _normalized_line(self.title, "title", allow_empty=True)
        _positive_integer(self.rank, "rank")
        _finite_number(self.hidden_gem_score, "hidden_gem_score")
        object.__setattr__(
            self,
            "factor_scores",
            _freeze_factor_scores(self.factor_scores),
        )
        object.__setattr__(
            self,
            "supporting_metrics",
            _freeze_mapping(self.supporting_metrics, "supporting_metrics"),
        )
        _normalized_line(self.summary, "summary")
        object.__setattr__(
            self,
            "evidence",
            _string_tuple(self.evidence, "evidence"),
        )
        _aware_datetime(self.execution_timestamp, "execution_timestamp")
        _positive_integer(
            self.source_intelligence_run_id,
            "source_intelligence_run_id",
        )
        _optional_trimmed_text(
            self.source_marketplace_snapshot_id,
            "source_marketplace_snapshot_id",
        )
        if self.marketplace_evidence is not None:
            if type(self.marketplace_evidence) is not MarketplaceEvidenceDetail:
                raise TypeError(
                    "marketplace_evidence must be MarketplaceEvidenceDetail or None."
                )
            if self.marketplace_evidence.release_id != self.release_id:
                raise CollectorReviewDomainError(
                    "Hidden Gem evidence must belong to the candidate release."
                )
        object.__setattr__(
            self,
            "warnings",
            _typed_tuple(self.warnings, ObservationWarning, "warnings"),
        )
        if type(self.queue_membership) is not QueueMembership:
            raise TypeError("queue_membership must be a QueueMembership.")


WeekendObservation = HotNowObservation | HiddenGemObservation


@dataclass(frozen=True)
class ObservationSourceSection:
    """One source-specific observation state and its immutable rows."""

    source: WeekendObservationSource
    status: ObservationSectionStatus
    summary: str
    observations: tuple[WeekendObservation, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _enum(self.source, WeekendObservationSource, "source")
        _enum(self.status, ObservationSectionStatus, "status")
        _normalized_line(self.summary, "summary")
        observations = _typed_union_tuple(
            self.observations,
            (HotNowObservation, HiddenGemObservation),
            "observations",
        )
        if any(value.observation_id.source is not self.source for value in observations):
            raise CollectorReviewDomainError(
                "A source section may contain only observations from its source."
            )
        if self.status is not ObservationSectionStatus.AVAILABLE and observations:
            raise CollectorReviewDomainError(
                "Only an available source section may contain observations."
            )
        identities = tuple(value.observation_id for value in observations)
        if len(set(identities)) != len(identities):
            raise CollectorReviewDomainError(
                "A source section cannot contain duplicate observation identities."
            )
        object.__setattr__(self, "observations", observations)
        object.__setattr__(
            self,
            "diagnostics",
            _string_tuple(self.diagnostics, "diagnostics"),
        )


@dataclass(frozen=True)
class WeekendObservationWorkspace:
    """One coherent read-only observation result used by Dashboard and review."""

    hot_now_section: ObservationSourceSection
    hidden_gems_section: ObservationSourceSection

    def __post_init__(self) -> None:
        if type(self.hot_now_section) is not ObservationSourceSection:
            raise TypeError("hot_now_section must be an ObservationSourceSection.")
        if type(self.hidden_gems_section) is not ObservationSourceSection:
            raise TypeError(
                "hidden_gems_section must be an ObservationSourceSection."
            )
        if self.hot_now_section.source is not WeekendObservationSource.HOT_NOW:
            raise CollectorReviewDomainError(
                "hot_now_section must use the Hot-now source."
            )
        if (
            self.hidden_gems_section.source
            is not WeekendObservationSource.HIDDEN_GEM
        ):
            raise CollectorReviewDomainError(
                "hidden_gems_section must use the Hidden Gem source."
            )

    @property
    def hot_now(self) -> tuple[HotNowObservation, ...]:
        return tuple(
            value
            for value in self.hot_now_section.observations
            if type(value) is HotNowObservation
        )

    @property
    def hidden_gems(self) -> tuple[HiddenGemObservation, ...]:
        return tuple(
            value
            for value in self.hidden_gems_section.observations
            if type(value) is HiddenGemObservation
        )

    @classmethod
    def unavailable(cls, message: str) -> "WeekendObservationWorkspace":
        _normalized_line(message, "message")
        return cls(
            ObservationSourceSection(
                WeekendObservationSource.HOT_NOW,
                ObservationSectionStatus.UNAVAILABLE,
                message,
            ),
            ObservationSourceSection(
                WeekendObservationSource.HIDDEN_GEM,
                ObservationSectionStatus.UNAVAILABLE,
                message,
            ),
        )


@dataclass(frozen=True)
class NewWeekendReviewQueueEntry:
    """Validated queue values awaiting a database-allocated identity."""

    release_id: int
    added_at: datetime
    status: WeekendReviewStatus
    review_note: str
    updated_at: datetime
    resolved_at: datetime | None
    source_type: WeekendObservationSource
    source_observed_at: datetime
    source_summary: str
    source_intelligence_run_id: int | None
    source_marketplace_snapshot_id: str | None

    def __post_init__(self) -> None:
        _validate_queue_values(self)


@dataclass(frozen=True)
class WeekendReviewQueueItem:
    """One durable collector-owned queue item."""

    queue_item_id: int
    release_id: int
    added_at: datetime
    status: WeekendReviewStatus
    review_note: str
    updated_at: datetime
    resolved_at: datetime | None
    source_type: WeekendObservationSource
    source_observed_at: datetime
    source_summary: str
    source_intelligence_run_id: int | None
    source_marketplace_snapshot_id: str | None

    def __post_init__(self) -> None:
        _positive_integer(self.queue_item_id, "queue_item_id")
        _validate_queue_values(self)


@dataclass(frozen=True)
class QueueAddResult:
    """One explicit add outcome and the durable item involved."""

    outcome: QueueAddOutcome
    item: WeekendReviewQueueItem

    def __post_init__(self) -> None:
        _enum(self.outcome, QueueAddOutcome, "outcome")
        if type(self.item) is not WeekendReviewQueueItem:
            raise TypeError("item must be a WeekendReviewQueueItem.")
        if (
            self.outcome is QueueAddOutcome.EXISTING_RESOLVED
            and self.item.status is not WeekendReviewStatus.RESOLVED
        ):
            raise CollectorReviewDomainError(
                "An existing-resolved outcome requires a resolved item."
            )
        if (
            self.outcome is QueueAddOutcome.EXISTING_ACTIVE
            and self.item.status is WeekendReviewStatus.RESOLVED
        ):
            raise CollectorReviewDomainError(
                "An existing-active outcome requires an active item."
            )


def normalize_source_summary(value: str) -> str:
    """Return the one-line deterministic source-summary representation."""

    if not isinstance(value, str):
        raise TypeError("source_summary must be a string.")
    return " ".join(value.split())


def normalize_review_note(value: str) -> str:
    """Return the canonical queue-note representation."""

    if not isinstance(value, str):
        raise TypeError("review_note must be a string.")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def utc_instant(value: datetime) -> datetime:
    """Return one aware datetime normalized for deterministic comparison."""

    _aware_datetime(value, "datetime")
    return value.astimezone(timezone.utc)


def _validate_queue_values(value: Any) -> None:
    _positive_integer(value.release_id, "release_id")
    _aware_datetime(value.added_at, "added_at")
    _enum(value.status, WeekendReviewStatus, "status")
    if normalize_review_note(value.review_note) != value.review_note:
        raise CollectorReviewDomainError("review_note must already be normalized.")
    _aware_datetime(value.updated_at, "updated_at")
    if value.resolved_at is not None:
        _aware_datetime(value.resolved_at, "resolved_at")
    _enum(value.source_type, WeekendObservationSource, "source_type")
    _aware_datetime(value.source_observed_at, "source_observed_at")
    _normalized_line(value.source_summary, "source_summary")
    if normalize_source_summary(value.source_summary) != value.source_summary:
        raise CollectorReviewDomainError(
            "source_summary must contain normalized one-line whitespace."
        )
    if value.source_intelligence_run_id is not None:
        _positive_integer(
            value.source_intelligence_run_id,
            "source_intelligence_run_id",
        )
    _optional_trimmed_text(
        value.source_marketplace_snapshot_id,
        "source_marketplace_snapshot_id",
    )
    if (
        value.source_type is WeekendObservationSource.HIDDEN_GEM
        and value.source_intelligence_run_id is None
    ):
        raise CollectorReviewDomainError(
            "A Hidden Gem queue item requires Intelligence provenance."
        )
    if (
        value.source_type is WeekendObservationSource.HOT_NOW
        and value.source_intelligence_run_id is not None
    ):
        raise CollectorReviewDomainError(
            "A Hot-now queue item cannot claim Intelligence provenance."
        )

    source_at = utc_instant(value.source_observed_at)
    added_at = utc_instant(value.added_at)
    updated_at = utc_instant(value.updated_at)
    if source_at > added_at:
        raise CollectorReviewDomainError(
            "source_observed_at must not follow added_at."
        )
    if added_at > updated_at:
        raise CollectorReviewDomainError("added_at must not follow updated_at.")
    if value.status is WeekendReviewStatus.RESOLVED:
        if value.resolved_at is None:
            raise CollectorReviewDomainError(
                "A resolved item requires resolved_at."
            )
        resolved_at = utc_instant(value.resolved_at)
        if not added_at <= resolved_at <= updated_at:
            raise CollectorReviewDomainError(
                "resolved_at must fall between added_at and updated_at."
            )
    elif value.resolved_at is not None:
        raise CollectorReviewDomainError(
            "An active item cannot contain resolved_at."
        )


def _positive_integer(value: Any, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise CollectorReviewDomainError(f"{name} must be positive.")
    return value


def _optional_non_negative_integer(value: Any, name: str) -> None:
    if value is None:
        return
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer or None.")
    if value < 0:
        raise CollectorReviewDomainError(f"{name} must be non-negative.")


def _aware_datetime(value: Any, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise CollectorReviewDomainError(f"{name} must be timezone-aware.")


def _finite_number(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric.")
    if not math.isfinite(float(value)):
        raise CollectorReviewDomainError(f"{name} must be finite.")


def _enum(value: Any, enum_type: type[Enum], name: str) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{name} must be a {enum_type.__name__}.")


def _identifier(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if (
        not value
        or value != value.strip()
        or any(not (character.islower() or character.isdigit() or character == "_")
                for character in value)
    ):
        raise CollectorReviewDomainError(
            f"{name} must be a non-empty lowercase identifier."
        )


def _normalized_line(
    value: Any,
    name: str,
    *,
    allow_empty: bool = False,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not allow_empty and not value:
        raise CollectorReviewDomainError(f"{name} must be non-empty.")
    if "\n" in value or "\r" in value or value != value.strip():
        raise CollectorReviewDomainError(
            f"{name} must be a trimmed single line."
        )


def _optional_trimmed_text(value: Any, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None.")
    if not value or value != value.strip():
        raise CollectorReviewDomainError(
            f"{name} must be non-empty and trimmed when supplied."
        )


def _typed_tuple(
    values: Any,
    item_type: type[Any],
    name: str,
) -> tuple[Any, ...]:
    return _typed_union_tuple(values, (item_type,), name)


def _typed_union_tuple(
    values: Any,
    item_types: tuple[type[Any], ...],
    name: str,
) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    if any(type(value) not in item_types for value in result):
        raise TypeError(f"{name} contains an unsupported value.")
    return result


def _string_tuple(values: Any, name: str) -> tuple[str, ...]:
    result = _typed_tuple(values, str, name)
    return tuple(result)


def _freeze_factor_scores(
    values: Mapping[str, float | None],
) -> Mapping[str, float | None]:
    if not isinstance(values, Mapping):
        raise TypeError("factor_scores must be a mapping.")
    frozen: dict[str, float | None] = {}
    for key in sorted(values):
        _identifier(key, "factor_scores key")
        score = values[key]
        if score is not None:
            _finite_number(score, f"factor_scores[{key!r}]")
            score = float(score)
        frozen[key] = score
    return MappingProxyType(frozen)


def _freeze_mapping(values: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must be a mapping.")
    frozen: dict[str, Any] = {}
    for key in sorted(values):
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be strings.")
        frozen[key] = _freeze_value(values[key], f"{name}[{key!r}]")
    return MappingProxyType(frozen)


def _freeze_value(value: Any, path: str) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value, path)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise CollectorReviewDomainError(f"{path} must be finite.")
        return value
    if type(value) is Decimal:
        if not value.is_finite():
            raise CollectorReviewDomainError(f"{path} must be finite.")
        return value
    if isinstance(value, Enum):
        return value
    if type(value) is datetime:
        _aware_datetime(value, path)
        return value
    raise TypeError(f"{path} contains unsupported type {type(value).__name__}.")


__all__ = [
    "CollectorReviewDomainError",
    "HiddenGemObservation",
    "HotNowObservation",
    "MarketplaceEvidenceDetail",
    "NewWeekendReviewQueueEntry",
    "ObservationIdentity",
    "ObservationSectionStatus",
    "ObservationSourceSection",
    "ObservationWarning",
    "QueueAddOutcome",
    "QueueAddResult",
    "QueueMembership",
    "WeekendObservation",
    "WeekendObservationSource",
    "WeekendObservationWorkspace",
    "WeekendReviewConflictError",
    "WeekendReviewItemNotFoundError",
    "WeekendReviewQueueItem",
    "WeekendReviewStatus",
    "WeekendReviewTransitionError",
    "normalize_review_note",
    "normalize_source_summary",
    "utc_instant",
]
