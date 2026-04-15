// SQLite 資料庫存取層 — 與 Python 端共用同一個 DB 檔案
use rusqlite::{Connection, params};
use serde_json::Value;
use std::path::PathBuf;
use std::sync::Mutex;

/// 取得資料庫路徑（專案根目錄下 data/gamebot.db）
pub fn db_path() -> PathBuf {
    // 從 src-tauri 向上兩層到專案根目錄
    let path = std::env::current_dir().unwrap_or_default();
    // 嘗試找到 data 資料夾
    let data_dir = path.join("data");
    if !data_dir.exists() {
        // 可能在 frontend/src-tauri 底下執行
        let parent_data = path.parent()
            .and_then(|p| p.parent())
            .map(|p| p.join("data"))
            .unwrap_or_else(|| data_dir.clone());
        if parent_data.exists() {
            return parent_data.join("gamebot.db");
        }
        std::fs::create_dir_all(&data_dir).ok();
    }
    data_dir.join("gamebot.db")
}

/// 初始化資料庫（建表 + 索引 + 預設設定）
pub fn init_db() -> rusqlite::Result<Connection> {
    let path = db_path();
    println!("📁 資料庫路徑: {:?}", path);

    // 確保目錄存在
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }

    let conn = Connection::open(&path)?;
    conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")?;

    // 執行建表 SQL
    conn.execute_batch(INIT_SQL)?;

    println!("✅ 資料庫初始化完成");
    Ok(conn)
}

/// 封裝為 Tauri State 可用的型別
pub struct DbState {
    pub conn: Mutex<Connection>,
}

impl DbState {
    pub fn new() -> Result<Self, String> {
        let conn = init_db().map_err(|e| format!("DB 初始化失敗: {}", e))?;
        Ok(Self { conn: Mutex::new(conn) })
    }
}

// ═══════════════════════════════════════════
//  腳本 CRUD
// ═══════════════════════════════════════════

/// 取得所有腳本
pub fn script_list_db(conn: &Connection) -> rusqlite::Result<Vec<Value>> {
    let mut stmt = conn.prepare(
        "SELECT id, name, description, version, nodes, edges, settings, rules, tags, created_at, updated_at
         FROM scripts WHERE is_deleted = 0 ORDER BY updated_at DESC"
    )?;

    let rows = stmt.query_map([], |row| {
        Ok(serde_json::json!({
            "id": row.get::<_, String>(0)?,
            "name": row.get::<_, String>(1)?,
            "description": row.get::<_, String>(2).unwrap_or_default(),
            "version": row.get::<_, i64>(3)?,
            "nodes": serde_json::from_str::<Value>(&row.get::<_, String>(4)?).unwrap_or(Value::Array(vec![])),
            "edges": serde_json::from_str::<Value>(&row.get::<_, String>(5)?).unwrap_or(Value::Array(vec![])),
            "settings": serde_json::from_str::<Value>(&row.get::<_, String>(6)?).unwrap_or(Value::Object(Default::default())),
            "rules": serde_json::from_str::<Value>(&row.get::<_, String>(7)?).unwrap_or(Value::Array(vec![])),
            "tags": row.get::<_, String>(8).unwrap_or_default(),
            "created_at": row.get::<_, String>(9)?,
            "updated_at": row.get::<_, String>(10)?,
        }))
    })?;

    rows.collect::<rusqlite::Result<Vec<Value>>>()
}

/// 建立新腳本
pub fn script_create_db(conn: &Connection, name: &str) -> rusqlite::Result<Value> {
    let id = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();
    let default_nodes = serde_json::json!([
        {"id": "start_1", "type": "start", "position": {"x": 100, "y": 200}, "data": {}},
        {"id": "end_1", "type": "end", "position": {"x": 600, "y": 200}, "data": {}},
    ]).to_string();
    let default_settings = serde_json::json!({"loop_enabled": true, "interval": 3, "max_runs": 0}).to_string();

    conn.execute(
        "INSERT INTO scripts (id, name, version, nodes, edges, settings, rules, created_at, updated_at)
         VALUES (?1, ?2, 1, ?3, '[]', ?4, '[]', ?5, ?6)",
        params![id, name, default_nodes, default_settings, now, now],
    )?;

    script_get_db(conn, &id)
}

