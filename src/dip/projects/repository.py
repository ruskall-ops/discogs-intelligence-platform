"""Storage-independent Project repository contract."""

from typing import Protocol

from .models import ManagedProject


class ProjectPersistenceError(RuntimeError):
    """Project storage failed without exposing an adapter-specific exception."""


class ProjectRepository(Protocol):
    def list_projects(self) -> tuple[ManagedProject, ...]: ...

    def get(self, project_id: str) -> ManagedProject | None: ...

    def add(self, project: ManagedProject) -> None: ...

    def active_project_id(self) -> str | None: ...

    def set_active(self, project_id: str) -> None: ...

    def update_last_opened(self, project_id: str) -> ManagedProject: ...

    def open(self, project_id: str) -> ManagedProject: ...


__all__ = ["ProjectPersistenceError", "ProjectRepository"]
