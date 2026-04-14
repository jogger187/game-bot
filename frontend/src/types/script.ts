// 腳本相關型別定義

export interface NodePosition {
  x: number;
  y: number;
}

// ═══════════════════════════════════════════
//  節點類型定義 — 頂級外掛模塊系統
// ═══════════════════════════════════════════

// 流程控制節點
export type FlowNodeType = 'start' | 'end' | 'if_else' | 'loop' | 'sub_script';

// 偵測/感知節點
export type DetectNodeType = 'find_image' | 'ocr_text' | 'pixel_check' | 'wait_image';

// 操作/動作節點
export type ActionNodeType = 'click' | 'swipe' | 'sleep' | 'input_text' | 'key_press' | 'screenshot';

// 邏輯節點
export type LogicNodeType = 'set_variable' | 'log' | 'random_delay';

export type ScriptNodeType = FlowNodeType | DetectNodeType | ActionNodeType | LogicNodeType;

// ═══════════════════════════════════════════
//  各模塊的資料結構
// ═══════════════════════════════════════════

/** 圖片搜尋節點 — 在螢幕上尋找模板圖片 */
export interface FindImageData {
  template: string;       // 模板圖片名稱 (e.g. "btn_start.png")
  threshold: number;      // 匹配信心度 0~1 (預設 0.8)
  region_enabled: boolean;
  region: { x: number; y: number; w: number; h: number }; // 搜尋區域
  timeout: number;        // 超時秒數
  variable: string;       // 將結果存入變數名
}

/** 等待圖片出現 — 持續截圖直到找到圖片 */
export interface WaitImageData {
  template: string;
  threshold: number;
  timeout: number;        // 最長等待秒數
  interval: number;       // 每次重試間隔
  region_enabled: boolean;
  region: { x: number; y: number; w: number; h: number };
}

/** OCR 文字識別 */
export interface OcrTextData {
  region: { x: number; y: number; w: number; h: number };
  language: string;       // "chi_tra" | "chi_sim" | "eng"
  variable: string;       // 將辨識結果存入變數
}

/** 像素顏色檢查 */
export interface PixelCheckData {
  x: number;
  y: number;
  expected_color: string; // "#RRGGBB"
  tolerance: number;      // 容差 0~255
  variable: string;
}

/** 點擊動作 */
export interface ClickData {
  mode: 'coordinate' | 'match_center' | 'match_random';
  x: number;              // 座標模式的 x
  y: number;              // 座標模式的 y
  template: string;       // 匹配模式的模板名
  threshold: number;
  offset_x: number;       // 偏移量
  offset_y: number;
  random_range: number;   // 隨機偏移範圍 (防檢測)
  hold_ms: number;        // 長按毫秒數
  repeat: number;         // 重複點擊次數
  repeat_interval: number; // 重複間隔 ms
}

/** 滑動手勢 */
export interface SwipeData {
  from_x: number;
  from_y: number;
  to_x: number;
  to_y: number;
  duration: number;       // 滑動持續時間 ms
  random_range: number;   // 隨機偏移
}

/** 等待/延遲 */
export interface SleepData {
  duration: number;       // 秒
  random_min: number;     // 隨機範圍最小 (0 = 不隨機)
  random_max: number;     // 隨機範圍最大
}

/** 文字輸入 */
export interface InputTextData {
  text: string;
  clear_first: boolean;   // 先清空輸入框
}

/** 按鍵模擬 */
export interface KeyPressData {
  key: 'back' | 'home' | 'recent' | 'volume_up' | 'volume_down' | 'power';
}

/** 條件分支 (if/else) */
export interface IfElseData {
  condition_type: 'image_found' | 'image_not_found' | 'ocr_contains' | 'ocr_not_contains' | 'variable_equals' | 'variable_gt' | 'variable_lt' | 'pixel_match' | 'always_true';
  // 圖片匹配條件
  template: string;
  threshold: number;
  // OCR 條件
  ocr_region: { x: number; y: number; w: number; h: number };
  ocr_text: string;
  // 變數條件
  variable: string;
  compare_value: string;
  // 像素條件
  pixel_x: number;
  pixel_y: number;
  pixel_color: string;
  pixel_tolerance: number;
}

/** 迴圈 */
export interface LoopData {
  mode: 'count' | 'while_image' | 'while_no_image' | 'infinite';
  count: number;          // 迴圈次數
  template: string;       // while 條件用的圖片
  threshold: number;
  max_iterations: number; // 安全上限
}

/** 設定變數 */
export interface SetVariableData {
  variable: string;
  value: string;
  value_type: 'string' | 'number' | 'counter_increment' | 'counter_decrement';
}

/** 日誌輸出 */
export interface LogData {
  message: string;
  level: 'info' | 'warn' | 'error';
}

/** 隨機延遲 */
export interface RandomDelayData {
  min_seconds: number;
  max_seconds: number;
}

// ═══════════════════════════════════════════
//  節點定義
// ═══════════════════════════════════════════
export interface ScriptNode {
  id: string;
  type: ScriptNodeType;
  position: NodePosition;
  data: Record<string, unknown>;
}

export interface ScriptEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;  // if_else 的 "true" / "false" 輸出
  label?: string;
}

export interface ScriptSettings {
  loop_enabled: boolean;
  interval: number;
  max_runs: number;
}

