// 資源管理頁面 — 模板截取 + 已存模板列表 (支援網格/列表切換與搜尋過濾)
import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Box, Typography, Paper, Grid, Card, CardActions, Button,
  IconButton, Tabs, Tab, Skeleton, Tooltip, TextField,
  InputAdornment, ToggleButton, ToggleButtonGroup, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Dialog, DialogTitle, DialogContent, DialogActions,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import CropIcon from '@mui/icons-material/Crop';
import ImageIcon from '@mui/icons-material/Image';
import BrokenImageIcon from '@mui/icons-material/BrokenImage';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import { useAppStore } from '../stores/appStore';
import TemplateCapturer from '../components/TemplateCapturer';
import * as api from '../utils/tauri';

// 棋盤格背景 (方便檢視透明背景模板圖)
const CHECKERBOARD_BG = {
  bgcolor: '#1e293b',
  backgroundImage:
    'linear-gradient(45deg, #334155 25%, transparent 25%), ' +
    'linear-gradient(-45deg, #334155 25%, transparent 25%), ' +
    'linear-gradient(45deg, transparent 75%, #334155 75%), ' +
    'linear-gradient(-45deg, transparent 75%, #334155 75%)',
  backgroundSize: '16px 16px',
  backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0px',
};

// 格式化檔案大小
const formatBytes = (bytes: number): string => {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
};

