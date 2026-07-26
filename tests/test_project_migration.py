from __future__ import annotations

import sqlite3
import unittest

from dip.persistence.sqlite.migrations.runner import run_migrations
from dip.persistence.sqlite.schema import SCHEMA_PATH


class ProjectMigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = self._connection()

    def tearDown(self) -> None:
        self.connection.close()

    def test_genuine_version_three_schema_upgrades_once_and_preserves_data(
        self,
    ) -> None:
        self._install_version_three_schema(self.connection)
        self.connection.execute(
            "INSERT INTO releases(release_id, artist) VALUES (101, 'Existing')"
        )
        self.connection.commit()

        applied = run_migrations(self.connection)

        self.assertEqual(tuple(item.version for item in applied), (4, 5))
        self.assertEqual(applied[0].name, "Add Project persistence")
        self._assert_schema(self.connection)
        self.assertEqual(
            self.connection.execute(
                "SELECT artist FROM releases WHERE release_id = 101"
            ).fetchone()["artist"],
            "Existing",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()[-1]["version"],
            5,
        )
        self.assertEqual(run_migrations(self.connection), [])

    def test_current_schema_and_version_four_migration_are_equivalent(
        self,
    ) -> None:
        self._install_version_three_schema(self.connection)
        run_migrations(self.connection)
        migrated = self._signature(self.connection)

        current = self._connection()
        try:
            current.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            fresh = self._signature(current)
        finally:
            current.close()

        self.assertEqual(migrated, fresh)

    def test_constraints_enforce_identity_order_and_active_integrity(self) -> None:
        self._install_version_three_schema(self.connection)
        run_migrations(self.connection)
        self.connection.execute(
            """
            INSERT INTO projects (
                project_id, name, description, insertion_order
            )
            VALUES ('one', 'One', 'First.', 1)
            """
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO projects (
                    project_id, name, description, insertion_order
                )
                VALUES ('two', 'Two', 'Second.', 1)
                """
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                UPDATE project_state
                SET active_project_id = 'missing'
                WHERE singleton_id = 1
                """
            )

    def test_incompatible_table_rolls_back_schema_and_version(self) -> None:
        self._install_version_three_schema(self.connection)
        self.connection.execute(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                payload_json TEXT
            )
            """
        )
        self.connection.commit()

        with self.assertRaisesRegex(RuntimeError, "Migration 4"):
            run_migrations(self.connection)

        self.assertIsNone(
            self.connection.execute(
                "SELECT version FROM schema_migrations WHERE version = 4"
            ).fetchone()
        )
        self.assertIsNone(
            self.connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'project_state'
                """
            ).fetchone()
        )

    @staticmethod
    def _connection() -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _install_version_three_schema(
        connection: sqlite3.Connection,
    ) -> None:
        current_schema = SCHEMA_PATH.read_text(encoding="utf-8")
        version_three, marker, _ = current_schema.partition(
            "CREATE TABLE IF NOT EXISTS projects"
        )
        if not marker:
            raise AssertionError("Unable to locate Project schema")
        connection.executescript(version_three)
        connection.executemany(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            ((1,), (2,), (3,)),
        )
        connection.commit()

    def _assert_schema(self, connection: sqlite3.Connection) -> None:
        signature = self._signature(connection)
        self.assertEqual(
            signature["projects"]["columns"],
            (
                ("project_id", "TEXT", 1, 1),
                ("name", "TEXT", 1, 0),
                ("description", "TEXT", 1, 0),
                ("last_opened_order", "INTEGER", 0, 0),
                ("insertion_order", "INTEGER", 1, 0),
            ),
        )
        self.assertIn(
            ("insertion_order",),
            signature["projects"]["unique_indexes"],
        )
        self.assertEqual(
            signature["project_state"]["foreign_keys"],
            (("active_project_id", "projects", "project_id", "RESTRICT"),),
        )
        self.assertEqual(
            connection.execute(
                "SELECT singleton_id, active_project_id FROM project_state"
            ).fetchall()[0]["singleton_id"],
            1,
        )

    @staticmethod
    def _signature(connection: sqlite3.Connection) -> dict[str, object]:
        result = {}
        for table in ("projects", "project_state"):
            result[table] = {
                "columns": tuple(
                    (
                        row["name"],
                        row["type"],
                        row["notnull"],
                        row["pk"],
                    )
                    for row in connection.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()
                ),
                "foreign_keys": tuple(
                    (
                        row["from"],
                        row["table"],
                        row["to"],
                        row["on_delete"],
                    )
                    for row in connection.execute(
                        f"PRAGMA foreign_key_list({table})"
                    ).fetchall()
                ),
                "unique_indexes": tuple(
                    tuple(
                        column["name"]
                        for column in connection.execute(
                            f"PRAGMA index_info({row['name']})"
                        ).fetchall()
                    )
                    for row in connection.execute(
                        f"PRAGMA index_list({table})"
                    ).fetchall()
                    if row["unique"]
                ),
                "sql": " ".join(
                    connection.execute(
                        """
                        SELECT sql FROM sqlite_master
                        WHERE type = 'table' AND name = ?
                        """,
                        (table,),
                    ).fetchone()["sql"].split()
                ),
            }
        return result


if __name__ == "__main__":
    unittest.main()
