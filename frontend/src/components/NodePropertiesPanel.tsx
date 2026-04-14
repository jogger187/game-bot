// 節點屬性面板 — 選取節點後在右側顯示可編輯的屬性
import {
  Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel,
  Switch, FormControlLabel, Divider,
} from '@mui/material';
import { NODE_MODULES, type ScriptNodeType } from '../types/script';
import { useAppStore } from '../stores/appStore';

interface Props {
  nodeType: ScriptNodeType;
  data: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

/** 可用資源列表下拉選擇器 */
const TemplateSelect = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => {
  const { assets } = useAppStore();
  return (
    <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
      <InputLabel>模板圖片</InputLabel>
      <Select value={value || ''} label="模板圖片" onChange={(e) => onChange(e.target.value)}>
        <MenuItem value="">（未選擇）</MenuItem>
        {assets.map((a) => (
          <MenuItem key={a.name} value={a.name}>{a.name}</MenuItem>
        ))}
      </Select>
    </FormControl>
  );
};

/** 數字輸入 */
const NumberField = ({ label, value, onChange, min, max, step }: {
  label: string; value: number; onChange: (v: number) => void;
  min?: number; max?: number; step?: number;
}) => (
  <TextField fullWidth size="small" type="number" label={label} value={value ?? 0}
    onChange={(e) => onChange(Number(e.target.value))}
    slotProps={{ htmlInput: { min, max, step: step ?? 1 } }}
    sx={{ mb: 1.5 }} />
);

const NodePropertiesPanel = ({ nodeType, data, onChange }: Props) => {
  const moduleDef = NODE_MODULES.find((m) => m.type === nodeType);
  if (!moduleDef) return null;

  const renderFields = () => {
    switch (nodeType) {
      // ═══ 點擊 ═══
      case 'click':
        return (
          <>
            <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
              <InputLabel>點擊模式</InputLabel>
              <Select value={data.mode || 'coordinate'} label="點擊模式"
                onChange={(e) => onChange('mode', e.target.value)}>
                <MenuItem value="coordinate">指定座標</MenuItem>
                <MenuItem value="match_center">匹配圖片中心</MenuItem>
                <MenuItem value="match_random">匹配圖片 (隨機偏移)</MenuItem>
              </Select>
            </FormControl>
            {data.mode === 'coordinate' ? (
              <Box sx={{ display: 'flex', gap: 1 }}>
                <NumberField label="X" value={data.x as number} onChange={(v) => onChange('x', v)} min={0} />
                <NumberField label="Y" value={data.y as number} onChange={(v) => onChange('y', v)} min={0} />
              </Box>
            ) : (
              <>
                <TemplateSelect value={data.template as string} onChange={(v) => onChange('template', v)} />
                <NumberField label="信心度" value={data.threshold as number} onChange={(v) => onChange('threshold', v)} min={0} max={1} step={0.05} />
              </>
            )}
            <NumberField label="隨機偏移 (px)" value={data.random_range as number} onChange={(v) => onChange('random_range', v)} min={0} />
            <NumberField label="長按 (ms, 0=普通)" value={data.hold_ms as number} onChange={(v) => onChange('hold_ms', v)} min={0} />
            <Box sx={{ display: 'flex', gap: 1 }}>
              <NumberField label="重複次數" value={data.repeat as number} onChange={(v) => onChange('repeat', v)} min={1} />
              <NumberField label="重複間隔 (ms)" value={data.repeat_interval as number} onChange={(v) => onChange('repeat_interval', v)} min={50} />
            </Box>
          </>
        );

      // ═══ 找圖 ═══
      case 'find_image':
        return (
          <>
            <TemplateSelect value={data.template as string} onChange={(v) => onChange('template', v)} />
            <NumberField label="信心度" value={data.threshold as number} onChange={(v) => onChange('threshold', v)} min={0} max={1} step={0.05} />
            <NumberField label="超時 (秒)" value={data.timeout as number} onChange={(v) => onChange('timeout', v)} min={0} />
            <TextField fullWidth size="small" label="結果存入變數" value={data.variable || ''}
              onChange={(e) => onChange('variable', e.target.value)} sx={{ mb: 1.5 }} />
          </>
        );

      // ═══ 等待圖片 ═══
      case 'wait_image':
        return (
          <>
            <TemplateSelect value={data.template as string} onChange={(v) => onChange('template', v)} />
            <NumberField label="信心度" value={data.threshold as number} onChange={(v) => onChange('threshold', v)} min={0} max={1} step={0.05} />
            <NumberField label="最長等待 (秒)" value={data.timeout as number} onChange={(v) => onChange('timeout', v)} min={1} />
            <NumberField label="重試間隔 (秒)" value={data.interval as number} onChange={(v) => onChange('interval', v)} min={0.5} step={0.5} />
          </>
        );

      // ═══ 條件分支 ═══
      case 'if_else':
        return (
          <>
            <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
              <InputLabel>條件類型</InputLabel>
              <Select value={data.condition_type || 'image_found'} label="條件類型"
                onChange={(e) => onChange('condition_type', e.target.value)}>
                <MenuItem value="image_found">🔍 找到圖片</MenuItem>
                <MenuItem value="image_not_found">🚫 找不到圖片</MenuItem>
                <MenuItem value="ocr_contains">📖 OCR 文字包含</MenuItem>
                <MenuItem value="ocr_not_contains">📖 OCR 文字不包含</MenuItem>
                <MenuItem value="variable_equals">📦 變數等於</MenuItem>
                <MenuItem value="variable_gt">📦 變數大於</MenuItem>
                <MenuItem value="variable_lt">📦 變數小於</MenuItem>
                <MenuItem value="pixel_match">🎨 像素顏色匹配</MenuItem>
                <MenuItem value="always_true">✅ 永遠為真</MenuItem>
              </Select>
            </FormControl>
            {(data.condition_type === 'image_found' || data.condition_type === 'image_not_found') && (
              <>
                <TemplateSelect value={data.template as string} onChange={(v) => onChange('template', v)} />
                <NumberField label="信心度" value={data.threshold as number} onChange={(v) => onChange('threshold', v)} min={0} max={1} step={0.05} />
              </>
            )}
            {(data.condition_type === 'ocr_contains' || data.condition_type === 'ocr_not_contains') && (
              <TextField fullWidth size="small" label="比對文字" value={data.ocr_text || ''}
                onChange={(e) => onChange('ocr_text', e.target.value)} sx={{ mb: 1.5 }} />
            )}
            {(data.condition_type === 'variable_equals' || data.condition_type === 'variable_gt' || data.condition_type === 'variable_lt') && (
              <>
                <TextField fullWidth size="small" label="變數名" value={data.variable || ''}
                  onChange={(e) => onChange('variable', e.target.value)} sx={{ mb: 1.5 }} />
                <TextField fullWidth size="small" label="比較值" value={data.compare_value || ''}
                  onChange={(e) => onChange('compare_value', e.target.value)} sx={{ mb: 1.5 }} />
              </>
            )}
            {data.condition_type === 'pixel_match' && (
              <>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <NumberField label="X" value={data.pixel_x as number} onChange={(v) => onChange('pixel_x', v)} min={0} />
                  <NumberField label="Y" value={data.pixel_y as number} onChange={(v) => onChange('pixel_y', v)} min={0} />
                </Box>
                <TextField fullWidth size="small" label="顏色 (#RRGGBB)" value={data.pixel_color || '#000000'}
                  onChange={(e) => onChange('pixel_color', e.target.value)} sx={{ mb: 1.5 }} />
                <NumberField label="容差" value={data.pixel_tolerance as number} onChange={(v) => onChange('pixel_tolerance', v)} min={0} max={255} />
              </>
            )}
          </>
        );

      // ═══ 迴圈 ═══
      case 'loop':
        return (
          <>
            <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
              <InputLabel>迴圈模式</InputLabel>
              <Select value={data.mode || 'count'} label="迴圈模式"
                onChange={(e) => onChange('mode', e.target.value)}>
                <MenuItem value="count">重複 N 次</MenuItem>
                <MenuItem value="while_image">While 有圖片</MenuItem>
                <MenuItem value="while_no_image">While 沒有圖片</MenuItem>
                <MenuItem value="infinite">無限迴圈</MenuItem>
              </Select>
            </FormControl>
            {data.mode === 'count' && (
              <NumberField label="重複次數" value={data.count as number} onChange={(v) => onChange('count', v)} min={1} />
            )}
            {(data.mode === 'while_image' || data.mode === 'while_no_image') && (
              <TemplateSelect value={data.template as string} onChange={(v) => onChange('template', v)} />
            )}
            <NumberField label="安全上限" value={data.max_iterations as number} onChange={(v) => onChange('max_iterations', v)} min={1} />
          </>
        );

      // ═══ 等待 ═══
      case 'sleep':
        return (
          <>
            <NumberField label="等待秒數" value={data.duration as number} onChange={(v) => onChange('duration', v)} min={0} step={0.5} />
            <Divider sx={{ my: 1 }} />
            <Typography variant="caption" color="text.secondary">隨機範圍（0 = 不隨機）</Typography>
            <Box sx={{ display: 'flex', gap: 1, mt: 0.5 }}>
              <NumberField label="最小 (s)" value={data.random_min as number} onChange={(v) => onChange('random_min', v)} min={0} step={0.5} />
              <NumberField label="最大 (s)" value={data.random_max as number} onChange={(v) => onChange('random_max', v)} min={0} step={0.5} />
            </Box>
          </>
        );

      // ═══ 隨機延遲 ═══
      case 'random_delay':
        return (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <NumberField label="最小 (s)" value={data.min_seconds as number} onChange={(v) => onChange('min_seconds', v)} min={0} step={0.1} />
            <NumberField label="最大 (s)" value={data.max_seconds as number} onChange={(v) => onChange('max_seconds', v)} min={0} step={0.1} />
          </Box>
        );

      // ═══ 滑動 ═══
      case 'swipe':
        return (
          <>
            <Typography variant="caption" color="text.secondary">起點</Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <NumberField label="X" value={data.from_x as number} onChange={(v) => onChange('from_x', v)} min={0} />
              <NumberField label="Y" value={data.from_y as number} onChange={(v) => onChange('from_y', v)} min={0} />
            </Box>
            <Typography variant="caption" color="text.secondary">終點</Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <NumberField label="X" value={data.to_x as number} onChange={(v) => onChange('to_x', v)} min={0} />
              <NumberField label="Y" value={data.to_y as number} onChange={(v) => onChange('to_y', v)} min={0} />
            </Box>
            <NumberField label="持續時間 (ms)" value={data.duration as number} onChange={(v) => onChange('duration', v)} min={100} />
            <NumberField label="隨機偏移 (px)" value={data.random_range as number} onChange={(v) => onChange('random_range', v)} min={0} />
          </>
        );

      // ═══ 文字輸入 ═══
      case 'input_text':
        return (
          <>
            <TextField fullWidth size="small" label="輸入文字" value={data.text || ''} multiline rows={2}
              onChange={(e) => onChange('text', e.target.value)} sx={{ mb: 1.5 }} />
            <FormControlLabel control={<Switch checked={!!data.clear_first} onChange={(e) => onChange('clear_first', e.target.checked)} />}
              label="先清空輸入框" />
          </>
        );

      // ═══ 按鍵 ═══
      case 'key_press':
        return (
          <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
            <InputLabel>按鍵</InputLabel>
            <Select value={data.key || 'back'} label="按鍵" onChange={(e) => onChange('key', e.target.value)}>
              <MenuItem value="back">← 返回鍵</MenuItem>
              <MenuItem value="home">🏠 Home 鍵</MenuItem>
              <MenuItem value="recent">📱 最近任務</MenuItem>
              <MenuItem value="volume_up">🔊 音量+</MenuItem>
              <MenuItem value="volume_down">🔉 音量-</MenuItem>
              <MenuItem value="power">⚡ 電源鍵</MenuItem>
            </Select>
          </FormControl>
        );

      // ═══ 設定變數 ═══
      case 'set_variable':
        return (
          <>
            <TextField fullWidth size="small" label="變數名" value={data.variable || ''}
              onChange={(e) => onChange('variable', e.target.value)} sx={{ mb: 1.5 }} />
            <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
              <InputLabel>類型</InputLabel>
              <Select value={data.value_type || 'string'} label="類型" onChange={(e) => onChange('value_type', e.target.value)}>
                <MenuItem value="string">文字</MenuItem>
                <MenuItem value="number">數字</MenuItem>
                <MenuItem value="counter_increment">計數器 +1</MenuItem>
                <MenuItem value="counter_decrement">計數器 -1</MenuItem>
              </Select>
            </FormControl>
            {(data.value_type === 'string' || data.value_type === 'number') && (
              <TextField fullWidth size="small" label="值" value={data.value || ''}
                onChange={(e) => onChange('value', e.target.value)} sx={{ mb: 1.5 }} />
            )}
          </>
        );

      // ═══ 日誌 ═══
      case 'log':
        return (
          <>
            <TextField fullWidth size="small" label="訊息" value={data.message || ''} multiline rows={2}
              onChange={(e) => onChange('message', e.target.value)} sx={{ mb: 1.5 }} />
            <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
              <InputLabel>等級</InputLabel>
              <Select value={data.level || 'info'} label="等級" onChange={(e) => onChange('level', e.target.value)}>
                <MenuItem value="info">ℹ️ Info</MenuItem>
                <MenuItem value="warn">⚠️ Warn</MenuItem>
                <MenuItem value="error">❌ Error</MenuItem>
              </Select>
            </FormControl>
          </>
        );

      // ═══ OCR ═══
      case 'ocr_text':
        return (
          <>
            <FormControl fullWidth size="small" sx={{ mb: 1.5 }}>
              <InputLabel>語言</InputLabel>
              <Select value={data.language || 'chi_tra'} label="語言" onChange={(e) => onChange('language', e.target.value)}>
                <MenuItem value="chi_tra">繁體中文</MenuItem>
                <MenuItem value="chi_sim">簡體中文</MenuItem>
                <MenuItem value="eng">英文</MenuItem>
              </Select>
            </FormControl>
            <TextField fullWidth size="small" label="結果存入變數" value={data.variable || ''}
              onChange={(e) => onChange('variable', e.target.value)} sx={{ mb: 1.5 }} />
          </>
        );

      // ═══ 像素檢查 ═══
      case 'pixel_check':
        return (
          <>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <NumberField label="X" value={data.x as number} onChange={(v) => onChange('x', v)} min={0} />
              <NumberField label="Y" value={data.y as number} onChange={(v) => onChange('y', v)} min={0} />
            </Box>
            <TextField fullWidth size="small" label="預期顏色 (#RRGGBB)" value={data.expected_color || '#FFFFFF'}
              onChange={(e) => onChange('expected_color', e.target.value)} sx={{ mb: 1.5 }} />
            <NumberField label="容差" value={data.tolerance as number} onChange={(v) => onChange('tolerance', v)} min={0} max={255} />
            <TextField fullWidth size="small" label="結果存入變數" value={data.variable || ''}
              onChange={(e) => onChange('variable', e.target.value)} sx={{ mb: 1.5 }} />
          </>
        );

      default:
        return <Typography color="text.secondary" sx={{ fontSize: 12 }}>此節點無需設定</Typography>;
    }
  };

  return (
    <Box sx={{ p: 2, overflow: 'auto', height: '100%' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography sx={{ fontSize: 22 }}>{moduleDef.icon}</Typography>
        <Box>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>{moduleDef.label}</Typography>
          <Typography variant="caption" color="text.secondary">{moduleDef.description}</Typography>
        </Box>
      </Box>
      <Divider sx={{ mb: 2 }} />
      {renderFields()}
    </Box>
  );
};

export default NodePropertiesPanel;
