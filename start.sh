#!/bin/bash
# 🎮 Game Bot 一鍵啟動（改進版）
# 同時啟動 Python API + 前端開發伺服器
# 修正：port 檢查、殭屍任務清理、TTY 阻塞問題

cd "$(dirname "$0")"

echo "🎮 Game Bot 啟動中..."
echo "========================"

# ═══════════════════════════════════════════
# 步驟 1：清理舊進程和殭屍任務
# ═══════════════════════════════════════════
echo "🧹 清理舊進程..."

# 停止舊的 API Server
if lsof -ti:8765 >/dev/null 2>&1; then
    echo "  ⚠️  Port 8765 被占用，正在清理..."
    lsof -ti:8765 | xargs kill -9 2>/dev/null
    sleep 1
fi

# 停止舊的前端
pkill -f "vite.*5173" 2>/dev/null
pkill -f "npm.*dev.*frontend" 2>/dev/null

# 清理資料庫中的殭屍任務
if [ -f "data/gamebot.db" ]; then
    echo "  🗑️  清理資料庫殭屍任務..."
    sqlite3 data/gamebot.db "UPDATE tasks SET enabled=0, completed=1, status='stopped' WHERE enabled=1;" 2>/dev/null
fi

sleep 1

# ═══════════════════════════════════════════
# 步驟 2：啟動 Python API Server
# ═══════════════════════════════════════════
echo "🐍 啟動 Python API (port 8765)..."

# 重定向輸出到日誌，避免 TTY 阻塞
nohup .venv/bin/python python-core/api_server.py > logs/api_server.log 2>&1 &
API_PID=$!

# 等待 API 就緒（最多 10 秒）
echo "  ⏳ 等待 API Server 啟動..."
for i in {1..20}; do
    if curl -s http://localhost:8765/api/scripts >/dev/null 2>&1; then
        echo "  ✅ API Server 已就緒"
        break
    fi
    sleep 0.5
done

# ═══════════════════════════════════════════
# 步驟 3：啟動前端 Vite
# ═══════════════════════════════════════════
echo "⚛️  啟動前端 (Vite)..."

# 使用 nohup 並重定向 stdin/stdout/stderr，避免 TTY 阻塞
cd frontend
nohup npm run dev </dev/null >../logs/vite.log 2>&1 &
FRONT_PID=$!
cd ..

# 等待前端就緒
echo "  ⏳ 等待前端啟動..."
sleep 3
for i in {1..15}; do
    if curl -s http://localhost:5173 >/dev/null 2>&1; then
        echo "  ✅ 前端已就緒"
        break
    fi
    sleep 0.5
done

# ═══════════════════════════════════════════
# 完成
# ═══════════════════════════════════════════
echo ""
echo "========================"
echo "✅ Game Bot 已啟動!"
echo ""
echo "   🌐 前端: http://localhost:5173"
echo "   🐍 API:  http://localhost:8765"
echo ""
echo "   📁 日誌:"
echo "      API:  logs/api_server.log"
echo "      前端: logs/vite.log"
echo ""
echo "   按 Ctrl+C 停止所有服務"
echo "========================"
echo ""

# 攔截 Ctrl+C，清理子進程
trap "echo ''; echo '🛑 停止服務...'; kill $API_PID $FRONT_PID 2>/dev/null; sleep 1; echo '✅ 已停止'; exit" SIGINT SIGTERM

# 等待任一進程結束
wait
