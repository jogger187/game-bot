// 腳本管理命令 — CRUD 操作
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

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
}

/// 取得腳本儲存目錄
fn scripts_dir() -> PathBuf {
    let dir = PathBuf::from("scripts");
    if !dir.exists() {
        fs::create_dir_all(&dir).ok();
    }
    dir
}

/// 取得所有腳本列表
#[tauri::command]
pub async fn script_list() -> Result<Vec<Script>, String> {
    let dir = scripts_dir();

    // 也嘗試讀取舊版 scripts.json
    let legacy_path = PathBuf::from("scripts.json");
    let mut scripts: Vec<Script> = Vec::new();

    // 讀取新格式（每個腳本一個 JSON 檔）
    if dir.exists() {
        let entries = fs::read_dir(&dir).map_err(|e| e.to_string())?;
        for entry in entries {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.extension().map_or(false, |ext| ext == "json") {
                let content = fs::read_to_string(&path).map_err(|e| e.to_string())?;
                if let Ok(script) = serde_json::from_str::<Script>(&content) {
                    scripts.push(script);
                }
            }
        }
    }

    // 如果沒有新格式腳本，嘗試讀取舊格式
    if scripts.is_empty() && legacy_path.exists() {
        let content = fs::read_to_string(&legacy_path).map_err(|e| e.to_string())?;
        if let Ok(legacy_scripts) = serde_json::from_str::<Vec<Value>>(&content) {
            for val in legacy_scripts {
                if let Ok(script) = serde_json::from_value::<Script>(val) {
                    scripts.push(script);
                }
            }
        }
    }

    Ok(scripts)
}

/// 儲存單一腳本
#[tauri::command]
pub async fn script_save(script: Script) -> Result<Script, String> {
    let dir = scripts_dir();
    let filename = format!("{}.json", script.id);
    let path = dir.join(&filename);

    let mut script = script;
    script.updated_at = chrono::Utc::now().to_rfc3339();
    if script.created_at.is_empty() {
        script.created_at = script.updated_at.clone();
    }
    script.version += 1;

    let content = serde_json::to_string_pretty(&script).map_err(|e| e.to_string())?;
    fs::write(&path, content).map_err(|e| e.to_string())?;

    Ok(script)
}

/// 刪除腳本
#[tauri::command]
pub async fn script_delete(script_id: String) -> Result<(), String> {
    let dir = scripts_dir();
    let filename = format!("{}.json", script_id);
    let path = dir.join(&filename);

    if path.exists() {
        fs::remove_file(&path).map_err(|e| e.to_string())?;
    }

    Ok(())
}

/// 建立新腳本（含預設節點）
#[tauri::command]
pub async fn script_create(name: String) -> Result<Script, String> {
    let id = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now().to_rfc3339();

    let script = Script {
        id: id.clone(),
        name,
        version: 1,
        created_at: now.clone(),
        updated_at: now,
        nodes: vec![
            ScriptNode {
                id: "start_1".to_string(),
                node_type: "start".to_string(),
                position: NodePosition { x: 100.0, y: 200.0 },
                data: serde_json::json!({}),
            },
            ScriptNode {
                id: "end_1".to_string(),
                node_type: "end".to_string(),
                position: NodePosition { x: 600.0, y: 200.0 },
                data: serde_json::json!({}),
            },
        ],
        edges: vec![],
        settings: ScriptSettings::default(),
        rules: vec![],
    };

    // 儲存到磁碟
    let dir = scripts_dir();
    let filename = format!("{}.json", id);
    let path = dir.join(&filename);
    let content = serde_json::to_string_pretty(&script).map_err(|e| e.to_string())?;
    fs::write(&path, content).map_err(|e| e.to_string())?;

    Ok(script)
}
