-- Agentic RFP Evaluation - SQLite schema
-- Minimum tables required by the brief, plus one criterion-level table for traceability.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id  INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,
    description   TEXT    NOT NULL,
    weight        REAL    NOT NULL CHECK (weight >= 0 AND weight <= 100),
    max_score     INTEGER NOT NULL DEFAULT 10 CHECK (max_score > 0),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id         TEXT PRIMARY KEY,
    created_at         TEXT NOT NULL,
    status             TEXT NOT NULL,          -- RUNNING | COMPLETED | COMPLETED_WITH_WARNINGS | FAILED
    ranking_mode       TEXT,
    llm_provider       TEXT,
    llm_model          TEXT,
    criteria_snapshot  TEXT,                   -- JSON: criteria exactly as used by this run
    run_warnings       TEXT,                   -- JSON list
    export_json        TEXT                    -- full downloadable result
);

CREATE TABLE IF NOT EXISTS supplier_results (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id         TEXT    NOT NULL REFERENCES rfp_runs(rfp_run_id) ON DELETE CASCADE,
    supplier_name      TEXT    NOT NULL,
    submission_date    TEXT    NOT NULL,
    experience_rating  REAL    NOT NULL,
    absolute_score     REAL    NOT NULL,
    ppi                REAL    NOT NULL,
    final_rank         INTEGER NOT NULL,
    result_json        TEXT    NOT NULL,
    UNIQUE (rfp_run_id, supplier_name)
);

CREATE TABLE IF NOT EXISTS criterion_assessments (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id         TEXT    NOT NULL REFERENCES rfp_runs(rfp_run_id) ON DELETE CASCADE,
    supplier_name      TEXT    NOT NULL,
    criterion_id       INTEGER NOT NULL,
    criterion_name     TEXT    NOT NULL,
    weight             REAL    NOT NULL,
    max_score          INTEGER NOT NULL,
    score              REAL    NOT NULL,
    benchmark          REAL    NOT NULL,
    gap                REAL    NOT NULL,
    relative_pct       REAL    NOT NULL,
    weighted_points    REAL    NOT NULL,
    justification      TEXT,
    evidence           TEXT,
    evidence_verified  INTEGER NOT NULL DEFAULT 0,
    normalized         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_supplier_results_run ON supplier_results(rfp_run_id);
CREATE INDEX IF NOT EXISTS idx_assessments_run ON criterion_assessments(rfp_run_id);
