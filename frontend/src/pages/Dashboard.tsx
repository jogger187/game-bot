// 儀表板頁面 — 裝置狀態總覽
import { useEffect } from 'react';
import {
  Box, Paper, Typography, Button, Grid, Card, CardContent, Chip,
} from '@mui/material';
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';
import PlayCircleIcon from '@mui/icons-material/PlayCircle';
import DescriptionIcon from '@mui/icons-material/Description';
import ImageIcon from '@mui/icons-material/Image';
import { useAppStore } from '../stores/appStore';

const Dashboard = () => {
  const { device, scripts, assets, tasks, logs, connectDevice, disconnectDevice, fetchDevice } = useAppStore();

  useEffect(() => {
    fetchDevice();
  }, [fetchDevice]);

  const runningTasks = tasks.filter((t) => t.enabled && !t.completed).length;

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
            <Button variant="contained" onClick={() => connectDevice()}>連接裝置</Button>
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
    </Box>
  );
};

export default Dashboard;
