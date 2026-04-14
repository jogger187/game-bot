// Tauri IPC 呼叫封裝 — 含瀏覽器開發 Mock 模式
import type { DeviceInfo, Script, AssetInfo, TaskInfo } from '../types/script';

// 偵測是否在 Tauri 環境中執行
const isTauri = () => !!(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;

// 動態載入 Tauri invoke（僅在 Tauri 環境）
const tauriInvoke = async <T>(cmd: string, args?: Record<string, unknown>): Promise<T> => {
  if (isTauri()) {
    const { invoke } = await import('@tauri-apps/api/core');
    return invoke<T>(cmd, args);
  }
  throw new Error(`[Mock] Tauri 未就緒，命令: ${cmd}`);
};

// ═══════════════════════════════════════════
//  Mock 資料（瀏覽器開發模式使用）
// ═══════════════════════════════════════════
let mockDevice: DeviceInfo | null = null;

const mockScripts: Script[] = [];

const mockTasks: TaskInfo[] = [];

const mockAssets: AssetInfo[] = [
  { name: 'btn_start.png', size: 2048 },
  { name: 'icon_gold.png', size: 1024 },
];

const mockLogs: string[] = [
  '[系統] Game Bot Mock 模式已啟動',
];

// ═══════════════════════════════════════════
//  裝置管理
// ═══════════════════════════════════════════
export const deviceConnect = async (params: {
  serial?: string;
  mode?: string;
  emulator_type?: string;
}): Promise<DeviceInfo> => {
  if (isTauri()) return tauriInvoke<DeviceInfo>('device_connect', { params });

  // Mock: 模擬連接
  mockDevice = {
    connected: true,
    serial: params.serial ?? '127.0.0.1:5555',
    mode: params.mode ?? 'adb',
    emulator_type: params.emulator_type ?? 'auto',
    resolution: [1920, 1080],
  };
  mockLogs.push(`[Mock] ✅ 已連接裝置: ${mockDevice.serial}`);
  return mockDevice;
};

export const deviceDisconnect = async (): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('device_disconnect');
  mockDevice = null;
  mockLogs.push('[Mock] 🔌 已斷開裝置連線');
};

export const deviceStatus = async (): Promise<DeviceInfo> => {
  if (isTauri()) return tauriInvoke<DeviceInfo>('device_status');
  return mockDevice ?? { connected: false, serial: '', mode: 'adb', emulator_type: 'auto', resolution: [0, 0] };
};

// ═══════════════════════════════════════════
//  截圖
// ═══════════════════════════════════════════
export const screenshotCapture = async () => {
  if (isTauri()) return tauriInvoke<{ image_b64: string; width: number; height: number }>('screenshot_capture');
  return { image_b64: '', width: 1920, height: 1080 };
};

export const screenshotHighres = async () => {
  if (isTauri()) return tauriInvoke<{ image_b64: string; width: number; height: number }>('screenshot_highres');
  return { image_b64: '', width: 1920, height: 1080 };
};

// ═══════════════════════════════════════════
//  腳本管理
// ═══════════════════════════════════════════
export const scriptList = async (): Promise<Script[]> => {
  if (isTauri()) return tauriInvoke<Script[]>('script_list');
  return [...mockScripts];
};

export const scriptCreate = async (name: string): Promise<Script> => {
  if (isTauri()) return tauriInvoke<Script>('script_create', { name });

  const script: Script = {
    id: `mock_${Date.now()}`,
    name,
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
  };
  mockScripts.push(script);
  mockLogs.push(`[Mock] 📝 已建立腳本: ${name}`);
  return script;
};

export const scriptSave = async (script: Script): Promise<Script> => {
  if (isTauri()) return tauriInvoke<Script>('script_save', { script });

  const idx = mockScripts.findIndex((s) => s.id === script.id);
  const updated = { ...script, version: script.version + 1, updated_at: new Date().toISOString() };
  if (idx >= 0) mockScripts[idx] = updated;
  mockLogs.push(`[Mock] 💾 已儲存腳本: ${script.name}`);
  return updated;
};

export const scriptDelete = async (scriptId: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('script_delete', { scriptId });

  const idx = mockScripts.findIndex((s) => s.id === scriptId);
  if (idx >= 0) mockScripts.splice(idx, 1);
  mockLogs.push('[Mock] 🗑️ 已刪除腳本');
};

// ═══════════════════════════════════════════
//  任務控制
// ═══════════════════════════════════════════
export const taskStart = async (params: {
  script_id: string;
  script_name: string;
  run_mode: string;
  max_runs: number;
}): Promise<TaskInfo> => {
  if (isTauri()) return tauriInvoke<TaskInfo>('task_start', { params });

  const task: TaskInfo = {
    job_id: `job_${Date.now()}`,
    script_id: params.script_id,
    script_name: params.script_name,
    enabled: true,
    completed: false,
    run_count: 0,
    max_runs: params.max_runs,
    run_mode: params.run_mode,
  };
  mockTasks.push(task);
  mockLogs.push(`[Mock] 🚀 已啟動任務: ${params.script_name}`);
  return task;
};

export const taskToggle = async (jobId: string): Promise<TaskInfo> => {
  if (isTauri()) return tauriInvoke<TaskInfo>('task_toggle', { jobId });

  const task = mockTasks.find((t) => t.job_id === jobId);
  if (!task) throw new Error('找不到任務');
  task.enabled = !task.enabled;
  return { ...task };
};

export const taskStop = async (jobId: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('task_stop', { jobId });

  const idx = mockTasks.findIndex((t) => t.job_id === jobId);
  if (idx >= 0) mockTasks.splice(idx, 1);
  mockLogs.push('[Mock] 🛑 已停止任務');
};

export const taskList = async (): Promise<TaskInfo[]> => {
  if (isTauri()) return tauriInvoke<TaskInfo[]>('task_list');
  return [...mockTasks];
};

export const getLogs = async (limit?: number): Promise<string[]> => {
  if (isTauri()) return tauriInvoke<string[]>('get_logs', { limit });
  const l = limit ?? 100;
  return mockLogs.slice(-l);
};

// ═══════════════════════════════════════════
//  資源管理
// ═══════════════════════════════════════════
export const assetList = async (): Promise<AssetInfo[]> => {
  if (isTauri()) return tauriInvoke<AssetInfo[]>('asset_list');
  return [...mockAssets];
};

export const assetSaveCrop = async (params: { name: string; image_b64: string }): Promise<AssetInfo> => {
  if (isTauri()) return tauriInvoke<AssetInfo>('asset_save_crop', { params });

  const asset: AssetInfo = { name: params.name, size: params.image_b64.length };
  mockAssets.push(asset);
  mockLogs.push(`[Mock] 📷 已儲存裁切: ${params.name}`);
  return asset;
};

export const assetDelete = async (name: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('asset_delete', { name });

  const idx = mockAssets.findIndex((a) => a.name === name);
  if (idx >= 0) mockAssets.splice(idx, 1);
  mockLogs.push(`[Mock] 🗑️ 已刪除資源: ${name}`);
};

export const assetRead = async (name: string): Promise<string> => {
  if (isTauri()) return tauriInvoke<string>('asset_read', { name });
  return 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPj/HwADBwIAMCbHYQAAAABJRU5ErkJggg==';
};
