import type { Node, Edge } from '@xyflow/react';
import type { ScriptNode, ScriptEdge, ScriptNodeType } from '../types/script';

export interface RecordedAction {
  time: number;
  action: 'tap' | 'swipe';
  x?: number;
  y?: number;
  from_x?: number;
  from_y?: number;
  to_x?: number;
  to_y?: number;
  duration?: number;
}

export type DelayMode = 'random_delay' | 'sleep' | 'none';
export type ApplyMode = 'insert_after' | 'replace' | 'new_script';

export interface ConvertOptions {
  applyMode: ApplyMode;
  delayMode: DelayMode;
  minDelayThreshold: number; // 秒，例如 0.3
  randomRange: number; // 像素，例如 3
  targetNodeId?: string | null;
  newScriptName?: string;
}

interface GeneratedNode {
  id: string;
  type: string;
  node_type: string;
  data: Record<string, unknown>;
}

/** 將單一動作清單轉為中間節點陣列 (不含起訖節點) */
export function convertActionsToRawNodes(
  actions: RecordedAction[],
  options: Pick<ConvertOptions, 'delayMode' | 'minDelayThreshold' | 'randomRange'>,
): GeneratedNode[] {
  const result: GeneratedNode[] = [];
  const baseTimestamp = Date.now();

  for (let i = 0; i < actions.length; i++) {
    const curr = actions[i];
    const prev = i > 0 ? actions[i - 1] : null;

    // 處理動作間隔延遲
    if (prev && options.delayMode !== 'none') {
      const delta = +(curr.time - prev.time).toFixed(2);
      if (delta >= options.minDelayThreshold) {
        const delayId = `delay_${baseTimestamp}_${i}`;
        if (options.delayMode === 'random_delay') {
          const minSec = Math.max(0.1, +(delta * 0.8).toFixed(2));
          const maxSec = +(delta * 1.2).toFixed(2);
          result.push({
            id: delayId,
            type: 'custom',
            node_type: 'random_delay',
            data: {
              node_type: 'random_delay',
              min_seconds: minSec,
              max_seconds: maxSec,
              min_ms: Math.round(minSec * 1000),
              max_ms: Math.round(maxSec * 1000),
            },
          });
        } else if (options.delayMode === 'sleep') {
          result.push({
            id: delayId,
            type: 'custom',
            node_type: 'sleep',
            data: {
              node_type: 'sleep',
              duration: delta,
              random_min: 0,
              random_max: 0,
              ms: Math.round(delta * 1000),
            },
          });
        }
      }
    }

    // 處理操作本身
    const actionId = `${curr.action}_${baseTimestamp}_${i}`;
    if (curr.action === 'tap') {
      result.push({
        id: actionId,
        type: 'custom',
        node_type: 'click',
        data: {
          node_type: 'click',
          mode: 'coordinate',
          x: curr.x ?? 0,
          y: curr.y ?? 0,
          template: '',
          threshold: 0.8,
          offset_x: 0,
          offset_y: 0,
          random_range: options.randomRange,
          hold_ms: 0,
          repeat: 1,
          repeat_interval: 100,
        },
      });
    } else if (curr.action === 'swipe') {
      result.push({
        id: actionId,
        type: 'custom',
        node_type: 'swipe',
        data: {
          node_type: 'swipe',
          from_x: curr.from_x ?? 0,
          from_y: curr.from_y ?? 0,
          to_x: curr.to_x ?? 0,
          to_y: curr.to_y ?? 0,
          x1: curr.from_x ?? 0,
          y1: curr.from_y ?? 0,
          x2: curr.to_x ?? 0,
          y2: curr.to_y ?? 0,
          duration: curr.duration ?? 300,
          random_range: options.randomRange,
        },
      });
    }
  }

  return result;
}

/** 依網格/蛇形計算節點座標 */
export function layoutNodesInGrid(
  startPos: { x: number; y: number },
  nodes: GeneratedNode[],
  cols = 4,
  spacingX = 220,
  spacingY = 130,
): Node[] {
  return nodes.map((n, idx) => {
    const row = Math.floor(idx / cols);
    const colInRow = idx % cols;
    // 蛇形排列：偶數行由左至右，奇數行由右至左
    const actualCol = row % 2 === 0 ? colInRow : cols - 1 - colInRow;

    return {
      id: n.id,
      type: 'custom',
      position: {
        x: startPos.x + actualCol * spacingX,
        y: startPos.y + row * spacingY,
      },
      data: n.data,
    };
  });
}

/** 產生節點之間的連續 Edge */
function buildLinearEdges(nodeIds: string[]): Edge[] {
  const edges: Edge[] = [];
  for (let i = 0; i < nodeIds.length - 1; i++) {
    edges.push({
      id: `e_${nodeIds[i]}_${nodeIds[i + 1]}`,
      source: nodeIds[i],
      target: nodeIds[i + 1],
      style: { stroke: '#6366f1' },
      animated: true,
    });
  }
  return edges;
}

/**
 * 將錄製結果套用到現有 React Flow 結構 (nodes & edges)
 */
