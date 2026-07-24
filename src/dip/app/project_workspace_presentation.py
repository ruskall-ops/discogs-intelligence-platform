"""Presentation boundary for the Project Workspace."""

from dip.experience.project_workspace import Project, ProjectStatus


class ProjectWorkspacePresentationService:
    def __init__(self, projects, builder):
        self._projects = projects
        self._builder = builder

    def workspace(self):
        active = self._projects.active_project()
        recent = self._projects.recent_projects()
        return self._builder.build(
            _project(active, ProjectStatus.ACTIVE) if active is not None else None,
            tuple(_project(value, ProjectStatus.RECENT) for value in recent),
        )


def _project(value, status):
    return Project(value.project_id, value.name, value.description, status)


__all__ = ["ProjectWorkspacePresentationService"]
