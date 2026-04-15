// 全域應用狀態管理
import { create } from 'zustand';
import type { DeviceInfo, Script, AssetInfo, TaskInfo } from '../types/script';
import * as api from '../utils/tauri';

type Page = 'dashboard' | 'scripts' | 'assets' | 'runner' | 'settings';

interface AppStore {
  // 導航
  currentPage: Page;
  setPage: (page: Page) => void;

  // 裝置
  device: DeviceInfo | null;
  fetchDevice: () => Promise<void>;
  connectDevice: (serial?: string, mode?: string) => Promise<void>;
  disconnectDevice: () => Promise<void>;

  // 腳本
  scripts: Script[];
  fetchScripts: () => Promise<void>;
  createScript: (name: string) => Promise<Script>;
  saveScript: (script: Script) => Promise<void>;
  deleteScript: (id: string) => Promise<void>;

  // 資源
  assets: AssetInfo[];
  fetchAssets: () => Promise<void>;
  deleteAsset: (name: string) => Promise<void>;

  // 任務
  tasks: TaskInfo[];
  fetchTasks: () => Promise<void>;
  startTask: (scriptId: string, scriptName: string, runMode: string, maxRuns: number, loopInterval?: number, scheduledTimes?: string[]) => Promise<void>;
  toggleTask: (jobId: string) => Promise<void>;
  stopTask: (jobId: string) => Promise<void>;
  removeTask: (jobId: string) => Promise<void>;

  // 日誌
  logs: string[];
  fetchLogs: () => Promise<void>;
  addLog: (msg: string) => void;
}

export const useAppStore = create<AppStore>((set, get) => ({
  // ── 導航 ──
  currentPage: 'dashboard',
  setPage: (page) => set({ currentPage: page }),

  // ── 裝置 ──
  device: null,
  fetchDevice: async () => {
    try {
      const info = await api.deviceStatus();
      set({ device: info });
    } catch {
      set({ device: null });
    }
  },
  connectDevice: async (serial, mode) => {
    try {
      const info = await api.deviceConnect({ serial, mode });
      set({ device: info });
      get().addLog(`✅ 已連接裝置: ${info.serial}`);
    } catch (e) {
      get().addLog(`❌ 連接失敗: ${e}`);
    }
  },
  disconnectDevice: async () => {
    try {
      await api.deviceDisconnect();
      set({ device: null });
      get().addLog('🔌 已斷開裝置連線');
    } catch (e) {
      get().addLog(`❌ 斷線失敗: ${e}`);
    }
  },

  // ── 腳本 ──
  scripts: [],
  fetchScripts: async () => {
    try {
      const list = await api.scriptList();
      set({ scripts: list });
    } catch {
      set({ scripts: [] });
    }
  },
  createScript: async (name) => {
    const script = await api.scriptCreate(name);
    set((s) => ({ scripts: [...s.scripts, script] }));
    get().addLog(`📝 已建立腳本: ${name}`);
    return script;
  },
  saveScript: async (script) => {
    const updated = await api.scriptSave(script);
    set((s) => ({
      scripts: s.scripts.map((sc) => (sc.id === updated.id ? updated : sc)),
    }));
    get().addLog(`💾 已儲存腳本: ${script.name}`);
  },
  deleteScript: async (id) => {
    await api.scriptDelete(id);
    set((s) => ({ scripts: s.scripts.filter((sc) => sc.id !== id) }));
    get().addLog('🗑️ 已刪除腳本');
  },

  // ── 資源 ──
  assets: [],
  fetchAssets: async () => {
    try {
      const list = await api.assetList();
      set({ assets: list });
    } catch {
      set({ assets: [] });
    }
  },
  deleteAsset: async (name) => {
    await api.assetDelete(name);
    set((s) => ({ assets: s.assets.filter((a) => a.name !== name) }));
    get().addLog(`🗑️ 已刪除資源: ${name}`);
  },

  // ── 任務 ──
  tasks: [],
  fetchTasks: async () => {
    try {
      const list = await api.taskList();
      set({ tasks: list });
    } catch {
      set({ tasks: [] });
    }
  },
  startTask: async (scriptId, scriptName, runMode, maxRuns, loopInterval = 3, scheduledTimes = []) => {
    const task = await api.taskStart({
      script_id: scriptId,
      script_name: scriptName,
      run_mode: runMode,
      max_runs: maxRuns,
      loop_interval: loopInterval,
      scheduled_times: scheduledTimes,
    });
    set((s) => ({ tasks: [...s.tasks, task] }));
    get().addLog(`🚀 已啟動任務: ${scriptName}`);
  },
  toggleTask: async (jobId) => {
    const updated = await api.taskToggle(jobId);
    set((s) => ({
      tasks: s.tasks.map((t) => (t.job_id === jobId ? updated : t)),
    }));
  },
  stopTask: async (jobId) => {
    await api.taskStop(jobId);
    // 停止後標記為已完成，不從列表移除
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.job_id === jobId ? { ...t, enabled: false, completed: true } : t
      ),
    }));
    get().addLog('🛑 已停止任務');
  },
  removeTask: async (jobId) => {
    await api.taskRemove(jobId);
    set((s) => ({ tasks: s.tasks.filter((t) => t.job_id !== jobId) }));
    get().addLog('🗑️ 已移除任務');
  },

  // ── 日誌 ──
  logs: [],
  fetchLogs: async () => {
    try {
      const list = await api.getLogs(200);
      set({ logs: list });
    } catch {
      /* noop */
    }
  },
  addLog: (msg) => {
    const ts = new Date().toLocaleTimeString();
    set((s) => ({ logs: [...s.logs.slice(-199), `[${ts}] ${msg}`] }));
  },
}));
