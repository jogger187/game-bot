# 🗄️ Game Bot 資料庫設計方案

## 問題分析：為什麼資料會不見？

### 現有存儲方式一覽

| 資料類型 | 現有存儲方式 | 持久化？ | 問題 |
|---------|------------|---------|------|
| **腳本 (Scripts)** | JSON 檔案 (`scripts/*.json`) | ✅ 有 | 路徑相對於 CWD，Tauri/Python 可能讀不同目錄 |
| **任務 (Tasks)** | Rust `Mutex<Vec>` / Python `dict` | ❌ **記憶體** | 重啟即消失 |
| **任務執行紀錄** | 不存在 | ❌ **完全沒有** | 無法回顧歷史 |
| **日誌 (Logs)** | `Mutex<Vec<String>>` / Python `list` | ❌ **記憶體** | 重啟即消失 |
| **設定 (Config)** | `Mutex<HashMap>` | ❌ **記憶體** | 重啟即消失 |
| **資源圖片 (Assets)** | 檔案 (`assets/*.png`) | ✅ 有 | 但 metadata 不追蹤 |
| **裝置狀態** | `Mutex<DeviceState>` | ❌ **記憶體** | 每次重啟要重新連線 |

**結論：除了腳本和資源圖片，其他資料全部只在記憶體中，重啟就消失。**

---

## 方案：使用 SQLite 資料庫

### 為什麼選 SQLite？

- ✅ **嵌入式**：不需要額外安裝資料庫伺服器
- ✅ **單一檔案**：整個 DB 就一個 `.db` 檔，容易備份和遷移
- ✅ **跨語言共用**：Rust（`rusqlite`）和 Python（`sqlite3` 內建）都能讀寫同一個檔案
- ✅ **桌面應用首選**：Tauri/Electron 類應用的標準做法
- ✅ **效能足夠**：對本專案的資料量綽綽有餘
- ✅ **系統已有**：你的機器上已安裝 `sqlite3`

### 資料庫檔案位置

```
# Tauri 模式：存在應用資料目錄
~/Library/Application Support/com.gamebot.app/gamebot.db

# 開發模式 / Python 模式：存在專案根目錄
./data/gamebot.db
```

---

## 資料表設計

### 1. `scripts` — 腳本主表

```sql
CREATE TABLE scripts (
    id          TEXT PRIMARY KEY,           -- UUID
    name        TEXT NOT NULL,              -- 腳本名稱
    description TEXT DEFAULT '',            -- 腳本描述
    version     INTEGER DEFAULT 1,          -- 版本號
    nodes       TEXT NOT NULL DEFAULT '[]', -- JSON: ScriptNode[]
    edges       TEXT NOT NULL DEFAULT '[]', -- JSON: ScriptEdge[]
    settings    TEXT NOT NULL DEFAULT '{}', -- JSON: ScriptSettings
    rules       TEXT NOT NULL DEFAULT '[]', -- JSON: 向後相容
    tags        TEXT DEFAULT '',            -- 標籤，逗號分隔
    is_deleted  INTEGER DEFAULT 0,          -- 軟刪除標記
    created_at  TEXT NOT NULL,              -- ISO 8601
    updated_at  TEXT NOT NULL               -- ISO 8601
);

CREATE INDEX idx_scripts_name ON scripts(name);
CREATE INDEX idx_scripts_updated ON scripts(updated_at DESC);
```

> **設計說明**：`nodes`、`edges`、`settings` 仍用 JSON 欄位存儲，保持前端資料格式一致。SQLite 的 JSON 函數支援查詢 JSON 內容。

---

### 2. `tasks` — 任務（持久化 + 可恢復）

```sql
CREATE TABLE tasks (
    job_id      TEXT PRIMARY KEY,           -- UUID (短 8 碼)
    script_id   TEXT NOT NULL,              -- 對應腳本 ID
    script_name TEXT NOT NULL,              -- 腳本名稱快照
    run_mode    TEXT NOT NULL DEFAULT 'loop', -- 'loop' | 'fixed'
    max_runs    INTEGER DEFAULT 0,          -- 固定模式的次數上限
    run_count   INTEGER DEFAULT 0,          -- 已執行次數
    enabled     INTEGER DEFAULT 1,          -- 是否啟用 (0/1)
    completed   INTEGER DEFAULT 0,          -- 是否完成 (0/1)
    status      TEXT DEFAULT 'pending',     -- 'pending' | 'running' | 'paused' | 'stopped' | 'completed' | 'error'
    error_msg   TEXT DEFAULT '',            -- 錯誤訊息
    started_at  TEXT,                       -- 實際開始時間
    stopped_at  TEXT,                       -- 停止時間
    created_at  TEXT NOT NULL,              -- 建立時間
    updated_at  TEXT NOT NULL,              -- 最後更新

    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE SET NULL
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);
```

