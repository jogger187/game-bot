// 資源管理頁面 — 模板截取 + 已存模板列表
import { useEffect, useState, useCallback } from 'react';
import {
  Box, Typography, Paper, Grid, Card, CardActions, Button,
  IconButton, Tabs, Tab, Skeleton, Tooltip,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import CropIcon from '@mui/icons-material/Crop';
import ImageIcon from '@mui/icons-material/Image';
import BrokenImageIcon from '@mui/icons-material/BrokenImage';
import { useAppStore } from '../stores/appStore';
import TemplateCapturer from '../components/TemplateCapturer';
import * as api from '../utils/tauri';

const AssetManager = () => {
  const { assets, fetchAssets, deleteAsset } = useAppStore();
  const [tab, setTab] = useState(0);
  // 縮圖快取: name -> base64 data URL
  const [thumbnails, setThumbnails] = useState<Record<string, string>>({});
  const [loadingThumbs, setLoadingThumbs] = useState(false);

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
  }, [deleteAsset]);

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
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h5" sx={{ fontWeight: 'bold' }}>🖼️ 已存模板</Typography>
            <Button startIcon={<RefreshIcon />} onClick={handleRefresh} disabled={loadingThumbs}>
              {loadingThumbs ? '載入中...' : '重新整理'}
            </Button>
          </Box>

          {assets.length === 0 ? (
            <Paper sx={{ p: 6, textAlign: 'center', border: '2px dashed', borderColor: 'divider' }}>
              <Typography color="text.secondary" sx={{ mb: 2 }}>尚無模板圖片</Typography>
              <Button variant="outlined" onClick={() => setTab(0)} startIcon={<CropIcon />}>
                前往截取模板
              </Button>
            </Paper>
          ) : (
            <Grid container spacing={2}>
              {assets.map((asset) => (
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
                      sx={{
                        height: 120,
                        bgcolor: '#1e293b',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        overflow: 'hidden',
                        position: 'relative',
                        // 棋盤格背景 — 方便看透明區域
                        backgroundImage:
                          'linear-gradient(45deg, #334155 25%, transparent 25%), ' +
                          'linear-gradient(-45deg, #334155 25%, transparent 25%), ' +
                          'linear-gradient(45deg, transparent 75%, #334155 75%), ' +
                          'linear-gradient(-45deg, transparent 75%, #334155 75%)',
                        backgroundSize: '16px 16px',
                        backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0px',
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

                    <CardActions sx={{ justifyContent: 'space-between', px: 1 }}>
                      <Tooltip title={asset.name} placement="top" arrow>
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{
                            fontFamily: 'monospace',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: 100,
                          }}
                        >
                          {asset.name}
                        </Typography>
                      </Tooltip>
                      <IconButton size="small" color="error" onClick={() => handleDelete(asset.name)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
      )}
    </Box>
  );
};

export default AssetManager;

