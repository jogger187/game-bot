// 左側導航欄
import {
  Box, List, ListItemButton, ListItemIcon, ListItemText,
  Typography, Chip, Divider,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import CodeIcon from '@mui/icons-material/Code';
import ImageIcon from '@mui/icons-material/Image';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SettingsIcon from '@mui/icons-material/Settings';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import { useAppStore } from '../../stores/appStore';

const NAV_ITEMS = [
  { key: 'dashboard' as const, label: '儀表板', icon: <DashboardIcon /> },
  { key: 'scripts' as const, label: '腳本編輯器', icon: <CodeIcon /> },
  { key: 'assets' as const, label: '資源管理', icon: <ImageIcon /> },
  { key: 'runner' as const, label: '任務控制', icon: <PlayArrowIcon /> },
  { key: 'settings' as const, label: '系統設定', icon: <SettingsIcon /> },
];

const Sidebar = () => {
  const { currentPage, setPage, device, tasks } = useAppStore();
  const runningCount = tasks.filter((t) => t.enabled && !t.completed).length;

  return (
    <Box
      sx={{
        width: 240,
        height: '100vh',
        bgcolor: '#0f172a',
        borderRight: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Logo 區域 */}
      <Box sx={{ p: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
          🎮 Game Bot
        </Typography>
        <Typography variant="caption" color="text.secondary">
          遊戲自動化控制台
        </Typography>
      </Box>

      <Divider />

      {/* 導航選單 */}
      <List sx={{ flex: 1, px: 1, py: 2 }}>
        {NAV_ITEMS.map((item) => (
          <ListItemButton
            key={item.key}
            selected={currentPage === item.key}
            onClick={() => setPage(item.key)}
            sx={{
              borderRadius: 2,
              mb: 0.5,
              '&.Mui-selected': {
                bgcolor: 'primary.dark',
                '&:hover': { bgcolor: 'primary.dark' },
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36, color: currentPage === item.key ? 'primary.light' : 'text.secondary' }}>
              {item.icon}
            </ListItemIcon>
            <ListItemText primary={item.label} slotProps={{ primary: { sx: { fontSize: 14 } } }} />
            {item.key === 'runner' && runningCount > 0 && (
              <Chip label={runningCount} size="small" color="success" sx={{ height: 20, fontSize: 11 }} />
            )}
          </ListItemButton>
        ))}
      </List>

      <Divider />

      {/* 裝置狀態 */}
      <Box sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FiberManualRecordIcon
            sx={{ fontSize: 10, color: device?.connected ? 'success.main' : 'error.main' }}
          />
          <Typography variant="caption" color="text.secondary">
            {device?.connected ? `已連線: ${device.serial}` : '尚未連線'}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default Sidebar;
