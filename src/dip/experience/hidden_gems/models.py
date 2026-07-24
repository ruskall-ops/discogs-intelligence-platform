"""Immutable presentation models for the Hidden Gems experience."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any


class HiddenGemsDetailConsistencyError(ValueError):
    """Raised when Hidden Gems detail values contradict their state."""


class HiddenGemsDetailState(str, Enum):
    """Explicit states supported by Hidden Gems detail interfaces."""

    LOADING = "loading"
    AVAILABLE = "available"
    PARTIAL = "partial"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class HiddenGemMetricViewModel:
    """One ordered metric value already produced by Hidden Gems."""

    metric_id: str
    label: str
    value: float | None

    def __post_init__(self) -> None:
        _validate_text(self.metric_id, "metric_id")
        _validate_text(self.label, "label")
        object.__setattr__(self, "value", _optional_number(self.value, "value"))


@dataclass(frozen=True)
class HiddenGemReleaseViewModel:
    """One ranked Hidden Gem candidate and its existing explanatory values."""

    rank: int
    release_id: int
    artist: str
    title: str
    score: float | None
    explanation: str
    supporting_metrics: tuple[HiddenGemMetricViewModel, ...] = ()
    factor_scores: tuple[HiddenGemMetricViewModel, ...] = ()
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _positive_integer(self.rank, "rank")
        _positive_integer(self.release_id, "release_id")
        _validate_text(self.artist, "artist")
        _validate_text(self.title, "title")
        _validate_text(self.explanation, "explanation")
        score = _optional_number(self.score, "score", maximum=100.0)
        supporting_metrics = _freeze_metrics(
            self.supporting_metrics,
            "supporting_metrics",
        )
        factor_scores = _freeze_metrics(self.factor_scores, "factor_scores")
        if any(
            metric.value is not None and metric.value > 100
            for metric in factor_scores
        ):
            raise ValueError("factor score values must not exceed 100.")
        evidence = _freeze_text(self.evidence, "evidence")
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "supporting_metrics", supporting_metrics)
        object.__setattr__(self, "factor_scores", factor_scores)
        object.__setattr__(self, "evidence", evidence)

    @property
    def has_unavailable_values(self) -> bool:
        """Return whether any expected candidate value is unavailable."""

        return self.score is None or any(
            metric.value is None
            for metric in (*self.supporting_metrics, *self.factor_scores)
        )


@dataclass(frozen=True)
class HiddenGemsDetailViewModel:
    """Presentation-ready detail derived from one Dashboard result."""

    state: HiddenGemsDetailState
    summary: str
    candidate_count: int | None = None
    candidates: tuple[HiddenGemReleaseViewModel, ...] = ()
    diagnostics: tuple[str, ...] = ()
    module_id: str = field(init=False, default="hidden_gems")
    title: str = field(init=False, default="Hidden Gems")

    def __post_init__(self) -> None:
        if type(self.state) is not HiddenGemsDetailState:
            raise TypeError("state must be a HiddenGemsDetailState.")
        _validate_text(self.summary, "summary")
        candidate_count = _optional_count(self.candidate_count)
        candidates = _freeze_candidates(self.candidates)
        diagnostics = _freeze_text(self.diagnostics, "diagnostics")

        if self.state is HiddenGemsDetailState.LOADING:
            if candidate_count is not None or candidates or diagnostics:
                raise HiddenGemsDetailConsistencyError(
                    "Loading Hidden Gems detail cannot contain result values."
                )
        elif self.state is HiddenGemsDetailState.UNAVAILABLE:
            if candidate_count is not None or candidates:
                raise HiddenGemsDetailConsistencyError(
                    "Unavailable Hidden Gems detail cannot contain candidates."
                )
        elif self.state is HiddenGemsDetailState.EMPTY:
            if candidate_count != 0 or candidates:
                raise HiddenGemsDetailConsistencyError(
                    "Empty Hidden Gems detail requires a zero count and no candidates."
                )
        elif self.state in {
            HiddenGemsDetailState.AVAILABLE,
            HiddenGemsDetailState.PARTIAL,
        }:
            if candidate_count is None or candidate_count <= 0:
                raise HiddenGemsDetailConsistencyError(
                    "Available Hidden Gems detail requires a positive count."
                )
            if candidate_count != len(candidates):
                raise HiddenGemsDetailConsistencyError(
                    "Candidate count must match the complete candidate list."
                )
            has_unavailable = any(
                candidate.has_unavailable_values for candidate in candidates
            )
            if self.state is HiddenGemsDetailState.AVAILABLE and has_unavailable:
                raise HiddenGemsDetailConsistencyError(
                    "Available Hidden Gems detail cannot contain unavailable values."
                )
            if self.state is HiddenGemsDetailState.PARTIAL and not has_unavailable:
                raise HiddenGemsDetailConsistencyError(
                    "Partial Hidden Gems detail requires an unavailable value."
                )

        object.__setattr__(self, "candidate_count", candidate_count)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "diagnostics", diagnostics)

    @classmethod
    def loading(cls) -> "HiddenGemsDetailViewModel":
        """Return the deterministic state shown before detail data is ready."""

        return cls(
            state=HiddenGemsDetailState.LOADING,
            summary="Hidden Gems detail is loading.",
        )


def _freeze_candidates(values: Any) -> tuple[HiddenGemReleaseViewModel, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError("candidates must be a collection.")
    try:
        candidates = tuple(values)
    except TypeError as exc:
        raise TypeError("candidates must be a collection.") from exc
    if any(type(value) is not HiddenGemReleaseViewModel for value in candidates):
        raise TypeError("candidates must contain HiddenGemReleaseViewModel values.")
    if tuple(candidate.rank for candidate in candidates) != tuple(
        range(1, len(candidates) + 1)
    ):
        raise HiddenGemsDetailConsistencyError(
            "Candidate ranks must be contiguous and preserve presentation order."
        )
    release_ids = tuple(candidate.release_id for candidate in candidates)
    if len(set(release_ids)) != len(release_ids):
        raise HiddenGemsDetailConsistencyError("Candidate release IDs must be unique.")
    return candidates


def _freeze_metrics(
    values: Any,
    name: str,
) -> tuple[HiddenGemMetricViewModel, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{name} must be a collection.")
    try:
        metrics = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{name} must be a collection.") from exc
    if any(type(value) is not HiddenGemMetricViewModel for value in metrics):
        raise TypeError(f"{name} must contain HiddenGemMetricViewModel values.")
    metric_ids = tuple(metric.metric_id for metric in metrics)
    if len(set(metric_ids)) != len(metric_ids):
        raise HiddenGemsDetailConsistencyError(f"{name} metric IDs must be unique.")
    return metrics


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


def _optional_number(
    value: Any,
    name: str,
    *,
    maximum: float | None = None,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number or None.")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative.")
    if maximum is not None and number > maximum:
        raise ValueError(f"{name} must not exceed {maximum:g}.")
    return number


def _optional_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("candidate_count must be an integer or None.")
    if value < 0:
        raise ValueError("candidate_count must be non-negative.")
    return value


def _positive_integer(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _validate_text(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a non-empty trimmed string.")


__all__ = [
    "HiddenGemMetricViewModel",
    "HiddenGemReleaseViewModel",
    "HiddenGemsDetailConsistencyError",
    "HiddenGemsDetailState",
    "HiddenGemsDetailViewModel",
]
