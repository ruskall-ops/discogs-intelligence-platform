"""Deterministic in-memory Project repository."""

from .models import ManagedProject


class InMemoryProjectRepository:
    def __init__(self, projects=(), *, active_project_id=None):
        projects = tuple(projects)
        if any(type(value) is not ManagedProject for value in projects):
            raise TypeError("projects must contain ManagedProject values.")
        identifiers = tuple(value.project_id for value in projects)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Project identities must be unique.")
        if active_project_id is not None and active_project_id not in identifiers:
            raise ValueError("active_project_id must identify a supplied project.")
        self._projects = {value.project_id: value for value in projects}
        self._active_project_id = active_project_id
        self._next_open_order = max(
            (value.last_opened_order or 0 for value in projects), default=0
        ) + 1

    def list_projects(self):
        return tuple(self._projects.values())

    def get(self, project_id):
        return self._projects.get(project_id)

    def add(self, project):
        if type(project) is not ManagedProject:
            raise TypeError("project must be ManagedProject.")
        if project.project_id in self._projects:
            raise ValueError("Project identity already exists.")
        self._projects[project.project_id] = project
        self._next_open_order = max(
            self._next_open_order,
            (project.last_opened_order or 0) + 1,
        )

    def active_project_id(self):
        return self._active_project_id

    def set_active(self, project_id):
        self._require(project_id)
        self._active_project_id = project_id

    def update_last_opened(self, project_id):
        project = self._require(project_id).opened(self._next_open_order)
        self._next_open_order += 1
        self._projects[project_id] = project
        return project

    def open(self, project_id):
        project = self._require(project_id).opened(self._next_open_order)
        self._next_open_order += 1
        self._projects[project_id] = project
        self._active_project_id = project_id
        return project

    def _require(self, project_id):
        if type(project_id) is not str or not project_id:
            raise TypeError("project_id must be a non-empty string.")
        project = self._projects.get(project_id)
        if project is None:
            raise ValueError("Project does not exist.")
        return project


__all__ = ["InMemoryProjectRepository"]
