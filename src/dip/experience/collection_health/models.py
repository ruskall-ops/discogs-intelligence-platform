"""Immutable presentation models for the Collection Health experience."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any


class CollectionHealthDetailConsistencyError(ValueError):
    """Raised when Collection Health detail values contradict their state."""


class CollectionHealthDetailState(str, Enum):
    """Explicit states supported by Collection Health detail interfaces."""

    LOADING = "loading"
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class CollectionHealthComponentViewModel:
    """One component score already calculated by Collection Health."""

    component_id: str
    label: str
    score: float

    def __post_init__(self) -> None:
        _validate_text(self.component_id, "component_id")
        _validate_text(self.label, "label")
        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise TypeError("score must be a number.")
        score = float(self.score)
        if not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError("score must be finite and between 0 and 100.")
        object.__setattr__(self, "score", score)


@dataclass(frozen=True)
class CollectionHealthDetailViewModel:
    """Presentation-ready detail for one established Collection Health card."""

    state: CollectionHealthDetailState
    summary: str
    overall_score: float | None = None
    components: tuple[CollectionHealthComponentViewModel, ...] = ()
    strengths: tuple[str, ...] = ()
    improvement_opportunities: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    module_id: str = field(init=False, default="collection_health")
    title: str = field(init=False, default="Collection Health")

    def __post_init__(self) -> None:
        if type(self.state) is not CollectionHealthDetailState:
            raise TypeError("state must be a CollectionHealthDetailState.")
        _validate_text(self.summary, "summary")

        components = _freeze_components(self.components)
        strengths = _freeze_text(self.strengths, "strengths")
        opportunities = _freeze_text(
            self.improvement_opportunities,
            "improvement_opportunities",
        )
        evidence = _freeze_text(self.evidence, "evidence")
        diagnostics = _freeze_text(self.diagnostics, "diagnostics")
        score = _optional_score(self.overall_score)

        if self.state is CollectionHealthDetailState.LOADING and (
            score is not None
            or components
            or strengths
            or opportunities
            or evidence
            or diagnostics
        ):
            raise CollectionHealthDetailConsistencyError(
                "A loading Collection Health detail cannot contain result values."
            )
        if self.state is CollectionHealthDetailState.UNAVAILABLE and (
            score is not None or components or strengths or opportunities or evidence
        ):
            raise CollectionHealthDetailConsistencyError(
                "An unavailable Collection Health detail cannot contain result values."
            )
        if self.state is CollectionHealthDetailState.AVAILABLE and score is None:
            raise CollectionHealthDetailConsistencyError(
                "Available Collection Health detail requires an overall score."
            )

        object.__setattr__(self, "overall_score", score)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "strengths", strengths)
        object.__setattr__(self, "improvement_opportunities", opportunities)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "diagnostics", diagnostics)

    @classmethod
    def loading(cls) -> "CollectionHealthDetailViewModel":
        """Return the deterministic state shown before detail data is ready."""

        return cls(
            state=CollectionHealthDetailState.LOADING,
            summary="Collection Health detail is loading.",
        )


def _freeze_components(
    values: Any,
) -> tuple[CollectionHealthComponentViewModel, ...]:
    try:
        components = tuple(values)
    except TypeError as exc:
        raise TypeError("components must be a collection.") from exc
    if any(type(value) is not CollectionHealthComponentViewModel for value in components):
        raise TypeError(
            "components must contain CollectionHealthComponentViewModel values."
        )
    component_ids = tuple(component.component_id for component in components)
    if len(set(component_ids)) != len(component_ids):
        raise CollectionHealthDetailConsistencyError(
            "Collection Health component IDs must be unique."
        )
    return components


def _freeze_text(values: Any, name: str) -> tuple[str, ...]:
    if isinstance(values, str):
        raise TypeError(f"{name} must be a collection of strings.")
    try:
        items = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection of strings.") from exc
    for value in items:
        _validate_text(value, f"{name} item")
    return items


def _optional_score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("overall_score must be a number or None.")
    score = float(value)
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("overall_score must be finite and between 0 and 100.")
    return score


def _validate_text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string.")


__all__ = [
    "CollectionHealthComponentViewModel",
    "CollectionHealthDetailConsistencyError",
    "CollectionHealthDetailState",
    "CollectionHealthDetailViewModel",
]
