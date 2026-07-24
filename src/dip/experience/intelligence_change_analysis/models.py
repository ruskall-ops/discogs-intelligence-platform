"""Frozen presentation models for Intelligence Change Analysis."""

from dataclasses import dataclass, field
from enum import Enum

from dip.historical_intelligence import IntelligenceComparisonOutput


class IntelligenceChangeAnalysisDetailState(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class IntelligenceChangeAnalysisViewModel:
    state: IntelligenceChangeAnalysisDetailState
    summary_text: str
    output: IntelligenceComparisonOutput | None = None
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Intelligence Change Analysis")

    def __post_init__(self):
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @classmethod
    def unavailable(cls):
        return cls(
            IntelligenceChangeAnalysisDetailState.UNAVAILABLE,
            "Intelligence Change Analysis has not been supplied.",
        )
