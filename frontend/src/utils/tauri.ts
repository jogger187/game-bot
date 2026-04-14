// Tauri IPC 呼叫封裝 — Tauri 模式用 invoke，瀏覽器模式用 Python HTTP API
import type { DeviceInfo, Script, AssetInfo, TaskInfo } from '../types/script';

// 偵測是否在 Tauri 環境中執行
const isTauri = () => !!(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;

// Python API 伺服器位址
const API_BASE = 'http://localhost:8765/api';

// 動態載入 Tauri invoke
const tauriInvoke = async <T>(cmd: string, args?: Record<string, unknown>): Promise<T> => {
  const { invoke } = await import('@tauri-apps/api/core');
  return invoke<T>(cmd, args);
};

// HTTP API 呼叫工具
const apiCall = async <T>(path: string, options?: RequestInit): Promise<T> => {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
};

// ═══════════════════════════════════════════
//  裝置管理
// ═══════════════════════════════════════════
export const deviceList = async (): Promise<{ devices: { serial: string; status: string }[] }> => {
  if (isTauri()) return tauriInvoke('device_list');
  return apiCall('/devices');
};

export const deviceConnect = async (params: {
  serial?: string;
  mode?: string;
  emulator_type?: string;
}): Promise<DeviceInfo> => {
  if (isTauri()) return tauriInvoke<DeviceInfo>('device_connect', { params });
  return apiCall<DeviceInfo>('/device/connect', {
    method: 'POST',
    body: JSON.stringify(params),
  });
};

export const deviceDisconnect = async (): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('device_disconnect');
  await apiCall('/device/disconnect', { method: 'POST' });
};

export const deviceStatus = async (): Promise<DeviceInfo> => {
  if (isTauri()) return tauriInvoke<DeviceInfo>('device_status');
  return apiCall<DeviceInfo>('/device/status');
};

// ═══════════════════════════════════════════
//  截圖
// ═══════════════════════════════════════════
export const screenshotCapture = async () => {
  if (isTauri()) return tauriInvoke<{ image_b64: string; width: number; height: number }>('screenshot_capture');
  return apiCall<{ image_b64: string; width: number; height: number }>('/screenshot', { method: 'POST' });
};

export const screenshotHighres = async () => {
  if (isTauri()) return tauriInvoke<{ image_b64: string; width: number; height: number }>('screenshot_highres');
  return apiCall<{ image_b64: string; width: number; height: number }>('/screenshot', { method: 'POST' });
};

// ═══════════════════════════════════════════
//  腳本管理
// ═══════════════════════════════════════════
export const scriptList = async (): Promise<Script[]> => {
  if (isTauri()) return tauriInvoke<Script[]>('script_list');
  // 瀏覽器開發模式暫時返回空列表（腳本管理較複雜，之後再接 API）
  return [];
};

export const scriptCreate = async (name: string): Promise<Script> => {
  if (isTauri()) return tauriInvoke<Script>('script_create', { name });
  const script: Script = {
    id: `dev_${Date.now()}`,
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
  return script;
};

export const scriptSave = async (script: Script): Promise<Script> => {
  if (isTauri()) return tauriInvoke<Script>('script_save', { script });
  return { ...script, version: script.version + 1, updated_at: new Date().toISOString() };
};

export const scriptDelete = async (scriptId: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('script_delete', { scriptId });
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
  return {
    job_id: `job_${Date.now()}`,
    script_id: params.script_id,
    script_name: params.script_name,
    enabled: true,
    completed: false,
    run_count: 0,
    max_runs: params.max_runs,
    run_mode: params.run_mode,
  };
};

export const taskToggle = async (jobId: string): Promise<TaskInfo> => {
  if (isTauri()) return tauriInvoke<TaskInfo>('task_toggle', { jobId });
  throw new Error('Task toggle not available in browser mode');
};

export const taskStop = async (jobId: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('task_stop', { jobId });
};

export const taskList = async (): Promise<TaskInfo[]> => {
  if (isTauri()) return tauriInvoke<TaskInfo[]>('task_list');
  return [];
};

export const getLogs = async (limit?: number): Promise<string[]> => {
  if (isTauri()) return tauriInvoke<string[]>('get_logs', { limit });
  return apiCall<string[]>(`/logs?limit=${limit ?? 100}`);
};

// ═══════════════════════════════════════════
//  資源管理
// ═══════════════════════════════════════════
export const assetList = async (): Promise<AssetInfo[]> => {
  if (isTauri()) return tauriInvoke<AssetInfo[]>('asset_list');
  return apiCall<AssetInfo[]>('/assets');
};

export const assetSaveCrop = async (params: { name: string; image_b64: string }): Promise<AssetInfo> => {
  if (isTauri()) return tauriInvoke<AssetInfo>('asset_save_crop', { params });
  return apiCall<AssetInfo>('/assets', {
    method: 'POST',
    body: JSON.stringify(params),
  });
};

export const assetDelete = async (name: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('asset_delete', { name });
  await apiCall(`/assets/${encodeURIComponent(name)}`, { method: 'DELETE' });
};

export const assetRead = async (name: string): Promise<string> => {
  if (isTauri()) return tauriInvoke<string>('asset_read', { name });
  const result = await apiCall<{ image_b64: string }>(`/assets/${encodeURIComponent(name)}/read`);
  return result.image_b64;
};
