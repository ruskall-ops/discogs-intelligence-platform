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
    result_count INTEGER NOT NULL CHECK (result_count >= 0),
    marketplace_snapshot_id TEXT
        REFERENCES marketplace_snapshots(snapshot_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_intelligence_runs_marketplace_snapshot
ON intelligence_runs(marketplace_snapshot_id)
WHERE marketplace_snapshot_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS marketplace_snapshots (
    snapshot_id TEXT PRIMARY KEY NOT NULL,
    captured_at TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN (
            'complete',
            'partial',
            'empty',
            'unavailable',
            'failed'
        )),
    schema_version INTEGER NOT NULL
        CHECK (schema_version > 0),
    payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_marketplace_snapshots_captured
ON marketplace_snapshots(captured_at DESC, snapshot_id DESC);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    last_opened_order INTEGER
        CHECK (last_opened_order IS NULL OR last_opened_order > 0),
    insertion_order INTEGER NOT NULL UNIQUE
        CHECK (insertion_order > 0)
);

CREATE TABLE IF NOT EXISTS project_state (
    singleton_id INTEGER PRIMARY KEY
        CHECK (singleton_id = 1),
    active_project_id TEXT,
    FOREIGN KEY (active_project_id)
        REFERENCES projects(project_id)
        ON DELETE RESTRICT
);

INSERT OR IGNORE INTO project_state(singleton_id, active_project_id)
VALUES (1, NULL);

CREATE TABLE IF NOT EXISTS weekend_review_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id INTEGER NOT NULL UNIQUE
        CHECK (typeof(release_id) = 'integer' AND release_id > 0),
    added_at TEXT NOT NULL
        CHECK (length(trim(added_at)) > 0),
    status TEXT NOT NULL
        CHECK (status IN ('to_review', 'reviewing', 'resolved')),
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
            AND instr(source_summary, char(32) || char(32)) = 0
            AND instr(source_summary, char(9)) = 0
            AND instr(source_summary, char(10)) = 0
            AND instr(source_summary, char(13)) = 0
        ),
    source_intelligence_run_id INTEGER,
    source_marketplace_snapshot_id TEXT,
    CHECK (
        (status = 'resolved' AND resolved_at IS NOT NULL)
        OR
        (status <> 'resolved' AND resolved_at IS NULL)
    ),
    CHECK (julianday(added_at) IS NOT NULL),
    CHECK (julianday(updated_at) IS NOT NULL),
    CHECK (julianday(source_observed_at) IS NOT NULL),
    CHECK (julianday(source_observed_at) <= julianday(added_at)),
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
);

CREATE INDEX IF NOT EXISTS idx_weekend_review_queue_status_order
ON weekend_review_queue(status, added_at ASC, id ASC);

CREATE TABLE IF NOT EXISTS desktop_session (
    singleton_id INTEGER PRIMARY KEY
        CHECK (singleton_id = 1),
    format_version INTEGER NOT NULL
        CHECK (format_version = 1),
    saved_at TEXT NOT NULL
        CHECK (length(trim(saved_at)) > 0),
    active_project_id TEXT
        CHECK (
            active_project_id IS NULL
            OR (
                length(active_project_id) > 0
                AND active_project_id = trim(active_project_id)
            )
        ),
    window_width INTEGER NOT NULL
        CHECK (window_width BETWEEN 1050 AND 32767),
    window_height INTEGER NOT NULL
        CHECK (window_height BETWEEN 650 AND 32767),
    window_x INTEGER NOT NULL
        CHECK (window_x BETWEEN -2147483648 AND 2147483647),
    window_y INTEGER NOT NULL
        CHECK (window_y BETWEEN -2147483648 AND 2147483647),
    top_level_destination TEXT NOT NULL
        CHECK (
            top_level_destination IN (
                'project',
                'dashboard',
                'collection_review'
            )
        ),
    collection_review_destination TEXT NOT NULL
        CHECK (
            collection_review_destination IN (
                'observations',
                'weekend_review_queue',
                'collection_decisions'
            )
        ),
    observation_source TEXT NOT NULL
        CHECK (observation_source IN ('hot_now', 'hidden_gem')),
    queue_filter TEXT NOT NULL
        CHECK (queue_filter IN ('active', 'resolved', 'all')),
    decision_priority_filter TEXT NOT NULL
        CHECK (
            decision_priority_filter IN (
                'all',
                'high_priority_review',
                'worth_reviewing',
                'possible_candidate',
                'low_priority',
                'not_scored'
            )
        ),
    decision_state_filter TEXT NOT NULL
        CHECK (
            decision_state_filter IN (
                'all',
                'review',
                'keep',
                'list_for_sale',
                'maybe',
                'ignore'
            )
        ),
    selected_observation_source TEXT
        CHECK (
            selected_observation_source IS NULL
            OR selected_observation_source IN ('hot_now', 'hidden_gem')
        ),
    selected_observation_release_id INTEGER
        CHECK (
            selected_observation_release_id IS NULL
            OR selected_observation_release_id > 0
        ),
    selected_queue_item_id INTEGER
        CHECK (
            selected_queue_item_id IS NULL
            OR selected_queue_item_id > 0
        ),
    selected_decision_release_id INTEGER
        CHECK (
            selected_decision_release_id IS NULL
            OR selected_decision_release_id > 0
        ),
    CHECK (
        (selected_observation_source IS NULL)
        =
        (selected_observation_release_id IS NULL)
    )
);

INSERT OR IGNORE INTO schema_migrations(version)
VALUES (1);
