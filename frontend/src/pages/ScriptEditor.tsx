// 可視化腳本編輯器 — 完整模塊系統 + 屬性面板
import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Box, Paper, Typography, Button, TextField, List, ListItemButton,
  ListItemText, IconButton, Divider, Dialog, DialogTitle, DialogContent,
  DialogActions, Tooltip, Accordion, AccordionSummary, AccordionDetails,
  Tabs, Tab,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SaveIcon from '@mui/icons-material/Save';
import DeleteIcon from '@mui/icons-material/Delete';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import {
  ReactFlow, Controls, Background, MiniMap,
  addEdge, useNodesState, useEdgesState,
  type Connection, type Node, type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useAppStore } from '../stores/appStore';
import { NODE_MODULES, type Script, type ScriptNodeType, type NodeModuleDef } from '../types/script';
import ScriptNodeComponent from '../components/ScriptNode';
import NodePropertiesPanel from '../components/NodePropertiesPanel';
import LiveRecorder from '../components/LiveRecorder';
import {
  applyActionsToFlow,
  buildScriptFromActions,
  type ConvertOptions,
  type RecordedAction,
} from '../utils/recordConverter';

// 註冊自訂節點類型
const nodeTypes = { custom: ScriptNodeComponent };

// 分類標籤
const CATEGORY_LABELS: Record<string, string> = {
  flow: '🔀 流程控制',
  detect: '🔍 偵測/感知',
  action: '👆 操作/動作',
  logic: '📦 邏輯',
};

// 按分類分組模塊（排除 start/end，不可手動新增）
const groupedModules = (['flow', 'detect', 'action', 'logic'] as const).map((cat) => ({
  category: cat,
  label: CATEGORY_LABELS[cat],
  modules: NODE_MODULES.filter((m) => m.category === cat && m.type !== 'start' && m.type !== 'end'),
}));

