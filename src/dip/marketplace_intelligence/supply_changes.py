"""Deterministic factual supply comparison over two supplied snapshots."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from .models import MarketplaceDataStatus, MarketplaceDiagnostic, MarketplaceSnapshot
from .price_changes import MarketplaceSnapshotComparisonInput


class SupplyChangesDomainError(ValueError):
    """Raised when Supply Changes values contradict the contract."""


class SupplyChangesComparisonState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"
    FAILED = "failed"


class SupplyChangeKind(str, Enum):
    INCREASED = "increased"
    DECREASED = "decreased"
    NEWLY_AVAILABLE = "newly_available"
    NO_LONGER_AVAILABLE = "no_longer_available"
    INCOMPARABLE = "incomparable"


@dataclass(frozen=True)
class SupplyChangesSnapshotReference:
    snapshot_id: str
    captured_at: datetime
    source: str
    status: MarketplaceDataStatus
    source_version: str | None = None

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        _aware(self.captured_at, "captured_at")
        _text(self.source, "source")
        if type(self.status) is not MarketplaceDataStatus:
            raise TypeError("status must be a MarketplaceDataStatus.")
        if self.source_version is not None:
            _text(self.source_version, "source_version")


@dataclass(frozen=True)
class ReleaseSupplyChange:
    release_id: int
    previous_supply: int | None
    latest_supply: int | None
    delta: int | None
    change_kind: SupplyChangeKind
    previous_snapshot_id: str
    latest_snapshot_id: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _optional_count(self.previous_supply, "previous_supply")
        _optional_count(self.latest_supply, "latest_supply")
        if self.delta is not None and (type(self.delta) is not int):
            raise TypeError("delta must be an integer or None.")
        if type(self.change_kind) is not SupplyChangeKind:
            raise TypeError("change_kind must be a SupplyChangeKind.")
        _text(self.previous_snapshot_id, "previous_snapshot_id")
        _text(self.latest_snapshot_id, "latest_snapshot_id")
        evidence = _strings(self.evidence, "evidence")
        if not evidence:
            raise SupplyChangesDomainError("A supply change requires factual evidence.")
        object.__setattr__(self, "evidence", evidence)
        expected = (
            None
            if self.previous_supply is None or self.latest_supply is None
            else self.latest_supply - self.previous_supply
        )
        if self.delta != expected:
            raise SupplyChangesDomainError("Delta must equal latest supply minus previous supply.")
        shapes = {
            SupplyChangeKind.INCREASED: self.delta is not None and self.delta > 0,
            SupplyChangeKind.DECREASED: self.delta is not None and self.delta < 0,
            SupplyChangeKind.NEWLY_AVAILABLE: self.previous_supply is None and self.latest_supply is not None,
            SupplyChangeKind.NO_LONGER_AVAILABLE: self.previous_supply is not None and self.latest_supply is None,
            SupplyChangeKind.INCOMPARABLE: self.delta is None and (self.previous_supply is None or self.latest_supply is None),
        }
        if not shapes[self.change_kind]:
            raise SupplyChangesDomainError("Supply change kind contradicts its supplied values.")


@dataclass(frozen=True)
class SupplyChangesSummary:
    increased_count: int = 0
    decreased_count: int = 0
    unchanged_count: int = 0
    newly_available_count: int = 0
    no_longer_available_count: int = 0
    incomparable_count: int = 0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _count(value, name)

    @property
    def change_count(self) -> int:
        return self.increased_count + self.decreased_count + self.newly_available_count + self.no_longer_available_count + self.incomparable_count

    @property
    def assessed_count(self) -> int:
        return self.change_count + self.unchanged_count


@dataclass(frozen=True)
class SupplyChangesOutput:
    previous_snapshot: SupplyChangesSnapshotReference | None
    latest_snapshot: SupplyChangesSnapshotReference | None
    source: str | None
    comparison_state: SupplyChangesComparisonState
    changes: tuple[ReleaseSupplyChange, ...] = ()
    summary: SupplyChangesSummary = field(default_factory=SupplyChangesSummary)
    diagnostics: tuple[MarketplaceDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (("previous_snapshot", self.previous_snapshot), ("latest_snapshot", self.latest_snapshot)):
            if value is not None and type(value) is not SupplyChangesSnapshotReference:
                raise TypeError(f"{name} must be a SupplyChangesSnapshotReference or None.")
        if self.source is not None:
            _text(self.source, "source")
        if type(self.comparison_state) is not SupplyChangesComparisonState:
            raise TypeError("comparison_state must be a SupplyChangesComparisonState.")
        if type(self.summary) is not SupplyChangesSummary:
            raise TypeError("summary must be a SupplyChangesSummary.")
        changes = _changes(self.changes)
        diagnostics = tuple(self.diagnostics)
        if any(type(value) is not MarketplaceDiagnostic for value in diagnostics):
            raise TypeError("diagnostics must contain MarketplaceDiagnostic values.")
        object.__setattr__(self, "changes", changes)
        object.__setattr__(self, "diagnostics", diagnostics)
        if tuple(value.release_id for value in changes) != tuple(sorted(value.release_id for value in changes)):
            raise SupplyChangesDomainError("Supply changes must use canonical release_id order.")
        counts = Counter(value.change_kind for value in changes)
        expected = {
            SupplyChangeKind.INCREASED: self.summary.increased_count,
            SupplyChangeKind.DECREASED: self.summary.decreased_count,
            SupplyChangeKind.NEWLY_AVAILABLE: self.summary.newly_available_count,
            SupplyChangeKind.NO_LONGER_AVAILABLE: self.summary.no_longer_available_count,
            SupplyChangeKind.INCOMPARABLE: self.summary.incomparable_count,
        }
        if any(counts[kind] != count for kind, count in expected.items()):
            raise SupplyChangesDomainError("Summary counts must match detailed supply changes.")
        no_detail = self.comparison_state in {SupplyChangesComparisonState.INSUFFICIENT_HISTORY, SupplyChangesComparisonState.INSUFFICIENT_DATA, SupplyChangesComparisonState.FAILED}
        if no_detail and (changes or self.summary.assessed_count):
            raise SupplyChangesDomainError("A non-comparison state cannot contain assessed supply values.")
        if self.comparison_state is SupplyChangesComparisonState.INSUFFICIENT_HISTORY:
            if self.previous_snapshot is not None:
                raise SupplyChangesDomainError("Insufficient history cannot include a previous snapshot.")
        elif self.previous_snapshot is None or self.latest_snapshot is None:
            raise SupplyChangesDomainError("A supplied comparison requires two snapshot references.")
        if self.previous_snapshot and self.latest_snapshot:
            if self.previous_snapshot.snapshot_id == self.latest_snapshot.snapshot_id:
                raise SupplyChangesDomainError("Compared snapshot IDs must differ.")
            for change in changes:
                if (change.previous_snapshot_id, change.latest_snapshot_id) != (self.previous_snapshot.snapshot_id, self.latest_snapshot.snapshot_id):
                    raise SupplyChangesDomainError("Change snapshot references do not match the output.")


class SupplyChangesModule:
    module_id = "supply_changes"
    module_version = "1.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        comparison = context.marketplace_comparison
        if comparison is None:
            return self._insufficient(None)
        if type(comparison) is not MarketplaceSnapshotComparisonInput:
            raise TypeError("marketplace_comparison must be a MarketplaceSnapshotComparisonInput or None.")
        previous, latest = comparison.previous_snapshot, comparison.latest_snapshot
        if previous is None or latest is None:
            return self._insufficient(latest)
        previous_ref, latest_ref = _reference(previous), _reference(latest)
        source_diagnostics = (*previous.diagnostics, *latest.diagnostics)
        diagnostics = tuple(f"{value.code}: {value.message}" for value in source_diagnostics)
        source = previous.source if previous.source == latest.source else None
        if MarketplaceDataStatus.FAILED in (previous.status, latest.status):
            output = SupplyChangesOutput(previous_ref, latest_ref, source, SupplyChangesComparisonState.FAILED, diagnostics=source_diagnostics)
            return self._result(IntelligenceStatus.FAILED, "Supply Changes could not compare a failed Marketplace snapshot.", output, (*diagnostics, "A supplied Marketplace snapshot has failed status."))
        if MarketplaceDataStatus.UNAVAILABLE in (previous.status, latest.status):
            output = SupplyChangesOutput(previous_ref, latest_ref, source, SupplyChangesComparisonState.INSUFFICIENT_DATA, diagnostics=source_diagnostics)
            return self._result(IntelligenceStatus.SKIPPED, "Supply Changes requires two available Marketplace snapshots.", output, (*diagnostics, "A supplied Marketplace snapshot is unavailable."))
        if _utc(previous.captured_at) == _utc(latest.captured_at) or source is None:
            reason = "Equal capture times do not define analytical ordering." if _utc(previous.captured_at) == _utc(latest.captured_at) else "Snapshot sources differ; no supply values were compared."
            output = SupplyChangesOutput(previous_ref, latest_ref, source, SupplyChangesComparisonState.INSUFFICIENT_DATA, diagnostics=source_diagnostics)
            return self._result(IntelligenceStatus.SKIPPED, "Supply Changes could not safely compare the supplied snapshots.", output, (*diagnostics, reason))

        changes, summary = _compare(previous, latest)
        if summary.assessed_count == 0 and not (previous.status is MarketplaceDataStatus.EMPTY and latest.status is MarketplaceDataStatus.EMPTY):
            output = SupplyChangesOutput(previous_ref, latest_ref, source, SupplyChangesComparisonState.INSUFFICIENT_DATA, diagnostics=source_diagnostics)
            return self._result(IntelligenceStatus.SKIPPED, "Supply Changes found no supplied release-level supply evidence to compare.", output, (*diagnostics, "No MarketplaceReleaseObservation supply_count values were supplied."))
        partial = MarketplaceDataStatus.PARTIAL in (previous.status, latest.status) or summary.incomparable_count > 0
        state = SupplyChangesComparisonState.PARTIAL if partial else SupplyChangesComparisonState.COMPLETE
        output = SupplyChangesOutput(previous_ref, latest_ref, source, state, changes, summary, source_diagnostics)
        summary_text = (f"Detected {summary.change_count} release supply change record{'s' if summary.change_count != 1 else ''}." if summary.change_count else "No release supply changes were detected between the two snapshots.")
        return self._result(IntelligenceStatus.COMPLETED, summary_text, output, diagnostics, tuple(e for c in changes for e in c.evidence))

    def _insufficient(self, latest: MarketplaceSnapshot | None) -> IntelligenceResult:
        output = SupplyChangesOutput(None, _reference(latest) if latest else None, latest.source if latest else None, SupplyChangesComparisonState.INSUFFICIENT_HISTORY, diagnostics=latest.diagnostics if latest else ())
        diagnostics = tuple(f"{d.code}: {d.message}" for d in latest.diagnostics) if latest else ()
        return self._result(IntelligenceStatus.SKIPPED, "Supply Changes requires two Marketplace snapshots.", output, (*diagnostics, "Fewer than two Marketplace snapshots were supplied."))

    def _result(self, status: IntelligenceStatus, summary: str, output: SupplyChangesOutput, diagnostics: tuple[str, ...], evidence: tuple[str, ...] = ()) -> IntelligenceResult:
        return IntelligenceResult(self.module_id, status, summary, metrics={"output": output}, evidence=evidence, diagnostics=diagnostics, module_version=self.module_version)


def _compare(previous: MarketplaceSnapshot, latest: MarketplaceSnapshot) -> tuple[tuple[ReleaseSupplyChange, ...], SupplyChangesSummary]:
    old = {value.release_id: value for value in previous.release_observations}
    new = {value.release_id: value for value in latest.release_observations}
    changes: list[ReleaseSupplyChange] = []
    counts: Counter[str] = Counter()
    for release_id in sorted(old.keys() | new.keys()):
        before = old.get(release_id)
        after = new.get(release_id)
        previous_supply = before.supply_count if before else None
        latest_supply = after.supply_count if after else None
        comparable_before = before is not None and before.status in {MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.PARTIAL} and previous_supply is not None
        comparable_after = after is not None and after.status in {MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.PARTIAL} and latest_supply is not None
        if comparable_before and comparable_after:
            delta = latest_supply - previous_supply  # type: ignore[operator]
            if delta == 0:
                counts["unchanged_count"] += 1
                continue
            kind = SupplyChangeKind.INCREASED if delta > 0 else SupplyChangeKind.DECREASED
        elif comparable_after and (before is None or before.status in {MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.EMPTY}):
            delta, kind = None, SupplyChangeKind.NEWLY_AVAILABLE
        elif comparable_before and (after is None or after.status in {MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.EMPTY}):
            delta, kind = None, SupplyChangeKind.NO_LONGER_AVAILABLE
        else:
            delta, kind = None, SupplyChangeKind.INCOMPARABLE
            previous_supply = previous_supply if comparable_before else None
            latest_supply = latest_supply if comparable_after else None
        counts[f"{kind.value}_count"] += 1
        evidence = (f"Release {release_id} supplied supply changed from {_shown(previous_supply)} to {_shown(latest_supply)}.",)
        changes.append(ReleaseSupplyChange(release_id, previous_supply, latest_supply, delta, kind, previous.snapshot_id, latest.snapshot_id, evidence))
    return tuple(changes), SupplyChangesSummary(**counts)


def _reference(snapshot: MarketplaceSnapshot) -> SupplyChangesSnapshotReference:
    return SupplyChangesSnapshotReference(snapshot.snapshot_id, snapshot.captured_at, snapshot.source, snapshot.status, snapshot.source_version)


def _changes(values: object) -> tuple[ReleaseSupplyChange, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError("changes must be a tuple or list.")
    result = tuple(values)
    if any(type(value) is not ReleaseSupplyChange for value in result):
        raise TypeError("changes must contain ReleaseSupplyChange values.")
    if len({value.release_id for value in result}) != len(result):
        raise SupplyChangesDomainError("Supply changes must have unique release IDs.")
    return result


def _shown(value: int | None) -> str:
    return "unavailable" if value is None else str(value)


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
        raise SupplyChangesDomainError(f"{name} must be non-empty and trimmed.")


def _positive(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise SupplyChangesDomainError(f"{name} must be positive.")


def _count(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise SupplyChangesDomainError(f"{name} must not be negative.")


def _optional_count(value: object, name: str) -> None:
    if value is not None:
        _count(value, name)


def _aware(value: object, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise SupplyChangesDomainError(f"{name} must be timezone-aware.")


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


__all__ = ["ReleaseSupplyChange", "SupplyChangeKind", "SupplyChangesComparisonState", "SupplyChangesDomainError", "SupplyChangesModule", "SupplyChangesOutput", "SupplyChangesSnapshotReference", "SupplyChangesSummary"]
