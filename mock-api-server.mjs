/**
 * 輕量級 Mock API 伺服器 — 用於前端 E2E 測試
 * 模擬 Python API Server 的任務、腳本相關端點
 */
import http from 'node:http';
import crypto from 'node:crypto';

// ── 模擬資料 ──
const scripts = [
  {
    id: 'script-001',
    name: '自動日常任務',
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    nodes: [
      { id: 'start_1', type: 'start', position: { x: 100, y: 200 }, data: {} },
      { id: 'end_1', type: 'end', position: { x: 600, y: 200 }, data: {} },
    ],
    edges: [],
    settings: { loop_enabled: true, interval: 3, max_runs: 0 },
    rules: [],
  },
  {
    id: 'script-002',
    name: '自動副本掃蕩',
    version: 2,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    nodes: [
      { id: 'start_1', type: 'start', position: { x: 100, y: 200 }, data: {} },
      { id: 'end_1', type: 'end', position: { x: 600, y: 200 }, data: {} },
    ],
    edges: [],
    settings: { loop_enabled: true, interval: 5, max_runs: 10 },
    rules: [],
  },
  {
    id: 'script-003',
    name: '競技場自動戰鬥',
    version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    nodes: [],
    edges: [],
    settings: { loop_enabled: false, interval: 3, max_runs: 5 },
    rules: [],
  },
];

// 活躍任務
const tasks = new Map();
const logs = [];

const addLog = (msg) => {
  const ts = new Date().toLocaleTimeString('zh-TW');
  logs.push(`[${ts}] ${msg}`);
  if (logs.length > 500) logs.shift();
  console.log(`[${ts}] ${msg}`);
};

// 模擬任務自動遞增 run_count
setInterval(() => {
  for (const [, task] of tasks) {
    if (task.enabled && !task.completed) {
      task.run_count += 1;
      if (task.max_runs > 0 && task.run_count >= task.max_runs) {
        task.completed = true;
        task.enabled = false;
        addLog(`✅ 任務完成: ${task.script_name} (已執行 ${task.run_count} 次)`);
      }
    }
  }
}, 3000);

// ── HTTP 處理 ──
const parseBody = (req) =>
  new Promise((resolve) => {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => {
      try { resolve(JSON.parse(body)); }
      catch { resolve({}); }
    });
  });

const json = (res, data, status = 200) => {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  });
  res.end(JSON.stringify(data));
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost:8765');
  const path = url.pathname;
  const method = req.method;

  // CORS preflight
  if (method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    return res.end();
  }

  // 裝置狀態（模擬已連線）
  if (path === '/api/device/status' && method === 'GET') {
    return json(res, {
      connected: true,
      serial: 'emulator-5554',
      mode: 'adb',
      emulator_type: 'auto',
      resolution: [1080, 1920],
    });
  }

  // 腳本列表
  if (path === '/api/scripts' && method === 'GET') {
    return json(res, scripts);
  }

  // 資源列表
  if (path === '/api/assets' && method === 'GET') {
    return json(res, []);
  }

  // 任務列表
  if (path === '/api/tasks' && method === 'GET') {
    return json(res, [...tasks.values()]);
  }

  // 啟動任務
  if (path === '/api/tasks' && method === 'POST') {
    const data = await parseBody(req);
    const jobId = crypto.randomUUID().slice(0, 8);
    const task = {
      job_id: jobId,
      script_id: data.script_id,
      script_name: data.script_name || '未命名',
      enabled: true,
      completed: false,
      run_count: 0,
      max_runs: data.max_runs || 0,
      run_mode: data.run_mode || 'loop',
    };
    tasks.set(jobId, task);
    addLog(`🚀 任務已啟動: ${task.script_name} (job=${jobId})`);
    return json(res, task);
  }

  // 暫停/繼續任務
  const toggleMatch = path.match(/^\/api\/tasks\/([^/]+)\/toggle$/);
  if (toggleMatch && method === 'POST') {
    const jobId = toggleMatch[1];
    const task = tasks.get(jobId);
    if (!task) return json(res, { error: '任務不存在' }, 404);
    task.enabled = !task.enabled;
    addLog(task.enabled ? `▶️ 任務繼續: ${task.script_name}` : `⏸️ 任務暫停: ${task.script_name}`);
    return json(res, task);
  }

  // 停止任務
  const stopMatch = path.match(/^\/api\/tasks\/([^/]+)\/stop$/);
  if (stopMatch && method === 'POST') {
    const jobId = stopMatch[1];
    const task = tasks.get(jobId);
    if (!task) return json(res, { error: '任務不存在' }, 404);
    task.enabled = false;
    task.completed = true;
    addLog(`🛑 任務已停止: ${task.script_name}`);
    return json(res, { ok: true });
  }

  // 移除任務
  const deleteMatch = path.match(/^\/api\/tasks\/([^/]+)$/);
  if (deleteMatch && method === 'DELETE') {
    const jobId = deleteMatch[1];
    const task = tasks.get(jobId);
    if (task) addLog(`🗑️ 已移除任務: ${task.script_name}`);
    tasks.delete(jobId);
    return json(res, { ok: true });
  }

  // 日誌
  if (path === '/api/logs' && method === 'GET') {
    const limit = parseInt(url.searchParams.get('limit') || '100');
    return json(res, logs.slice(-limit));
  }

  // 404
  json(res, { error: `Not found: ${method} ${path}` }, 404);
});

server.listen(8765, () => {
  console.log('='.repeat(50));
  console.log('  Mock API Server for E2E Testing');
  console.log('  http://localhost:8765');
  console.log('='.repeat(50));
  addLog('🚀 Mock API Server 啟動完成');
});
