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
  return apiCall<Script[]>('/scripts');
};

export const scriptCreate = async (name: string): Promise<Script> => {
  if (isTauri()) return tauriInvoke<Script>('script_create', { name });
  return apiCall<Script>('/scripts', {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
};

export const scriptSave = async (script: Script): Promise<Script> => {
  if (isTauri()) return tauriInvoke<Script>('script_save', { script });
  return apiCall<Script>('/scripts', {
    method: 'PUT',
    body: JSON.stringify(script),
  });
};

export const scriptDelete = async (scriptId: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('script_delete', { scriptId });
  await apiCall(`/scripts/${encodeURIComponent(scriptId)}`, { method: 'DELETE' });
};

// ═══════════════════════════════════════════
//  任務控制
// ═══════════════════════════════════════════
export const taskStart = async (params: {
  script_id: string;
  script_name: string;
  run_mode: string;
  max_runs: number;
  loop_interval?: number;
  scheduled_times?: string[];
}): Promise<TaskInfo> => {
  if (isTauri()) return tauriInvoke<TaskInfo>('task_start', { params });
  return apiCall<TaskInfo>('/tasks', {
    method: 'POST',
    body: JSON.stringify(params),
  });
};

export const taskToggle = async (jobId: string): Promise<TaskInfo> => {
  if (isTauri()) return tauriInvoke<TaskInfo>('task_toggle', { jobId });
  return apiCall<TaskInfo>(`/tasks/${encodeURIComponent(jobId)}/toggle`, { method: 'POST' });
};

export const taskStop = async (jobId: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('task_stop', { jobId });
  await apiCall(`/tasks/${encodeURIComponent(jobId)}/stop`, { method: 'POST' });
};

export const taskRemove = async (jobId: string): Promise<void> => {
  if (isTauri()) return tauriInvoke<void>('task_remove', { jobId });
  await apiCall(`/tasks/${encodeURIComponent(jobId)}`, { method: 'DELETE' });
};

export const taskList = async (): Promise<TaskInfo[]> => {
  if (isTauri()) return tauriInvoke<TaskInfo[]>('task_list');
  return apiCall<TaskInfo[]>('/tasks');
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
