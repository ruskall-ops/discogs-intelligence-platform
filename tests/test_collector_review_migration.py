from __future__ import annotations

import sqlite3
import re
import unittest
from unittest.mock import patch

from dip.persistence.sqlite.migrations.runner import run_migrations
from dip.persistence.sqlite.migrations.versions.v006_add_weekend_review_queue import (
    _CREATE_TABLE_SQL,
    _canonical_create_table,
    migration,
)
from dip.persistence.sqlite.schema import SCHEMA_PATH


class CollectorReviewMigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = self._connection()

    def tearDown(self) -> None:
        self.connection.close()

    def test_genuine_version_five_upgrades_empty_and_preserves_existing_data(
        self,
    ) -> None:
        self._install_version_five(self.connection)
        self.connection.execute(
            "INSERT INTO releases(release_id, artist) VALUES (7, 'Existing')"
        )
        self.connection.commit()

        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[migration],
        ):
            applied = run_migrations(self.connection)

        self.assertEqual(tuple(item.version for item in applied), (6,))
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM weekend_review_queue"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT artist FROM releases WHERE release_id=7"
            ).fetchone()["artist"],
            "Existing",
        )
        self.assertEqual(
            tuple(
                row["version"]
                for row in self.connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            ),
            (1, 2, 3, 4, 5, 6),
        )

    def test_fresh_and_migrated_queue_schemas_are_equivalent(self) -> None:
        self._install_version_five(self.connection)
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

    def test_incompatible_table_rolls_back_index_and_version(self) -> None:
        self._install_version_five(self.connection)
        self.connection.execute(
            "CREATE TABLE weekend_review_queue(id INTEGER PRIMARY KEY)"
        )
        self.connection.commit()
        with patch(
            "dip.persistence.sqlite.migrations.runner._discover_migrations",
            return_value=[migration],
        ):
            with self.assertRaisesRegex(RuntimeError, "Migration 6"):
                run_migrations(self.connection)
        self.assertIsNone(
            self.connection.execute(
                "SELECT version FROM schema_migrations WHERE version=6"
            ).fetchone()
        )

    def test_canonicalizer_accepts_formatting_and_preserves_sql_literals(
        self,
    ) -> None:
        formatted = (
            _CREATE_TABLE_SQL.replace("CREATE TABLE", "create  table", 1)
            .replace("weekend_review_queue", '"weekend_review_queue"', 1)
            .rstrip()
            + " ; "
        )
        self.assertEqual(
            _canonical_create_table(formatted),
            _canonical_create_table(_CREATE_TABLE_SQL),
        )
        altered_literal = _CREATE_TABLE_SQL.replace(
            "'to_review'",
            "'TO_REVIEW'",
            1,
        )
        self.assertNotEqual(
            _canonical_create_table(altered_literal),
            _canonical_create_table(_CREATE_TABLE_SQL),
        )

    def test_every_constraint_mutation_is_rejected_without_version_advance(
        self,
    ) -> None:
        mutations = {
            "missing release check": (
                "CHECK (\n            typeof(release_id) = 'integer'\n"
                "            AND release_id > 0\n        )",
                "CHECK (1)",
            ),
            "extra or": (
                "AND release_id > 0",
                "AND (release_id > 0 OR release_id = 0)",
            ),
            "extra and": (
                "AND release_id > 0",
                "AND release_id > 0 AND release_id <> 99",
            ),
            "status value": ("'reviewing'", "'pending'"),
            "source value": ("'hidden_gem'", "'hidden_candidate'"),
            "resolved lifecycle": (
                "status <> 'resolved'\n            AND resolved_at IS NULL",
                "status <> 'resolved'",
            ),
            "source ordering": (
                "julianday(source_observed_at) <= julianday(added_at)",
                "julianday(source_observed_at) <= julianday(updated_at)",
            ),
            "updated ordering": (
                "julianday(added_at) <= julianday(updated_at)",
                "julianday(added_at) <= julianday(source_observed_at)",
            ),
            "hidden provenance": (
                "source_type <> 'hidden_gem'",
                "source_type = 'hidden_gem'",
            ),
            "hot provenance": (
                "source_type <> 'hot_now'",
                "source_type = 'hot_now'",
            ),
            "extra check": (
                "FOREIGN KEY (release_id)",
                "CHECK (release_id <> 42),\n    FOREIGN KEY (release_id)",
            ),
            "wrong function": ("julianday(added_at)", "date(added_at)"),
            "wrong column": (
                "length(trim(source_summary)) > 0",
                "length(trim(review_note)) > 0",
            ),
        }
        for name, (old, new) in mutations.items():
            with self.subTest(name=name):
                connection = self._connection()
                try:
                    self._install_version_five(connection)
                    mutant = _CREATE_TABLE_SQL.replace(old, new, 1)
                    self.assertNotEqual(mutant, _CREATE_TABLE_SQL)
                    connection.execute(mutant)
                    connection.commit()
                    with patch(
                        "dip.persistence.sqlite.migrations.runner._discover_migrations",
                        return_value=[migration],
                    ):
                        with self.assertRaisesRegex(RuntimeError, "Migration 6"):
                            run_migrations(connection)
                    self.assertIsNone(
                        connection.execute(
                            """
                            SELECT version FROM schema_migrations
                            WHERE version=6
                            """
                        ).fetchone()
                    )
                    self.assertIsNone(
                        connection.execute(
                            """
                            SELECT name FROM sqlite_master
                            WHERE type='index'
                              AND name='idx_weekend_review_queue_status_order'
                            """
                        ).fetchone()
                    )
                finally:
                    connection.close()

    def test_every_check_contract_is_required_as_a_complete_definition(
        self,
    ) -> None:
        check_count = _CREATE_TABLE_SQL.upper().count("CHECK")
        self.assertGreater(check_count, 10)
        for check_index in range(check_count):
            with self.subTest(check_index=check_index):
                connection = self._connection()
                try:
                    self._install_version_five(connection)
                    connection.execute(
                        _replace_check_with_noop(
                            _CREATE_TABLE_SQL,
                            check_index,
                        )
                    )
                    connection.commit()
                    with patch(
                        "dip.persistence.sqlite.migrations.runner._discover_migrations",
                        return_value=[migration],
                    ):
                        with self.assertRaisesRegex(RuntimeError, "Migration 6"):
                            run_migrations(connection)
                    self.assertIsNone(
                        connection.execute(
                            """
                            SELECT version FROM schema_migrations
                            WHERE version=6
                            """
                        ).fetchone()
                    )
                finally:
                    connection.close()
        self.assertIsNone(
            self.connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='index'
                  AND name='idx_weekend_review_queue_status_order'
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
    def _install_version_five(connection: sqlite3.Connection) -> None:
        schema, marker, _ = SCHEMA_PATH.read_text(encoding="utf-8").partition(
            "CREATE TABLE IF NOT EXISTS weekend_review_queue"
        )
        if not marker:
            raise AssertionError("Unable to locate migration 6 schema boundary.")
        connection.executescript(schema)
        connection.executemany(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            ((1,), (2,), (3,), (4,), (5,)),
        )
        connection.commit()

    @staticmethod
    def _signature(connection: sqlite3.Connection) -> dict[str, object]:
        table_sql = connection.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='weekend_review_queue'
            """
        ).fetchone()["sql"]
        return {
            "columns": tuple(
                (
                    row["name"],
                    row["type"],
                    row["notnull"],
                    row["dflt_value"],
                    row["pk"],
                )
                for row in connection.execute(
                    "PRAGMA table_info(weekend_review_queue)"
                ).fetchall()
            ),
            "foreign_keys": set(
                (
                    row["from"],
                    row["table"],
                    row["to"],
                    row["on_update"],
                    row["on_delete"],
                )
                for row in connection.execute(
                    "PRAGMA foreign_key_list(weekend_review_queue)"
                ).fetchall()
            ),
            "indexes": tuple(
                sorted(
                    (
                        row["name"],
                        row["unique"],
                        tuple(
                            column["name"]
                            for column in connection.execute(
                                f"PRAGMA index_info({row['name']})"
                            ).fetchall()
                        ),
                    )
                    for row in connection.execute(
                        "PRAGMA index_list(weekend_review_queue)"
                    ).fetchall()
                    if not row["name"].startswith("sqlite_autoindex")
                )
            ),
            "checks": re.sub(
                r"\s+",
                "",
                table_sql[table_sql.index("(") :],
            ),
        }


def _replace_check_with_noop(sql: str, target_index: int) -> str:
    upper = sql.upper()
    cursor = 0
    for current_index in range(target_index + 1):
        start = upper.find("CHECK", cursor)
        if start < 0:
            raise AssertionError("CHECK index is outside the canonical SQL.")
        cursor = start + len("CHECK")
    open_parenthesis = sql.find("(", cursor)
    if open_parenthesis < 0:
        raise AssertionError("CHECK has no opening parenthesis.")
    depth = 0
    in_literal = False
    index = open_parenthesis
    while index < len(sql):
        character = sql[index]
        if character == "'":
            if in_literal and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            in_literal = not in_literal
        elif not in_literal:
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return sql[:start] + "CHECK (1)" + sql[index + 1 :]
        index += 1
    raise AssertionError("CHECK has no balanced closing parenthesis.")


if __name__ == "__main__":
    unittest.main()
