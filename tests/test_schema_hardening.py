from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from dip.persistence.sqlite import Database
from dip.persistence.sqlite.migrations.versions import (
    v005_add_intelligence_marketplace_provenance as migration_5,
)
from dip.persistence.sqlite.migrations.versions import (
    v006_add_weekend_review_queue as migration_6,
)
from dip.persistence.sqlite.schema import (
    SchemaIntegrityError,
    initialise_schema,
)
from tests.fixtures.v0_4_0_schema import SCHEMA_SQL


class SchemaHardeningTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_fresh_and_current_initialization_validate_without_session_row(
        self,
    ) -> None:
        path = self.root / "fresh.db"
        database = Database(path)
        database.close()
        with self._connection(path) as connection:
            initialise_schema(connection)
            self.assertEqual(self._versions(connection), tuple(range(1, 8)))
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM desktop_session"
                ).fetchone()[0],
                0,
            )

    def test_registered_missing_objects_are_rejected_without_repair(self) -> None:
        cases = (
            (
                "provenance_index",
                "DROP INDEX idx_intelligence_runs_marketplace_snapshot",
                "index",
                "idx_intelligence_runs_marketplace_snapshot",
            ),
            (
                "queue",
                "DROP TABLE weekend_review_queue",
                "table",
                "weekend_review_queue",
            ),
            (
                "session",
                "DROP TABLE desktop_session",
                "table",
                "desktop_session",
            ),
        )
        for name, mutation, object_type, object_name in cases:
            with self.subTest(name=name):
                path = self.root / f"{name}.db"
                database = Database(path)
                database.conn.execute(
                    "INSERT INTO releases(release_id, artist) VALUES (7, 'A')"
                )
                database.conn.commit()
                database.close()
                with self._connection(path) as connection:
                    connection.execute(mutation)
                    connection.commit()
                    with self.assertRaises(SchemaIntegrityError):
                        initialise_schema(connection)
                    self.assertIsNone(
                        connection.execute(
                            """
                            SELECT 1 FROM sqlite_schema
                            WHERE type = ? AND name = ?
                            """,
                            (object_type, object_name),
                        ).fetchone()
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT artist FROM releases WHERE release_id=7"
                        ).fetchone()[0],
                        "A",
                    )
                    self.assertEqual(
                        self._versions(connection),
                        tuple(range(1, 8)),
                    )

    def test_altered_session_constraint_is_rejected(self) -> None:
        path = self.root / "constraint.db"
        database = Database(path)
        database.close()
        with self._connection(path) as connection:
            connection.execute("DROP TABLE desktop_session")
            connection.execute(
                """
                CREATE TABLE desktop_session (
                    singleton_id INTEGER PRIMARY KEY,
                    format_version INTEGER NOT NULL
                )
                """
            )
            connection.commit()
            with self.assertRaises(SchemaIntegrityError):
                initialise_schema(connection)

    def test_registered_provenance_column_and_queue_index_corruption_fail(
        self,
    ) -> None:
        provenance = self.root / "provenance-column.db"
        database = Database(provenance)
        database.close()
        with self._connection(provenance) as connection:
            connection.execute(
                "DROP INDEX idx_intelligence_runs_marketplace_snapshot"
            )
            connection.execute(
                """
                ALTER TABLE intelligence_runs
                DROP COLUMN marketplace_snapshot_id
                """
            )
            connection.commit()
            with self.assertRaises(SchemaIntegrityError):
                initialise_schema(connection)
            self.assertNotIn(
                "marketplace_snapshot_id",
                {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(intelligence_runs)"
                    )
                },
            )

        queue = self.root / "queue-index.db"
        database = Database(queue)
        database.close()
        with self._connection(queue) as connection:
            connection.execute(
                "DROP INDEX idx_weekend_review_queue_status_order"
            )
            connection.execute(
                """
                CREATE INDEX idx_weekend_review_queue_status_order
                ON weekend_review_queue(added_at)
                """
            )
            connection.commit()
            with self.assertRaises(SchemaIntegrityError):
                initialise_schema(connection)

    def test_compatible_current_object_without_record_is_validated_and_registered(
        self,
    ) -> None:
        path = self.root / "missing-record.db"
        database = Database(path)
        database.close()
        with self._connection(path) as connection:
            connection.execute(
                "DELETE FROM schema_migrations WHERE version=7"
            )
            connection.commit()
            initialise_schema(connection)
            self.assertEqual(self._versions(connection), tuple(range(1, 8)))

    def test_partial_schema_without_migration_baseline_fails_closed(self) -> None:
        path = self.root / "partial.db"
        with self._connection(path) as connection:
            connection.execute(
                "CREATE TABLE releases(release_id INTEGER PRIMARY KEY)"
            )
            connection.execute(
                "INSERT INTO releases(release_id) VALUES (7)"
            )
            connection.commit()
            with self.assertRaises(SchemaIntegrityError):
                initialise_schema(connection)
            self.assertIsNone(
                connection.execute(
                    """
                    SELECT 1 FROM sqlite_schema
                    WHERE type='table' AND name='schema_migrations'
                    """
                ).fetchone()
            )
            self.assertEqual(
                connection.execute(
                    "SELECT release_id FROM releases"
                ).fetchone()[0],
                7,
            )

    def test_genuine_v5_and_v6_states_upgrade_to_current(self) -> None:
        for version in (5, 6):
            with self.subTest(version=version):
                path = self.root / f"v{version}.db"
                with self._connection(path) as connection:
                    connection.executescript(SCHEMA_SQL)
                    connection.execute(
                        """
                        ALTER TABLE schema_migrations
                        ADD COLUMN name TEXT NOT NULL DEFAULT ''
                        """
                    )
                    connection.execute(
                        """
                        INSERT INTO schema_migrations(version, name)
                        VALUES (2, ''), (3, ''), (4, '')
                        """
                    )
                    migration_5.migration.upgrade(connection)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations(version, name)
                        VALUES (5, ?)
                        """,
                        (migration_5.migration.name,),
                    )
                    if version == 6:
                        migration_6.migration.upgrade(connection)
                        connection.execute(
                            """
                            INSERT INTO schema_migrations(version, name)
                            VALUES (6, ?)
                            """,
                            (migration_6.migration.name,),
                        )
                    connection.commit()
                    initialise_schema(connection)
                    self.assertEqual(
                        self._versions(connection),
                        tuple(range(1, 8)),
                    )

    @staticmethod
    def _connection(path: Path):
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)

    @staticmethod
    def _versions(connection: sqlite3.Connection) -> tuple[int, ...]:
        return tuple(
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        )


if __name__ == "__main__":
    unittest.main()
