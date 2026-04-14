// 系統設定頁面
import { useState } from 'react';
import {
  Box, Typography, Paper, TextField, FormControl, InputLabel, Select,
  MenuItem, Button, Divider, Switch, FormControlLabel,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import { useAppStore } from '../stores/appStore';

const Settings = () => {
  const { device, addLog } = useAppStore();
  const [serial, setSerial] = useState(device?.serial ?? '127.0.0.1:5555');
  const [capMode, setCapMode] = useState(device?.mode ?? 'adb');
  const [emulator, setEmulator] = useState(device?.emulator_type ?? 'auto');
  const [antiDetect, setAntiDetect] = useState(true);
  const [randomDelay, setRandomDelay] = useState(true);

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
          <TextField label="裝置序列號" value={serial} onChange={(e) => setSerial(e.target.value)}
            size="small" helperText="模擬器預設 127.0.0.1:5555" />
          <FormControl size="small">
            <InputLabel>截圖方式</InputLabel>
            <Select value={capMode} onChange={(e) => setCapMode(e.target.value)} label="截圖方式">
              <MenuItem value="adb">ADB screencap</MenuItem>
              <MenuItem value="minicap">Minicap（高效能）</MenuItem>
              <MenuItem value="emulator">模擬器 API</MenuItem>
            </Select>
          </FormControl>
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
    </Box>
  );
};

export default Settings;
