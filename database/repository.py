from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Iterable

from .connection import create_connection
from .schema import initialise_schema


class Database:
    """Persistence layer for the Discogs Intelligence Platform."""

    def __init__(self, path: Path):
        self.path = Path(path).expanduser().resolve()
        self._lock = RLock()
        self.conn = create_connection(self.path)
        initialise_schema(self.conn)

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

    def add_snapshot(
        self,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    release_id,
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
        priority: str = "",
        decision: str = "",
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

        if priority and priority != "All":
            where.append("s.priority = ?")
            params.append(priority)

        if decision and decision != "All":
            where.append("d.decision = ?")
            params.append(decision)

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
                    COALESCE(l.wants, 0) AS wants,
                    COALESCE(l.haves, 0) AS haves,
                    COALESCE(l.copies_for_sale, 0) AS copies_for_sale,
                    COALESCE(l.lowest_price, 0) AS lowest_price,
                    COALESCE(l.currency, '') AS currency,
                    COALESCE(s.value_score, 0) AS value_score,
                    COALESCE(s.demand_score, 0) AS demand_score,
                    COALESCE(s.liquidity_score, 0) AS liquidity_score,
                    COALESCE(s.momentum_score, 0) AS momentum_score,
                    COALESCE(s.opportunity_score, 0) AS opportunity_score,
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

    def save_decision(
        self,
        release_id: int,
        decision: str,
        miss_rating: str,
        notes: str,
        protected: bool,
    ) -> None:
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