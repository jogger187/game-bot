// 自訂 React Flow 節點元件 — 根據節點類型顯示不同外觀
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Box, Typography } from '@mui/material';
import { NODE_MODULES } from '../types/script';

/** 取得模塊定義 */
const getModuleDef = (nodeType: string) =>
  NODE_MODULES.find((m) => m.type === nodeType);

/** 取得節點摘要文字 */
const getSummary = (nodeType: string, data: Record<string, unknown>): string => {
  switch (nodeType) {
    case 'click': {
      const mode = data.mode as string;
      if (mode === 'coordinate') return `(${data.x}, ${data.y})`;
      if (mode === 'match_center' || mode === 'match_random') return `${data.template || '未設定'}`;
      return '';
    }
    case 'find_image':
    case 'wait_image':
      return (data.template as string) || '未設定模板';
    case 'if_else': {
      const ct = data.condition_type as string;
      if (ct === 'image_found') return `找到 ${data.template || '?'}`;
      if (ct === 'image_not_found') return `找不到 ${data.template || '?'}`;
      if (ct === 'ocr_contains') return `文字含 "${data.ocr_text || ''}"`;
      if (ct === 'variable_equals') return `${data.variable} == ${data.compare_value}`;
      if (ct === 'always_true') return '永遠為真';
      return ct;
    }
    case 'loop': {
      const mode = data.mode as string;
      if (mode === 'count') return `重複 ${data.count} 次`;
      if (mode === 'infinite') return '無限迴圈';
      return `While ${data.template || ''}`;
    }
    case 'sleep':
      return `${data.duration}s`;
    case 'random_delay':
      return `${data.min_seconds}~${data.max_seconds}s`;
    case 'swipe':
      return `(${data.from_x},${data.from_y}) → (${data.to_x},${data.to_y})`;
    case 'input_text':
      return `"${(data.text as string)?.slice(0, 15) || ''}"`;
    case 'key_press':
      return `${data.key}`;
    case 'set_variable':
      return `${data.variable} = ${data.value}`;
    case 'log':
      return `${(data.message as string)?.slice(0, 20) || ''}`;
    case 'ocr_text':
      return `→ $${data.variable}`;
    case 'pixel_check':
      return `(${data.x},${data.y}) ${data.expected_color}`;
    default:
      return '';
  }
};

/** 自訂節點元件 */
const ScriptNodeComponent = memo(({ data, selected }: NodeProps) => {
  const nodeType = (data.node_type as string) || 'start';
  const moduleDef = getModuleDef(nodeType);
  const icon = moduleDef?.icon || '⬜';
  const label = moduleDef?.label || nodeType;
  const color = moduleDef?.color || '#334155';
  const summary = getSummary(nodeType, data as Record<string, unknown>);
  const isIfElse = nodeType === 'if_else';
  const isLoop = nodeType === 'loop';
  const isStart = nodeType === 'start';
  const isEnd = nodeType === 'end';

  return (
    <Box
      sx={{
        background: color,
        border: selected ? '2px solid #818cf8' : '1px solid #475569',
        borderRadius: '8px',
        minWidth: 160,
        maxWidth: 220,
        boxShadow: selected ? '0 0 12px rgba(129,140,248,0.4)' : 'none',
        transition: 'box-shadow 0.2s',
      }}
    >
      {/* 輸入連接點（非 start 節點才有） */}
      {!isStart && (
        <Handle type="target" position={Position.Top} style={{ background: '#818cf8', width: 10, height: 10 }} />
      )}

      {/* 節點內容 */}
      <Box sx={{ px: 1.5, py: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography sx={{ fontSize: 18, lineHeight: 1 }}>{icon}</Typography>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ color: '#fff', fontWeight: 'bold', fontSize: 12, lineHeight: 1.2 }}>
            {label}
          </Typography>
          {summary && (
            <Typography sx={{ color: 'rgba(255,255,255,0.65)', fontSize: 10, lineHeight: 1.3, mt: 0.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {summary}
            </Typography>
          )}
        </Box>
      </Box>

      {/* 輸出連接點 */}
      {isIfElse ? (
        <>
          {/* 條件分支：True 和 False 輸出 */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1.5, pb: 0.5 }}>
            <Typography sx={{ color: '#4ade80', fontSize: 9, fontWeight: 'bold' }}>✓ True</Typography>
            <Typography sx={{ color: '#f87171', fontSize: 9, fontWeight: 'bold' }}>✗ False</Typography>
          </Box>
          <Handle type="source" position={Position.Bottom} id="true"
            style={{ background: '#4ade80', width: 10, height: 10, left: '30%' }} />
          <Handle type="source" position={Position.Bottom} id="false"
            style={{ background: '#f87171', width: 10, height: 10, left: '70%' }} />
        </>
      ) : isLoop ? (
        <>
          {/* 迴圈：Body 和 Done 輸出 */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 1.5, pb: 0.5 }}>
            <Typography sx={{ color: '#a78bfa', fontSize: 9, fontWeight: 'bold' }}>🔄 Body</Typography>
            <Typography sx={{ color: '#94a3b8', fontSize: 9, fontWeight: 'bold' }}>→ Done</Typography>
          </Box>
          <Handle type="source" position={Position.Bottom} id="body"
            style={{ background: '#a78bfa', width: 10, height: 10, left: '30%' }} />
          <Handle type="source" position={Position.Bottom} id="done"
            style={{ background: '#94a3b8', width: 10, height: 10, left: '70%' }} />
        </>
      ) : !isEnd ? (
        <Handle type="source" position={Position.Bottom} style={{ background: '#818cf8', width: 10, height: 10 }} />
      ) : null}
    </Box>
  );
});

ScriptNodeComponent.displayName = 'ScriptNodeComponent';

export default ScriptNodeComponent;
