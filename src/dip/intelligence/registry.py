"""Protocol and ordered registry for pluggable intelligence modules."""

from collections.abc import Iterable, Iterator
from typing import Protocol, runtime_checkable

from .context import IntelligenceContext
from .models import IntelligenceResult


@runtime_checkable
class IntelligenceModule(Protocol):
    """Contract implemented by every Collection Intelligence module."""

    module_id: str
    module_version: str

    def analyse(self, context: IntelligenceContext) -> IntelligenceResult: ...


class IntelligenceRegistry:
    """Maintain a deterministic, uniquely identified module collection."""

    def __init__(
        self,
        modules: Iterable[IntelligenceModule] = (),
    ) -> None:
        self._modules: dict[str, IntelligenceModule] = {}

        for module in modules:
            self.register(module)

    def register(self, module: IntelligenceModule) -> None:
        """Register a module, rejecting invalid or duplicate identifiers."""

        module_id = getattr(module, "module_id", None)
        module_version = getattr(module, "module_version", None)
        analyse = getattr(module, "analyse", None)

        if not isinstance(module_id, str) or not module_id.strip():
            raise ValueError("Intelligence modules require a non-empty module_id.")

        if not isinstance(module_version, str) or not module_version.strip():
            raise ValueError(
                f"Intelligence module {module_id!r} requires a module_version."
            )

        if not callable(analyse):
            raise TypeError(
                f"Intelligence module {module_id!r} must define analyse()."
            )

        if module_id in self._modules:
            raise ValueError(
                f"Intelligence module {module_id!r} is already registered."
            )

        self._modules[module_id] = module

    def unregister(self, module_id: str) -> IntelligenceModule:
        """Remove and return a module by identifier."""

        try:
            return self._modules.pop(module_id)
        except KeyError as exc:
            raise KeyError(
                f"Intelligence module {module_id!r} is not registered."
            ) from exc

    def get(self, module_id: str) -> IntelligenceModule:
        """Return a registered module by identifier."""

        try:
            return self._modules[module_id]
        except KeyError as exc:
            raise KeyError(
                f"Intelligence module {module_id!r} is not registered."
            ) from exc

    @property
    def module_ids(self) -> tuple[str, ...]:
        return tuple(self._modules)

    def __iter__(self) -> Iterator[IntelligenceModule]:
        return iter(self._modules.values())

    def __len__(self) -> int:
        return len(self._modules)
