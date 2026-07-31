from dataclasses import FrozenInstanceError
import unittest

from dip.app import ProjectManagementService, ProjectWorkspacePresentationService
from dip.experience.desktop.project_workspace_renderer import (
    DesktopProjectWorkspaceController,
)
from dip.experience.project_workspace import (
    Project,
    ProjectStatus,
    ProjectSummary,
    ProjectWorkspaceBuilder,
    ProjectWorkspaceNavigationTarget,
)
from dip.projects import InMemoryProjectRepository, ManagedProject


def active():
    return Project(
        "current", "Current Collection", "Collector working environment.",
        ProjectStatus.ACTIVE,
    )


class ProjectWorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        self.builder = ProjectWorkspaceBuilder()
        management = ProjectManagementService(
            InMemoryProjectRepository(
                (
                    ManagedProject(
                        "current", "Current Collection",
                        "Collector working environment.", 1,
                    ),
                ),
                active_project_id="current",
            )
        )
        self.presentation = ProjectWorkspacePresentationService(
            management, self.builder
        )

    def test_project_models_are_immutable_and_validate_status_roles(self):
        project = active()
        self.assertIs(project.status, ProjectStatus.ACTIVE)
        with self.assertRaises(FrozenInstanceError):
            project.name = "Changed"
        with self.assertRaises(ValueError):
            self.builder.build(
                project,
                (Project("recent", "Recent", "Recent project.", ProjectStatus.ACTIVE),),
            )

    def test_builder_is_deterministic_and_preserves_recent_project_order(self):
        recent = (
            Project("two", "Second", "Second recent project.", ProjectStatus.RECENT),
            Project("one", "First", "First recent project.", ProjectStatus.RECENT),
        )
        summary = ProjectSummary("Summary", ("Supplied detail.",))
        first = self.builder.build(active(), recent, summary)
        second = self.builder.build(active(), recent, summary)
        self.assertEqual(first, second)
        self.assertEqual(
            tuple(value.project_id for value in first.recent_projects.projects),
            ("two", "one"),
        )

    def test_navigation_model_enables_only_existing_workspace_transitions(self):
        workspace = self.presentation.workspace()
        enabled = tuple(
            value.target for value in workspace.actions if value.enabled
        )
        self.assertEqual(
            enabled,
            (ProjectWorkspaceNavigationTarget.DASHBOARD,),
        )
        self.assertEqual(
            tuple(value.target for value in workspace.actions),
            tuple(ProjectWorkspaceNavigationTarget),
        )

    def test_renderer_displays_landing_sections_and_empty_recent_state(self):
        rendered = DesktopProjectWorkspaceController(self.presentation).open()
        self.assertEqual(
            tuple(value.title for value in rendered.sections),
            ("Active Project", "Recent Projects", "Project Summary", "Quick Actions"),
        )
        body = "\n".join(value.body for value in rendered.sections)
        for expected in (
            "Current Collection",
            "No recent projects have been supplied.",
            "Project identity and active state are stored in SQLite",
            "primary desktop session restoration is enabled",
            "Open Dashboard",
            "Open Portfolio Workspace",
        ):
            self.assertIn(expected, body)

    def test_renderer_supports_no_active_project_without_retrieval(self):
        empty = ProjectWorkspacePresentationService(
            ProjectManagementService(InMemoryProjectRepository()),
            ProjectWorkspaceBuilder(),
        )
        rendered = DesktopProjectWorkspaceController(empty).open()
        self.assertEqual(
            rendered.sections[0].body, "No active project has been supplied."
        )


if __name__ == "__main__":
    unittest.main()
