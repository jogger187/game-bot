<!--
Sync Impact Report:
- Version change: Initial template -> 1.0.0
- List of modified principles:
  - PRINCIPLE_1: I. 三層架構邊界嚴格隔離 (Three-Tier Architecture Isolation)
  - PRINCIPLE_2: II. 雙軌 IPC 契約與協定對齊 (Dual-Track IPC & Protocol Alignment)
  - PRINCIPLE_3: III. 跨進程 SQLite WAL 數據持久化規範 (Cross-Process SQLite WAL Discipline)
  - PRINCIPLE_4: IV. 語意化 Emoji 日誌與錯誤處理邊界 (Structured Semantic Logging & Error Boundaries)
  - PRINCIPLE_5: V. 安全性優先與緊急中斷原則 (Safety-First & Emergency Stop Mechanism)
- Added sections:
  - Technical Stack & Quality Standards
  - Development Workflow & Testing Strategy
- Removed sections: None
- Follow-up TODOs: None
-->

# Game Bot Constitution

## Core Principles

### I. 三層架構邊界嚴格隔離 (Three-Tier Architecture Isolation)
專案嚴格區分為「渲染層 (React/Vite)」、「桌面主進程 (Tauri/Rust)」、「自動化運算核心 (Python)」三層。
- 渲染進程嚴禁直接進行 ADB 或系統底層呼叫，所有系統操作必須透過 IPC 請求主進程。
- 主進程負責桌面視窗生命週期、子進程管理與資料庫中繼，不承載重度電腦視覺與 OCR 運算。
- Python 核心負責 CV、OCR、ADB 通訊與自動化邏輯，輸出結果必須透過標準資料結構回傳。

### II. 雙軌 IPC 契約與協定對齊 (Dual-Track IPC & Protocol Alignment)
為兼顧桌面端正式運行與純 Web 開發模式，前端必須維持雙軌通訊支援：
- **Tauri 原生模式**：透過 `@tauri-apps/api/core` 的 `invoke` 呼叫 Rust 指令；Rust 透過 `stdin/stdout` 經由 JSON-RPC 2.0 協議與 Python 核心溝通。
- **Web 開發模式**：降級走 HTTP REST API (`localhost:8765/api`)。
- 所有 IPC 方法與資料結構在 TypeScript (`script.ts`)、Rust (`commands/*.rs`) 與 Python (`engine.py` / `api_server.py`) 之間必須保持欄位與型別絕對對齊。

### III. 跨進程 SQLite WAL 數據持久化規範 (Cross-Process SQLite WAL Discipline)
Rust 主進程與 Python 核心共用同一個實體資料庫檔案 (`data/gamebot.db`)：
- 資料庫連線初始化時，必須一律強制開啟 `PRAGMA journal_mode=WAL;` 與 `PRAGMA foreign_keys=ON;`，防止跨進程讀寫衝突與鎖死。
- 腳本節點 (`nodes`) 與連線 (`edges`) 以 JSON 格式持久化，結構變更時必須向後相容。

### IV. 語意化 Emoji 日誌與錯誤處理邊界 (Structured Semantic Logging & Error Boundaries)
- **錯誤邊界**：Rust 命令必須以 `Result<T, String>` 封裝，將內部異常透過 `.map_err` 轉換為友善錯誤訊息拋回前端；前端非同步操作一律以 `try-catch` 包覆，不可引發 UI 崩潰。
- **日誌慣例**：所有關鍵生命週期與動作操作，必須包含語意化 Emoji 前綴（例如：`🚀 已啟動任務`、`⏸️ 已暫停`、`🔌 已斷開`、`❌ 失敗`、`✅ 成功`），並同時寫入 DB `logs` 表與系統輸出。

### V. 安全性優先與緊急中斷原則 (Safety-First & Emergency Stop Mechanism)
- 遊戲自動化涉及模擬點擊與設備輸入，腳本執行器 (`script_runner.py`) 必須支援全域緊急中斷機制（如 ESC 熱鍵與全域中斷 Event）。
- 自動化點擊動作應具備防封號隨機微調偏移（Anti-detection jitter/random delay），避免機械化定點定時點擊。

## Technical Stack & Quality Standards

- **前端技術棧**：React 19 + TypeScript + Vite + MUI v9 + `@xyflow/react` + Zustand。
  - 樣式優先遵循 Material-UI 主題規範，圖形節點必須型別安全。
- **主進程技術棧**：Tauri v2 + Rust (2021 Edition) + `rusqlite` + `serde`。
- **運算核心技術棧**：Python >= 3.10 + `adbutils` + `opencv-python-headless` + `paddleocr` + `loguru`。
- **代碼品質約束**：
  - Python 代碼遵循 `ruff` 規範，單行上限 120 字元。
  - TypeScript 必須通過嚴格型別檢查 (`tsc -b`) 與 ESLint。

## Development Workflow & Testing Strategy

1. **契約優先**：新增或修改功能前，必須先在 `.specify/` 建立規格說明，並確認前後端資料結構契約。
2. **本機除錯**：支援獨立啟動前端除錯伺服器 (`npm run dev`) 與 Python API 伺服器 (`python-core/api_server.py`)，亦支援 `npm run tauri:dev` 完整桌面整合除錯。
3. **驗證要求**：牽涉 ADB 操作與圖像特徵比對的改動，需提供離線測試或單元測試保護。

## Governance

- 本 Constitution 為專案最高開發原則，所有 PR、規格設計與程式碼產出必須符合本規範。
- 若需調整核心原則（例如更換資料庫、重構 IPC 協議），需更新此憲章並提升版本號：
  - MAJOR：架構性重大變更或破壞性協議更動。
  - MINOR：新增核心原則或擴充技術標準。
  - PATCH：文字澄清與細微修訂。

**Version**: 1.0.0 | **Ratified**: 2026-10-28 | **Last Amended**: 2026-10-28
