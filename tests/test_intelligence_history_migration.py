from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from dip.persistence.sqlite.migrations.base import Migration
from dip.persistence.sqlite.migrations.runner import run_migrations
from dip.persistence.sqlite.schema import SCHEMA_PATH


class _FailingMigration(Migration):
    version = 99
    name = "Deliberately failing migration"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        connection.execute("CREATE TABLE should_roll_back (id INTEGER)")
        connection.execute("THIS IS NOT VALID SQL")


class IntelligenceHistoryMigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = self._connection()

    def tearDown(self) -> None:
        self.connection.close()

    def test_real_version_one_schema_upgrades_through_current_migrations(self) -> None:
        self._install_version_one_schema(self.connection)

        applied = run_migrations(self.connection)

        self.assertEqual(
            tuple(migration.version for migration in applied),
            (2, 3),
        )
        self.assertEqual(applied[0].name, "Add Intelligence History tables")
        self.assertIn("Marketplace History", applied[1].name)
        self._assert_intelligence_history_schema(self.connection)
        versions = {
            row["version"]
            for row in self.connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        self.assertEqual(versions, {1, 2, 3})

    def test_migration_failure_rolls_back_ddl_and_version_record(self) -> None:
        self._install_version_one_schema(self.connection)

        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[_FailingMigration()],
        ):
            with self.assertRaisesRegex(RuntimeError, "Migration 99"):
                run_migrations(self.connection)

        table = self.connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            ("should_roll_back",),
        ).fetchone()
        version = self.connection.execute(
            "SELECT version FROM schema_migrations WHERE version = ?",
            (99,),
        ).fetchone()
        self.assertIsNone(table)
        self.assertIsNone(version)

    def test_current_schema_and_pending_migrations_are_equivalent(self) -> None:
        self._install_version_one_schema(self.connection)
        run_migrations(self.connection)
        migrated_signature = self._schema_signature(self.connection)

        current = self._connection()
        try:
            current.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            current_signature = self._schema_signature(current)
        finally:
            current.close()

        self.assertEqual(migrated_signature, current_signature)

    @staticmethod
    def _connection() -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _install_version_one_schema(connection: sqlite3.Connection) -> None:
        current_schema = SCHEMA_PATH.read_text(encoding="utf-8")
        version_one_schema, marker, _ = current_schema.partition(
            "CREATE TABLE IF NOT EXISTS intelligence_runs"
        )
        if not marker:
            raise AssertionError("Unable to locate Intelligence History schema")
        connection.executescript(version_one_schema)
        connection.execute(
            "INSERT INTO schema_migrations(version) VALUES (?)",
            (1,),
        )
        connection.commit()

    def _assert_intelligence_history_schema(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        signature = self._schema_signature(connection)
        self.assertEqual(
            tuple(signature["intelligence_runs"]["columns"]),
            (
                ("id", "INTEGER", 0),
                ("executed_at", "TEXT", 1),
                ("executed_at_json", "TEXT", 1),
                ("engine_version", "TEXT", 0),
                ("collection_snapshot_id", "INTEGER", 0),
                ("result_count", "INTEGER", 1),
            ),
        )
        self.assertIn(
            "CHECK (result_count >= 0)",
            signature["intelligence_runs"]["sql"],
        )
        self.assertEqual(
            signature["intelligence_results"]["foreign_keys"],
            (("run_id", "intelligence_runs", "id", "RESTRICT"),),
        )
        self.assertIn(
            ("run_id", "module_id"),
            signature["intelligence_results"]["unique_indexes"],
        )
        self.assertEqual(
            signature["named_indexes"],
            {
                "idx_intelligence_results_module_run": (
                    "module_id",
                    "run_id",
                ),
                "idx_intelligence_runs_executed": ("executed_at", "id"),
            },
        )

    @staticmethod
    def _schema_signature(connection: sqlite3.Connection) -> dict[str, object]:
        signature: dict[str, object] = {}
        for table in ("intelligence_runs", "intelligence_results"):
            columns = tuple(
                (row["name"], row["type"], row["notnull"])
                for row in connection.execute(
                    f"PRAGMA table_info({table})"
                ).fetchall()
            )
            foreign_keys = tuple(
                (
                    row["from"],
                    row["table"],
                    row["to"],
                    row["on_delete"],
                )
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({table})"
                ).fetchall()
            )
            table_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()["sql"]
            unique_indexes = tuple(
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
            )
            signature[table] = {
                "columns": columns,
                "foreign_keys": foreign_keys,
                "sql": " ".join(table_sql.split()),
                "unique_indexes": unique_indexes,
            }

        signature["named_indexes"] = {
            row["name"]: tuple(
                column["name"]
                for column in connection.execute(
                    f"PRAGMA index_info({row['name']})"
                ).fetchall()
            )
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'index' AND name LIKE 'idx_intelligence_%'
                ORDER BY name
                """
            ).fetchall()
        }
        return signature


if __name__ == "__main__":
    unittest.main()
