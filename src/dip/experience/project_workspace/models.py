"""Immutable presentation models for the Project Workspace."""

from dataclasses import dataclass, field
from enum import Enum


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    RECENT = "recent"
    UNAVAILABLE = "unavailable"


class ProjectWorkspaceNavigationTarget(str, Enum):
    OPEN_PROJECT = "open_project"
    CREATE_PROJECT = "create_project"
    REFRESH_COLLECTION = "refresh_collection"
    DASHBOARD = "dashboard"
    PORTFOLIO = "portfolio"


@dataclass(frozen=True)
class Project:
    project_id: str
    name: str
    description: str
    status: ProjectStatus

    def __post_init__(self):
        for name in ("project_id", "name", "description"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise TypeError(f"{name} must be a non-empty string.")
        if type(self.status) is not ProjectStatus:
            raise TypeError("status must be ProjectStatus.")


@dataclass(frozen=True)
class ProjectSummary:
    heading: str
    details: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "details", tuple(self.details))
        if type(self.heading) is not str or not self.heading:
            raise TypeError("heading must be a non-empty string.")
        if any(type(value) is not str or not value for value in self.details):
            raise TypeError("details must contain non-empty strings.")


@dataclass(frozen=True)
class RecentProjects:
    projects: tuple[Project, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "projects", tuple(self.projects))
        if any(type(value) is not Project for value in self.projects):
            raise TypeError("projects must contain Project values.")
        if any(value.status is not ProjectStatus.RECENT for value in self.projects):
            raise ValueError("Recent projects must use RECENT status.")


@dataclass(frozen=True)
class ActiveProject:
    project: Project | None

    def __post_init__(self):
        if self.project is not None and type(self.project) is not Project:
            raise TypeError("project must be Project or None.")
        if self.project is not None and self.project.status is not ProjectStatus.ACTIVE:
            raise ValueError("Active project must use ACTIVE status.")


@dataclass(frozen=True)
class ProjectWorkspaceAction:
    label: str
    target: ProjectWorkspaceNavigationTarget
    enabled: bool

    def __post_init__(self):
        if type(self.label) is not str or not self.label:
            raise TypeError("label must be a non-empty string.")
        if type(self.target) is not ProjectWorkspaceNavigationTarget:
            raise TypeError("target must be ProjectWorkspaceNavigationTarget.")
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be a boolean.")


@dataclass(frozen=True)
class ProjectWorkspaceViewModel:
    active_project: ActiveProject
    recent_projects: RecentProjects
    summary: ProjectSummary
    actions: tuple[ProjectWorkspaceAction, ...]
    title: str = field(init=False, default="Project Workspace")

    def __post_init__(self):
        object.__setattr__(self, "actions", tuple(self.actions))
        if type(self.active_project) is not ActiveProject:
            raise TypeError("active_project must be ActiveProject.")
        if type(self.recent_projects) is not RecentProjects:
            raise TypeError("recent_projects must be RecentProjects.")
        if type(self.summary) is not ProjectSummary:
            raise TypeError("summary must be ProjectSummary.")
        if any(type(value) is not ProjectWorkspaceAction for value in self.actions):
            raise TypeError("actions must contain ProjectWorkspaceAction values.")


__all__ = [
    "ActiveProject", "Project", "ProjectStatus", "ProjectSummary",
    "ProjectWorkspaceAction", "ProjectWorkspaceNavigationTarget",
    "ProjectWorkspaceViewModel", "RecentProjects",
]
