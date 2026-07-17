from __future__ import annotations

import sqlite3
from pathlib import Path


def create_connection(path: Path) -> sqlite3.Connection:
    """Create and configure a SQLite connection."""

    database_path = Path(path).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        database_path,
        check_same_thread=False,
        timeout=30.0,
    )

    connection.row_factory = sqlite3.Row

    # Foreign-key enforcement must be enabled for every connection.
    connection.execute("PRAGMA foreign_keys = ON")

    # Wait briefly rather than immediately failing if the database is busy.
    connection.execute("PRAGMA busy_timeout = 30000")

    return connection
