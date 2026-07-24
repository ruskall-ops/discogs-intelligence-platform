"""Immutable evidence-first Intelligence Insight presentation models."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class IntelligenceInsightCategory(str, Enum):
    SNAPSHOT = "snapshot"
    CHANGE = "change"
    TREND = "trend"


class IntelligenceInsightType(str, Enum):
    OVERALL = "overall"
    ASSESSMENT = "assessment"
    EVIDENCE = "evidence"
    NUMERIC_METRIC = "numeric_metric"
    DIMENSION = "dimension"
    REASON = "reason"
    DIAGNOSTIC = "diagnostic"
    CONFIGURATION = "configuration"
    PROVENANCE = "provenance"


class IntelligenceInsightPriority(str, Enum):
    CRITICAL = "critical"
    IMPORTANT = "important"
    INFORMATIONAL = "informational"


class IntelligenceInsightCollectionState(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    NO_SNAPSHOT = "no_snapshot"
    NO_CHANGE = "no_change"
    NO_TREND = "no_trend"


@dataclass(frozen=True)
class IntelligenceInsightEvidence:
    label: str
    values: tuple[Any, ...]

    def __post_init__(self):
        if type(self.label) is not str or not self.label:
            raise TypeError("Evidence label must be a non-empty string.")
        values = tuple(self.values)
        if not values:
            raise ValueError("An insight requires explicit evidence values.")
        object.__setattr__(self, "values", values)


@dataclass(frozen=True)
class IntelligenceInsightSource:
    view_model_type: str
    module_id: str | None = None
    module_version: str | None = None
    rule_set_version: str | None = None
    identity: Any = None


@dataclass(frozen=True)
class IntelligenceInsight:
    title: str
    summary: str
    evidence: tuple[IntelligenceInsightEvidence, ...]
    source: IntelligenceInsightSource
    reason_codes: tuple[Any, ...]
    diagnostics: tuple[Any, ...]
    provenance: Any
    priority: IntelligenceInsightPriority
    category: IntelligenceInsightCategory
    insight_type: IntelligenceInsightType

    def __post_init__(self):
        if type(self.title) is not str or not self.title:
            raise TypeError("Insight title must be a non-empty string.")
        if type(self.summary) is not str or not self.summary:
            raise TypeError("Insight summary must be a non-empty string.")
        evidence = tuple(self.evidence)
        if not evidence or any(type(value) is not IntelligenceInsightEvidence for value in evidence):
            raise ValueError("Insights require structured evidence.")
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True)
class IntelligenceInsightCollection:
    state: IntelligenceInsightCollectionState
    category: IntelligenceInsightCategory | None
    insights: tuple[IntelligenceInsight, ...]
    message: str

    def __post_init__(self):
        insights = tuple(self.insights)
        if any(type(value) is not IntelligenceInsight for value in insights):
            raise TypeError("insights must contain IntelligenceInsight values.")
        if self.state is IntelligenceInsightCollectionState.AVAILABLE and not insights:
            raise ValueError("An available collection requires insights.")
        if self.state is not IntelligenceInsightCollectionState.AVAILABLE and insights:
            raise ValueError("An unavailable or empty collection cannot contain insights.")
        object.__setattr__(self, "insights", insights)


__all__ = [
    "IntelligenceInsight", "IntelligenceInsightCategory",
    "IntelligenceInsightCollection", "IntelligenceInsightCollectionState",
    "IntelligenceInsightEvidence", "IntelligenceInsightPriority",
    "IntelligenceInsightSource", "IntelligenceInsightType",
]
