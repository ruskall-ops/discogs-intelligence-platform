from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from dip.persistence.sqlite.migrations.runner import run_migrations
from dip.persistence.sqlite.migrations.versions.v007_add_desktop_session import (
    _CREATE_TABLE_SQL,
    _validate_schema,
    migration,
)
from dip.persistence.sqlite.schema import SCHEMA_PATH


class SessionMigrationTestCase(unittest.TestCase):
    def setUp(self):
        self.connection = self._connection()

    def tearDown(self):
        self.connection.close()

    def test_genuine_version_six_upgrade_is_empty_and_preserves_data(self):
        self._install_version_six(self.connection)
        self.connection.execute(
            "INSERT INTO releases(release_id, artist) VALUES (7, 'Existing')"
        )
        self.connection.commit()
        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[migration],
        ):
            applied = run_migrations(self.connection)
        self.assertEqual(tuple(value.version for value in applied), (7,))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM desktop_session"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT artist FROM releases WHERE release_id=7"
            ).fetchone()["artist"],
            "Existing",
        )
        self.assertIsNotNone(
            self.connection.execute(
                "SELECT version FROM schema_migrations WHERE version=7"
            ).fetchone()
        )

    def test_fresh_and_migrated_schema_are_equivalent(self):
        self._install_version_six(self.connection)
        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[migration],
        ):
            run_migrations(self.connection)
        migrated = self._signature(self.connection)
        fresh = self._connection()
        try:
            fresh.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            current = self._signature(fresh)
        finally:
            fresh.close()
        self.assertEqual(migrated, current)

    def test_incompatible_existing_table_rolls_back_version(self):
        self._install_version_six(self.connection)
        self.connection.execute(
            "CREATE TABLE desktop_session(singleton_id INTEGER PRIMARY KEY)"
        )
        self.connection.commit()
        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[migration],
        ):
            with self.assertRaisesRegex(RuntimeError, "Migration 7"):
                run_migrations(self.connection)
        self.assertIsNone(
            self.connection.execute(
                "SELECT version FROM schema_migrations WHERE version=7"
            ).fetchone()
        )

    def test_exact_contract_rejects_weakened_added_and_changed_constraints(self):
        mutations = (
            ("CHECK (format_version = 1)", "CHECK (format_version >= 1)"),
            (
                "window_width BETWEEN 1050 AND 32767",
                "window_width BETWEEN 800 AND 32767",
            ),
            ("'hidden_gem'", "'hidden_candidate'"),
            (
                "CHECK (\n        (selected_observation_source IS NULL)",
                "CHECK (1),\n    CHECK (\n        "
                "(selected_observation_source IS NULL)",
            ),
            (
                "selected_decision_release_id > 0",
                "selected_decision_release_id >= 0",
            ),
        )
        for old, new in mutations:
            with self.subTest(old=old):
                connection = self._connection()
                try:
                    mutant = _CREATE_TABLE_SQL.replace(old, new, 1)
                    self.assertNotEqual(mutant, _CREATE_TABLE_SQL)
                    connection.execute(mutant)
                    with self.assertRaises(sqlite3.OperationalError):
                        _validate_schema(connection)
                finally:
                    connection.close()

    def test_mutated_migration_contract_rolls_back_table_version_and_data(self):
        mutations = (
            ("singleton_id INTEGER PRIMARY KEY", "singleton_id INTEGER"),
            ("CHECK (singleton_id = 1)", "CHECK (singleton_id >= 1)"),
            ("CHECK (singleton_id = 1)", ""),
            ("format_version = 1", "format_version = 2"),
            ("window_height BETWEEN 650 AND 32767",
             "window_height BETWEEN 600 AND 32767"),
            ("window_x BETWEEN -2147483648 AND 2147483647",
             "window_x BETWEEN -1 AND 1"),
            ("'hidden_gem'", "'hidden_gem', 'other'"),
            ("'hot_now', 'hidden_gem'", "'hot_now'"),
            ("selected_queue_item_id > 0", "selected_queue_item_id >= 0"),
            (
                "(selected_observation_release_id IS NULL)\n    )",
                "(selected_observation_release_id IS NOT NULL)\n    )",
            ),
            (
                "CHECK (format_version = 1)",
                "CHECK (format_version = 1 AND window_width > 0)",
            ),
            (
                "CHECK (format_version = 1)",
                "CHECK (format_version = 1 OR window_width > 0)",
            ),
            (
                "CHECK (format_version = 1)",
                "CHECK (format_version = 1), CHECK (format_version = 2)",
            ),
            (
                "saved_at TEXT NOT NULL",
                "saved_at TEXT NOT NULL, unexpected TEXT",
            ),
            (
                "    selected_decision_release_id INTEGER\n"
                "        CHECK (\n"
                "            selected_decision_release_id IS NULL\n"
                "            OR selected_decision_release_id > 0\n"
                "        ),\n",
                "",
            ),
            (
                "selected_decision_release_id INTEGER",
                "selected_decision_release_id TEXT",
            ),
        )
        for old, new in mutations:
            with self.subTest(old=old, new=new):
                connection = self._connection()
                try:
                    self._install_version_six(connection)
                    connection.execute(
                        "INSERT INTO releases(release_id, artist) "
                        "VALUES (7, 'Existing')"
                    )
                    connection.commit()
                    mutant = _CREATE_TABLE_SQL.replace(old, new, 1)
                    self.assertNotEqual(mutant, _CREATE_TABLE_SQL)
                    def apply_mutant(target, sql=mutant):
                        target.execute(sql)
                        _validate_schema(target)

                    with patch.object(
                        migration,
                        "upgrade",
                        side_effect=apply_mutant,
                    ), patch(
                        "dip.persistence.sqlite.migrations.runner."
                        "_discover_migrations",
                        return_value=[migration],
                    ):
                        with self.assertRaises(RuntimeError):
                            run_migrations(connection)
                    self.assertIsNone(
                        connection.execute(
                            "SELECT 1 FROM sqlite_master "
                            "WHERE type='table' AND name='desktop_session'"
                        ).fetchone()
                    )
                    self.assertIsNone(
                        connection.execute(
                            "SELECT 1 FROM schema_migrations WHERE version=7"
                        ).fetchone()
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT artist FROM releases WHERE release_id=7"
                        ).fetchone()["artist"],
                        "Existing",
                    )
                finally:
                    connection.close()

    def test_validator_rejects_added_foreign_key_and_index(self):
        foreign_key_sql = _CREATE_TABLE_SQL.replace(
            "active_project_id TEXT",
            "active_project_id TEXT REFERENCES projects(id)",
            1,
        )
        connection = self._connection()
        try:
            self._install_version_six(connection)
            connection.execute(foreign_key_sql)
            with self.assertRaises(sqlite3.OperationalError):
                _validate_schema(connection)
        finally:
            connection.close()

        connection = self._connection()
        try:
            connection.execute(_CREATE_TABLE_SQL)
            connection.execute(
                "CREATE INDEX unexpected_session_index "
                "ON desktop_session(saved_at)"
            )
            with self.assertRaises(sqlite3.OperationalError):
                _validate_schema(connection)
        finally:
            connection.close()

    def test_contract_has_no_foreign_keys_or_additional_indexes(self):
        self._install_version_six(self.connection)
        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[migration],
        ):
            run_migrations(self.connection)
        self.assertEqual(
            self.connection.execute(
                "PRAGMA foreign_key_list(desktop_session)"
            ).fetchall(),
            [],
        )
        self.assertEqual(
            tuple(
                row["name"]
                for row in self.connection.execute(
                    "PRAGMA index_list(desktop_session)"
                ).fetchall()
                if not row["name"].startswith("sqlite_autoindex")
            ),
            (),
        )

    @staticmethod
    def _connection():
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _install_version_six(connection):
        schema, marker, _ = SCHEMA_PATH.read_text(encoding="utf-8").partition(
            "CREATE TABLE IF NOT EXISTS desktop_session"
        )
        if not marker:
            raise AssertionError("Unable to find migration 7 schema boundary.")
        connection.executescript(schema)
        connection.executemany(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            tuple((value,) for value in range(1, 7)),
        )
        connection.commit()

    @staticmethod
    def _signature(connection):
        row = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='desktop_session'
            """
        ).fetchone()
        return {
            "sql": "".join(row["sql"].split()).lower(),
            "columns": tuple(
                tuple(value)
                for value in connection.execute(
                    "PRAGMA table_info(desktop_session)"
                ).fetchall()
            ),
            "foreign_keys": tuple(
                tuple(value)
                for value in connection.execute(
                    "PRAGMA foreign_key_list(desktop_session)"
                ).fetchall()
            ),
            "indexes": tuple(
                tuple(value)
                for value in connection.execute(
                    "PRAGMA index_list(desktop_session)"
                ).fetchall()
            ),
        }


if __name__ == "__main__":
    unittest.main()
