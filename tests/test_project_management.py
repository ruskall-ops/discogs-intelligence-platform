from dataclasses import FrozenInstanceError
import unittest

from dip.app import ProjectManagementService
from dip.projects import InMemoryProjectRepository, ManagedProject


class ProjectManagementTestCase(unittest.TestCase):
    def test_repository_preserves_insertion_order_and_immutable_values(self):
        projects = (
            ManagedProject("b", "Beta", "Second project."),
            ManagedProject("a", "Alpha", "First project."),
        )
        repository = InMemoryProjectRepository(projects)
        self.assertEqual(
            tuple(value.project_id for value in repository.list_projects()),
            ("b", "a"),
        )
        with self.assertRaises(FrozenInstanceError):
            projects[0].name = "Changed"

    def test_create_opens_project_and_rejects_duplicate_identity(self):
        service = ProjectManagementService(InMemoryProjectRepository())
        created = service.create_project("one", "One", "First project.")
        self.assertEqual(service.active_project(), created)
        self.assertEqual(created.last_opened_order, 1)
        with self.assertRaises(ValueError):
            service.create_project("one", "Duplicate", "Duplicate project.")

    def test_open_project_changes_active_and_updates_order(self):
        repository = InMemoryProjectRepository((
            ManagedProject("one", "One", "First project."),
            ManagedProject("two", "Two", "Second project."),
        ))
        service = ProjectManagementService(repository)
        first = service.open_project("one")
        second = service.open_project("two")
        reopened = service.open_project("one")
        self.assertEqual((first.last_opened_order, second.last_opened_order), (1, 2))
        self.assertEqual(reopened.last_opened_order, 3)
        self.assertEqual(service.active_project().project_id, "one")

    def test_update_last_opened_does_not_change_active_project(self):
        repository = InMemoryProjectRepository((
            ManagedProject("one", "One", "First project."),
            ManagedProject("two", "Two", "Second project."),
        ))
        service = ProjectManagementService(repository)
        service.open_project("one")
        updated = service.update_last_opened("two")
        self.assertEqual(updated.last_opened_order, 2)
        self.assertEqual(service.active_project().project_id, "one")

    def test_recent_projects_exclude_active_and_use_open_order_then_identity(self):
        repository = InMemoryProjectRepository((
            ManagedProject("active", "Active", "Active project.", 3),
            ManagedProject("beta", "Beta", "Beta project.", 2),
            ManagedProject("alpha", "Alpha", "Alpha project.", 2),
            ManagedProject("never", "Never", "Never opened."),
        ), active_project_id="active")
        service = ProjectManagementService(repository)
        self.assertEqual(
            tuple(value.project_id for value in service.recent_projects()),
            ("alpha", "beta"),
        )
        self.assertEqual(service.recent_projects(limit=1)[0].project_id, "alpha")

    def test_missing_projects_and_invalid_limits_fail_explicitly(self):
        service = ProjectManagementService(InMemoryProjectRepository())
        self.assertIsNone(service.active_project())
        with self.assertRaises(ValueError):
            service.open_project("missing")
        with self.assertRaises(ValueError):
            service.recent_projects(0)
        with self.assertRaises(TypeError):
            service.recent_projects(True)


if __name__ == "__main__":
    unittest.main()
