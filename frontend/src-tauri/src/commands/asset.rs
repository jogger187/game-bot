// 模板圖片資源管理命令
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Serialize)]
pub struct AssetInfo {
    pub name: String,
    pub size: u64,
}

/// 取得 assets 目錄路徑
fn assets_dir() -> PathBuf {
    let dir = PathBuf::from("assets");
    if !dir.exists() {
        fs::create_dir_all(&dir).ok();
    }
    dir
}

/// 列出所有模板圖片
#[tauri::command]
pub async fn asset_list() -> Result<Vec<AssetInfo>, String> {
    let dir = assets_dir();
    let mut assets = Vec::new();

    let entries = fs::read_dir(&dir).map_err(|e| e.to_string())?;
    for entry in entries {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if path.extension().map_or(false, |ext| ext == "png" || ext == "jpg" || ext == "jpeg") {
            let meta = entry.metadata().map_err(|e| e.to_string())?;
            assets.push(AssetInfo {
                name: entry.file_name().to_string_lossy().to_string(),
                size: meta.len(),
            });
        }
    }

    Ok(assets)
}

#[derive(Debug, Deserialize)]
pub struct SaveCropParams {
    pub name: String,
    pub image_b64: String,
}

/// 儲存裁切的模板圖片
#[tauri::command]
pub async fn asset_save_crop(params: SaveCropParams) -> Result<AssetInfo, String> {
    let dir = assets_dir();

    // 確保檔名帶有 .png 副檔名
    let name = if params.name.ends_with(".png") {
        params.name.clone()
    } else {
        format!("{}.png", params.name)
    };

    // 解碼 base64（移除 data:image/png;base64, 前綴）
    let b64_data = params.image_b64
        .split(',')
        .last()
        .unwrap_or(&params.image_b64);

    let img_data = base64::Engine::decode(
        &base64::engine::general_purpose::STANDARD,
        b64_data,
    ).map_err(|e| format!("Base64 解碼失敗: {}", e))?;

    let path = dir.join(&name);
    fs::write(&path, &img_data).map_err(|e| format!("儲存檔案失敗: {}", e))?;

    Ok(AssetInfo {
        name,
        size: img_data.len() as u64,
    })
}

/// 刪除模板圖片
#[tauri::command]
pub async fn asset_delete(name: String) -> Result<(), String> {
    let dir = assets_dir();
    let path = dir.join(&name);

    if path.exists() {
        fs::remove_file(&path).map_err(|e| e.to_string())?;
    }

    Ok(())
}

/// 讀取模板圖片（回傳 base64）
#[tauri::command]
pub async fn asset_read(name: String) -> Result<String, String> {
    let dir = assets_dir();
    let path = dir.join(&name);

    if !path.exists() {
        return Err(format!("檔案不存在: {}", name));
    }

    let data = fs::read(&path).map_err(|e| e.to_string())?;
    let b64 = base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &data);

    Ok(format!("data:image/png;base64,{}", b64))
}
