"""Desktop rendering for the immutable Project Workspace."""

from dataclasses import dataclass

from dip.experience.project_workspace import (
    ProjectWorkspaceAction,
    ProjectWorkspaceViewModel,
)


@dataclass(frozen=True)
class DesktopProjectWorkspaceSection:
    title: str
    body: str


@dataclass(frozen=True)
class DesktopProjectWorkspaceView:
    title: str
    sections: tuple[DesktopProjectWorkspaceSection, ...]
    actions: tuple[ProjectWorkspaceAction, ...]


class DesktopProjectWorkspaceRenderer:
    def render(self, workspace):
        if type(workspace) is not ProjectWorkspaceViewModel:
            raise TypeError("workspace must be ProjectWorkspaceViewModel.")
        active = workspace.active_project.project
        active_body = (
            f"{active.name}\n{active.description}\nStatus: {active.status.value.title()}"
            if active is not None else "No active project has been supplied."
        )
        recent_body = (
            "\n\n".join(
                f"{value.name}\n{value.description}" for value in workspace.recent_projects.projects
            )
            or "No recent projects have been supplied."
        )
        return DesktopProjectWorkspaceView(
            workspace.title,
            (
                DesktopProjectWorkspaceSection("Active Project", active_body),
                DesktopProjectWorkspaceSection("Recent Projects", recent_body),
                DesktopProjectWorkspaceSection(
                    "Project Summary",
                    "\n".join((workspace.summary.heading, *workspace.summary.details)),
                ),
                DesktopProjectWorkspaceSection(
                    "Quick Actions",
                    "\n".join(value.label for value in workspace.actions),
                ),
            ),
            workspace.actions,
        )


class DesktopProjectWorkspaceController:
    def __init__(self, presentation, renderer=None):
        self._presentation = presentation
        self._renderer = renderer or DesktopProjectWorkspaceRenderer()

    def open(self, active_project, recent_projects=(), summary=None):
        return self._renderer.render(
            self._presentation.workspace(active_project, recent_projects, summary)
        )


__all__ = [
    "DesktopProjectWorkspaceController", "DesktopProjectWorkspaceRenderer",
    "DesktopProjectWorkspaceSection", "DesktopProjectWorkspaceView",
]
