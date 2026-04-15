"""
SQLite 資料庫存取層 — 提供所有資料的持久化 CRUD 操作
Rust (Tauri) 和 Python 共用同一個 DB 檔案
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 資料庫檔案路徑
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "gamebot.db"
MIGRATIONS_DIR = DB_DIR / "migrations"


def _now_iso() -> str:
    """取得目前時間（ISO 8601 格式）"""
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    """取得資料庫連線（自動建立資料夾與初始化）"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """初始化資料庫（執行 migration SQL）"""
    if conn is None:
        conn = get_connection()

    migration_file = MIGRATIONS_DIR / "001_init.sql"
    if migration_file.exists():
        sql = migration_file.read_text("utf-8")
        conn.executescript(sql)
        print(f"✅ 資料庫初始化完成: {DB_PATH}")
    else:
        print(f"⚠️ 找不到 migration 檔案: {migration_file}")

    return conn


# ═══════════════════════════════════════════
#  腳本 CRUD
# ═══════════════════════════════════════════

def script_list(conn: sqlite3.Connection) -> list[dict]:
    """取得所有未刪除的腳本"""
    rows = conn.execute(
        "SELECT * FROM scripts WHERE is_deleted = 0 ORDER BY updated_at DESC"
    ).fetchall()
    return [_script_row_to_dict(r) for r in rows]


def script_get(conn: sqlite3.Connection, script_id: str) -> Optional[dict]:
    """依 ID 取得單一腳本"""
    row = conn.execute(
        "SELECT * FROM scripts WHERE id = ? AND is_deleted = 0", (script_id,)
    ).fetchone()
    return _script_row_to_dict(row) if row else None


def script_create(conn: sqlite3.Connection, name: str) -> dict:
    """建立新腳本（含預設 start/end 節點）"""
    now = _now_iso()
    script_id = str(uuid.uuid4())

    default_nodes = json.dumps([
        {"id": "start_1", "type": "start", "position": {"x": 100, "y": 200}, "data": {}},
        {"id": "end_1", "type": "end", "position": {"x": 600, "y": 200}, "data": {}},
    ])
    default_settings = json.dumps({"loop_enabled": True, "interval": 3, "max_runs": 0})

    conn.execute(
        """INSERT INTO scripts (id, name, version, nodes, edges, settings, rules, created_at, updated_at)
           VALUES (?, ?, 1, ?, '[]', ?, '[]', ?, ?)""",
        (script_id, name, default_nodes, default_settings, now, now),
    )
    conn.commit()

    return script_get(conn, script_id)


def script_save(conn: sqlite3.Connection, script: dict) -> dict:
    """更新腳本（自動遞增版本號）"""
    now = _now_iso()
    script_id = script["id"]

    conn.execute(
        """UPDATE scripts SET
            name = ?, version = version + 1,
            nodes = ?, edges = ?, settings = ?, rules = ?,
            tags = ?, description = ?, updated_at = ?
           WHERE id = ?""",
        (
            script.get("name", ""),
            json.dumps(script.get("nodes", [])),
            json.dumps(script.get("edges", [])),
            json.dumps(script.get("settings", {})),
            json.dumps(script.get("rules", [])),
            script.get("tags", ""),
            script.get("description", ""),
            now,
            script_id,
        ),
    )
    conn.commit()
    return script_get(conn, script_id)


def script_delete(conn: sqlite3.Connection, script_id: str) -> None:
    """軟刪除腳本"""
    conn.execute(
        "UPDATE scripts SET is_deleted = 1, updated_at = ? WHERE id = ?",
        (_now_iso(), script_id),
    )
    conn.commit()


def _script_row_to_dict(row: sqlite3.Row) -> dict:
    """將 DB Row 轉換為前端期望的 dict 格式"""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "version": row["version"],
        "nodes": json.loads(row["nodes"]),
        "edges": json.loads(row["edges"]),
        "settings": json.loads(row["settings"]),
        "rules": json.loads(row["rules"]),
        "tags": row["tags"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ═══════════════════════════════════════════
#  任務 CRUD
# ═══════════════════════════════════════════

def task_list(conn: sqlite3.Connection) -> list[dict]:
    """取得所有任務"""
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY created_at DESC"
    ).fetchall()
    return [_task_row_to_dict(r) for r in rows]


def task_create(
    conn: sqlite3.Connection,
    script_id: str,
    script_name: str,
    run_mode: str = "loop",
    max_runs: int = 0,
) -> dict:
    """建立新任務"""
    now = _now_iso()
    job_id = str(uuid.uuid4())[:8]

    conn.execute(
        """INSERT INTO tasks
           (job_id, script_id, script_name, run_mode, max_runs,
            run_count, enabled, completed, status, started_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 0, 1, 0, 'running', ?, ?, ?)""",
        (job_id, script_id, script_name, run_mode, max_runs, now, now, now),
    )
    conn.commit()
    return task_get(conn, job_id)


def task_get(conn: sqlite3.Connection, job_id: str) -> Optional[dict]:
    """依 job_id 取得任務"""
    row = conn.execute("SELECT * FROM tasks WHERE job_id = ?", (job_id,)).fetchone()
    return _task_row_to_dict(row) if row else None


def task_update_count(conn: sqlite3.Connection, job_id: str, run_count: int) -> None:
    """更新任務執行次數"""
    conn.execute(
        "UPDATE tasks SET run_count = ?, updated_at = ? WHERE job_id = ?",
        (run_count, _now_iso(), job_id),
    )
    conn.commit()


def task_toggle(conn: sqlite3.Connection, job_id: str) -> Optional[dict]:
    """暫停/繼續任務"""
    task = task_get(conn, job_id)
    if not task:
        return None

    new_enabled = 0 if task["enabled"] else 1
    new_status = "running" if new_enabled else "paused"

    conn.execute(
        "UPDATE tasks SET enabled = ?, status = ?, updated_at = ? WHERE job_id = ?",
        (new_enabled, new_status, _now_iso(), job_id),
    )
    conn.commit()
    return task_get(conn, job_id)


def task_stop(conn: sqlite3.Connection, job_id: str) -> None:
    """停止任務（標記為已完成）"""
    now = _now_iso()
    conn.execute(
        """UPDATE tasks SET enabled = 0, completed = 1, status = 'stopped',
           stopped_at = ?, updated_at = ? WHERE job_id = ?""",
        (now, now, job_id),
    )
    conn.commit()


def task_complete(conn: sqlite3.Connection, job_id: str) -> None:
    """任務自然完成"""
    now = _now_iso()
    conn.execute(
        """UPDATE tasks SET enabled = 0, completed = 1, status = 'completed',
           stopped_at = ?, updated_at = ? WHERE job_id = ?""",
        (now, now, job_id),
    )
    conn.commit()


def task_remove(conn: sqlite3.Connection, job_id: str) -> None:
    """從列表移除任務"""
    conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
    conn.commit()


def _task_row_to_dict(row: sqlite3.Row) -> dict:
    """將 DB Row 轉換為前端期望的 TaskInfo 格式"""
    return {
        "job_id": row["job_id"],
        "script_id": row["script_id"],
        "script_name": row["script_name"],
        "run_mode": row["run_mode"],
        "max_runs": row["max_runs"],
        "run_count": row["run_count"],
        "enabled": bool(row["enabled"]),
        "completed": bool(row["completed"]),
        "status": row["status"],
        "error_msg": row["error_msg"] or "",
        "started_at": row["started_at"] or "",
        "stopped_at": row["stopped_at"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ═══════════════════════════════════════════
#  任務執行歷史
# ═══════════════════════════════════════════

def task_run_add(
    conn: sqlite3.Connection,
    job_id: str,
    run_number: int,
    status: str = "success",
    duration_ms: int = 0,
    error_msg: str = "",
    log_summary: str = "",
) -> None:
    """記錄一次任務執行"""
    now = _now_iso()
    conn.execute(
        """INSERT INTO task_runs (job_id, run_number, status, duration_ms, error_msg, log_summary, started_at, finished_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, run_number, status, duration_ms, error_msg, log_summary, now, now),
    )
    conn.commit()


