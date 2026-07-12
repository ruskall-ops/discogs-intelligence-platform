
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable, Any

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS releases (
    release_id INTEGER PRIMARY KEY,
    artist TEXT,
    title TEXT,
    label TEXT,
    catalog_no TEXT,
    format TEXT,
    released TEXT,
    collection_folder TEXT,
    date_added TEXT,
    rating TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    wants INTEGER NOT NULL DEFAULT 0,
    haves INTEGER NOT NULL DEFAULT 0,
    copies_for_sale INTEGER NOT NULL DEFAULT 0,
    lowest_price REAL NOT NULL DEFAULT 0,
    currency TEXT,
    styles TEXT,
    genres TEXT,
    discogs_uri TEXT,
    FOREIGN KEY (release_id) REFERENCES releases(release_id) ON DELETE CASCADE,
    UNIQUE(release_id, captured_at)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_release_date
ON market_snapshots(release_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS scores (
    release_id INTEGER PRIMARY KEY,
    calculated_at TEXT NOT NULL,
    value_score REAL NOT NULL DEFAULT 0,
    demand_score REAL NOT NULL DEFAULT 0,
    liquidity_score REAL NOT NULL DEFAULT 0,
    momentum_score REAL NOT NULL DEFAULT 0,
    opportunity_score REAL NOT NULL DEFAULT 0,
    sell_window TEXT,
    priority TEXT,
    explanation TEXT,
    FOREIGN KEY (release_id) REFERENCES releases(release_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    release_id INTEGER PRIMARY KEY,
    decision TEXT NOT NULL DEFAULT 'Review',
    miss_rating TEXT NOT NULL DEFAULT 'Unsure',
    personal_notes TEXT NOT NULL DEFAULT '',
    protected INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (release_id) REFERENCES releases(release_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def import_releases(self, rows: Iterable[dict[str, Any]], release_col: str) -> int:
        sql = """
        INSERT INTO releases (
            release_id, artist, title, label, catalog_no, format,
            released, collection_folder, date_added, rating
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(release_id) DO UPDATE SET
            artist=excluded.artist,
            title=excluded.title,
            label=excluded.label,
            catalog_no=excluded.catalog_no,
            format=excluded.format,
            released=excluded.released,
            collection_folder=excluded.collection_folder,
            date_added=excluded.date_added,
            rating=excluded.rating
        """
        count = 0
        with self.conn:
            for row in rows:
                rid = str(row.get(release_col, "")).strip()
                if not rid:
                    continue
                self.conn.execute(sql, (
                    int(rid),
                    row.get("Artist", ""),
                    row.get("Title", ""),
                    row.get("Label", ""),
                    row.get("Catalog#", ""),
                    row.get("Format", ""),
                    row.get("Released", ""),
                    row.get("CollectionFolder", ""),
                    row.get("Date Added", ""),
                    row.get("Rating", ""),
                ))
                self.conn.execute(
                    "INSERT OR IGNORE INTO decisions(release_id) VALUES (?)",
                    (int(rid),)
                )
                count += 1
        return count

    def release_ids(self):
        return [r["release_id"] for r in self.conn.execute(
            "SELECT release_id FROM releases ORDER BY release_id"
        )]

    def add_snapshot(self, release_id: int, captured_at: str, data: dict):
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO market_snapshots (
                    release_id, captured_at, wants, haves, copies_for_sale,
                    lowest_price, currency, styles, genres, discogs_uri
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                release_id, captured_at,
                int(data.get("wants", 0)),
                int(data.get("haves", 0)),
                int(data.get("copies_for_sale", 0)),
                float(data.get("lowest_price", 0) or 0),
                data.get("currency", ""),
                data.get("styles", ""),
                data.get("genres", ""),
                data.get("discogs_uri", ""),
            ))

    def previous_snapshot(self, release_id: int, before: str):
        return self.conn.execute("""
            SELECT * FROM market_snapshots
            WHERE release_id=? AND captured_at < ?
            ORDER BY captured_at DESC LIMIT 1
        """, (release_id, before)).fetchone()

    def upsert_score(self, release_id: int, calculated_at: str, score: dict):
        with self.conn:
            self.conn.execute("""
                INSERT INTO scores (
                    release_id, calculated_at, value_score, demand_score,
                    liquidity_score, momentum_score, opportunity_score,
                    sell_window, priority, explanation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(release_id) DO UPDATE SET
                    calculated_at=excluded.calculated_at,
                    value_score=excluded.value_score,
                    demand_score=excluded.demand_score,
                    liquidity_score=excluded.liquidity_score,
                    momentum_score=excluded.momentum_score,
                    opportunity_score=excluded.opportunity_score,
                    sell_window=excluded.sell_window,
                    priority=excluded.priority,
                    explanation=excluded.explanation
            """, (
                release_id, calculated_at,
                score["value_score"], score["demand_score"],
                score["liquidity_score"], score["momentum_score"],
                score["opportunity_score"], score["sell_window"],
                score["priority"], score["explanation"],
            ))

    def dashboard(self):
        return self.conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN s.priority='High-priority review' THEN 1 ELSE 0 END) AS high_priority,
                SUM(CASE WHEN s.priority='Worth reviewing' THEN 1 ELSE 0 END) AS worth_reviewing,
                SUM(CASE WHEN s.sell_window='Hot now' THEN 1 ELSE 0 END) AS hot_now,
                SUM(CASE WHEN d.protected=1 OR d.decision='Keep' THEN 1 ELSE 0 END) AS protected
            FROM releases r
            LEFT JOIN scores s ON s.release_id=r.release_id
            LEFT JOIN decisions d ON d.release_id=r.release_id
        """).fetchone()

    def review_rows(self, search="", priority="", decision="", limit=2000):
        where = []
        params = []
        if search:
            where.append("(r.artist LIKE ? OR r.title LIKE ? OR r.label LIKE ? OR r.catalog_no LIKE ?)")
            q = f"%{search}%"
            params += [q, q, q, q]
        if priority and priority != "All":
            where.append("s.priority=?")
            params.append(priority)
        if decision and decision != "All":
            where.append("d.decision=?")
            params.append(decision)
        clause = "WHERE " + " AND ".join(where) if where else ""
        params.append(limit)
        return self.conn.execute(f"""
            WITH latest AS (
                SELECT ms.*
                FROM market_snapshots ms
                JOIN (
                    SELECT release_id, MAX(captured_at) captured_at
                    FROM market_snapshots GROUP BY release_id
                ) x ON x.release_id=ms.release_id AND x.captured_at=ms.captured_at
            )
            SELECT r.release_id, r.artist, r.title, r.label, r.catalog_no,
                   COALESCE(l.wants,0) wants,
                   COALESCE(l.haves,0) haves,
                   COALESCE(l.copies_for_sale,0) copies_for_sale,
                   COALESCE(l.lowest_price,0) lowest_price,
                   COALESCE(l.currency,'') currency,
                   COALESCE(s.value_score,0) value_score,
                   COALESCE(s.demand_score,0) demand_score,
                   COALESCE(s.liquidity_score,0) liquidity_score,
                   COALESCE(s.momentum_score,0) momentum_score,
                   COALESCE(s.opportunity_score,0) opportunity_score,
                   COALESCE(s.sell_window,'Not scored') sell_window,
                   COALESCE(s.priority,'Not scored') priority,
                   COALESCE(s.explanation,'') explanation,
                   COALESCE(d.decision,'Review') decision,
                   COALESCE(d.miss_rating,'Unsure') miss_rating,
                   COALESCE(d.personal_notes,'') personal_notes,
                   COALESCE(d.protected,0) protected,
                   COALESCE(l.discogs_uri,'') discogs_uri
            FROM releases r
            LEFT JOIN latest l ON l.release_id=r.release_id
            LEFT JOIN scores s ON s.release_id=r.release_id
            LEFT JOIN decisions d ON d.release_id=r.release_id
            {clause}
            ORDER BY s.opportunity_score DESC, l.lowest_price DESC
            LIMIT ?
        """, params).fetchall()

    def save_decision(self, release_id, decision, miss_rating, notes, protected):
        with self.conn:
            self.conn.execute("""
                INSERT INTO decisions (
                    release_id, decision, miss_rating, personal_notes, protected, updated_at
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(release_id) DO UPDATE SET
                    decision=excluded.decision,
                    miss_rating=excluded.miss_rating,
                    personal_notes=excluded.personal_notes,
                    protected=excluded.protected,
                    updated_at=CURRENT_TIMESTAMP
            """, (release_id, decision, miss_rating, notes, int(protected)))
