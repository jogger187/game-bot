# 🎮 Game Bot — 遊戲自動化控制台

可自定義腳本的遊戲自動化外掛，基於 **Tauri 2.0 + React + MUI + Python** 的桌面應用。

## 📁 專案結構

```
game-bot/
├── frontend/                   # Tauri 桌面應用
│   ├── src/                    # React 前端 (TypeScript + MUI)
│   │   ├── components/         # UI 組件
│   │   │   └── layout/         # 佈局組件 (Sidebar)
│   │   ├── pages/              # 頁面
│   │   │   ├── Dashboard.tsx   # 儀表板 (裝置狀態、日誌)
│   │   │   ├── ScriptEditor.tsx# 可視化腳本編輯器 (React Flow)
│   │   │   ├── AssetManager.tsx# 模板圖片資源管理
│   │   │   ├── TaskRunner.tsx  # 任務執行控制
│   │   │   └── Settings.tsx    # 系統設定
│   │   ├── stores/             # Zustand 狀態管理
│   │   ├── types/              # TypeScript 型別定義
│   │   ├── utils/              # Tauri IPC 封裝
│   │   ├── App.tsx             # 主應用入口
│   │   └── theme.ts            # MUI 暗色主題
│   ├── src-tauri/              # Rust 後端
│   │   ├── src/
│   │   │   ├── commands/       # Tauri 命令 (device, screenshot, script, task, asset)
│   │   │   ├── state.rs        # 全域共享狀態
│   │   │   ├── python_bridge.rs# Python 子進程 JSON-RPC 橋接
│   │   │   ├── lib.rs          # 模組註冊
│   │   │   └── main.rs         # 程式入口
│   │   ├── Cargo.toml
│   │   └── tauri.conf.json
│   └── package.json
│
├── python-core/                # Python 自動化核心引擎
│   ├── engine.py               # JSON-RPC IPC 入口
│   ├── core/                   # 核心功能模組
│   │   ├── adb_controller.py   # ADB 裝置控制
│   │   ├── screen_matcher.py   # 模板匹配
│   │   ├── input_simulator.py  # 輸入模擬
│   │   ├── ocr_reader.py       # OCR 文字辨識
│   │   ├── scene_detector.py   # 場景偵測
│   │   └── anti_detect.py      # 防偵測
│   └── tasks/                  # 任務調度系統
│
├── scripts/                    # 腳本存儲 (JSON)
├── assets/                     # 模板圖片存儲
└── config.yaml                 # 全域配置
```

## 🏗️ 架構設計

```
┌─────────────────────────────────────────────┐
│            Tauri Desktop App                │
│  ┌────────────┐     ┌────────────────────┐  │
│  │   React    │     │     Rust Backend   │  │
│  │  Frontend  │◄───►│   (Tauri Commands) │  │
│  │ MUI + Flow │ IPC │   State / FS / IO  │  │
│  └────────────┘     └─────────┬──────────┘  │
│                               │              │
│                     JSON-RPC stdin/stdout    │
│                               │              │
│                    ┌──────────▼──────────┐   │
│                    │   Python Core       │   │
│                    │  engine.py (子進程)  │   │
│                    │  ADB / OCR / Match  │   │
│                    └─────────────────────┘   │
└─────────────────────────────────────────────┘
```

## 🚀 開發啟動

```bash
# 1. 安裝前端依賴
cd frontend && npm install

# 2. 啟動 Tauri 開發模式（同時啟動 Vite + Rust）
npm run tauri:dev

# 3. 打包發佈
npm run tauri:build
```

## 🧩 核心功能

| 功能 | 說明 |
|------|------|
| **可視化腳本編輯器** | 基於 React Flow 的拖拽式節點圖，支援條件/動作/邏輯節點 |
| **模板匹配** | OpenCV 模板比對 + OCR 文字辨識 |
| **任務排程** | 循環/固定次數執行，暫停/繼續/停止控制 |
| **資源管理** | 截圖裁切、模板圖片上傳管理 |
| **防偵測** | 隨機延遲、座標偏移、多種輸入模式 |
| **多模擬器支援** | MuMu / 雷電 / BlueStacks / 夜神 |
