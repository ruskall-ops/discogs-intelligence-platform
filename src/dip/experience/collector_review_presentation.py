"""Closed immutable presentation values for Collector Review desktop views."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from numbers import Real
from typing import Any

from dip.collector_review import HiddenGemObservation, HotNowObservation, WeekendReviewStatus


def _text(value: Any, name: str) -> None:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string.")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be non-empty and trimmed.")


class CollectionDecisionColumnId(str, Enum):
    ARTIST = "artist"
    TITLE = "title"
    PRICE = "price"
    WANTS = "wants"
    SUPPLY = "sale"
    OPPORTUNITY = "opportunity"
    SELL_WINDOW = "window"
    PRIORITY = "priority"
    DECISION = "decision"


class ColumnAnchor(str, Enum):
    LEFT = "w"
    RIGHT = "e"


class ReviewDetailSectionKind(str, Enum):
    CALCULATED = "calculated"
    MARKETPLACE_EVIDENCE = "marketplace_evidence"
    EVIDENCE_LIMITATIONS = "evidence_limitations"
    QUEUE_STATE = "queue_state"
    TECHNICAL_PROVENANCE = "technical_provenance"


class WarningProjectionState(str, Enum):
    """Closed semantic states for public evidence-warning projection."""

    EVIDENCE_LIMITED = "evidence_limited"
    SUPPRESSED = "suppressed"


class DisabledActionReason(str, Enum):
    NO_OBSERVATION = "Select an observation to see available workflow actions."
    OBSERVATION_SERVICE_UNAVAILABLE = "Queue actions are unavailable because the queue service is unavailable."
    NOT_QUEUED = "This observation is not currently in the Weekend Review Queue."
    RESOLVED_OBSERVATION = "This queue item is resolved; reopen it to continue review."
    ALREADY_QUEUED = "This observation is already in the Weekend Review Queue."
    NO_QUEUE_ITEM = "Select a queue item to enable workflow actions."
    QUEUE_SERVICE_UNAVAILABLE = "Queue actions are unavailable because the queue service is unavailable."
    RESOLVED_START_REVIEW = "Start Review is unavailable because this queue item is resolved."
    UNSAVED_NOTE = "Save or discard the unsaved note before leaving this queue item."
    QUEUE_ACTIONS_AVAILABLE = "Workflow actions apply to the selected queue item."


@dataclass(frozen=True)
class CollectionDecisionColumn:
    column_id: CollectionDecisionColumnId
    label: str
    width: int
    anchor: ColumnAnchor

    def __post_init__(self) -> None:
        if type(self.column_id) is not CollectionDecisionColumnId:
            raise TypeError("column_id must be a CollectionDecisionColumnId.")
        _text(self.label, "label")
        if type(self.width) is not int:
            raise TypeError("width must be a non-boolean integer.")
        if self.width <= 0:
            raise ValueError("width must be positive.")
        if type(self.anchor) is not ColumnAnchor:
            raise TypeError("anchor must be a ColumnAnchor.")


@dataclass(frozen=True)
class ReviewDetailSection:
    kind: ReviewDetailSectionKind
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.kind) is not ReviewDetailSectionKind:
            raise TypeError("kind must be a ReviewDetailSectionKind.")
        lines = tuple(self.lines)
        if not lines:
            raise ValueError("lines must not be empty.")
        for line in lines:
            _text(line, "line")
            if "\n" in line or "\r" in line:
                raise ValueError("detail lines must be single-line text.")
        object.__setattr__(self, "lines", lines)

    @property
    def title(self) -> str:
        return _SECTION_TITLES[self.kind]


_SECTION_TITLES = {
    ReviewDetailSectionKind.CALCULATED: "Calculated observation",
    ReviewDetailSectionKind.MARKETPLACE_EVIDENCE: "Marketplace evidence",
    ReviewDetailSectionKind.EVIDENCE_LIMITATIONS: "Evidence limitations / warnings",
    ReviewDetailSectionKind.QUEUE_STATE: "Weekend Review Queue state",
    ReviewDetailSectionKind.TECHNICAL_PROVENANCE: "Technical provenance",
}

COLLECTION_DECISION_COLUMNS = (
    CollectionDecisionColumn(CollectionDecisionColumnId.ARTIST, "Artist", 210, ColumnAnchor.LEFT),
    CollectionDecisionColumn(CollectionDecisionColumnId.TITLE, "Title", 310, ColumnAnchor.LEFT),
    CollectionDecisionColumn(CollectionDecisionColumnId.PRICE, "Lowest £", 95, ColumnAnchor.RIGHT),
    CollectionDecisionColumn(CollectionDecisionColumnId.WANTS, "Wants", 80, ColumnAnchor.RIGHT),
    CollectionDecisionColumn(CollectionDecisionColumnId.SUPPLY, "For Sale", 80, ColumnAnchor.RIGHT),
    CollectionDecisionColumn(CollectionDecisionColumnId.OPPORTUNITY, "Opportunity", 105, ColumnAnchor.RIGHT),
    CollectionDecisionColumn(CollectionDecisionColumnId.SELL_WINDOW, "Sell Window", 150, ColumnAnchor.LEFT),
    CollectionDecisionColumn(CollectionDecisionColumnId.PRIORITY, "Priority", 185, ColumnAnchor.LEFT),
    CollectionDecisionColumn(CollectionDecisionColumnId.DECISION, "Decision", 110, ColumnAnchor.LEFT),
)

_KNOWN_WARNING_COPY = {
    "hot_now_failed_run": "This stored score came from a Collector Run that did not complete.",
    "hot_now_provenance_unavailable": "Canonical provenance is unavailable for this stored score.",
    "hot_now_retained": "The latest evidence window did not provide usable evidence for this release.",
    "hot_now_score_stale": "Newer usable Marketplace evidence exists for this release.",
    "marketplace_evidence_partial": "The supplied Marketplace evidence is partial.",
    "hidden_gem_marketplace_provenance_unavailable": "Marketplace provenance is unavailable for this persisted result.",
    "hidden_gem_marketplace_evidence_unavailable": "Matching Marketplace evidence is unavailable for this persisted result.",
}
_GENERIC_LIMITATION = "Some supplied Marketplace evidence was incomplete."


def format_price(value: Any) -> str:
    if value is None:
        return "—"
    _numeric(value, "price")
    return f"{value:.2f}"


def format_score(value: Any) -> str:
    if value is None:
        return "—"
    _numeric(value, "score")
    return f"{value:.1f}"


def format_count(value: Any) -> str:
    if value is None:
        return "—"
    if type(value) is not int:
        raise TypeError("count must be a non-boolean integer or None.")
    return str(value)


def decision_row_values(row: Any) -> tuple[str, ...]:
    """Detach one repository row using field-authoritative formatting."""

    return (
        _optional_text(row["artist"]),
        _optional_text(row["title"]),
        format_price(row["lowest_price"]),
        format_count(row["wants"]),
        format_count(row["copies_for_sale"]),
        format_score(row["opportunity_score"]),
        _optional_text(row["sell_window"]),
        _optional_text(row["priority"]),
        _optional_text(row["decision"]),
    )


def public_warning_lines(
    state: WarningProjectionState,
    warnings: tuple[Any, ...],
) -> tuple[str, ...]:
    """Map typed warning identities to fixed public copy without raw messages."""

    if type(state) is not WarningProjectionState:
        raise TypeError("state must be a WarningProjectionState.")
    if type(warnings) is not tuple:
        raise TypeError("warnings must be a tuple.")
    if state is WarningProjectionState.SUPPRESSED:
        return ()
    lines: list[str] = []
    unknown = False
    for warning in warnings:
        code = getattr(warning, "code", None)
        fixed = _KNOWN_WARNING_COPY.get(code)
        if fixed is None:
            unknown = True
        elif fixed not in lines:
            lines.append(fixed)
    if unknown and _GENERIC_LIMITATION not in lines:
        lines.append(_GENERIC_LIMITATION)
    return tuple(f"• {line}" for line in lines)


def observation_detail_sections(observation: Any) -> tuple[ReviewDetailSection, ...]:
    """Build closed labelled sections from typed observation fields only."""

    calculated = [
        f"Current catalogue label: {observation.artist} — {observation.title}",
        f"Release ID: {observation.release_id}",
    ]
    if type(observation) is HotNowObservation:
        calculated.extend((
            f"Classification: {observation.sell_window}",
            f"Opportunity: {format_score(observation.opportunity_score)}",
            f"Momentum: {format_score(observation.momentum_score)}",
            f"Demand: {format_score(observation.demand_score)}",
            f"Liquidity: {format_score(observation.liquidity_score)}",
            f"Value: {format_score(observation.value_score)}",
            f"Explanation: {observation.explanation or 'No explanation supplied.'}",
        ))
        evidence = observation.evidence
    elif type(observation) is HiddenGemObservation:
        calculated.extend((
            f"Rank: {observation.rank}",
            f"Hidden Gem score: {format_score(observation.hidden_gem_score)}",
            *(f"Evidence statement: {value}" for value in observation.evidence),
        ))
        evidence = observation.marketplace_evidence
    else:
        raise TypeError("observation must be a supported typed observation.")

    sections = [ReviewDetailSection(ReviewDetailSectionKind.CALCULATED, tuple(calculated))]
    if evidence is not None:
        money = format_price(evidence.lowest_price)
        if evidence.lowest_price is not None and evidence.currency:
            money = f"{money} {evidence.currency}"
        sections.append(ReviewDetailSection(
            ReviewDetailSectionKind.MARKETPLACE_EVIDENCE,
            (
                f"Observed: {evidence.observed_at.isoformat()}",
                f"Wants: {format_count(evidence.wants)}",
                f"Copies for sale: {format_count(evidence.copies_for_sale)}",
                f"Lowest price: {money}",
            ),
        ))
    warning_lines = public_warning_lines(
        WarningProjectionState.EVIDENCE_LIMITED,
        observation.warnings,
    )
    if warning_lines:
        sections.append(ReviewDetailSection(ReviewDetailSectionKind.EVIDENCE_LIMITATIONS, warning_lines))
    membership = observation.queue_membership
    queue_state = "Not queued" if not membership.is_queued else "Resolved" if membership.status is WeekendReviewStatus.RESOLVED else "Queued"
    sections.append(ReviewDetailSection(ReviewDetailSectionKind.QUEUE_STATE, (f"State: {queue_state}",)))
    provenance = []
    intelligence_run_id = getattr(observation, "source_intelligence_run_id", None)
    marketplace_snapshot_id = getattr(observation, "source_marketplace_snapshot_id", None)
    if intelligence_run_id is not None:
        provenance.append(f"Intelligence run ID: {intelligence_run_id}")
    if marketplace_snapshot_id is not None:
        provenance.append(f"Marketplace snapshot ID: {marketplace_snapshot_id}")
    if provenance:
        sections.append(ReviewDetailSection(ReviewDetailSectionKind.TECHNICAL_PROVENANCE, tuple(provenance)))
    return tuple(sections)


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    if type(value) is not str:
        raise TypeError("textual facts must be strings or None.")
    return value


def _numeric(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (Decimal, Real)):
        raise TypeError(f"{name} must be a non-boolean numeric value or None.")


__all__ = [
    "COLLECTION_DECISION_COLUMNS", "CollectionDecisionColumn",
    "CollectionDecisionColumnId", "ColumnAnchor", "DisabledActionReason",
    "ReviewDetailSection", "ReviewDetailSectionKind", "decision_row_values",
    "format_count", "format_price", "format_score", "observation_detail_sections",
    "public_warning_lines", "WarningProjectionState",
]
