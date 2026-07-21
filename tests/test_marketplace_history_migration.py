from __future__ import annotations

import sqlite3
import unittest

from dip.persistence.sqlite.migrations.runner import run_migrations
from dip.persistence.sqlite.schema import SCHEMA_PATH


class MarketplaceHistoryMigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = self._connection()

    def tearDown(self) -> None:
        self.connection.close()

    def test_genuine_version_two_schema_upgrades_once_and_preserves_data(self) -> None:
        self._install_version_two_schema(self.connection)
        self._insert_existing_data(self.connection)

        applied = run_migrations(self.connection)

        self.assertEqual(tuple(item.version for item in applied), (3,))
        self.assertIn("Marketplace History", applied[0].name)
        self._assert_marketplace_history_schema(self.connection)
        self.assertEqual(
            self.connection.execute(
                "SELECT artist FROM releases WHERE release_id = 101"
            ).fetchone()[0],
            "Existing Artist",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT wants FROM market_snapshots WHERE release_id = 101"
            ).fetchone()[0],
            41,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT summary FROM intelligence_results WHERE module_id = ?",
                ("collection_health",),
            ).fetchone()[0],
            "Existing intelligence.",
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM marketplace_snapshots"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            {
                row["version"]
                for row in self.connection.execute(
                    "SELECT version FROM schema_migrations"
                ).fetchall()
            },
            {1, 2, 3},
        )

        self.assertEqual(run_migrations(self.connection), [])
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = 3"
            ).fetchone()[0],
            1,
        )

    def test_current_schema_and_version_three_migration_are_equivalent(self) -> None:
        self._install_version_two_schema(self.connection)
        run_migrations(self.connection)
        migrated_signature = self._schema_signature(self.connection)

        current = self._connection()
        try:
            current.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            current_signature = self._schema_signature(current)
        finally:
            current.close()

        self.assertEqual(migrated_signature, current_signature)

    def test_snapshot_id_is_unique_and_index_order_is_explicit(self) -> None:
        self._install_version_two_schema(self.connection)
        run_migrations(self.connection)

        insert = """
            INSERT INTO marketplace_snapshots (
                snapshot_id,
                captured_at,
                source,
                status,
                schema_version,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """
        values = (
            "snapshot-1",
            "2026-07-21T12:00:00.000000+00:00",
            "discogs",
            "empty",
            1,
            "{}",
        )
        self.connection.execute(insert, values)

        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(insert, values)

        index_rows = self.connection.execute(
            "PRAGMA index_xinfo(idx_marketplace_snapshots_captured)"
        ).fetchall()
        ordered_columns = tuple(
            (row["name"], row["desc"])
            for row in index_rows
            if row["key"] == 1
        )
        self.assertEqual(
            ordered_columns,
            (("captured_at", 1), ("snapshot_id", 1)),
        )

    def test_incompatible_preexisting_table_is_not_recorded_as_migrated(self) -> None:
        self._install_version_two_schema(self.connection)
        self.connection.execute(
            """
            CREATE TABLE marketplace_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                captured_at TEXT,
                source TEXT,
                status TEXT,
                schema_version INTEGER,
                payload_json BLOB
            )
            """
        )
        self.connection.commit()

        with self.assertRaisesRegex(RuntimeError, "Migration 3"):
            run_migrations(self.connection)

        self.assertIsNone(
            self.connection.execute(
                "SELECT version FROM schema_migrations WHERE version = 3"
            ).fetchone()
        )
        self.assertIsNone(
            self.connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'index'
                  AND name = 'idx_marketplace_snapshots_captured'
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
    def _install_version_two_schema(connection: sqlite3.Connection) -> None:
        current_schema = SCHEMA_PATH.read_text(encoding="utf-8")
        version_two_schema, marker, _ = current_schema.partition(
            "CREATE TABLE IF NOT EXISTS marketplace_snapshots"
        )
        if not marker:
            raise AssertionError("Unable to locate Marketplace History schema")
        connection.executescript(version_two_schema)
        connection.executemany(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            ((1,), (2,)),
        )
        connection.commit()

    @staticmethod
    def _insert_existing_data(connection: sqlite3.Connection) -> None:
        connection.execute(
            "INSERT INTO releases(release_id, artist) VALUES (?, ?)",
            (101, "Existing Artist"),
        )
        connection.execute(
            """
            INSERT INTO market_snapshots (
                release_id,
                captured_at,
                wants,
                haves,
                copies_for_sale,
                lowest_price
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (101, "2026-07-20T12:00:00+00:00", 41, 12, 3, 10.5),
        )
        run_id = connection.execute(
            """
            INSERT INTO intelligence_runs (
                executed_at,
                executed_at_json,
                result_count
            )
            VALUES (?, ?, ?)
            """,
            (
                "2026-07-20T12:00:00.000000+00:00",
                '{"__dip_type__":"datetime","value":"2026-07-20T12:00:00+00:00"}',
                1,
            ),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO intelligence_results (
                run_id,
                module_id,
                status_json,
                summary,
                insights_json,
                metrics_json,
                evidence_json,
                diagnostics_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "collection_health",
                '"completed"',
                "Existing intelligence.",
                '{"__dip_type__":"tuple","items":[]}',
                '{"__dip_type__":"mapping","items":[]}',
                '{"__dip_type__":"tuple","items":[]}',
                '{"__dip_type__":"tuple","items":[]}',
            ),
        )
        connection.commit()

    def _assert_marketplace_history_schema(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        signature = self._schema_signature(connection)
        self.assertEqual(
            signature["columns"],
            (
                ("snapshot_id", "TEXT", 1, 1),
                ("captured_at", "TEXT", 1, 0),
                ("source", "TEXT", 1, 0),
                ("status", "TEXT", 1, 0),
                ("schema_version", "INTEGER", 1, 0),
                ("payload_json", "TEXT", 1, 0),
            ),
        )
        self.assertEqual(signature["foreign_keys"], ())
        self.assertIn(("snapshot_id",), signature["unique_indexes"])
        self.assertEqual(
            signature["named_indexes"],
            {"idx_marketplace_snapshots_captured": ("captured_at", "snapshot_id")},
        )
        table_sql = signature["sql"]
        self.assertIn("CHECK (schema_version > 0)", table_sql)
        for status in ("complete", "partial", "empty", "unavailable", "failed"):
            self.assertIn(f"'{status}'", table_sql)

    @staticmethod
    def _schema_signature(connection: sqlite3.Connection) -> dict[str, object]:
        table = "marketplace_snapshots"
        columns = tuple(
            (row["name"], row["type"], row["notnull"], row["pk"])
            for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
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
        table_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        table_sql = "" if table_row is None else " ".join(table_row["sql"].split())
        unique_indexes = tuple(
            tuple(
                column["name"]
                for column in connection.execute(
                    f"PRAGMA index_info({row['name']})"
                ).fetchall()
            )
            for row in connection.execute(f"PRAGMA index_list({table})").fetchall()
            if row["unique"]
        )
        named_indexes = {
            row["name"]: tuple(
                column["name"]
                for column in connection.execute(
                    f"PRAGMA index_info({row['name']})"
                ).fetchall()
            )
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'index'
                  AND name LIKE 'idx_marketplace_snapshots_%'
                ORDER BY name
                """
            ).fetchall()
        }
        return {
            "columns": columns,
            "foreign_keys": foreign_keys,
            "sql": table_sql,
            "unique_indexes": unique_indexes,
            "named_indexes": named_indexes,
        }


if __name__ == "__main__":
    unittest.main()
