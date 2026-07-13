PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
    FOREIGN KEY (release_id)
        REFERENCES releases(release_id)
        ON DELETE CASCADE,
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
    FOREIGN KEY (release_id)
        REFERENCES releases(release_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    release_id INTEGER PRIMARY KEY,
    decision TEXT NOT NULL DEFAULT 'Review',
    miss_rating TEXT NOT NULL DEFAULT 'Unsure',
    personal_notes TEXT NOT NULL DEFAULT '',
    protected INTEGER NOT NULL DEFAULT 0
        CHECK (protected IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (release_id)
        REFERENCES releases(release_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

INSERT OR IGNORE INTO schema_migrations(version)
VALUES (1);