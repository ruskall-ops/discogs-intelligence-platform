from __future__ import annotations

import re
import sqlite3

from ..base import Migration


_INDEX_NAME = "idx_intelligence_runs_marketplace_snapshot"
_PROVENANCE_COLUMN = "marketplace_snapshot_id"


class AddIntelligenceMarketplaceProvenanceMigration(Migration):
    version = 5
    name = "Add Intelligence Marketplace provenance"

    def upgrade(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]: row
            for row in connection.execute(
                "PRAGMA table_info(intelligence_runs)"
            ).fetchall()
        }
        if "marketplace_snapshot_id" not in columns:
            connection.execute(
                """
                ALTER TABLE intelligence_runs
                ADD COLUMN marketplace_snapshot_id TEXT
                    REFERENCES marketplace_snapshots(snapshot_id)
                    ON UPDATE RESTRICT
                    ON DELETE RESTRICT
                """
            )

        connection.execute(
            f"""
            CREATE UNIQUE INDEX IF NOT EXISTS {_INDEX_NAME}
            ON intelligence_runs(marketplace_snapshot_id)
            WHERE marketplace_snapshot_id IS NOT NULL
            """
        )
        _validate_schema(connection)


def _validate_schema(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]: row
        for row in connection.execute(
            "PRAGMA table_info(intelligence_runs)"
        ).fetchall()
    }
    column = columns.get("marketplace_snapshot_id")
    if (
        column is None
        or str(column["type"]).upper() != "TEXT"
        or column["notnull"] != 0
    ):
        raise sqlite3.OperationalError(
            "Intelligence Marketplace provenance column is incompatible."
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
            "PRAGMA foreign_key_list(intelligence_runs)"
        ).fetchall()
        if row["from"] == "marketplace_snapshot_id"
    )
    if foreign_keys != (
        (
            "marketplace_snapshot_id",
            "marketplace_snapshots",
            "snapshot_id",
            "RESTRICT",
            "RESTRICT",
        ),
    ):
        raise sqlite3.OperationalError(
            "Intelligence Marketplace provenance foreign key is incompatible."
        )

    index = connection.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'index' AND name = ?
        """,
        (_INDEX_NAME,),
    ).fetchone()
    listed = tuple(
        row
        for row in connection.execute(
            "PRAGMA index_list(intelligence_runs)"
        ).fetchall()
        if row["name"] == _INDEX_NAME
    )
    indexed_columns = tuple(
        row["name"]
        for row in connection.execute(
            f"PRAGMA index_info({_INDEX_NAME})"
        ).fetchall()
    )
    predicate_is_exact = (
        index is not None
        and type(index["sql"]) is str
        and _has_exact_provenance_predicate(index["sql"])
    )
    if (
        index is None
        or len(listed) != 1
        or listed[0]["unique"] != 1
        or listed[0]["partial"] != 1
        or indexed_columns != ("marketplace_snapshot_id",)
        or not predicate_is_exact
    ):
        raise sqlite3.OperationalError(
            "Intelligence Marketplace provenance index is incompatible."
        )


def _has_exact_provenance_predicate(index_sql: str) -> bool:
    match = re.search(r"\bwhere\b", index_sql, flags=re.IGNORECASE)
    if match is None:
        return False
    predicate = index_sql[match.end() :].strip()
    if predicate.endswith(";"):
        predicate = predicate[:-1].rstrip()
    predicate = _strip_outer_parentheses(predicate)
    identifier = (
        rf'(?:{re.escape(_PROVENANCE_COLUMN)}|'
        rf'"{re.escape(_PROVENANCE_COLUMN)}"|'
        rf"`{re.escape(_PROVENANCE_COLUMN)}`|"
        rf"\[{re.escape(_PROVENANCE_COLUMN)}\])"
    )
    return (
        re.fullmatch(
            rf"{identifier}\s+is\s+not\s+null",
            predicate,
            flags=re.IGNORECASE,
        )
        is not None
    )


def _strip_outer_parentheses(value: str) -> str:
    result = value.strip()
    while result.startswith("(") and result.endswith(")"):
        depth = 0
        wraps_entire_value = True
        for index, character in enumerate(result):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth < 0:
                    return result
                if depth == 0 and index != len(result) - 1:
                    wraps_entire_value = False
                    break
        if depth != 0 or not wraps_entire_value:
            break
        result = result[1:-1].strip()
    return result


migration = AddIntelligenceMarketplaceProvenanceMigration()
