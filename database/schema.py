from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def initialise_schema(connection: sqlite3.Connection) -> None:
    """Create or update the database schema."""

    try:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read database schema from {SCHEMA_PATH}"
        ) from exc

    with connection:
        connection.executescript(schema_sql)