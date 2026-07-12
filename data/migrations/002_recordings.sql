-- Game Bot 錄製記錄表
-- 002_recordings.sql

CREATE TABLE IF NOT EXISTS recordings (
    id          TEXT PRIMARY KEY,
    script_id   TEXT,
    name        TEXT NOT NULL,
    actions     TEXT NOT NULL DEFAULT '[]',
    duration_ms INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_recordings_script ON recordings(script_id);
CREATE INDEX IF NOT EXISTS idx_recordings_created ON recordings(created_at DESC);
