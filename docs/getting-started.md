# 🚀 快速啟動指南

## 環境需求

| 工具 | 版本 | 說明 |
|------|------|------|
| **Node.js** | >= 18 | 前端建置 |
| **Rust** | >= 1.75 | Tauri 後端編譯 |
| **Python** | >= 3.10 | 自動化核心引擎 |
| **ADB** | 最新版 | Android 裝置控制 |
| **Android 模擬器** | 任一 | BlueStacks / MuMu / 雷電 / 夜神 |

---

## 一、安裝系統依賴

### macOS

```bash
# Homebrew 安裝基礎工具
brew install node rust python@3.12 android-platform-tools

# 安裝 Tauri 系統依賴
xcode-select --install
```

### Windows

```powershell
# 安裝 Node.js (https://nodejs.org)
# 安裝 Rust (https://rustup.rs)
winget install -e --id Rustlang.Rustup

# 安裝 Python 3.12+
winget install -e --id Python.Python.3.12

# 安裝 ADB (Android SDK Platform Tools)
# 下載: https://developer.android.com/tools/releases/platform-tools
# 或透過 scoop:
scoop install adb
```

### Linux (Ubuntu/Debian)

```bash
# Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Python
sudo apt install python3.12 python3.12-venv

# Tauri 系統依賴
sudo apt install -y libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev

# ADB
sudo apt install android-tools-adb
```

---

## 二、複製專案

```bash
git clone git@github.com:jogger187/game-bot.git
cd game-bot
```

---

## 三、安裝依賴

### 前端 (Node.js + Tauri)

```bash
cd frontend
npm install
cd ..
```

### Python 核心引擎

```bash
# 建立虛擬環境
python3 -m venv .venv

# 啟用虛擬環境
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 安裝依賴
pip install -e .
pip install aiohttp aiohttp-cors  # API 伺服器額外依賴
```

---

## 四、啟動開發模式

### 方式一：瀏覽器開發模式（推薦日常開發）

開兩個終端：

**終端 1 — Python API 伺服器：**
```bash
cd game-bot
source .venv/bin/activate
python python-core/api_server.py
```
輸出：
```
🚀 Game Bot API Server 啟動中...
  http://localhost:8765
```

**終端 2 — 前端開發伺服器：**
```bash
cd game-bot/frontend
npm run dev
```
輸出：
```
  VITE v8.x  ready in xxx ms
  ➜  Local:   http://localhost:5174/
```

然後在瀏覽器打開 `http://localhost:5174`

### 方式二：Tauri 桌面應用開發模式

```bash
cd game-bot/frontend
npm run tauri:dev
```

> ⚠️ 首次執行需要編譯 Rust，約需 3-5 分鐘

---

## 五、連接模擬器

### 確認 ADB 可用

```bash
adb devices
```

### 各模擬器 ADB 連接方式

| 模擬器 | ADB 連線 |
|--------|---------|
| **BlueStacks** | 自動偵測 `emulator-5554` |
| **MuMu 12** | `adb connect 127.0.0.1:7555` |
| **雷電模擬器** | `adb connect 127.0.0.1:5555` |
| **夜神模擬器** | `adb connect 127.0.0.1:62001` |
| **USB 實機** | 開啟 USB 偵錯，自動偵測 |

### 在 App 中選擇裝置

1. 開啟 **儀表板** 頁面
2. 點擊「選擇裝置連線」
3. 從列表中選擇你的模擬器/手機
4. 確認連線成功（顯示解析度）

---

## 六、使用流程

```
1. 擷取模板 → 資源管理 → 擷取截圖 → 框選物件 → 儲存
2. 建立腳本 → 腳本編輯器 → 新增 → 從工具箱拖入模塊
3. 設定屬性 → 點擊節點 → 右側面板設定參數
4. 連接節點 → 拖動連接點建立執行流程
5. 儲存腳本 → 右上角儲存按鈕
6. 執行任務 → 任務控制 → 選擇腳本 → 開始執行
```

---

## 常見問題

### Q: ADB 找不到裝置？
```bash
adb kill-server
adb start-server
adb devices
```

### Q: Python API 啟動失敗？
```bash
# 確認虛擬環境
which python  # 應顯示 .venv/bin/python

# 重新安裝依賴
pip install -e . && pip install aiohttp aiohttp-cors
```

### Q: Tauri 編譯失敗？
```bash
# 更新 Rust
rustup update

# 清除快取重建
cd frontend/src-tauri
cargo clean
cd ..
npm run tauri:dev
```
