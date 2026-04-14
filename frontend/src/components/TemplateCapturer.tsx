// 模板截取工具 — 從裝置截圖上框選區域並命名儲存
import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Box, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Typography, Paper, Chip, IconButton,
} from '@mui/material';
import CropIcon from '@mui/icons-material/Crop';
import CameraAltIcon from '@mui/icons-material/CameraAlt';
import SaveIcon from '@mui/icons-material/Save';
import RefreshIcon from '@mui/icons-material/Refresh';
import CloseIcon from '@mui/icons-material/Close';
import { useAppStore } from '../stores/appStore';
import * as api from '../utils/tauri';

interface CropRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

const TemplateCapturer = () => {
  const { device, addLog, fetchAssets, connectDevice } = useAppStore();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // 截圖狀態
  const [screenshotSrc, setScreenshotSrc] = useState<string | null>(null);
  const [, setImgSize] = useState({ w: 0, h: 0 });
  const [scale, setScale] = useState(1);
  const [loading, setLoading] = useState(false);

  // 框選狀態
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState({ x: 0, y: 0 });
  const [cropRect, setCropRect] = useState<CropRect | null>(null);

  // 命名對話框
  const [nameOpen, setNameOpen] = useState(false);
  const [templateName, setTemplateName] = useState('');

  // 擷取截圖
  const captureScreenshot = useCallback(async () => {
    setLoading(true);
    setCropRect(null);
    try {
      const result = await api.screenshotCapture();
      if (result.image_b64) {
        const src = result.image_b64.startsWith('data:')
          ? result.image_b64
          : `data:image/jpeg;base64,${result.image_b64}`;
        setScreenshotSrc(src);
        setImgSize({ w: result.width, h: result.height });
        addLog('📸 已擷取裝置截圖');
      } else {
        // Mock 模式：生成測試圖片
        generateMockScreenshot();
      }
    } catch {
      // Mock fallback
      generateMockScreenshot();
      addLog('📸 [Mock] 已生成模擬截圖');
    } finally {
      setLoading(false);
    }
  }, [addLog]);

  // 生成 Mock 截圖
  const generateMockScreenshot = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 1920;
    canvas.height = 1080;
    const ctx = canvas.getContext('2d')!;

    // 背景
    const gradient = ctx.createLinearGradient(0, 0, 1920, 1080);
    gradient.addColorStop(0, '#1a1a2e');
    gradient.addColorStop(1, '#16213e');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 1920, 1080);

    // 模擬遊戲元素
    ctx.fillStyle = '#e94560';
    ctx.fillRect(800, 850, 320, 80);
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 32px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('START', 960, 900);

    ctx.fillStyle = '#0f3460';
    ctx.fillRect(50, 50, 200, 60);
    ctx.fillStyle = '#FFD700';
    ctx.font = '24px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('💰 12,345', 70, 90);

    ctx.fillStyle = '#533483';
    ctx.fillRect(50, 130, 200, 60);
    ctx.fillStyle = '#00ff88';
    ctx.fillText('❤️ HP: 85%', 70, 170);

    // 隨機圖標
    const icons = ['⚔️', '🛡️', '🏆', '⭐', '🎁'];
    icons.forEach((icon, i) => {
      ctx.font = '48px sans-serif';
      ctx.fillText(icon, 400 + i * 220, 500);
    });

    ctx.font = '16px monospace';
    ctx.fillStyle = '#666';
    ctx.fillText('Mock Game Screenshot - 請框選要識別的物件區域', 650, 1060);

    setScreenshotSrc(canvas.toDataURL('image/jpeg', 0.9));
    setImgSize({ w: 1920, h: 1080 });
  };

  // 繪製 Canvas（截圖 + 框選框）
  useEffect(() => {
    if (!screenshotSrc || !canvasRef.current || !containerRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d')!;
    const img = new Image();

    img.onload = () => {
      // 計算縮放比例讓圖片適合容器
      const containerWidth = containerRef.current!.clientWidth;
      const containerHeight = containerRef.current!.clientHeight - 10;
      const scaleX = containerWidth / img.width;
      const scaleY = containerHeight / img.height;
      const s = Math.min(scaleX, scaleY, 1);
      setScale(s);

      canvas.width = img.width * s;
      canvas.height = img.height * s;

      // 繪製截圖
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // 繪製框選框
      if (cropRect) {
        const { x, y, w, h } = cropRect;

        // 半透明遮罩
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // 清除選取區域（顯示原圖）
        ctx.clearRect(x * s, y * s, w * s, h * s);
        ctx.drawImage(
          img,
          x, y, w, h,
          x * s, y * s, w * s, h * s
        );

        // 框選邊框
        ctx.strokeStyle = '#6366f1';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 3]);
        ctx.strokeRect(x * s, y * s, w * s, h * s);
        ctx.setLineDash([]);

        // 尺寸標籤
        ctx.fillStyle = '#6366f1';
        ctx.fillRect(x * s, y * s - 22, 120, 20);
        ctx.fillStyle = '#fff';
        ctx.font = '12px monospace';
        ctx.fillText(`${w} × ${h}`, x * s + 4, y * s - 7);
      }
    };

    img.src = screenshotSrc;
  }, [screenshotSrc, cropRect, scale]);

  // 滑鼠事件：開始框選
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.round((e.clientX - rect.left) / scale);
    const y = Math.round((e.clientY - rect.top) / scale);
    setStartPoint({ x, y });
    setIsDrawing(true);
    setCropRect(null);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.round((e.clientX - rect.left) / scale);
    const y = Math.round((e.clientY - rect.top) / scale);

    const cropX = Math.min(startPoint.x, x);
    const cropY = Math.min(startPoint.y, y);
    const cropW = Math.abs(x - startPoint.x);
    const cropH = Math.abs(y - startPoint.y);

    if (cropW > 5 && cropH > 5) {
      setCropRect({ x: cropX, y: cropY, w: cropW, h: cropH });
    }
  };

  const handleMouseUp = () => {
    setIsDrawing(false);
  };

  // 儲存模板
  const handleSaveTemplate = async () => {
    if (!cropRect || !templateName.trim() || !screenshotSrc) return;

    // 從原圖裁切指定區域
    const img = new Image();
    img.src = screenshotSrc;

    await new Promise<void>((resolve) => {
      img.onload = () => {
        const cropCanvas = document.createElement('canvas');
        cropCanvas.width = cropRect.w;
        cropCanvas.height = cropRect.h;
        const ctx = cropCanvas.getContext('2d')!;
        ctx.drawImage(
          img,
          cropRect.x, cropRect.y, cropRect.w, cropRect.h,
          0, 0, cropRect.w, cropRect.h,
        );

        const b64 = cropCanvas.toDataURL('image/png');
        const name = templateName.trim().endsWith('.png')
          ? templateName.trim()
          : `${templateName.trim()}.png`;

        api.assetSaveCrop({ name, image_b64: b64 })
          .then(() => {
            addLog(`✅ 已儲存模板: ${name} (${cropRect.w}×${cropRect.h})`);
            fetchAssets();
            setNameOpen(false);
            setTemplateName('');
            setCropRect(null);
          })
          .catch((err) => addLog(`❌ 儲存失敗: ${err}`));

        resolve();
      };
    });
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 工具列 */}
      <Paper
        sx={{
          p: 1.5, display: 'flex', alignItems: 'center', gap: 1,
          borderRadius: 0, borderBottom: '1px solid', borderColor: 'divider',
        }}
      >
        <CropIcon sx={{ color: 'primary.main', mr: 1 }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mr: 2 }}>模板截取工具</Typography>

        <Button
          size="small"
          variant="contained"
          startIcon={<CameraAltIcon />}
          onClick={captureScreenshot}
          disabled={loading || !device?.connected}
        >
          {loading ? '擷取中...' : '擷取截圖'}
        </Button>

        {!device?.connected && (
          <Typography variant="caption" color="warning.main">需先連接裝置</Typography>
        )}

        {screenshotSrc && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={captureScreenshot}
          >
            重新擷取
          </Button>
        )}

        {cropRect && (
          <>
            <Chip
              label={`選取: ${cropRect.w} × ${cropRect.h}`}
              size="small"
              color="primary"
              variant="outlined"
            />
            <Button
              size="small"
              variant="contained"
              color="success"
              startIcon={<SaveIcon />}
              onClick={() => setNameOpen(true)}
            >
              儲存為模板
            </Button>
          </>
        )}

        {device?.connected && (
          <Chip
            label={`已連線: ${device.serial}`}
            size="small"
            color="success"
            variant="outlined"
            sx={{ ml: 'auto' }}
          />
        )}
      </Paper>

      {/* 截圖展示區域 */}
      <Box
        ref={containerRef}
        sx={{
          flex: 1,
          overflow: 'auto',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: '#0a0f1a',
          position: 'relative',
        }}
      >
        {screenshotSrc ? (
          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{
              cursor: 'crosshair',
              border: '1px solid #334155',
              borderRadius: 4,
            }}
          />
        ) : !device?.connected ? (
          /* 未連線提示 */
          <Box sx={{ textAlign: 'center' }}>
            <Box sx={{ fontSize: 64, mb: 2 }}>📱</Box>
            <Typography color="text.secondary" variant="h6" sx={{ mb: 1 }}>
              請先連接裝置
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              需要連線到模擬器或手機才能擷取遊戲畫面
            </Typography>
            <Button variant="contained" onClick={() => connectDevice()}>
              連接裝置
            </Button>
          </Box>
        ) : (
          /* 已連線但尚未截圖 */
          <Box sx={{ textAlign: 'center' }}>
            <CameraAltIcon sx={{ fontSize: 80, color: '#334155', mb: 2 }} />
            <Typography color="text.secondary" sx={{ mb: 1 }}>
              裝置已連線，點擊「擷取截圖」取得裝置畫面
            </Typography>
            <Typography variant="caption" color="text.secondary">
              然後在截圖上拖拽框選要識別的物件區域
            </Typography>
          </Box>
        )}
      </Box>

      {/* 命名對話框 */}
      <Dialog open={nameOpen} onClose={() => setNameOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          儲存識別模板
          <IconButton size="small" onClick={() => setNameOpen(false)}><CloseIcon /></IconButton>
        </DialogTitle>
        <DialogContent>
          {cropRect && (
            <Box sx={{ mb: 2, p: 1, bgcolor: '#0f172a', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                裁切區域: {cropRect.x},{cropRect.y} — {cropRect.w} × {cropRect.h} px
              </Typography>
            </Box>
          )}
          <TextField
            autoFocus
            fullWidth
            label="模板名稱"
            placeholder="例如: btn_start, icon_gold, hp_bar"
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSaveTemplate()}
            helperText="此名稱將用於腳本中的圖像比對條件"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNameOpen(false)}>取消</Button>
          <Button
            variant="contained"
            color="success"
            disabled={!templateName.trim()}
            onClick={handleSaveTemplate}
            startIcon={<SaveIcon />}
          >
            儲存模板
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TemplateCapturer;
