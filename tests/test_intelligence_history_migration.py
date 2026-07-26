from __future__ import annotations

import re
import sqlite3
import unittest
from unittest.mock import patch

from dip.persistence.sqlite.migrations.base import Migration
from dip.persistence.sqlite.migrations.runner import run_migrations
from dip.persistence.sqlite.migrations.versions.v002_add_intelligence_history import (
    migration as intelligence_history_migration,
)
from dip.persistence.sqlite.migrations.versions.v003_add_marketplace_history import (
    migration as marketplace_history_migration,
)
from dip.persistence.sqlite.migrations.versions.v004_add_projects import (
    migration as projects_migration,
)
from dip.persistence.sqlite.migrations.versions.v005_add_intelligence_marketplace_provenance import (
    _has_exact_provenance_predicate,
    migration as provenance_migration,
)
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
            (2, 3, 4, 5),
        )
        self.assertEqual(applied[0].name, "Add Intelligence History tables")
        self.assertIn("Marketplace History", applied[1].name)
        self.assertIn("Project", applied[2].name)
        self.assertIn("Marketplace provenance", applied[3].name)
        self._assert_intelligence_history_schema(self.connection)
        versions = {
            row["version"]
            for row in self.connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        self.assertEqual(versions, {1, 2, 3, 4, 5})

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

    def test_genuine_version_four_upgrades_to_five_and_preserves_null_history(self):
        self._install_version_four_schema(self.connection)
        self.connection.execute(
            """
            INSERT INTO intelligence_runs (
                executed_at, executed_at_json, result_count
            )
            VALUES (?, ?, 0)
            """,
            (
                "2026-07-24T12:00:00.000000+00:00",
                '{"__dip_type__":"datetime","value":"2026-07-24T12:00:00+00:00"}',
            ),
        )
        self.connection.commit()

        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[provenance_migration],
        ):
            applied = run_migrations(self.connection)

        self.assertEqual(tuple(item.version for item in applied), (5,))
        row = self.connection.execute(
            "SELECT marketplace_snapshot_id FROM intelligence_runs"
        ).fetchone()
        self.assertIsNone(row["marketplace_snapshot_id"])
        self.assertEqual(
            tuple(
                row["version"]
                for row in self.connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            ),
            (1, 2, 3, 4, 5),
        )

    def test_version_five_validation_failure_rolls_back_column_and_version(self):
        self._install_version_four_schema(self.connection)
        self.connection.execute(
            """
            CREATE INDEX idx_intelligence_runs_marketplace_snapshot
            ON intelligence_runs(executed_at)
            """
        )
        self.connection.commit()

        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[provenance_migration],
        ):
            with self.assertRaisesRegex(RuntimeError, "Migration 5"):
                run_migrations(self.connection)

        self.assertNotIn(
            "marketplace_snapshot_id",
            {
                row["name"]
                for row in self.connection.execute(
                    "PRAGMA table_info(intelligence_runs)"
                ).fetchall()
            },
        )
        self.assertIsNone(
            self.connection.execute(
                "SELECT version FROM schema_migrations WHERE version = 5"
            ).fetchone()
        )

    def test_version_five_predicate_parser_accepts_only_exact_semantics(self):
        valid = (
            """
            CREATE UNIQUE INDEX idx
            ON intelligence_runs(marketplace_snapshot_id)
            WHERE marketplace_snapshot_id IS NOT NULL
            """,
            """
            create unique index idx
            on intelligence_runs("marketplace_snapshot_id")
            where ((( "marketplace_snapshot_id" is not null )));
            """,
            """
            CREATE UNIQUE INDEX idx
            ON intelligence_runs(`marketplace_snapshot_id`)
            WHERE [marketplace_snapshot_id] IS NOT NULL
            """,
        )
        invalid = (
            "CREATE UNIQUE INDEX idx ON intelligence_runs(marketplace_snapshot_id)",
            (
                "CREATE UNIQUE INDEX idx ON intelligence_runs"
                "(marketplace_snapshot_id) "
                "WHERE marketplace_snapshot_id IS NOT NULL OR result_count > 0"
            ),
            (
                "CREATE UNIQUE INDEX idx ON intelligence_runs"
                "(marketplace_snapshot_id) "
                "WHERE marketplace_snapshot_id IS NOT NULL AND result_count > 0"
            ),
            (
                "CREATE UNIQUE INDEX idx ON intelligence_runs"
                "(marketplace_snapshot_id) WHERE executed_at IS NOT NULL"
            ),
            (
                "CREATE UNIQUE INDEX idx ON intelligence_runs"
                "(marketplace_snapshot_id) "
                "WHERE NOT marketplace_snapshot_id IS NULL"
            ),
        )
        for sql in valid:
            with self.subTest(sql=sql):
                self.assertTrue(_has_exact_provenance_predicate(sql))
        for sql in invalid:
            with self.subTest(sql=sql):
                self.assertFalse(_has_exact_provenance_predicate(sql))

    def test_version_five_rejects_each_incompatible_index_shape(self):
        definitions = {
            "or condition": """
                CREATE UNIQUE INDEX idx_intelligence_runs_marketplace_snapshot
                ON intelligence_runs(marketplace_snapshot_id)
                WHERE marketplace_snapshot_id IS NOT NULL OR result_count > 0
            """,
            "and condition": """
                CREATE UNIQUE INDEX idx_intelligence_runs_marketplace_snapshot
                ON intelligence_runs(marketplace_snapshot_id)
                WHERE marketplace_snapshot_id IS NOT NULL AND result_count > 0
            """,
            "wrong predicate column": """
                CREATE UNIQUE INDEX idx_intelligence_runs_marketplace_snapshot
                ON intelligence_runs(marketplace_snapshot_id)
                WHERE executed_at IS NOT NULL
            """,
            "absent where": """
                CREATE UNIQUE INDEX idx_intelligence_runs_marketplace_snapshot
                ON intelligence_runs(marketplace_snapshot_id)
            """,
            "non-unique": """
                CREATE INDEX idx_intelligence_runs_marketplace_snapshot
                ON intelligence_runs(marketplace_snapshot_id)
                WHERE marketplace_snapshot_id IS NOT NULL
            """,
            "wrong indexed column": """
                CREATE UNIQUE INDEX idx_intelligence_runs_marketplace_snapshot
                ON intelligence_runs(executed_at)
                WHERE marketplace_snapshot_id IS NOT NULL
            """,
        }
        for name, definition in definitions.items():
            with self.subTest(name=name):
                connection = self._connection()
                try:
                    self._install_version_four_schema(connection)
                    connection.execute(
                        """
                        ALTER TABLE intelligence_runs
                        ADD COLUMN marketplace_snapshot_id TEXT
                            REFERENCES marketplace_snapshots(snapshot_id)
                            ON UPDATE RESTRICT
                            ON DELETE RESTRICT
                        """
                    )
                    connection.execute(definition)
                    connection.commit()
                    with patch(
                        "dip.persistence.sqlite.migrations.runner._discover_migrations",
                        return_value=[provenance_migration],
                    ):
                        with self.assertRaisesRegex(RuntimeError, "Migration 5"):
                            run_migrations(connection)
                    self.assertIsNone(
                        connection.execute(
                            """
                            SELECT version FROM schema_migrations
                            WHERE version = 5
                            """
                        ).fetchone()
                    )
                finally:
                    connection.close()

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

    @classmethod
    def _install_version_four_schema(
        cls,
        connection: sqlite3.Connection,
    ) -> None:
        cls._install_version_one_schema(connection)
        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[
                intelligence_history_migration,
                marketplace_history_migration,
                projects_migration,
            ],
        ):
            run_migrations(connection)

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
                ("marketplace_snapshot_id", "TEXT", 0),
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
        self.assertEqual(
            signature["intelligence_runs"]["foreign_keys"],
            (
                (
                    "marketplace_snapshot_id",
                    "marketplace_snapshots",
                    "snapshot_id",
                    "RESTRICT",
                ),
            ),
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
                "idx_intelligence_runs_marketplace_snapshot": (
                    "marketplace_snapshot_id",
                ),
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
                "sql": re.sub(
                    r"\s+([,)])",
                    r"\1",
                    re.sub(r"\s*,\s*", ", ", " ".join(table_sql.split())),
                ),
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
