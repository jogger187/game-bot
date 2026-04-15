// 任務執行控制頁面
import { useEffect, useState, useRef } from 'react';
import {
  Box, Typography, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, IconButton, Button, Chip, FormControl, InputLabel,
  Select, MenuItem, Dialog, DialogTitle, DialogContent, DialogActions,
  Tooltip,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import DeleteIcon from '@mui/icons-material/Delete';
import { useAppStore } from '../stores/appStore';

const TaskRunner = () => {
  const { scripts, tasks, fetchScripts, fetchTasks, startTask, toggleTask, stopTask, removeTask } = useAppStore();
  const [launchOpen, setLaunchOpen] = useState(false);
  const [selectedScript, setSelectedScript] = useState('');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 初始載入 + 自動輪詢任務狀態
  useEffect(() => {
    fetchScripts();
    fetchTasks();

    // 每 2 秒刷新任務列表
    intervalRef.current = setInterval(() => {
      fetchTasks();
    }, 2000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchScripts, fetchTasks]);

  const handleStart = async () => {
    const script = scripts.find((s) => s.id === selectedScript);
    if (!script) return;
    await startTask(script.id, script.name, 'loop', 0);
    setLaunchOpen(false);
    setSelectedScript('');
  };

  // 狀態顏色和文字
  const getStatusChip = (t: typeof tasks[0]) => {
    if (t.completed) return <Chip label="已完成" size="small" color="default" />;
    if (!t.enabled) return <Chip label="暫停中" size="small" color="warning" />;
    return <Chip label="執行中" size="small" color="success" />;
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
                  目前沒有任務，點擊「啟動新任務」開始
                </TableCell>
              </TableRow>
            ) : (
              tasks.map((t) => (
                <TableRow key={t.job_id} sx={{ opacity: t.completed ? 0.6 : 1 }}>
                  <TableCell>{t.script_name}</TableCell>
                  <TableCell>{t.run_mode === 'loop' ? '循環' : `固定 ${t.max_runs} 次`}</TableCell>
                  <TableCell>{t.run_count}{t.max_runs > 0 ? ` / ${t.max_runs}` : ''}</TableCell>
                  <TableCell>{getStatusChip(t)}</TableCell>
                  <TableCell align="right">
                    {/* 暫停 / 繼續 按鈕 */}
                    {!t.completed && (
                      <Tooltip title={t.enabled ? '暫停' : '繼續'}>
                        <IconButton
                          size="small"
                          color={t.enabled ? 'warning' : 'success'}
                          onClick={() => toggleTask(t.job_id)}
                        >
                          {t.enabled ? <PauseIcon /> : <PlayArrowIcon />}
                        </IconButton>
                      </Tooltip>
                    )}

                    {/* 停止 按鈕（僅執行中/暫停中顯示） */}
                    {!t.completed && (
                      <Tooltip title="停止">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => stopTask(t.job_id)}
                        >
                          <StopIcon />
                        </IconButton>
                      </Tooltip>
                    )}

                    {/* 刪除 按鈕（已完成才顯示） */}
                    {t.completed && (
                      <Tooltip title="移除">
                        <IconButton
                          size="small"
                          color="default"
                          onClick={() => removeTask(t.job_id)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    )}
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
