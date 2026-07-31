from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dip import __version__
from dip.composition import build_desktop_application_dependencies
from dip.persistence.sqlite import Database
from tests.fixtures.v0_4_0_schema import SCHEMA_SQL


class ReleasedVersionUpgradeTestCase(unittest.TestCase):
    def test_exact_v0_4_schema_upgrades_through_five_six_and_seven(self) -> None:
        self.assertEqual(
            hashlib.sha256(SCHEMA_SQL.encode("utf-8")).hexdigest(),
            "d64ef4601302ef4e27018efc763236643bde26292892d72789758cde1c7b60a6",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "released-v0.4.0.db"
            connection = sqlite3.connect(path)
            try:
                connection.executescript(SCHEMA_SQL)
                connection.executescript(
                    """
                    INSERT INTO schema_migrations(version) VALUES (2), (3), (4);
                    INSERT INTO releases(
                        release_id, artist, title, label, catalog_no
                    ) VALUES (
                        7, 'Existing Artist', 'Existing Title',
                        'Existing Label', 'CAT-7'
                    );
                    INSERT INTO collection_ownership(
                        release_id, quantity, notes
                    ) VALUES (7, 2, 'ownership note');
                    INSERT INTO decisions(
                        release_id, decision, personal_notes, protected
                    ) VALUES (7, 'Keep', 'decision note', 1);
                    INSERT INTO analysis_runs(
                        id, status, started_at, completed_at,
                        releases_attempted, releases_succeeded
                    ) VALUES (
                        11, 'completed', '2026-07-01T00:00:00+00:00',
                        '2026-07-01T00:01:00+00:00', 1, 1
                    );
                    INSERT INTO market_snapshots(
                        release_id, analysis_run_id, captured_at, wants,
                        haves, copies_for_sale, lowest_price
                    ) VALUES (7, 11, '2026-07-01T00:00:00+00:00', 5, 8, 1, 10.5);
                    INSERT INTO scores(
                        release_id, calculated_at, value_score,
                        demand_score, opportunity_score, explanation
                    ) VALUES (
                        7, '2026-07-01T00:00:00+00:00',
                        9.0, 8.0, 42.0, 'preserved score'
                    );
                    INSERT INTO intelligence_runs(
                        id, executed_at, executed_at_json, engine_version,
                        result_count
                    ) VALUES (
                        21, '2026-07-01T00:00:00.000000+00:00',
                        '{"__dip_type__":"datetime","value":"2026-07-01T00:00:00+00:00"}',
                        'engine-v0.4', 0
                    );
                    INSERT INTO intelligence_results(
                        id, run_id, module_id, module_version, status_json,
                        summary, insights_json, metrics_json, evidence_json,
                        diagnostics_json
                    ) VALUES (
                        22, 21, 'fixture.module', '1.0',
                        '"completed"', 'preserved result',
                        '[]', '{}', '[]', '[]'
                    );
                    UPDATE intelligence_runs SET result_count=1 WHERE id=21;
                    INSERT INTO marketplace_snapshots(
                        snapshot_id, captured_at, source, status,
                        schema_version, payload_json
                    ) VALUES (
                        'snapshot-v04', '2026-07-01T00:00:00.000000+00:00',
                        'fixture', 'empty', 1, '{}'
                    );
                    INSERT INTO projects(
                        project_id, name, description, last_opened_order,
                        insertion_order
                    ) VALUES (
                        'current_collection', 'Current Collection',
                        'Existing project.', 1, 1
                    );
                    UPDATE project_state
                    SET active_project_id='current_collection'
                    WHERE singleton_id=1;
                    """
                )
                connection.commit()
            finally:
                connection.close()

            database = Database(path)
            try:
                versions = tuple(
                    row[0]
                    for row in database.conn.execute(
                        "SELECT version FROM schema_migrations ORDER BY version"
                    )
                )
                self.assertEqual(versions, tuple(range(1, 8)))
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT artist, title, label, catalog_no
                        FROM releases WHERE release_id=7
                        """
                    ).fetchone()),
                    (
                        "Existing Artist",
                        "Existing Title",
                        "Existing Label",
                        "CAT-7",
                    ),
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT quantity, notes FROM collection_ownership
                        WHERE release_id=7
                        """
                    ).fetchone()),
                    (2, "ownership note"),
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT decision, personal_notes, protected
                        FROM decisions WHERE release_id=7
                        """
                    ).fetchone()),
                    ("Keep", "decision note", 1),
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT status, started_at, completed_at
                        FROM analysis_runs WHERE id=11
                        """
                    ).fetchone()),
                    (
                        "completed",
                        "2026-07-01T00:00:00+00:00",
                        "2026-07-01T00:01:00+00:00",
                    ),
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT wants, haves, copies_for_sale, lowest_price
                        FROM market_snapshots WHERE analysis_run_id=11
                        """
                    ).fetchone()),
                    (5, 8, 1, 10.5),
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT value_score, demand_score, opportunity_score,
                               explanation
                        FROM scores WHERE release_id=7
                        """
                    ).fetchone()),
                    (9.0, 8.0, 42.0, "preserved score"),
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT module_id, module_version, summary
                        FROM intelligence_results WHERE id=22
                        """
                    ).fetchone()),
                    (
                        "fixture.module",
                        "1.0",
                        "preserved result",
                    ),
                )
                self.assertIsNone(
                    database.conn.execute(
                        """
                        SELECT marketplace_snapshot_id
                        FROM intelligence_runs WHERE id=21
                        """
                    ).fetchone()[0]
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT snapshot_id, status, payload_json
                        FROM marketplace_snapshots
                        WHERE snapshot_id='snapshot-v04'
                        """
                    ).fetchone()),
                    ("snapshot-v04", "empty", "{}"),
                )
                self.assertEqual(
                    tuple(database.conn.execute(
                        """
                        SELECT p.project_id, p.name, p.last_opened_order,
                               s.active_project_id
                        FROM projects p CROSS JOIN project_state s
                        WHERE p.project_id='current_collection'
                        """
                    ).fetchone()),
                    (
                        "current_collection",
                        "Current Collection",
                        1,
                        "current_collection",
                    ),
                )
                self.assertEqual(
                    database.conn.execute(
                        "SELECT COUNT(*) FROM weekend_review_queue"
                    ).fetchone()[0],
                    0,
                )
                self.assertEqual(
                    database.conn.execute(
                        "SELECT COUNT(*) FROM desktop_session"
                    ).fetchone()[0],
                    0,
                )
            finally:
                database.close()

            with patch(
                "dip.composition.SETTINGS",
                SimpleNamespace(
                    database_path=path,
                    application_version=__version__,
                    discogs_request_delay_seconds=0,
                ),
            ):
                dependencies = build_desktop_application_dependencies()
            try:
                self.assertEqual(__version__, "0.5.0")
                self.assertEqual(
                    dependencies.project_management.active_project().project_id,
                    "current_collection",
                )
                self.assertIsNotNone(dependencies.collector_run._provider_factory)
            finally:
                dependencies.database.close()


if __name__ == "__main__":
    unittest.main()
