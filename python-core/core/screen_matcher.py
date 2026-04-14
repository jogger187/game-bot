"""螢幕模板比對 — 用 OpenCV 在截圖中找到目標 UI 元素

支援:
- 標準模板比對 (TM_CCOEFF_NORMED)
- 多尺度模板比對 (自動 resize 0.7x~1.3x)
- 灰階比對模式 (色差不敏感場景)
- Mask 模板比對 (PNG 透明區域忽略)
"""

from __future__ import annotations

import time
from pathlib import Path
from dataclasses import dataclass

import cv2
import numpy as np
from loguru import logger
from PIL import Image


@dataclass
class MatchResult:
    """比對結果"""
    x: int          # 中心點 x
    y: int          # 中心點 y
    confidence: float
    top_left: tuple[int, int]
    bottom_right: tuple[int, int]
    template_name: str
    scale: float = 1.0  # 匹配時的縮放比例

    def __bool__(self) -> bool:
        return self.confidence > 0


class ScreenMatcher:
    """OpenCV 模板比對引擎"""

    def __init__(
        self,
        assets_dir: str | Path = "assets",
        default_threshold: float = 0.85,
        multi_scale: bool = False,
        scale_range: tuple[float, float] = (0.8, 1.2),
        scale_steps: int = 5,
        grayscale: bool = False,
    ):
        self.assets_dir = Path(assets_dir)
        self.default_threshold = default_threshold
        self.multi_scale = multi_scale
        self.scale_range = scale_range
        self.scale_steps = scale_steps
        self.grayscale = grayscale
        self._template_cache: dict[str, np.ndarray] = {}
        self._mask_cache: dict[str, np.ndarray | None] = {}

    def _load_template(self, name: str) -> np.ndarray:
        """載入模板圖片（帶快取）"""
        if name in self._template_cache:
            return self._template_cache[name]

        path = self.assets_dir / name
        if not path.exists():
            raise FileNotFoundError(f"模板不存在: {path}")

        # 讀取含 alpha 通道（如果有）
        tmpl = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if tmpl is None:
            raise ValueError(f"無法讀取模板: {path}")

        # 處理 alpha 通道 → 產生 mask
        mask = None
        if tmpl.shape[-1] == 4:
            alpha = tmpl[:, :, 3]
            mask = alpha  # alpha > 0 的區域才參與比對
            tmpl = tmpl[:, :, :3]  # 去掉 alpha

        self._template_cache[name] = tmpl
        self._mask_cache[name] = mask
        return tmpl

    def _get_mask(self, name: str) -> np.ndarray | None:
        """取得模板的 mask（用於不規則形狀比對）"""
        if name not in self._mask_cache:
            self._load_template(name)
        return self._mask_cache.get(name)

    def _to_bgr(self, screenshot: np.ndarray | Image.Image) -> np.ndarray:
        """轉換為 BGR numpy array"""
        if isinstance(screenshot, Image.Image):
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        return screenshot

    def _to_gray(self, img: np.ndarray) -> np.ndarray:
        """轉灰階"""
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _match_at_scale(
        self,
        screen: np.ndarray,
        template: np.ndarray,
        mask: np.ndarray | None,
        scale: float,
        use_gray: bool,
    ) -> tuple[float, tuple[int, int], int, int]:
        """
        在指定縮放下做模板比對

        Returns:
            (max_val, max_loc, template_w, template_h)
        """
        if scale != 1.0:
            th, tw = template.shape[:2]
            new_w = int(tw * scale)
            new_h = int(th * scale)
            if new_w < 5 or new_h < 5:
                return (0.0, (0, 0), 0, 0)
            tmpl_scaled = cv2.resize(template, (new_w, new_h))
            mask_scaled = cv2.resize(mask, (new_w, new_h)) if mask is not None else None
        else:
            tmpl_scaled = template
            mask_scaled = mask
            new_h, new_w = template.shape[:2]

        if use_gray:
            screen_match = self._to_gray(screen)
            tmpl_match = self._to_gray(tmpl_scaled)
            mask_match = mask_scaled  # mask 本身已是單通道
        else:
            screen_match = screen
            tmpl_match = tmpl_scaled
            mask_match = mask_scaled
            # mask 需要與模板相同通道數
            if mask_match is not None and len(mask_match.shape) == 2 and len(tmpl_match.shape) == 3:
                mask_match = cv2.merge([mask_match] * 3)

        # 檢查模板是否比截圖大
        if tmpl_match.shape[0] > screen_match.shape[0] or tmpl_match.shape[1] > screen_match.shape[1]:
            return (0.0, (0, 0), 0, 0)

        if mask_match is not None:
            result = cv2.matchTemplate(screen_match, tmpl_match, cv2.TM_CCOEFF_NORMED, mask=mask_match)
        else:
            result = cv2.matchTemplate(screen_match, tmpl_match, cv2.TM_CCOEFF_NORMED)

        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        return (max_val, max_loc, new_w, new_h)

    def find(
        self,
        screenshot: np.ndarray | Image.Image,
        template_name: str,
        threshold: float | None = None,
        region: tuple[int, int, int, int] | None = None,
        use_multi_scale: bool | None = None,
        use_grayscale: bool | None = None,
    ) -> MatchResult | None:
        """
        在截圖中尋找模板

        Args:
            screenshot: BGR numpy array 或 PIL Image
            template_name: assets 目錄下的模板檔名
            threshold: 信心門檻，None 則用預設值
            region: (x, y, w, h) 限定搜尋區域（加速比對）
            use_multi_scale: 是否多尺度比對，None 用預設
            use_grayscale: 是否灰階比對，None 用預設

        Returns:
            MatchResult 或 None (找不到)
        """
        threshold = threshold or self.default_threshold
        multi = use_multi_scale if use_multi_scale is not None else self.multi_scale
        gray = use_grayscale if use_grayscale is not None else self.grayscale

        screen = self._to_bgr(screenshot)
        template = self._load_template(template_name)
        mask = self._get_mask(template_name)

        # 限定搜尋區域
        offset_x, offset_y = 0, 0
        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry + rh, rx:rx + rw]
            offset_x, offset_y = rx, ry

        best_val = 0.0
        best_loc = (0, 0)
        best_tw, best_th = 0, 0
        best_scale = 1.0

        if multi:
            # 多尺度搜尋
            scales = np.linspace(self.scale_range[0], self.scale_range[1], self.scale_steps)
            for s in scales:
                val, loc, tw, th = self._match_at_scale(screen, template, mask, s, gray)
                if val > best_val:
                    best_val = val
                    best_loc = loc
                    best_tw, best_th = tw, th
                    best_scale = s
        else:
            best_val, best_loc, best_tw, best_th = self._match_at_scale(
                screen, template, mask, 1.0, gray
            )

        if best_val >= threshold:
            cx = best_loc[0] + best_tw // 2 + offset_x
            cy = best_loc[1] + best_th // 2 + offset_y
            tl = (best_loc[0] + offset_x, best_loc[1] + offset_y)
            br = (tl[0] + best_tw, tl[1] + best_th)

            match = MatchResult(
                x=cx, y=cy,
                confidence=float(best_val),
                top_left=tl,
                bottom_right=br,
                template_name=template_name,
                scale=best_scale,
            )
            logger.debug(
                f"🎯 找到 [{template_name}] 信心={best_val:.3f} "
                f"位置=({cx}, {cy}) 縮放={best_scale:.2f}"
            )
            return match

        logger.debug(f"❌ 找不到 [{template_name}] 最高信心={best_val:.3f} < {threshold}")
        return None

    def find_all(
        self,
        screenshot: np.ndarray | Image.Image,
        template_name: str,
        threshold: float | None = None,
        min_distance: int = 20,
        region: tuple[int, int, int, int] | None = None,
    ) -> list[MatchResult]:
        """
        找出截圖中所有符合的模板位置

        Args:
            min_distance: 兩個結果間的最小距離（避免重複偵測）
            region: (x, y, w, h) 限定搜尋區域
        """
        threshold = threshold or self.default_threshold
        screen = self._to_bgr(screenshot)
        template = self._load_template(template_name)
        mask = self._get_mask(template_name)
        th, tw = template.shape[:2]

        # 限定搜尋區域
        offset_x, offset_y = 0, 0
        if region:
            rx, ry, rw, rh = region
            screen = screen[ry:ry + rh, rx:rx + rw]
            offset_x, offset_y = rx, ry

        use_gray = self.grayscale
        if use_gray:
            screen_match = self._to_gray(screen)
            tmpl_match = self._to_gray(template)
            mask_match = mask
        else:
            screen_match = screen
            tmpl_match = template
            mask_match = mask
            if mask_match is not None and len(mask_match.shape) == 2 and len(tmpl_match.shape) == 3:
                mask_match = cv2.merge([mask_match] * 3)

        if mask_match is not None:
            result = cv2.matchTemplate(screen_match, tmpl_match, cv2.TM_CCOEFF_NORMED, mask=mask_match)
        else:
            result = cv2.matchTemplate(screen_match, tmpl_match, cv2.TM_CCOEFF_NORMED)

        locations = np.where(result >= threshold)

        # NMS 去重
        matches: list[MatchResult] = []
        for pt in zip(*locations[::-1]):  # (x, y)
            cx = pt[0] + tw // 2 + offset_x
            cy = pt[1] + th // 2 + offset_y
            too_close = any(
                abs(cx - m.x) < min_distance and abs(cy - m.y) < min_distance
                for m in matches
            )
            if not too_close:
                matches.append(MatchResult(
                    x=cx, y=cy,
                    confidence=float(result[pt[1], pt[0]]),
                    top_left=(pt[0] + offset_x, pt[1] + offset_y),
                    bottom_right=(pt[0] + tw + offset_x, pt[1] + th + offset_y),
                    template_name=template_name,
                ))

        logger.debug(f"🔍 [{template_name}] 找到 {len(matches)} 個匹配")
        return matches

    def exists(
        self,
        screenshot: np.ndarray | Image.Image,
        template_name: str,
        threshold: float | None = None,
    ) -> bool:
        """快速檢查模板是否存在"""
        return self.find(screenshot, template_name, threshold) is not None

    def wait_for(
        self,
        screenshot_fn,
        template_name: str,
        timeout: float = 10.0,
        interval: float = 0.5,
        threshold: float | None = None,
    ) -> MatchResult | None:
        """
        等待模板出現

        Args:
            screenshot_fn: 呼叫後回傳截圖的 callable (通常是 adb.screenshot)
            timeout: 最長等待秒數
            interval: 檢查間隔秒數
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            screen = screenshot_fn()
            match = self.find(screen, template_name, threshold)
            if match:
                return match
            time.sleep(interval)

        logger.warning(f"⏰ 等待 [{template_name}] 超時 ({timeout}s)")
        return None

    def wait_until_gone(
        self,
        screenshot_fn,
        template_name: str,
        timeout: float = 10.0,
        interval: float = 0.5,
        threshold: float | None = None,
    ) -> bool:
        """
        等待模板消失

        Returns:
            True=已消失, False=超時仍存在
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            screen = screenshot_fn()
            if not self.exists(screen, template_name, threshold):
                return True
            time.sleep(interval)

        logger.warning(f"⏰ 等待 [{template_name}] 消失超時 ({timeout}s)")
        return False

    def clear_cache(self) -> None:
        """清除模板快取"""
        self._template_cache.clear()
        self._mask_cache.clear()

