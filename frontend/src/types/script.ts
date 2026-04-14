// 腳本相關型別定義

export interface NodePosition {
  x: number;
  y: number;
}

export type ScriptNodeType = 'start' | 'end' | 'condition' | 'action' | 'logic';
export type ConditionType = 'image_match' | 'ocr_text' | 'pixel_color' | 'always_true';
export type ActionType = 'click_match' | 'click_coord' | 'swipe' | 'wait' | 'input_text';

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
