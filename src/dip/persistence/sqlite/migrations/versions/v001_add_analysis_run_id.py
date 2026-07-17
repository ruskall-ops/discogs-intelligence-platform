from __future__ import annotations

import sqlite3

from ..base import Migration


class AddAnalysisRunIdMigration(Migration):
    version = 1
    name = "Add analysis_run_id to market_snapshots"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(market_snapshots)"
            ).fetchall()
        }

        if "analysis_run_id" not in columns:
            connection.execute(
                """
                ALTER TABLE market_snapshots
                ADD COLUMN analysis_run_id INTEGER
                REFERENCES analysis_runs(id)
                ON DELETE SET NULL
                """
            )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_snapshots_analysis_run
            ON market_snapshots(analysis_run_id)
            """
        )


migration = AddAnalysisRunIdMigration()
