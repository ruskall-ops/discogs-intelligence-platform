"""Frozen presentation model for Intelligence Trend Analysis."""

from dataclasses import dataclass, field
from enum import Enum

from dip.historical_intelligence import IntelligenceTrendAnalysisOutput


class IntelligenceTrendAnalysisDetailState(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class IntelligenceTrendAnalysisViewModel:
    state: IntelligenceTrendAnalysisDetailState
    summary_text: str
    output: IntelligenceTrendAnalysisOutput | None = None
    diagnostics: tuple[str, ...] = ()
    title: str = field(init=False, default="Intelligence Trend Analysis")

    def __post_init__(self):
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @classmethod
    def unavailable(cls):
        return cls(IntelligenceTrendAnalysisDetailState.UNAVAILABLE, "Intelligence Trend Analysis has not been supplied.")
