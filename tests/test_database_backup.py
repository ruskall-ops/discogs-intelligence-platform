from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from dip.app.database_backup import (
    DatabaseBackupError,
    DatabaseBackupService,
    DatabaseBackupValidationError,
)
from dip.database_backup import database_manifest
from dip.database_backup import DatabaseBackupManifest
from dip.persistence.sqlite import Database, SQLiteDatabaseBackupAdapter


class DatabaseBackupTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / "source.sqlite3"
        self.database = Database(self.source)
        self.database.conn.execute(
            "INSERT INTO releases(release_id, artist, title) VALUES (7, 'Artist', 'Title')"
        )
        self.database.conn.execute(
            "INSERT INTO collection_ownership(release_id, quantity) VALUES (7, 2)"
        )
        self.database.conn.execute(
            """
            INSERT INTO decisions(release_id, personal_notes)
            VALUES (7, 'private note')
            """
        )
        self.database.conn.commit()
        self.adapter = SQLiteDatabaseBackupAdapter(self.database)
        self.service = DatabaseBackupService(self.adapter)

    def tearDown(self) -> None:
        try:
            self.database.close()
        except sqlite3.Error:
            pass
        self.directory.cleanup()

    def test_open_source_is_backed_up_consistently_with_all_tables(self) -> None:
        target = self.root / "backup.sqlite3"

        result = self.service.backup(target)

        self.assertEqual(result.filename, "backup.sqlite3")
        with closing(sqlite3.connect(target)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT artist FROM releases WHERE release_id=7"
                ).fetchone()[0],
                "Artist",
            )
            self.assertEqual(
                connection.execute(
                    "SELECT personal_notes FROM decisions WHERE release_id=7"
                ).fetchone()[0],
                "private note",
            )
            self.assertEqual(
                tuple(
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                ),
                tuple(range(1, 8)),
            )
            self.assertEqual(
                connection.execute("PRAGMA quick_check").fetchone()[0],
                "ok",
            )
        self.assertEqual(
            self.database.conn.execute(
                "SELECT quantity FROM collection_ownership WHERE release_id=7"
            ).fetchone()[0],
            2,
        )

    def test_existing_target_requires_overwrite_and_is_replaced_atomically(self) -> None:
        target = self.root / "backup.sqlite3"
        target.write_bytes(b"previous")

        with self.assertRaises(DatabaseBackupValidationError):
            self.service.backup(target)
        self.assertEqual(target.read_bytes(), b"previous")

        self.service.backup(target, overwrite=True)
        with closing(sqlite3.connect(target)) as connection:
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_rejects_source_alias_hard_link_symlink_and_invalid_destinations(self) -> None:
        hard_link = self.root / "source-hard-link.sqlite3"
        os.link(self.source, hard_link)
        symlink = self.root / "source-symlink.sqlite3"
        symlink.symlink_to(self.source)
        invalid = (
            self.source,
            hard_link,
            symlink,
            self.root / "backup.db",
            self.root / "missing" / "backup.sqlite3",
            self.root,
        )
        for target in invalid:
            with self.subTest(target=target):
                with self.assertRaises(DatabaseBackupValidationError):
                    self.service.backup(target, overwrite=True)

    def test_backup_failure_preserves_previous_target_and_cleans_temporary(self) -> None:
        target = self.root / "backup.sqlite3"
        target.write_bytes(b"previous")
        with patch.object(
            self.adapter,
            "create_backup",
            side_effect=RuntimeError("private path and SQL"),
        ):
            with self.assertRaises(DatabaseBackupError):
                self.service.backup(target, overwrite=True)

        self.assertEqual(target.read_bytes(), b"previous")
        self.assertEqual(
            tuple(path for path in self.root.iterdir() if path.name.startswith(".backup")),
            (),
        )

    def test_verification_and_atomic_replace_failures_preserve_target(self) -> None:
        target = self.root / "backup.sqlite3"
        target.write_bytes(b"previous")
        for failure in ("verification", "replace"):
            with self.subTest(failure=failure):
                target.write_bytes(b"previous")
                context = (
                    patch.object(
                        self.adapter,
                        "verify_backup",
                        side_effect=DatabaseBackupError("unsafe"),
                    )
                    if failure == "verification"
                    else patch(
                        "dip.app.database_backup.os.replace",
                        side_effect=OSError("private path"),
                    )
                )
                with context:
                    with self.assertRaises(DatabaseBackupError):
                        self.service.backup(target, overwrite=True)
                self.assertEqual(target.read_bytes(), b"previous")

    def test_adapter_verification_failure_is_rejected(self) -> None:
        target = self.root / "backup.sqlite3"
        with patch.object(
            self.adapter,
            "verify_backup",
            side_effect=DatabaseBackupError("unsafe"),
        ):
            with self.assertRaises(DatabaseBackupError):
                self.service.backup(target)
        self.assertFalse(target.exists())

    def test_closed_source_is_a_value_neutral_failure(self) -> None:
        self.database.close()
        with self.assertRaisesRegex(
            DatabaseBackupError,
            "^Database backup could not be created\\.$",
        ) as raised:
            self.service.backup(self.root / "backup.sqlite3")
        self.assertNotIn(str(self.source), str(raised.exception))

    def test_active_transaction_fails_immediately_without_mutation(self) -> None:
        target = self.root / "backup.sqlite3"
        self.database.conn.execute(
            "UPDATE releases SET title='Uncommitted' WHERE release_id=7"
        )
        started = time.monotonic()

        with self.assertRaises(DatabaseBackupError):
            self.service.backup(target)

        self.assertLess(time.monotonic() - started, 1.0)
        self.assertTrue(self.database.conn.in_transaction)
        self.assertEqual(
            self.database.conn.execute(
                "SELECT title FROM releases WHERE release_id=7"
            ).fetchone()[0],
            "Uncommitted",
        )
        self.assertFalse(target.exists())
        self.database.conn.rollback()
        self.assertEqual(
            self.database.conn.execute(
                "SELECT title FROM releases WHERE release_id=7"
            ).fetchone()[0],
            "Title",
        )

    def test_manifest_and_backup_share_one_lock_acquisition(self) -> None:
        original = self.database.locked_connection
        acquisitions = 0

        from contextlib import contextmanager

        @contextmanager
        def counted():
            nonlocal acquisitions
            acquisitions += 1
            with original() as connection:
                yield connection

        with patch.object(
            self.database,
            "locked_connection",
            side_effect=counted,
        ):
            manifest = self.adapter.create_backup(
                self.root / "temporary.sqlite3"
            )

        self.assertEqual(acquisitions, 1)
        with closing(
            sqlite3.connect(self.root / "temporary.sqlite3")
        ) as backup:
            self.assertEqual(database_manifest(backup), manifest)

    def test_competing_writer_cannot_enter_between_manifest_and_backup(
        self,
    ) -> None:
        lock = threading.Lock()
        backup_started = threading.Event()
        allow_backup_to_finish = threading.Event()
        writer_entered = threading.Event()

        class Cursor:
            def __init__(self, rows):
                self._rows = rows

            def fetchall(self):
                return self._rows

        class Source:
            in_transaction = False

            def execute(self, sql):
                if "schema_migrations" in sql:
                    return Cursor([(1,), (2,)])
                return Cursor([("releases",), ("schema_migrations",)])

            def backup(self, _target):
                backup_started.set()
                self.assert_writer_blocked()
                allow_backup_to_finish.wait(2)

            @staticmethod
            def assert_writer_blocked():
                if writer_entered.is_set():
                    raise AssertionError(
                        "writer entered before backup completed"
                    )

        source = Source()

        class FakeDatabase:
            path = Path("/tmp/source.db")

            @contextmanager
            def locked_connection(self):
                with lock:
                    yield source

        adapter = SQLiteDatabaseBackupAdapter(FakeDatabase())
        result = {}
        target_connection = Mock()
        with patch(
            "dip.persistence.sqlite.backup.sqlite3.connect",
            return_value=target_connection,
        ):
            backup_thread = threading.Thread(
                target=lambda: result.setdefault(
                    "manifest",
                    adapter.create_backup(Path("/tmp/temporary.sqlite3")),
                )
            )
            backup_thread.start()
            self.assertTrue(backup_started.wait(1))

            def writer():
                with FakeDatabase().locked_connection():
                    writer_entered.set()

            writer_thread = threading.Thread(target=writer)
            writer_thread.start()
            self.assertFalse(writer_entered.wait(0.05))
            allow_backup_to_finish.set()
            backup_thread.join(1)
            writer_thread.join(1)

        self.assertFalse(backup_thread.is_alive())
        self.assertFalse(writer_thread.is_alive())
        self.assertTrue(writer_entered.is_set())
        self.assertEqual(result["manifest"].migration_versions, (1, 2))
        target_connection.close.assert_called_once_with()

    def test_application_boundary_has_no_sqlite_dependency(self) -> None:
        source = (
            Path(__file__).resolve().parents[1]
            / "src/dip/app/database_backup.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("import sqlite3", source)
        self.assertNotIn("from sqlite3", source)

    def test_verification_rejects_foreign_key_migration_and_table_changes(
        self,
    ) -> None:
        for failure in ("foreign_key", "migration", "table"):
            with self.subTest(failure=failure):
                target = self.root / f"{failure}.sqlite3"
                manifest = self.adapter.create_backup(target)
                with closing(sqlite3.connect(target)) as connection:
                    connection.execute("PRAGMA foreign_keys = OFF")
                    if failure == "foreign_key":
                        connection.execute(
                            """
                            INSERT INTO collection_ownership(
                                release_id, quantity
                            ) VALUES (9999, 1)
                            """
                        )
                    elif failure == "migration":
                        connection.execute(
                            "DELETE FROM schema_migrations WHERE version=7"
                        )
                    else:
                        connection.execute(
                            "CREATE TABLE unexpected(value TEXT)"
                        )
                    connection.commit()
                with self.assertRaises(Exception):
                    self.adapter.verify_backup(
                        target,
                        expected_manifest=manifest,
                    )

    def test_temporary_creation_and_cleanup_failures_are_safe(self) -> None:
        target = self.root / "backup.sqlite3"
        with patch(
            "dip.app.database_backup.tempfile.mkstemp",
            side_effect=OSError("private destination"),
        ):
            with self.assertRaisesRegex(
                DatabaseBackupError,
                "^Database backup could not be created\\.$",
            ):
                self.service.backup(target)
        self.assertFalse(target.exists())

        with (
            patch.object(
                self.adapter,
                "create_backup",
                side_effect=RuntimeError("primary token"),
            ),
            patch.object(Path, "unlink", side_effect=OSError("cleanup path")),
        ):
            with self.assertRaisesRegex(
                DatabaseBackupError,
                "^Database backup could not be created\\.$",
            ) as raised:
                self.service.backup(target)
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        self.assertIn("primary token", str(raised.exception.__cause__))

    def test_temporary_descriptor_close_failure_removes_exact_file(self) -> None:
        target = self.root / "backup.sqlite3"
        temporary_path: Path | None = None
        real_mkstemp = tempfile.mkstemp
        real_close = os.close

        def tracked_mkstemp(*args, **kwargs):
            nonlocal temporary_path
            descriptor, name = real_mkstemp(*args, **kwargs)
            temporary_path = Path(name)
            return descriptor, name

        def close_then_fail(descriptor):
            real_close(descriptor)
            raise OSError("private close failure")

        with (
            patch(
                "dip.app.database_backup.tempfile.mkstemp",
                side_effect=tracked_mkstemp,
            ),
            patch(
                "dip.app.database_backup.os.close",
                side_effect=close_then_fail,
            ),
        ):
            with self.assertRaisesRegex(
                DatabaseBackupError,
                "^Database backup could not be created\\.$",
            ):
                self.service.backup(target)

        self.assertIsNotNone(temporary_path)
        self.assertFalse(temporary_path.exists())
        self.assertFalse(target.exists())

    def test_target_appearance_is_revalidated_before_publication(self) -> None:
        target = self.root / "appeared.sqlite3"
        original_verify = self.adapter.verify_backup

        def verify_and_create(path, *, expected_manifest):
            original_verify(path, expected_manifest=expected_manifest)
            target.write_bytes(b"other writer")

        with patch.object(
            self.adapter,
            "verify_backup",
            side_effect=verify_and_create,
        ):
            with self.assertRaises(DatabaseBackupValidationError):
                self.service.backup(target)
        self.assertEqual(target.read_bytes(), b"other writer")

    def test_uppercase_extension_broken_symlink_and_symlinked_parent(self) -> None:
        uppercase = self.root / "backup.SQLITE3"
        self.service.backup(uppercase)
        self.assertTrue(uppercase.exists())

        broken = self.root / "broken.sqlite3"
        broken.symlink_to(self.root / "absent")
        with self.assertRaises(DatabaseBackupValidationError):
            self.service.backup(broken, overwrite=True)

        real_parent = self.root / "real"
        real_parent.mkdir()
        linked_parent = self.root / "linked"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        through_link = linked_parent / "backup.sqlite3"
        self.service.backup(through_link)
        self.assertTrue((real_parent / "backup.sqlite3").exists())

        relative_source = Path(os.path.relpath(self.source, Path.cwd()))
        with self.assertRaises(DatabaseBackupValidationError):
            self.service.backup(relative_source, overwrite=True)
        child = self.root / "child"
        child.mkdir()
        dotdot_source = child / ".." / self.source.name
        with self.assertRaises(DatabaseBackupValidationError):
            self.service.backup(dotdot_source, overwrite=True)

    def test_destination_and_verification_close_failures_are_safe(self) -> None:
        class Source:
            in_transaction = False

            def execute(self, sql):
                rows = (
                    [(1,)]
                    if "schema_migrations" in sql
                    else [("schema_migrations",)]
                )
                return Mock(fetchall=Mock(return_value=rows))

            def backup(self, _target):
                return None

        class FakeDatabase:
            path = Path("/tmp/source.db")

            @contextmanager
            def locked_connection(self):
                yield Source()

        adapter = SQLiteDatabaseBackupAdapter(FakeDatabase())
        destination = Mock()
        destination.close.side_effect = OSError("private close")
        with patch(
            "dip.persistence.sqlite.backup.sqlite3.connect",
            return_value=destination,
        ):
            with self.assertRaisesRegex(
                Exception,
                "^SQLite backup destination could not be closed\\.$",
            ):
                adapter.create_backup(Path("/tmp/temporary.sqlite3"))

        verification = Mock()
        verification.execute.return_value.fetchall.return_value = (
            ("not ok",),
        )
        verification.close.side_effect = OSError("private close")
        with patch(
            "dip.persistence.sqlite.backup.sqlite3.connect",
            return_value=verification,
        ):
            with self.assertRaisesRegex(
                Exception,
                "^SQLite backup verification failed\\.$",
            ):
                adapter.verify_backup(
                    Path("/tmp/temporary.sqlite3"),
                    expected_manifest=DatabaseBackupManifest(
                        (1,),
                        ("schema_migrations",),
                    ),
                )
        verification.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
