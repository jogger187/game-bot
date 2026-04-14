# 📦 編譯與打包安裝檔

## 目錄
- [快速打包指令](#快速打包指令)
- [各平台詳細步驟](#各平台詳細步驟)
- [產出檔案說明](#產出檔案說明)
- [進階設定](#進階設定)

---

## 快速打包指令

### 一鍵打包（當前平台）

```bash
cd game-bot/frontend
npm run tauri:build
```

> 這會自動執行：`tsc → vite build → cargo build --release → 打包安裝檔`

### 打包輸出路徑

```
frontend/src-tauri/target/release/bundle/
├── macos/           # macOS .app 與 .dmg
├── msi/             # Windows .msi 安裝檔
├── nsis/            # Windows .exe 安裝檔
├── deb/             # Linux .deb 套件
└── appimage/        # Linux .AppImage
```

---

## 各平台詳細步驟

### macOS (.app / .dmg)

#### 前置需求
```bash
# 確認 Xcode Command Line Tools
xcode-select --install

# 確認 Rust 已安裝
rustc --version   # 需要 >= 1.75

# 確認 Node.js
node --version    # 需要 >= 18
```

#### 打包
```bash
cd game-bot/frontend

# 安裝依賴（首次）
npm install

# 打包
npm run tauri:build
```

#### 產出
```
src-tauri/target/release/bundle/macos/
├── Game Bot.app          # 可直接執行的 .app
└── Game Bot.dmg          # 拖拽安裝的 .dmg 映像檔
```

#### Apple Silicon (M1/M2/M3)
```bash
# 原生 ARM64 打包（預設）
npm run tauri:build

# 如需打包 Intel x86_64 版本
npm run tauri:build -- --target x86_64-apple-darwin

# 通用二進位（同時支援 ARM + Intel）
npm run tauri:build -- --target universal-apple-darwin
```

#### 程式碼簽署（發佈用）
```bash
# 設定 Apple Developer 簽署
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (TEAM_ID)"

# 帶簽署打包
npm run tauri:build
```

---

### Windows (.msi / .exe)

#### 前置需求
```powershell
# 安裝 Rust
winget install -e --id Rustlang.Rustup

# 安裝 Visual Studio Build Tools (C++ 工具鏈)
# 下載: https://visualstudio.microsoft.com/visual-cpp-build-tools/
# 安裝時勾選「使用 C++ 的桌面開發」

# 安裝 Node.js
winget install -e --id OpenJS.NodeJS.LTS

# 確認安裝
rustc --version
node --version
npm --version
```

#### 打包
```powershell
cd game-bot\frontend

# 安裝依賴
npm install

# 打包
npm run tauri:build
```

#### 產出
```
src-tauri\target\release\bundle\
├── msi\
│   └── Game Bot_0.1.0_x64.msi      # Windows Installer 安裝檔
└── nsis\
    └── Game Bot_0.1.0_x64-setup.exe # NSIS 安裝精靈
```

#### 自訂 NSIS 安裝精靈

在 `tauri.conf.json` 加入：
```json
{
  "bundle": {
    "targets": ["msi", "nsis"],
    "windows": {
      "nsis": {
        "displayLanguageSelector": true,
        "languages": ["English", "TraditionalChinese"]
      }
    }
  }
}
```

---

### Linux (.deb / .AppImage)

#### 前置需求 (Ubuntu/Debian)
```bash
# 系統依賴
sudo apt update && sudo apt install -y \
  libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev \
  librsvg2-dev patchelf

# Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

#### 打包
```bash
cd game-bot/frontend
npm install
npm run tauri:build
```

#### 產出
```
src-tauri/target/release/bundle/
├── deb/
│   └── game-bot_0.1.0_amd64.deb    # Debian/Ubuntu 套件
└── appimage/
    └── game-bot_0.1.0_amd64.AppImage  # 通用 Linux 可執行檔
```

#### 安裝 .deb
```bash
sudo dpkg -i game-bot_0.1.0_amd64.deb
```

---

## 產出檔案說明

| 平台 | 格式 | 檔案大小 (約) | 說明 |
|------|------|-------------|------|
| macOS | `.app` | 15-25 MB | 直接可執行 |
| macOS | `.dmg` | 15-25 MB | 拖拽安裝映像 |
| Windows | `.msi` | 8-15 MB | Windows Installer |
| Windows | `.exe` | 8-15 MB | NSIS 安裝精靈 |
| Linux | `.deb` | 8-12 MB | Debian 套件 |
| Linux | `.AppImage` | 50-80 MB | 獨立可執行檔 |

---

## 進階設定

### 修改應用程式資訊

編輯 `frontend/src-tauri/tauri.conf.json`：

```json
{
  "productName": "Game Bot",
  "version": "0.1.0",
  "identifier": "com.gamebot.app",
  "app": {
    "title": "Game Bot - 遊戲自動化控制台",
    "windows": [{
      "width": 1280,
      "height": 800,
      "minWidth": 1024,
      "minHeight": 600
    }]
  }
}
```

### 修改應用程式圖示

```bash
cd frontend/src-tauri

# 準備一張 1024x1024 PNG 圖片，命名為 app-icon.png
# 使用 Tauri 工具自動生成各尺寸圖示：
npx tauri icon app-icon.png
```

### 設定自動更新

在 `tauri.conf.json` 加入：
```json
{
  "plugins": {
    "updater": {
      "endpoints": ["https://your-server.com/update/{{target}}/{{arch}}/{{current_version}}"],
      "pubkey": "your-public-key"
    }
  }
}
```

### Debug 模式打包

```bash
# 帶 DevTools 的打包（用於測試）
npm run tauri:build -- --debug
```

### CI/CD 自動建置

可在 GitHub Actions 中使用：

```yaml
# .github/workflows/build.yml
name: Build
on:
  push:
    tags: ['v*']

jobs:
  build:
    strategy:
      matrix:
        platform: [macos-latest, ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.platform }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - uses: dtolnay/rust-toolchain@stable
      - run: cd frontend && npm install
      - run: cd frontend && npm run tauri:build
      - uses: actions/upload-artifact@v4
        with:
          name: bundle-${{ matrix.platform }}
          path: frontend/src-tauri/target/release/bundle/**/*
```

---

## 指令速查表

| 指令 | 說明 |
|------|------|
| `cd frontend && npm run dev` | 啟動前端 Vite 開發伺服器 |
| `cd frontend && npm run tauri:dev` | 啟動 Tauri 桌面應用開發模式 |
| `cd frontend && npm run tauri:build` | **打包安裝檔** |
| `cd frontend && npm run tauri:build -- --debug` | Debug 模式打包 |
| `cd frontend && npm run tauri:build -- --target universal-apple-darwin` | macOS 通用打包 |
| `cd frontend && npx tauri icon icon.png` | 自動生成應用圖示 |
| `source .venv/bin/activate && python python-core/api_server.py` | 啟動 Python API |
