// 全域共享狀態
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use std::collections::HashMap;

/// 裝置連線狀態
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceState {
    pub connected: bool,
    pub serial: String,
    pub mode: String,            // "adb" | "minicap" | "emulator"
    pub emulator_type: String,   // "auto" | "mumu" | "ldplayer" | "bluestacks" | "nox"
    pub resolution: (u32, u32),
}

impl Default for DeviceState {
    fn default() -> Self {
        Self {
            connected: false,
            serial: "127.0.0.1:5555".to_string(),
            mode: "adb".to_string(),
            emulator_type: "auto".to_string(),
            resolution: (0, 0),
        }
    }
}

/// 任務執行狀態
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskState {
    pub job_id: String,
    pub script_id: String,
    pub script_name: String,
    pub enabled: bool,
    pub completed: bool,
    pub run_count: u32,
    pub max_runs: u32,
    pub run_mode: String, // "loop" | "fixed"
}

/// Python 引擎狀態
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EngineState {
    pub running: bool,
    pub pid: Option<u32>,
}

impl Default for EngineState {
    fn default() -> Self {
        Self {
            running: false,
            pid: None,
        }
    }
}

/// 全域應用狀態（透過 Tauri State 管理）
pub struct AppState {
    pub device: Mutex<DeviceState>,
    pub engine: Mutex<EngineState>,
    pub tasks: Mutex<Vec<TaskState>>,
    pub logs: Mutex<Vec<String>>,
    pub config: Mutex<HashMap<String, serde_json::Value>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            device: Mutex::new(DeviceState::default()),
            engine: Mutex::new(EngineState::default()),
            tasks: Mutex::new(Vec::new()),
            logs: Mutex::new(Vec::new()),
            config: Mutex::new(HashMap::new()),
        }
    }
}
