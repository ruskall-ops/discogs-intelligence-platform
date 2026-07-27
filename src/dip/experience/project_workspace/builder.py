"""Deterministic Project Workspace presentation composition."""

from .models import (
    ActiveProject,
    ProjectSummary,
    ProjectWorkspaceAction,
    ProjectWorkspaceNavigationTarget,
    ProjectWorkspaceViewModel,
    RecentProjects,
)


_ACTIONS = (
    ProjectWorkspaceAction(
        "Open Project", ProjectWorkspaceNavigationTarget.OPEN_PROJECT, False
    ),
    ProjectWorkspaceAction(
        "Create Project", ProjectWorkspaceNavigationTarget.CREATE_PROJECT, False
    ),
    ProjectWorkspaceAction(
        "Refresh Collection",
        ProjectWorkspaceNavigationTarget.REFRESH_COLLECTION,
        False,
    ),
    ProjectWorkspaceAction(
        "Open Dashboard", ProjectWorkspaceNavigationTarget.DASHBOARD, True
    ),
    ProjectWorkspaceAction(
        "Open Portfolio Workspace — Not available in this release",
        ProjectWorkspaceNavigationTarget.PORTFOLIO,
        False,
    ),
)


class ProjectWorkspaceBuilder:
    def build(self, active_project, recent_projects=(), summary=None):
        active = ActiveProject(active_project)
        recent = RecentProjects(recent_projects)
        if summary is None:
            summary = ProjectSummary(
                "Collector working environment",
                (
                    "Dashboard, Portfolio, Marketplace, and Historical Intelligence "
                    "describe the platform direction; unavailable destinations "
                    "are clearly marked in this release.",
                    "Project identity and active state are stored in SQLite; "
                    "primary desktop session restoration is enabled.",
                ),
            )
        return ProjectWorkspaceViewModel(active, recent, summary, _ACTIONS)


__all__ = ["ProjectWorkspaceBuilder"]
