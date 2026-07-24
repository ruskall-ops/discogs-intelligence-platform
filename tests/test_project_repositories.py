from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dip.app import ProjectManagementService
from dip.persistence.sqlite import Database, SQLiteProjectRepository
from dip.projects import (
    InMemoryProjectRepository,
    ManagedProject,
    ProjectPersistenceError,
)


class _ProjectRepositoryContract:
    repository: object

    def make_repository(self):
        raise NotImplementedError

    def setUp(self) -> None:
        self.repository = self.make_repository()

    def test_empty_state_and_missing_project_behaviour(self) -> None:
        self.assertEqual(self.repository.list_projects(), ())
        self.assertIsNone(self.repository.get("missing"))
        self.assertIsNone(self.repository.active_project_id())
        for operation in (
            self.repository.set_active,
            self.repository.update_last_opened,
            self.repository.open,
        ):
            with self.assertRaises(ValueError):
                operation("missing")
            with self.assertRaises(TypeError):
                operation("")

    def test_add_get_and_list_preserve_models_and_insertion_order(self) -> None:
        beta = ManagedProject("beta", "Beta", "Second.", 4)
        alpha = ManagedProject("alpha", "Alpha", "First.")
        self.repository.add(beta)
        self.repository.add(alpha)

        self.assertEqual(self.repository.get("beta"), beta)
        self.assertEqual(
            tuple(value.project_id for value in self.repository.list_projects()),
            ("beta", "alpha"),
        )

    def test_add_validates_type_and_rejects_duplicate_identity(self) -> None:
        project = ManagedProject("one", "One", "First.")
        self.repository.add(project)
        with self.assertRaises(TypeError):
            self.repository.add(object())
        with self.assertRaises(ValueError):
            self.repository.add(
                ManagedProject("one", "Duplicate", "Duplicate.")
            )
        self.assertEqual(self.repository.list_projects(), (project,))

    def test_set_active_and_last_opened_are_independent(self) -> None:
        self.repository.add(ManagedProject("one", "One", "First."))
        self.repository.add(ManagedProject("two", "Two", "Second."))

        self.repository.set_active("one")
        updated = self.repository.update_last_opened("two")

        self.assertEqual(self.repository.active_project_id(), "one")
        self.assertEqual(updated.last_opened_order, 1)

    def test_open_atomically_updates_active_and_monotonic_order(self) -> None:
        self.repository.add(ManagedProject("one", "One", "First."))
        self.repository.add(ManagedProject("two", "Two", "Second.", 7))

        opened = self.repository.open("one")
        reopened = self.repository.open("two")

        self.assertEqual(opened.last_opened_order, 8)
        self.assertEqual(reopened.last_opened_order, 9)
        self.assertEqual(self.repository.active_project_id(), "two")

    def test_service_recent_order_uses_identity_to_break_ties(self) -> None:
        for project in (
            ManagedProject("active", "Active", "Active.", 3),
            ManagedProject("beta", "Beta", "Beta.", 2),
            ManagedProject("alpha", "Alpha", "Alpha.", 2),
            ManagedProject("never", "Never", "Never."),
        ):
            self.repository.add(project)
        self.repository.set_active("active")

        recent = ProjectManagementService(self.repository).recent_projects()

        self.assertEqual(
            tuple(value.project_id for value in recent),
            ("alpha", "beta"),
        )


class InMemoryProjectRepositoryContractTestCase(
    _ProjectRepositoryContract,
    unittest.TestCase,
):
    def make_repository(self):
        return InMemoryProjectRepository()


class SQLiteProjectRepositoryContractTestCase(
    _ProjectRepositoryContract,
    unittest.TestCase,
):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "projects.db"
        self.database = Database(self.database_path)
        super().setUp()

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def make_repository(self):
        return SQLiteProjectRepository(self.database)

    def test_projects_and_active_state_survive_restart(self) -> None:
        self.repository.add(ManagedProject("one", "One", "First."))
        opened = self.repository.open("one")
        self.database.close()

        self.database = Database(self.database_path)
        self.repository = SQLiteProjectRepository(self.database)

        self.assertEqual(self.repository.list_projects(), (opened,))
        self.assertEqual(self.repository.active_project_id(), "one")

    def test_default_project_is_created_once_and_existing_state_is_reused(
        self,
    ) -> None:
        default = ManagedProject(
            "current_collection",
            "Current Collection",
            "Collector environment.",
            1,
        )
        self.assertEqual(
            self.repository.ensure_default_project(default),
            default,
        )
        self.repository.add(ManagedProject("other", "Other", "Other.", 2))
        self.repository.open("other")
        self.database.close()

        self.database = Database(self.database_path)
        self.repository = SQLiteProjectRepository(self.database)
        stored = self.repository.ensure_default_project(
            ManagedProject(
                "current_collection",
                "Changed default",
                "Must not overwrite.",
            )
        )

        self.assertEqual(stored, default)
        self.assertEqual(
            tuple(value.project_id for value in self.repository.list_projects()),
            ("current_collection", "other"),
        )
        self.assertEqual(self.repository.active_project_id(), "other")

    def test_open_failure_rolls_back_order_and_active_state(self) -> None:
        self.repository.add(ManagedProject("one", "One", "First."))
        self.repository.add(ManagedProject("two", "Two", "Second."))
        first = self.repository.open("one")
        self.database.conn.execute(
            """
            CREATE TRIGGER fail_project_activation
            BEFORE UPDATE ON project_state
            BEGIN
                SELECT RAISE(ABORT, 'activation failed');
            END
            """
        )
        self.database.conn.commit()

        with self.assertRaises(ProjectPersistenceError) as raised:
            self.repository.open("two")

        self.assertNotEqual(
            type(raised.exception.__cause__).__module__,
            type(raised.exception).__module__,
        )
        self.assertEqual(self.repository.active_project_id(), "one")
        self.assertEqual(self.repository.get("one"), first)
        self.assertIsNone(self.repository.get("two").last_opened_order)

    def test_nested_write_respects_outer_transaction_rollback(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "roll back outer"):
            with self.database.transaction():
                self.repository.add(
                    ManagedProject("one", "One", "First.")
                )
                raise RuntimeError("roll back outer")

        self.assertEqual(self.repository.list_projects(), ())

    def test_invalid_stored_project_is_rejected(self) -> None:
        self.database.conn.execute(
            """
            INSERT INTO projects (
                project_id,
                name,
                description,
                insertion_order
            )
            VALUES ('broken', '', 'Invalid.', 1)
            """
        )
        self.database.conn.commit()

        with self.assertRaises(ProjectPersistenceError):
            self.repository.get("broken")

    def test_sqlite_errors_do_not_escape_repository_boundary(self) -> None:
        self.database.close()
        with self.assertRaises(ProjectPersistenceError) as raised:
            self.repository.list_projects()
        self.assertNotEqual(
            type(raised.exception.__cause__),
            type(raised.exception),
        )
        self.database = Database(self.database_path)


if __name__ == "__main__":
    unittest.main()
