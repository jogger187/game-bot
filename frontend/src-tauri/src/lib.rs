// Game Bot — Tauri 應用模組註冊
mod commands;
mod database;
mod python_bridge;
mod state;

use database::DbState;
use state::AppState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // 初始化資料庫
    let db_state = DbState::new().expect("資料庫初始化失敗");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(db_state)
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            // 裝置管理
            commands::device::device_connect,
            commands::device::device_disconnect,
            commands::device::device_status,
            // 截圖
            commands::screenshot::screenshot_capture,
            commands::screenshot::screenshot_highres,
            // 腳本管理
            commands::script::script_list,
            commands::script::script_save,
            commands::script::script_delete,
            commands::script::script_create,
            // 任務控制
            commands::task::task_start,
            commands::task::task_toggle,
            commands::task::task_stop,
            commands::task::task_list,
            commands::task::get_logs,
            // 資源管理
            commands::asset::asset_list,
            commands::asset::asset_save_crop,
            commands::asset::asset_delete,
            commands::asset::asset_read,
        ])
        .run(tauri::generate_context!())
        .expect("啟動 Game Bot 應用失敗");
}
