from __future__ import annotations

import sqlite3
from pathlib import Path

from .migrations import run_migrations
from .migrations.versions.v006_add_weekend_review_queue import (
    _canonical_create_table,
)


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_CURRENT_MIGRATIONS = tuple(range(1, 8))


class SchemaIntegrityError(RuntimeError):
    """Raised when persisted schema state is not safely reconstructable."""


def initialise_schema(connection: sqlite3.Connection) -> None:
    """Create a fresh schema or migrate and validate an existing one."""

    try:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Unable to read database schema from {SCHEMA_PATH}"
        ) from exc

    application_objects = _application_objects(connection)
    if not application_objects:
        with connection:
            connection.executescript(schema_sql)
        run_migrations(connection)
    else:
        if "schema_migrations" not in application_objects:
            raise SchemaIntegrityError(
                "The database schema is incomplete or incompatible."
            )
        run_migrations(connection)

    _validate_current_schema(connection, schema_sql)


def _validate_current_schema(
    connection: sqlite3.Connection,
    schema_sql: str,
) -> None:
    versions = tuple(
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    )
    if versions != _CURRENT_MIGRATIONS:
        raise SchemaIntegrityError(
            "The database migration state is incomplete or incompatible."
        )

    expected = sqlite3.connect(":memory:")
    expected.row_factory = sqlite3.Row
    try:
        expected.execute("PRAGMA foreign_keys = ON")
        expected.executescript(schema_sql)
        run_migrations(expected)
        expected_signature = _schema_signature(expected)
    finally:
        expected.close()

    if _schema_signature(connection) != expected_signature:
        raise SchemaIntegrityError(
            "The database schema is incomplete or incompatible."
        )


def _application_objects(connection: sqlite3.Connection) -> frozenset[str]:
    return frozenset(
        str(row[0])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_schema
            WHERE name NOT LIKE 'sqlite_%'
              AND type IN ('table', 'index', 'view', 'trigger')
            """
        ).fetchall()
    )


def _schema_signature(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, object], ...]:
    tables = tuple(
        str(row[0])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_schema
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    )
    signature: list[tuple[str, object]] = []
    for table in tables:
        table_row = connection.execute(
            """
            SELECT sql
            FROM sqlite_schema
            WHERE type = 'table' AND name = ?
            """,
            (table,),
        ).fetchone()
        if table_row is None or type(table_row[0]) is not str:
            raise SchemaIntegrityError(
                "The database schema is incomplete or incompatible."
            )
        columns = tuple(
            (
                str(row["name"]),
                str(row["type"]).upper(),
                int(row["notnull"]),
                row["dflt_value"],
                int(row["pk"]),
            )
            for row in connection.execute(
                f"PRAGMA table_info({_quote_identifier(table)})"
            ).fetchall()
        )
        foreign_keys = tuple(
            sorted(
                (
                    str(row["from"]),
                    str(row["table"]),
                    str(row["to"]),
                    str(row["on_update"]),
                    str(row["on_delete"]),
                )
                for row in connection.execute(
                    f"PRAGMA foreign_key_list({_quote_identifier(table)})"
                ).fetchall()
            )
        )
        indexes = []
        for row in connection.execute(
            f"PRAGMA index_list({_quote_identifier(table)})"
        ).fetchall():
            index_name = str(row["name"])
            key_columns = tuple(
                (
                    item["name"],
                    int(item["desc"]),
                    item["coll"],
                )
                for item in connection.execute(
                    f"PRAGMA index_xinfo({_quote_identifier(index_name)})"
                ).fetchall()
                if item["key"]
            )
            index_sql_row = connection.execute(
                """
                SELECT sql FROM sqlite_schema
                WHERE type = 'index' AND name = ?
                """,
                (index_name,),
            ).fetchone()
            index_sql = (
                None
                if index_sql_row is None or index_sql_row[0] is None
                else " ".join(str(index_sql_row[0]).split()).casefold()
            )
            indexes.append(
                (
                    index_name,
                    int(row["unique"]),
                    str(row["origin"]),
                    int(row["partial"]),
                    key_columns,
                    index_sql,
                )
            )
        signature.append(
            (
                table,
                (
                    columns,
                    foreign_keys,
                    tuple(sorted(indexes)),
                    _canonical_create_table(str(table_row[0])),
                ),
            )
        )
    return tuple(signature)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


__all__ = [
    "SCHEMA_PATH",
    "SchemaIntegrityError",
    "initialise_schema",
]
