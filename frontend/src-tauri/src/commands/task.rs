// 任務控制命令 — 使用 SQLite 資料庫
use crate::database::{self, DbState};
use serde::{Deserialize, Serialize};
use tauri::State;

#[derive(Debug, Deserialize)]
pub struct StartTaskParams {
    pub script_id: String,
    pub script_name: String,
    pub run_mode: String,  // "loop" | "fixed"
    pub max_runs: u32,
}

/// 任務執行狀態（與前端和 DB 一致）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskState {
    pub job_id: String,
    pub script_id: String,
    pub script_name: String,
    pub run_mode: String,
    pub max_runs: u32,
    pub run_count: u32,
    pub enabled: bool,
    pub completed: bool,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub error_msg: String,
}

/// 啟動任務
#[tauri::command]
pub async fn task_start(
    db: State<'_, DbState>,
    params: StartTaskParams,
) -> Result<TaskState, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    
    let task_json = database::task_create_db(
        &conn,
        &params.script_id,
        &params.script_name,
        &params.run_mode,
        params.max_runs,
    ).map_err(|e| e.to_string())?;
    
    // 記錄日誌
    let msg = format!("🚀 已啟動任務: {} ({})", params.script_name, params.run_mode);
    database::log_add_db(&conn, &msg, "info", "task").ok();
    
    // 轉換為 TaskState
    serde_json::from_value(task_json).map_err(|e| e.to_string())
}

/// 暫停/繼續任務
#[tauri::command]
pub async fn task_toggle(
    db: State<'_, DbState>,
    job_id: String,
) -> Result<TaskState, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    
    let task_json = database::task_toggle_db(&conn, &job_id).map_err(|e| e.to_string())?;
    let task: TaskState = serde_json::from_value(task_json).map_err(|e| e.to_string())?;
    
    // 記錄日誌
    let status = if task.enabled { "▶️ 已繼續" } else { "⏸️ 已暫停" };
    let msg = format!("{} 任務: {}", status, task.script_name);
    database::log_add_db(&conn, &msg, "info", "task").ok();
    
    Ok(task)
}

/// 停止並移除任務
#[tauri::command]
pub async fn task_stop(
    db: State<'_, DbState>,
    job_id: String,
) -> Result<(), String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    
    // 先取得任務名稱用於日誌
    let task_json = database::task_get_db(&conn, &job_id)
        .unwrap_or_else(|_| serde_json::json!({"script_name": "未知"}));
    let name = task_json["script_name"].as_str().unwrap_or("未知");
    
    // 停止任務
    database::task_stop_db(&conn, &job_id).map_err(|e| e.to_string())?;
    
    // 記錄日誌
    let msg = format!("🛑 已停止任務: {} (job={})", name, &job_id[..8.min(job_id.len())]);
    database::log_add_db(&conn, &msg, "info", "task").ok();
    
    Ok(())
}

/// 取得所有任務狀態
#[tauri::command]
pub async fn task_list(db: State<'_, DbState>) -> Result<Vec<TaskState>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let tasks_json = database::task_list_db(&conn).map_err(|e| e.to_string())?;
    
    // 將 JSON Value 轉換為 TaskState 型別
    let tasks: Vec<TaskState> = tasks_json
        .into_iter()
        .filter_map(|val| serde_json::from_value(val).ok())
        .collect();
    
    Ok(tasks)
}

/// 取得日誌
#[tauri::command]
pub async fn get_logs(
    db: State<'_, DbState>,
    limit: Option<usize>,
) -> Result<Vec<String>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let limit = limit.unwrap_or(100);
    
    database::log_list_db(&conn, limit).map_err(|e| e.to_string())
}
