"""Typed, immutable vocabulary for Collection Decisions values and filters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReviewFilterField(str, Enum):
    PRIORITY = "priority"
    DECISION = "decision"


class ReviewFilterChoiceKind(str, Enum):
    ALL = "all"
    CANONICAL = "canonical"
    RETAINED = "retained"


@dataclass(frozen=True)
class ReviewFilterChoice:
    """One display choice with a separate exact repository query value."""

    field: ReviewFilterField
    kind: ReviewFilterChoiceKind
    label: str
    query_value: str | None

    def __post_init__(self) -> None:
        if type(self.field) is not ReviewFilterField:
            raise TypeError("field must be a ReviewFilterField.")
        if type(self.kind) is not ReviewFilterChoiceKind:
            raise TypeError("kind must be a ReviewFilterChoiceKind.")
        if type(self.label) is not str or not self.label:
            raise ValueError("label must be a non-empty string.")
        if self.kind is ReviewFilterChoiceKind.ALL:
            if self.query_value is not None:
                raise ValueError("All must not have a query value.")
        elif type(self.query_value) is not str:
            raise TypeError("A value choice must have a string query value.")


CANONICAL_DECISIONS = (
    "Review",
    "Keep",
    "List for sale",
    "Maybe",
    "Ignore",
)

CANONICAL_PRIORITIES = (
    "High-priority review",
    "Worth reviewing",
    "Possible candidate",
    "Low priority",
    "Not scored",
)


def validate_writable_decision(value: object) -> str:
    """Return a canonical decision or reject an unsupported write."""

    if type(value) is not str:
        raise TypeError("decision must be a string.")
    if not value or value.strip() != value:
        raise ValueError("decision must be non-empty and trimmed.")
    if value not in CANONICAL_DECISIONS:
        raise ValueError("decision must be a canonical writable value.")
    return value


def review_filter_choices(
    field: ReviewFilterField,
    stored_values: tuple[str, ...],
) -> tuple[ReviewFilterChoice, ...]:
    """Build canonical choices followed by exact retained compatibility values."""

    if type(field) is not ReviewFilterField:
        raise TypeError("field must be a ReviewFilterField.")
    if type(stored_values) is not tuple:
        raise TypeError("stored_values must be a tuple.")
    canonical = (
        CANONICAL_DECISIONS
        if field is ReviewFilterField.DECISION
        else CANONICAL_PRIORITIES
    )
    for value in stored_values:
        if type(value) is not str:
            raise TypeError("stored filter values must be strings.")
    retained = tuple(
        sorted(
            (value for value in set(stored_values) if value not in canonical),
            key=lambda value: (value.casefold(), value),
        )
    )
    return (
        ReviewFilterChoice(field, ReviewFilterChoiceKind.ALL, "All", None),
        *(
            ReviewFilterChoice(
                field,
                ReviewFilterChoiceKind.CANONICAL,
                value,
                value,
            )
            for value in canonical
        ),
        *(
            ReviewFilterChoice(
                field,
                ReviewFilterChoiceKind.RETAINED,
                f"Retained: {value}",
                value,
            )
            for value in retained
        ),
    )
