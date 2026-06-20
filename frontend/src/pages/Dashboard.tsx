// 儀表板頁面 — 裝置狀態總覽 + 裝置選擇器
import { useEffect, useState, useCallback } from 'react';
import {
  Box, Paper, Typography, Button, Grid, Card, CardContent, Chip,
  Dialog, DialogTitle, DialogContent, List, ListItemButton, ListItemText,
  ListItemIcon, CircularProgress, Tabs, Tab, TextField,
} from '@mui/material';
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import DescriptionIcon from '@mui/icons-material/Description';
import ImageIcon from '@mui/icons-material/Image';
import ComputerIcon from '@mui/icons-material/Computer';
import SmartphoneIcon from '@mui/icons-material/Smartphone';
import DesktopWindowsIcon from '@mui/icons-material/DesktopWindows';
import RefreshIcon from '@mui/icons-material/Refresh';
import AdsClickIcon from '@mui/icons-material/AdsClick';
import { useAppStore } from '../stores/appStore';
import * as api from '../utils/tauri';
import type { DesktopWindow } from '../utils/tauri';

interface AdbDevice {
  serial: string;
  status: string;
}

const Dashboard = () => {
  const { device, scripts, assets, tasks, logs, connectDevice, disconnectDevice, fetchDevice } = useAppStore();

  // 裝置選擇對話框
  const [pickerOpen, setPickerOpen] = useState(false);
  const [devicesList, setDevicesList] = useState<AdbDevice[]>([]);
  const [loadingDevices, setLoadingDevices] = useState(false);
  const [pickerTab, setPickerTab] = useState(0);  // 0=ADB, 1=Desktop
  const [windowsList, setWindowsList] = useState<DesktopWindow[]>([]);
  const [loadingWindows, setLoadingWindows] = useState(false);
  const [pickingWindow, setPickingWindow] = useState(false);
  const [windowSearch, setWindowSearch] = useState('');

  const filteredWindows = windowsList.filter(w =>
    w.owner_name.toLowerCase().includes(windowSearch.toLowerCase()) ||
    w.window_name.toLowerCase().includes(windowSearch.toLowerCase())
  );

  useEffect(() => { fetchDevice(); }, [fetchDevice]);

  const runningTasks = tasks.filter((t) => t.enabled && !t.completed).length;

  // 載入裝置列表
  const loadDevices = useCallback(async () => {
    setLoadingDevices(true);
    try {
      const result = await api.deviceList();
      setDevicesList(result.devices.filter((d) => d.status === 'device'));
    } catch {
      setDevicesList([]);
    } finally {
      setLoadingDevices(false);
    }
  }, []);

  // 載入桌面視窗列表
  const loadWindows = useCallback(async () => {
    setLoadingWindows(true);
    try {
      const windows = await api.desktopListWindows();
      setWindowsList(windows);
    } catch {
      setWindowsList([]);
    } finally {
      setLoadingWindows(false);
    }
  }, []);

  // 開啟裝置選擇器
  const openPicker = () => {
    setPickerOpen(true);
    loadDevices();
    loadWindows();
  };

  const handlePickWindow = async () => {
    setPickingWindow(true);
    addLog('請在 15 秒內點擊目標視窗...');
    try {
      const win = await api.desktopPickWindow();
      // 切換到桌面分頁，自動填入搜尋並選中
      setPickerTab(1);
      setWindowSearch(win.owner_name || win.window_name);
      addLog(`✅ 選取視窗: ${win.owner_name} - ${win.window_name} (${win.width}x${win.height})`);
      // 直接連線
      selectDesktopWindow(win);
    } catch (e: unknown) {
      addLog(`❌ 選取失敗: ${(e as Error).message}`);
    } finally {
      setPickingWindow(false);
    }
  };

  // 選擇裝置並連線
  const selectDevice = async (serial: string) => {
    setPickerOpen(false);
    await connectDevice(serial);
  };

  // 選擇桌面視窗並連線
  const selectDesktopWindow = async (win: DesktopWindow) => {
    setPickerOpen(false);
    try {
      await api.desktopConnect({ window_id: win.window_id });
      await fetchDevice();
    } catch {
      // fallback
      await connectDevice(`desktop:${win.window_id}`, 'desktop');
    }
  };

  // 判斷裝置類型圖標
  const getDeviceIcon = (serial: string) => {
    if (serial.startsWith('desktop:'))
      return <DesktopWindowsIcon sx={{ color: '#8b5cf6' }} />;
    if (serial.includes('emulator') || serial.includes('127.0.0.1') || serial.includes(':'))
      return <ComputerIcon sx={{ color: '#6366f1' }} />;
    return <SmartphoneIcon sx={{ color: '#10b981' }} />;
  };

  // 判斷裝置描述
  const getDeviceLabel = (serial: string) => {
    if (serial.startsWith('desktop:')) return '桌面應用擷取';
    if (serial.includes('emulator')) return '模擬器 (BlueStacks/Nox)';
    if (serial.includes('127.0.0.1') || serial.match(/:\d+$/)) return '模擬器 (TCP)';
    return '實體手機 (USB)';
  };

  return (
    <Box sx={{ p: 4, overflow: 'auto', height: '100%' }}>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 'bold' }}>
        📊 儀表板
      </Typography>

      {/* 統計卡片 */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {[
          { icon: <PhoneAndroidIcon />, label: '裝置狀態', value: device?.connected ? '已連線' : '未連線', color: device?.connected ? '#10b981' : '#ef4444' },
          { icon: <DescriptionIcon />, label: '腳本數量', value: `${scripts.length} 個`, color: '#6366f1' },
          { icon: <ImageIcon />, label: '模板資源', value: `${assets.length} 張`, color: '#f59e0b' },
          { icon: <PlayCircleIcon />, label: '執行中任務', value: `${runningTasks} 個`, color: '#10b981' },
        ].map((stat, i) => (
          <Grid size={{ xs: 12, sm: 6, md: 3 }} key={i}>
            <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ color: stat.color, fontSize: 40 }}>{stat.icon}</Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">{stat.label}</Typography>
                  <Typography variant="h6" sx={{ fontWeight: 'bold', color: stat.color }}>{stat.value}</Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* 裝置控制 */}
      <Paper sx={{ p: 3, mb: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ mb: 2 }}>🔗 裝置連線</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {device?.connected ? (
            <>
              <Chip label={`${device.serial}`} color="success" variant="outlined" />
              <Chip label={`${device.resolution[0]}x${device.resolution[1]}`} variant="outlined" />
              <Button variant="outlined" color="error" onClick={disconnectDevice}>斷開連線</Button>
            </>
          ) : (
            <Button variant="contained" onClick={openPicker}>選擇裝置連線</Button>
          )}
        </Box>
      </Paper>

      {/* 即時日誌 */}
      <Paper sx={{ p: 3, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="h6" sx={{ mb: 2 }}>📋 即時日誌</Typography>
        <Box
          sx={{
            bgcolor: '#0f172a', borderRadius: 1, p: 2, maxHeight: 250, overflow: 'auto',
            fontFamily: 'monospace', fontSize: 12, lineHeight: 1.8,
          }}
        >
          {logs.length === 0 ? (
            <Typography color="text.secondary" sx={{ fontSize: 12 }}>尚無日誌...</Typography>
          ) : (
            logs.slice(-50).map((log, i) => (
              <Box key={i} sx={{ color: log.includes('❌') ? '#ef4444' : log.includes('✅') ? '#10b981' : '#94a3b8' }}>
                {log}
              </Box>
            ))
          )}
        </Box>
      </Paper>

      {/* 裝置選擇對話框 */}
      <Dialog open={pickerOpen} onClose={() => setPickerOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          選擇要連接的裝置
          <Box>
            <Button size="small" startIcon={<AdsClickIcon />} onClick={handlePickWindow} disabled={pickingWindow || loadingDevices || loadingWindows} sx={{ mr: 1 }}>
              點擊選取視窗
            </Button>
            <Button size="small" startIcon={<RefreshIcon />} onClick={() => { loadDevices(); loadWindows(); }}
              disabled={loadingDevices || loadingWindows}>
              重新掃描
            </Button>
          </Box>
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <Tabs value={pickerTab} onChange={(_, v) => setPickerTab(v)} sx={{ px: 2, borderBottom: 1, borderColor: 'divider' }}>
            <Tab label="Android 裝置" icon={<PhoneAndroidIcon />} iconPosition="start" sx={{ minHeight: 48 }} />
            <Tab label="桌面應用" icon={<DesktopWindowsIcon />} iconPosition="start" sx={{ minHeight: 48 }} />
          </Tabs>

          {/* ADB 裝置分頁 */}
          {pickerTab === 0 && (
            loadingDevices ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                <CircularProgress />
              </Box>
            ) : devicesList.length === 0 ? (
              <Box sx={{ textAlign: 'center', p: 4 }}>
                <Typography color="text.secondary">找不到可用裝置</Typography>
                <Typography variant="caption" color="text.secondary">
                  請確認模擬器已啟動或手機已透過 USB 連接
                </Typography>
              </Box>
            ) : (
              <List sx={{ px: 2, py: 1 }}>
                {devicesList.map((d) => (
                  <ListItemButton
                    key={d.serial}
                    onClick={() => selectDevice(d.serial)}
                    sx={{
                      border: '1px solid', borderColor: 'divider', borderRadius: 1, mb: 1,
                      '&:hover': { borderColor: 'primary.main', bgcolor: 'rgba(99,102,241,0.08)' },
                    }}
                  >
                    <ListItemIcon>{getDeviceIcon(d.serial)}</ListItemIcon>
                    <ListItemText
                      primary={d.serial}
                      secondary={getDeviceLabel(d.serial)}
                      slotProps={{ primary: { sx: { fontFamily: 'monospace', fontWeight: 'bold' } } }}
                    />
                    <Chip label={d.status} size="small" color="success" variant="outlined" />
                  </ListItemButton>
                ))}
              </List>
            )
          )}

          {/* 桌面視窗分頁 */}
          {pickerTab === 1 && (
            loadingWindows ? (
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
              <Box sx={{ px: 2, py: 1 }}>
                <TextField
                  fullWidth
                  size="small"
                  placeholder="搜尋應用程式名稱..."
                  value={windowSearch}
                  onChange={(e) => setWindowSearch(e.target.value)}
                  sx={{ mb: 2 }}
                />
                <List>
                  {filteredWindows.length === 0 ? (
                    <Typography color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                      沒有符合的視窗
                    </Typography>
                  ) : (
                    filteredWindows.map((win) => (
                      <ListItemButton
                        key={win.window_id}
                        onClick={() => selectDesktopWindow(win)}
                        sx={{
                          border: '1px solid', borderColor: 'divider', borderRadius: 1, mb: 1,
                          '&:hover': { borderColor: '#8b5cf6', bgcolor: 'rgba(139,92,246,0.08)' },
                        }}
                      >
                        <ListItemIcon>
                          <DesktopWindowsIcon sx={{ color: '#8b5cf6' }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {win.owner_name}
                          </Typography>
                          {win.window_name && (
                            <Typography variant="caption" color="text.secondary" noWrap sx={{ maxWidth: 180 }}>
                              — {win.window_name}
                            </Typography>
                          )}
                        </Box>
                      }
                      secondary={`${win.width}×${win.height} · PID ${win.pid}`}
                    />
                    <Chip label={`ID ${win.window_id}`} size="small" variant="outlined" sx={{ fontSize: 10 }} />
                  </ListItemButton>
                    ))
                  )}
                </List>
              </Box>
            )
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default Dashboard;