const AssetManager = () => {
  const { assets, fetchAssets, deleteAsset } = useAppStore();
  const [tab, setTab] = useState(0);

  // 視圖切換 ('grid' | 'list')，預設由 localStorage 記憶
  const [viewMode, setViewMode] = useState<'grid' | 'list'>(() => {
    return (localStorage.getItem('asset_view_mode') as 'grid' | 'list') || 'grid';
  });

  // 搜尋過濾
  const [searchQuery, setSearchQuery] = useState('');

  // 縮圖快取: name -> base64 data URL
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({});
  const [loadingThumbs, setLoadingThumbs] = useState(false);

  // 大圖預覽 Dialog
  const [previewAsset, setPreviewAsset] = useState<{ name: string; size: number } | null>(null);

  // 批次載入所有縮圖
  const loadThumbnails = useCallback(async (assetList: typeof assets) => {
    if (assetList.length === 0) return;
    setLoadingThumbs(true);
    const results: Record<string, string> = {};
    await Promise.allSettled(
      assetList.map(async (asset) => {
        try {
          const b64 = await api.assetRead(asset.name);
          results[asset.name] = b64;
        } catch {
          // 載入失敗就不放入快取
        }
      }),
    );
    setThumbnails((prev) => ({ ...prev, ...results }));
    setLoadingThumbs(false);
  }, []);

  useEffect(() => { fetchAssets(); }, [fetchAssets]);

  // 當 assets 更新時載入縮圖
  useEffect(() => {
    if (assets.length > 0) {
      loadThumbnails(assets);
    }
  }, [assets, loadThumbnails]);

  const handleRefresh = useCallback(async () => {
    setThumbnails({});
    await fetchAssets();
  }, [fetchAssets]);

  const handleDelete = useCallback(async (name: string) => {
    await deleteAsset(name);
    setThumbnails((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
    if (previewAsset?.name === name) {
      setPreviewAsset(null);
    }
  }, [deleteAsset, previewAsset]);

  const handleViewModeChange = (
    _: React.MouseEvent<HTMLElement>,
    nextMode: 'grid' | 'list' | null,
  ) => {
    if (nextMode) {
      setViewMode(nextMode);
      localStorage.setItem('asset_view_mode', nextMode);
    }
  };

  // 即時搜尋過濾
  const filteredAssets = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return assets;
    return assets.filter((a) => a.name.toLowerCase().includes(q));
  }, [assets, searchQuery]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 頁籤切換 */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab icon={<CropIcon />} iconPosition="start" label="模板截取" />
          <Tab icon={<ImageIcon />} iconPosition="start" label={`已存模板 (${assets.length})`} />
        </Tabs>
      </Box>

      {/* 模板截取工具 */}
      {tab === 0 && (
        <Box sx={{ flex: 1, overflow: 'hidden' }}>
          <TemplateCapturer />
        </Box>
      )}

      {/* 已存模板列表 */}
      {tab === 1 && (
        <Box sx={{ flex: 1, overflow: 'auto', p: 3 }}>
          {/* 工具列排版：標題 + 計數 ── 搜尋 + 呈現切換 + 重新整理 */}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              mb: 2.5,
              flexWrap: 'wrap',
              gap: 1.5,
            }}
          >
            {/* 左側：標題與數量標籤 */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
                🖼️ 已存模板
              </Typography>
              <Chip
                size="small"
                label={
                  searchQuery.trim()
                    ? `找到 ${filteredAssets.length} / 共 ${assets.length}`
                    : `共 ${assets.length} 個`
                }
                color={searchQuery.trim() ? 'primary' : 'default'}
                variant="outlined"
                sx={{ fontSize: 12, height: 24 }}
              />
            </Box>

            {/* 右側：搜尋欄位 + 呈現方式切換 + 重新整理按鈕 */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              {/* 搜尋欄位 */}
              <TextField
                size="small"
                placeholder="搜尋模板名稱..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                slotProps={{
                  input: {
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                      </InputAdornment>
                    ),
                    endAdornment: searchQuery ? (
                      <InputAdornment position="end">
                        <IconButton
                          size="small"
                          onClick={() => setSearchQuery('')}
                          edge="end"
                          aria-label="清除搜尋"
                        >
                          <ClearIcon fontSize="small" />
                        </IconButton>
                      </InputAdornment>
                    ) : null,
                  },
                }}
                sx={{
                  width: { xs: 180, sm: 240 },
                  bgcolor: 'background.paper',
                  borderRadius: 1,
                  '& .MuiOutlinedInput-root': {
                    height: 36,
                    fontSize: 13,
                  },
                }}
              />

              {/* 呈現方式切換 (網格 / 列表) */}
              <ToggleButtonGroup
                size="small"
                value={viewMode}
                exclusive
                onChange={handleViewModeChange}
                aria-label="呈現方式"
                sx={{ height: 36 }}
              >
                <ToggleButton value="grid" aria-label="網格圖示">
                  <Tooltip title="網格圖示" arrow>
                    <ViewModuleIcon fontSize="small" />
                  </Tooltip>
                </ToggleButton>
                <ToggleButton value="list" aria-label="清單列表">
                  <Tooltip title="詳細列表" arrow>
                    <ViewListIcon fontSize="small" />
                  </Tooltip>
                </ToggleButton>
              </ToggleButtonGroup>

              {/* 重新整理 */}
              <Button
                size="small"
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={handleRefresh}
                disabled={loadingThumbs}
                sx={{ height: 36, whiteSpace: 'nowrap' }}
              >
                {loadingThumbs ? '載入中...' : '重新整理'}
              </Button>
            </Box>
          </Box>

          {/* 無資料狀態 */}
          {assets.length === 0 ? (
            <Paper sx={{ p: 6, textAlign: 'center', border: '2px dashed', borderColor: 'divider' }}>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                尚無模板圖片
              </Typography>
              <Button variant="outlined" onClick={() => setTab(0)} startIcon={<CropIcon />}>
                前往截取模板
              </Button>
            </Paper>
          ) : filteredAssets.length === 0 ? (
            /* 搜尋無符合項目 */
            <Paper sx={{ p: 6, textAlign: 'center', border: '1px dashed', borderColor: 'divider' }}>
              <Typography color="text.secondary" sx={{ mb: 1.5 }}>
                找不到符合「{searchQuery}」的模板
              </Typography>
              <Button size="small" variant="text" onClick={() => setSearchQuery('')}>
                清除搜尋條件
              </Button>
            </Paper>
          ) : viewMode === 'grid' ? (
            /* ══════ 模式 1: 網格圖示視圖 ══════ */
            <Grid container spacing={2}>
              {filteredAssets.map((asset) => (
                <Grid size={{ xs: 6, sm: 4, md: 3, lg: 2 }} key={asset.name}>
                  <Card
                    sx={{
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: 'divider',
                      transition: 'transform 0.15s, box-shadow 0.15s',
                      '&:hover': {
                        transform: 'translateY(-2px)',
                        boxShadow: '0 4px 20px rgba(99,102,241,0.15)',
                      },
                    }}
                  >
                    {/* 縮圖區域 */}
                    <Box
                      onClick={() => thumbnails[asset.name] && setPreviewAsset(asset)}
                      sx={{
                        height: 120,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        overflow: 'hidden',
                        position: 'relative',
                        cursor: thumbnails[asset.name] ? 'zoom-in' : 'default',
                        ...CHECKERBOARD_BG,
                      }}
                    >
                      {thumbnails[asset.name] ? (
                        <img
                          src={thumbnails[asset.name]}
                          alt={asset.name}
                          style={{
                            maxWidth: '100%',
                            maxHeight: '100%',
                            objectFit: 'contain',
                            imageRendering: 'pixelated',
                          }}
                        />
                      ) : loadingThumbs ? (
                        <Skeleton
                          variant="rectangular"
                          width="80%"
                          height="80%"
                          sx={{ bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}
                        />
                      ) : (
                        <BrokenImageIcon sx={{ fontSize: 32, color: '#475569' }} />
                      )}
                    </Box>

                    <CardActions sx={{ justifyContent: 'space-between', px: 1, py: 0.5 }}>
                      <Box sx={{ minWidth: 0, flex: 1, mr: 0.5 }}>
                        <Tooltip title={asset.name} placement="top" arrow>
                          <Typography
                            variant="caption"
                            sx={{
                              fontFamily: 'monospace',
                              fontWeight: 500,
                              display: 'block',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {asset.name}
                          </Typography>
                        </Tooltip>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                          {formatBytes(asset.size)}
                        </Typography>
                      </Box>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleDelete(asset.name)}
                        title="刪除"
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          ) : (
            /* ══════ 模式 2: 詳細列表視圖 ══════ */
            <TableContainer
              component={Paper}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                overflow: 'hidden',
              }}
            >
              <Table size="small">
                <TableHead sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                  <TableRow>
                    <TableCell width={70} sx={{ fontWeight: 'bold' }}>預覽</TableCell>
                    <TableCell sx={{ fontWeight: 'bold' }}>模板名稱</TableCell>
                    <TableCell width={140} sx={{ fontWeight: 'bold' }}>大小</TableCell>
                    <TableCell width={110} align="right" sx={{ fontWeight: 'bold' }}>操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredAssets.map((asset) => (
                    <TableRow key={asset.name} hover>
                      {/* 小縮圖 */}
                      <TableCell sx={{ py: 0.8 }}>
                        <Box
                          onClick={() => thumbnails[asset.name] && setPreviewAsset(asset)}
                          sx={{
                            width: 44,
                            height: 44,
                            borderRadius: 1,
                            overflow: 'hidden',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: thumbnails[asset.name] ? 'zoom-in' : 'default',
                            border: '1px solid',
                            borderColor: 'divider',
                            ...CHECKERBOARD_BG,
                          }}
                        >
                          {thumbnails[asset.name] ? (
                            <img
                              src={thumbnails[asset.name]}
                              alt={asset.name}
                              style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'contain',
                                imageRendering: 'pixelated',
                              }}
                            />
                          ) : loadingThumbs ? (
                            <Skeleton variant="rectangular" width={32} height={32} />
                          ) : (
                            <BrokenImageIcon sx={{ fontSize: 20, color: '#475569' }} />
                          )}
                        </Box>
                      </TableCell>

                      {/* 模板名稱 */}
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: 13, fontWeight: 500 }}>
                        {asset.name}
                      </TableCell>

                      {/* 檔案大小 */}
                      <TableCell sx={{ color: 'text.secondary', fontSize: 12 }}>
                        {formatBytes(asset.size)}
                      </TableCell>

                      {/* 操作 */}
                      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                        <Tooltip title="預覽大圖" arrow>
                          <span>
                            <IconButton
                              size="small"
                              onClick={() => thumbnails[asset.name] && setPreviewAsset(asset)}
                              disabled={!thumbnails[asset.name]}
                              sx={{ mr: 0.5 }}
                            >
                              <ZoomInIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title="刪除模板" arrow>
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleDelete(asset.name)}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}

      {/* ══════ 大圖預覽 Dialog ══════ */}
      <Dialog
        open={Boolean(previewAsset)}
        onClose={() => setPreviewAsset(null)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ fontFamily: 'monospace', fontWeight: 'bold' }}>
            🔍 {previewAsset?.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {previewAsset ? formatBytes(previewAsset.size) : ''}
          </Typography>
        </DialogTitle>
        <DialogContent
          dividers
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            p: 3,
            minHeight: 240,
            ...CHECKERBOARD_BG,
          }}
        >
          {previewAsset && thumbnails[previewAsset.name] ? (
            <img
              src={thumbnails[previewAsset.name]}
              alt={previewAsset.name}
              style={{
                maxWidth: '100%',
                maxHeight: '65vh',
                objectFit: 'contain',
                imageRendering: 'pixelated',
                boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
              }}
            />
          ) : (
            <BrokenImageIcon sx={{ fontSize: 48, color: '#64748b' }} />
          )}
        </DialogContent>
        <DialogActions sx={{ px: 2.5, py: 1.5 }}>
          <Button onClick={() => setPreviewAsset(null)}>關閉</Button>
          {previewAsset && (
            <Button
              color="error"
              variant="outlined"
              startIcon={<DeleteIcon />}
              onClick={() => handleDelete(previewAsset.name)}
            >
              刪除模板
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AssetManager;

