"""Comparer protocol and deterministic module comparison registry."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Protocol, runtime_checkable

from dip.intelligence_history import IntelligenceHistoryRecord

from .models import ModuleComparison


@runtime_checkable
class ModuleComparer(Protocol):
    """Compare historical records for one canonical module identifier."""

    module_id: str

    def compare(
        self,
        previous: IntelligenceHistoryRecord | None,
        current: IntelligenceHistoryRecord | None,
    ) -> ModuleComparison: ...


ModuleComparerFactory = Callable[[str], ModuleComparer]


class ComparisonRegistry:
    """Maintain deterministic explicit comparers with an optional fallback."""

    def __init__(
        self,
        comparers: Iterable[ModuleComparer] = (),
        *,
        fallback_factory: ModuleComparerFactory | None = None,
    ) -> None:
        self._comparers: dict[str, ModuleComparer] = {}
        self._fallback_factory = fallback_factory
        for comparer in comparers:
            self.register(comparer)

    def register(self, comparer: ModuleComparer) -> None:
        """Register one comparer, rejecting invalid or duplicate identifiers."""

        module_id = getattr(comparer, "module_id", None)
        compare = getattr(comparer, "compare", None)
        _validate_module_id(module_id)
        if not callable(compare):
            raise TypeError(
                f"Module comparer {module_id!r} must define compare()."
            )
        if module_id in self._comparers:
            raise ValueError(
                f"Module comparer {module_id!r} is already registered."
            )
        self._comparers[module_id] = comparer

    def unregister(self, module_id: str) -> ModuleComparer:
        """Remove and return a registered comparer."""

        try:
            return self._comparers.pop(module_id)
        except KeyError as exc:
            raise KeyError(
                f"Module comparer {module_id!r} is not registered."
            ) from exc

    def get(self, module_id: str) -> ModuleComparer:
        """Return an explicit comparer or a deterministic fallback comparer."""

        _validate_module_id(module_id)
        comparer = self._comparers.get(module_id)
        if comparer is not None:
            return comparer
        if self._fallback_factory is None:
            raise KeyError(f"Module comparer {module_id!r} is not registered.")

        fallback = self._fallback_factory(module_id)
        fallback_module_id = getattr(fallback, "module_id", None)
        compare = getattr(fallback, "compare", None)
        if fallback_module_id != module_id or not callable(compare):
            raise TypeError(
                "The comparison fallback factory returned an invalid comparer."
            )
        return fallback

    @property
    def module_ids(self) -> tuple[str, ...]:
        return tuple(self._comparers)

    def __iter__(self) -> Iterator[ModuleComparer]:
        return iter(self._comparers.values())

    def __len__(self) -> int:
        return len(self._comparers)


def _validate_module_id(module_id: object) -> None:
    if not isinstance(module_id, str) or not module_id.strip():
        raise ValueError("Module comparers require a non-empty module_id.")
    if module_id != module_id.strip():
        raise ValueError("Module comparer IDs must not contain surrounding whitespace.")
