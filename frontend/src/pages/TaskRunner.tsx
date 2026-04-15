// 任務執行控制頁面
import { useEffect, useState, useRef } from 'react';
import {
  Box, Typography, Paper, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, IconButton, Button, Chip, FormControl, InputLabel,
  Select, MenuItem, Dialog, DialogTitle, DialogContent, DialogActions,
  Tooltip, TextField, RadioGroup, FormControlLabel, Radio, FormLabel, Stack,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import StopIcon from '@mui/icons-material/Stop';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { useAppStore } from '../stores/appStore';

const TaskRunner = () => {
  const { scripts, tasks, fetchScripts, fetchTasks, startTask, toggleTask, stopTask, removeTask } = useAppStore();
  const [launchOpen, setLaunchOpen] = useState(false);
  const [selectedScript, setSelectedScript] = useState('');
  const [runMode, setRunMode] = useState<'loop' | 'fixed' | 'scheduled'>('loop');
  const [maxRuns, setMaxRuns] = useState<number>(1);
  const [loopInterval, setLoopInterval] = useState<number>(3);
  const [scheduledTimes, setScheduledTimes] = useState<string[]>([]);
  const [newTime, setNewTime] = useState<string>('09:00:00');
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
    await startTask(script.id, script.name, runMode, maxRuns, loopInterval, scheduledTimes);
    setLaunchOpen(false);
    setSelectedScript('');
    setRunMode('loop');
    setMaxRuns(1);
    setLoopInterval(3);
    setScheduledTimes([]);
  };

  const handleAddTime = () => {
    if (scheduledTimes.length >= 24) {
      alert('最多只能添加 24 個時間點');
      return;
    }
    if (scheduledTimes.includes(newTime)) {
      alert('此時間點已存在');
      return;
    }
    setScheduledTimes([...scheduledTimes, newTime].sort());
  };

  const handleRemoveTime = (time: string) => {
    setScheduledTimes(scheduledTimes.filter((t) => t !== time));
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
                  <TableCell>
                    {t.run_mode === 'loop' ? '循環' : t.run_mode === 'scheduled' ? '每日定時' : `固定 ${t.max_runs} 次`}
                  </TableCell>
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
      <Dialog open={launchOpen} onClose={() => setLaunchOpen(false)} maxWidth="sm" fullWidth>
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

          <FormControl component="fieldset" sx={{ mt: 3 }}>
            <FormLabel component="legend">執行模式</FormLabel>
            <RadioGroup value={runMode} onChange={(e) => setRunMode(e.target.value as 'loop' | 'fixed' | 'scheduled')}>
              <FormControlLabel value="loop" control={<Radio />} label="常駐循環" />
              <FormControlLabel value="fixed" control={<Radio />} label="指定循環次數" />
              <FormControlLabel value="scheduled" control={<Radio />} label="每日定時觸發 (UTC)" />
            </RadioGroup>
          </FormControl>

          {runMode === 'fixed' && (
            <TextField
              fullWidth
              label="執行次數"
              type="number"
              value={maxRuns}
              onChange={(e) => setMaxRuns(Math.max(1, parseInt(e.target.value) || 1))}
              sx={{ mt: 2 }}
              slotProps={{ htmlInput: { min: 1 } }}
            />
          )}

          {runMode === 'scheduled' && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                定時觸發時間點 (UTC 時區) {scheduledTimes.length}/24
              </Typography>
              <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                <TextField
                  label="時間 (HH:MM:SS)"
                  type="time"
                  value={newTime}
                  onChange={(e) => setNewTime(e.target.value + ':00')}
                  slotProps={{ htmlInput: { step: 1 } }}
                  sx={{ flex: 1 }}
                />
                <Button
                  variant="outlined"
                  startIcon={<AddIcon />}
                  onClick={handleAddTime}
                  disabled={scheduledTimes.length >= 24}
                >
                  添加
                </Button>
              </Stack>
              <Paper variant="outlined" sx={{ p: 1, maxHeight: 200, overflow: 'auto' }}>
                {scheduledTimes.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                    尚未添加時間點
                  </Typography>
                ) : (
                  <Stack spacing={0.5}>
                    {scheduledTimes.map((time) => (
                      <Box
                        key={time}
                        sx={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          p: 1,
                          bgcolor: 'action.hover',
                          borderRadius: 1,
                        }}
                      >
                        <Typography variant="body2">{time}</Typography>
                        <IconButton size="small" onClick={() => handleRemoveTime(time)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    ))}
                  </Stack>
                )}
              </Paper>
            </Box>
          )}

          {runMode !== 'scheduled' && (
            <TextField
              fullWidth
              label="循環間隔 (秒)"
              type="number"
              value={loopInterval}
              onChange={(e) => setLoopInterval(Math.max(0, parseInt(e.target.value) || 0))}
              sx={{ mt: 2 }}
              helperText="每次執行完成後等待的時間"
              slotProps={{ htmlInput: { min: 0 } }}
            />
          )}
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
