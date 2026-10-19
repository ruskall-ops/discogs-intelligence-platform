from dataclasses import FrozenInstanceError
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

from dip.app.collection_decision import CollectionDecisionService, CollectionDecisionError
from dip.persistence.sqlite import Database
from tests.test_portfolio_artist_inspection import manifest


class CollectionDecisionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)/"synthetic.sqlite3"
        self.database = Database(self.path)
        self.database.conn.executemany("INSERT INTO releases(release_id,artist,title) VALUES (?, 'Artist', 'Title')", ((value,) for value in range(1, 5003)))
        self.database.conn.commit()
        self.service = CollectionDecisionService(self.database)

    def tearDown(self):
        self.database.close()
        self.directory.cleanup()

    def test_exact_id_beyond_review_caps_and_filters_reads_without_writes(self):
        self.assertEqual(len(self.database.review_rows(limit=5000)), 5000)
        self.assertEqual(self.database.review_rows(search="absent", decision="Keep"), [])
        before = manifest(self.database.conn)
        changes = self.database.conn.total_changes
        record = self.service.load(5002)
        self.assertEqual((record.release_id, record.decision, record.personal_notes, record.protected), (5002, "Review", "", False))
        self.assertEqual(manifest(self.database.conn), before)
        self.assertEqual(self.database.conn.total_changes, changes)
        with self.assertRaises(FrozenInstanceError):
            record.release_id = 1

    def test_explicit_save_changes_only_selected_decision_and_survives_read_only_reopen(self):
        before = dict(manifest(self.database.conn)[1])
        record = self.service.load(5002)
        self.service.save(record, "Keep", "Would miss it", "Synthetic note", True)
        after = dict(manifest(self.database.conn)[1])
        self.assertEqual({key for key in before if before[key] != after[key]}, {"decisions"})
        self.assertEqual(len(after["decisions"]), 1)
        self.assertEqual(self.service.load(5002).personal_notes, "Synthetic note")
        self.database.close()
        with sqlite3.connect(self.path.as_uri()+"?mode=ro",uri=True) as connection:
            self.assertEqual(connection.execute("SELECT release_id,decision,protected FROM decisions").fetchall(), [(5002,"Keep",1)])
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0],"ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(),[])
            self.assertEqual([row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")],list(range(1,8)))
        self.assertEqual(tuple(Path(self.directory.name).iterdir()),(self.path,))
        self.database = Database(self.path)

    def test_retained_value_reads_unchanged_but_cannot_be_saved_as_new_choice(self):
        self.database.conn.execute("INSERT INTO decisions(release_id,decision,personal_notes) VALUES (1,'Retained legacy','Original')")
        self.database.conn.commit()
        before = manifest(self.database.conn)
        record = self.service.load(1)
        self.assertEqual(record.decision,"Retained legacy")
        self.assertEqual(manifest(self.database.conn), before)
        for invalid in (record.decision, " Keep", "", True):
            with self.subTest(invalid=invalid), self.assertRaises(CollectionDecisionError):
                self.service.save(record,invalid,"Unsure","Changed",False)
            self.assertEqual(manifest(self.database.conn),before)

    def test_missing_and_invalid_identity_never_substitutes_another_release(self):
        self.assertIsNone(self.service.load(99999))
        for value in (True,0,-1,"1"):
            with self.assertRaises(ValueError): self.service.load(value)

    def test_malformed_lookup_is_a_safe_failure(self):
        repository = Mock()
        service = CollectionDecisionService(repository)
        good = self.database.collection_decision_for_release(1)
        for values in ({**good,"release_id":2},{**good,"protected":2},{**good,"personal_notes":3},object()):
            repository.collection_decision_for_release.return_value=values
            with self.assertRaises(CollectionDecisionError) as raised: service.load(1)
            self.assertNotIn("SELECT",str(raised.exception))
            repository.save_decision.assert_not_called()

    def test_deleted_record_cannot_be_saved(self):
        record=self.service.load(1)
        self.database.conn.execute("DELETE FROM releases WHERE release_id=1")
        self.database.conn.commit()
        before=manifest(self.database.conn)
        with self.assertRaises(CollectionDecisionError): self.service.save(record,"Keep","Unsure","",False)
        self.assertEqual(manifest(self.database.conn),before)

    def test_read_preserves_caller_owned_transaction(self):
        self.database.conn.execute("BEGIN")
        self.database.conn.execute("INSERT INTO releases(release_id,title) VALUES (6000,'Uncommitted')")
        self.assertEqual(self.service.load(6000).title,"Uncommitted")
        self.assertTrue(self.database.conn.in_transaction)
        self.database.conn.rollback()
        self.assertIsNone(self.service.load(6000))

    def test_repository_failure_preserves_cause_and_uses_fixed_copy(self):
        repository=Mock()
        repository.collection_decision_for_release.side_effect=RuntimeError("secret database path")
        with self.assertRaises(CollectionDecisionError) as raised: CollectionDecisionService(repository).load(1)
        self.assertIsInstance(raised.exception.__cause__,RuntimeError)
        self.assertNotIn("secret",str(raised.exception))
