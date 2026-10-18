// 模板選擇器元件 — 點擊彈出 Dialog，支援文字搜尋過濾與縮圖預覽
import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box, Typography, Button, IconButton, TextField, InputAdornment,
  Dialog, DialogTitle, DialogContent, DialogActions, Chip, Tooltip,
  Skeleton, Paper,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import ClearIcon from '@mui/icons-material/Clear';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ImageIcon from '@mui/icons-material/Image';
import BrokenImageIcon from '@mui/icons-material/BrokenImage';
import AddPhotoAlternateIcon from '@mui/icons-material/AddPhotoAlternate';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAppStore } from '../stores/appStore';
import * as api from '../utils/tauri';

// 模組層級縮圖快取，避免重複請求
const thumbnailCache = new Map<string, string>();

/** 格式化檔案大小 */
const formatSize = (bytes?: number): string => {
  if (bytes === undefined || bytes === null || bytes === 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

/** 棋盤格透明背景樣式 */
const CHECKERBOARD_BG = {
  backgroundColor: '#1e293b',
  backgroundImage:
    'linear-gradient(45deg, #334155 25%, transparent 25%), ' +
    'linear-gradient(-45deg, #334155 25%, transparent 25%), ' +
    'linear-gradient(45deg, transparent 75%, #334155 75%), ' +
    'linear-gradient(-45deg, transparent 75%, #334155 75%)',
  backgroundSize: '14px 14px',
  backgroundPosition: '0 0, 0 7px, 7px -7px, -7px 0px',
};

interface Props {
  value: string;
  onChange: (value: string) => void;
  label?: string;
}

export const TemplateSelect = ({ value, onChange, label = '模板圖片' }: Props) => {
  const { assets, fetchAssets } = useAppStore();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [thumbnails, setThumbnails] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    thumbnailCache.forEach((v, k) => {
      initial[k] = v;
    });
    return initial;
  });
  const [loadingThumbs, setLoadingThumbs] = useState(false);
  const [selectedThumb, setSelectedThumb] = useState<string | null>(() => thumbnailCache.get(value) || null);

  // 當前選取的資源資訊
  const currentAsset = useMemo(() => assets.find((a) => a.name === value), [assets, value]);

  // 當 value 變更時載入對應縮圖
  useEffect(() => {
    if (!value) {
      setSelectedThumb(null);
      return;
    }
    if (thumbnailCache.has(value)) {
      setSelectedThumb(thumbnailCache.get(value) || null);
      return;
    }
    let active = true;
    api
      .assetRead(value)
      .then((b64) => {
        thumbnailCache.set(value, b64);
        if (active) setSelectedThumb(b64);
      })
      .catch(() => {
        if (active) setSelectedThumb(null);
      });
    return () => {
      active = false;
    };
  }, [value]);

  // 打開 Dialog 時重新確認資源並批次載入縮圖
  useEffect(() => {
    if (!open) return;
    fetchAssets();
  }, [open, fetchAssets]);

  // 載入缺少的縮圖
  useEffect(() => {
    if (!open || assets.length === 0) return;
    const missing = assets.filter((a) => !thumbnailCache.has(a.name));
    if (missing.length === 0) return;

    let active = true;
    setLoadingThumbs(true);

    Promise.allSettled(
      missing.map(async (asset) => {
        try {
          const b64 = await api.assetRead(asset.name);
          thumbnailCache.set(asset.name, b64);
          if (active) {
            setThumbnails((prev) => ({ ...prev, [asset.name]: b64 }));
          }
        } catch {
          // 忽略失敗項目
        }
      })
    ).finally(() => {
      if (active) setLoadingThumbs(false);
    });

    return () => {
      active = false;
    };
  }, [open, assets]);

  // 文字過濾列表
  const filteredAssets = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return assets;
    return assets.filter((a) => a.name.toLowerCase().includes(q));
  }, [assets, search]);

  const handleSelect = useCallback(
    (name: string) => {
      onChange(name);
      setOpen(false);
    },
    [onChange]
  );

  const handleClear = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onChange('');
    },
    [onChange]
  );

  return (
    <Box sx={{ mb: 1.5 }}>
      {/* 標籤 */}
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ display: 'block', mb: 0.5, fontWeight: 500 }}
      >
        {label}
      </Typography>

      {/* 外觀觸發區 (屬性面板內) */}
      {value ? (
        <Paper
          onClick={() => setOpen(true)}
          sx={{
            p: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1.2,
            border: '1px solid',
            borderColor: 'primary.dark',
            bgcolor: 'rgba(99, 102, 241, 0.05)',
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              borderColor: 'primary.main',
              bgcolor: 'rgba(99, 102, 241, 0.1)',
            },
          }}
        >
          {/* 小縮圖 */}
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: 1,
              overflow: 'hidden',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid #334155',
              ...CHECKERBOARD_BG,
            }}
          >
            {selectedThumb ? (
              <img
                src={selectedThumb}
                alt={value}
                style={{
                  maxWidth: '100%',
                  maxHeight: '100%',
                  objectFit: 'contain',
                  imageRendering: 'pixelated',
                }}
              />
            ) : (
              <ImageIcon sx={{ fontSize: 22, color: 'text.secondary' }} />
            )}
          </Box>

          {/* 模板資訊 */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Tooltip title={value} placement="top" arrow>
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                  fontSize: 12,
                  lineHeight: 1.3,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {value}
              </Typography>
            </Tooltip>
            {currentAsset?.size ? (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                {formatSize(currentAsset.size)}
              </Typography>
            ) : (
              <Typography variant="caption" color="primary.light" sx={{ fontSize: 10 }}>
                點擊更換模板
              </Typography>
            )}
          </Box>

          {/* 快速按鈕 */}
          <Tooltip title="更換模板">
            <IconButton size="small" sx={{ p: 0.5, color: 'text.secondary' }}>
              <SwapHorizIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="清除選擇">
            <IconButton
              size="small"
              onClick={handleClear}
              sx={{ p: 0.5, color: 'text.secondary', '&:hover': { color: 'error.main' } }}
            >
              <CloseIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Paper>
      ) : (
        <Paper
          onClick={() => setOpen(true)}
          sx={{
            p: 1.2,
            border: '1px dashed #475569',
            borderRadius: 1.5,
            bgcolor: 'background.paper',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 1,
            cursor: 'pointer',
            transition: 'all 0.2s',
            '&:hover': {
              borderColor: 'primary.main',
              bgcolor: 'rgba(99, 102, 241, 0.08)',
            },
          }}
        >
          <AddPhotoAlternateIcon sx={{ fontSize: 20, color: 'primary.light' }} />
          <Typography variant="body2" color="text.secondary" sx={{ fontSize: 12 }}>
            點擊選擇圖片模板...
          </Typography>
        </Paper>
      )}

      {/* 選擇模板 Dialog */}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        maxWidth="md"
        fullWidth
        slotProps={{
          paper: {
            sx: {
              bgcolor: 'background.paper',
              backgroundImage: 'none',
              maxHeight: '85vh',
              display: 'flex',
              flexDirection: 'column',
              borderRadius: 2,
            },
          },
        }}
      >
        {/* 標題欄 */}
        <DialogTitle
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            pb: 1,
            pt: 2,
            px: 2.5,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ImageIcon sx={{ color: 'primary.main', fontSize: 24 }} />
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              選擇圖片模板
            </Typography>
            <Chip
              label={`共 ${assets.length} 個模板`}
              size="small"
              sx={{ height: 22, fontSize: 11, bgcolor: 'rgba(99, 102, 241, 0.15)', color: 'primary.light' }}
            />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Tooltip title="重新載入模板列表">
              <IconButton size="small" onClick={() => fetchAssets()} disabled={loadingThumbs}>
                <RefreshIcon sx={{ fontSize: 20 }} />
              </IconButton>
            </Tooltip>
            <IconButton size="small" onClick={() => setOpen(false)}>
              <CloseIcon sx={{ fontSize: 20 }} />
            </IconButton>
          </Box>
        </DialogTitle>

        {/* 內容區 */}
        <DialogContent
          sx={{
            p: 2.5,
            pt: 1,
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            overflow: 'hidden',
          }}
        >
          {/* 針對文字的搜尋輸入框 */}
          <TextField
            fullWidth
            size="small"
            autoFocus
            placeholder="搜尋模板名稱 (例如：btn_start, icon...)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                  </InputAdornment>
                ),
                endAdornment: search ? (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setSearch('')}>
                      <ClearIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </InputAdornment>
                ) : null,
              },
            }}
          />

          {/* 搜尋結果提示 */}
          {search && (
            <Typography variant="caption" color="text.secondary">
              搜尋「{search}」：找到 {filteredAssets.length} / {assets.length} 個相符模板
            </Typography>
          )}

          {/* 模板網格展示區 */}
          <Box
            sx={{
              flex: 1,
              overflowY: 'auto',
              minHeight: 280,
              maxHeight: '55vh',
              pr: 0.5,
            }}
          >
            {assets.length === 0 ? (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  py: 6,
                  border: '2px dashed #334155',
                  borderRadius: 2,
                }}
              >
                <ImageIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
                <Typography variant="body1" color="text.secondary" sx={{ fontWeight: 'bold' }}>
                  尚無模板圖片
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                  請至「資源管理」頁面截取或新增圖片模板
                </Typography>
              </Box>
            ) : filteredAssets.length === 0 ? (
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  py: 6,
                  border: '1px dashed #334155',
                  borderRadius: 2,
                }}
              >
                <SearchIcon sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
                <Typography variant="body2" color="text.secondary">
                  找不到符合「{search}」的模板圖片
                </Typography>
                <Button size="small" sx={{ mt: 1.5 }} onClick={() => setSearch('')}>
                  清除搜尋字詞
                </Button>
              </Box>
            ) : (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: 'repeat(2, 1fr)',
                    sm: 'repeat(3, 1fr)',
                    md: 'repeat(4, 1fr)',
                  },
                  gap: 1.5,
                }}
              >
                {filteredAssets.map((asset) => {
                  const isSelected = asset.name === value;
                  const thumb = thumbnails[asset.name] || thumbnailCache.get(asset.name);

                  return (
                    <Paper
                      key={asset.name}
                      onClick={() => handleSelect(asset.name)}
                      sx={{
                        position: 'relative',
                        border: '2px solid',
                        borderColor: isSelected ? 'primary.main' : '#334155',
                        bgcolor: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'background.default',
                        borderRadius: 2,
                        overflow: 'hidden',
                        cursor: 'pointer',
                        transition: 'transform 0.15s, border-color 0.15s, box-shadow 0.15s',
                        '&:hover': {
                          transform: 'translateY(-2px)',
                          borderColor: isSelected ? 'primary.light' : '#818cf8',
                          boxShadow: '0 6px 16px rgba(99,102,241,0.25)',
                        },
                      }}
                    >
                      {/* 選中狀態打勾標記 */}
                      {isSelected && (
                        <CheckCircleIcon
                          sx={{
                            position: 'absolute',
                            top: 6,
                            right: 6,
                            color: 'primary.light',
                            bgcolor: '#1e293b',
                            borderRadius: '50%',
                            fontSize: 22,
                            zIndex: 3,
                          }}
                        />
                      )}

                      {/* 縮圖區域 */}
                      <Box
                        sx={{
                          height: 110,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          overflow: 'hidden',
                          ...CHECKERBOARD_BG,
                        }}
                      >
                        {thumb ? (
                          <img
                            src={thumb}
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
                            width="75%"
                            height="75%"
                            sx={{ bgcolor: 'rgba(255,255,255,0.06)', borderRadius: 1 }}
                          />
                        ) : (
                          <BrokenImageIcon sx={{ fontSize: 32, color: '#475569' }} />
                        )}
                      </Box>

                      {/* 檔名與大小 */}
                      <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                        <Tooltip title={asset.name} placement="top" arrow>
                          <Typography
                            variant="caption"
                            sx={{
                              display: 'block',
                              fontFamily: 'monospace',
                              fontWeight: isSelected ? 'bold' : 500,
                              color: isSelected ? 'primary.light' : 'text.primary',
                              fontSize: 11,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {asset.name}
                          </Typography>
                        </Tooltip>
                        {asset.size ? (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{ fontSize: 10, display: 'block', mt: 0.2 }}
                          >
                            {formatSize(asset.size)}
                          </Typography>
                        ) : null}
                      </Box>
                    </Paper>
                  );
                })}
              </Box>
            )}
          </Box>
        </DialogContent>

        {/* 底部操作按鈕 */}
        <DialogActions
          sx={{
            px: 2.5,
            py: 1.5,
            borderTop: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          <Box>
            {value && (
              <Button
                color="error"
                size="small"
                onClick={() => {
                  onChange('');
                  setOpen(false);
                }}
              >
                清除目前選擇
              </Button>
            )}
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button variant="outlined" size="small" onClick={() => setOpen(false)}>
              關閉
            </Button>
          </Box>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TemplateSelect;
