from __future__ import annotations
from .migrations import run_migrations
import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def initialise_schema(connection: sqlite3.Connection) -> None:
    """Create the current schema and apply pending database migrations."""

    try:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read database schema from {SCHEMA_PATH}"
        ) from exc

    with connection:
        connection.executescript(schema_sql)
    run_migrations(connection)  



    """
    Add analysis_run_id to databases created before Analysis Runs existed.

    This is a temporary compatibility upgrade. The formal migration
    framework will be introduced under Issue #19.
    """

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