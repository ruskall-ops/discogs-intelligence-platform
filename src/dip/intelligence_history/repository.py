"""Persistence boundary for immutable Intelligence History executions."""

from collections.abc import Sequence
from typing import Protocol

from .models import IntelligenceHistoryRecord, IntelligenceHistoryRun


class IntelligenceHistoryRepository(Protocol):
    """Store and retrieve historical intelligence without storage coupling."""

    def save_execution(
        self,
        run: IntelligenceHistoryRun,
        records: Sequence[IntelligenceHistoryRecord],
    ) -> IntelligenceHistoryRun:
        """Atomically save a new run and records whose run_id is None."""
        ...

    def latest_run(self) -> IntelligenceHistoryRun | None:
        """Return the most recent run using deterministic ordering."""
        ...

    def previous_run(self) -> IntelligenceHistoryRun | None:
        """Return the run immediately preceding the latest run."""
        ...

    def latest_result(
        self,
        module_id: str,
    ) -> IntelligenceHistoryRecord | None:
        """Return the latest result recorded for a module."""
        ...

    def previous_result(
        self,
        module_id: str,
    ) -> IntelligenceHistoryRecord | None:
        """Return the result immediately preceding a module's latest result."""
        ...

    def history_for_module(
        self,
        module_id: str,
    ) -> tuple[IntelligenceHistoryRecord, ...]:
        """Return a module's complete history in chronological order."""
        ...
