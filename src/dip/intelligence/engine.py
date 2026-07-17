"""Execution boundary for registered Collection Intelligence modules."""

from collections.abc import Iterable
from dataclasses import replace

from .context import IntelligenceContext
from .models import IntelligenceExecution, IntelligenceResult, IntelligenceStatus
from .registry import IntelligenceModule, IntelligenceRegistry


class IntelligenceEngine:
    """Execute deterministic modules with validation and failure isolation."""

    def __init__(
        self,
        modules: Iterable[IntelligenceModule] | IntelligenceRegistry = (),
    ) -> None:
        self.registry = (
            modules
            if isinstance(modules, IntelligenceRegistry)
            else IntelligenceRegistry(modules)
        )

    def run(self, context: IntelligenceContext) -> tuple[IntelligenceResult, ...]:
        """Return results using the original package-foundation API."""

        return self.execute(context).results

    def execute(self, context: IntelligenceContext) -> IntelligenceExecution:
        """Execute every module, continuing after individual failures."""

        results = tuple(
            self._execute_module(module, context)
            for module in self.registry
        )

        return IntelligenceExecution(results=results)

    def _execute_module(
        self,
        module: IntelligenceModule,
        context: IntelligenceContext,
    ) -> IntelligenceResult:
        try:
            result = module.analyse(context)
            self._validate_result(module, result)

            if result.module_version is None:
                result = replace(
                    result,
                    module_version=module.module_version,
                )

            return result
        except Exception as exc:
            return IntelligenceResult(
                module_id=module.module_id,
                module_version=module.module_version,
                status=IntelligenceStatus.FAILED,
                summary=f"{module.module_id} could not complete its analysis.",
                diagnostics=(f"{type(exc).__name__}: {exc}",),
            )

    @staticmethod
    def _validate_result(
        module: IntelligenceModule,
        result: IntelligenceResult,
    ) -> None:
        if not isinstance(result, IntelligenceResult):
            raise TypeError("analyse() must return an IntelligenceResult.")

        if result.module_id != module.module_id:
            raise ValueError(
                "The result module_id must match the registered module_id."
            )
