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
        "Open Portfolio Workspace",
        ProjectWorkspaceNavigationTarget.PORTFOLIO,
        True,
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
                    "remain available through existing workspaces.",
                    "Project storage and session restoration are not implemented.",
                ),
            )
        return ProjectWorkspaceViewModel(active, recent, summary, _ACTIONS)


__all__ = ["ProjectWorkspaceBuilder"]
