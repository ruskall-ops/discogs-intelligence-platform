from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import count
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from dip.collection_decision_vocabulary import (
    ReviewFilterChoice,
    ReviewFilterChoiceKind,
    ReviewFilterField,
    validate_writable_decision,
)

from .connection import create_connection
from .schema import initialise_schema


_COLLECTION_EVIDENCE_BATCH_SIZE = 900


class Database:
    """Persistence layer for the Discogs Intelligence Platform."""

    def __init__(self, path: Path):
        self.path = Path(path).expanduser().resolve()
        self._lock = RLock()
        self._savepoint_ids = count(1)
        self.conn = create_connection(self.path)
        try:
            initialise_schema(self.conn)
        except BaseException:
            self.conn.close()
            raise

    @contextmanager
    def locked_connection(self) -> Iterator[sqlite3.Connection]:
        """Yield the shared connection while holding its coordinating lock."""

        with self._lock:
            yield self.conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Own a transaction or isolate work inside a caller transaction.

        A top-level call commits or rolls back its own transaction. When the
        caller already has an active transaction, a savepoint isolates failure
        while leaving the final commit or rollback decision with the caller.
        """

        with self._lock:
            if not self.conn.in_transaction:
                self.conn.execute("BEGIN")
                try:
                    yield self.conn
                except BaseException:
                    self.conn.rollback()
                    raise
                else:
                    self.conn.commit()
                return

            savepoint = f"dip_transaction_{next(self._savepoint_ids)}"
            self.conn.execute(f"SAVEPOINT {savepoint}")
            try:
                yield self.conn
            except BaseException:
                self.conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            else:
                self.conn.execute(f"RELEASE SAVEPOINT {savepoint}")

    def close(self) -> None:
        """Close the active database connection."""

        with self._lock:
            self.conn.close()

    def import_releases(
        self,
        rows: Iterable[dict[str, Any]],
        release_col: str,
    ) -> int:
        """
        Import Discogs collection rows.

        Releases are stored once per Discogs release ID. Duplicate CSV rows
        are represented through the quantity field in collection_ownership.

        Returns the number of valid CSV rows processed.
        """

        release_sql = """
        INSERT INTO releases (
            release_id,
            artist,
            title,
            label,
            catalog_no,
            format,
            released,
            collection_folder,
            date_added,
            rating
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(release_id) DO UPDATE SET
            artist = excluded.artist,
            title = excluded.title,
            label = excluded.label,
            catalog_no = excluded.catalog_no,
            format = excluded.format,
            released = excluded.released,
            collection_folder = excluded.collection_folder,
            date_added = excluded.date_added,
            rating = excluded.rating
        """

        ownership_sql = """
        INSERT INTO collection_ownership (
            release_id,
            quantity,
            collection_folder,
            rating,
            date_added,
            media_condition,
            sleeve_condition,
            notes,
            last_imported_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(release_id) DO UPDATE SET
            quantity = excluded.quantity,
            collection_folder = excluded.collection_folder,
            rating = excluded.rating,
            date_added = excluded.date_added,
            media_condition = excluded.media_condition,
            sleeve_condition = excluded.sleeve_condition,
            notes = excluded.notes,
            last_imported_at = CURRENT_TIMESTAMP
        """

        grouped_rows: dict[int, list[dict[str, Any]]] = {}
        processed_rows = 0

        for row in rows:
            raw_release_id = str(row.get(release_col, "")).strip()

            if not raw_release_id:
                continue

            try:
                release_id = int(raw_release_id)
            except ValueError:
                continue

            grouped_rows.setdefault(release_id, []).append(row)
            processed_rows += 1

        with self._lock, self.conn:
            for release_id, copies in grouped_rows.items():
                representative_row = copies[0]
                quantity = len(copies)

                self.conn.execute(
                    release_sql,
                    (
                        release_id,
                        representative_row.get("Artist", ""),
                        representative_row.get("Title", ""),
                        representative_row.get("Label", ""),
                        representative_row.get("Catalog#", ""),
                        representative_row.get("Format", ""),
                        representative_row.get("Released", ""),
                        representative_row.get("CollectionFolder", ""),
                        representative_row.get("Date Added", ""),
                        representative_row.get("Rating", ""),
                    ),
                )

                self.conn.execute(
                    ownership_sql,
                    (
                        release_id,
                        quantity,
                        representative_row.get("CollectionFolder", ""),
                        representative_row.get("Rating", ""),
                        representative_row.get("Date Added", ""),
                        representative_row.get(
                            "Collection Media Condition",
                            "",
                        ),
                        representative_row.get(
                            "Collection Sleeve Condition",
                            "",
                        ),
                        representative_row.get("Collection Notes", ""),
                    ),
                )

                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO decisions(release_id)
                    VALUES (?)
                    """,
                    (release_id,),
                )

        return processed_rows

    def release_ids(self) -> list[int]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT release_id
                FROM releases
                ORDER BY release_id
                """
            ).fetchall()

        return [int(row["release_id"]) for row in rows]

    def collection_evidence_rows(
        self,
        release_ids: tuple[int, ...],
    ) -> tuple[dict[str, Any], ...]:
        """Return score-free collection evidence for an exact fixed scope."""

        if type(release_ids) is not tuple or not release_ids:
            raise ValueError("release_ids must be a non-empty tuple.")
        seen: set[int] = set()
        validated: list[int] = []
        for index, value in enumerate(release_ids):
            if type(value) is not int:
                raise TypeError(f"release_ids[{index}] must be an integer.")
            if value <= 0:
                raise ValueError(f"release_ids[{index}] must be positive.")
            if value in seen:
                raise ValueError("release_ids must not contain duplicates.")
            seen.add(value)
            validated.append(value)

        requested = set(validated)
        collected: dict[int, dict[str, Any]] = {}
        with self._lock:
            for offset in range(0, len(validated), _COLLECTION_EVIDENCE_BATCH_SIZE):
                batch = validated[
                    offset : offset + _COLLECTION_EVIDENCE_BATCH_SIZE
                ]
                placeholders = ", ".join("?" for _ in batch)
                statement = (
                    """
                    SELECT
                        r.release_id,
                        r.artist,
                        r.title,
                        r.label,
                        co.quantity
                    FROM releases r
                    JOIN collection_ownership co
                        ON co.release_id = r.release_id
                    WHERE r.release_id IN (
                    """
                    + placeholders
                    + """
                    )
                    ORDER BY r.release_id
                    """
                )
                rows = self.conn.execute(
                    statement,
                    batch,
                ).fetchall()
                for row in rows:
                    detached = dict(row)
                    release_id = detached.get("release_id")
                    if (
                        type(release_id) is not int
                        or release_id not in requested
                    ):
                        raise ValueError(
                            "Collection evidence returned an unexpected identity."
                        )
                    if release_id in collected:
                        raise ValueError(
                            "Collection evidence returned a duplicate identity."
                        )
                    collected[release_id] = detached
        return tuple(collected[value] for value in sorted(collected))

    def owned_portfolio_rows(self) -> list[sqlite3.Row]:
        """Return canonical ownership facts in deterministic release order."""

        with self._lock:
            return self.conn.execute(
                """
                SELECT
                    release_id,
                    quantity
                FROM collection_ownership
                ORDER BY release_id
                """
            ).fetchall()

    def owned_portfolio_metadata_rows(self) -> list[sqlite3.Row]:
        """Return canonical ownership and release metadata in release order."""

        with self._lock:
            return self.conn.execute(
                """
                SELECT
                    co.release_id,
                    co.quantity,
                    r.artist,
                    r.label,
                    r.format,
                    r.released
                FROM collection_ownership co
                JOIN releases r
                    ON r.release_id = co.release_id
                ORDER BY co.release_id
                """
            ).fetchall()
        
    def start_analysis_run(
        self,
        run_type: str = "market_refresh",
        source: str = "discogs",
        application_version: str | None = None,
    ) -> int:
        """Create a new analysis run and return its database ID."""

        with self._lock, self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO analysis_runs (
                    run_type,
                    source,
                    status,
                    application_version
                )
                VALUES (?, ?, 'running', ?)
                """,
                (
                    run_type,
                    source,
                    application_version,
                ),
            )

        return int(cursor.lastrowid)

    def complete_analysis_run(
        self,
        run_id: int,
        releases_attempted: int,
        releases_succeeded: int,
        releases_failed: int,
    ) -> None:
        """Mark an analysis run as completed."""

        with self._lock, self.conn:
            self.conn.execute(
                """
                UPDATE analysis_runs
                SET
                    status = 'completed',
                    completed_at = CURRENT_TIMESTAMP,
                    releases_attempted = ?,
                    releases_succeeded = ?,
                    releases_failed = ?,
                    error_message = NULL
                WHERE id = ?
                """,
                (
                    releases_attempted,
                    releases_succeeded,
                    releases_failed,
                    run_id,
                ),
            )

    def fail_analysis_run(
        self,
        run_id: int,
        error_message: str,
        releases_attempted: int = 0,
        releases_succeeded: int = 0,
        releases_failed: int = 0,
    ) -> None:
        """Mark an analysis run as failed."""

        with self._lock, self.conn:
            self.conn.execute(
                """
                UPDATE analysis_runs
                SET
                    status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    releases_attempted = ?,
                    releases_succeeded = ?,
                    releases_failed = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (
                    releases_attempted,
                    releases_succeeded,
                    releases_failed,
                    error_message,
                    run_id,
                ),
            )

    def cancel_analysis_run(
        self,
        run_id: int,
        releases_attempted: int = 0,
        releases_succeeded: int = 0,
        releases_failed: int = 0,
    ) -> None:
        """Mark an analysis run as cancelled."""

        with self._lock, self.conn:
            self.conn.execute(
                """
                UPDATE analysis_runs
                SET
                    status = 'cancelled',
                    completed_at = CURRENT_TIMESTAMP,
                    releases_attempted = ?,
                    releases_succeeded = ?,
                    releases_failed = ?
                WHERE id = ?
                """,
                (
                    releases_attempted,
                    releases_succeeded,
                    releases_failed,
                    run_id,
                ),
            )
    def latest_completed_analysis_run(
        self,
        run_type: str = "market_refresh",
    ) -> sqlite3.Row | None:
        """Return the most recent completed analysis run."""

        with self._lock:
            return self.conn.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE status = 'completed'
                  AND run_type = ?
                ORDER BY completed_at DESC, id DESC
                LIMIT 1
                """,
                (run_type,),
            ).fetchone()

    def previous_completed_analysis_run(
        self,
        before_run_id: int,
        run_type: str = "market_refresh",
    ) -> sqlite3.Row | None:
        """Return the completed run immediately before another run."""

        with self._lock:
            return self.conn.execute(
                """
                SELECT *
                FROM analysis_runs
                WHERE status = 'completed'
                  AND run_type = ?
                  AND id < ?
                ORDER BY completed_at DESC, id DESC
                LIMIT 1
                """,
                (
                    run_type,
                    before_run_id,
                ),
            ).fetchone()

    def snapshots_for_analysis_run(
        self,
        run_id: int,
    ) -> list[sqlite3.Row]:
        """Return all marketplace snapshots captured during a run."""

        with self._lock:
            return self.conn.execute(
                """
                SELECT *
                FROM market_snapshots
                WHERE analysis_run_id = ?
                ORDER BY release_id
                """,
                (run_id,),
            ).fetchall()        

    def add_snapshot(
        self,
        analysis_run_id: int,
        release_id: int,
        captured_at: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Add a marketplace snapshot.

        Returns True when a new snapshot is inserted and False when an
        identical release/timestamp observation already exists.

        Existing historical observations are never silently replaced.
        """

        with self._lock, self.conn:
            cursor = self.conn.execute(
                """
                INSERT OR IGNORE INTO market_snapshots (
                    release_id,
                    analysis_run_id,
                    captured_at,
                    wants,
                    haves,
                    copies_for_sale,
                    lowest_price,
                    currency,
                    styles,
                    genres,
                    discogs_uri
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
                    analysis_run_id,
                    captured_at,
                    int(data.get("wants", 0) or 0),
                    int(data.get("haves", 0) or 0),
                    int(data.get("copies_for_sale", 0) or 0),
                    float(data.get("lowest_price", 0) or 0),
                    data.get("currency", ""),
                    data.get("styles", ""),
                    data.get("genres", ""),
                    data.get("discogs_uri", ""),
                ),
            )

        return cursor.rowcount == 1

    def previous_snapshot(
        self,
        release_id: int,
        before: str,
    ) -> sqlite3.Row | None:
        with self._lock:
            return self.conn.execute(
                """
                SELECT *
                FROM market_snapshots
                WHERE release_id = ?
                  AND captured_at < ?
                ORDER BY captured_at DESC
                LIMIT 1
                """,
                (release_id, before),
            ).fetchone()

    def upsert_score(
        self,
        release_id: int,
        calculated_at: str,
        score: dict[str, Any],
    ) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO scores (
                    release_id,
                    calculated_at,
                    value_score,
                    demand_score,
                    liquidity_score,
                    momentum_score,
                    opportunity_score,
                    sell_window,
                    priority,
                    explanation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(release_id) DO UPDATE SET
                    calculated_at = excluded.calculated_at,
                    value_score = excluded.value_score,
                    demand_score = excluded.demand_score,
                    liquidity_score = excluded.liquidity_score,
                    momentum_score = excluded.momentum_score,
                    opportunity_score = excluded.opportunity_score,
                    sell_window = excluded.sell_window,
                    priority = excluded.priority,
                    explanation = excluded.explanation
                """,
                (
                    release_id,
                    calculated_at,
                    score["value_score"],
                    score["demand_score"],
                    score["liquidity_score"],
                    score["momentum_score"],
                    score["opportunity_score"],
                    score["sell_window"],
                    score["priority"],
                    score["explanation"],
                ),
            )

    def dashboard(self) -> sqlite3.Row:
        with self._lock:
            return self.conn.execute(
                """
                SELECT
                    COUNT(*) AS unique_releases,
                    COALESCE(SUM(co.quantity), 0) AS owned_copies,
                    SUM(
                        CASE
                            WHEN s.priority = 'High-priority review'
                            THEN 1
                            ELSE 0
                        END
                    ) AS high_priority,
                    SUM(
                        CASE
                            WHEN s.priority = 'Worth reviewing'
                            THEN 1
                            ELSE 0
                        END
                    ) AS worth_reviewing,
                    SUM(
                        CASE
                            WHEN s.sell_window = 'Hot now'
                            THEN 1
                            ELSE 0
                        END
                    ) AS hot_now,
                    SUM(
                        CASE
                            WHEN d.protected = 1
                              OR d.decision = 'Keep'
                            THEN 1
                            ELSE 0
                        END
                    ) AS protected
                FROM releases r
                LEFT JOIN collection_ownership co
                    ON co.release_id = r.release_id
                LEFT JOIN scores s
                    ON s.release_id = r.release_id
                LEFT JOIN decisions d
                    ON d.release_id = r.release_id
                """
            ).fetchone()

    def review_rows(
        self,
        search: str = "",
        priority: str | ReviewFilterChoice = "",
        decision: str | ReviewFilterChoice = "",
        limit: int = 2000,
    ) -> list[sqlite3.Row]:
        where: list[str] = []
        params: list[Any] = []

        if search:
            where.append(
                """
                (
                    r.artist LIKE ?
                    OR r.title LIKE ?
                    OR r.label LIKE ?
                    OR r.catalog_no LIKE ?
                )
                """
            )
            query = f"%{search}%"
            params.extend([query, query, query, query])

        priority_value = _review_filter_value(priority, ReviewFilterField.PRIORITY)
        decision_value = _review_filter_value(decision, ReviewFilterField.DECISION)

        if priority_value is not None:
            where.append("COALESCE(s.priority, 'Not scored') = ?")
            params.append(priority_value)

        if decision_value is not None:
            where.append("COALESCE(d.decision, 'Review') = ?")
            params.append(decision_value)

        clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(max(1, int(limit)))

        with self._lock:
            return self.conn.execute(
                f"""
                WITH latest AS (
                    SELECT ms.*
                    FROM market_snapshots ms
                    JOIN (
                        SELECT
                            release_id,
                            MAX(captured_at) AS captured_at
                        FROM market_snapshots
                        GROUP BY release_id
                    ) latest_dates
                        ON latest_dates.release_id = ms.release_id
                       AND latest_dates.captured_at = ms.captured_at
                )
                SELECT
                    r.release_id,
                    r.artist,
                    r.title,
                    r.label,
                    r.catalog_no,
                    l.wants AS wants,
                    l.haves AS haves,
                    l.copies_for_sale AS copies_for_sale,
                    l.lowest_price AS lowest_price,
                    l.currency AS currency,
                    s.value_score AS value_score,
                    s.demand_score AS demand_score,
                    s.liquidity_score AS liquidity_score,
                    s.momentum_score AS momentum_score,
                    s.opportunity_score AS opportunity_score,
                    COALESCE(s.sell_window, 'Not scored') AS sell_window,
                    COALESCE(s.priority, 'Not scored') AS priority,
                    COALESCE(s.explanation, '') AS explanation,
                    COALESCE(d.decision, 'Review') AS decision,
                    COALESCE(d.miss_rating, 'Unsure') AS miss_rating,
                    COALESCE(d.personal_notes, '') AS personal_notes,
                    COALESCE(d.protected, 0) AS protected,
                    COALESCE(l.discogs_uri, '') AS discogs_uri
                FROM releases r
                LEFT JOIN latest l
                    ON l.release_id = r.release_id
                LEFT JOIN scores s
                    ON s.release_id = r.release_id
                LEFT JOIN decisions d
                    ON d.release_id = r.release_id
                {clause}
                ORDER BY
                    s.opportunity_score DESC,
                    l.lowest_price DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

    def review_filter_values(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return exact visible priority and decision values deterministically."""

        with self._lock:
            rows = self.conn.execute(
                """
                SELECT DISTINCT
                    COALESCE(s.priority, 'Not scored') AS priority,
                    COALESCE(d.decision, 'Review') AS decision
                FROM releases r
                LEFT JOIN scores s ON s.release_id = r.release_id
                LEFT JOIN decisions d ON d.release_id = r.release_id
                ORDER BY 1 COLLATE BINARY, 2 COLLATE BINARY
                """
            ).fetchall()
        return (
            tuple(sorted({row["priority"] for row in rows})),
            tuple(sorted({row["decision"] for row in rows})),
        )

    def save_decision(
        self,
        release_id: int,
        decision: str,
        miss_rating: str,
        notes: str,
        protected: bool,
    ) -> None:
        decision = validate_writable_decision(decision)
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO decisions (
                    release_id,
                    decision,
                    miss_rating,
                    personal_notes,
                    protected,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(release_id) DO UPDATE SET
                    decision = excluded.decision,
                    miss_rating = excluded.miss_rating,
                    personal_notes = excluded.personal_notes,
                    protected = excluded.protected,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    release_id,
                    decision,
                    miss_rating,
                    notes,
                    int(protected),
                ),
            )


def _review_filter_value(
    selection: str | ReviewFilterChoice,
    field: ReviewFilterField,
) -> str | None:
    if type(selection) is ReviewFilterChoice:
        if selection.field is not field:
            raise ValueError("Review filter field does not match its query.")
        if selection.kind is ReviewFilterChoiceKind.ALL:
            return None
        return selection.query_value
    if type(selection) is not str:
        raise TypeError("review filter must be a string or ReviewFilterChoice.")
    return None if not selection or selection == "All" else selection
