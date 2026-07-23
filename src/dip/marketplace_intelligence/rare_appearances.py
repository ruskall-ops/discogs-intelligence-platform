"""Deterministic historical release-appearance frequency analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from .models import MarketplaceDataStatus, MarketplaceDiagnostic, MarketplaceSnapshot


DEFAULT_APPEARANCE_THRESHOLD = 3


class RareAppearancesDomainError(ValueError):
    """Raised when historical appearance values contradict the contract."""


class RareAppearancesAnalysisState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_HISTORY = "insufficient_history"


@dataclass(frozen=True)
class RareAppearanceSnapshotReference:
    snapshot_id: str
    captured_at: datetime

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        _aware(self.captured_at, "captured_at")


@dataclass(frozen=True)
class RareAppearance:
    release_id: int
    first_observed_snapshot: RareAppearanceSnapshotReference
    latest_observed_snapshot: RareAppearanceSnapshotReference
    appearance_count: int
    history_snapshot_count: int
    appearance_ratio: Decimal
    longest_absence: int
    observation_snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        for name, value in (("first_observed_snapshot", self.first_observed_snapshot), ("latest_observed_snapshot", self.latest_observed_snapshot)):
            if type(value) is not RareAppearanceSnapshotReference:
                raise TypeError(f"{name} must be a RareAppearanceSnapshotReference.")
        _positive(self.appearance_count, "appearance_count")
        _positive(self.history_snapshot_count, "history_snapshot_count")
        if self.appearance_count > self.history_snapshot_count:
            raise RareAppearancesDomainError("appearance_count cannot exceed history_snapshot_count.")
        if type(self.appearance_ratio) is not Decimal:
            raise TypeError("appearance_ratio must be a Decimal.")
        expected_ratio = Decimal(self.appearance_count) / Decimal(self.history_snapshot_count)
        if not self.appearance_ratio.is_finite() or self.appearance_ratio != expected_ratio:
            raise RareAppearancesDomainError("appearance_ratio must equal appearance_count divided by history_snapshot_count.")
        _count(self.longest_absence, "longest_absence")
        snapshot_ids = _identifiers(self.observation_snapshot_ids, "observation_snapshot_ids")
        if len(snapshot_ids) != self.appearance_count:
            raise RareAppearancesDomainError("Observation snapshot IDs must match appearance_count.")
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise RareAppearancesDomainError("Observation snapshot IDs must be unique.")
        if snapshot_ids[0] != self.first_observed_snapshot.snapshot_id or snapshot_ids[-1] != self.latest_observed_snapshot.snapshot_id:
            raise RareAppearancesDomainError("First and latest snapshot references must match observation order.")
        if self.longest_absence > self.history_snapshot_count - self.appearance_count:
            raise RareAppearancesDomainError("longest_absence exceeds the absent snapshot count.")
        if self.appearance_count == 1 and self.longest_absence != 0:
            raise RareAppearancesDomainError("A single appearance cannot have an internal absence.")
        object.__setattr__(self, "observation_snapshot_ids", snapshot_ids)


@dataclass(frozen=True)
class RareAppearancesSummary:
    history_snapshot_count: int
    release_count: int
    included_release_count: int
    excluded_snapshot_count: int = 0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _count(value, name)
        if self.included_release_count > self.release_count:
            raise RareAppearancesDomainError("included_release_count cannot exceed release_count.")


@dataclass(frozen=True)
class RareAppearancesOutput:
    threshold: int
    analysis_state: RareAppearancesAnalysisState
    snapshots: tuple[RareAppearanceSnapshotReference, ...]
    appearances: tuple[RareAppearance, ...]
    summary: RareAppearancesSummary
    diagnostics: tuple[MarketplaceDiagnostic, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _positive(self.threshold, "threshold")
        if type(self.analysis_state) is not RareAppearancesAnalysisState:
            raise TypeError("analysis_state must be a RareAppearancesAnalysisState.")
        snapshots = tuple(self.snapshots)
        appearances = tuple(self.appearances)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not RareAppearanceSnapshotReference for value in snapshots):
            raise TypeError("snapshots must contain RareAppearanceSnapshotReference values.")
        if any(type(value) is not RareAppearance for value in appearances):
            raise TypeError("appearances must contain RareAppearance values.")
        if any(type(value) is not MarketplaceDiagnostic for value in diagnostics):
            raise TypeError("diagnostics must contain MarketplaceDiagnostic values.")
        snapshot_ids = tuple(value.snapshot_id for value in snapshots)
        if len(set(snapshot_ids)) != len(snapshot_ids):
            raise RareAppearancesDomainError("Snapshot identifiers must be unique.")
        if tuple((value.captured_at.astimezone(timezone.utc), value.snapshot_id) for value in snapshots) != tuple(sorted((value.captured_at.astimezone(timezone.utc), value.snapshot_id) for value in snapshots)):
            raise RareAppearancesDomainError("Snapshots must be in chronological order.")
        expected_order = tuple(sorted(appearances, key=lambda value: (value.appearance_count, -value.longest_absence, value.release_id)))
        if appearances != expected_order:
            raise RareAppearancesDomainError("Appearances must use canonical frequency order.")
        if len({value.release_id for value in appearances}) != len(appearances):
            raise RareAppearancesDomainError("Appearance release IDs must be unique.")
        if any(value.appearance_count >= self.threshold for value in appearances):
            raise RareAppearancesDomainError("Included appearances must be below the threshold.")
        if type(self.summary) is not RareAppearancesSummary:
            raise TypeError("summary must be a RareAppearancesSummary.")
        if self.summary.history_snapshot_count != len(snapshots) or self.summary.included_release_count != len(appearances):
            raise RareAppearancesDomainError("Summary counts must match typed output collections.")
        if self.analysis_state is RareAppearancesAnalysisState.INSUFFICIENT_HISTORY and (snapshots or appearances or self.summary.history_snapshot_count):
            raise RareAppearancesDomainError("Insufficient history cannot contain analyzed snapshots.")
        object.__setattr__(self, "snapshots", snapshots)
        object.__setattr__(self, "appearances", appearances)
        object.__setattr__(self, "diagnostics", diagnostics)


class RareAppearancesModule:
    module_id = "rare_appearances"
    module_version = "1.0"

    def __init__(self, threshold: int = DEFAULT_APPEARANCE_THRESHOLD) -> None:
        _positive(threshold, "threshold")
        self.threshold = threshold

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        if type(context.marketplace_history) is not tuple or any(type(value) is not MarketplaceSnapshot for value in context.marketplace_history):
            raise TypeError("marketplace_history must be a tuple of MarketplaceSnapshot values.")
        history = context.marketplace_history
        _validate_history(history)
        usable = tuple(snapshot for snapshot in history if snapshot.status not in {MarketplaceDataStatus.UNAVAILABLE, MarketplaceDataStatus.FAILED})
        excluded_count = len(history) - len(usable)
        source_diagnostics = tuple(diagnostic for snapshot in history for diagnostic in snapshot.diagnostics)
        diagnostics = [f"{value.code}: {value.message}" for value in source_diagnostics]
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
            output = RareAppearancesOutput(self.threshold, RareAppearancesAnalysisState.INSUFFICIENT_HISTORY, (), (), RareAppearancesSummary(0, 0, 0, excluded_count), source_diagnostics)
            return self._result(IntelligenceStatus.SKIPPED, "Rare Appearances requires at least one available Marketplace snapshot.", output, tuple(diagnostics))
        appearances, release_count = _appearances(usable, self.threshold)
        state = RareAppearancesAnalysisState.PARTIAL if excluded_count or partial_count else RareAppearancesAnalysisState.COMPLETE
        output = RareAppearancesOutput(self.threshold, state, tuple(_reference(snapshot) for snapshot in usable), appearances, RareAppearancesSummary(len(usable), release_count, len(appearances), excluded_count), source_diagnostics)
        summary = f"Found {len(appearances)} release{'s' if len(appearances) != 1 else ''} appearing in fewer than {self.threshold} analyzed snapshots."
        return self._result(IntelligenceStatus.COMPLETED, summary, output, tuple(diagnostics), tuple(f"Release {value.release_id} appeared in {value.appearance_count} of {value.history_snapshot_count} analyzed snapshots." for value in appearances))

    def _result(self, status: IntelligenceStatus, summary: str, output: RareAppearancesOutput, diagnostics: tuple[str, ...], evidence: tuple[str, ...] = ()) -> IntelligenceResult:
        return IntelligenceResult(self.module_id, status, summary, metrics={"output": output}, evidence=evidence, diagnostics=diagnostics, module_version=self.module_version)


def _appearances(history: tuple[MarketplaceSnapshot, ...], threshold: int) -> tuple[tuple[RareAppearance, ...], int]:
    positions: dict[int, list[int]] = {}
    for index, snapshot in enumerate(history):
        for observation in snapshot.release_observations:
            positions.setdefault(observation.release_id, []).append(index)
    values: list[RareAppearance] = []
    for release_id, indexes in positions.items():
        if len(indexes) >= threshold:
            continue
        gaps = tuple(right - left - 1 for left, right in zip(indexes, indexes[1:]))
        first = history[indexes[0]]
        latest = history[indexes[-1]]
        values.append(RareAppearance(release_id, _reference(first), _reference(latest), len(indexes), len(history), Decimal(len(indexes)) / Decimal(len(history)), max(gaps, default=0), tuple(history[index].snapshot_id for index in indexes)))
    return tuple(sorted(values, key=lambda value: (value.appearance_count, -value.longest_absence, value.release_id))), len(positions)


def _validate_history(history: tuple[MarketplaceSnapshot, ...]) -> None:
    ids = tuple(value.snapshot_id for value in history)
    if len(set(ids)) != len(ids):
        raise RareAppearancesDomainError("Marketplace History snapshot IDs must be unique.")
    order = tuple((value.captured_at.astimezone(timezone.utc), value.snapshot_id) for value in history)
    if order != tuple(sorted(order)):
        raise RareAppearancesDomainError("Marketplace History must be chronological.")


def _reference(snapshot: MarketplaceSnapshot) -> RareAppearanceSnapshotReference:
    return RareAppearanceSnapshotReference(snapshot.snapshot_id, snapshot.captured_at)


def _identifiers(values: object, name: str) -> tuple[str, ...]:
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
        raise RareAppearancesDomainError(f"{name} must be non-empty and trimmed.")


def _count(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise RareAppearancesDomainError(f"{name} must not be negative.")


def _positive(value: object, name: str) -> None:
    _count(value, name)
    if value == 0:
        raise RareAppearancesDomainError(f"{name} must be positive.")


def _aware(value: object, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise RareAppearancesDomainError(f"{name} must be timezone-aware.")


__all__ = ["DEFAULT_APPEARANCE_THRESHOLD", "RareAppearance", "RareAppearanceSnapshotReference", "RareAppearancesAnalysisState", "RareAppearancesDomainError", "RareAppearancesModule", "RareAppearancesOutput", "RareAppearancesSummary"]
