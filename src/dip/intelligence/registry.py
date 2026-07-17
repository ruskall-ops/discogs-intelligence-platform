"""Protocol and registry for pluggable intelligence modules."""

from typing import Protocol

from .context import IntelligenceContext
from .models import IntelligenceResult


class IntelligenceModule(Protocol):
    module_id: str

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult: ...
