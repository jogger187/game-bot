// 任務控制命令
use crate::state::{AppState, TaskState};
use serde::Deserialize;
use tauri::State;

#[derive(Debug, Deserialize)]
pub struct StartTaskParams {
    pub script_id: String,
    pub script_name: String,
    pub run_mode: String,  // "loop" | "fixed"
    pub max_runs: u32,
}

/// 啟動任務
#[tauri::command]
pub async fn task_start(
    state: State<'_, AppState>,
    params: StartTaskParams,
) -> Result<TaskState, String> {
    let job_id = uuid::Uuid::new_v4().to_string();

    let task = TaskState {
        job_id: job_id.clone(),
        script_id: params.script_id,
        script_name: params.script_name.clone(),
        enabled: true,
        completed: false,
        run_count: 0,
        max_runs: if params.run_mode == "fixed" { params.max_runs } else { 0 },
        run_mode: params.run_mode,
    };

    let mut tasks = state.tasks.lock().map_err(|e| e.to_string())?;
    tasks.push(task.clone());

    let mut logs = state.logs.lock().map_err(|e| e.to_string())?;
    logs.push(format!("🚀 已啟動任務: {}", params.script_name));

    // TODO: 透過 PythonBridge 實際啟動腳本執行

    Ok(task)
}

/// 暫停/繼續任務
#[tauri::command]
pub async fn task_toggle(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<TaskState, String> {
    let mut tasks = state.tasks.lock().map_err(|e| e.to_string())?;

    let task = tasks
        .iter_mut()
        .find(|t| t.job_id == job_id)
        .ok_or("找不到指定的任務")?;

    task.enabled = !task.enabled;
    let status = if task.enabled { "▶️ 已繼續" } else { "⏸️ 已暫停" };

    let task_clone = task.clone();

    drop(tasks);
    let mut logs = state.logs.lock().map_err(|e| e.to_string())?;
    logs.push(format!("{} 任務: {}", status, task_clone.script_name));

    Ok(task_clone)
}

/// 停止並移除任務
#[tauri::command]
pub async fn task_stop(
    state: State<'_, AppState>,
    job_id: String,
) -> Result<(), String> {
    let mut tasks = state.tasks.lock().map_err(|e| e.to_string())?;

    let name = tasks
        .iter()
        .find(|t| t.job_id == job_id)
        .map(|t| t.script_name.clone());

    tasks.retain(|t| t.job_id != job_id);

    if let Some(name) = name {
        let mut logs = state.logs.lock().map_err(|e| e.to_string())?;
        logs.push(format!("🛑 已停止任務: {}", name));
    }

    // TODO: 透過 PythonBridge 實際停止腳本

    Ok(())
}

/// 取得所有任務狀態
#[tauri::command]
pub async fn task_list(state: State<'_, AppState>) -> Result<Vec<TaskState>, String> {
    let tasks = state.tasks.lock().map_err(|e| e.to_string())?;
    Ok(tasks.clone())
}

/// 取得日誌
#[tauri::command]
pub async fn get_logs(
    state: State<'_, AppState>,
    limit: Option<usize>,
) -> Result<Vec<String>, String> {
    let logs = state.logs.lock().map_err(|e| e.to_string())?;
    let limit = limit.unwrap_or(100);
    let start = if logs.len() > limit { logs.len() - limit } else { 0 };
    Ok(logs[start..].to_vec())
}
