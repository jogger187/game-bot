// 裝置管理命令
use crate::state::AppState;
use serde::{Deserialize, Serialize};
use tauri::State;

#[derive(Debug, Serialize, Deserialize)]
pub struct DeviceInfo {
    pub connected: bool,
    pub serial: String,
    pub mode: String,
    pub emulator_type: String,
    pub resolution: (u32, u32),
}

#[derive(Debug, Deserialize)]
pub struct ConnectParams {
    pub serial: Option<String>,
    pub mode: Option<String>,
    pub emulator_type: Option<String>,
}

/// 連接裝置
#[tauri::command]
pub async fn device_connect(
    state: State<'_, AppState>,
    params: ConnectParams,
) -> Result<DeviceInfo, String> {
    let mut device = state.device.lock().map_err(|e| e.to_string())?;

    // 更新設定
    if let Some(serial) = params.serial {
        device.serial = serial;
    }
    if let Some(mode) = params.mode {
        device.mode = mode;
    }
    if let Some(emu_type) = params.emulator_type {
        device.emulator_type = emu_type;
    }

    // TODO: 實際呼叫 Python 引擎連接裝置
    device.connected = true;
    device.resolution = (1920, 1080);

    let mut logs = state.logs.lock().map_err(|e| e.to_string())?;
    logs.push(format!("✅ 已連接裝置: {}", device.serial));

    Ok(DeviceInfo {
        connected: device.connected,
        serial: device.serial.clone(),
        mode: device.mode.clone(),
        emulator_type: device.emulator_type.clone(),
        resolution: device.resolution,
    })
}

/// 斷開裝置連線
#[tauri::command]
pub async fn device_disconnect(state: State<'_, AppState>) -> Result<(), String> {
    let mut device = state.device.lock().map_err(|e| e.to_string())?;
    device.connected = false;
    device.resolution = (0, 0);

    let mut logs = state.logs.lock().map_err(|e| e.to_string())?;
    logs.push("🔌 已斷開裝置連線".to_string());

    Ok(())
}

/// 取得裝置狀態
#[tauri::command]
pub async fn device_status(state: State<'_, AppState>) -> Result<DeviceInfo, String> {
    let device = state.device.lock().map_err(|e| e.to_string())?;
    Ok(DeviceInfo {
        connected: device.connected,
        serial: device.serial.clone(),
        mode: device.mode.clone(),
        emulator_type: device.emulator_type.clone(),
        resolution: device.resolution,
    })
}