---

### 3. `task_runs` — 任務執行歷史紀錄

```sql
CREATE TABLE task_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT NOT NULL,              -- 對應任務
    run_number  INTEGER NOT NULL,           -- 第幾次執行
    status      TEXT NOT NULL,              -- 'success' | 'error' | 'skipped'
    duration_ms INTEGER DEFAULT 0,          -- 本次執行耗時 (毫秒)
    error_msg   TEXT DEFAULT '',            -- 錯誤訊息
    log_summary TEXT DEFAULT '',            -- 簡要日誌
    started_at  TEXT NOT NULL,
    finished_at TEXT,

    FOREIGN KEY (job_id) REFERENCES tasks(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_task_runs_job ON task_runs(job_id);
CREATE INDEX idx_task_runs_time ON task_runs(started_at DESC);
```

---

### 4. `logs` — 系統日誌（持久化）

```sql
CREATE TABLE logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT DEFAULT 'info',         -- 'debug' | 'info' | 'warn' | 'error'
    source     TEXT DEFAULT 'system',       -- 'system' | 'task' | 'device' | 'script'
    job_id     TEXT,                        -- 關聯的任務 (可為 NULL)
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_logs_level ON logs(level);
CREATE INDEX idx_logs_source ON logs(source);
CREATE INDEX idx_logs_time ON logs(created_at DESC);
CREATE INDEX idx_logs_job ON logs(job_id);

-- 自動清理：保留最近 10,000 筆日誌
-- (透過應用層定時清理，或用 trigger)
```

---

### 5. `assets` — 模板圖片 metadata

```sql
CREATE TABLE assets (
    name        TEXT PRIMARY KEY,           -- 檔案名稱 (e.g. "skip.png")
    file_path   TEXT NOT NULL,              -- 實際檔案路徑
    file_size   INTEGER DEFAULT 0,          -- 檔案大小 (bytes)
    width       INTEGER DEFAULT 0,          -- 圖片寬度
    height      INTEGER DEFAULT 0,          -- 圖片高度
    tags        TEXT DEFAULT '',            -- 標籤
    description TEXT DEFAULT '',            -- 描述
    used_in     TEXT DEFAULT '[]',          -- JSON: 被哪些腳本使用
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

> **設計說明**：圖片檔案本身仍存在 `assets/` 資料夾，DB 只管 metadata。

---

### 6. `settings` — 全域設定（Key-Value）

```sql
CREATE TABLE settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,              -- JSON 值
    updated_at  TEXT NOT NULL
);

-- 預設設定
INSERT INTO settings (key, value, updated_at) VALUES
    ('device.default_serial', '"127.0.0.1:5555"', datetime('now')),
    ('device.mode', '"adb"', datetime('now')),
    ('device.emulator_type', '"auto"', datetime('now')),
    ('task.auto_restart', 'false', datetime('now')),
    ('task.default_interval', '3', datetime('now')),
    ('ui.theme', '"dark"', datetime('now')),
    ('log.max_entries', '10000', datetime('now')),
    ('log.auto_clean_days', '7', datetime('now'));
```

---

### 7. `schedules` — 排程（未來擴展用）

```sql
CREATE TABLE schedules (
    id          TEXT PRIMARY KEY,
    script_id   TEXT NOT NULL,
    name        TEXT NOT NULL,
    cron_expr   TEXT NOT NULL,              -- Cron 表達式 (e.g. "0 8 * * *")
    run_mode    TEXT DEFAULT 'loop',
    max_runs    INTEGER DEFAULT 0,
    enabled     INTEGER DEFAULT 1,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,

    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
);
```

---

## ER 關聯圖

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   scripts    │       │    tasks     │       │  task_runs   │
│──────────────│       │──────────────│       │──────────────│
│ id       PK  │◄──────│ script_id FK │       │ id       PK  │
│ name         │       │ job_id    PK │◄──────│ job_id   FK  │
│ nodes   JSON │       │ run_mode     │       │ run_number   │
│ edges   JSON │       │ status       │       │ status       │
│ settings JSON│       │ run_count    │       │ duration_ms  │
│ version      │       │ created_at   │       │ started_at   │
└──────────────┘       └──────────────┘       └──────────────┘
                              │
                              │ job_id
                              ▼
                       ┌──────────────┐
                       │    logs      │
                       │──────────────│
                       │ id       PK  │
                       │ level        │
                       │ source       │
                       │ message      │
                       │ job_id   FK  │
                       │ created_at   │
                       └──────────────┘

┌──────────────┐       ┌──────────────┐
│   assets     │       │  settings    │
│──────────────│       │──────────────│
│ name     PK  │       │ key      PK  │
│ file_path    │       │ value   JSON │
│ file_size    │       │ updated_at   │
│ width        │       └──────────────┘
│ height       │
│ created_at   │       ┌──────────────┐
└──────────────┘       │  schedules   │
                       │──────────────│
                       │ id       PK  │
                       │ script_id FK │
                       │ cron_expr    │
                       │ enabled      │
                       └──────────────┘
```

