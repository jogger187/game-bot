// 截圖命令
use crate::state::AppState;
use serde::Serialize;
use tauri::State;

#[derive(Debug, Serialize)]
pub struct ScreenshotResult {
    pub image_b64: String,
    pub width: u32,
    pub height: u32,
    pub timestamp: f64,
}

/// 擷取當前畫面截圖（回傳 base64）
#[tauri::command]
pub async fn screenshot_capture(state: State<'_, AppState>) -> Result<ScreenshotResult, String> {
    let device = state.device.lock().map_err(|e| e.to_string())?;
    if !device.connected {
        return Err("裝置尚未連線".to_string());
    }

    // TODO: 透過 PythonBridge 呼叫截圖
    // 目前回傳空白圖片作為佔位符
    Ok(ScreenshotResult {
        image_b64: String::new(),
        width: device.resolution.0,
        height: device.resolution.1,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64(),
    })
}

/// 擷取高畫質截圖（供裁切模板使用）
#[tauri::command]
pub async fn screenshot_highres(state: State<'_, AppState>) -> Result<ScreenshotResult, String> {
    let device = state.device.lock().map_err(|e| e.to_string())?;
    if !device.connected {
        return Err("裝置尚未連線".to_string());
    }

    // TODO: 透過 PythonBridge 呼叫高解析截圖
    Ok(ScreenshotResult {
        image_b64: String::new(),
        width: device.resolution.0,
        height: device.resolution.1,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64(),
    })
}
