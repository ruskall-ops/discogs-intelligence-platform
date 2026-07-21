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
CREATE TABLE IF NOT EXISTS collection_ownership (
    release_id INTEGER PRIMARY KEY,
    quantity INTEGER NOT NULL DEFAULT 1
        CHECK (quantity >= 0),
    collection_folder TEXT,
    rating TEXT,
    date_added TEXT,
    media_condition TEXT,
    sleeve_condition TEXT,
    notes TEXT,
    last_imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (release_id)
        REFERENCES releases(release_id)
        ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL DEFAULT 'market_refresh',
    source TEXT NOT NULL DEFAULT 'discogs',
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    releases_attempted INTEGER NOT NULL DEFAULT 0,
    releases_succeeded INTEGER NOT NULL DEFAULT 0,
    releases_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    application_version TEXT
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_started_at
ON analysis_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_status
ON analysis_runs(status);

CREATE INDEX IF NOT EXISTS idx_collection_ownership_quantity
ON collection_ownership(quantity);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id INTEGER NOT NULL,
    analysis_run_id INTEGER,
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
    FOREIGN KEY (analysis_run_id)
    REFERENCES analysis_runs(id)
    ON DELETE SET NULL,
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

CREATE TABLE IF NOT EXISTS intelligence_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    executed_at TEXT NOT NULL,
    executed_at_json TEXT NOT NULL,
    engine_version TEXT,
    collection_snapshot_id INTEGER,
    result_count INTEGER NOT NULL CHECK (result_count >= 0)
);

CREATE TABLE IF NOT EXISTS intelligence_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    module_id TEXT NOT NULL,
    module_version TEXT,
    status_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    insights_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL,
    FOREIGN KEY (run_id)
        REFERENCES intelligence_runs(id)
        ON DELETE RESTRICT,
    UNIQUE (run_id, module_id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_runs_executed
ON intelligence_runs(executed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_intelligence_results_module_run
ON intelligence_results(module_id, run_id DESC);

INSERT OR IGNORE INTO schema_migrations(version)
VALUES (1);