/// 取得單一腳本
pub fn script_get_db(conn: &Connection, script_id: &str) -> rusqlite::Result<Value> {
    conn.query_row(
        "SELECT id, name, description, version, nodes, edges, settings, rules, tags, created_at, updated_at
         FROM scripts WHERE id = ?1 AND is_deleted = 0",
        params![script_id],
        |row| {
            Ok(serde_json::json!({
                "id": row.get::<_, String>(0)?,
                "name": row.get::<_, String>(1)?,
                "description": row.get::<_, String>(2).unwrap_or_default(),
                "version": row.get::<_, i64>(3)?,
                "nodes": serde_json::from_str::<Value>(&row.get::<_, String>(4)?).unwrap_or(Value::Array(vec![])),
                "edges": serde_json::from_str::<Value>(&row.get::<_, String>(5)?).unwrap_or(Value::Array(vec![])),
                "settings": serde_json::from_str::<Value>(&row.get::<_, String>(6)?).unwrap_or(Value::Object(Default::default())),
                "rules": serde_json::from_str::<Value>(&row.get::<_, String>(7)?).unwrap_or(Value::Array(vec![])),
                "tags": row.get::<_, String>(8).unwrap_or_default(),
                "created_at": row.get::<_, String>(9)?,
                "updated_at": row.get::<_, String>(10)?,
            }))
        },
    )
}

/// 儲存腳本
pub fn script_save_db(conn: &Connection, script: &Value) -> rusqlite::Result<Value> {
    let now = chrono::Utc::now().to_rfc3339();
    let id = script["id"].as_str().unwrap_or("");

    conn.execute(
        "UPDATE scripts SET name = ?1, version = version + 1,
         nodes = ?2, edges = ?3, settings = ?4, rules = ?5,
         tags = ?6, description = ?7, updated_at = ?8
         WHERE id = ?9",
        params![
            script["name"].as_str().unwrap_or(""),
            serde_json::to_string(&script["nodes"]).unwrap_or_else(|_| "[]".to_string()),
            serde_json::to_string(&script["edges"]).unwrap_or_else(|_| "[]".to_string()),
            serde_json::to_string(&script["settings"]).unwrap_or_else(|_| "{}".to_string()),
            serde_json::to_string(&script["rules"]).unwrap_or_else(|_| "[]".to_string()),
            script["tags"].as_str().unwrap_or(""),
            script["description"].as_str().unwrap_or(""),
            now,
            id,
        ],
    )?;

    script_get_db(conn, id)
}

/// 軟刪除腳本
pub fn script_delete_db(conn: &Connection, script_id: &str) -> rusqlite::Result<()> {
    let now = chrono::Utc::now().to_rfc3339();
    conn.execute(
        "UPDATE scripts SET is_deleted = 1, updated_at = ?1 WHERE id = ?2",
        params![now, script_id],
    )?;
    Ok(())
}

// ═══════════════════════════════════════════
//  任務 CRUD
// ═══════════════════════════════════════════

/// 取得所有任務
pub fn task_list_db(conn: &Connection) -> rusqlite::Result<Vec<Value>> {
    let mut stmt = conn.prepare(
        "SELECT job_id, script_id, script_name, run_mode, max_runs, run_count,
                enabled, completed, status, error_msg, started_at, stopped_at, created_at, updated_at
         FROM tasks ORDER BY created_at DESC"
    )?;

    let rows = stmt.query_map([], |row| {
        Ok(serde_json::json!({
            "job_id": row.get::<_, String>(0)?,
            "script_id": row.get::<_, String>(1)?,
            "script_name": row.get::<_, String>(2)?,
            "run_mode": row.get::<_, String>(3)?,
            "max_runs": row.get::<_, i64>(4)?,
            "run_count": row.get::<_, i64>(5)?,
            "enabled": row.get::<_, bool>(6)?,
            "completed": row.get::<_, bool>(7)?,
            "status": row.get::<_, String>(8).unwrap_or_default(),
            "error_msg": row.get::<_, String>(9).unwrap_or_default(),
        }))
    })?;

    rows.collect::<rusqlite::Result<Vec<Value>>>()
}

/// 建立新任務
pub fn task_create_db(
    conn: &Connection,
    script_id: &str,
    script_name: &str,
    run_mode: &str,
    max_runs: u32,
) -> rusqlite::Result<Value> {
    let job_id = uuid::Uuid::new_v4().to_string()[..8].to_string();
    let now = chrono::Utc::now().to_rfc3339();

    conn.execute(
        "INSERT INTO tasks (job_id, script_id, script_name, run_mode, max_runs,
         run_count, enabled, completed, status, started_at, created_at, updated_at)
         VALUES (?1, ?2, ?3, ?4, ?5, 0, 1, 0, 'running', ?6, ?7, ?8)",
        params![job_id, script_id, script_name, run_mode, max_runs, now, now, now],
    )?;

    Ok(serde_json::json!({
        "job_id": job_id,
        "script_id": script_id,
        "script_name": script_name,
        "run_mode": run_mode,
        "max_runs": max_runs,
        "run_count": 0,
        "enabled": true,
        "completed": false,
    }))
}

