from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dip.persistence.sqlite import Database


class DatabaseTestCase(unittest.TestCase):
    """Base tests for DIP's SQLite persistence layer."""

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temp_directory.name)
            / "test_discogs_intelligence.db"
        )
        self.database = Database(self.database_path)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_directory.cleanup()

    def test_schema_initialises_required_tables(self) -> None:
        rows = self.database.conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

        table_names = {
            str(row["name"])
            for row in rows
        }

        required_tables = {
            "releases",
            "collection_ownership",
            "market_snapshots",
            "analysis_runs",
            "scores",
            "decisions",
            "schema_migrations",
            "intelligence_runs",
            "intelligence_results",
            "marketplace_snapshots",
        }

        self.assertTrue(
            required_tables.issubset(table_names)
        )


    def test_migrations_are_only_applied_once(self) -> None:
        """Reopening the database should not duplicate migrations."""

        rows_before = self.database.conn.execute(
            """
            SELECT COUNT(*)
            FROM schema_migrations
            """
        ).fetchone()[0]

        self.database.close()

        self.database = Database(self.database_path)

        rows_after = self.database.conn.execute(
            """
            SELECT COUNT(*)
            FROM schema_migrations
            """
        ).fetchone()[0]

        self.assertEqual(rows_before, rows_after)

    def test_owned_portfolio_rows_are_complete_and_release_ordered(self) -> None:
        self.database.conn.executemany(
            "INSERT INTO releases (release_id, artist, title) VALUES (?, ?, ?)",
            ((20, "Artist", "Twenty"), (3, "Artist", "Three")),
        )
        self.database.conn.executemany(
            "INSERT INTO collection_ownership (release_id, quantity) VALUES (?, ?)",
            ((20, 2), (3, 1)),
        )

        rows = self.database.owned_portfolio_rows()

        self.assertEqual(
            tuple((row["release_id"], row["quantity"]) for row in rows),
            ((3, 1), (20, 2)),
        )

    def test_owned_portfolio_metadata_rows_preserve_canonical_release_values(self) -> None:
        self.database.conn.execute(
            """
            INSERT INTO releases (
                release_id, artist, title, label, format, released
            ) VALUES (7, 'Artist', 'Title', 'Label', 'Vinyl', '1984')
            """
        )
        self.database.conn.execute(
            "INSERT INTO collection_ownership (release_id, quantity) VALUES (7, 3)"
        )

        rows = self.database.owned_portfolio_metadata_rows()

        self.assertEqual(
            tuple(dict(value) for value in rows),
            ({
                "release_id": 7,
                "quantity": 3,
                "artist": "Artist",
                "label": "Label",
                "format": "Vinyl",
                "released": "1984",
            },),
        )


if __name__ == "__main__":
    unittest.main()
