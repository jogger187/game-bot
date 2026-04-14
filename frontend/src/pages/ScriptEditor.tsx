// 可視化腳本編輯器 — 基於 React Flow 的拖拽式節點編輯
import { useEffect, useState, useCallback } from 'react';
import {
  Box, Paper, Typography, Button, TextField, List, ListItemButton,
  ListItemText, IconButton, Divider, Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SaveIcon from '@mui/icons-material/Save';
import DeleteIcon from '@mui/icons-material/Delete';
import {
  ReactFlow, Controls, Background, MiniMap,
  addEdge, useNodesState, useEdgesState,
  type Connection, type Node, type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useAppStore } from '../stores/appStore';
import type { Script } from '../types/script';

const ScriptEditor = () => {
  const { scripts, fetchScripts, createScript, saveScript, deleteScript } = useAppStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');

  useEffect(() => { fetchScripts(); }, [fetchScripts]);

  const selected = scripts.find((s) => s.id === selectedId) ?? null;

  // 載入腳本節點到 React Flow
  useEffect(() => {
    if (!selected) { setNodes([]); setEdges([]); return; }

    const flowNodes: Node[] = selected.nodes.map((n) => ({
      id: n.id,
      type: n.type === 'start' ? 'input' : n.type === 'end' ? 'output' : 'default',
      position: n.position,
      data: { label: `${n.type === 'start' ? '🟢 開始' : n.type === 'end' ? '🔴 結束' : n.type === 'condition' ? '🔵 條件' : '🟡 動作'}`, ...n.data },
      style: {
        background: n.type === 'start' ? '#065f46' : n.type === 'end' ? '#7f1d1d' : n.type === 'condition' ? '#1e3a5f' : '#713f12',
        color: 'white', border: '1px solid #475569', borderRadius: 8, padding: 10,
      },
    }));

    const flowEdges: Edge[] = selected.edges.map((e) => ({
      id: e.id, source: e.source, target: e.target, label: e.label ?? '',
      style: { stroke: '#6366f1' }, animated: true,
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [selected, setNodes, setEdges]);

  const onConnect = useCallback((conn: Connection) => {
    setEdges((eds) => addEdge({ ...conn, animated: true, style: { stroke: '#6366f1' } }, eds));
  }, [setEdges]);

  // 新增節點
  const addNode = (type: string) => {
    const id = `${type}_${Date.now()}`;
    const labels: Record<string, string> = { condition: '🔵 條件', action: '🟡 動作' };
    const colors: Record<string, string> = { condition: '#1e3a5f', action: '#713f12' };
    const newNode: Node = {
      id, type: 'default',
      position: { x: 250 + Math.random() * 200, y: 150 + Math.random() * 200 },
      data: { label: labels[type] ?? type, node_type: type },
      style: { background: colors[type] ?? '#334155', color: 'white', border: '1px solid #475569', borderRadius: 8, padding: 10 },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  // 儲存腳本
  const handleSave = async () => {
    if (!selected) return;
    const updated: Script = {
      ...selected,
      nodes: nodes.map((n) => ({
        id: n.id,
        type: ((n.data as Record<string, unknown>).node_type as string ?? n.type ?? 'default') as Script['nodes'][number]['type'],
        position: n.position, data: n.data as Record<string, unknown>,
      })),
      edges: edges.map((e) => ({
        id: e.id, source: e.source, target: e.target, label: (e.label as string) ?? undefined,
      })),
    };
    await saveScript(updated);
  };

  const handleCreate = async () => {
    if (!newName.trim()) return;
    const s = await createScript(newName.trim());
    setSelectedId(s.id);
    setNewName('');
    setCreateOpen(false);
  };

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* 腳本列表面板 */}
      <Paper sx={{ width: 260, borderRadius: 0, borderRight: '1px solid', borderColor: 'divider', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>📋 腳本列表</Typography>
          <IconButton size="small" color="primary" onClick={() => setCreateOpen(true)}><AddIcon /></IconButton>
        </Box>
        <Divider />
        <List sx={{ flex: 1, overflow: 'auto' }}>
          {scripts.map((s) => (
            <ListItemButton key={s.id} selected={selectedId === s.id} onClick={() => setSelectedId(s.id)}>
              <ListItemText primary={s.name} secondary={`v${s.version}`} />
              <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); deleteScript(s.id); }}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </ListItemButton>
          ))}
          {scripts.length === 0 && (
            <Typography sx={{ p: 2, textAlign: 'center', color: 'text.secondary', fontSize: 13 }}>
              尚無腳本，點擊 + 建立
            </Typography>
          )}
        </List>
      </Paper>

      {/* React Flow 編輯區 */}
      <Box sx={{ flex: 1, position: 'relative' }}>
        {selected ? (
          <>
            {/* 工具列 */}
            <Box sx={{ position: 'absolute', top: 12, left: 12, zIndex: 10, display: 'flex', gap: 1 }}>
              <Button size="small" variant="contained" onClick={() => addNode('condition')}>+ 條件</Button>
              <Button size="small" variant="contained" color="warning" onClick={() => addNode('action')}>+ 動作</Button>
              <Button size="small" variant="contained" color="success" startIcon={<SaveIcon />} onClick={handleSave}>儲存</Button>
            </Box>

            <ReactFlow
              nodes={nodes} edges={edges}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              fitView
              style={{ background: '#0f172a' }}
            >
              <Controls />
              <MiniMap style={{ background: '#1e293b' }} />
              <Background color="#334155" gap={20} />
            </ReactFlow>
          </>
        ) : (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Typography color="text.secondary">← 請從左側選擇或建立腳本</Typography>
          </Box>
        )}
      </Box>

      {/* 建立腳本對話框 */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)}>
        <DialogTitle>建立新腳本</DialogTitle>
        <DialogContent>
          <TextField autoFocus fullWidth label="腳本名稱" value={newName}
            onChange={(e) => setNewName(e.target.value)} sx={{ mt: 1 }}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>取消</Button>
          <Button variant="contained" onClick={handleCreate}>建立</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ScriptEditor;