/// 暫停/繼續任務
pub fn task_toggle_db(conn: &Connection, job_id: &str) -> rusqlite::Result<Value> {
    let now = chrono::Utc::now().to_rfc3339();

    // 取得目前狀態
    let enabled: bool = conn.query_row(
        "SELECT enabled FROM tasks WHERE job_id = ?1",
        params![job_id],
        |row| row.get(0),
    )?;

    let new_enabled = !enabled;
    let new_status = if new_enabled { "running" } else { "paused" };

    conn.execute(
        "UPDATE tasks SET enabled = ?1, status = ?2, updated_at = ?3 WHERE job_id = ?4",
        params![new_enabled, new_status, now, job_id],
    )?;

    // 回傳更新後的任務
    task_get_db(conn, job_id)
}

/// 取得單一任務
pub fn task_get_db(conn: &Connection, job_id: &str) -> rusqlite::Result<Value> {
    conn.query_row(
        "SELECT job_id, script_id, script_name, run_mode, max_runs, run_count,
                enabled, completed, status, error_msg
         FROM tasks WHERE job_id = ?1",
        params![job_id],
        |row| {
            Ok(serde_json::json!({
                "job_id": row.get::<_, String>(0)?,
                "script_id": row.get::<_, String>(1)?,
                "script_name": row.get::<_, String>(2)?,
                "run_mode": row.get::<_, String>(3)?,
                "max_runs": row.get::<_, i64>(4)?,
                "run_count": row.get::<_, i64>(5)?,
                "enabled": row.get::<_, bool>(6)?,
                "completed": row.get::<_, bool>(7)?,
                "status": row.get::<_, String>(8).unwrap_or_default(),
                "error_msg": row.get::<_, String>(9).unwrap_or_default(),
            }))
        },
    )
}

/// 停止任務
pub fn task_stop_db(conn: &Connection, job_id: &str) -> rusqlite::Result<()> {
    let now = chrono::Utc::now().to_rfc3339();
    conn.execute(
        "UPDATE tasks SET enabled = 0, completed = 1, status = 'stopped',
         stopped_at = ?1, updated_at = ?2 WHERE job_id = ?3",
        params![now, now, job_id],
    )?;
    Ok(())
}

/// 移除任務
pub fn task_remove_db(conn: &Connection, job_id: &str) -> rusqlite::Result<()> {
    conn.execute("DELETE FROM tasks WHERE job_id = ?1", params![job_id])?;
    Ok(())
}

// ═══════════════════════════════════════════
//  日誌
// ═══════════════════════════════════════════

/// 新增日誌
pub fn log_add_db(conn: &Connection, message: &str, level: &str, source: &str) -> rusqlite::Result<()> {
    let now = chrono::Utc::now().to_rfc3339();
    conn.execute(
        "INSERT INTO logs (level, source, message, created_at) VALUES (?1, ?2, ?3, ?4)",
        params![level, source, message, now],
    )?;
    Ok(())
}

/// 取得日誌
pub fn log_list_db(conn: &Connection, limit: usize) -> rusqlite::Result<Vec<String>> {
    let mut stmt = conn.prepare(
        "SELECT message, created_at FROM logs ORDER BY id DESC LIMIT ?1"
    )?;

    let rows = stmt.query_map(params![limit as i64], |row| {
        let msg: String = row.get(0)?;
        let ts: String = row.get(1)?;
        // 提取時間部分
        let time_part = if ts.len() >= 19 {
            &ts[11..19]
        } else {
            &ts
        };
        Ok(format!("[{}] {}", time_part, msg))
    })?;

    let mut result: Vec<String> = rows.collect::<rusqlite::Result<Vec<String>>>()?;
    result.reverse(); // 反轉為時間正序
    Ok(result)
}

// ═══════════════════════════════════════════
//  建表 SQL
// ═══════════════════════════════════════════
const INIT_SQL: &str = r#"
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
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL,
    run_number  INTEGER NOT NULL,
    status      TEXT NOT NULL,
    duration_ms INTEGER DEFAULT 0,
    error_msg   TEXT DEFAULT '',
    log_summary TEXT DEFAULT '',
    started_at  TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT DEFAULT 'info',
    source     TEXT DEFAULT 'system',
    job_id     TEXT,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scripts_name ON scripts(name);
CREATE INDEX IF NOT EXISTS idx_scripts_updated ON scripts(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_logs_time ON logs(created_at DESC);

INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
    ('device.default_serial', '"127.0.0.1:5555"', datetime('now')),
    ('device.mode', '"adb"', datetime('now')),
    ('device.emulator_type', '"auto"', datetime('now')),
    ('task.auto_restart', 'false', datetime('now')),
    ('task.default_interval', '3', datetime('now')),
    ('ui.theme', '"dark"', datetime('now'));
"#;
