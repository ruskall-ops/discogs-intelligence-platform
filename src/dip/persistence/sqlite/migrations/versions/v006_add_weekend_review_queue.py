"""Migration 6: add the durable collector-owned Weekend Review Queue."""

from __future__ import annotations

import sqlite3

from ..base import Migration


_TABLE = "weekend_review_queue"
_INDEX = "idx_weekend_review_queue_status_order"
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weekend_review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id INTEGER NOT NULL UNIQUE
        CHECK (
            typeof(release_id) = 'integer'
            AND release_id > 0
        ),
    added_at TEXT NOT NULL
        CHECK (length(trim(added_at)) > 0),
    status TEXT NOT NULL
        CHECK (
            status IN ('to_review', 'reviewing', 'resolved')
        ),
    review_note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
        CHECK (length(trim(updated_at)) > 0),
    resolved_at TEXT,
    source_type TEXT NOT NULL
        CHECK (source_type IN ('hot_now', 'hidden_gem')),
    source_observed_at TEXT NOT NULL
        CHECK (length(trim(source_observed_at)) > 0),
    source_summary TEXT NOT NULL
        CHECK (
            length(trim(source_summary)) > 0
            AND source_summary = trim(source_summary)
            AND instr(
                source_summary,
                char(32) || char(32)
            ) = 0
            AND instr(source_summary, char(9)) = 0
            AND instr(source_summary, char(10)) = 0
            AND instr(source_summary, char(13)) = 0
        ),
    source_intelligence_run_id INTEGER,
    source_marketplace_snapshot_id TEXT,
    CHECK (
        (
            status = 'resolved'
            AND resolved_at IS NOT NULL
        )
        OR
        (
            status <> 'resolved'
            AND resolved_at IS NULL
        )
    ),
    CHECK (julianday(added_at) IS NOT NULL),
    CHECK (julianday(updated_at) IS NOT NULL),
    CHECK (julianday(source_observed_at) IS NOT NULL),
    CHECK (
        julianday(source_observed_at) <= julianday(added_at)
    ),
    CHECK (julianday(added_at) <= julianday(updated_at)),
    CHECK (
        resolved_at IS NULL
        OR (
            julianday(resolved_at) IS NOT NULL
            AND julianday(added_at) <= julianday(resolved_at)
            AND julianday(resolved_at) <= julianday(updated_at)
        )
    ),
    CHECK (
        source_type <> 'hidden_gem'
        OR (
            typeof(source_intelligence_run_id) = 'integer'
            AND source_intelligence_run_id > 0
        )
    ),
    CHECK (
        source_type <> 'hot_now'
        OR source_intelligence_run_id IS NULL
    ),
    CHECK (
        source_marketplace_snapshot_id IS NULL
        OR (
            length(trim(source_marketplace_snapshot_id)) > 0
            AND source_marketplace_snapshot_id =
                trim(source_marketplace_snapshot_id)
        )
    ),
    FOREIGN KEY (release_id)
        REFERENCES releases(release_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    FOREIGN KEY (source_intelligence_run_id)
        REFERENCES intelligence_runs(id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,
    FOREIGN KEY (source_marketplace_snapshot_id)
        REFERENCES marketplace_snapshots(snapshot_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
)
"""


class AddWeekendReviewQueueMigration(Migration):
    version = 6
    name = "Add Weekend Review Queue"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        connection.execute(_CREATE_TABLE_SQL)
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_weekend_review_queue_status_order
            ON weekend_review_queue(status, added_at ASC, id ASC)
            """
        )
        _validate_schema(connection)


def _validate_schema(connection: sqlite3.Connection) -> None:
    table = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (_TABLE,),
    ).fetchone()
    if table is None or type(table["sql"]) is not str:
        raise sqlite3.OperationalError(
            "Weekend Review Queue table is missing."
        )

    columns = tuple(
        (
            row["name"],
            str(row["type"]).upper(),
            row["notnull"],
            row["dflt_value"],
            row["pk"],
        )
        for row in connection.execute(
            f"PRAGMA table_info({_TABLE})"
        ).fetchall()
    )
    expected_columns = (
        ("id", "INTEGER", 0, None, 1),
        ("release_id", "INTEGER", 1, None, 0),
        ("added_at", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("review_note", "TEXT", 1, "''", 0),
        ("updated_at", "TEXT", 1, None, 0),
        ("resolved_at", "TEXT", 0, None, 0),
        ("source_type", "TEXT", 1, None, 0),
        ("source_observed_at", "TEXT", 1, None, 0),
        ("source_summary", "TEXT", 1, None, 0),
        ("source_intelligence_run_id", "INTEGER", 0, None, 0),
        ("source_marketplace_snapshot_id", "TEXT", 0, None, 0),
    )
    if columns != expected_columns:
        raise sqlite3.OperationalError(
            "Weekend Review Queue columns are incompatible."
        )

    foreign_keys = tuple(
        (
            row["from"],
            row["table"],
            row["to"],
            row["on_update"],
            row["on_delete"],
        )
        for row in connection.execute(
            f"PRAGMA foreign_key_list({_TABLE})"
        ).fetchall()
    )
    if set(foreign_keys) != {
        ("release_id", "releases", "release_id", "RESTRICT", "RESTRICT"),
        (
            "source_intelligence_run_id",
            "intelligence_runs",
            "id",
            "RESTRICT",
            "RESTRICT",
        ),
        (
            "source_marketplace_snapshot_id",
            "marketplace_snapshots",
            "snapshot_id",
            "RESTRICT",
            "RESTRICT",
        ),
    }:
        raise sqlite3.OperationalError(
            "Weekend Review Queue foreign keys are incompatible."
        )

    indexes = tuple(
        row
        for row in connection.execute(
            f"PRAGMA index_list({_TABLE})"
        ).fetchall()
    )
    release_unique = tuple(
        row
        for row in indexes
        if row["unique"]
        and tuple(
            column["name"]
            for column in connection.execute(
                f"PRAGMA index_info({row['name']})"
            ).fetchall()
        )
        == ("release_id",)
    )
    if len(release_unique) != 1:
        raise sqlite3.OperationalError(
            "Weekend Review Queue release identity is not unique."
        )

    named = tuple(row for row in indexes if row["name"] == _INDEX)
    order = tuple(
        (row["name"], row["desc"])
        for row in connection.execute(
            f"PRAGMA index_xinfo({_INDEX})"
        ).fetchall()
        if row["key"]
    )
    if len(named) != 1 or named[0]["unique"] or order != (
        ("status", 0),
        ("added_at", 0),
        ("id", 0),
    ):
        raise sqlite3.OperationalError(
            "Weekend Review Queue ordering index is incompatible."
        )

    if _canonical_create_table(table["sql"]) != _canonical_create_table(
        _CREATE_TABLE_SQL
    ):
        raise sqlite3.OperationalError(
            "Weekend Review Queue constraints are incompatible."
        )


def _canonical_create_table(value: str) -> tuple[tuple[str, str], ...]:
    """Tokenize one focused CREATE TABLE definition without changing literals."""

    if not isinstance(value, str):
        raise TypeError("CREATE TABLE SQL must be a string.")
    tokens: list[tuple[str, str]] = []
    index = 0
    length = len(value)
    punctuation = set("(),=<>+-*/|.;")
    while index < length:
        character = value[index]
        if character.isspace():
            index += 1
            continue
        if character == "'":
            start = index
            index += 1
            while index < length:
                if value[index] != "'":
                    index += 1
                    continue
                index += 1
                if index < length and value[index] == "'":
                    index += 1
                    continue
                break
            else:
                raise sqlite3.OperationalError(
                    "Weekend Review Queue SQL contains an unterminated literal."
                )
            tokens.append(("literal", value[start:index]))
            continue
        if character in {'"', "`", "["}:
            closing = "]" if character == "[" else character
            index += 1
            identifier: list[str] = []
            while index < length and value[index] != closing:
                identifier.append(value[index])
                index += 1
            if index >= length:
                raise sqlite3.OperationalError(
                    "Weekend Review Queue SQL contains an unterminated identifier."
                )
            index += 1
            tokens.append(("word", "".join(identifier).lower()))
            continue
        if character in punctuation:
            if (
                character == ";"
                and not value[index + 1 :].strip()
            ):
                index += 1
                continue
            two = value[index : index + 2]
            if two in {"<=", ">=", "<>", "!=", "||"}:
                tokens.append(("symbol", two))
                index += 2
            else:
                tokens.append(("symbol", character))
                index += 1
            continue
        start = index
        while (
            index < length
            and not value[index].isspace()
            and value[index] not in punctuation
            and value[index] not in {"'", '"', "`", "["}
        ):
            index += 1
        tokens.append(("word", value[start:index].lower()))
    optional = (
        ("word", "create"),
        ("word", "table"),
        ("word", "if"),
        ("word", "not"),
        ("word", "exists"),
    )
    if tuple(tokens[:5]) == optional:
        tokens[2:5] = []
    return tuple(tokens)


migration = AddWeekendReviewQueueMigration()


__all__ = ["migration"]
