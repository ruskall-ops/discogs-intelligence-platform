"""Prepared, presentation-independent input for intelligence modules."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class IntelligenceContext:
    """One consistent view of the evidence available to an analysis run.

    Modules receive this context instead of querying SQLite or external data
    providers directly. Defaults preserve the lightweight context introduced
    with the original package foundation.
    """

    collection: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    marketplace: Mapping[int, Mapping[str, Any]] = field(default_factory=dict)
    history: Mapping[int, Sequence[Mapping[str, Any]]] = field(default_factory=dict)
    user_context: Mapping[str, Any] = field(default_factory=dict)
    filters: Mapping[str, Any] = field(default_factory=dict)
    analysis_run_id: int | None = None
    captured_at: datetime | None = None
