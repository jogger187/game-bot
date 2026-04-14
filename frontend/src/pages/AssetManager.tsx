// 資源管理頁面 — 模板截取 + 已存模板列表
import { useEffect, useState } from 'react';
import {
  Box, Typography, Paper, Grid, Card, CardMedia, CardActions, Button,
  IconButton, Tabs, Tab,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import CropIcon from '@mui/icons-material/Crop';
import ImageIcon from '@mui/icons-material/Image';
import { useAppStore } from '../stores/appStore';
import TemplateCapturer from '../components/TemplateCapturer';

const AssetManager = () => {
  const { assets, fetchAssets, deleteAsset } = useAppStore();
  const [tab, setTab] = useState(0);

  useEffect(() => { fetchAssets(); }, [fetchAssets]);

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
            <Button startIcon={<RefreshIcon />} onClick={fetchAssets}>重新整理</Button>
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
                  <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                    <CardMedia
                      sx={{ height: 100, bgcolor: '#334155', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                      <Typography variant="caption" color="text.secondary">📷 {asset.name}</Typography>
                    </CardMedia>
                    <CardActions sx={{ justifyContent: 'space-between', px: 1 }}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 100 }}
                      >
                        {asset.name}
                      </Typography>
                      <IconButton size="small" color="error" onClick={() => deleteAsset(asset.name)}>
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
