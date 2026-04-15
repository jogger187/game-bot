#!/bin/bash
set -e
API="http://localhost:8765/api"

echo "=== 1. 連線裝置 ==="
curl -s -X POST "$API/device/connect" -H "Content-Type: application/json" -d '{"serial":"emulator-5554"}' | jq '{connected, serial}'

echo "=== 2. 啟動任務 ==="
RESULT=$(curl -s -X POST "$API/tasks" -H "Content-Type: application/json" -d '{"script_id":"46d0ba99-9091-4b3d-95dc-059a0e9d7829","run_mode":"loop","max_runs":0}')
JOB_ID=$(echo "$RESULT" | jq -r '.job_id')
echo "  job_id=$JOB_ID"
echo "$RESULT" | jq '{enabled, completed}'
sleep 3

echo "=== 3. 暫停 ==="
curl -s -X POST "$API/tasks/$JOB_ID/toggle" | jq '{enabled, completed}'

echo "=== 4. 繼續 ==="
curl -s -X POST "$API/tasks/$JOB_ID/toggle" | jq '{enabled, completed}'
sleep 1

echo "=== 5. 停止(保留列表) ==="
curl -s -X POST "$API/tasks/$JOB_ID/stop" | jq .
sleep 1

echo "=== 5b. 列表(應有1筆completed) ==="
curl -s "$API/tasks" | jq '[.[] | {job_id, enabled, completed}]'

echo "=== 6. 移除(DELETE) ==="
curl -s -X DELETE "$API/tasks/$JOB_ID" | jq .

echo "=== 6b. 列表(應為空) ==="
COUNT=$(curl -s "$API/tasks" | jq 'length')
echo "  任務數量: $COUNT"

if [ "$COUNT" = "0" ]; then
  echo "=== ✅ 全部測試通過 ==="
else
  echo "=== ❌ 測試失敗: 列表應為空 ==="
fi
