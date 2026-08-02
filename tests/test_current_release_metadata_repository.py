import tempfile
import unittest
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dip.persistence.sqlite import (
    CurrentReleaseMetadataPersistenceError,
    Database,
    SQLiteCurrentReleaseMetadataRepository,
)


class CurrentReleaseMetadataRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "test.sqlite3")
        self.repository = SQLiteCurrentReleaseMetadataRepository(self.database)

    def tearDown(self):
        self.database.close()
        self.temp.cleanup()

    def test_returns_detached_ordered_subset_without_ownership_join(self):
        with self.database.transaction() as connection:
            connection.executemany(
                "INSERT INTO releases(release_id, artist, title) VALUES (?, ?, ?)",
                ((2, "Two", "Second"), (1, "One", "First")),
            )
        values = self.repository.metadata_for_release_ids((1, 2, 3))
        self.assertEqual(tuple(value.release_id for value in values), (1, 2))
        self.assertEqual(values[0].artist, "One")

    def test_empty_and_invalid_inputs(self):
        self.assertEqual(self.repository.metadata_for_release_ids(()), ())
        for value, error in (((True,), TypeError), ((0,), ValueError), ((2, 1), ValueError), ((1, 1), ValueError)):
            with self.assertRaises(error):
                self.repository.metadata_for_release_ids(value)

    def test_batches_beyond_sqlite_parameter_limit(self):
        with self.database.transaction() as connection:
            connection.executemany(
                "INSERT INTO releases(release_id, artist, title) VALUES (?, '', '')",
                ((value,) for value in range(1, 1002)),
            )
        values = self.repository.metadata_for_release_ids(tuple(range(1, 1002)))
        self.assertEqual((values[0].release_id, values[-1].release_id), (1, 1001))

    def test_closed_database_is_translated_without_exposing_sql(self):
        self.database.close()
        with self.assertRaises(CurrentReleaseMetadataPersistenceError) as raised:
            self.repository.metadata_for_release_ids((1,))
        self.assertIsNotNone(raised.exception.__cause__)
        self.assertNotIn("SELECT", str(raised.exception))

    def test_read_does_not_commit_or_rollback_caller_transaction(self):
        with self.database.locked_connection() as connection:
            connection.execute("BEGIN")
            connection.execute("INSERT INTO releases(release_id, artist, title) VALUES (1, 'A', 'T')")
            self.assertEqual(self.repository.metadata_for_release_ids((1,))[0].artist, "A")
            self.assertTrue(connection.in_transaction)
            connection.rollback()
        self.assertEqual(self.repository.metadata_for_release_ids((1,)), ())

    def test_read_preserves_caller_commit_and_nested_boundary(self):
        with self.database.locked_connection() as connection:
            connection.execute("BEGIN")
            connection.execute("INSERT INTO releases(release_id, artist, title) VALUES (1, 'A', 'T')")
            self.assertEqual(self.repository.metadata_for_release_ids((1,))[0].title, "T")
            self.assertTrue(connection.in_transaction)
            connection.commit()
        self.assertEqual(self.repository.metadata_for_release_ids((1,))[0].artist, "A")

    def test_real_outer_transaction_and_nested_savepoint_remain_caller_owned(self):
        with self.database.locked_connection() as connection:
            connection.execute("BEGIN")
            connection.execute(
                "INSERT INTO releases(release_id, artist, title) VALUES (1, 'A', 'T')"
            )
            self.assertEqual(
                self.repository.metadata_for_release_ids((1,))[0].title,
                "T",
            )
            self.assertTrue(connection.in_transaction)
            connection.execute("SAVEPOINT caller_scope")
            connection.execute(
                "UPDATE releases SET title = 'Temporary' WHERE release_id = 1"
            )
            self.assertEqual(
                self.repository.metadata_for_release_ids((1,))[0].title,
                "Temporary",
            )
            connection.execute("ROLLBACK TO caller_scope")
            connection.execute("RELEASE caller_scope")
            self.assertEqual(
                self.repository.metadata_for_release_ids((1,))[0].title,
                "T",
            )
            self.assertTrue(connection.in_transaction)
            connection.commit()

        with self.database.locked_connection() as connection:
            connection.execute("BEGIN")
            connection.execute("SAVEPOINT caller_scope")
            self.assertEqual(
                self.repository.metadata_for_release_ids((1,))[0].artist,
                "A",
            )
            connection.execute("RELEASE caller_scope")
            self.assertTrue(connection.in_transaction)
            connection.execute("DELETE FROM releases WHERE release_id = 1")
            connection.rollback()

        self.assertEqual(
            self.repository.metadata_for_release_ids((1,))[0].release_id,
            1,
        )

    def test_sqlite_operational_failure_is_translated_with_cause(self):
        with self.database.transaction() as connection:
            connection.execute("DROP TABLE releases")
        with self.assertRaises(CurrentReleaseMetadataPersistenceError) as raised:
            self.repository.metadata_for_release_ids((1,))
        self.assertIsNotNone(raised.exception.__cause__)
        self.assertNotIn("SELECT", str(raised.exception))

    def test_empty_scope_does_not_open_a_connection_or_execute_sql(self):
        class DatabaseThatMustNotBeUsed:
            def locked_connection(self):
                raise AssertionError("empty lookup must not touch SQLite")
        repository = SQLiteCurrentReleaseMetadataRepository(DatabaseThatMustNotBeUsed())
        self.assertEqual(repository.metadata_for_release_ids(()), ())

    def test_malformed_storage_types_and_identities_fail_closed(self):
        valid = {
            "release_id": 1,
            "artist": "Artist",
            "title": "Title",
            "release_id_type": "integer",
            "artist_type": "text",
            "title_type": "text",
        }
        cases = (
            {**valid, "release_id": "1", "release_id_type": "text"},
            {**valid, "release_id": 1.0, "release_id_type": "real"},
            {**valid, "release_id": b"1", "release_id_type": "blob"},
            {**valid, "release_id": None, "release_id_type": "null"},
            {**valid, "release_id": 0},
            {**valid, "release_id": -1},
            {**valid, "artist": 7, "artist_type": "integer"},
            {**valid, "title": b"Title", "title_type": "blob"},
        )
        for row in cases:
            with self.subTest(row=row):
                repository, _ = fake_repository((row,))
                with self.assertRaises(CurrentReleaseMetadataPersistenceError):
                    repository.metadata_for_release_ids((1,))

    def test_duplicate_and_unexpected_returned_identities_fail_closed(self):
        row = {
            "release_id": 1, "artist": "A", "title": "T",
            "release_id_type": "integer", "artist_type": "text", "title_type": "text",
        }
        for rows in ((row, row), ({**row, "release_id": 2},)):
            with self.subTest(rows=rows):
                repository, _ = fake_repository(rows)
                with self.assertRaises(CurrentReleaseMetadataPersistenceError):
                    repository.metadata_for_release_ids((1,))

    def test_adapter_never_commits_or_rolls_back_and_propagates_savepoint_scope(self):
        row = {
            "release_id": 1, "artist": "A", "title": "T",
            "release_id_type": "integer", "artist_type": "text", "title_type": "text",
        }
        repository, connection = fake_repository((row,))
        self.assertEqual(repository.metadata_for_release_ids((1,))[0].release_id, 1)
        self.assertEqual((connection.commit_calls, connection.rollback_calls), (0, 0))

    def test_sqlite_execute_failure_is_translated(self):
        repository, _ = fake_repository((), error=sqlite3.OperationalError("private SQL"))
        with self.assertRaises(CurrentReleaseMetadataPersistenceError) as raised:
            repository.metadata_for_release_ids((1,))
        self.assertIsInstance(raised.exception.__cause__, sqlite3.OperationalError)
        self.assertNotIn("private SQL", str(raised.exception))


class FakeCursor:
    def __init__(self, rows): self._rows = rows
    def fetchall(self): return self._rows


class FakeConnection:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error
        self.commit_calls = 0
        self.rollback_calls = 0
        self.execute_calls = 0
    def execute(self, statement, parameters):
        self.execute_calls += 1
        if self.error is not None:
            raise self.error
        return FakeCursor(self.rows)
    def commit(self): self.commit_calls += 1
    def rollback(self): self.rollback_calls += 1


def fake_repository(rows, error=None):
    connection = FakeConnection(rows, error)
    class FakeDatabase:
        @contextmanager
        def locked_connection(self):
            yield connection
    return SQLiteCurrentReleaseMetadataRepository(FakeDatabase()), connection


if __name__ == "__main__":
    unittest.main()
