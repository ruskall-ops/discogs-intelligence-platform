"""Standard outputs shared by the Collection Intelligence Engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class IntelligenceStatus(str, Enum):
    """Supported module execution outcomes."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class IntelligenceResult:
    """Explainable, renderer-independent output from one module."""

    module_id: str
    status: IntelligenceStatus | str
    summary: str
    insights: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()
    module_version: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == IntelligenceStatus.COMPLETED

    @property
    def failed(self) -> bool:
        return self.status == IntelligenceStatus.FAILED


@dataclass(frozen=True)
class IntelligenceExecution:
    """Aggregate outcome of one engine execution."""

    results: tuple[IntelligenceResult, ...]

    @property
    def module_count(self) -> int:
        return len(self.results)

    @property
    def completed_count(self) -> int:
        return sum(result.succeeded for result in self.results)

    @property
    def failed_count(self) -> int:
        return sum(result.failed for result in self.results)

    @property
    def skipped_count(self) -> int:
        return sum(
            result.status == IntelligenceStatus.SKIPPED
            for result in self.results
        )

    @property
    def successful(self) -> bool:
        return self.failed_count == 0

    def result_for(self, module_id: str) -> IntelligenceResult | None:
        """Return a module result without presentation-specific lookup code."""

        return next(
            (
                result
                for result in self.results
                if result.module_id == module_id
            ),
            None,
        )
