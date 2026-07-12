# 即時畫面串流與錄製
- [x] 實作 scrcpy 即時畫面串流 (Backend -> Frontend，透過 WebSocket JPEG Binary)
- [x] 前端實作擷取畫面點擊/滑動座標並透過 WebSocket 傳送 (LiveRecorder.tsx)
- [x] 後端實作接收座標，透過 scrcpy 注入極低延遲點擊/滑動事件
- [x] 後端實作將操作記錄與時間戳記保存成錄製記錄 (recordings 表)
- [ ] 錄製結果轉換為 nodes/edges 格式 (可在方塊編輯器微調)

# 資料庫安全防護架構 (商業級防護)
- [ ] 導入 `pysqlcipher3` (或 `sqlcipher3`) 以 AES-256 加密 SQLite 敏感資料
- [ ] 整合 Python `keyring` 套件，將隨機金鑰託管給系統安全區 (macOS Keychain)
- [ ] 實作分拆式資料庫架構：
  - `cache.db` (明文)：儲存 UI 偏好設定、非敏感腳本資料
  - `vault.db` (加密)：儲存授權金鑰 (License)、密碼等敏感資料
