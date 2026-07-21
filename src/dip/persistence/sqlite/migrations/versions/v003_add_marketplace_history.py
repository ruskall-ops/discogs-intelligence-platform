from __future__ import annotations

import sqlite3

from ..base import Migration


class AddMarketplaceHistoryMigration(Migration):
    version = 3
    name = "Add Marketplace History table"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS marketplace_snapshots (
                snapshot_id TEXT PRIMARY KEY NOT NULL,
                captured_at TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL
                    CHECK (status IN (
                        'complete',
                        'partial',
                        'empty',
                        'unavailable',
                        'failed'
                    )),
                schema_version INTEGER NOT NULL
                    CHECK (schema_version > 0),
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_marketplace_snapshots_captured
            ON marketplace_snapshots(captured_at DESC, snapshot_id DESC)
            """
        )
        _validate_schema(connection)


def _validate_schema(connection: sqlite3.Connection) -> None:
    """Reject an incompatible table hidden by ``IF NOT EXISTS``."""

    columns = tuple(
        (
            row["name"],
            row["type"].upper(),
            row["notnull"],
            row["pk"],
        )
        for row in connection.execute(
            "PRAGMA table_info(marketplace_snapshots)"
        ).fetchall()
    )
    expected_columns = (
        ("snapshot_id", "TEXT", 1, 1),
        ("captured_at", "TEXT", 1, 0),
        ("source", "TEXT", 1, 0),
        ("status", "TEXT", 1, 0),
        ("schema_version", "INTEGER", 1, 0),
        ("payload_json", "TEXT", 1, 0),
    )
    if columns != expected_columns:
        raise sqlite3.OperationalError(
            "Existing marketplace_snapshots table has an incompatible shape."
        )

    if connection.execute(
        "PRAGMA foreign_key_list(marketplace_snapshots)"
    ).fetchall():
        raise sqlite3.OperationalError(
            "Existing marketplace_snapshots table has unexpected foreign keys."
        )

    table_row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'marketplace_snapshots'
        """
    ).fetchone()
    if table_row is None or type(table_row["sql"]) is not str:
        raise sqlite3.OperationalError(
            "Marketplace snapshot table definition is unavailable."
        )
    table_sql = " ".join(table_row["sql"].split())
    folded_sql = table_sql.casefold()
    required_fragments = (
        "check (status in (",
        "'complete'",
        "'partial'",
        "'empty'",
        "'unavailable'",
        "'failed'",
        "check (schema_version > 0)",
    )
    if any(fragment not in folded_sql for fragment in required_fragments):
        raise sqlite3.OperationalError(
            "Existing marketplace_snapshots table has incompatible constraints."
        )

    index_names = {
        row["name"]
        for row in connection.execute(
            "PRAGMA index_list(marketplace_snapshots)"
        ).fetchall()
    }
    index_name = "idx_marketplace_snapshots_captured"
    if index_name not in index_names:
        raise sqlite3.OperationalError(
            "Marketplace snapshot ordering index is missing."
        )
    ordering = tuple(
        (row["name"], row["desc"])
        for row in connection.execute(
            "PRAGMA index_xinfo(idx_marketplace_snapshots_captured)"
        ).fetchall()
        if row["key"] == 1
    )
    if ordering != (("captured_at", 1), ("snapshot_id", 1)):
        raise sqlite3.OperationalError(
            "Marketplace snapshot ordering index is incompatible."
        )


migration = AddMarketplaceHistoryMigration()
