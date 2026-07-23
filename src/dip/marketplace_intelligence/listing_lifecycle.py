"""Deterministic listing lifecycle analysis over supplied Marketplace History."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from .models import MarketplaceDataStatus, MarketplaceSnapshot


class ListingLifecycleDomainError(ValueError):
    """Raised when listing lifecycle facts contradict the domain contract."""


class ListingLifecycleAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_HISTORY = "insufficient_history"


class ListingLifecycleState(str, Enum):
    """Mutually exclusive current states in canonical presentation order."""

    NEW = "new"
    ACTIVE = "active"
    DISAPPEARED = "disappeared"
    REAPPEARED = "reappeared"
    INTERMITTENT = "intermittent"
    ENDED = "ended"


@dataclass(frozen=True)
class ListingLifecycleSnapshotReference:
    snapshot_id: str
    captured_at: datetime

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        _aware(self.captured_at, "captured_at")


@dataclass(frozen=True)
class ListingLifecycle:
    release_id: int
    listing_id: str
    first_observation: ListingLifecycleSnapshotReference
    latest_observation: ListingLifecycleSnapshotReference
    snapshots_observed: int
    history_snapshot_count: int
    observation_ratio: Decimal
    currently_present: bool
    continuous_lifetime: int
    disappearance_count: int
    reappearance_count: int
    longest_absence: int
    lifecycle_state: ListingLifecycleState
    observation_snapshot_ids: tuple[str, ...]
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _text(self.listing_id, "listing_id")
        for name, value in (("first_observation", self.first_observation), ("latest_observation", self.latest_observation)):
            if type(value) is not ListingLifecycleSnapshotReference:
                raise TypeError(f"{name} must be a ListingLifecycleSnapshotReference.")
        _positive(self.snapshots_observed, "snapshots_observed")
        _positive(self.history_snapshot_count, "history_snapshot_count")
        if self.snapshots_observed > self.history_snapshot_count:
            raise ListingLifecycleDomainError("snapshots_observed cannot exceed history_snapshot_count.")
        if type(self.observation_ratio) is not Decimal:
            raise TypeError("observation_ratio must be a Decimal.")
        expected_ratio = Decimal(self.snapshots_observed) / Decimal(self.history_snapshot_count)
        if not self.observation_ratio.is_finite() or self.observation_ratio != expected_ratio:
            raise ListingLifecycleDomainError("observation_ratio must equal snapshots_observed divided by history_snapshot_count.")
        if type(self.currently_present) is not bool:
            raise TypeError("currently_present must be a boolean.")
        _positive(self.continuous_lifetime, "continuous_lifetime")
        if self.continuous_lifetime > self.snapshots_observed:
            raise ListingLifecycleDomainError("continuous_lifetime cannot exceed snapshots_observed.")
        _count(self.disappearance_count, "disappearance_count")
        _count(self.reappearance_count, "reappearance_count")
        _count(self.longest_absence, "longest_absence")
        if type(self.lifecycle_state) is not ListingLifecycleState:
            raise TypeError("lifecycle_state must be a ListingLifecycleState.")
        snapshot_ids = _strings(self.observation_snapshot_ids, "observation_snapshot_ids")
        diagnostics = _strings(self.diagnostics, "diagnostics")
        if len(snapshot_ids) != self.snapshots_observed or len(set(snapshot_ids)) != len(snapshot_ids):
            raise ListingLifecycleDomainError("Observation snapshot IDs must be unique and match snapshots_observed.")
        if snapshot_ids[0] != self.first_observation.snapshot_id or snapshot_ids[-1] != self.latest_observation.snapshot_id:
            raise ListingLifecycleDomainError("Observation boundaries must match observation snapshot order.")
        if self.first_observation.captured_at > self.latest_observation.captured_at:
            raise ListingLifecycleDomainError("First observation cannot follow latest observation.")
        _validate_state_shape(self)
        object.__setattr__(self, "observation_snapshot_ids", snapshot_ids)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True)
class ListingLifecycleSummary:
    history_snapshot_count: int
    listing_count: int
    currently_present_count: int
    excluded_snapshot_count: int = 0
    new_count: int = 0
    active_count: int = 0
    disappeared_count: int = 0
    reappeared_count: int = 0
    intermittent_count: int = 0
    ended_count: int = 0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _count(value, name)
        state_total = self.new_count + self.active_count + self.disappeared_count + self.reappeared_count + self.intermittent_count + self.ended_count
        if state_total != self.listing_count:
            raise ListingLifecycleDomainError("Lifecycle state summary counts must equal listing_count.")
        if self.currently_present_count > self.listing_count:
            raise ListingLifecycleDomainError("currently_present_count cannot exceed listing_count.")


@dataclass(frozen=True)
class ListingLifecycleOutput:
    analysis_state: ListingLifecycleAnalysisState
    snapshots: tuple[ListingLifecycleSnapshotReference, ...]
    lifecycles: tuple[ListingLifecycle, ...]
    summary: ListingLifecycleSummary
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if type(self.analysis_state) is not ListingLifecycleAnalysisState:
            raise TypeError("analysis_state must be a ListingLifecycleAnalysisState.")
        snapshots = tuple(self.snapshots)
        lifecycles = tuple(self.lifecycles)
        diagnostics = _strings(self.diagnostics, "diagnostics")
        if any(type(value) is not ListingLifecycleSnapshotReference for value in snapshots):
            raise TypeError("snapshots must contain ListingLifecycleSnapshotReference values.")
        if any(type(value) is not ListingLifecycle for value in lifecycles):
            raise TypeError("lifecycles must contain ListingLifecycle values.")
        snapshot_ids = tuple(value.snapshot_id for value in snapshots)
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise ListingLifecycleDomainError("History snapshot IDs must be unique.")
        order = tuple((value.captured_at.astimezone(timezone.utc), value.snapshot_id) for value in snapshots)
        if order != tuple(sorted(order)):
            raise ListingLifecycleDomainError("History snapshots must be chronological.")
        identities = tuple((value.release_id, value.listing_id) for value in lifecycles)
        if len(set(identities)) != len(identities):
            raise ListingLifecycleDomainError("Listing lifecycle identities must be unique.")
        if lifecycles != tuple(sorted(lifecycles, key=_lifecycle_order)):
            raise ListingLifecycleDomainError("Listing lifecycles must use canonical state and ratio order.")
        if type(self.summary) is not ListingLifecycleSummary:
            raise TypeError("summary must be a ListingLifecycleSummary.")
        if self.summary.history_snapshot_count != len(snapshots) or self.summary.listing_count != len(lifecycles):
            raise ListingLifecycleDomainError("Summary counts must match output collections.")
        if self.analysis_state is ListingLifecycleAnalysisState.COMPLETE and self.summary.excluded_snapshot_count:
            raise ListingLifecycleDomainError("Complete lifecycle output cannot report excluded snapshots.")
        if self.analysis_state is ListingLifecycleAnalysisState.PARTIAL and not diagnostics and not self.summary.excluded_snapshot_count:
            raise ListingLifecycleDomainError("Partial lifecycle output requires factual diagnostics or excluded snapshots.")
        if self.summary.currently_present_count != sum(value.currently_present for value in lifecycles):
            raise ListingLifecycleDomainError("Summary currently_present_count must match lifecycles.")
        for lifecycle in lifecycles:
            if lifecycle.history_snapshot_count != len(snapshots):
                raise ListingLifecycleDomainError("Each lifecycle history count must match analyzed snapshots.")
            references = {value.snapshot_id: value for value in snapshots}
            if references.get(lifecycle.first_observation.snapshot_id) != lifecycle.first_observation or references.get(lifecycle.latest_observation.snapshot_id) != lifecycle.latest_observation:
                raise ListingLifecycleDomainError("Lifecycle observation references must match analyzed snapshot references.")
            _validate_against_history(lifecycle, snapshot_ids)
        counts = Counter(value.lifecycle_state for value in lifecycles)
        expected = {
            ListingLifecycleState.NEW: self.summary.new_count,
            ListingLifecycleState.ACTIVE: self.summary.active_count,
            ListingLifecycleState.DISAPPEARED: self.summary.disappeared_count,
            ListingLifecycleState.REAPPEARED: self.summary.reappeared_count,
            ListingLifecycleState.INTERMITTENT: self.summary.intermittent_count,
            ListingLifecycleState.ENDED: self.summary.ended_count,
        }
        if any(counts[state] != count for state, count in expected.items()):
            raise ListingLifecycleDomainError("Summary lifecycle state counts must match lifecycles.")
        if self.analysis_state is ListingLifecycleAnalysisState.INSUFFICIENT_HISTORY and (snapshots or lifecycles or self.summary.history_snapshot_count):
            raise ListingLifecycleDomainError("Insufficient history cannot contain analyzed lifecycle data.")
        object.__setattr__(self, "snapshots", snapshots)
        object.__setattr__(self, "lifecycles", lifecycles)
        object.__setattr__(self, "diagnostics", diagnostics)


class ListingLifecycleModule:
    module_id = "listing_lifecycle"
    module_version = "1.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        history = context.marketplace_history
        if type(history) is not tuple or any(type(value) is not MarketplaceSnapshot for value in history):
            raise TypeError("marketplace_history must be a tuple of MarketplaceSnapshot values.")
        _validate_history(history)
        usable = tuple(snapshot for snapshot in history if snapshot.status not in {MarketplaceDataStatus.UNAVAILABLE, MarketplaceDataStatus.FAILED})
        excluded_count = len(history) - len(usable)
        diagnostics = [f"{value.code}: {value.message}" for snapshot in history for value in snapshot.diagnostics]
        unavailable_count = sum(snapshot.status is MarketplaceDataStatus.UNAVAILABLE for snapshot in history)
        failed_count = sum(snapshot.status is MarketplaceDataStatus.FAILED for snapshot in history)
        partial_count = sum(snapshot.status is MarketplaceDataStatus.PARTIAL for snapshot in usable)
        if unavailable_count:
            diagnostics.append(f"Ignored {unavailable_count} unavailable Marketplace snapshot{'s' if unavailable_count != 1 else ''}.")
        if failed_count:
            diagnostics.append(f"Excluded {failed_count} failed Marketplace snapshot{'s' if failed_count != 1 else ''}.")
        if partial_count:
            diagnostics.append(f"Included {partial_count} partial Marketplace snapshot{'s' if partial_count != 1 else ''}.")
        if not usable:
            output = ListingLifecycleOutput(ListingLifecycleAnalysisState.INSUFFICIENT_HISTORY, (), (), ListingLifecycleSummary(0, 0, 0, excluded_count), tuple(diagnostics))
            return IntelligenceResult(self.module_id, IntelligenceStatus.SKIPPED, "Listing Lifecycle requires at least one available Marketplace snapshot.", metrics={"output": output}, diagnostics=tuple(diagnostics), module_version=self.module_version)
        lifecycles = _analyze(usable)
        state = ListingLifecycleAnalysisState.PARTIAL if excluded_count or partial_count else ListingLifecycleAnalysisState.COMPLETE
        summary = _summary(len(usable), excluded_count, lifecycles)
        output = ListingLifecycleOutput(state, tuple(_reference(value) for value in usable), lifecycles, summary, tuple(diagnostics))
        text = f"Described the historical lifecycle of {len(lifecycles)} Marketplace listing{'s' if len(lifecycles) != 1 else ''}."
        return IntelligenceResult(self.module_id, IntelligenceStatus.COMPLETED, text, metrics={"output": output}, evidence=tuple(f"Listing {value.listing_id} for release {value.release_id} was observed in {value.snapshots_observed} of {value.history_snapshot_count} analyzed snapshots." for value in lifecycles), diagnostics=tuple(diagnostics), module_version=self.module_version)


def _analyze(history: tuple[MarketplaceSnapshot, ...]) -> tuple[ListingLifecycle, ...]:
    positions: dict[tuple[int, str], list[int]] = {}
    for index, snapshot in enumerate(history):
        seen: set[tuple[int, str]] = set()
        for listing in snapshot.listing_observations:
            identity = (listing.release_id, listing.listing_id)
            if identity in seen:
                raise ListingLifecycleDomainError(f"Duplicate listing identity {identity!r} in snapshot {snapshot.snapshot_id!r}.")
            seen.add(identity)
            positions.setdefault(identity, []).append(index)
    values = tuple(_lifecycle(identity, indexes, history) for identity, indexes in positions.items())
    return tuple(sorted(values, key=_lifecycle_order))


def _lifecycle(identity: tuple[int, str], indexes: list[int], history: tuple[MarketplaceSnapshot, ...]) -> ListingLifecycle:
    presence = tuple(index in set(indexes) for index in range(len(history)))
    observed_runs = _runs(presence, True)
    absent_runs = _runs(presence[indexes[0]:indexes[-1] + 1], False)
    disappearances = sum(left and not right for left, right in zip(presence, presence[1:]))
    reappearances = sum(not left and right for left, right in zip(presence[indexes[0]:], presence[indexes[0] + 1:]))
    trailing_absence = len(history) - indexes[-1] - 1
    currently_present = indexes[-1] == len(history) - 1
    state = _state(indexes, len(history), currently_present, reappearances, trailing_absence)
    first, latest = history[indexes[0]], history[indexes[-1]]
    return ListingLifecycle(
        release_id=identity[0],
        listing_id=identity[1],
        first_observation=_reference(first),
        latest_observation=_reference(latest),
        snapshots_observed=len(indexes),
        history_snapshot_count=len(history),
        observation_ratio=Decimal(len(indexes)) / Decimal(len(history)),
        currently_present=currently_present,
        continuous_lifetime=max(observed_runs),
        disappearance_count=disappearances,
        reappearance_count=reappearances,
        longest_absence=max(absent_runs, default=0),
        lifecycle_state=state,
        observation_snapshot_ids=tuple(history[index].snapshot_id for index in indexes),
    )


def _state(indexes: list[int], history_count: int, currently_present: bool, reappearances: int, trailing_absence: int) -> ListingLifecycleState:
    if currently_present and indexes[0] == history_count - 1:
        return ListingLifecycleState.NEW
    if currently_present and reappearances == 0:
        return ListingLifecycleState.ACTIVE
    if currently_present and reappearances == 1:
        return ListingLifecycleState.REAPPEARED
    if currently_present:
        return ListingLifecycleState.INTERMITTENT
    if trailing_absence == 1:
        return ListingLifecycleState.DISAPPEARED
    return ListingLifecycleState.ENDED


def _runs(values: tuple[bool, ...], target: bool) -> tuple[int, ...]:
    runs: list[int] = []
    current = 0
    for value in values:
        if value is target:
            current += 1
        elif current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return tuple(runs)


def _summary(history_count: int, excluded_count: int, values: tuple[ListingLifecycle, ...]) -> ListingLifecycleSummary:
    counts = Counter(value.lifecycle_state for value in values)
    return ListingLifecycleSummary(history_count, len(values), sum(value.currently_present for value in values), excluded_count, counts[ListingLifecycleState.NEW], counts[ListingLifecycleState.ACTIVE], counts[ListingLifecycleState.DISAPPEARED], counts[ListingLifecycleState.REAPPEARED], counts[ListingLifecycleState.INTERMITTENT], counts[ListingLifecycleState.ENDED])


def _validate_history(history: tuple[MarketplaceSnapshot, ...]) -> None:
    ids = tuple(value.snapshot_id for value in history)
    if len(set(ids)) != len(ids):
        raise ListingLifecycleDomainError("Marketplace History snapshot IDs must be unique.")
    order = tuple((value.captured_at.astimezone(timezone.utc), value.snapshot_id) for value in history)
    if order != tuple(sorted(order)):
        raise ListingLifecycleDomainError("Marketplace History must be chronological.")


def _reference(snapshot: MarketplaceSnapshot) -> ListingLifecycleSnapshotReference:
    return ListingLifecycleSnapshotReference(snapshot.snapshot_id, snapshot.captured_at)


def _lifecycle_order(value: ListingLifecycle) -> tuple[int, Decimal, int, str]:
    return (tuple(ListingLifecycleState).index(value.lifecycle_state), -value.observation_ratio, value.release_id, value.listing_id)


def _validate_state_shape(value: ListingLifecycle) -> None:
    state = value.lifecycle_state
    if state is ListingLifecycleState.NEW and (not value.currently_present or value.snapshots_observed != 1 or value.latest_observation.snapshot_id != value.first_observation.snapshot_id):
        raise ListingLifecycleDomainError("NEW lifecycle facts are inconsistent.")
    if state is ListingLifecycleState.ACTIVE and (not value.currently_present or value.reappearance_count != 0 or value.continuous_lifetime != value.snapshots_observed):
        raise ListingLifecycleDomainError("ACTIVE lifecycle facts are inconsistent.")
    if state is ListingLifecycleState.DISAPPEARED and value.currently_present:
        raise ListingLifecycleDomainError("DISAPPEARED lifecycle facts are inconsistent.")
    if state is ListingLifecycleState.REAPPEARED and (not value.currently_present or value.reappearance_count != 1):
        raise ListingLifecycleDomainError("REAPPEARED lifecycle facts are inconsistent.")
    if state is ListingLifecycleState.INTERMITTENT and (not value.currently_present or value.reappearance_count < 2):
        raise ListingLifecycleDomainError("INTERMITTENT lifecycle facts require repeated reappearance and current presence.")
    if state is ListingLifecycleState.ENDED and value.currently_present:
        raise ListingLifecycleDomainError("ENDED lifecycle facts are inconsistent.")


def _validate_against_history(value: ListingLifecycle, history_snapshot_ids: tuple[str, ...]) -> None:
    try:
        indexes = [history_snapshot_ids.index(snapshot_id) for snapshot_id in value.observation_snapshot_ids]
    except ValueError as exc:
        raise ListingLifecycleDomainError("Lifecycle observations must reference analyzed history snapshots.") from exc
    if indexes != sorted(indexes):
        raise ListingLifecycleDomainError("Lifecycle observation snapshot IDs must be chronological.")
    presence = tuple(index in set(indexes) for index in range(len(history_snapshot_ids)))
    disappearances = sum(left and not right for left, right in zip(presence, presence[1:]))
    reappearances = sum(not left and right for left, right in zip(presence[indexes[0]:], presence[indexes[0] + 1:]))
    continuous = max(_runs(presence, True))
    absences = _runs(presence[indexes[0]:indexes[-1] + 1], False)
    current = indexes[-1] == len(history_snapshot_ids) - 1
    trailing = len(history_snapshot_ids) - indexes[-1] - 1
    expected_state = _state(indexes, len(history_snapshot_ids), current, reappearances, trailing)
    expected = (current, continuous, disappearances, reappearances, max(absences, default=0), expected_state)
    actual = (value.currently_present, value.continuous_lifetime, value.disappearance_count, value.reappearance_count, value.longest_absence, value.lifecycle_state)
    if actual != expected:
        raise ListingLifecycleDomainError("Lifecycle facts contain an impossible transition or state.")


def _strings(values: object, name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list.")
    result = tuple(values)
    for value in result:
        _text(value, name)
    return result


def _text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value.strip() != value:
        raise ListingLifecycleDomainError(f"{name} must be non-empty and trimmed.")


def _count(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise ListingLifecycleDomainError(f"{name} must not be negative.")


def _positive(value: object, name: str) -> None:
    _count(value, name)
    if value == 0:
        raise ListingLifecycleDomainError(f"{name} must be positive.")


def _aware(value: object, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ListingLifecycleDomainError(f"{name} must be timezone-aware.")


__all__ = ["ListingLifecycle", "ListingLifecycleAnalysisState", "ListingLifecycleDomainError", "ListingLifecycleModule", "ListingLifecycleOutput", "ListingLifecycleSnapshotReference", "ListingLifecycleState", "ListingLifecycleSummary"]