export function applyActionsToFlow(
  currentNodes: Node[],
  currentEdges: Edge[],
  actions: RecordedAction[],
  options: ConvertOptions,
): { nodes: Node[]; edges: Edge[]; insertedNodeIds: string[] } {
  const rawNodes = convertActionsToRawNodes(actions, options);
  if (rawNodes.length === 0) {
    return { nodes: currentNodes, edges: currentEdges, insertedNodeIds: [] };
  }

  // ═══════════════════════════════════════════
  // 模式 1: 覆蓋當前腳本 (Replace)
  // ═══════════════════════════════════════════
  if (options.applyMode === 'replace') {
    let startNode = currentNodes.find((n) => (n.data as Record<string, unknown>)?.node_type === 'start');
    let endNode = currentNodes.find((n) => (n.data as Record<string, unknown>)?.node_type === 'end');

    if (!startNode) {
      startNode = {
        id: 'start_1',
        type: 'custom',
        position: { x: 100, y: 150 },
        data: { node_type: 'start' },
      };
    }
    if (!endNode) {
      endNode = {
        id: 'end_1',
        type: 'custom',
        position: { x: 100, y: 350 },
        data: { node_type: 'end' },
      };
    }

    const cols = Math.min(5, Math.max(3, Math.ceil(Math.sqrt(rawNodes.length))));
    const layouted = layoutNodesInGrid({ x: startNode.position.x + 220, y: startNode.position.y }, rawNodes, cols);

    // end 節點移到最後一個節點的右側或下方
    const lastNode = layouted[layouted.length - 1];
    const updatedEndNode: Node = {
      ...endNode,
      position: {
        x: lastNode.position.x + 220,
        y: lastNode.position.y,
      },
    };

    const allNodeIds = [startNode.id, ...layouted.map((n) => n.id), updatedEndNode.id];
    const newEdges = buildLinearEdges(allNodeIds);

    return {
      nodes: [startNode, ...layouted, updatedEndNode],
      edges: newEdges,
      insertedNodeIds: layouted.map((n) => n.id),
    };
  }

  // ═══════════════════════════════════════════
  // 模式 2: 插入至選取節點之後 (Insert After)
  // ═══════════════════════════════════════════
  let pivotNode = options.targetNodeId
    ? currentNodes.find((n) => n.id === options.targetNodeId)
    : null;

  // 若沒選取或選取的是 end 節點，則預設以 start 節點或第一個可用節點為基準
  if (!pivotNode || (pivotNode.data as Record<string, unknown>)?.node_type === 'end') {
    pivotNode =
      currentNodes.find((n) => (n.data as Record<string, unknown>)?.node_type === 'start') ??
      currentNodes[0];
  }

  // 如果畫布完全為空
  if (!pivotNode) {
    const layouted = layoutNodesInGrid({ x: 100, y: 150 }, rawNodes);
    return {
      nodes: layouted,
      edges: buildLinearEdges(layouted.map((n) => n.id)),
      insertedNodeIds: layouted.map((n) => n.id),
    };
  }

  // 找出 pivot 原本連往的下游 edges (例如 pivot -> next)
  const outgoingEdges = currentEdges.filter((e) => e.source === pivotNode!.id);
  const nextTargetId = outgoingEdges.length > 0 ? outgoingEdges[0].target : null;

  // 排版新節點：從 pivot 節點右側開始
  const cols = Math.min(4, Math.max(2, rawNodes.length));
  const startPos = {
    x: pivotNode.position.x + 220,
    y: pivotNode.position.y,
  };
  const layoutedNewNodes = layoutNodesInGrid(startPos, rawNodes, cols);

  // 計算新鏈條
  const newChainIds = [pivotNode.id, ...layoutedNewNodes.map((n) => n.id)];
  if (nextTargetId) {
    newChainIds.push(nextTargetId);
  }

  // 移出原 outgoing 邊，並換上新鏈條邊
  const remainingEdges = currentEdges.filter((e) => !outgoingEdges.some((out) => out.id === e.id));
  const insertedEdges = buildLinearEdges(newChainIds);

  // 下游節點 (如果是 next 及其之後的節點) 稍微向下/向右平移，避免重疊
  const lastNewNode = layoutedNewNodes[layoutedNewNodes.length - 1];
  const deltaShiftX = Math.max(0, lastNewNode.position.x - pivotNode.position.x);

  const adjustedExistingNodes = currentNodes.map((node) => {
    if (node.id === pivotNode!.id) return node;
    // 如果節點原本就在 pivot 右方，適度右移
    if (node.position.x > pivotNode!.position.x && nextTargetId) {
      return {
        ...node,
        position: {
          x: node.position.x + deltaShiftX,
          y: node.position.y,
        },
      };
    }
    return node;
  });

  return {
    nodes: [...adjustedExistingNodes, ...layoutedNewNodes],
    edges: [...remainingEdges, ...insertedEdges],
    insertedNodeIds: layoutedNewNodes.map((n) => n.id),
  };
}

/**
 * 轉為全新腳本物件所使用的節點與連線格式
 */
export function buildScriptFromActions(
  actions: RecordedAction[],
  options: ConvertOptions,
): { nodes: ScriptNode[]; edges: ScriptEdge[] } {
  const dummyNodes: Node[] = [
    { id: 'start_1', type: 'custom', position: { x: 100, y: 150 }, data: { node_type: 'start' } },
    { id: 'end_1', type: 'custom', position: { x: 800, y: 150 }, data: { node_type: 'end' } },
  ];
  const dummyEdges: Edge[] = [];

  const { nodes, edges } = applyActionsToFlow(dummyNodes, dummyEdges, actions, {
    ...options,
    applyMode: 'replace',
  });

  const scriptNodes: ScriptNode[] = nodes.map((n) => {
    const { node_type, ...restData } = (n.data as Record<string, unknown>) ?? {};
    return {
      id: n.id,
      type: (node_type as ScriptNodeType) ?? 'start',
      position: n.position,
      data: restData,
    };
  });

  const scriptEdges: ScriptEdge[] = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? undefined,
    label: (e.label as string) ?? undefined,
  }));

  return { nodes: scriptNodes, edges: scriptEdges };
}
