"""Standard outputs shared by every intelligence module."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class IntelligenceResult:
    module_id: str
    status: str
    summary: str
    insights: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
