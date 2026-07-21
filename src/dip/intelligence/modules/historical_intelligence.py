"""Deterministic comparison of the two latest prepared collection snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from ..context import IntelligenceContext
from ..models import IntelligenceResult, IntelligenceStatus


@dataclass(frozen=True)
class HistoricalIntelligenceConfig:
    """Behavioural limits for Historical Intelligence."""

    maximum_gainers: int = 10
    maximum_decliners: int = 10
    minimum_absolute_value_change: Decimal = Decimal("0.01")
    minimum_percentage_change: Decimal | None = None
    value_decimal_places: int = 2
    value_fields: tuple[str, ...] = ("estimated_value", "lowest_price")

    def __post_init__(self) -> None:
        if self.maximum_gainers < 0 or self.maximum_decliners < 0:
            raise ValueError("maximum gainers and decliners must be non-negative")
        absolute = _decimal(self.minimum_absolute_value_change)
        percentage = (
            None
            if self.minimum_percentage_change is None
            else _decimal(self.minimum_percentage_change)
        )
        if absolute is None or absolute < 0:
            raise ValueError("minimum absolute value change must be non-negative")
        if percentage is not None and percentage < 0:
            raise ValueError("minimum percentage change must be non-negative")
        if not 0 <= self.value_decimal_places <= 8:
            raise ValueError("value decimal places must be between 0 and 8")
        if not self.value_fields or any(
            not isinstance(field, str) or not field.strip()
            for field in self.value_fields
        ):
            raise ValueError("at least one non-empty value field is required")
        object.__setattr__(self, "minimum_absolute_value_change", absolute)
        object.__setattr__(self, "minimum_percentage_change", percentage)
        object.__setattr__(self, "value_fields", tuple(self.value_fields))


@dataclass(frozen=True)
class HistoricalSnapshotInfo:
    snapshot_id: str
    timestamp: datetime | None
    collection_size: int
    valued_release_count: int


@dataclass(frozen=True)
class HistoricalReleaseIdentity:
    release_id: int
    artist: str
    title: str


@dataclass(frozen=True)
class HistoricalReleaseChange:
    release_id: int
    artist: str
    title: str
    previous_estimated_value: Decimal
    current_estimated_value: Decimal
    absolute_change: Decimal
    percentage_change: Decimal | None
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class HistoricalComparison:
    previous_snapshot: HistoricalSnapshotInfo
    current_snapshot: HistoricalSnapshotInfo
    elapsed_time: timedelta | None
    previous_collection_size: int
    current_collection_size: int
    collection_size_change: int
    additions: tuple[HistoricalReleaseIdentity, ...]
    removals: tuple[HistoricalReleaseIdentity, ...]
    previous_total_estimated_value: Decimal | None
    current_total_estimated_value: Decimal | None
    total_estimated_value_change: Decimal | None
    total_estimated_value_percentage_change: Decimal | None
    previous_average_release_value: Decimal | None
    current_average_release_value: Decimal | None
    average_release_value_change: Decimal | None
    previous_median_release_value: Decimal | None
    current_median_release_value: Decimal | None
    median_release_value_change: Decimal | None
    largest_gainers: tuple[HistoricalReleaseChange, ...]
    largest_decliners: tuple[HistoricalReleaseChange, ...]

    @property
    def additions_count(self) -> int:
        return len(self.additions)

    @property
    def removals_count(self) -> int:
        return len(self.removals)


@dataclass(frozen=True)
class _Snapshot:
    snapshot_id: str
    timestamp: datetime | None
    rows: Mapping[int, Mapping[str, Any]]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True)
class _Valuation:
    total: Decimal | None
    average: Decimal | None
    median: Decimal | None
    values: Mapping[int, Decimal]


class HistoricalIntelligenceModule:
    """Compare the latest and immediately preceding prepared snapshots."""

    module_id = "historical_intelligence"
    module_version = "0.2"

    def __init__(self, config: HistoricalIntelligenceConfig | None = None) -> None:
        self.config = config or HistoricalIntelligenceConfig()
        self._unit = Decimal(1).scaleb(-self.config.value_decimal_places)

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        snapshots, preparation_diagnostics = self._snapshots(context.history)
        if len(snapshots) < 2:
            return self._skipped(len(snapshots), preparation_diagnostics)

        previous, current, ordering_evidence = self._select(snapshots)
        comparison, diagnostics = self._compare(previous, current)
        evidence = (
            ordering_evidence,
            (
                f"Compared snapshot {previous.snapshot_id} with snapshot "
                f"{current.snapshot_id}."
            ),
            (
                "Collection size is the count of unique valid release identifiers; "
                f"it changed by {comparison.collection_size_change:+d}."
            ),
            (
                "Additions and removals are set differences by release_id and are "
                "excluded from valuation movements."
            ),
            self._valuation_evidence(previous, comparison.previous_snapshot),
            self._valuation_evidence(current, comparison.current_snapshot),
        )
        metrics = {
            "comparison": comparison,
            "previous_snapshot": comparison.previous_snapshot,
            "current_snapshot": comparison.current_snapshot,
            "elapsed_time": comparison.elapsed_time,
            "previous_collection_size": comparison.previous_collection_size,
            "current_collection_size": comparison.current_collection_size,
            "collection_size_change": comparison.collection_size_change,
            "additions_count": comparison.additions_count,
            "removals_count": comparison.removals_count,
            "previous_total_estimated_value": comparison.previous_total_estimated_value,
            "current_total_estimated_value": comparison.current_total_estimated_value,
            "total_estimated_value_change": comparison.total_estimated_value_change,
            "total_estimated_value_percentage_change": comparison.total_estimated_value_percentage_change,
            "previous_average_release_value": comparison.previous_average_release_value,
            "current_average_release_value": comparison.current_average_release_value,
            "average_release_value_change": comparison.average_release_value_change,
            "previous_median_release_value": comparison.previous_median_release_value,
            "current_median_release_value": comparison.current_median_release_value,
            "median_release_value_change": comparison.median_release_value_change,
            "largest_gainers": comparison.largest_gainers,
            "largest_decliners": comparison.largest_decliners,
        }
        return IntelligenceResult(
            module_id=self.module_id,
            module_version=self.module_version,
            status=IntelligenceStatus.COMPLETED,
            summary=(
                f"Historical Intelligence compared snapshots {previous.snapshot_id} "
                f"and {current.snapshot_id}; collection size changed by "
                f"{comparison.collection_size_change:+d}."
            ),
            insights=(
                f"{comparison.additions_count} additions and "
                f"{comparison.removals_count} removals were identified.",
                f"{len(comparison.largest_gainers)} gainers and "
                f"{len(comparison.largest_decliners)} decliners met the configured thresholds.",
            ),
            metrics=metrics,
            evidence=evidence,
            diagnostics=tuple(preparation_diagnostics) + diagnostics,
        )

    def _snapshots(
        self, history: Mapping[int, Sequence[Mapping[str, Any]]]
    ) -> tuple[list[_Snapshot], list[str]]:
        snapshots: list[_Snapshot] = []
        diagnostics: list[str] = []
        if not isinstance(history, Mapping):
            return snapshots, ["Historical context was not a snapshot mapping."]
        for raw_id, raw_rows in history.items():
            snapshot_id = str(raw_id)
            if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
                diagnostics.append(f"Snapshot {snapshot_id} was excluded because its rows were malformed.")
                continue
            rows: dict[int, Mapping[str, Any]] = {}
            snapshot_diagnostics: list[str] = []
            timestamps: list[datetime] = []
            for index, row in enumerate(raw_rows):
                if not isinstance(row, Mapping):
                    snapshot_diagnostics.append(f"Snapshot {snapshot_id} row {index} was excluded because it was malformed.")
                    continue
                release_id = self._release_id(row.get("release_id"))
                if release_id is None:
                    snapshot_diagnostics.append(f"Snapshot {snapshot_id} row {index} was excluded because release_id was missing or invalid.")
                    continue
                if release_id in rows:
                    snapshot_diagnostics.append(f"Snapshot {snapshot_id} duplicate release {release_id} was excluded; the first record was retained.")
                    continue
                rows[release_id] = row
                timestamp = self._timestamp(row.get("captured_at"))
                if timestamp is not None:
                    timestamps.append(timestamp)
            if raw_rows and not rows:
                diagnostics.extend(snapshot_diagnostics)
                diagnostics.append(f"Snapshot {snapshot_id} was excluded because it contained no valid release records.")
                continue
            timestamp = self._timestamp(raw_id)
            if timestamp is None and timestamps:
                timestamp = max(timestamps)
                if len(set(timestamps)) > 1:
                    snapshot_diagnostics.append(f"Snapshot {snapshot_id} contained differing capture times; the latest valid time was used.")
            snapshots.append(_Snapshot(snapshot_id, timestamp, rows, tuple(snapshot_diagnostics)))
        return snapshots, diagnostics

    def _select(self, snapshots: list[_Snapshot]) -> tuple[_Snapshot, _Snapshot, str]:
        if all(snapshot.timestamp is not None for snapshot in snapshots):
            ordered = sorted(snapshots, key=lambda item: (item.timestamp, self._id_key(item.snapshot_id)))
            rule = "Snapshots were ordered by captured_at, then snapshot identifier as a tie-breaker."
        else:
            ordered = sorted(snapshots, key=lambda item: self._id_key(item.snapshot_id))
            rule = "At least one snapshot lacked captured_at, so snapshots were ordered by snapshot identifier."
        return ordered[-2], ordered[-1], rule

    def _compare(self, previous: _Snapshot, current: _Snapshot) -> tuple[HistoricalComparison, tuple[str, ...]]:
        diagnostics = list(previous.diagnostics + current.diagnostics)
        previous_ids, current_ids = set(previous.rows), set(current.rows)
        additions = tuple(self._identity(current.rows[item], item) for item in sorted(current_ids - previous_ids))
        removals = tuple(self._identity(previous.rows[item], item) for item in sorted(previous_ids - current_ids))
        previous_values = self._valuation(previous, diagnostics)
        current_values = self._valuation(current, diagnostics)
        changes: list[HistoricalReleaseChange] = []
        for release_id in sorted(previous_ids & current_ids):
            old = previous_values.values.get(release_id)
            new = current_values.values.get(release_id)
            if old is None or new is None:
                diagnostics.append(f"Release {release_id} was excluded from value movements because both snapshots did not contain usable values.")
                continue
            change = self._round(new - old)
            percentage = None if old == 0 else self._round((change / old) * 100)
            if abs(change) < self.config.minimum_absolute_value_change:
                continue
            minimum_percentage = self.config.minimum_percentage_change
            if minimum_percentage is not None and (percentage is None or abs(percentage) < minimum_percentage):
                continue
            row = current.rows[release_id]
            identity = self._identity(row, release_id, previous.rows[release_id])
            changes.append(HistoricalReleaseChange(
                release_id, identity.artist, identity.title, old, new, change, percentage,
                (f"Release {release_id} changed from {old} to {new}; absolute change {change}.",
                 "Percentage change is unavailable because the previous value was zero." if percentage is None else f"Percentage change is {percentage}% ((current - previous) / previous × 100).")
            ))
        gainers = tuple(sorted((item for item in changes if item.absolute_change > 0), key=lambda item: (-item.absolute_change, item.release_id))[:self.config.maximum_gainers])
        decliners = tuple(sorted((item for item in changes if item.absolute_change < 0), key=lambda item: (item.absolute_change, item.release_id))[:self.config.maximum_decliners])
        elapsed = None
        if previous.timestamp is not None and current.timestamp is not None:
            elapsed = current.timestamp - previous.timestamp
            if elapsed == timedelta(0):
                diagnostics.append("The selected snapshots have identical timestamps; identifier ordering resolved the tie.")
        else:
            diagnostics.append("Elapsed time is unavailable because at least one selected snapshot has no valid timestamp.")
        previous_info = HistoricalSnapshotInfo(previous.snapshot_id, previous.timestamp, len(previous.rows), len(previous_values.values))
        current_info = HistoricalSnapshotInfo(current.snapshot_id, current.timestamp, len(current.rows), len(current_values.values))
        comparison = HistoricalComparison(
            previous_info, current_info, elapsed, len(previous.rows), len(current.rows), len(current.rows) - len(previous.rows),
            additions, removals, previous_values.total, current_values.total,
            self._difference(current_values.total, previous_values.total),
            self._percentage(current_values.total, previous_values.total),
            previous_values.average, current_values.average,
            self._difference(current_values.average, previous_values.average),
            previous_values.median, current_values.median,
            self._difference(current_values.median, previous_values.median), gainers, decliners,
        )
        return comparison, tuple(diagnostics)

    def _valuation(self, snapshot: _Snapshot, diagnostics: list[str]) -> _Valuation:
        values: dict[int, Decimal] = {}
        for release_id, row in snapshot.rows.items():
            value = next((parsed for field in self.config.value_fields if (parsed := _decimal(row.get(field))) is not None and parsed >= 0), None)
            if value is not None:
                values[release_id] = self._round(value)
        missing = len(snapshot.rows) - len(values)
        if missing:
            diagnostics.append(f"Snapshot {snapshot.snapshot_id} excluded {missing}/{len(snapshot.rows)} releases from valuation because usable value evidence was unavailable; aggregate valuation metrics were withheld.")
            return _Valuation(None, None, None, values)
        if not values:
            return _Valuation(self._round(Decimal(0)), None, None, values)
        ordered = sorted(values.values())
        total = self._round(sum(ordered, Decimal(0)))
        average = self._round(total / len(ordered))
        middle = len(ordered) // 2
        median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        return _Valuation(total, average, self._round(median), values)

    def _valuation_evidence(self, snapshot: _Snapshot, info: HistoricalSnapshotInfo) -> str:
        return (f"Snapshot {snapshot.snapshot_id} valuation coverage was {info.valued_release_count}/{info.collection_size}; "
                "total, average and median use all releases only when coverage is complete. Values use the first valid configured field: "
                + ", ".join(self.config.value_fields) + ".")

    def _skipped(self, count: int, diagnostics: list[str]) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=self.module_id, module_version=self.module_version,
            status=IntelligenceStatus.SKIPPED,
            summary="Historical Intelligence was skipped because fewer than two comparable snapshots were available.",
            metrics={"comparable_snapshot_count": count},
            evidence=(f"The prepared context contained {count} comparable snapshot(s).",),
            diagnostics=tuple(diagnostics) + ("No historical values were fabricated.",),
        )

    def _round(self, value: Decimal) -> Decimal:
        return value.quantize(self._unit, rounding=ROUND_HALF_UP)

    def _difference(self, current: Decimal | None, previous: Decimal | None) -> Decimal | None:
        return None if current is None or previous is None else self._round(current - previous)

    def _percentage(self, current: Decimal | None, previous: Decimal | None) -> Decimal | None:
        return None if current is None or previous in (None, Decimal(0)) else self._round(((current - previous) / previous) * 100)

    @staticmethod
    def _release_id(value: Any) -> int | None:
        try:
            parsed = int(value)
            return parsed if parsed > 0 and not isinstance(value, bool) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _identity(row: Mapping[str, Any], release_id: int, fallback: Mapping[str, Any] | None = None) -> HistoricalReleaseIdentity:
        fallback = fallback or {}
        artist = str(row.get("artist") or fallback.get("artist") or "Unknown artist")
        title = str(row.get("title") or fallback.get("title") or "Unknown title")
        return HistoricalReleaseIdentity(release_id, artist, title)

    @staticmethod
    def _timestamp(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            result = value
        elif isinstance(value, str) and ("-" in value or "T" in value):
            try:
                result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)

    @staticmethod
    def _id_key(value: str) -> tuple[int, Any, str]:
        try:
            return (0, int(value), value)
        except ValueError:
            return (1, value, value)


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() else None
