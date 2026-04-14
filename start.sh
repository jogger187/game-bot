#!/bin/bash
# 🎮 Game Bot 一鍵啟動
# 同時啟動 Python API + 前端開發伺服器

cd "$(dirname "$0")"

echo "🎮 Game Bot 啟動中..."
echo "========================"

# 啟動 Python API 伺服器（背景）
echo "🐍 啟動 Python API (port 8765)..."
.venv/bin/python python-core/api_server.py &
API_PID=$!

# 等 API 就緒
sleep 1

# 啟動前端
echo "⚛️  啟動前端 (Vite)..."
cd frontend && npm run dev &
FRONT_PID=$!

echo ""
echo "========================"
echo "✅ 已啟動!"
echo "   🌐 前端: http://localhost:5174"
echo "   🐍 API:  http://localhost:8765"
echo ""
echo "   按 Ctrl+C 停止所有服務"
echo "========================"

# 攔截 Ctrl+C，清理子進程
trap "echo '🛑 停止服務...'; kill $API_PID $FRONT_PID 2>/dev/null; exit" SIGINT SIGTERM

# 等待任一進程結束
wait
