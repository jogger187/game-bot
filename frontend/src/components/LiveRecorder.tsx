/**
 * 即時畫面串流 + 操作錄製元件
 *
 * 透過 WebSocket 接收後端 scrcpy 串流的 JPEG 畫面，
 * 攔截使用者點擊/滑動事件並注入裝置，同時支援錄製操作。
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import {
  Box, Paper, Typography, Button, IconButton, Chip, List,
  ListItem, ListItemText, ListItemSecondaryAction, Tooltip,
  Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Alert, Radio, RadioGroup, FormControlLabel, FormControl,
  FormLabel, Divider, CircularProgress,
} from '@mui/material';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import StopIcon from '@mui/icons-material/Stop';
import SaveIcon from '@mui/icons-material/Save';
import DeleteIcon from '@mui/icons-material/Delete';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import SwipeIcon from '@mui/icons-material/Swipe';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import type { RecordedAction, ConvertOptions, ApplyMode, DelayMode } from '../utils/recordConverter';

interface LiveRecorderProps {
  scriptId: string | null;
  selectedNodeId?: string | null;
  selectedNodeLabel?: string | null;
  onApplyToScript?: (options: ConvertOptions, actions: RecordedAction[]) => Promise<void>;
}

const WS_URL = 'ws://localhost:8765/ws/stream';

const LiveRecorder = ({
  scriptId,
  selectedNodeId,
  selectedNodeLabel,
  onApplyToScript,
}: LiveRecorderProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamSize, setStreamSize] = useState<{ w: number; h: number } | null>(null);
  const [recording, setRecording] = useState(false);
  const [actions, setActions] = useState<RecordedAction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState('');

  // 轉換為方塊對話框狀態
  const [applyOpen, setApplyOpen] = useState(false);
  const [applyMode, setApplyMode] = useState<ApplyMode>('insert_after');
  const [delayMode, setDelayMode] = useState<DelayMode>('random_delay');
  const [minDelayThreshold, setMinDelayThreshold] = useState<number>(0.3);
  const [randomRange, setRandomRange] = useState<number>(3);
  const [newScriptName, setNewScriptName] = useState<string>('');
  const [applying, setApplying] = useState(false);

  // 滑動追蹤
  const swipeStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const isDraggingRef = useRef(false);

  // ── WebSocket 連線 ──
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    // 建立隱藏的 Image 用於解碼 JPEG
    if (!imgRef.current) {
      imgRef.current = new Image();
    }

    ws.onopen = () => {
      setConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary: JPEG frame
        const blob = new Blob([event.data], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        const img = imgRef.current!;
        img.onload = () => {
          const canvas = canvasRef.current;
          if (canvas) {
            // 自動適配 canvas 大小
            if (canvas.width !== img.width || canvas.height !== img.height) {
              canvas.width = img.width;
              canvas.height = img.height;
            }
            const ctx = canvas.getContext('2d');
            ctx?.drawImage(img, 0, 0);
          }
          URL.revokeObjectURL(url);
        };
        img.src = url;
      } else {
        // Text: JSON 控制訊息
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'stream_started') {
            setStreaming(true);
            setStreamSize({ w: data.width, h: data.height });
          } else if (data.type === 'stream_stopped') {
            setStreaming(false);
            setStreamSize(null);
          } else if (data.type === 'recording_status') {
            setRecording(data.recording);
            if (data.actions) {
              setActions(data.actions);
            }
          } else if (data.type === 'recording_saved') {
            setSaveOpen(false);
            setSaveName('');
          } else if (data.type === 'error') {
            setError(data.message);
          }
        } catch {
          // ignore
        }
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setStreaming(false);
    };

    ws.onerror = () => {
      setError('WebSocket 連線失敗');
      setConnected(false);
    };
  }, []);

  // 自動連線
  useEffect(() => {
    connectWs();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWs]);

  // ── WebSocket 訊息發送 ──
  const sendMsg = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  // ── 串流控制 ──
  const handleStartStream = () => sendMsg({ type: 'start_stream' });
  const handleStopStream = () => sendMsg({ type: 'stop_stream' });

  // ── 錄製控制 ──
  const handleStartRecording = () => {
    setActions([]);
    sendMsg({ type: 'start_recording' });
  };
  const handleStopRecording = () => sendMsg({ type: 'stop_recording' });
  const handleSaveRecording = () => {
    if (!saveName.trim()) return;
    sendMsg({
      type: 'save_recording',
      name: saveName.trim(),
      script_id: scriptId,
      actions,
    });
  };

  const handleClearActions = () => {
    setActions([]);
  };

  const handleOpenApplyDialog = () => {
    const defaultName = `錄製腳本_${new Date().toLocaleTimeString('zh-TW', { hour12: false })}`;
    setNewScriptName(defaultName);
    setApplyOpen(true);
  };

  const handleApply = async () => {
    if (!onApplyToScript || actions.length === 0) return;
    setApplying(true);
    try {
      await onApplyToScript(
        {
          applyMode,
          delayMode,
          minDelayThreshold,
          randomRange,
          targetNodeId: selectedNodeId,
          newScriptName: newScriptName.trim(),
        },
        actions,
      );
      setApplyOpen(false);
    } catch (e) {
      setError(`套用失敗: ${e}`);
    } finally {
      setApplying(false);
    }
  };

  // ── 計算實際裝置座標 ──
  const getDeviceCoords = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !streamSize) return null;

    const rect = canvas.getBoundingClientRect();
    const imageAspectRatio = canvas.width / canvas.height;
    const rectAspectRatio = rect.width / rect.height;

    let renderWidth, renderHeight, offsetX = 0, offsetY = 0;

    // 計算 object-fit: contain 造成的實際繪製區域與黑邊
    if (imageAspectRatio > rectAspectRatio) {
      renderWidth = rect.width;
      renderHeight = rect.width / imageAspectRatio;
      offsetY = (rect.height - renderHeight) / 2;
    } else {
      renderHeight = rect.height;
      renderWidth = rect.height * imageAspectRatio;
      offsetX = (rect.width - renderWidth) / 2;
    }

    const scaleX = canvas.width / renderWidth;
    const scaleY = canvas.height / renderHeight;

    const x = Math.round((e.clientX - rect.left - offsetX) * scaleX);
    const y = Math.round((e.clientY - rect.top - offsetY) * scaleY);
    
    // 如果點擊在黑邊上，則忽略
    if (x < 0 || x > canvas.width || y < 0 || y > canvas.height) return null;
    
    return { x, y };
  }, [streamSize]);

  // ── 滑鼠事件 → 點擊 / 滑動 ──
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const coords = getDeviceCoords(e);
    if (!coords) return;
    swipeStartRef.current = { ...coords, time: Date.now() };
    isDraggingRef.current = false;
  }, [getDeviceCoords]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!swipeStartRef.current) return;
    const coords = getDeviceCoords(e);
    if (!coords) return;

    const dx = Math.abs(coords.x - swipeStartRef.current.x);
    const dy = Math.abs(coords.y - swipeStartRef.current.y);
    if (dx > 10 || dy > 10) {
      isDraggingRef.current = true;
    }
  }, [getDeviceCoords]);

  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!swipeStartRef.current) return;
    const coords = getDeviceCoords(e);
    if (!coords) return;

    if (isDraggingRef.current) {
      // 滑動
      const duration = Math.max(100, Math.min(2000, Date.now() - swipeStartRef.current.time));
      sendMsg({
        type: 'swipe',
        from_x: swipeStartRef.current.x,
        from_y: swipeStartRef.current.y,
        to_x: coords.x,
        to_y: coords.y,
        duration,
      });
    } else {
      // 點擊
      sendMsg({ type: 'tap', x: coords.x, y: coords.y });
    }

    swipeStartRef.current = null;
    isDraggingRef.current = false;
  }, [getDeviceCoords, sendMsg]);

  // ── 刪除錄製動作 ──
  const handleDeleteAction = (index: number) => {
    setActions((prev) => prev.filter((_, i) => i !== index));
  };

  // ── 格式化操作名稱 ──
  const formatAction = (a: RecordedAction) => {
    if (a.action === 'tap') return `👆 點擊 (${a.x}, ${a.y})`;
    if (a.action === 'swipe') return `👉 滑動 (${a.from_x},${a.from_y}) → (${a.to_x},${a.to_y})`;
    return `❓ ${a.action}`;
  };

  return (
    <Box sx={{ display: 'flex', height: '100%', gap: 0 }}>
      {/* ══════ 左側：畫面串流 ══════ */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* 頂部工具列 */}
        <Paper
          sx={{
            px: 2, py: 1, borderRadius: 0,
            display: 'flex', alignItems: 'center', gap: 1,
            borderBottom: '1px solid', borderColor: 'divider',
          }}
        >
          {!streaming ? (
            <Button
              size="small" variant="contained" color="primary"
              startIcon={<PlayArrowIcon />}
              onClick={handleStartStream}
              disabled={!connected}
            >
              啟動串流
            </Button>
          ) : (
            <Button
              size="small" variant="outlined" color="error"
              startIcon={<StopIcon />}
              onClick={handleStopStream}
            >
              停止串流
            </Button>
          )}

          <Box sx={{ flex: 1 }} />

          {streaming && !recording && (
            <Button
              size="small" variant="contained" color="error"
              startIcon={<FiberManualRecordIcon />}
              onClick={handleStartRecording}
              sx={{ animation: 'none' }}
            >
              開始錄製
            </Button>
          )}

          {recording && (
            <>
              <Chip
                icon={<FiberManualRecordIcon sx={{ fontSize: 12, color: '#ef4444 !important' }} />}
                label={`錄製中 (${actions.length} 步)`}
                size="small"
                sx={{
                  bgcolor: 'rgba(239,68,68,0.15)',
                  color: '#ef4444',
                  animation: 'pulse 1.5s infinite',
                  '@keyframes pulse': {
                    '0%, 100%': { opacity: 1 },
                    '50%': { opacity: 0.6 },
                  },
                }}
              />
              <Button
                size="small" variant="contained" color="warning"
                startIcon={<StopIcon />}
                onClick={handleStopRecording}
              >
                停止錄製
              </Button>
            </>
          )}

          {!recording && actions.length > 0 && (
            <>
              <Button
                size="small" variant="contained"
                startIcon={<AutoFixHighIcon />}
                onClick={handleOpenApplyDialog}
                sx={{
                  background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                  color: '#fff',
                  fontWeight: 600,
                  '&:hover': {
                    background: 'linear-gradient(135deg, #4338ca 0%, #6d28d9 100%)',
                  },
                }}
              >
                轉為方塊 ({actions.length} 步)
              </Button>
              <Button
                size="small" variant="outlined" color="success"
                startIcon={<SaveIcon />}
                onClick={() => setSaveOpen(true)}
              >
                儲存記錄
              </Button>
            </>
          )}

          {/* 連線狀態 */}
          <Chip
            size="small"
            label={connected ? (streaming ? '串流中' : '已連線') : '未連線'}
            color={connected ? (streaming ? 'success' : 'default') : 'error'}
            variant="outlined"
            sx={{ fontSize: 11 }}
          />
        </Paper>

        {/* 畫面區域 */}
        <Box
          sx={{
            flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
            bgcolor: '#0a0e1a', overflow: 'hidden', position: 'relative',
          }}
        >
          {error && (
            <Alert severity="error" sx={{ position: 'absolute', top: 12, left: 12, right: 12, zIndex: 10 }}>
              {error}
            </Alert>
          )}

          {streaming ? (
            <canvas
              ref={canvasRef}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              style={{
                maxWidth: '100%',
                maxHeight: '100%',
                objectFit: 'contain',
                cursor: recording ? 'crosshair' : 'pointer',
                imageRendering: 'auto',
              }}
            />
          ) : (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h6" color="text.secondary" gutterBottom>
                📹 即時錄製
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {connected
                  ? '點擊「啟動串流」開始即時畫面'
                  : '正在連線 WebSocket...'}
              </Typography>
              {streamSize && (
                <Typography variant="caption" color="text.secondary">
                  裝置解析度: {streamSize.w} × {streamSize.h}
                </Typography>
              )}
            </Box>
          )}
        </Box>
      </Box>

      {/* ══════ 右側：操作清單 ══════ */}
      <Paper
        sx={{
          width: 280, borderRadius: 0,
          borderLeft: '1px solid', borderColor: 'divider',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        <Box sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
            📋 操作清單 {actions.length > 0 && `(${actions.length})`}
          </Typography>
          {actions.length > 0 && !recording && (
            <Tooltip title="清空操作清單" arrow>
              <IconButton size="small" color="error" onClick={handleClearActions}>
                <DeleteSweepIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        <List dense sx={{ flex: 1, overflow: 'auto', py: 0 }}>
          {actions.length === 0 ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="body2" color="text.secondary">
                {recording ? '在左側畫面上操作...' : '尚無錄製操作'}
              </Typography>
            </Box>
          ) : (
            actions.map((action, index) => (
              <ListItem key={index} sx={{ py: 0.3, px: 1.5 }}>
                <Tooltip title={action.action === 'tap' ? '點擊' : '滑動'} arrow>
                  <Box sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                    {action.action === 'tap' ? (
                      <TouchAppIcon sx={{ fontSize: 16, color: '#f59e0b' }} />
                    ) : (
                      <SwipeIcon sx={{ fontSize: 16, color: '#3b82f6' }} />
                    )}
                  </Box>
                </Tooltip>
                <ListItemText
                  primary={formatAction(action)}
                  secondary={`${action.time.toFixed(2)}s`}
                  slotProps={{
                    primary: { sx: { fontSize: 12 } },
                    secondary: { sx: { fontSize: 10 } },
                  }}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end" size="small"
                    onClick={() => handleDeleteAction(index)}
                  >
                    <DeleteIcon sx={{ fontSize: 14 }} />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))
          )}
        </List>
      </Paper>

      {/* 儲存對話框 (純存 DB 歷史) */}
      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)}>
        <DialogTitle>💾 儲存錄製記錄</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus fullWidth label="錄製名稱"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            sx={{ mt: 1 }}
            onKeyDown={(e) => e.key === 'Enter' && handleSaveRecording()}
            placeholder="例：自動刷副本"
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            共 {actions.length} 個操作，將儲存至後端資料庫
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleSaveRecording} disabled={!saveName.trim()}>
            儲存
          </Button>
        </DialogActions>
      </Dialog>

      {/* 轉為方塊對話框 */}
      <Dialog open={applyOpen} onClose={() => !applying && setApplyOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
          <AutoFixHighIcon color="primary" /> 解析錄製結果並轉為流程方塊
        </DialogTitle>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            {/* 套用方式 */}
            <FormControl component="fieldset">
              <FormLabel component="legend" sx={{ fontWeight: 'bold', mb: 1, fontSize: 14 }}>
                1. 套用目標
              </FormLabel>
              <RadioGroup
                value={applyMode}
                onChange={(e) => setApplyMode(e.target.value as ApplyMode)}
              >
                <FormControlLabel
                  value="insert_after"
                  control={<Radio size="small" />}
                  label={
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        插入於節點後
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {selectedNodeId
                          ? `將插入在目前選取的節點 [${selectedNodeLabel || selectedNodeId}] 之後，自動重連邊線`
                          : '目前未選取節點，將預設接在 Start 起點節點之後'}
                      </Typography>
                    </Box>
                  }
                  sx={{ mb: 1 }}
                />
                <FormControlLabel
                  value="replace"
                  control={<Radio size="small" color="warning" />}
                  label={
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 'bold', color: '#f59e0b' }}>
                        覆蓋當前腳本 (取代整張圖)
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        保留 Start/End 起止節點，清空中間所有方塊並改為此次錄製流程
                      </Typography>
                    </Box>
                  }
                  sx={{ mb: 1 }}
                />
                <FormControlLabel
                  value="new_script"
                  control={<Radio size="small" />}
                  label={
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        另存為全新腳本
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        不改動當前腳本，直接建立一個全新腳本並切換
                      </Typography>
                    </Box>
                  }
                />
              </RadioGroup>
            </FormControl>

            {applyMode === 'new_script' && (
              <TextField
                size="small"
                fullWidth
                label="新腳本名稱"
                value={newScriptName}
                onChange={(e) => setNewScriptName(e.target.value)}
                placeholder="輸入新腳本名稱"
              />
            )}

            <Divider />

            {/* 延遲處理 */}
            <FormControl component="fieldset">
              <FormLabel component="legend" sx={{ fontWeight: 'bold', mb: 1, fontSize: 14 }}>
                2. 動作間隔延遲處理
              </FormLabel>
              <RadioGroup
                value={delayMode}
                onChange={(e) => setDelayMode(e.target.value as DelayMode)}
              >
                <FormControlLabel
                  value="random_delay"
                  control={<Radio size="small" />}
                  label={
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        🎲 隨機延遲 (推薦，防偵測防封號)
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        依實際操作間隔自動浮動 ±20%，產生 random_delay 節點
                      </Typography>
                    </Box>
                  }
                  sx={{ mb: 0.5 }}
                />
                <FormControlLabel
                  value="sleep"
                  control={<Radio size="small" />}
                  label={
                    <Box>
                      <Typography variant="body2">
                        ⏱️ 固定延遲 (產生 sleep 節點)
                      </Typography>
                    </Box>
                  }
                  sx={{ mb: 0.5 }}
                />
                <FormControlLabel
                  value="none"
                  control={<Radio size="small" />}
                  label={<Typography variant="body2">🚫 不加延遲 (連續快速執行)</Typography>}
                />
              </RadioGroup>
            </FormControl>

            {delayMode !== 'none' && (
              <Box sx={{ display: 'flex', gap: 2 }}>
                <TextField
                  size="small"
                  type="number"
                  label="最小延遲門檻 (秒)"
                  value={minDelayThreshold}
                  onChange={(e) => setMinDelayThreshold(Math.max(0.1, Number(e.target.value)))}
                  helperText="小於此秒數的操作間隔將被視為連續操作，不插入等待"
                  slotProps={{ htmlInput: { min: 0.1, step: 0.1 } }}
                  sx={{ flex: 1 }}
                />
                <TextField
                  size="small"
                  type="number"
                  label="點擊隨機偏移 (px)"
                  value={randomRange}
                  onChange={(e) => setRandomRange(Math.max(0, Number(e.target.value)))}
                  helperText="點擊時隨機偏移像素範圍 (防座標檢測)"
                  slotProps={{ htmlInput: { min: 0, max: 20 } }}
                  sx={{ flex: 1 }}
                />
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setApplyOpen(false)} disabled={applying}>
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleApply}
            disabled={applying || (applyMode === 'new_script' && !newScriptName.trim())}
            startIcon={applying ? <CircularProgress size={16} color="inherit" /> : <AutoFixHighIcon />}
            sx={{
              background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            }}
          >
            {applying ? '轉換中...' : `確認轉換 (${actions.length} 步)`}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default LiveRecorder;