export interface Script {
  id: string;
  name: string;
  version: number;
  created_at: string;
  updated_at: string;
  nodes: ScriptNode[];
  edges: ScriptEdge[];
  settings: ScriptSettings;
  rules: Record<string, unknown>[];
}

export interface AssetInfo {
  name: string;
  size: number;
}

export interface TaskInfo {
  job_id: string;
  script_id: string;
  script_name: string;
  enabled: boolean;
  completed: boolean;
  run_count: number;
  max_runs: number;
  run_mode: string;
}

export interface DeviceInfo {
  connected: boolean;
  serial: string;
  mode: string;
  emulator_type: string;
  resolution: [number, number];
}

// ═══════════════════════════════════════════
//  節點模塊定義（用於工具箱）
// ═══════════════════════════════════════════
export interface NodeModuleDef {
  type: ScriptNodeType;
  label: string;
  icon: string;
  color: string;
  category: 'flow' | 'detect' | 'action' | 'logic';
  description: string;
  defaultData: Record<string, unknown>;
}

/** 所有可用的模塊定義 */
export const NODE_MODULES: NodeModuleDef[] = [
  // ── 流程控制 ──
  { type: 'start',      label: '開始',     icon: '🟢', color: '#065f46', category: 'flow',   description: '腳本入口點', defaultData: {} },
  { type: 'end',        label: '結束',     icon: '🔴', color: '#7f1d1d', category: 'flow',   description: '腳本結束點', defaultData: {} },
  { type: 'if_else',    label: '條件分支',  icon: '🔀', color: '#1e3a8a', category: 'flow',   description: 'If/Else 條件判斷',
    defaultData: { condition_type: 'image_found', template: '', threshold: 0.8, ocr_region: { x: 0, y: 0, w: 0, h: 0 }, ocr_text: '', variable: '', compare_value: '', pixel_x: 0, pixel_y: 0, pixel_color: '#000000', pixel_tolerance: 30 } },
  { type: 'loop',       label: '迴圈',     icon: '🔄', color: '#4c1d95', category: 'flow',   description: '重複執行 N 次或條件迴圈',
    defaultData: { mode: 'count', count: 5, template: '', threshold: 0.8, max_iterations: 999 } },

  // ── 偵測/感知 ──
  { type: 'find_image', label: '找圖',     icon: '🔍', color: '#0e7490', category: 'detect', description: '在螢幕上搜尋模板圖片',
    defaultData: { template: '', threshold: 0.8, region_enabled: false, region: { x: 0, y: 0, w: 0, h: 0 }, timeout: 5, variable: 'match_result' } },
  { type: 'wait_image', label: '等待圖片',  icon: '⏳', color: '#0369a1', category: 'detect', description: '持續等待直到圖片出現',
    defaultData: { template: '', threshold: 0.8, timeout: 30, interval: 1, region_enabled: false, region: { x: 0, y: 0, w: 0, h: 0 } } },
  { type: 'ocr_text',   label: 'OCR 辨識', icon: '📖', color: '#7c3aed', category: 'detect', description: '識別螢幕區域文字',
    defaultData: { region: { x: 0, y: 0, w: 200, h: 50 }, language: 'chi_tra', variable: 'ocr_result' } },
  { type: 'pixel_check',label: '像素檢查',  icon: '🎨', color: '#a21caf', category: 'detect', description: '檢查指定座標的像素顏色',
    defaultData: { x: 0, y: 0, expected_color: '#FFFFFF', tolerance: 30, variable: 'pixel_result' } },

  // ── 操作/動作 ──
  { type: 'click',      label: '點擊',     icon: '👆', color: '#b45309', category: 'action', description: '點擊座標或匹配圖片位置',
    defaultData: { mode: 'coordinate', x: 0, y: 0, template: '', threshold: 0.8, offset_x: 0, offset_y: 0, random_range: 3, hold_ms: 0, repeat: 1, repeat_interval: 100 } },
  { type: 'swipe',      label: '滑動',     icon: '👉', color: '#c2410c', category: 'action', description: '滑動手勢',
    defaultData: { from_x: 500, from_y: 800, to_x: 500, to_y: 300, duration: 300, random_range: 5 } },
  { type: 'sleep',      label: '等待',     icon: '⏱️', color: '#475569', category: 'action', description: '暫停指定秒數',
    defaultData: { duration: 1, random_min: 0, random_max: 0 } },
  { type: 'input_text', label: '文字輸入',  icon: '⌨️', color: '#0f766e', category: 'action', description: '輸入文字到當前輸入框',
    defaultData: { text: '', clear_first: true } },
  { type: 'key_press',  label: '按鍵',     icon: '🔘', color: '#6b7280', category: 'action', description: '模擬按下硬體按鍵 (返回/Home)',
    defaultData: { key: 'back' } },

  // ── 邏輯 ──
  { type: 'set_variable',label: '設定變數', icon: '📦', color: '#374151', category: 'logic', description: '設定或修改變數值',
    defaultData: { variable: 'my_var', value: '0', value_type: 'string' } },
  { type: 'log',         label: '日誌',    icon: '📝', color: '#334155', category: 'logic', description: '輸出日誌訊息',
    defaultData: { message: '', level: 'info' } },
  { type: 'random_delay',label: '隨機延遲', icon: '🎲', color: '#57534e', category: 'logic', description: '隨機等待 (防檢測)',
    defaultData: { min_seconds: 0.5, max_seconds: 2.0 } },
];
