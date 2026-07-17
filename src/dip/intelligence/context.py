"""Prepared input supplied to intelligence modules."""

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class IntelligenceContext:
    collection: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    marketplace: Mapping[int, Mapping[str, Any]] = field(default_factory=dict)
    history: Mapping[int, Sequence[Mapping[str, Any]]] = field(default_factory=dict)
    user_context: Mapping[str, Any] = field(default_factory=dict)
