"""Deterministic factual price comparison over two supplied snapshots."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import re
from types import MappingProxyType
from typing import Any

from dip.intelligence import IntelligenceContext, IntelligenceResult, IntelligenceStatus

from .models import (
    MarketplaceDataStatus,
    MarketplaceDiagnostic,
    MarketplaceMoney,
    MarketplaceReleaseObservation,
    MarketplaceSnapshot,
)


_CURRENCY = re.compile(r"^[A-Z]{3}$")
_STABLE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]*$")
_PROCESSABLE_STATUSES = {
    MarketplaceDataStatus.COMPLETE,
    MarketplaceDataStatus.PARTIAL,
    MarketplaceDataStatus.EMPTY,
}


class PriceChangesDomainError(ValueError):
    """Raised when Price Changes values contradict the defined contract."""


class PriceChangesComparisonState(str, Enum):
    """Domain outcome of attempting one supplied snapshot comparison."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT_HISTORY = "insufficient_history"
    INSUFFICIENT_DATA = "insufficient_data"
    FAILED = "failed"


class ListingPriceChangeKind(str, Enum):
    """Factual listing-price classifications emitted as detail records."""

    INCREASED = "increased"
    DECREASED = "decreased"
    NEWLY_OBSERVED = "newly_observed"
    NO_LONGER_OBSERVED = "no_longer_observed"
    INCOMPARABLE = "incomparable"


class ReleasePriceChangeKind(str, Enum):
    """Factual release-price classifications emitted as detail records."""

    INCREASED = "increased"
    DECREASED = "decreased"
    NEWLY_AVAILABLE = "newly_available"
    NO_LONGER_AVAILABLE = "no_longer_available"
    INCOMPARABLE = "incomparable"


class ReleasePriceMetric(str, Enum):
    """Canonical supplied release-level monetary facts in comparison order."""

    LOWEST_PRICE = "lowest_price"
    HIGHEST_PRICE = "highest_price"


@dataclass(frozen=True)
class MarketplaceSnapshotComparisonInput:
    """Already-selected Marketplace snapshots supplied to Price Changes.

    Pair-specific source, source-version, and strict chronological compatibility
    is enforced by both Price and Supply calculators. A later
    ``previous_snapshot`` is malformed input and is rejected here as well.
    """

    previous_snapshot: MarketplaceSnapshot | None = None
    latest_snapshot: MarketplaceSnapshot | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("previous_snapshot", self.previous_snapshot),
            ("latest_snapshot", self.latest_snapshot),
        ):
            if value is not None and type(value) is not MarketplaceSnapshot:
                raise TypeError(f"{name} must be a MarketplaceSnapshot or None.")
        if self.previous_snapshot is not None and self.latest_snapshot is None:
            raise PriceChangesDomainError(
                "A previous snapshot cannot be supplied without a latest snapshot."
            )
        if self.previous_snapshot is None or self.latest_snapshot is None:
            return
        if self.previous_snapshot.snapshot_id == self.latest_snapshot.snapshot_id:
            raise PriceChangesDomainError(
                "Previous and latest snapshot IDs must differ."
            )
        if _utc(self.previous_snapshot.captured_at) > _utc(
            self.latest_snapshot.captured_at
        ):
            raise PriceChangesDomainError(
                "Previous snapshot capture time must not follow the latest snapshot."
            )


@dataclass(frozen=True)
class PriceChangesSnapshotReference:
    """History-ready identity and provenance for one compared snapshot."""

    snapshot_id: str
    captured_at: datetime
    source: str
    status: MarketplaceDataStatus
    source_version: str | None = None

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot_id")
        _aware_datetime(self.captured_at, "captured_at")
        _stable_identifier(self.source, "source")
        if type(self.status) is not MarketplaceDataStatus:
            raise TypeError("status must be a MarketplaceDataStatus.")
        if self.source_version is not None:
            _text(self.source_version, "source_version")


