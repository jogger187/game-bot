// 腳本管理命令 — 使用 SQLite 資料庫
use crate::database::{self, DbState};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::State;

/// 腳本節點
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScriptNode {
    pub id: String,
    #[serde(rename = "type")]
    pub node_type: String,
    pub position: NodePosition,
    pub data: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodePosition {
    pub x: f64,
    pub y: f64,
}

/// 腳本連線
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScriptEdge {
    pub id: String,
    pub source: String,
    pub target: String,
    #[serde(default)]
    pub label: Option<String>,
}

/// 腳本執行設定
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScriptSettings {
    #[serde(default = "default_true")]
    pub loop_enabled: bool,
    #[serde(default = "default_interval")]
    pub interval: f64,
    #[serde(default)]
    pub max_runs: u32,
}

fn default_true() -> bool { true }
fn default_interval() -> f64 { 3.0 }

impl Default for ScriptSettings {
    fn default() -> Self {
        Self {
            loop_enabled: true,
            interval: 3.0,
            max_runs: 0,
        }
    }
}

/// 完整腳本資料
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Script {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub version: u32,
    #[serde(default)]
    pub created_at: String,
    #[serde(default)]
    pub updated_at: String,
    #[serde(default)]
    pub nodes: Vec<ScriptNode>,
    #[serde(default)]
    pub edges: Vec<ScriptEdge>,
    #[serde(default)]
    pub settings: ScriptSettings,
    /// 向後相容：舊版的 rules 格式
    #[serde(default)]
    pub rules: Vec<Value>,
    #[serde(default)]
    pub tags: String,
}

/// 取得所有腳本列表
#[tauri::command]
pub async fn script_list(db: State<'_, DbState>) -> Result<Vec<Script>, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let scripts_json = database::script_list_db(&conn).map_err(|e| e.to_string())?;
    
    // 將 JSON Value 轉換為 Script 型別
    let scripts: Vec<Script> = scripts_json
        .into_iter()
        .filter_map(|val| serde_json::from_value(val).ok())
        .collect();
    
    Ok(scripts)
}

/// 建立新腳本（含預設節點）
#[tauri::command]
pub async fn script_create(name: String, db: State<'_, DbState>) -> Result<Script, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    let script_json = database::script_create_db(&conn, &name).map_err(|e| e.to_string())?;
    
    // 將 JSON Value 轉換為 Script 型別
    serde_json::from_value(script_json).map_err(|e| e.to_string())
}

/// 儲存單一腳本
#[tauri::command]
pub async fn script_save(script: Script, db: State<'_, DbState>) -> Result<Script, String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    
    // 將 Script 轉換為 JSON Value
    let script_json = serde_json::to_value(&script).map_err(|e| e.to_string())?;
    
    let saved_json = database::script_save_db(&conn, &script_json).map_err(|e| e.to_string())?;
    
    // 轉回 Script 型別
    serde_json::from_value(saved_json).map_err(|e| e.to_string())
}

/// 刪除腳本
#[tauri::command]
pub async fn script_delete(script_id: String, db: State<'_, DbState>) -> Result<(), String> {
    let conn = db.conn.lock().map_err(|e| e.to_string())?;
    database::script_delete_db(&conn, &script_id).map_err(|e| e.to_string())
}
