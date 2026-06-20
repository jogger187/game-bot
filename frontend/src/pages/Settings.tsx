// 系統設定頁面
import { useState, useCallback } from 'react';
import {
  Box, Typography, Paper, TextField, FormControl, InputLabel, Select,
  MenuItem, Button, Divider, Switch, FormControlLabel, Chip,
  List, ListItemButton, ListItemText, ListItemIcon,
  Dialog, DialogTitle, DialogContent, CircularProgress, Alert,
  Collapse, IconButton, Tooltip,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import DesktopWindowsIcon from '@mui/icons-material/DesktopWindows';
import RefreshIcon from '@mui/icons-material/Refresh';
import LinkIcon from '@mui/icons-material/Link';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import AdsClickIcon from '@mui/icons-material/AdsClick';
import { useAppStore } from '../stores/appStore';
import * as api from '../utils/tauri';
import type { DesktopWindow } from '../utils/tauri';

const Settings = () => {
  const { device, addLog } = useAppStore();
  const [serial, setSerial] = useState(device?.serial ?? '127.0.0.1:5555');
  const [capMode, setCapMode] = useState(device?.mode ?? 'adb');
  const [emulator, setEmulator] = useState(device?.emulator_type ?? 'auto');
  const [antiDetect, setAntiDetect] = useState(true);
  const [randomDelay, setRandomDelay] = useState(true);

  // 桌面視窗選擇
  const [windowPickerOpen, setWindowPickerOpen] = useState(false);
  const [windowsList, setWindowsList] = useState<DesktopWindow[]>([]);
  const [loadingWindows, setLoadingWindows] = useState(false);
  const [selectedWindow, setSelectedWindow] = useState<DesktopWindow | null>(null);
  const [connectingWindow, setConnectingWindow] = useState(false);
  const [pickingWindow, setPickingWindow] = useState(false);
  const [windowSearch, setWindowSearch] = useState('');

  const filteredWindows = windowsList.filter(w =>
    w.owner_name.toLowerCase().includes(windowSearch.toLowerCase()) ||
    w.window_name.toLowerCase().includes(windowSearch.toLowerCase())
  );

  // 載入桌面視窗列表
  const loadWindows = useCallback(async () => {
    setLoadingWindows(true);
    try {
      const windows = await api.desktopListWindows();
      setWindowsList(windows);
    } catch (e) {
      addLog(`❌ 無法列舉桌面視窗: ${e}`);
      setWindowsList([]);
    } finally {
      setLoadingWindows(false);
    }
  }, [addLog]);

  // 連線到桌面視窗
  const connectDesktopWindow = useCallback(async (win: DesktopWindow) => {
    setConnectingWindow(true);
    try {
      await api.desktopConnect({ window_id: win.window_id });
      setSelectedWindow(win);
      setWindowPickerOpen(false);
      addLog(`✅ 已連線桌面視窗: ${win.owner_name} - ${win.window_name}`);
    } catch (e) {
      addLog(`❌ 連線桌面視窗失敗: ${e}`);
    } finally {
      setConnectingWindow(false);
    }
  }, [addLog]);

  const handlePickWindow = async () => {
    setPickingWindow(true);
    addLog('請在 15 秒內點擊目標視窗...');
    try {
      const win = await api.desktopPickWindow();
      setWindowSearch(win.owner_name || win.window_name);
      addLog(`✅ 選取視窗: ${win.owner_name} - ${win.window_name} (${win.width}x${win.height})`);
      await connectDesktopWindow(win);
    } catch (e: unknown) {
      addLog(`❌ 選取失敗: ${(e as Error).message}`);
    } finally {
      setPickingWindow(false);
    }
  };

  // 開啟視窗選擇器
  const openWindowPicker = () => {
    setWindowPickerOpen(true);
    loadWindows();
  };

  const handleSave = () => {
    addLog('💾 設定已儲存');
  };

  return (
    <Box sx={{ p: 4, overflow: 'auto', height: '100%', maxWidth: 700 }}>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 'bold' }}>⚙️ 系統設定</Typography>

      {/* 裝置設定 */}
      <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ mb: 2 }}>📱 裝置設定</Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <FormControl size="small">
            <InputLabel>截圖方式</InputLabel>
            <Select value={capMode} onChange={(e) => setCapMode(e.target.value)} label="截圖方式">
              <MenuItem value="adb">ADB screencap</MenuItem>
              <MenuItem value="minicap">Minicap（高效能）</MenuItem>
              <MenuItem value="emulator">模擬器 API</MenuItem>
              <MenuItem value="desktop">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <DesktopWindowsIcon fontSize="small" />
                  桌面應用擷取
                </Box>
              </MenuItem>
            </Select>
          </FormControl>

          {/* ADB 模式設定 */}
          <Collapse in={capMode !== 'desktop'}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField label="裝置序列號" value={serial} onChange={(e) => setSerial(e.target.value)}
                size="small" helperText="模擬器預設 127.0.0.1:5555" />
              <FormControl size="small">
                <InputLabel>模擬器類型</InputLabel>
                <Select value={emulator} onChange={(e) => setEmulator(e.target.value)} label="模擬器類型">
                  <MenuItem value="auto">自動偵測</MenuItem>
                  <MenuItem value="mumu">MuMu</MenuItem>
                  <MenuItem value="ldplayer">雷電</MenuItem>
                  <MenuItem value="bluestacks">BlueStacks</MenuItem>
                  <MenuItem value="nox">夜神</MenuItem>
                </Select>
              </FormControl>
            </Box>
          </Collapse>

          {/* 桌面模式設定 */}
          <Collapse in={capMode === 'desktop'}>
            <Paper
              variant="outlined"
              sx={{
                p: 2,
                bgcolor: 'rgba(99, 102, 241, 0.04)',
                borderColor: 'rgba(99, 102, 241, 0.2)',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <DesktopWindowsIcon sx={{ color: '#6366f1' }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                    桌面視窗擷取
                  </Typography>
                </Box>
                <Chip
                  label={selectedWindow ? '已連線' : '未連線'}
                  size="small"
                  color={selectedWindow ? 'success' : 'default'}
                  variant="outlined"
                />
              </Box>

              {selectedWindow && (
                <Paper
                  sx={{
                    p: 1.5, mb: 2, bgcolor: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: 1,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <CheckCircleIcon sx={{ color: '#10b981', fontSize: 18 }} />
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {selectedWindow.owner_name}
                    </Typography>
                    {selectedWindow.window_name && (
                      <Typography variant="caption" color="text.secondary">
                        — {selectedWindow.window_name}
                      </Typography>
                    )}
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 3.5 }}>
                    {selectedWindow.width}×{selectedWindow.height} · PID {selectedWindow.pid} · ID {selectedWindow.window_id}
                  </Typography>
                </Paper>
              )}

              <Button
                variant={selectedWindow ? 'outlined' : 'contained'}
                size="small"
                startIcon={<LinkIcon />}
                onClick={openWindowPicker}
                fullWidth
              >
                {selectedWindow ? '切換視窗' : '選擇目標視窗'}
              </Button>

              <Alert severity="info" sx={{ mt: 2, fontSize: 12 }}>
                macOS 需在「系統設定 → 隱私與安全性 → 螢幕錄製」中授權此應用，否則截圖將為空白。
              </Alert>
            </Paper>
          </Collapse>
        </Box>
      </Paper>

      {/* 防偵測設定 */}
      <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ mb: 2 }}>🛡️ 防偵測設定</Typography>
        <FormControlLabel control={<Switch checked={antiDetect} onChange={(_, v) => setAntiDetect(v)} />}
          label="啟用防偵測模式" />
        <FormControlLabel control={<Switch checked={randomDelay} onChange={(_, v) => setRandomDelay(v)} />}
          label="隨機延遲點擊" />
      </Paper>

      <Divider sx={{ my: 2 }} />

      <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave}>儲存設定</Button>

      {/* 桌面視窗選擇對話框 */}
      <Dialog
        open={windowPickerOpen}
        onClose={() => setWindowPickerOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: { bgcolor: 'background.paper', maxHeight: '70vh' },
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <DesktopWindowsIcon sx={{ color: '#6366f1' }} />
            選擇目標視窗
          </Box>
          <Box>
            <Button size="small" startIcon={<AdsClickIcon />} onClick={handlePickWindow} disabled={pickingWindow || loadingWindows} sx={{ mr: 1 }}>
              點擊選取視窗
            </Button>
            <Tooltip title="重新掃描">
              <IconButton size="small" onClick={loadWindows} disabled={loadingWindows}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          {loadingWindows ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : windowsList.length === 0 ? (
            <Box sx={{ textAlign: 'center', p: 4 }}>
              <Typography color="text.secondary">找不到可用視窗</Typography>
              <Typography variant="caption" color="text.secondary">
                請確認目標應用已開啟，且已授權螢幕錄製權限
              </Typography>
            </Box>
          ) : (
            <Box sx={{ px: 2, pb: 2 }}>
              <TextField
                fullWidth
                size="small"
                placeholder="搜尋應用程式名稱..."
                value={windowSearch}
                onChange={(e) => setWindowSearch(e.target.value)}
                sx={{ mb: 2, mt: 1 }}
              />
              <List sx={{ p: 0 }}>
                {filteredWindows.length === 0 ? (
                  <Typography color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                    沒有符合的視窗
                  </Typography>
                ) : (
                  filteredWindows.map((win) => (
                    <ListItemButton
                  key={win.window_id}
                  onClick={() => connectDesktopWindow(win)}
                  disabled={connectingWindow}
                  sx={{
                    border: '1px solid',
                    borderColor: selectedWindow?.window_id === win.window_id ? 'primary.main' : 'divider',
                    borderRadius: 1,
                    mb: 1,
                    bgcolor: selectedWindow?.window_id === win.window_id ? 'rgba(99,102,241,0.08)' : 'transparent',
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: 'rgba(99,102,241,0.06)',
                    },
                  }}
                >
                  <ListItemIcon>
                    <DesktopWindowsIcon sx={{ color: '#6366f1' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {win.owner_name}
                        </Typography>
                        {win.window_name && (
                          <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 200 }}>
                            — {win.window_name}
                          </Typography>
                        )}
                      </Box>
                    }
                    secondary={`${win.width}×${win.height} · PID ${win.pid}`}
                  />
                  <Chip
                    label={`ID ${win.window_id}`}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: 10 }}
                  />
                </ListItemButton>
                  ))
                )}
              </List>
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default Settings;
