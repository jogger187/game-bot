// 任務執行控制頁面
import { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, IconButton, Button, Chip, FormControl, InputLabel,
  Select, MenuItem, Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import { useAppStore } from '../stores/appStore';

const TaskRunner = () => {
  const { scripts, tasks, fetchScripts, fetchTasks, startTask, toggleTask, stopTask } = useAppStore();
  const [launchOpen, setLaunchOpen] = useState(false);
  const [selectedScript, setSelectedScript] = useState('');

  useEffect(() => { fetchScripts(); fetchTasks(); }, [fetchScripts, fetchTasks]);

  const handleStart = async () => {
    const script = scripts.find((s) => s.id === selectedScript);
    if (!script) return;
    await startTask(script.id, script.name, 'loop', 0);
    setLaunchOpen(false);
    setSelectedScript('');
  };

  return (
    <Box sx={{ p: 4, overflow: 'auto', height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>🚀 任務控制</Typography>
        <Button variant="contained" startIcon={<PlayArrowIcon />} onClick={() => setLaunchOpen(true)}>
          啟動新任務
        </Button>
      </Box>

      <TableContainer component={Paper} sx={{ border: '1px solid', borderColor: 'divider' }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>腳本名稱</TableCell>
              <TableCell>模式</TableCell>
              <TableCell>執行次數</TableCell>
              <TableCell>狀態</TableCell>
              <TableCell align="right">操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tasks.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} sx={{ textAlign: 'center', py: 4, color: 'text.secondary' }}>
                  目前沒有執行中的任務
                </TableCell>
              </TableRow>
            ) : (
              tasks.map((t) => (
                <TableRow key={t.job_id}>
                  <TableCell>{t.script_name}</TableCell>
                  <TableCell>{t.run_mode === 'loop' ? '循環' : `固定 ${t.max_runs} 次`}</TableCell>
                  <TableCell>{t.run_count}{t.max_runs > 0 ? ` / ${t.max_runs}` : ''}</TableCell>
                  <TableCell>
                    <Chip
                      label={t.completed ? '已完成' : t.enabled ? '執行中' : '暫停中'}
                      size="small"
                      color={t.completed ? 'default' : t.enabled ? 'success' : 'warning'}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <IconButton size="small" onClick={() => toggleTask(t.job_id)} disabled={t.completed}>
                      {t.enabled ? <PauseIcon /> : <PlayArrowIcon />}
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => stopTask(t.job_id)}>
                      <StopIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* 啟動任務對話框 */}
      <Dialog open={launchOpen} onClose={() => setLaunchOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>啟動新任務</DialogTitle>
        <DialogContent>
          <FormControl fullWidth sx={{ mt: 1 }}>
            <InputLabel>選擇腳本</InputLabel>
            <Select value={selectedScript} onChange={(e) => setSelectedScript(e.target.value)} label="選擇腳本">
              {scripts.map((s) => (
                <MenuItem key={s.id} value={s.id}>{s.name}</MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLaunchOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleStart} disabled={!selectedScript}>啟動</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TaskRunner;
