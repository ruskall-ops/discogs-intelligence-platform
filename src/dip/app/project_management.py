"""Application orchestration for Project management."""

from dip.projects import ManagedProject, ProjectRepository


class ProjectManagementService:
    def __init__(self, repository: ProjectRepository):
        self._repository = repository

    def list_projects(self):
        return self._repository.list_projects()

    def active_project(self):
        project_id = self._repository.active_project_id()
        return None if project_id is None else self._repository.get(project_id)

    def create_project(self, project_id, name, description):
        project = ManagedProject(project_id, name, description)
        self._repository.add(project)
        return self.open_project(project_id)

    def open_project(self, project_id):
        return self._repository.open(project_id)

    def update_last_opened(self, project_id):
        return self._repository.update_last_opened(project_id)

    def recent_projects(self, limit=5):
        if type(limit) is not int:
            raise TypeError("limit must be an integer.")
        if limit <= 0:
            raise ValueError("limit must be positive.")
        active = self._repository.active_project_id()
        projects = tuple(
            value for value in self._repository.list_projects()
            if value.project_id != active and value.last_opened_order is not None
        )
        return tuple(
            sorted(
                projects,
                key=lambda value: (-value.last_opened_order, value.project_id),
            )[:limit]
        )


__all__ = ["ProjectManagementService"]
