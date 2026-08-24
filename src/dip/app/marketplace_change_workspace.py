"""One read-only Marketplace Change workspace over a shared history window."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from dip.app.current_release_metadata import (
    CurrentReleaseMetadata,
    CurrentReleaseMetadataRepository,
)
from dip.app.marketplace_history import MarketplaceHistoryConsistencyError
from dip.experience.price_changes import (
    PriceChangesDetailViewModelBuilder,
    PriceChangesDetailState,
    PriceChangesDetailViewModel,
    PriceChangesSnapshotViewModel,
    ReleasePriceChangeViewModel,
)
from dip.experience.results_presentation import ComparisonContextViewModel
from dip.experience.supply_changes import (
    SupplyChangesDetailViewModelBuilder,
    ReleaseSupplyChangeViewModel,
    SupplyChangesDetailState,
    SupplyChangesDetailViewModel,
    SupplyChangesSnapshotViewModel,
)
from dip.marketplace_history import MarketplaceHistoryIntegrityError
from dip.marketplace_intelligence import (
    MarketplaceDataStatus,
    MarketplaceSnapshot,
    MarketplaceSnapshotComparisonInput,
    PriceChangesModule,
    PriceChangesComparisonState,
    ReleasePriceChangeKind,
    ReleasePriceMetric,
    SupplyChangeKind,
    SupplyChangesModule,
    SupplyChangesComparisonState,
)


INCOMPATIBLE_HISTORY_COPY = (
    "Newer historical snapshots were skipped because they were not compatible "
    "with the latest snapshot’s source contract."
)
NO_COMPATIBLE_BASELINE_COPY = (
    "No earlier compatible Marketplace snapshot is available for comparison."
)
METADATA_COPY = (
    "Artist and title are current catalogue metadata provided for identification. "
    "They were not captured with the Marketplace snapshots."
)
METADATA_FAILURE_COPY = (
    "Current catalogue metadata could not be loaded. Marketplace Changes remain "
    "available and are identified by release ID."
)
PARTIAL_COPY = (
    "Some releases could not be compared because Marketplace evidence was incomplete."
)
INELIGIBLE_COPY = "Failed or unavailable Marketplace snapshots were skipped."
EQUAL_TIME_COPY = "Equal-time Marketplace snapshots were skipped because they cannot establish direction."
SOURCE_MISMATCH_COPY = "Marketplace snapshots from a different source were skipped."
SOURCE_VERSION_MISMATCH_COPY = "Marketplace snapshots with a different source version were skipped."


class MarketplaceChangeWorkspaceState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


class MarketplaceChangeOutcomeReason(str, Enum):
    NO_ELIGIBLE_CURRENT = "no_eligible_current"
    NO_COMPATIBLE_BASELINE = "no_compatible_baseline"
    NO_COMPARABLE_FACTS = "no_comparable_facts"
    HISTORY_UNREADABLE = "history_unreadable"
    HISTORY_INVALID = "history_invalid"
    COMPARISON_FAILED = "comparison_failed"


class MarketplaceSnapshotExclusionReason(str, Enum):
    INELIGIBLE_STATUS = "ineligible_status"
    EQUAL_CAPTURE_INSTANT = "equal_capture_instant"
    SOURCE_MISMATCH = "source_mismatch"
    SOURCE_VERSION_MISMATCH = "source_version_mismatch"


@dataclass(frozen=True)
class MarketplaceSnapshotProvenance:
    snapshot_id: str
    captured_at: datetime
    source: str
    source_version: str | None
    status: MarketplaceDataStatus

    def __post_init__(self) -> None:
        _snapshot_identity(self.snapshot_id, self.captured_at, self.source, self.source_version, self.status)


@dataclass(frozen=True)
class ExcludedMarketplaceSnapshot:
    snapshot_id: str
    captured_at: datetime
    source: str
    source_version: str | None
    status: MarketplaceDataStatus
    reason: MarketplaceSnapshotExclusionReason

    def __post_init__(self) -> None:
        _snapshot_identity(self.snapshot_id, self.captured_at, self.source, self.source_version, self.status)
        if type(self.reason) is not MarketplaceSnapshotExclusionReason:
            raise TypeError("reason must be a MarketplaceSnapshotExclusionReason.")


@dataclass(frozen=True)
class MarketplaceSnapshotWindow:
    current: MarketplaceSnapshotProvenance | None
    baseline: MarketplaceSnapshotProvenance | None
    excluded: tuple[ExcludedMarketplaceSnapshot, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (("current", self.current), ("baseline", self.baseline)):
            if value is not None and type(value) is not MarketplaceSnapshotProvenance:
                raise TypeError(f"{name} must be MarketplaceSnapshotProvenance or None.")
        if self.baseline is not None and self.current is None:
            raise ValueError("A baseline cannot exist without a current snapshot.")
        if self.baseline and self.current:
            if _utc(self.baseline.captured_at) >= _utc(self.current.captured_at):
                raise ValueError("Baseline must be strictly earlier than current.")
            if self.baseline.source != self.current.source or self.baseline.source_version != self.current.source_version:
                raise ValueError("Selected snapshots must share source and source version.")
        object.__setattr__(self, "excluded", _typed_tuple(self.excluded, ExcludedMarketplaceSnapshot, "excluded"))
        object.__setattr__(self, "diagnostics", _strings(self.diagnostics, "diagnostics"))


@dataclass(frozen=True)
class MarketplaceChangeWorkspace:
    state: MarketplaceChangeWorkspaceState
    window: MarketplaceSnapshotWindow
    price_changes: PriceChangesDetailViewModel
    supply_changes: SupplyChangesDetailViewModel
    warnings: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    outcome_reason: MarketplaceChangeOutcomeReason | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not MarketplaceChangeWorkspaceState:
            raise TypeError("state must be a MarketplaceChangeWorkspaceState.")
        if type(self.window) is not MarketplaceSnapshotWindow:
            raise TypeError("window must be a MarketplaceSnapshotWindow.")
        if type(self.price_changes) is not PriceChangesDetailViewModel or type(self.supply_changes) is not SupplyChangesDetailViewModel:
            raise TypeError("Workspace results must be typed Price and Supply details.")
        object.__setattr__(self, "warnings", _strings(self.warnings, "warnings"))
        object.__setattr__(self, "diagnostics", _strings(self.diagnostics, "diagnostics"))
        if self.outcome_reason is not None and type(self.outcome_reason) is not MarketplaceChangeOutcomeReason:
            raise TypeError("outcome_reason must be MarketplaceChangeOutcomeReason or None.")
        if self.state is MarketplaceChangeWorkspaceState.ERROR:
            if self.price_changes.state is not PriceChangesDetailState.ERROR or self.supply_changes.state is not SupplyChangesDetailState.ERROR:
                raise ValueError("An error workspace cannot contain successful results.")
            if self.window.current is not None or self.window.baseline is not None:
                raise ValueError("An error workspace cannot retain a selected snapshot pair.")
            if self.price_changes.release_changes or self.price_changes.listing_changes or self.supply_changes.changes:
                raise ValueError("An error workspace cannot contain successful details.")
            if any((self.price_changes.release_change_count, self.price_changes.listing_change_count, self.price_changes.unchanged_count, self.price_changes.incomparable_count, self.supply_changes.change_count, self.supply_changes.unchanged_count, self.supply_changes.incomparable_count)):
                raise ValueError("An error workspace requires zero comparison counts.")
            if self.outcome_reason not in {MarketplaceChangeOutcomeReason.HISTORY_UNREADABLE, MarketplaceChangeOutcomeReason.HISTORY_INVALID, MarketplaceChangeOutcomeReason.COMPARISON_FAILED}:
                raise ValueError("An error workspace requires a safe failure outcome reason.")
            if self.price_changes.comparison_context is not None or self.supply_changes.comparison_context is not None:
                raise ValueError("A workspace without a selected pair cannot retain presentation context.")
            return
        if self.state is MarketplaceChangeWorkspaceState.INSUFFICIENT_HISTORY:
            if self.outcome_reason not in {MarketplaceChangeOutcomeReason.NO_ELIGIBLE_CURRENT, MarketplaceChangeOutcomeReason.NO_COMPATIBLE_BASELINE}:
                raise ValueError("Insufficient history requires a typed history outcome reason.")
        elif self.state is MarketplaceChangeWorkspaceState.INSUFFICIENT_DATA:
            if self.outcome_reason is not MarketplaceChangeOutcomeReason.NO_COMPARABLE_FACTS:
                raise ValueError("Insufficient data requires the no-comparable-facts reason.")
        elif self.outcome_reason is not None:
            raise ValueError("Successful workspaces cannot retain an outcome reason.")
        if self.window.baseline is None and self.state is not MarketplaceChangeWorkspaceState.INSUFFICIENT_HISTORY:
            raise ValueError("A workspace without a baseline is insufficient history.")
        if self.window.baseline and self.window.current:
            expected = (self.window.baseline.snapshot_id, self.window.current.snapshot_id)
            for detail in (self.price_changes, self.supply_changes):
                actual = (detail.previous_snapshot.snapshot_id, detail.latest_snapshot.snapshot_id) if detail.previous_snapshot and detail.latest_snapshot else None
                if actual != expected:
                    raise ValueError("Price and Supply must use the selected snapshot pair.")
            if self.price_changes.comparison_context != self.supply_changes.comparison_context:
                raise ValueError("Price and Supply must share one presentation context.")
            context = self.price_changes.comparison_context
            if context is None or not _context_matches_window(
                context,
                self.window.baseline,
                self.window.current,
            ):
                raise ValueError("Presentation context must match the selected snapshot window exactly.")
        elif self.price_changes.comparison_context is not None or self.supply_changes.comparison_context is not None:
            raise ValueError("A workspace without a selected pair cannot retain presentation context.")
        if self.state is not _workspace_state(self.price_changes, self.supply_changes):
            raise ValueError("Workspace state must be derived from its child results.")


class _MarketplaceHistoryQueries(Protocol):
    def all_snapshots(self) -> tuple[MarketplaceSnapshot, ...]: ...


class MarketplaceSnapshotWindowSelector:
    """Select one exact-source/version pair from canonical chronological history."""

    _ELIGIBLE = frozenset(
        (MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.PARTIAL, MarketplaceDataStatus.EMPTY)
    )

    def select(self, history: tuple[MarketplaceSnapshot, ...]) -> MarketplaceSnapshotWindow:
        """Return detached safe provenance; raw snapshots are never retained."""

        return _select_marketplace_snapshot_pair(history).window

    def _select(self, history: tuple[MarketplaceSnapshot, ...]) -> "_SelectedMarketplaceSnapshotPair":
        """Internal calculation boundary retaining raw values only transiently."""

        return _select_marketplace_snapshot_pair(history)


@dataclass(frozen=True)
class _SelectedMarketplaceSnapshotPair:
    current: MarketplaceSnapshot | None = field(repr=False)
    baseline: MarketplaceSnapshot | None = field(repr=False)
    window: MarketplaceSnapshotWindow


def _select_marketplace_snapshot_pair(
    history: tuple[MarketplaceSnapshot, ...],
) -> _SelectedMarketplaceSnapshotPair:
        if type(history) is not tuple:
            raise TypeError("history must be a tuple.")
        if any(type(snapshot) is not MarketplaceSnapshot for snapshot in history):
            raise TypeError("history must contain MarketplaceSnapshot values.")
        eligible = MarketplaceSnapshotWindowSelector._ELIGIBLE
        current = next(
            (snapshot for snapshot in reversed(history) if snapshot.status in eligible),
            None,
        )
        if current is None:
            return _SelectedMarketplaceSnapshotPair(
                None, None, MarketplaceSnapshotWindow(None, None)
            )
        current_time = _utc(current.captured_at)
        current_index = history.index(current)
        excluded: list[ExcludedMarketplaceSnapshot] = [
            _excluded(snapshot, MarketplaceSnapshotExclusionReason.INELIGIBLE_STATUS)
            for snapshot in history[current_index + 1 :]
            if snapshot.status not in eligible
        ]
        baseline = None
        for candidate in reversed(history[:current_index]):
            if candidate.status not in eligible:
                excluded.append(_excluded(candidate, MarketplaceSnapshotExclusionReason.INELIGIBLE_STATUS))
                continue
            if _utc(candidate.captured_at) == current_time:
                excluded.append(_excluded(candidate, MarketplaceSnapshotExclusionReason.EQUAL_CAPTURE_INSTANT))
                continue
            if candidate.source != current.source:
                excluded.append(_excluded(candidate, MarketplaceSnapshotExclusionReason.SOURCE_MISMATCH))
                continue
            if candidate.source_version != current.source_version:
                excluded.append(_excluded(candidate, MarketplaceSnapshotExclusionReason.SOURCE_VERSION_MISMATCH))
                continue
            baseline = candidate
            break
        copies = {MarketplaceSnapshotExclusionReason.INELIGIBLE_STATUS: INELIGIBLE_COPY, MarketplaceSnapshotExclusionReason.EQUAL_CAPTURE_INSTANT: EQUAL_TIME_COPY, MarketplaceSnapshotExclusionReason.SOURCE_MISMATCH: SOURCE_MISMATCH_COPY, MarketplaceSnapshotExclusionReason.SOURCE_VERSION_MISMATCH: SOURCE_VERSION_MISMATCH_COPY}
        diagnostics = tuple(copies[reason] for reason in copies if any(value.reason is reason for value in excluded))
        if baseline is None:
            diagnostics = (*diagnostics, NO_COMPATIBLE_BASELINE_COPY)
        window = MarketplaceSnapshotWindow(
            _provenance(current),
            None if baseline is None else _provenance(baseline),
            tuple(excluded),
            diagnostics,
        )
        return _SelectedMarketplaceSnapshotPair(
            current,
            baseline,
            window,
        )


class MarketplaceChangeWorkspaceService:
    """Build Price and Supply views with one History and at most one metadata query."""

    def __init__(
        self,
        history: _MarketplaceHistoryQueries,
        metadata: CurrentReleaseMetadataRepository,
        selector: MarketplaceSnapshotWindowSelector | None = None,
        *,
        price_calculator: object | None = None,
        supply_calculator: object | None = None,
        price_builder: object | None = None,
        supply_builder: object | None = None,
    ) -> None:
        self._history = history
        self._metadata = metadata
        self._selector = selector or MarketplaceSnapshotWindowSelector()
        self._price_calculator = price_calculator or PriceChangesModule()
        self._supply_calculator = supply_calculator or SupplyChangesModule()
        self._price_builder = price_builder or PriceChangesDetailViewModelBuilder()
        self._supply_builder = supply_builder or SupplyChangesDetailViewModelBuilder()

    def build(self) -> MarketplaceChangeWorkspace:
        try:
            history = self._history.all_snapshots()
        except MarketplaceHistoryIntegrityError as exc:
            return _error_workspace(MarketplaceChangeOutcomeReason.HISTORY_INVALID)
        except MarketplaceHistoryConsistencyError as exc:
            return _error_workspace(MarketplaceChangeOutcomeReason.HISTORY_INVALID)
        except Exception:
            return _error_workspace(MarketplaceChangeOutcomeReason.HISTORY_UNREADABLE)
        try:
            selected = self._selector._select(history)
            window = selected.window
            if selected.current is None or selected.baseline is None:
                return _insufficient_workspace(window)
            comparison = MarketplaceSnapshotComparisonInput(selected.baseline, selected.current)
            price_result = self._price_calculator.calculate_pair(comparison)
            supply_result = self._supply_calculator.calculate_pair(comparison)
            price = self._price_builder.build(price_result)
            supply = self._supply_builder.build(supply_result)
            price = _append_price_diagnostics(price, window.diagnostics)
            supply = _append_supply_diagnostics(supply, window.diagnostics)
            core_state = _workspace_state(price, supply)
            core_outcome = MarketplaceChangeOutcomeReason.NO_COMPARABLE_FACTS if core_state is MarketplaceChangeWorkspaceState.INSUFFICIENT_DATA else None
            MarketplaceChangeWorkspace(core_state, window, price, supply, diagnostics=window.diagnostics, outcome_reason=core_outcome)
        except Exception:
            return _error_workspace(MarketplaceChangeOutcomeReason.COMPARISON_FAILED)
        release_ids = tuple(sorted({
            *(value.release_id for value in price.release_changes),
            *(value.release_id for value in supply.changes),
        }))
        metadata_warning = False
        metadata_by_id: dict[int, CurrentReleaseMetadata] = {}
        if release_ids:
            try:
                values = tuple(self._metadata.metadata_for_release_ids(release_ids))
                identities = tuple(value.release_id for value in values)
                if identities != tuple(sorted(identities)) or len(set(identities)) != len(identities):
                    raise ValueError("Metadata identities must be unique and ordered.")
                if any(value not in release_ids for value in identities):
                    raise ValueError("Metadata returned an unexpected identity.")
                metadata_by_id = {value.release_id: value for value in values}
            except Exception:
                metadata_warning = True
                metadata_by_id = {}
        try:
            price = _enrich_price(price, metadata_by_id, metadata_warning)
            supply = _enrich_supply(supply, metadata_by_id, metadata_warning)
        except Exception:
            metadata_warning = True
            price = _enrich_price(price, {}, True)
            supply = _enrich_supply(supply, {}, True)
        state = _workspace_state(price, supply)
        outcome = MarketplaceChangeOutcomeReason.NO_COMPARABLE_FACTS if state is MarketplaceChangeWorkspaceState.INSUFFICIENT_DATA else None
        warnings = (METADATA_COPY,)
        if metadata_warning:
            warnings = (*warnings, METADATA_FAILURE_COPY)
        try:
            return MarketplaceChangeWorkspace(state, window, price, supply, warnings, window.diagnostics, outcome)
        except Exception:
            return _error_workspace(MarketplaceChangeOutcomeReason.COMPARISON_FAILED)


def _enrich_price(detail: PriceChangesDetailViewModel, metadata: dict[int, CurrentReleaseMetadata], failed: bool) -> PriceChangesDetailViewModel:
    return replace(detail, release_changes=tuple(_replace_price_label(value, metadata.get(value.release_id)) for value in detail.release_changes), diagnostics=(*detail.diagnostics, METADATA_COPY, *((METADATA_FAILURE_COPY,) if failed else ())))


def _enrich_supply(detail: SupplyChangesDetailViewModel, metadata: dict[int, CurrentReleaseMetadata], failed: bool) -> SupplyChangesDetailViewModel:
    return replace(detail, changes=tuple(_replace_supply_label(value, metadata.get(value.release_id)) for value in detail.changes), diagnostics=(*detail.diagnostics, METADATA_COPY, *((METADATA_FAILURE_COPY,) if failed else ())))


def _replace_price_label(value: ReleasePriceChangeViewModel, metadata: CurrentReleaseMetadata | None) -> ReleasePriceChangeViewModel:
    artist, title, label, uses = _label(value.release_id, metadata)
    return ReleasePriceChangeViewModel(**{**value.__dict__, "artist": artist, "title": title, "display_label": label, "uses_current_metadata": uses})


def _replace_supply_label(value: ReleaseSupplyChangeViewModel, metadata: CurrentReleaseMetadata | None) -> ReleaseSupplyChangeViewModel:
    artist, title, label, uses = _label(value.release_id, metadata)
    return ReleaseSupplyChangeViewModel(**{**value.__dict__, "artist": artist, "title": title, "display_label": label, "uses_current_metadata": uses})


def _label(release_id: int, metadata: CurrentReleaseMetadata | None) -> tuple[str | None, str | None, str, bool]:
    artist = None if metadata is None or not metadata.artist or not metadata.artist.strip() else metadata.artist.strip()
    title = None if metadata is None or not metadata.title or not metadata.title.strip() else metadata.title.strip()
    if artist and title:
        return artist, title, f"{artist} — {title}", True
    if artist:
        return artist, None, artist, True
    if title:
        return None, title, title, True
    return None, None, f"Release {release_id}", False


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _same_capture_value(left: datetime, right: datetime) -> bool:
    """Compare original aware timestamp representations without normalizing them."""

    return left.isoformat() == right.isoformat() and left.fold == right.fold


def _context_matches_window(
    context: ComparisonContextViewModel,
    baseline: MarketplaceSnapshotProvenance,
    current: MarketplaceSnapshotProvenance,
) -> bool:
    return (
        context.previous_snapshot_id == baseline.snapshot_id
        and _same_capture_value(context.previous_captured_at, baseline.captured_at)
        and context.latest_snapshot_id == current.snapshot_id
        and _same_capture_value(context.latest_captured_at, current.captured_at)
        and context.source == baseline.source
        and context.source == current.source
        and context.source_version == baseline.source_version
        and context.source_version == current.source_version
    )


def _provenance(snapshot: MarketplaceSnapshot) -> MarketplaceSnapshotProvenance:
    return MarketplaceSnapshotProvenance(snapshot.snapshot_id, snapshot.captured_at, snapshot.source, snapshot.source_version, snapshot.status)


def _excluded(snapshot: MarketplaceSnapshot, reason: MarketplaceSnapshotExclusionReason) -> ExcludedMarketplaceSnapshot:
    return ExcludedMarketplaceSnapshot(snapshot.snapshot_id, snapshot.captured_at, snapshot.source, snapshot.source_version, snapshot.status, reason)


def _price_snapshot(snapshot: MarketplaceSnapshot) -> PriceChangesSnapshotViewModel:
    return PriceChangesSnapshotViewModel(snapshot.snapshot_id, snapshot.captured_at, snapshot.source, snapshot.status, snapshot.source_version)


def _supply_snapshot(snapshot: MarketplaceSnapshot) -> SupplyChangesSnapshotViewModel:
    return SupplyChangesSnapshotViewModel(snapshot.snapshot_id, snapshot.captured_at, snapshot.source, snapshot.status, snapshot.source_version)


def _append_price_diagnostics(detail: PriceChangesDetailViewModel, values: tuple[str, ...]) -> PriceChangesDetailViewModel:
    return replace(detail, diagnostics=(*detail.diagnostics, *values))


def _append_supply_diagnostics(detail: SupplyChangesDetailViewModel, values: tuple[str, ...]) -> SupplyChangesDetailViewModel:
    return replace(detail, diagnostics=(*detail.diagnostics, *values))


def _workspace_state(price: PriceChangesDetailViewModel, supply: SupplyChangesDetailViewModel) -> MarketplaceChangeWorkspaceState:
    states = (price.state, supply.state)
    if PriceChangesDetailState.ERROR in states or SupplyChangesDetailState.ERROR in states:
        return MarketplaceChangeWorkspaceState.ERROR
    if PriceChangesDetailState.PARTIAL in states or SupplyChangesDetailState.PARTIAL in states:
        return MarketplaceChangeWorkspaceState.PARTIAL
    if states == (PriceChangesDetailState.EMPTY, SupplyChangesDetailState.EMPTY):
        return MarketplaceChangeWorkspaceState.EMPTY
    if states == (PriceChangesDetailState.INSUFFICIENT_DATA, SupplyChangesDetailState.INSUFFICIENT_DATA):
        return MarketplaceChangeWorkspaceState.INSUFFICIENT_DATA
    if states == (PriceChangesDetailState.INSUFFICIENT_HISTORY, SupplyChangesDetailState.INSUFFICIENT_HISTORY):
        return MarketplaceChangeWorkspaceState.INSUFFICIENT_HISTORY
    return MarketplaceChangeWorkspaceState.AVAILABLE


def _snapshot_identity(snapshot_id: object, captured_at: object, source: object, source_version: object, status: object) -> None:
    if not isinstance(snapshot_id, str) or not snapshot_id or snapshot_id.strip() != snapshot_id:
        raise ValueError("snapshot_id must be non-empty and trimmed.")
    if type(captured_at) is not datetime or captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware.")
    if not isinstance(source, str) or not source or source.strip() != source:
        raise ValueError("source must be non-empty and trimmed.")
    if source_version is not None and (not isinstance(source_version, str) or not source_version or source_version.strip() != source_version):
        raise ValueError("source_version must be non-empty and trimmed or None.")
    if type(status) is not MarketplaceDataStatus:
        raise TypeError("status must be a MarketplaceDataStatus.")


def _typed_tuple(values: object, expected: type, name: str) -> tuple:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be a tuple.")
    if any(type(value) is not expected for value in values):
        raise TypeError(f"{name} contains an invalid value.")
    return values


def _strings(values: object, name: str) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TypeError(f"{name} must be a tuple.")
    if any(not isinstance(value, str) or not value or value.strip() != value for value in values):
        raise ValueError(f"{name} must contain non-empty trimmed strings.")
    return values


def _insufficient_workspace(window: MarketplaceSnapshotWindow) -> MarketplaceChangeWorkspace:
    price = PriceChangesDetailViewModel(PriceChangesDetailState.INSUFFICIENT_HISTORY, "Price and Supply Changes require two eligible Marketplace snapshots.", PriceChangesComparisonState.INSUFFICIENT_HISTORY, latest_snapshot=None if window.current is None else _price_snapshot(window.current), source=None if window.current is None else window.current.source, listing_change_count=0, release_change_count=0, unchanged_count=0, incomparable_count=0, diagnostics=window.diagnostics)
    supply = SupplyChangesDetailViewModel(SupplyChangesDetailState.INSUFFICIENT_HISTORY, "Price and Supply Changes require two eligible Marketplace snapshots.", SupplyChangesComparisonState.INSUFFICIENT_HISTORY, latest_snapshot=None if window.current is None else _supply_snapshot(window.current), source=None if window.current is None else window.current.source, change_count=0, unchanged_count=0, incomparable_count=0, diagnostics=window.diagnostics)
    reason = MarketplaceChangeOutcomeReason.NO_ELIGIBLE_CURRENT if window.current is None else MarketplaceChangeOutcomeReason.NO_COMPATIBLE_BASELINE
    return MarketplaceChangeWorkspace(MarketplaceChangeWorkspaceState.INSUFFICIENT_HISTORY, window, price, supply, diagnostics=window.diagnostics, outcome_reason=reason)


def _error_workspace(reason: MarketplaceChangeOutcomeReason) -> MarketplaceChangeWorkspace:
    message = {
        MarketplaceChangeOutcomeReason.HISTORY_UNREADABLE: "Saved Marketplace history could not be read safely.",
        MarketplaceChangeOutcomeReason.HISTORY_INVALID: "Saved Marketplace history is invalid and could not be used safely.",
        MarketplaceChangeOutcomeReason.COMPARISON_FAILED: "Marketplace changes could not be loaded.",
    }[reason]
    window = MarketplaceSnapshotWindow(None, None, diagnostics=(message,))
    price = PriceChangesDetailViewModel(PriceChangesDetailState.ERROR, message, PriceChangesComparisonState.FAILED, listing_change_count=0, release_change_count=0, unchanged_count=0, incomparable_count=0, diagnostics=(message,))
    supply = SupplyChangesDetailViewModel(SupplyChangesDetailState.ERROR, message, SupplyChangesComparisonState.FAILED, change_count=0, unchanged_count=0, incomparable_count=0, diagnostics=(message,))
    return MarketplaceChangeWorkspace(MarketplaceChangeWorkspaceState.ERROR, window, price, supply, diagnostics=(message,), outcome_reason=reason)


__all__ = ["CurrentReleaseMetadata", "ExcludedMarketplaceSnapshot", "MarketplaceChangeOutcomeReason", "MarketplaceChangeWorkspace", "MarketplaceChangeWorkspaceService", "MarketplaceChangeWorkspaceState", "MarketplaceSnapshotExclusionReason", "MarketplaceSnapshotProvenance", "MarketplaceSnapshotWindow", "MarketplaceSnapshotWindowSelector"]
