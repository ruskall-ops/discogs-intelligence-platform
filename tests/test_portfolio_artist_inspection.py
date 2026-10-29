from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from dip.app.current_release_metadata import CurrentReleaseMetadata
from dip.app.portfolio_artist_inspection import PortfolioArtistInspectionService, LABEL_FAILURE, PortfolioDistributionDimension as Dimension
from dip.composition import build_desktop_application_dependencies
from dip.persistence.sqlite import Database, SQLiteCurrentReleaseMetadataRepository
from tests.test_current_collection_portfolio_presentation import _outcome, _row


def manifest(connection):
    schema = tuple(tuple(row) for row in connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
    tables = tuple(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
    return schema, tuple((name, tuple(sorted((tuple(row) for row in connection.execute('SELECT * FROM "' + name + '"')), key=repr))) for name in tables)


class ArtistInspectionTest(unittest.TestCase):
    def setUp(self):
        self.source = _outcome((_row(10, quantity=3, artist="A"), _row(20, quantity=2, artist="A"), _row(30, artist="B"), _row(40, artist=None)))[0].portfolio
        self.category = self.source.distribution.output.dimensions[0].entries[0]
        self.metadata = Mock()
        self.metadata.metadata_for_release_ids.return_value = (CurrentReleaseMetadata(10, "Changed artist", "Current title"),)
        self.service = PortfolioArtistInspectionService(self.metadata)

    def test_exact_retained_membership_quantities_totals_and_current_labels(self):
        result = self.service.inspect(self.source, self.category.category_id)
        self.assertIs(result.source, self.source)
        self.assertIs(result.category, self.category)
        self.assertEqual(tuple((value.release_id, value.copies_at_calculation) for value in result.members), ((10, 3), (20, 2)))
        self.assertEqual((result.category.unique_release_count, result.category.owned_copy_count, result.category.release_denominator, result.category.copy_denominator), (2, 5, 4, 7))
        self.assertEqual(result.members[0].current_metadata.artist, "Changed artist")
        self.assertIsNone(result.members[1].current_metadata)
        self.assertEqual(result.label_error, "")
        self.metadata.metadata_for_release_ids.assert_called_once_with((10, 20))
        with self.assertRaises(FrozenInstanceError):
            result.members[0].release_id = 99

    def test_unknown_category_and_invalid_source_do_not_query(self):
        for source, category in ((None, "x"), (self.source, "not retained"), (self.source, True)):
            with self.assertRaises((TypeError, ValueError)):
                self.service.inspect(source, category)
        self.metadata.metadata_for_release_ids.assert_not_called()

    def test_malformed_lookups_never_publish_a_successful_partial_result(self):
        good = CurrentReleaseMetadata(10, "A", "T")
        for values in ((good, good), (good, CurrentReleaseMetadata(999, "A", "T")), (good, object()), [good], (CurrentReleaseMetadata(20, "A", "T"), good)):
            with self.subTest(values=values):
                self.metadata.metadata_for_release_ids.return_value = values
                result = self.service.inspect(self.source, self.category.category_id)
                self.assertEqual(result.label_error, LABEL_FAILURE)
                self.assertEqual(tuple(value.release_id for value in result.members), (10, 20))
                self.assertTrue(all(value.current_metadata is None for value in result.members))

    def test_failed_lookup_preserves_all_members_and_safe_copy(self):
        self.metadata.metadata_for_release_ids.side_effect = RuntimeError("secret SQL path")
        result = self.service.inspect(self.source, self.category.category_id)
        self.assertEqual(result.label_error, LABEL_FAILURE)
        self.assertNotIn("secret", result.label_error)
        self.assertEqual(tuple(value.copies_at_calculation for value in result.members), (3, 2))

    def test_immutable_inspection_rejects_contradictory_membership_or_quantities(self):
        result=self.service.inspect(self.source,self.category.category_id)
        for members in (result.members[:-1],tuple(reversed(result.members)),(replace(result.members[0],copies_at_calculation=99),result.members[1])):
            with self.assertRaises(ValueError):replace(result,members=members)
        with self.assertRaises(ValueError):replace(result,label_error="raw exception")
        with self.assertRaises(ValueError):replace(result,label_error=LABEL_FAILURE)
        with self.assertRaises(ValueError):replace(result.members[0],current_metadata=CurrentReleaseMetadata(99,"A","T"))

    def test_null_labels_are_distinct_from_a_missing_record(self):
        self.metadata.metadata_for_release_ids.return_value = (CurrentReleaseMetadata(10, None, None),)
        result = self.service.inspect(self.source, self.category.category_id)
        self.assertIsNotNone(result.members[0].current_metadata)
        self.assertIsNone(result.members[1].current_metadata)

    def test_real_production_composition_reads_without_writes_and_reopens(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.sqlite3"
            from dip.composition import SETTINGS
            with patch("dip.composition.SETTINGS", replace(SETTINGS, database_path=path)), patch("dip.composition.DiscogsClient", side_effect=AssertionError("provider forbidden")) as provider, patch("socket.socket.connect", side_effect=AssertionError("network forbidden")) as network:
                dependencies = build_desktop_application_dependencies()
                database = dependencies.database
                try:
                    database.conn.executemany("INSERT INTO releases(release_id,artist,title,label,format,released) VALUES (?, ?, ?, ?, ?, ?)", ((10, "A", "First", "Shared", "Vinyl", "1991"), (20, "A", "Second", "Other", "CD", "2001"), (30, "B", "Third", "Shared", "Vinyl", "2005")))
                    database.conn.executemany("INSERT INTO collection_ownership(release_id,quantity) VALUES (?, ?)", ((10, 3), (20, 2), (30, 1)))
                    database.conn.commit()
                    before = manifest(database.conn)
                    changes = database.conn.total_changes
                    statements = []
                    database.conn.set_trace_callback(statements.append)
                    outcome = dependencies.current_collection_portfolio_execution.execute()
                    self.assertTrue(outcome.succeeded)
                    category = outcome.portfolio.distribution.output.dimensions[0].entries[0]
                    result = dependencies.portfolio_artist_inspection.inspect(outcome.portfolio, category.category_id)
                    self.assertEqual(tuple((v.release_id, v.copies_at_calculation) for v in result.members), ((10, 3), (20, 2)))
                    self.assertEqual(result.members[1].current_metadata.title, "Second")
                    expected = {
                        Dimension.ARTIST: (("A", (10,20), 5), ("B", (30,), 1)),
                        Dimension.LABEL: (("Shared", (10,30), 4), ("Other", (20,), 2)),
                        Dimension.FORMAT: (("Vinyl", (10,30), 4), ("CD", (20,), 2)),
                        Dimension.RELEASE_YEAR: (("1991", (10,), 3), ("2001", (20,), 2), ("2005", (30,), 1)),
                        Dimension.DECADE: (("1990", (10,), 3), ("2000", (20,30), 3)),
                    }
                    for dimension in outcome.portfolio.distribution.output.dimensions:
                        self.assertEqual(tuple((c.category_id,c.release_ids,c.owned_copy_count) for c in dimension.entries), expected[dimension.dimension])
                        for category in dimension.entries:
                            inspected = dependencies.portfolio_artist_inspection.inspect(outcome.portfolio, category.category_id, dimension=dimension.dimension)
                            self.assertIs(inspected.source, outcome.portfolio)
                            self.assertIs(inspected.category, category)
                            self.assertEqual(tuple(m.release_id for m in inspected.members), category.release_ids)
                            self.assertEqual((category.release_denominator,category.copy_denominator), (3,6))
                            self.assertEqual(sum(m.copies_at_calculation for m in inspected.members), category.owned_copy_count)
                            self.assertEqual(inspected.label_error, "")
                            self.assertTrue(all(m.current_metadata is not None for m in inspected.members))
                    self.assertEqual(database.conn.total_changes, changes)
                    self.assertFalse(any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT")) for sql in statements))
                    self.assertEqual(manifest(database.conn), before)
                    self.assertFalse(database.conn.in_transaction)
                    provider.assert_not_called()
                    network.assert_not_called()
                finally:
                    database.close()
                with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as reopened:
                    self.assertEqual(manifest(reopened), before)
                    self.assertEqual(reopened.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                    self.assertEqual(reopened.execute("PRAGMA quick_check").fetchone()[0], "ok")
                    self.assertEqual(reopened.execute("PRAGMA foreign_key_check").fetchall(), [])
                    self.assertEqual([row[0] for row in reopened.execute("SELECT version FROM schema_migrations ORDER BY version")], list(range(1, 8)))
                self.assertEqual(tuple(Path(directory).iterdir()), (path,))

    def test_metadata_lookup_batches_without_losing_large_membership(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory)/"synthetic.sqlite3")
            try:
                database.conn.executemany("INSERT INTO releases(release_id,artist,title) VALUES (?, 'Current', 'Title')", ((value,) for value in range(1, 1002)))
                database.conn.commit()
                source = _outcome(tuple(_row(value, artist="Retained") for value in range(1,1002)))[0].portfolio
                service = PortfolioArtistInspectionService(SQLiteCurrentReleaseMetadataRepository(database))
                result = service.inspect(source, source.distribution.output.dimensions[0].entries[0].category_id)
                self.assertEqual(tuple(value.release_id for value in result.members), tuple(range(1, 1002)))
                self.assertTrue(all(value.current_metadata.artist == "Current" for value in result.members))
            finally:
                database.close()


class DimensionInspectionTest(unittest.TestCase):
    def setUp(self):
        self.source = _outcome((
            _row(10, quantity=3, artist="Shared", label="Other", format_value='12"', released="1991"),
            _row(20, quantity=2, artist="Other", label="Shared", format_value="CD", released="2001"),
            _row(30, artist="Shared", label="Shared", format_value='12"', released="2005"),
            _row(40, artist=None, label=None, format_value=None, released=None),
            _row(50, quantity=4, artist="2000", label="2000", format_value="2000", released="2000"),
        ))[0].portfolio
        self.metadata = Mock()
        self.metadata.metadata_for_release_ids.side_effect = lambda ids: tuple(
            CurrentReleaseMetadata(value, "Current changed artist", "Current title") for value in ids
        )
        self.service = PortfolioArtistInspectionService(self.metadata)

    def test_all_dimensions_preserve_exact_entries_order_counts_and_source(self):
        expected = {
            Dimension.ARTIST: (("Shared", (10, 30), 4), ("2000", (50,), 4), ("Other", (20,), 2)),
            Dimension.LABEL: (("Shared", (20, 30), 3), ("2000", (50,), 4), ("Other", (10,), 3)),
            Dimension.FORMAT: (('12"', (10, 30), 4), ("2000", (50,), 4), ("CD", (20,), 2)),
            Dimension.RELEASE_YEAR: (("2000", (50,), 4), ("1991", (10,), 3), ("2001", (20,), 2), ("2005", (30,), 1)),
            Dimension.DECADE: (("1990", (10,), 3), ("2000", (20, 30, 50), 7)),
        }
        quantities = {10: 3, 20: 2, 30: 1, 50: 4}
        for dimension, entries in zip(Dimension, self.source.distribution.output.dimensions):
            self.assertIs(entries.dimension, dimension)
            self.assertEqual(tuple((e.category_id, e.release_ids, e.owned_copy_count) for e in entries.entries), expected[dimension])
            self.assertEqual((entries.releases_with_metadata, entries.copies_with_metadata, entries.missing_release_ids), (4, 10, (40,)))
            for category in entries.entries:
                with self.subTest(dimension=dimension, category=category.category_id):
                    result = self.service.inspect(self.source, category.category_id, dimension=dimension)
                    self.assertIs(result.source, self.source)
                    self.assertIs(result.dimension, dimension)
                    self.assertIs(result.category, category)
                    self.assertEqual(tuple((v.release_id, v.copies_at_calculation) for v in result.members), tuple((i, quantities[i]) for i in category.release_ids))
                    self.assertEqual((category.unique_release_count, category.release_denominator, category.copy_denominator), (len(category.release_ids), 5, 11))
                    self.assertEqual(category.release_ratio, Decimal(len(category.release_ids)) / Decimal(5))
                    self.assertEqual(category.copy_ratio, Decimal(category.owned_copy_count) / Decimal(11))
                    self.assertTrue(all(v.current_metadata.artist == "Current changed artist" for v in result.members))
                    self.assertNotIn(40, category.release_ids)
                    self.assertNotEqual(category.display_name, "Unknown")

    def test_colliding_ids_require_typed_dimension_and_exact_category_object(self):
        artist = self.service.inspect(self.source, "Shared")
        label = self.service.inspect(self.source, "Shared", dimension=Dimension.LABEL)
        self.assertEqual(tuple(v.release_id for v in artist.members), (10, 30))
        self.assertEqual(tuple(v.release_id for v in label.members), (20, 30))
        with self.assertRaises(ValueError): replace(artist, dimension=Dimension.LABEL)
        other_source = _outcome((_row(10, artist="Shared"),))[0].portfolio
        with self.assertRaises(ValueError): replace(artist, source=other_source)
        self.metadata.reset_mock()
        for value in ("artist", None, True, 1):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.service.inspect(self.source, "Shared", dimension=value)
        self.metadata.metadata_for_release_ids.assert_not_called()

    def test_empty_dimensions_exclude_missing_without_query(self):
        source = _outcome((_row(1, artist=None, label=None, format_value=None, released=None),))[0].portfolio
        for dimension in Dimension:
            with self.subTest(dimension=dimension), self.assertRaises(ValueError):
                self.service.inspect(source, "Unknown", dimension=dimension)
        self.metadata.metadata_for_release_ids.assert_not_called()

    def test_missing_and_malformed_labels_preserve_each_dimensions_complete_membership(self):
        for dimension in Dimension:
            category = next(d for d in self.source.distribution.output.dimensions if d.dimension is dimension).entries[0]
            with self.subTest(dimension=dimension):
                self.metadata.metadata_for_release_ids.side_effect = None
                self.metadata.metadata_for_release_ids.return_value = ()
                result = self.service.inspect(self.source, category.category_id, dimension=dimension)
                self.assertEqual(tuple(v.release_id for v in result.members), category.release_ids)
                self.assertTrue(all(v.current_metadata is None for v in result.members))
                self.assertEqual(result.label_error, "")
                for bad in ((object(),), (CurrentReleaseMetadata(999, "Bad", "Bad"),)):
                    self.metadata.metadata_for_release_ids.return_value = bad
                    result = self.service.inspect(self.source, category.category_id, dimension=dimension)
                    self.assertEqual(result.label_error, LABEL_FAILURE)
                    self.assertEqual(tuple(v.release_id for v in result.members), category.release_ids)
                    self.assertTrue(all(v.current_metadata is None for v in result.members))
