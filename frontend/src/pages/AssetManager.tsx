// 模板圖片資源管理頁面
import { useEffect } from 'react';
import { Box, Typography, Paper, Grid, Card, CardMedia, CardActions, Button, IconButton } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAppStore } from '../stores/appStore';

const AssetManager = () => {
  const { assets, fetchAssets, deleteAsset } = useAppStore();

  useEffect(() => { fetchAssets(); }, [fetchAssets]);

  return (
    <Box sx={{ p: 4, overflow: 'auto', height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>🖼️ 資源管理</Typography>
        <Button startIcon={<RefreshIcon />} onClick={fetchAssets}>重新整理</Button>
      </Box>

      {assets.length === 0 ? (
        <Paper sx={{ p: 6, textAlign: 'center', border: '2px dashed', borderColor: 'divider' }}>
          <Typography color="text.secondary" sx={{ mb: 2 }}>尚無模板圖片</Typography>
          <Typography variant="body2" color="text.secondary">
            請透過儀表板的截圖裁切功能新增模板圖片
          </Typography>
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
                  <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis' }}>
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
  );
};

export default AssetManager;