---

## 技術實作路線

### Rust 端 (Tauri) — 推薦使用 `rusqlite`

```toml
# Cargo.toml 新增依賴
[dependencies]
rusqlite = { version = "0.31", features = ["bundled"] }
```

```rust
// 範例：初始化 DB
use rusqlite::Connection;

pub fn init_db(db_path: &str) -> rusqlite::Result<Connection> {
    let conn = Connection::open(db_path)?;
    conn.execute_batch(include_str!("../migrations/001_init.sql"))?;
    Ok(conn)
}
```

### Python 端 — 使用內建 `sqlite3`

```python
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "gamebot.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 允許並發讀取
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
```

### 共用同一個 DB 檔案的注意事項

| 場景 | 說明 |
|------|------|
| Tauri + Python 同時運行 | 使用 **WAL 模式** 允許並發讀取，寫入仍為序列化 |
| 純 Python 模式 (瀏覽器開發) | 直接讀寫，無衝突 |
| 純 Tauri 模式 | 直接讀寫，無衝突 |

---

## 遷移策略 (Migration)

### 從現有 JSON 檔案遷移

```sql
-- migrations/001_init.sql
-- 建立所有資料表（如上方的 CREATE TABLE 語句）

-- migrations/002_migrate_json_scripts.py
-- Python 腳本：讀取 scripts/*.json → 寫入 scripts 表
```

```python
# migrate_json_scripts.py
import json, sqlite3
from pathlib import Path

def migrate():
    db = sqlite3.connect("data/gamebot.db")
    scripts_dir = Path("scripts")
    
    for f in scripts_dir.glob("*.json"):
        script = json.loads(f.read_text())
        db.execute("""
            INSERT OR REPLACE INTO scripts 
            (id, name, version, nodes, edges, settings, rules, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            script["id"], script["name"], script.get("version", 1),
            json.dumps(script.get("nodes", [])),
            json.dumps(script.get("edges", [])),
            json.dumps(script.get("settings", {})),
            json.dumps(script.get("rules", [])),
            script.get("created_at", ""), script.get("updated_at", ""),
        ))
    
    db.commit()
    print(f"已遷移 {len(list(scripts_dir.glob('*.json')))} 個腳本")
```

---

## 建議實作優先順序

| 優先級 | 項目 | 影響 |
|--------|------|------|
| 🔴 P0 | `scripts` 表 + 遷移工具 | 解決腳本消失問題 |
| 🔴 P0 | `tasks` 表 | 任務可恢復、不再消失 |
| 🟡 P1 | `logs` 表 | 可追蹤歷史操作 |
| 🟡 P1 | `settings` 表 | 設定持久化 |
| 🟢 P2 | `task_runs` 歷史 | 執行統計分析 |
| 🟢 P2 | `assets` metadata | 資源管理增強 |
| ⚪ P3 | `schedules` 排程 | 未來功能 |

---

## 完整初始化 SQL

```sql
-- data/migrations/001_init.sql

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

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
    updated_at  TEXT NOT NULL,
    FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE SET NULL
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
    finished_at TEXT,
    FOREIGN KEY (job_id) REFERENCES tasks(job_id) ON DELETE CASCADE
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

-- 索引
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

-- 預設設定
INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES
    ('device.default_serial', '"127.0.0.1:5555"', datetime('now')),
    ('device.mode', '"adb"', datetime('now')),
    ('device.emulator_type', '"auto"', datetime('now')),
    ('task.auto_restart', 'false', datetime('now')),
    ('task.default_interval', '3', datetime('now')),
    ('ui.theme', '"dark"', datetime('now')),
    ('log.max_entries', '10000', datetime('now')),
    ('log.auto_clean_days', '7', datetime('now'));
```
