from __future__ import annotations

import sqlite3

from ..base import Migration


class AddIntelligenceHistoryMigration(Migration):
    version = 2
    name = "Add Intelligence History tables"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS intelligence_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                executed_at TEXT NOT NULL,
                executed_at_json TEXT NOT NULL,
                engine_version TEXT,
                collection_snapshot_id INTEGER,
                result_count INTEGER NOT NULL CHECK (result_count >= 0)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS intelligence_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                module_id TEXT NOT NULL,
                module_version TEXT,
                status_json TEXT NOT NULL,
                summary TEXT NOT NULL,
                insights_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                diagnostics_json TEXT NOT NULL,
                FOREIGN KEY (run_id)
                    REFERENCES intelligence_runs(id)
                    ON DELETE RESTRICT,
                UNIQUE (run_id, module_id)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_intelligence_runs_executed
            ON intelligence_runs(executed_at DESC, id DESC)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_intelligence_results_module_run
            ON intelligence_results(module_id, run_id DESC)
            """
        )
migration = AddIntelligenceHistoryMigration()
