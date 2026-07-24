from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dip.composition import build_desktop_application_dependencies
from dip.persistence.sqlite import SQLiteProjectRepository


class ProjectCompositionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "composition.db"

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def build(self):
        with patch(
            "dip.composition.SETTINGS",
            SimpleNamespace(database_path=self.database_path),
        ):
            return build_desktop_application_dependencies()

    def test_composition_uses_sqlite_and_creates_default_once(self) -> None:
        first = self.build()
        try:
            repository = first.project_management._repository
            self.assertIsInstance(repository, SQLiteProjectRepository)
            self.assertEqual(
                tuple(
                    project.project_id
                    for project in first.project_management.list_projects()
                ),
                ("current_collection",),
            )
            self.assertEqual(
                first.project_management.active_project().project_id,
                "current_collection",
            )
            first.project_management.create_project(
                "other",
                "Other",
                "A persisted Project.",
            )
        finally:
            first.database.close()

        second = self.build()
        try:
            self.assertEqual(
                tuple(
                    project.project_id
                    for project in second.project_management.list_projects()
                ),
                ("current_collection", "other"),
            )
            self.assertEqual(
                second.project_management.active_project().project_id,
                "other",
            )
            workspace = second.project_workspace_controller.open()
            self.assertIn("Other", workspace.sections[0].body)
            self.assertIn(
                "Current Collection",
                workspace.sections[1].body,
            )
        finally:
            second.database.close()


if __name__ == "__main__":
    unittest.main()
