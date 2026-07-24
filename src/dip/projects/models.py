"""Immutable application model for managed Projects."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ManagedProject:
    project_id: str
    name: str
    description: str
    last_opened_order: int | None = None

    def __post_init__(self):
        for name in ("project_id", "name", "description"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise TypeError(f"{name} must be a non-empty string.")
        if (
            self.last_opened_order is not None
            and (
                type(self.last_opened_order) is not int
                or self.last_opened_order <= 0
            )
        ):
            raise ValueError("last_opened_order must be a positive integer or None.")

    def opened(self, order):
        return replace(self, last_opened_order=order)


__all__ = ["ManagedProject"]
