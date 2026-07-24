"""Presentation boundary for the Project Workspace."""


class ProjectWorkspacePresentationService:
    def __init__(self, builder):
        self._builder = builder

    def workspace(self, active_project, recent_projects=(), summary=None):
        return self._builder.build(active_project, recent_projects, summary)


__all__ = ["ProjectWorkspacePresentationService"]
