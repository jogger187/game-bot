#!/bin/bash
# 🛑 Game Bot 停止腳本
# 清理所有相關進程

echo "🛑 停止 Game Bot 服務..."

# 停止 Python API Server
echo "  🐍 停止 API Server..."
lsof -ti:8765 | xargs kill -9 2>/dev/null
pkill -f "python.*api_server" 2>/dev/null

# 停止前端 Vite
echo "  ⚛️  停止前端..."
pkill -f "vite.*5173" 2>/dev/null
pkill -f "npm.*dev.*frontend" 2>/dev/null

# 清理資料庫殭屍任務
if [ -f "data/gamebot.db" ]; then
    echo "  🗑️  清理資料庫殭屍任務..."
    sqlite3 data/gamebot.db "UPDATE tasks SET enabled=0, completed=1, status='stopped' WHERE enabled=1;" 2>/dev/null
fi

sleep 1
echo "✅ 所有服務已停止"