const ScriptEditor = () => {
  const { scripts, fetchScripts, createScript, saveScript, deleteScript, fetchAssets } = useAppStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => { fetchScripts(); fetchAssets(); }, [fetchScripts, fetchAssets]);

  const selected = scripts.find((s) => s.id === selectedId) ?? null;
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

  // 載入腳本節點到 React Flow
  useEffect(() => {
    if (!selected) { setNodes([]); setEdges([]); setSelectedNodeId(null); return; }

    const flowNodes: Node[] = selected.nodes.map((n) => ({
      id: n.id,
      type: 'custom',
      position: n.position,
      data: { node_type: n.type, ...n.data },
    }));

    const flowEdges: Edge[] = selected.edges.map((e) => ({
      id: e.id, source: e.source, target: e.target,
      sourceHandle: e.sourceHandle ?? undefined,
      label: e.label ?? '',
      style: { stroke: e.sourceHandle === 'false' ? '#f87171' : e.sourceHandle === 'true' ? '#4ade80' : '#6366f1' },
      animated: true,
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
    setSelectedNodeId(null);
  }, [selected, setNodes, setEdges]);

  const onConnect = useCallback((conn: Connection) => {
    const edgeColor = conn.sourceHandle === 'false' ? '#f87171' : conn.sourceHandle === 'true' ? '#4ade80' : '#6366f1';
    const label = conn.sourceHandle === 'true' ? 'True' : conn.sourceHandle === 'false' ? 'False'
      : conn.sourceHandle === 'body' ? 'Body' : conn.sourceHandle === 'done' ? 'Done' : '';
    setEdges((eds) => addEdge({
      ...conn, animated: true, style: { stroke: edgeColor }, label,
    }, eds));
  }, [setEdges]);

  // 點擊節點 → 選取
  const onNodeClick = useCallback((_: unknown, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  // 點擊空白 → 取消選取
  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  // 新增模塊節點
  const nodeCounter = useRef(0);
  const addModuleNode = useCallback((moduleDef: NodeModuleDef) => {
    nodeCounter.current += 1;
    const id = `${moduleDef.type}_${nodeCounter.current}_${performance.now().toFixed(0)}`;
    setNodes((nds) => {
      const offsetX = (nds.length % 5) * 40;
      const offsetY = (nds.length % 3) * 60;
      return [...nds, {
        id, type: 'custom',
        position: { x: 300 + offsetX, y: 150 + offsetY },
        data: { node_type: moduleDef.type, ...moduleDef.defaultData },
      }];
    });
    setSelectedNodeId(id);
  }, [setNodes]);

  // 更新節點屬性
  const handlePropertyChange = useCallback((key: string, value: unknown) => {
    if (!selectedNodeId) return;
    setNodes((nds) => nds.map((n) =>
      n.id === selectedNodeId ? { ...n, data: { ...n.data, [key]: value } } : n
    ));
  }, [selectedNodeId, setNodes]);

  // 儲存腳本
  const handleSave = async () => {
    if (!selected) return;
    const updated: Script = {
      ...selected,
      nodes: nodes.map((n) => ({
        id: n.id,
        type: ((n.data as Record<string, unknown>).node_type as ScriptNodeType) ?? 'start',
        position: n.position,
        data: (() => {
          const { node_type: _unused, ...rest } = n.data as Record<string, unknown>;
          void _unused;
          return rest;
        })(),
      })),
      edges: edges.map((e) => ({
        id: e.id, source: e.source, target: e.target,
        sourceHandle: e.sourceHandle ?? undefined,
        label: (e.label as string) ?? undefined,
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

  // 刪除選取的節點
  const deleteSelectedNode = () => {
    if (!selectedNodeId) return;
    const nodeType = (selectedNode?.data as Record<string, unknown>)?.node_type;
    if (nodeType === 'start' || nodeType === 'end') return; // 不可刪除起止節點
    setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
    setSelectedNodeId(null);
  };

  // ── 錄製操作轉換為流程方塊 ──
  const handleApplyRecordedActions = async (
    options: ConvertOptions,
    recordedActions: RecordedAction[],
  ) => {
    if (options.applyMode === 'new_script') {
      const scriptName = options.newScriptName?.trim() || `錄製腳本_${Date.now()}`;
      const newScript = await createScript(scriptName);
      const { nodes: convertedNodes, edges: convertedEdges } = buildScriptFromActions(
        recordedActions,
        options,
      );
      await saveScript({
        ...newScript,
        nodes: convertedNodes,
        edges: convertedEdges,
      });
      setSelectedId(newScript.id);
      setActiveTab(0);
      return;
    }

    if (!selected) return;

    const { nodes: newNodes, edges: newEdges, insertedNodeIds } = applyActionsToFlow(
      nodes,
      edges,
      recordedActions,
      options,
    );

    setNodes(newNodes);
    setEdges(newEdges);
    if (insertedNodeIds.length > 0) {
      setSelectedNodeId(insertedNodeIds[0]);
    }

    // 自動保存更新後的腳本
    const updatedScript: Script = {
      ...selected,
      nodes: newNodes.map((n) => {
        const { node_type, ...restData } = (n.data as Record<string, unknown>) ?? {};
        return {
          id: n.id,
          type: (node_type as ScriptNodeType) ?? 'start',
          position: n.position,
          data: restData,
        };
      }),
      edges: newEdges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? undefined,
        label: (e.label as string) ?? undefined,
      })),
    };

    await saveScript(updatedScript);
    setActiveTab(0); // 自動切回方塊編輯頁面查看
  };

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* ══════ 左側：腳本列表 + 模塊工具箱 ══════ */}
      <Paper
        sx={{
          width: 260,
          borderRadius: 0,
          borderRight: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          height: '100%',
        }}
      >
        {/* ── 上半部：腳本列表 (未選中佔 100%，已選中各佔 50%) ── */}
        <Box
          sx={{
            flex: selected ? '0 0 50%' : 1,
            height: selected ? '50%' : '100%',
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            overflow: 'hidden',
            transition: 'all 0.2s ease-in-out',
          }}
        >
          <Box sx={{ p: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>📋 腳本</Typography>
            <IconButton size="small" color="primary" onClick={() => setCreateOpen(true)}>
              <AddIcon />
            </IconButton>
          </Box>
          <Divider />
          <List dense sx={{ flex: 1, overflow: 'auto', minHeight: 0, py: 0 }}>
            {scripts.map((s) => (
              <ListItemButton
                key={s.id}
                selected={selectedId === s.id}
                onClick={() => setSelectedId(s.id)}
                sx={{ py: 0.5 }}
              >
                <ListItemText
                  primary={s.name}
                  secondary={`v${s.version}`}
                  slotProps={{ primary: { sx: { fontSize: 13 } }, secondary: { sx: { fontSize: 11 } } }}
                />
                <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); deleteScript(s.id); }}>
                  <DeleteIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </ListItemButton>
            ))}
            {scripts.length === 0 && (
              <Typography sx={{ p: 1.5, textAlign: 'center', color: 'text.secondary', fontSize: 12 }}>
                尚無腳本
              </Typography>
            )}
          </List>
        </Box>

        {/* ── 下半部：模塊工具箱 (選中時才顯示，佔 50%) ── */}
        {selected && (
          <Box
            sx={{
              flex: '0 0 50%',
              height: '50%',
              display: 'flex',
              flexDirection: 'column',
              minHeight: 0,
              overflow: 'hidden',
              borderTop: '1px solid',
              borderColor: 'divider',
              transition: 'all 0.2s ease-in-out',
            }}
          >
            <Box sx={{ p: 1.5, pb: 1 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>🧩 模塊工具箱</Typography>
            </Box>
            <Box sx={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
              {groupedModules.map((group) => (
                <Accordion
                  key={group.category}
                  defaultExpanded
                  disableGutters
                  sx={{ bgcolor: 'transparent', boxShadow: 'none', '&:before': { display: 'none' } }}
                >
                  <AccordionSummary
                    expandIcon={<ExpandMoreIcon sx={{ fontSize: 16 }} />}
                    sx={{ minHeight: 32, '& .MuiAccordionSummary-content': { my: 0 } }}
                  >
                    <Typography sx={{ fontSize: 12, fontWeight: 'bold' }}>{group.label}</Typography>
                  </AccordionSummary>
                  <AccordionDetails sx={{ p: 0.5, pt: 0 }}>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {group.modules.map((m) => (
                        <Tooltip key={m.type} title={m.description} arrow>
                          <Button
                            size="small"
                            variant="outlined"
                            onClick={() => addModuleNode(m)}
                            sx={{
                              fontSize: 11, px: 1, py: 0.3, minWidth: 0,
                              borderColor: m.color, color: '#fff',
                              bgcolor: `${m.color}40`,
                              '&:hover': { bgcolor: `${m.color}80`, borderColor: m.color },
                            }}
                          >
                            {m.icon} {m.label}
                          </Button>
                        </Tooltip>
                      ))}
                    </Box>
                  </AccordionDetails>
                </Accordion>
              ))}
            </Box>
          </Box>
        )}
      </Paper>

      {/* ══════ 中間：編輯區 (分頁籤) ══════ */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {selected ? (
          <>
            {/* Tab 切換 */}
            <Tabs
              value={activeTab}
              onChange={(_, v) => setActiveTab(v)}
              sx={{
                minHeight: 36,
                borderBottom: '1px solid',
                borderColor: 'divider',
                bgcolor: '#0f172a',
                '& .MuiTab-root': { minHeight: 36, fontSize: 13, py: 0 },
              }}
            >
              <Tab label="🧩 方塊編輯" />
              <Tab label="📹 即時錄製" />
            </Tabs>

            {/* Tab 0: React Flow 編輯器 */}
            <Box
              sx={{
                flex: 1,
                position: 'relative',
                display: activeTab === 0 ? 'flex' : 'none',
                flexDirection: 'column',
                minHeight: 0,
              }}
            >
              {/* 頂部工具列 */}
              <Box sx={{ position: 'absolute', top: 12, right: 12, zIndex: 10, display: 'flex', gap: 1 }}>
                {selectedNodeId && (selectedNode?.data as Record<string, unknown>)?.node_type !== 'start'
                  && (selectedNode?.data as Record<string, unknown>)?.node_type !== 'end' && (
                  <Button size="small" variant="contained" color="error" onClick={deleteSelectedNode}>
                    🗑 刪除節點
                  </Button>
                )}
                <Button size="small" variant="contained" color="success" startIcon={<SaveIcon />} onClick={handleSave}>
                  儲存
                </Button>
              </Box>

              <ReactFlow
                nodes={nodes} edges={edges}
                onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onNodeClick={onNodeClick}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                fitView
                style={{ background: '#0f172a' }}
              >
                <Controls />
                <MiniMap style={{ background: '#1e293b' }} />
                <Background color="#334155" gap={20} />
              </ReactFlow>
            </Box>

            {/* Tab 1: 即時錄製 */}
            <Box
              sx={{
                flex: 1,
                display: activeTab === 1 ? 'block' : 'none',
                height: '100%',
                minHeight: 0,
              }}
            >
              <LiveRecorder
                scriptId={selectedId}
                selectedNodeId={selectedNodeId}
                selectedNodeLabel={
                  selectedNode
                    ? ((selectedNode.data as Record<string, unknown>)?.node_type as string) || selectedNode.id
                    : null
                }
                onApplyToScript={handleApplyRecordedActions}
              />
            </Box>
          </>
        ) : (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Typography color="text.secondary">← 請從左側選擇或建立腳本</Typography>
          </Box>
        )}
      </Box>

      {/* ══════ 右側：屬性面板 (只在方塊編輯模式顯示) ══════ */}
      {selected && activeTab === 0 && (
        <Paper sx={{ width: 280, borderRadius: 0, borderLeft: '1px solid', borderColor: 'divider', overflow: 'hidden' }}>
          {selectedNode ? (
            <NodePropertiesPanel
              nodeType={(selectedNode.data as Record<string, unknown>).node_type as ScriptNodeType}
              data={selectedNode.data as Record<string, unknown>}
              onChange={handlePropertyChange}
            />
          ) : (
            <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <Typography color="text.secondary" sx={{ fontSize: 13, textAlign: 'center' }}>
                點擊節點<br />編輯屬性
              </Typography>
            </Box>
          )}
        </Paper>
      )}

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
