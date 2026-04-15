-- Game Bot 資料庫初始化
-- SQLite 3 — WAL 模式、外鍵約束

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ═══════════════════════════════════════════
--  腳本表
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS scripts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    version     INTEGER DEFAULT 1,
    nodes       TEXT NOT NULL DEFAULT '[]',
    edges       TEXT NOT NULL DEFAULT '[]',
    settings    TEXT NOT NULL DEFAULT '{}',
    rules       TEXT NOT NULL DEFAULT '[]',
    tags        TEXT DEFAULT '',
    is_deleted  INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ═══════════════════════════════════════════
--  任務表
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS tasks (
    job_id      TEXT PRIMARY KEY,
    script_id   TEXT NOT NULL,
    script_name TEXT NOT NULL,
    run_mode    TEXT NOT NULL DEFAULT 'loop',
    max_runs    INTEGER DEFAULT 0,
    run_count   INTEGER DEFAULT 0,
    enabled     INTEGER DEFAULT 1,
    completed   INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'pending',
    error_msg   TEXT DEFAULT '',
    started_at  TEXT,
    stopped_at  TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE SET NULL
);

-- ═══════════════════════════════════════════
--  任務執行歷史
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS task_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL,
    run_number  INTEGER NOT NULL,
    status      TEXT NOT NULL,
    duration_ms INTEGER DEFAULT 0,
    error_msg   TEXT DEFAULT '',
    log_summary TEXT DEFAULT '',
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (job_id) REFERENCES tasks(job_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════
--  系統日誌
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT DEFAULT 'info',
    source     TEXT DEFAULT 'system',
    job_id     TEXT,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- ═══════════════════════════════════════════
--  模板圖片 metadata
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS assets (
    name        TEXT PRIMARY KEY,
    file_path   TEXT NOT NULL,
    file_size   INTEGER DEFAULT 0,
    width       INTEGER DEFAULT 0,
    height      INTEGER DEFAULT 0,
    tags        TEXT DEFAULT '',
    description TEXT DEFAULT '',
    used_in     TEXT DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ═══════════════════════════════════════════
--  全域設定 (Key-Value)
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ═══════════════════════════════════════════
--  排程 (未來擴展)
-- ═══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS schedules (
    id          TEXT PRIMARY KEY,
    script_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    cron_expr   TEXT NOT NULL,
    run_mode    TEXT DEFAULT 'loop',
    max_runs    INTEGER DEFAULT 0,
    enabled     INTEGER DEFAULT 1,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════
--  索引
-- ═══════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_scripts_name ON scripts(name);
CREATE INDEX IF NOT EXISTS idx_scripts_updated ON scripts(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_runs_job ON task_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_time ON task_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_source ON logs(source);
CREATE INDEX IF NOT EXISTS idx_logs_time ON logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_job ON logs(job_id);

-- ═══════════════════════════════════════════
--  預設設定
-- ═══════════════════════════════════════════
INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
    ('device.default_serial', '"127.0.0.1:5555"', datetime('now')),
    ('device.mode', '"adb"', datetime('now')),
    ('device.emulator_type', '"auto"', datetime('now')),
    ('task.auto_restart', 'false', datetime('now')),
    ('task.default_interval', '3', datetime('now')),
    ('ui.theme', '"dark"', datetime('now')),
    ('log.max_entries', '10000', datetime('now')),
    ('log.auto_clean_days', '7', datetime('now'));