def task_run_list(conn: sqlite3.Connection, job_id: str, limit: int = 50) -> list[dict]:
    """取得任務的執行歷史"""
    rows = conn.execute(
        "SELECT * FROM task_runs WHERE job_id = ? ORDER BY run_number DESC LIMIT ?",
        (job_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════
#  日誌
# ═══════════════════════════════════════════

def log_add(
    conn: sqlite3.Connection,
    message: str,
    level: str = "info",
    source: str = "system",
    job_id: Optional[str] = None,
) -> None:
    """新增日誌"""
    conn.execute(
        "INSERT INTO logs (level, source, job_id, message, created_at) VALUES (?, ?, ?, ?, ?)",
        (level, source, job_id, message, _now_iso()),
    )
    conn.commit()


def log_list(conn: sqlite3.Connection, limit: int = 200, level: Optional[str] = None) -> list[str]:
    """取得日誌（返回格式化字串列表，相容前端）"""
    if level:
        rows = conn.execute(
            "SELECT * FROM logs WHERE level = ? ORDER BY id DESC LIMIT ?",
            (level, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    # 反轉為時間正序，格式化為前端期望的字串
    result = []
    for r in reversed(rows):
        ts = r["created_at"]
        # 嘗試提取時間部分
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            time_str = ts[:19] if ts else ""
        result.append(f"[{time_str}] {r['message']}")
    return result


def log_cleanup(conn: sqlite3.Connection, max_entries: int = 10000) -> int:
    """清理舊日誌，保留最新 N 筆"""
    count_row = conn.execute("SELECT COUNT(*) as cnt FROM logs").fetchone()
    total = count_row["cnt"] if count_row else 0

    if total <= max_entries:
        return 0

    delete_count = total - max_entries
    conn.execute(
        "DELETE FROM logs WHERE id IN (SELECT id FROM logs ORDER BY id ASC LIMIT ?)",
        (delete_count,),
    )
    conn.commit()
    return delete_count


# ═══════════════════════════════════════════
#  設定
# ═══════════════════════════════════════════

def setting_get(conn: sqlite3.Connection, key: str, default=None):
    """取得設定值（自動解析 JSON）"""
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]
    return default


def setting_set(conn: sqlite3.Connection, key: str, value) -> None:
    """設定值（自動序列化為 JSON）"""
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        (key, json.dumps(value), _now_iso()),
    )
    conn.commit()


def settings_all(conn: sqlite3.Connection) -> dict:
    """取得所有設定"""
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    result = {}
    for r in rows:
        try:
            result[r["key"]] = json.loads(r["value"])
        except (json.JSONDecodeError, TypeError):
            result[r["key"]] = r["value"]
    return result


# ═══════════════════════════════════════════
#  資源 metadata
# ═══════════════════════════════════════════

def asset_upsert(
    conn: sqlite3.Connection,
    name: str,
    file_path: str,
    file_size: int = 0,
    width: int = 0,
    height: int = 0,
) -> None:
    """新增或更新資源 metadata"""
    now = _now_iso()
    conn.execute(
        """INSERT INTO assets (name, file_path, file_size, width, height, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
             file_path = excluded.file_path,
             file_size = excluded.file_size,
             width = excluded.width,
             height = excluded.height,
             updated_at = excluded.updated_at""",
        (name, file_path, file_size, width, height, now, now),
    )
    conn.commit()


def asset_delete(conn: sqlite3.Connection, name: str) -> None:
    """刪除資源 metadata"""
    conn.execute("DELETE FROM assets WHERE name = ?", (name,))
    conn.commit()


def asset_list(conn: sqlite3.Connection) -> list[dict]:
    """取得所有資源"""
    rows = conn.execute("SELECT * FROM assets ORDER BY name").fetchall()
    return [{"name": r["name"], "size": r["file_size"]} for r in rows]
