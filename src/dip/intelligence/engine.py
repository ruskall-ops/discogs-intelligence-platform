"""Execution boundary for registered intelligence modules."""

from collections.abc import Iterable

from .context import IntelligenceContext
from .models import IntelligenceResult
from .registry import IntelligenceModule


class IntelligenceEngine:
    """Execute deterministic intelligence modules against one context."""

    def __init__(self, modules: Iterable[IntelligenceModule]) -> None:
        self._modules = tuple(modules)

    def run(self, context: IntelligenceContext) -> tuple[IntelligenceResult, ...]:
        return tuple(module.analyse(context) for module in self._modules)
