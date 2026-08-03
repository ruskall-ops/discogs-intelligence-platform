from __future__ import annotations

import codecs
import tempfile
import unittest
from pathlib import Path

from dip.collection.importers import (
    CollectionImportError,
    CollectionImportResult,
    DiscogsCSVImporter,
)
from dip.collection.services import ImportService
from dip.persistence.sqlite import Database


MINIMAL_HEADER = "Release ID,Artist,Title"
STANDARD_HEADER = (
    "Catalog#,Artist,Title,Label,Format,Rating,Released,release_id,"
    "CollectionFolder,Date Added,Collection Media Condition,"
    "Collection Sleeve Condition,Collection Notes"
)


class CSVImportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _csv(self, text: str, *, bom: bool = False, name: str = "collection.csv") -> Path:
        data = text.encode("utf-8")
        if bom:
            data = codecs.BOM_UTF8 + data
        path = self.root / name
        path.write_bytes(data)
        return path

    def _database(self, name: str = "collection.sqlite3") -> Database:
        return Database(self.root / name)

    def test_minimal_utf8_csv_supports_lf_crlf_and_optional_bom(self) -> None:
        for line_ending in ("\n", "\r\n"):
            for bom in (False, True):
                with self.subTest(line_ending=repr(line_ending), bom=bom):
                    path = self._csv(
                        line_ending.join((MINIMAL_HEADER, "101,Artist,Title", "")),
                        bom=bom,
                        name=f"minimal-{len(line_ending)}-{bom}.csv",
                    )

                    result = DiscogsCSVImporter().read(path)

                    self.assertEqual(result.release_id_column, "Release ID")
                    self.assertEqual(result.total_rows, 1)
                    self.assertEqual(result.valid_release_ids, 1)
                    self.assertEqual(result.invalid_release_ids, 0)

    def test_genuine_discogs_style_headers_are_supported(self) -> None:
        path = self._csv(
            STANDARD_HEADER
            + "\r\nCAT,Artist,Title,Label,Vinyl,5,1999,202,Folder,"
            "2026-08-01,Mint,Mint,\r\n"
        )

        result = DiscogsCSVImporter().read(path)

        self.assertEqual(result.release_id_column, "release_id")
        self.assertEqual(result.total_rows, 1)
        self.assertEqual(result.valid_release_ids, 1)

    def test_quoted_commas_escaped_quotes_and_embedded_newlines_are_supported(self) -> None:
        path = self._csv(
            MINIMAL_HEADER
            + '\n101,"Artist, Name","A ""Quoted"" Title\nSecond Line"\n'
        )

        result = DiscogsCSVImporter().read(path)

        self.assertEqual(result.total_rows, 1)
        self.assertEqual(result.valid_release_ids, 1)
        self.assertEqual(result.invalid_release_ids, 0)

    def test_blank_physical_lines_are_ignored(self) -> None:
        path = self._csv(
            MINIMAL_HEADER + "\n\n202,Artist,Title\n\n"
        )

        result = DiscogsCSVImporter().read(path)

        self.assertEqual(result.total_rows, 1)
        self.assertEqual(result.valid_release_ids, 1)

    def test_empty_file_uses_missing_header_failure(self) -> None:
        path = self._csv("")

        with self.assertRaises(CollectionImportError) as raised:
            DiscogsCSVImporter().read(path)

        self.assertIn("No Discogs release ID column was found", str(raised.exception))

    def test_header_only_file_imports_zero_rows(self) -> None:
        path = self._csv(MINIMAL_HEADER + "\n")
        database = self._database()
        self.addCleanup(database.close)

        summary = ImportService(database).import_collection(path)

        self.assertEqual(summary.imported_records, 0)
        self.assertEqual(summary.total_rows, 0)
        self.assertEqual(database.release_ids(), [])

    def test_missing_release_id_header_is_rejected(self) -> None:
        path = self._csv("Artist,Title\nArtist,Title\n")

        with self.assertRaises(CollectionImportError):
            DiscogsCSVImporter().read(path)

    def test_invalid_release_identity_is_reported_and_skipped(self) -> None:
        path = self._csv(
            MINIMAL_HEADER
            + "\ninvalid,Artist,Title\n303,Artist,Title\n"
        )
        database = self._database()
        self.addCleanup(database.close)

        summary = ImportService(database).import_collection(path)

        self.assertEqual(summary.total_rows, 2)
        self.assertEqual(summary.valid_release_ids, 1)
        self.assertEqual(summary.invalid_release_ids, 1)
        self.assertEqual(summary.imported_records, 1)
        self.assertEqual(database.release_ids(), [303])

    def test_boolean_like_release_identities_are_invalid(self) -> None:
        path = self._csv(
            MINIMAL_HEADER
            + "\ntrue,Artist,Title\nfalse,Artist,Title\n303,Artist,Title\n"
        )
        database = self._database()
        self.addCleanup(database.close)

        summary = ImportService(database).import_collection(path)

        self.assertEqual(summary.valid_release_ids, 1)
        self.assertEqual(summary.invalid_release_ids, 2)
        self.assertEqual(summary.imported_records, 1)
        self.assertEqual(database.release_ids(), [303])

    def test_malformed_row_width_is_rejected_without_row_data(self) -> None:
        for name, row in (
            ("extra", "404,Artist,Title,Unexpected"),
            ("missing", "404,Artist"),
        ):
            with self.subTest(name=name):
                path = self._csv(
                    MINIMAL_HEADER + "\n" + row + "\n",
                    name=f"{name}.csv",
                )

                with self.assertRaises(CollectionImportError) as raised:
                    DiscogsCSVImporter().read(path)

                self.assertEqual(
                    str(raised.exception),
                    "The CSV rows do not match the header structure.",
                )

    def test_duplicate_release_ids_aggregate_ownership_quantity(self) -> None:
        path = self._csv(
            MINIMAL_HEADER
            + "\n505,Artist,Title\n505,Artist,Title\n606,Artist,Title\n"
        )
        database = self._database()
        self.addCleanup(database.close)

        summary = ImportService(database).import_collection(path)
        quantities = database.conn.execute(
            "SELECT quantity FROM collection_ownership ORDER BY release_id"
        ).fetchall()

        self.assertEqual(summary.imported_records, 3)
        self.assertEqual([row["quantity"] for row in quantities], [2, 1])

    def test_complete_import_is_durable_after_reopen(self) -> None:
        path = self._csv(
            MINIMAL_HEADER
            + "\n707,Artist,Title\n808,Artist,Title\n"
        )
        database_path = self.root / "durable.sqlite3"
        database = Database(database_path)

        summary = ImportService(database).import_collection(path)
        database.close()
        reopened = Database(database_path)
        self.addCleanup(reopened.close)

        self.assertEqual(summary.imported_records, 2)
        self.assertEqual(
            self._durable_counts(reopened),
            {
                "releases": 2,
                "collection_ownership": 2,
                "decisions": 2,
                "analysis_runs": 0,
                "marketplace_snapshots": 0,
                "desktop_session": 0,
            },
        )

    def test_import_failure_rolls_back_all_collection_writes(self) -> None:
        class FailingRowsImporter:
            def read(self, path: Path) -> CollectionImportResult:
                return CollectionImportResult(
                    rows=[
                        {"Release ID": "909", "Artist": "Artist", "Title": "Title"},
                        {
                            "Release ID": str(2**100),
                            "Artist": "Artist",
                            "Title": "Title",
                        },
                    ],
                    release_id_column="Release ID",
                    total_rows=2,
                    valid_release_ids=2,
                    invalid_release_ids=0,
                )

        database = self._database()
        self.addCleanup(database.close)

        with self.assertRaises(OverflowError):
            ImportService(database, FailingRowsImporter()).import_collection(
                self.root / "unused.csv"
            )

        self.assertEqual(
            self._durable_counts(database),
            {
                "releases": 0,
                "collection_ownership": 0,
                "decisions": 0,
                "analysis_runs": 0,
                "marketplace_snapshots": 0,
                "desktop_session": 0,
            },
        )

    @staticmethod
    def _durable_counts(database: Database) -> dict[str, int]:
        tables = (
            "releases",
            "collection_ownership",
            "decisions",
            "analysis_runs",
            "marketplace_snapshots",
            "desktop_session",
        )
        return {
            table: int(
                database.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            for table in tables
        }


if __name__ == "__main__":
    unittest.main()