@dataclass(frozen=True)
class PriceChangeDelta:
    """An exact signed ``latest - previous`` monetary delta."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if type(self.amount) is not Decimal:
            raise TypeError("amount must be a Decimal.")
        if not self.amount.is_finite():
            raise PriceChangesDomainError("amount must be finite.")
        if not isinstance(self.currency, str):
            raise TypeError("currency must be a string.")
        if _CURRENCY.fullmatch(self.currency) is None:
            raise PriceChangesDomainError(
                "currency must be an uppercase three-letter code."
            )


@dataclass(frozen=True)
class ListingPriceChange:
    """One changed or incomparable listing identity between two snapshots."""

    listing_id: str
    release_id: int
    change_kind: ListingPriceChangeKind
    previous_price: MarketplaceMoney | None
    latest_price: MarketplaceMoney | None
    delta: PriceChangeDelta | None
    previous_observed_at: datetime | None
    latest_observed_at: datetime | None
    previous_snapshot_id: str
    latest_snapshot_id: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.listing_id, "listing_id")
        _positive_integer(self.release_id, "release_id")
        if type(self.change_kind) is not ListingPriceChangeKind:
            raise TypeError("change_kind must be a ListingPriceChangeKind.")
        _optional_money(self.previous_price, "previous_price")
        _optional_money(self.latest_price, "latest_price")
        if self.delta is not None and type(self.delta) is not PriceChangeDelta:
            raise TypeError("delta must be a PriceChangeDelta or None.")
        _optional_aware_datetime(
            self.previous_observed_at,
            "previous_observed_at",
        )
        _optional_aware_datetime(self.latest_observed_at, "latest_observed_at")
        _different_snapshot_ids(
            self.previous_snapshot_id,
            self.latest_snapshot_id,
        )
        evidence = _string_tuple(self.evidence, "evidence")
        if not evidence:
            raise PriceChangesDomainError("Listing price changes require evidence.")
        object.__setattr__(self, "evidence", evidence)
        self._validate_classification()

    @property
    def relevant_observed_at(self) -> datetime:
        """Return the timestamp used by the canonical detail ordering."""

        value = (
            self.previous_observed_at
            if self.change_kind is ListingPriceChangeKind.NO_LONGER_OBSERVED
            else self.latest_observed_at
        )
        if value is None:  # protected by classification validation
            raise PriceChangesDomainError(
                "Listing price change lacks its relevant observation time."
            )
        return value

    def _validate_classification(self) -> None:
        if self.change_kind is ListingPriceChangeKind.NEWLY_OBSERVED:
            if (
                self.previous_price is not None
                or self.previous_observed_at is not None
                or self.latest_price is None
                or self.latest_observed_at is None
                or self.delta is not None
            ):
                raise PriceChangesDomainError(
                    "A newly observed listing requires only latest price evidence."
                )
            return
        if self.change_kind is ListingPriceChangeKind.NO_LONGER_OBSERVED:
            if (
                self.previous_price is None
                or self.previous_observed_at is None
                or self.latest_price is not None
                or self.latest_observed_at is not None
                or self.delta is not None
            ):
                raise PriceChangesDomainError(
                    "A no-longer-observed listing requires only previous price evidence."
                )
            return

        if (
            self.previous_price is None
            or self.latest_price is None
            or self.previous_observed_at is None
            or self.latest_observed_at is None
        ):
            raise PriceChangesDomainError(
                "Continuing listing changes require previous and latest evidence."
            )
        if self.change_kind is ListingPriceChangeKind.INCOMPARABLE:
            if self.delta is not None:
                raise PriceChangesDomainError(
                    "An incomparable listing cannot contain a calculated delta."
                )
            if self.previous_price.currency == self.latest_price.currency:
                raise PriceChangesDomainError(
                    "An incomparable listing requires differing price currencies."
                )
            return
        _validate_comparable_delta(
            self.previous_price,
            self.latest_price,
            self.delta,
            increased=self.change_kind is ListingPriceChangeKind.INCREASED,
        )


@dataclass(frozen=True)
class ReleasePriceChange:
    """One changed or incomparable supplied release-level monetary fact."""

    release_id: int
    metric: ReleasePriceMetric
    change_kind: ReleasePriceChangeKind
    previous_value: MarketplaceMoney | None
    latest_value: MarketplaceMoney | None
    delta: PriceChangeDelta | None
    previous_snapshot_id: str
    latest_snapshot_id: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive_integer(self.release_id, "release_id")
        if type(self.metric) is not ReleasePriceMetric:
            raise TypeError("metric must be a ReleasePriceMetric.")
        if type(self.change_kind) is not ReleasePriceChangeKind:
            raise TypeError("change_kind must be a ReleasePriceChangeKind.")
        _optional_money(self.previous_value, "previous_value")
        _optional_money(self.latest_value, "latest_value")
        if self.delta is not None and type(self.delta) is not PriceChangeDelta:
            raise TypeError("delta must be a PriceChangeDelta or None.")
        _different_snapshot_ids(
            self.previous_snapshot_id,
            self.latest_snapshot_id,
        )
        evidence = _string_tuple(self.evidence, "evidence")
        if not evidence:
            raise PriceChangesDomainError("Release price changes require evidence.")
        object.__setattr__(self, "evidence", evidence)
        self._validate_classification()

    def _validate_classification(self) -> None:
        if self.change_kind is ReleasePriceChangeKind.NEWLY_AVAILABLE:
            if (
                self.previous_value is not None
                or self.latest_value is None
                or self.delta is not None
            ):
                raise PriceChangesDomainError(
                    "A newly available release price requires only a latest value."
                )
            return
        if self.change_kind is ReleasePriceChangeKind.NO_LONGER_AVAILABLE:
            if (
                self.previous_value is None
                or self.latest_value is not None
                or self.delta is not None
            ):
                raise PriceChangesDomainError(
                    "A no-longer-available release price requires only a previous value."
                )
            return
        if self.change_kind is ReleasePriceChangeKind.INCOMPARABLE:
            if self.delta is not None:
                raise PriceChangesDomainError(
                    "An incomparable release price cannot contain a calculated delta."
                )
            if (
                self.previous_value is not None
                and self.latest_value is not None
                and self.previous_value.currency == self.latest_value.currency
            ):
                raise PriceChangesDomainError(
                    "An incomparable release price requires differing currencies."
                )
            return
        if self.previous_value is None or self.latest_value is None:
            raise PriceChangesDomainError(
                "Continuing release price changes require previous and latest values."
            )
        _validate_comparable_delta(
            self.previous_value,
            self.latest_value,
            self.delta,
            increased=self.change_kind is ReleasePriceChangeKind.INCREASED,
        )


@dataclass(frozen=True)
class PriceChangesSummary:
    """Explicit accountable counts for emitted and omitted classifications."""

    listing_increased_count: int = 0
    listing_decreased_count: int = 0
    listing_unchanged_count: int = 0
    listing_newly_observed_count: int = 0
    listing_no_longer_observed_count: int = 0
    listing_incomparable_count: int = 0
    release_increased_count: int = 0
    release_decreased_count: int = 0
    release_unchanged_count: int = 0
    release_newly_available_count: int = 0
    release_no_longer_available_count: int = 0
    release_incomparable_count: int = 0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            _non_negative_integer(getattr(self, name), name)

    @property
    def listing_change_count(self) -> int:
        return (
            self.listing_increased_count
            + self.listing_decreased_count
            + self.listing_newly_observed_count
            + self.listing_no_longer_observed_count
            + self.listing_incomparable_count
        )

    @property
    def release_change_count(self) -> int:
        return (
            self.release_increased_count
            + self.release_decreased_count
            + self.release_newly_available_count
            + self.release_no_longer_available_count
            + self.release_incomparable_count
        )

    @property
    def unchanged_count(self) -> int:
        return self.listing_unchanged_count + self.release_unchanged_count

    @property
    def incomparable_count(self) -> int:
        return self.listing_incomparable_count + self.release_incomparable_count

    @property
    def detected_change_count(self) -> int:
        return self.listing_change_count + self.release_change_count

    @property
    def assessed_price_count(self) -> int:
        """Return changed, incomparable, and unchanged supported price facts."""

        return self.detected_change_count + self.unchanged_count

    @property
    def comparable_price_count(self) -> int:
        """Return only facts for which an exact comparison was possible."""

        return (
            self.listing_increased_count
            + self.listing_decreased_count
            + self.listing_unchanged_count
            + self.listing_newly_observed_count
            + self.listing_no_longer_observed_count
            + self.release_increased_count
            + self.release_decreased_count
            + self.release_unchanged_count
            + self.release_newly_available_count
            + self.release_no_longer_available_count
        )


@dataclass(frozen=True)
class PriceChangesOutput:
    """Typed, history-ready Price Changes result payload."""

    previous_snapshot: PriceChangesSnapshotReference | None
    latest_snapshot: PriceChangesSnapshotReference | None
    source: str | None
    comparison_state: PriceChangesComparisonState
    summary: PriceChangesSummary = field(default_factory=PriceChangesSummary)
    listing_changes: tuple[ListingPriceChange, ...] = ()
    release_changes: tuple[ReleasePriceChange, ...] = ()
    diagnostics: tuple[MarketplaceDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("previous_snapshot", self.previous_snapshot),
            ("latest_snapshot", self.latest_snapshot),
        ):
            if value is not None and type(value) is not PriceChangesSnapshotReference:
                raise TypeError(
                    f"{name} must be a PriceChangesSnapshotReference or None."
                )
        if self.source is not None:
            _text(self.source, "source")
        if type(self.comparison_state) is not PriceChangesComparisonState:
            raise TypeError(
                "comparison_state must be a PriceChangesComparisonState."
            )
        if type(self.summary) is not PriceChangesSummary:
            raise TypeError("summary must be a PriceChangesSummary.")
        listing_changes = _listing_change_tuple(self.listing_changes)
        release_changes = _release_change_tuple(self.release_changes)
        diagnostics = _typed_tuple(
            self.diagnostics,
            MarketplaceDiagnostic,
            "diagnostics",
        )
        object.__setattr__(self, "listing_changes", listing_changes)
        object.__setattr__(self, "release_changes", release_changes)
        object.__setattr__(self, "diagnostics", diagnostics)
        references = tuple(
            value
            for value in (self.previous_snapshot, self.latest_snapshot)
            if value is not None
        )
        if any(
            value.status
            in {
                MarketplaceDataStatus.PARTIAL,
                MarketplaceDataStatus.UNAVAILABLE,
                MarketplaceDataStatus.FAILED,
            }
            for value in references
        ) and not diagnostics:
            raise PriceChangesDomainError(
                "Incomplete or unusable snapshot context requires source diagnostics."
            )
        self._validate_context()
        self._validate_summary(listing_changes, release_changes)

    def _validate_context(self) -> None:
        has_successful_values = bool(
            self.listing_changes
            or self.release_changes
            or self.summary.detected_change_count
            or self.summary.unchanged_count
        )
        if self.comparison_state is PriceChangesComparisonState.INSUFFICIENT_HISTORY:
            if self.previous_snapshot is not None or has_successful_values:
                raise PriceChangesDomainError(
                    "Insufficient history cannot contain a previous comparison or results."
                )
            expected_source = (
                None if self.latest_snapshot is None else self.latest_snapshot.source
            )
            if self.source != expected_source:
                raise PriceChangesDomainError(
                    "Insufficient-history source must match its latest snapshot."
                )
            return

        if self.previous_snapshot is None or self.latest_snapshot is None:
            raise PriceChangesDomainError(
                "This comparison state requires both snapshot contexts."
            )
        if self.previous_snapshot.snapshot_id == self.latest_snapshot.snapshot_id:
            raise PriceChangesDomainError("Compared snapshot IDs must differ.")
        same_source = self.previous_snapshot.source == self.latest_snapshot.source
        expected_source = self.previous_snapshot.source if same_source else None
        if self.source != expected_source:
            raise PriceChangesDomainError(
                "Comparison source must match both snapshot contexts."
            )

        if self.comparison_state in {
            PriceChangesComparisonState.INSUFFICIENT_DATA,
            PriceChangesComparisonState.FAILED,
        }:
            if self.comparison_state is PriceChangesComparisonState.FAILED and has_successful_values:
                raise PriceChangesDomainError(
                    "An unsuccessful comparison cannot contain successful output."
                )
            if (
                self.comparison_state is PriceChangesComparisonState.INSUFFICIENT_DATA
                and self.summary.comparable_price_count != 0
            ):
                raise PriceChangesDomainError(
                    "Insufficient data cannot contain comparable price facts."
                )
            has_failed_input = (
                self.previous_snapshot.status is MarketplaceDataStatus.FAILED
                or self.latest_snapshot.status is MarketplaceDataStatus.FAILED
            )
            if self.comparison_state is PriceChangesComparisonState.FAILED:
                if not has_failed_input:
                    raise PriceChangesDomainError(
                        "A failed comparison requires a failed input snapshot."
                    )
                return
            has_unavailable_input = (
                self.previous_snapshot.status is MarketplaceDataStatus.UNAVAILABLE
                or self.latest_snapshot.status is MarketplaceDataStatus.UNAVAILABLE
            )
            invalid_time_order = _utc(
                self.previous_snapshot.captured_at
            ) >= _utc(self.latest_snapshot.captured_at)
            lacks_supported_price_evidence = (
                same_source
                and not invalid_time_order
                and self.previous_snapshot.status in _PROCESSABLE_STATUSES
                and self.latest_snapshot.status in _PROCESSABLE_STATUSES
                and not (
                    self.previous_snapshot.status is MarketplaceDataStatus.EMPTY
                    and self.latest_snapshot.status is MarketplaceDataStatus.EMPTY
                )
                and self.summary.comparable_price_count == 0
            )
            if has_failed_input or not (
                has_unavailable_input
                or not same_source
                or invalid_time_order
                or lacks_supported_price_evidence
            ):
                raise PriceChangesDomainError(
                    "Insufficient data requires unavailable, differently sourced, "
                    "analytically unordered, or unsupported-price snapshots."
                )
            return

        if not same_source:
            raise PriceChangesDomainError(
                "A successful comparison requires matching snapshot sources."
            )
        if _utc(self.previous_snapshot.captured_at) >= _utc(
            self.latest_snapshot.captured_at
        ):
            raise PriceChangesDomainError(
                "A successful comparison requires a strictly earlier previous snapshot."
            )
        if self.previous_snapshot.status not in _PROCESSABLE_STATUSES or (
            self.latest_snapshot.status not in _PROCESSABLE_STATUSES
        ):
            raise PriceChangesDomainError(
                "A successful comparison requires processable snapshot statuses."
            )
        for value in (*self.listing_changes, *self.release_changes):
            if (
                value.previous_snapshot_id != self.previous_snapshot.snapshot_id
                or value.latest_snapshot_id != self.latest_snapshot.snapshot_id
            ):
                raise PriceChangesDomainError(
                    "Change snapshot IDs must match the output comparison context."
                )
        partial_reason = (
            self.previous_snapshot.status is MarketplaceDataStatus.PARTIAL
            or self.latest_snapshot.status is MarketplaceDataStatus.PARTIAL
            or self.summary.incomparable_count > 0
        )
        if partial_reason != (
            self.comparison_state is PriceChangesComparisonState.PARTIAL
        ):
            raise PriceChangesDomainError(
                "Comparison state must reflect partial or incomparable evidence."
            )

    def _validate_summary(
        self,
        listing_changes: tuple[ListingPriceChange, ...],
        release_changes: tuple[ReleasePriceChange, ...],
    ) -> None:
        listing_counts = Counter(value.change_kind for value in listing_changes)
        release_counts = Counter(value.change_kind for value in release_changes)
        expected = {
            "listing_increased_count": listing_counts[
                ListingPriceChangeKind.INCREASED
            ],
            "listing_decreased_count": listing_counts[
                ListingPriceChangeKind.DECREASED
            ],
            "listing_newly_observed_count": listing_counts[
                ListingPriceChangeKind.NEWLY_OBSERVED
            ],
            "listing_no_longer_observed_count": listing_counts[
                ListingPriceChangeKind.NO_LONGER_OBSERVED
            ],
            "listing_incomparable_count": listing_counts[
                ListingPriceChangeKind.INCOMPARABLE
            ],
            "release_increased_count": release_counts[
                ReleasePriceChangeKind.INCREASED
            ],
            "release_decreased_count": release_counts[
                ReleasePriceChangeKind.DECREASED
            ],
            "release_newly_available_count": release_counts[
                ReleasePriceChangeKind.NEWLY_AVAILABLE
            ],
            "release_no_longer_available_count": release_counts[
                ReleasePriceChangeKind.NO_LONGER_AVAILABLE
            ],
            "release_incomparable_count": release_counts[
                ReleasePriceChangeKind.INCOMPARABLE
            ],
        }
        for name, value in expected.items():
            if getattr(self.summary, name) != value:
                raise PriceChangesDomainError(
                    f"{name} does not match the detailed change records."
                )


class PriceChangesModule:
    """Compare exactly the supplied immutable Marketplace snapshot pair."""

    module_id = "price_changes"
    module_version = "2.0"

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult:
        """Return factual price differences without querying or using time."""

        if type(context) is not IntelligenceContext:
            raise TypeError("context must be an IntelligenceContext.")
        comparison = context.marketplace_comparison
        if comparison is None:
            return self._insufficient_history(None)
        if type(comparison) is not MarketplaceSnapshotComparisonInput:
            raise TypeError(
                "marketplace_comparison must be a "
                "MarketplaceSnapshotComparisonInput or None."
            )
        return self.calculate_pair(comparison)

    def calculate_pair(
        self,
        comparison: MarketplaceSnapshotComparisonInput,
    ) -> IntelligenceResult:
        """Apply the authoritative release-level lowest-price contract."""

        return self._calculate_pair(comparison, include_listing_prices=False)

    def calculate_listing_pair(
        self,
        comparison: MarketplaceSnapshotComparisonInput,
    ) -> IntelligenceResult:
        """Delegate to the distinctly identified historical listing capability."""

        return ListingPriceChangesModule().calculate_pair(comparison)

    def _calculate_pair(
        self,
        comparison: MarketplaceSnapshotComparisonInput,
        *,
        include_listing_prices: bool,
        result_module_id: str = "price_changes",
        result_module_version: str = "2.0",
    ) -> IntelligenceResult:
        """Calculate from an already-selected pair without querying History."""

        if type(comparison) is not MarketplaceSnapshotComparisonInput:
            raise TypeError("comparison must be a MarketplaceSnapshotComparisonInput.")
        previous = comparison.previous_snapshot
        latest = comparison.latest_snapshot
        if previous is None or latest is None:
            return self._insufficient_history(
                latest,
                module_id=result_module_id,
                module_version=result_module_version,
            )

        _validate_pair(previous, latest)

        previous_reference = _snapshot_reference(previous)
        latest_reference = _snapshot_reference(latest)
        source_diagnostics = _source_diagnostics(previous, latest)
        diagnostics = _source_diagnostic_texts(previous, latest)

        if (
            previous.status is MarketplaceDataStatus.FAILED
            or latest.status is MarketplaceDataStatus.FAILED
        ):
            output = PriceChangesOutput(
                previous_reference,
                latest_reference,
                previous.source if previous.source == latest.source else None,
                PriceChangesComparisonState.FAILED,
                diagnostics=source_diagnostics,
            )
            return self._result(
                IntelligenceStatus.FAILED,
                "Price Changes could not compare a failed Marketplace snapshot.",
                output,
                diagnostics=(
                    *diagnostics,
                    "A supplied Marketplace snapshot has failed status.",
                ),
                module_id=result_module_id,
                module_version=result_module_version,
            )
        if (
            previous.status is MarketplaceDataStatus.UNAVAILABLE
            or latest.status is MarketplaceDataStatus.UNAVAILABLE
        ):
            output = PriceChangesOutput(
                previous_reference,
                latest_reference,
                previous.source if previous.source == latest.source else None,
                PriceChangesComparisonState.INSUFFICIENT_DATA,
                diagnostics=source_diagnostics,
            )
            return self._result(
                IntelligenceStatus.SKIPPED,
                "Price Changes requires two available Marketplace snapshots.",
                output,
                diagnostics=(
                    *diagnostics,
                    "A supplied Marketplace snapshot is unavailable.",
                ),
                module_id=result_module_id,
                module_version=result_module_version,
            )
        if include_listing_prices:
            listing_changes, listing_counts = _compare_listings(previous, latest)
            release_changes, release_counts = _compare_releases(previous, latest)
            comparison_fact_diagnostics = ()
        else:
            listing_changes, listing_counts = (), _empty_listing_counts()
            release_changes, release_counts, comparison_fact_diagnostics = _compare_release_lowest_prices(previous, latest)
        safe_output_diagnostics = (*source_diagnostics, *comparison_fact_diagnostics)
        summary = PriceChangesSummary(**listing_counts, **release_counts)
        assessed = summary.assessed_price_count if include_listing_prices else summary.comparable_price_count
        if assessed == 0 and not (
            previous.status is MarketplaceDataStatus.EMPTY
            and latest.status is MarketplaceDataStatus.EMPTY
        ):
            output = PriceChangesOutput(
                previous_reference,
                latest_reference,
                previous.source,
                PriceChangesComparisonState.INSUFFICIENT_DATA,
                summary,
                listing_changes,
                release_changes,
                diagnostics=safe_output_diagnostics,
            )
            return self._result(
                IntelligenceStatus.SKIPPED,
                "Price Changes found no supported price evidence to compare.",
                output,
                diagnostics=(*diagnostics, *(f"{value.code}: {value.message}" for value in comparison_fact_diagnostics), *(
                    ("No comparable listing or release-price evidence was supplied.",)
                    if include_listing_prices
                    else ("No comparable release-level lowest-price evidence was supplied.",)
                )),
                module_id=result_module_id,
                module_version=result_module_version,
            )
        partial = (
            previous.status is MarketplaceDataStatus.PARTIAL
            or latest.status is MarketplaceDataStatus.PARTIAL
            or summary.incomparable_count > 0
        )
        comparison_state = (
            PriceChangesComparisonState.PARTIAL
            if partial
            else PriceChangesComparisonState.COMPLETE
        )
        output = PriceChangesOutput(
            previous_reference,
            latest_reference,
            previous.source,
            comparison_state,
            summary,
            listing_changes,
            release_changes,
            safe_output_diagnostics,
        )
        comparison_diagnostics = [*diagnostics, *(f"{value.code}: {value.message}" for value in comparison_fact_diagnostics)]
        for change in listing_changes:
            if change.change_kind is ListingPriceChangeKind.INCOMPARABLE:
                comparison_diagnostics.append(
                    f"Listing {change.listing_id} for release {change.release_id} "
                    "uses different currencies across the snapshots."
                )
        if summary.detected_change_count == 0:
            result_summary = (
                "No listing or supplied release-price changes were detected between the two snapshots."
                if include_listing_prices
                else "No observed release-level lowest-price changes were detected between the selected snapshots."
            )
        else:
            result_summary = (
                f"Detected {summary.listing_change_count} listing price-change record{'s' if summary.listing_change_count != 1 else ''} and {summary.release_change_count} supplied release-price change record{'s' if summary.release_change_count != 1 else ''}."
                if include_listing_prices
                else f"Detected {summary.release_change_count} observed release-level lowest-price change record{'s' if summary.release_change_count != 1 else ''}."
            )
        return self._result(
            IntelligenceStatus.COMPLETED,
            result_summary,
            output,
            evidence=tuple(
                evidence
                for value in (*listing_changes, *release_changes)
                for evidence in value.evidence
            ),
            diagnostics=tuple(comparison_diagnostics),
            module_id=result_module_id,
            module_version=result_module_version,
        )

    def _insufficient_history(
        self,
        latest: MarketplaceSnapshot | None,
        *,
        module_id: str = "price_changes",
        module_version: str = "2.0",
    ) -> IntelligenceResult:
        output = PriceChangesOutput(
            None,
            None if latest is None else _snapshot_reference(latest),
            None if latest is None else latest.source,
            PriceChangesComparisonState.INSUFFICIENT_HISTORY,
            diagnostics=() if latest is None else _snapshot_diagnostics(latest),
        )
        diagnostics = (
            ("No Marketplace snapshots were supplied.",)
            if latest is None
            else (
                *_diagnostic_texts("latest", latest),
                "Only one Marketplace snapshot was supplied.",
            )
        )
        return self._result(
            IntelligenceStatus.SKIPPED,
            "Price Changes requires two historical Marketplace snapshots.",
            output,
            diagnostics=diagnostics,
            module_id=module_id,
            module_version=module_version,
        )

    def _result(
        self,
        status: IntelligenceStatus,
        summary: str,
        output: PriceChangesOutput,
        *,
        evidence: tuple[str, ...] = (),
        diagnostics: tuple[str, ...] = (),
        module_id: str = "price_changes",
        module_version: str = "2.0",
    ) -> IntelligenceResult:
        return IntelligenceResult(
            module_id=module_id,
            module_version=module_version,
            status=status,
            summary=summary,
            metrics=MappingProxyType({"output": output}),
            evidence=evidence,
            diagnostics=diagnostics,
        )


class ListingPriceChangesModule:
    """Non-production listing/highest-price capability with distinct identity."""

    module_id = "listing_price_changes"
    module_version = "1.0"

    def calculate_pair(
        self,
        comparison: MarketplaceSnapshotComparisonInput,
    ) -> IntelligenceResult:
        return PriceChangesModule()._calculate_pair(
            comparison,
            include_listing_prices=True,
            result_module_id=self.module_id,
            result_module_version=self.module_version,
        )


def _compare_listings(
    previous: MarketplaceSnapshot,
    latest: MarketplaceSnapshot,
) -> tuple[tuple[ListingPriceChange, ...], dict[str, int]]:
    previous_by_identity = {
        (value.release_id, value.listing_id): value
        for value in previous.listing_observations
    }
    latest_by_identity = {
        (value.release_id, value.listing_id): value
        for value in latest.listing_observations
    }
    counts = {
        "listing_increased_count": 0,
        "listing_decreased_count": 0,
        "listing_unchanged_count": 0,
        "listing_newly_observed_count": 0,
        "listing_no_longer_observed_count": 0,
        "listing_incomparable_count": 0,
    }
    changes: list[ListingPriceChange] = []
    for release_id, listing_id in sorted(
        previous_by_identity.keys() | latest_by_identity.keys()
    ):
        prior = previous_by_identity.get((release_id, listing_id))
        current = latest_by_identity.get((release_id, listing_id))
        if prior is None:
            counts["listing_newly_observed_count"] += 1
            changes.append(
                ListingPriceChange(
                    listing_id,
                    release_id,
                    ListingPriceChangeKind.NEWLY_OBSERVED,
                    None,
                    current.price,
                    None,
                    None,
                    current.observed_at,
                    previous.snapshot_id,
                    latest.snapshot_id,
                    (
                        "Listing identity was observed in the latest snapshot but not "
                        "in the supplied previous snapshot.",
                    ),
                )
            )
            continue
        if current is None:
            counts["listing_no_longer_observed_count"] += 1
            changes.append(
                ListingPriceChange(
                    listing_id,
                    release_id,
                    ListingPriceChangeKind.NO_LONGER_OBSERVED,
                    prior.price,
                    None,
                    None,
                    prior.observed_at,
                    None,
                    previous.snapshot_id,
                    latest.snapshot_id,
                    (
                        "Listing identity was observed in the previous snapshot but not "
                        "in the supplied latest snapshot.",
                    ),
                )
            )
            continue
        if prior.price.currency != current.price.currency:
            counts["listing_incomparable_count"] += 1
            changes.append(
                ListingPriceChange(
                    listing_id,
                    release_id,
                    ListingPriceChangeKind.INCOMPARABLE,
                    prior.price,
                    current.price,
                    None,
                    prior.observed_at,
                    current.observed_at,
                    previous.snapshot_id,
                    latest.snapshot_id,
                    (
                        "Continuing listing prices use different currencies; no delta "
                        "was calculated.",
                    ),
                )
            )
            continue
        amount_delta = _exact_decimal_delta(
            current.price.amount,
            prior.price.amount,
        )
        if amount_delta == 0:
            counts["listing_unchanged_count"] += 1
            continue
        increased = amount_delta > 0
        kind = (
            ListingPriceChangeKind.INCREASED
            if increased
            else ListingPriceChangeKind.DECREASED
        )
        counts[
            "listing_increased_count" if increased else "listing_decreased_count"
        ] += 1
        changes.append(
            ListingPriceChange(
                listing_id,
                release_id,
                kind,
                prior.price,
                current.price,
                PriceChangeDelta(amount_delta, current.price.currency),
                prior.observed_at,
                current.observed_at,
                previous.snapshot_id,
                latest.snapshot_id,
                (
                    "Continuing listing price was higher in the latest snapshot."
                    if increased
                    else "Continuing listing price was lower in the latest snapshot.",
                ),
            )
        )
    return _ordered_listing_changes(tuple(changes)), counts


def _empty_listing_counts() -> dict[str, int]:
    return {
        "listing_increased_count": 0,
        "listing_decreased_count": 0,
        "listing_unchanged_count": 0,
        "listing_newly_observed_count": 0,
        "listing_no_longer_observed_count": 0,
        "listing_incomparable_count": 0,
    }


def _compare_release_lowest_prices(
    previous: MarketplaceSnapshot,
    latest: MarketplaceSnapshot,
) -> tuple[tuple[ReleasePriceChange, ...], dict[str, int], tuple[MarketplaceDiagnostic, ...]]:
    """Compare only current-scope lowest prices; absence is incomparable."""

    old = {value.release_id: value for value in previous.release_observations}
    new = {value.release_id: value for value in latest.release_observations}
    counts = {
        "release_increased_count": 0,
        "release_decreased_count": 0,
        "release_unchanged_count": 0,
        "release_newly_available_count": 0,
        "release_no_longer_available_count": 0,
        "release_incomparable_count": 0,
    }
    changes: list[ReleasePriceChange] = []
    diagnostics: list[MarketplaceDiagnostic] = []
    usable = {MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.PARTIAL}
    for release_id in sorted(old.keys() | new.keys()):
        before, after = old.get(release_id), new.get(release_id)
        previous_value = (
            before.lowest_price if before is not None and before.status in usable else None
        )
        latest_value = (
            after.lowest_price if after is not None and after.status in usable else None
        )
        if (
            previous_value is None
            or latest_value is None
            or previous_value.currency != latest_value.currency
        ):
            code, copy = _lowest_price_incomparable_reason(before, after)
            diagnostics.append(MarketplaceDiagnostic(code, copy))
            counts["release_incomparable_count"] += 1
            changes.append(
                ReleasePriceChange(
                    release_id,
                    ReleasePriceMetric.LOWEST_PRICE,
                    ReleasePriceChangeKind.INCOMPARABLE,
                    previous_value,
                    latest_value,
                    None,
                    previous.snapshot_id,
                    latest.snapshot_id,
                    (copy,),
                )
            )
            continue
        delta = _exact_decimal_delta(latest_value.amount, previous_value.amount)
        if delta == 0:
            counts["release_unchanged_count"] += 1
            continue
        kind = (
            ReleasePriceChangeKind.INCREASED
            if delta > 0
            else ReleasePriceChangeKind.DECREASED
        )
        counts[
            "release_increased_count" if delta > 0 else "release_decreased_count"
        ] += 1
        changes.append(
            ReleasePriceChange(
                release_id,
                ReleasePriceMetric.LOWEST_PRICE,
                kind,
                previous_value,
                latest_value,
                PriceChangeDelta(delta, latest_value.currency),
                previous.snapshot_id,
                latest.snapshot_id,
                ("Observed lowest price changed between the selected snapshots.",),
            )
        )
    return tuple(changes), counts, tuple(diagnostics)


def _lowest_price_incomparable_reason(
    previous: MarketplaceReleaseObservation | None,
    latest: MarketplaceReleaseObservation | None,
) -> tuple[str, str]:
    usable = {MarketplaceDataStatus.COMPLETE, MarketplaceDataStatus.PARTIAL}
    if previous is None:
        return "missing_baseline_release", "The baseline release observation is missing."
    if latest is None:
        return "missing_current_release", "The current release observation is missing."
    if previous.status not in usable:
        return "unusable_baseline_observation", "The baseline release observation is not usable for comparison."
    if latest.status not in usable:
        return "unusable_current_observation", "The current release observation is not usable for comparison."
    if previous.lowest_price is None:
        return "missing_baseline_lowest_price", "The baseline lowest-price observation is missing."
    if latest.lowest_price is None:
        return "missing_current_lowest_price", "The current lowest-price observation is missing."
    if previous.lowest_price.currency != latest.lowest_price.currency:
        return "lowest_price_currency_mismatch", "The observed lowest prices use different currencies."
    return "marketplace_evidence_incomplete", "Marketplace evidence was incomplete for this observation."


def _compare_releases(
    previous: MarketplaceSnapshot,
    latest: MarketplaceSnapshot,
) -> tuple[tuple[ReleasePriceChange, ...], dict[str, int]]:
    previous_by_id = {
        value.release_id: value for value in previous.release_observations
    }
    latest_by_id = {value.release_id: value for value in latest.release_observations}
    counts = {
        "release_increased_count": 0,
        "release_decreased_count": 0,
        "release_unchanged_count": 0,
        "release_newly_available_count": 0,
        "release_no_longer_available_count": 0,
        "release_incomparable_count": 0,
    }
    changes: list[ReleasePriceChange] = []
    for release_id in sorted(previous_by_id.keys() | latest_by_id.keys()):
        prior = previous_by_id.get(release_id)
        current = latest_by_id.get(release_id)
        for metric in ReleasePriceMetric:
            previous_value = None if prior is None else getattr(prior, metric.value)
            latest_value = None if current is None else getattr(current, metric.value)
            if previous_value is None and latest_value is None:
                continue
            if previous_value is None:
                counts["release_newly_available_count"] += 1
                changes.append(
                    ReleasePriceChange(
                        release_id,
                        metric,
                        ReleasePriceChangeKind.NEWLY_AVAILABLE,
                        None,
                        latest_value,
                        None,
                        previous.snapshot_id,
                        latest.snapshot_id,
                        (
                            f"Release {metric.value} was supplied only in the latest "
                            "snapshot.",
                        ),
                    )
                )
                continue
            if latest_value is None:
                counts["release_no_longer_available_count"] += 1
                changes.append(
                    ReleasePriceChange(
                        release_id,
                        metric,
                        ReleasePriceChangeKind.NO_LONGER_AVAILABLE,
                        previous_value,
                        None,
                        None,
                        previous.snapshot_id,
                        latest.snapshot_id,
                        (
                            f"Release {metric.value} was supplied only in the previous "
                            "snapshot.",
                        ),
                    )
                )
                continue
            if previous_value.currency != latest_value.currency:
                counts["release_incomparable_count"] += 1
                changes.append(
                    ReleasePriceChange(
                        release_id,
                        metric,
                        ReleasePriceChangeKind.INCOMPARABLE,
                        previous_value,
                        latest_value,
                        None,
                        previous.snapshot_id,
                        latest.snapshot_id,
                        (
                            f"Release {metric.value} values use different currencies; "
                            "no delta was calculated.",
                        ),
                    )
                )
                continue
            amount_delta = _exact_decimal_delta(
                latest_value.amount,
                previous_value.amount,
            )
            if amount_delta == 0:
                counts["release_unchanged_count"] += 1
                continue
            increased = amount_delta > 0
            kind = (
                ReleasePriceChangeKind.INCREASED
                if increased
                else ReleasePriceChangeKind.DECREASED
            )
            counts[
                "release_increased_count" if increased else "release_decreased_count"
            ] += 1
            changes.append(
                ReleasePriceChange(
                    release_id,
                    metric,
                    kind,
                    previous_value,
                    latest_value,
                    PriceChangeDelta(amount_delta, latest_value.currency),
                    previous.snapshot_id,
                    latest.snapshot_id,
                    (
                        f"Release {metric.value} was higher in the latest snapshot."
                        if increased
                        else f"Release {metric.value} was lower in the latest snapshot.",
                    ),
                )
            )
    return _ordered_release_changes(tuple(changes)), counts


def _snapshot_reference(snapshot: MarketplaceSnapshot) -> PriceChangesSnapshotReference:
    return PriceChangesSnapshotReference(
        snapshot.snapshot_id,
        snapshot.captured_at,
        snapshot.source,
        snapshot.status,
        snapshot.source_version,
    )


def _source_diagnostic_texts(
    previous: MarketplaceSnapshot,
    latest: MarketplaceSnapshot,
) -> tuple[str, ...]:
    return (
        *_diagnostic_texts("previous", previous),
        *_diagnostic_texts("latest", latest),
    )


def _source_diagnostics(
    previous: MarketplaceSnapshot,
    latest: MarketplaceSnapshot,
) -> tuple[MarketplaceDiagnostic, ...]:
    return (*_snapshot_diagnostics(previous), *_snapshot_diagnostics(latest))


def _snapshot_diagnostics(
    snapshot: MarketplaceSnapshot,
) -> tuple[MarketplaceDiagnostic, ...]:
    return (
        *(_safe_diagnostic(value) for value in snapshot.diagnostics),
        *(
            _safe_diagnostic(diagnostic)
            for release in snapshot.release_observations
            for diagnostic in release.diagnostics
        ),
    )


def _diagnostic_texts(
    role: str,
    snapshot: MarketplaceSnapshot,
) -> tuple[str, ...]:
    snapshot_diagnostics = tuple(
        f"{role} snapshot {snapshot.snapshot_id}: {_diagnostic_text(value)}"
        for value in snapshot.diagnostics
    )
    release_diagnostics = tuple(
        f"{role} snapshot {snapshot.snapshot_id}, release {release.release_id}: "
        f"{_diagnostic_text(value)}"
        for release in snapshot.release_observations
        for value in release.diagnostics
    )
    return (*snapshot_diagnostics, *release_diagnostics)


def _diagnostic_text(value: MarketplaceDiagnostic) -> str:
    safe = _safe_diagnostic(value)
    return f"{safe.severity.value}:{safe.code}: {safe.message}"


def _safe_diagnostic(value: MarketplaceDiagnostic) -> MarketplaceDiagnostic:
    """Copy only structured identity and application-owned neutral text."""

    known = {"source_unavailable", "partial_observation", "missing_field"}
    code = value.code if value.code in known else "marketplace_evidence_incomplete"
    return MarketplaceDiagnostic(code, _safe_diagnostic_copy(code), value.severity)


def _safe_diagnostic_copy(code: str) -> str:
    return {
        "source_unavailable": "Marketplace evidence was unavailable for this observation.",
        "partial_observation": "Marketplace evidence was incomplete for this observation.",
        "missing_field": "Marketplace evidence was incomplete for this observation.",
    }.get(code, "Marketplace evidence was incomplete for this observation.")


def _listing_change_tuple(values: Any) -> tuple[ListingPriceChange, ...]:
    result = _typed_tuple(values, ListingPriceChange, "listing_changes")
    identities = tuple((value.release_id, value.listing_id) for value in result)
    if len(set(identities)) != len(identities):
        raise PriceChangesDomainError(
            "Listing change identities must be unique."
        )
    if result != _ordered_listing_changes(result):
        raise PriceChangesDomainError(
            "Listing changes must use canonical Price Changes order."
        )
    return result


def _release_change_tuple(values: Any) -> tuple[ReleasePriceChange, ...]:
    result = _typed_tuple(values, ReleasePriceChange, "release_changes")
    identities = tuple((value.release_id, value.metric) for value in result)
    if len(set(identities)) != len(identities):
        raise PriceChangesDomainError(
            "Release metric change identities must be unique."
        )
    if result != _ordered_release_changes(result):
        raise PriceChangesDomainError(
            "Release changes must use canonical Price Changes order."
        )
    return result


def _ordered_listing_changes(
    values: tuple[ListingPriceChange, ...],
) -> tuple[ListingPriceChange, ...]:
    kind_order = {value: index for index, value in enumerate(ListingPriceChangeKind)}
    by_identity = sorted(
        values,
        key=lambda value: (
            value.release_id,
            value.listing_id,
            kind_order[value.change_kind],
        ),
    )
    return tuple(
        sorted(
            by_identity,
            key=lambda value: _utc(value.relevant_observed_at),
            reverse=True,
        )
    )


def _ordered_release_changes(
    values: tuple[ReleasePriceChange, ...],
) -> tuple[ReleasePriceChange, ...]:
    metric_order = {value: index for index, value in enumerate(ReleasePriceMetric)}
    return tuple(
        sorted(
            values,
            key=lambda value: (value.release_id, metric_order[value.metric]),
        )
    )


def _validate_comparable_delta(
    previous: MarketplaceMoney,
    latest: MarketplaceMoney,
    delta: PriceChangeDelta | None,
    *,
    increased: bool,
) -> None:
    if previous.currency != latest.currency:
        raise PriceChangesDomainError(
            "Comparable prices must use the same currency."
        )
    if delta is None:
        raise PriceChangesDomainError("A changed comparable price requires a delta.")
    if delta.currency != latest.currency:
        raise PriceChangesDomainError("Delta currency must match compared prices.")
    expected = _exact_decimal_delta(latest.amount, previous.amount)
    if delta.amount != expected:
        raise PriceChangesDomainError("Delta must equal latest minus previous.")
    if increased and delta.amount <= 0:
        raise PriceChangesDomainError(
            "An increased price requires a positive signed delta."
        )
    if not increased and delta.amount >= 0:
        raise PriceChangesDomainError(
            "A decreased price requires a negative signed delta."
        )


def _exact_decimal_delta(latest: Decimal, previous: Decimal) -> Decimal:
    """Subtract without allowing the ambient Decimal context to round."""

    latest_tuple = latest.as_tuple()
    previous_tuple = previous.as_tuple()
    latest_exponent = int(latest_tuple.exponent)
    previous_exponent = int(previous_tuple.exponent)
    if previous.is_zero() and previous_exponent >= 0:
        return latest
    if latest.is_zero() and latest_exponent >= 0:
        return previous.copy_negate()
    common_exponent = min(latest_exponent, previous_exponent)
    latest_coefficient = _decimal_coefficient(latest) * 10 ** (
        latest_exponent - common_exponent
    )
    previous_coefficient = _decimal_coefficient(previous) * 10 ** (
        previous_exponent - common_exponent
    )
    difference = latest_coefficient - previous_coefficient
    digits = Decimal(abs(difference)).as_tuple().digits
    return Decimal((1 if difference < 0 else 0, digits, common_exponent))


def _decimal_coefficient(value: Decimal) -> int:
    result = 0
    parts = value.as_tuple()
    for digit in parts.digits:
        result = result * 10 + digit
    return -result if parts.sign else result


def _different_snapshot_ids(previous: Any, latest: Any) -> None:
    _text(previous, "previous_snapshot_id")
    _text(latest, "latest_snapshot_id")
    if previous == latest:
        raise PriceChangesDomainError("Previous and latest snapshot IDs must differ.")


def _optional_money(value: Any, name: str) -> None:
    if value is not None and type(value) is not MarketplaceMoney:
        raise TypeError(f"{name} must be a MarketplaceMoney or None.")


def _typed_tuple(values: Any, value_type: type[Any], name: str) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection.")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    if any(type(value) is not value_type for value in result):
        raise TypeError(f"{name} contains an unsupported value.")
    return result


def _string_tuple(values: Any, name: str) -> tuple[str, ...]:
    result = _typed_tuple(values, str, name)
    for value in result:
        _text(value, f"{name} item")
    return result


def _optional_aware_datetime(value: Any, name: str) -> None:
    if value is not None:
        _aware_datetime(value, name)


def _aware_datetime(value: Any, name: str) -> None:
    if type(value) is not datetime:
        raise TypeError(f"{name} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise PriceChangesDomainError(f"{name} must be timezone-aware.")


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _validate_pair(previous: MarketplaceSnapshot, latest: MarketplaceSnapshot) -> None:
    """Reject analytically incompatible pairs at the public calculation boundary."""

    if previous.source != latest.source:
        raise PriceChangesDomainError("Price Changes requires matching snapshot sources.")
    if previous.source_version != latest.source_version:
        raise PriceChangesDomainError("Price Changes requires matching snapshot source versions.")
    if _utc(previous.captured_at) >= _utc(latest.captured_at):
        raise PriceChangesDomainError("Price Changes requires a strictly earlier baseline snapshot.")


def _positive_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise PriceChangesDomainError(f"{name} must be positive.")


def _non_negative_integer(value: Any, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise PriceChangesDomainError(f"{name} must be non-negative.")


def _text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise PriceChangesDomainError(f"{name} must be non-empty and trimmed.")


def _stable_identifier(value: Any, name: str) -> None:
    _text(value, name)
    if _STABLE_IDENTIFIER.fullmatch(value) is None:
        raise PriceChangesDomainError(
            f"{name} must use stable lowercase identifier syntax."
        )


__all__ = [
    "ListingPriceChange",
    "ListingPriceChangeKind",
    "ListingPriceChangesModule",
    "MarketplaceSnapshotComparisonInput",
    "PriceChangeDelta",
    "PriceChangesComparisonState",
    "PriceChangesDomainError",
    "PriceChangesModule",
    "PriceChangesOutput",
    "PriceChangesSnapshotReference",
    "PriceChangesSummary",
    "ReleasePriceChange",
    "ReleasePriceChangeKind",
    "ReleasePriceMetric",
]
