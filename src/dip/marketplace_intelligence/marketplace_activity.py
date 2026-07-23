"""Composite aggregation of existing Marketplace Intelligence outputs."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from .price_changes import PriceChangesOutput
from .rare_appearances import RareAppearancesAnalysisState, RareAppearancesOutput
from .supply_changes import SupplyChangesOutput


class MarketplaceActivityDomainError(ValueError):
    """Raised when composite source facts cannot form a consistent profile."""


class MarketplaceActivityState(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class MarketplaceActivityObservationReference:
    snapshot_id: str
    captured_at: datetime

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        if type(self.captured_at) is not datetime or self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise MarketplaceActivityDomainError("captured_at must be timezone-aware.")


@dataclass(frozen=True)
class ReleaseActivity:
    release_id: int
    appearance_count: int
    appearance_ratio: Decimal
    historical_price_change_count: int
    historical_supply_change_count: int
    longest_absence: int
    first_observation: MarketplaceActivityObservationReference
    latest_observation: MarketplaceActivityObservationReference
    total_activity_count: int

    def __post_init__(self) -> None:
        _positive(self.release_id, "release_id")
        _positive(self.appearance_count, "appearance_count")
        _count(self.historical_price_change_count, "historical_price_change_count")
        _count(self.historical_supply_change_count, "historical_supply_change_count")
        _count(self.longest_absence, "longest_absence")
        _count(self.total_activity_count, "total_activity_count")
        if type(self.appearance_ratio) is not Decimal or not self.appearance_ratio.is_finite() or not Decimal(0) < self.appearance_ratio <= Decimal(1):
            raise MarketplaceActivityDomainError("appearance_ratio must be a finite Decimal between zero and one.")
        for name, value in (("first_observation", self.first_observation), ("latest_observation", self.latest_observation)):
            if type(value) is not MarketplaceActivityObservationReference:
                raise TypeError(f"{name} must be a MarketplaceActivityObservationReference.")
        if self.first_observation.captured_at > self.latest_observation.captured_at:
            raise MarketplaceActivityDomainError("First observation cannot follow latest observation.")
        expected = self.appearance_count + self.historical_price_change_count + self.historical_supply_change_count
        if self.total_activity_count != expected:
            raise MarketplaceActivityDomainError("total_activity_count must equal the aggregated source event counts.")


@dataclass(frozen=True)
class MarketplaceActivitySummary:
    release_count: int = 0
    total_activity_count: int = 0
    price_change_count: int = 0
    supply_change_count: int = 0
    appearance_count: int = 0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            _count(value, name)
        if self.total_activity_count != self.price_change_count + self.supply_change_count + self.appearance_count:
            raise MarketplaceActivityDomainError("Summary total activity count is inconsistent.")


@dataclass(frozen=True)
class MarketplaceActivityOutput:
    state: MarketplaceActivityState
    history_snapshot_ids: tuple[str, ...]
    activities: tuple[ReleaseActivity, ...]
    summary: MarketplaceActivitySummary = field(default_factory=MarketplaceActivitySummary)
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.state) is not MarketplaceActivityState:
            raise TypeError("state must be a MarketplaceActivityState.")
        history_ids = _strings(self.history_snapshot_ids, "history_snapshot_ids")
        activities = tuple(self.activities)
        diagnostics = _strings(self.diagnostics, "diagnostics")
        if len(set(history_ids)) != len(history_ids):
            raise MarketplaceActivityDomainError("History snapshot IDs must be unique.")
        if any(type(value) is not ReleaseActivity for value in activities):
            raise TypeError("activities must contain ReleaseActivity values.")
        if len({value.release_id for value in activities}) != len(activities):
            raise MarketplaceActivityDomainError("Release activities must have unique release IDs.")
        expected_order = tuple(sorted(activities, key=lambda value: (-value.total_activity_count, value.appearance_count, value.release_id)))
        if activities != expected_order:
            raise MarketplaceActivityDomainError("Release activities must use canonical activity order.")
        if type(self.summary) is not MarketplaceActivitySummary:
            raise TypeError("summary must be a MarketplaceActivitySummary.")
        if self.summary.release_count != len(activities):
            raise MarketplaceActivityDomainError("Summary release_count must match activities.")
        if self.summary.total_activity_count != sum(value.total_activity_count for value in activities):
            raise MarketplaceActivityDomainError("Summary total_activity_count must match activities.")
        if self.summary.price_change_count != sum(value.historical_price_change_count for value in activities):
            raise MarketplaceActivityDomainError("Summary price_change_count must match activities.")
        if self.summary.supply_change_count != sum(value.historical_supply_change_count for value in activities):
            raise MarketplaceActivityDomainError("Summary supply_change_count must match activities.")
        if self.summary.appearance_count != sum(value.appearance_count for value in activities):
            raise MarketplaceActivityDomainError("Summary appearance_count must match activities.")
        if self.state is MarketplaceActivityState.INSUFFICIENT_DATA and (history_ids or activities or self.summary.release_count):
            raise MarketplaceActivityDomainError("Insufficient data cannot contain aggregated activity.")
        object.__setattr__(self, "history_snapshot_ids", history_ids)
        object.__setattr__(self, "activities", activities)
        object.__setattr__(self, "diagnostics", diagnostics)


class MarketplaceActivityModule:
    module_id = "marketplace_activity"
    module_version = "1.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        sources = context.marketplace_activity_sources
        if type(sources) is not tuple or any(type(value) is not IntelligenceResult for value in sources):
            raise TypeError("marketplace_activity_sources must be a tuple of IntelligenceResult values.")
        by_module: dict[str, IntelligenceResult] = {}
        for source in sources:
            if source.module_id in by_module:
                raise MarketplaceActivityDomainError(f"Duplicate source result for {source.module_id!r}.")
            by_module[source.module_id] = source
        required = ("price_changes", "supply_changes", "rare_appearances")
        missing = tuple(module_id for module_id in required if module_id not in by_module)
        if missing:
            diagnostic = f"Missing required source intelligence: {', '.join(missing)}."
            return self._insufficient((diagnostic,))
        try:
            price_result, price = _typed_source(by_module["price_changes"], PriceChangesOutput)
            supply_result, supply = _typed_source(by_module["supply_changes"], SupplyChangesOutput)
            rare_result, rare = _typed_source(by_module["rare_appearances"], RareAppearancesOutput)
        except (TypeError, MarketplaceActivityDomainError) as exc:
            return self._insufficient((f"Source intelligence is incompatible: {exc}",))
        diagnostics = tuple(value for source in sources for value in source.diagnostics)
        if rare.analysis_state is RareAppearancesAnalysisState.INSUFFICIENT_HISTORY:
            return self._insufficient((*diagnostics, "Rare Appearances contains no analyzed Marketplace history."))
        history_ids = tuple(value.snapshot_id for value in rare.snapshots)
        compatibility = _compatibility_diagnostics(price, supply, history_ids)
        if compatibility:
            return self._insufficient((*diagnostics, *compatibility))
        price_counts: Counter[int] = Counter()
        for change in (*price.listing_changes, *price.release_changes):
            price_counts[change.release_id] += 1
        supply_counts = Counter(change.release_id for change in supply.changes)
        appearances_by_id = {value.release_id: value for value in rare.appearances}
        unmatched = sorted((set(price_counts) | set(supply_counts)) - set(appearances_by_id))
        aggregate_diagnostics = list(diagnostics)
        if unmatched:
            aggregate_diagnostics.append(
                "Source change records lacked threshold-qualified appearance detail for release IDs: "
                + ", ".join(str(value) for value in unmatched)
                + "."
            )
        activities = tuple(
            sorted(
                (
                    ReleaseActivity(
                        release_id=value.release_id,
                        appearance_count=value.appearance_count,
                        appearance_ratio=value.appearance_ratio,
                        historical_price_change_count=price_counts[value.release_id],
                        historical_supply_change_count=supply_counts[value.release_id],
                        longest_absence=value.longest_absence,
                        first_observation=MarketplaceActivityObservationReference(value.first_observed_snapshot.snapshot_id, value.first_observed_snapshot.captured_at),
                        latest_observation=MarketplaceActivityObservationReference(value.latest_observed_snapshot.snapshot_id, value.latest_observed_snapshot.captured_at),
                        total_activity_count=value.appearance_count + price_counts[value.release_id] + supply_counts[value.release_id],
                    )
                    for value in rare.appearances
                ),
                key=lambda value: (-value.total_activity_count, value.appearance_count, value.release_id),
            )
        )
        summary = MarketplaceActivitySummary(len(activities), sum(value.total_activity_count for value in activities), sum(value.historical_price_change_count for value in activities), sum(value.historical_supply_change_count for value in activities), sum(value.appearance_count for value in activities))
        partial = unmatched or rare.analysis_state is RareAppearancesAnalysisState.PARTIAL or any(source.status is not IntelligenceStatus.COMPLETED for source in (price_result, supply_result, rare_result))
        state = MarketplaceActivityState.PARTIAL if partial else MarketplaceActivityState.COMPLETE
        output = MarketplaceActivityOutput(state, history_ids, activities, summary, tuple(aggregate_diagnostics))
        text = f"Aggregated factual Marketplace activity for {len(activities)} release{'s' if len(activities) != 1 else ''}."
        return IntelligenceResult(self.module_id, IntelligenceStatus.COMPLETED, text, metrics={"output": output}, evidence=tuple(f"Release {value.release_id} has {value.total_activity_count} aggregated historical events." for value in activities), diagnostics=tuple(aggregate_diagnostics), module_version=self.module_version)

    def _insufficient(self, diagnostics: tuple[str, ...]) -> IntelligenceResult:
        output = MarketplaceActivityOutput(MarketplaceActivityState.INSUFFICIENT_DATA, (), (), diagnostics=diagnostics)
        return IntelligenceResult(self.module_id, IntelligenceStatus.SKIPPED, "Marketplace Activity requires compatible Price Changes, Supply Changes, and Rare Appearances results.", metrics={"output": output}, diagnostics=diagnostics, module_version=self.module_version)


def _typed_source(result: IntelligenceResult, output_type: type) -> tuple[IntelligenceResult, object]:
    if not isinstance(result.metrics, Mapping):
        raise TypeError(f"{result.module_id} metrics must be a mapping.")
    output = result.metrics.get("output")
    if type(output) is not output_type:
        raise MarketplaceActivityDomainError(f"{result.module_id} requires its typed output.")
    return result, output


def _compatibility_diagnostics(price: PriceChangesOutput, supply: SupplyChangesOutput, history_ids: tuple[str, ...]) -> tuple[str, ...]:
    diagnostics: list[str] = []
    price_pair = _price_pair(price)
    supply_pair = _supply_pair(supply)
    if price_pair and supply_pair and price_pair != supply_pair:
        diagnostics.append("Price Changes and Supply Changes reference different snapshot pairs.")
    for label, pair in (("Price Changes", price_pair), ("Supply Changes", supply_pair)):
        if pair and any(snapshot_id not in history_ids for snapshot_id in pair):
            diagnostics.append(f"{label} references snapshots outside the Rare Appearances history.")
        if len(pair) == 2 and len(history_ids) >= 2 and pair != history_ids[-2:]:
            diagnostics.append(f"{label} does not reference the latest pair in the supplied history.")
    return tuple(diagnostics)


def _price_pair(output: PriceChangesOutput) -> tuple[str, ...]:
    return tuple(value.snapshot_id for value in (output.previous_snapshot, output.latest_snapshot) if value is not None)


def _supply_pair(output: SupplyChangesOutput) -> tuple[str, ...]:
    return tuple(value.snapshot_id for value in (output.previous_snapshot, output.latest_snapshot) if value is not None)


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
        raise MarketplaceActivityDomainError(f"{name} must be non-empty and trimmed.")


def _count(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise MarketplaceActivityDomainError(f"{name} must not be negative.")


def _positive(value: object, name: str) -> None:
    _count(value, name)
    if value == 0:
        raise MarketplaceActivityDomainError(f"{name} must be positive.")


__all__ = ["MarketplaceActivityDomainError", "MarketplaceActivityModule", "MarketplaceActivityObservationReference", "MarketplaceActivityOutput", "MarketplaceActivityState", "MarketplaceActivitySummary", "ReleaseActivity"]
