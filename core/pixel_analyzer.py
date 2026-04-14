"""像素分析器 — HSV 色彩偵測、進度條分析、像素比對

適用場景:
- 血條/體力條讀取
- 技能 CD 判斷（灰色 vs 彩色）
- buff/debuff 圖示顏色辨識
- 特定像素狀態判斷

使用方式:
    pa = PixelAnalyzer()
    hp = pa.read_progress_bar(img, region=(100, 50, 200, 20), bar_hsv_range=(...))
    regions = pa.find_color_region(img, hsv_low=(0, 100, 100), hsv_high=(10, 255, 255))
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from loguru import logger
from PIL import Image


@dataclass
class ColorRegion:
    """色彩區域"""

    x: int  # bounding box 左上 x
    y: int  # bounding box 左上 y
    w: int  # 寬
    h: int  # 高
    area: int  # 像素面積
    center: tuple[int, int]  # 中心點
    contour: np.ndarray | None = None  # 原始輪廓

    def __bool__(self) -> bool:
        return self.area > 0


class PixelAnalyzer:
    """像素級分析工具"""

    @staticmethod
    def _to_bgr(image: np.ndarray | Image.Image) -> np.ndarray:
        if isinstance(image, Image.Image):
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        return image

    @staticmethod
    def _to_hsv(image: np.ndarray | Image.Image) -> np.ndarray:
        bgr = PixelAnalyzer._to_bgr(image)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # ── 色彩區域偵測 ──────────────────────────────────────

    def find_color_region(
        self,
        image: np.ndarray | Image.Image,
        hsv_low: tuple[int, int, int],
        hsv_high: tuple[int, int, int],
        min_area: int = 100,
        region: tuple[int, int, int, int] | None = None,
    ) -> list[ColorRegion]:
        """
        找出圖片中符合 HSV 色彩範圍的區域

        Args:
            hsv_low: HSV 下界 (H: 0-179, S: 0-255, V: 0-255)
            hsv_high: HSV 上界
            min_area: 最小面積（過濾雜訊）
            region: (x, y, w, h) 限定搜尋區域

        Returns:
            ColorRegion 列表，按面積大到小
        """
        hsv = self._to_hsv(image)
        offset_x, offset_y = 0, 0

        if region:
            rx, ry, rw, rh = region
            hsv = hsv[ry:ry + rh, rx:rx + rw]
            offset_x, offset_y = rx, ry

        low = np.array(hsv_low, dtype=np.uint8)
        high = np.array(hsv_high, dtype=np.uint8)
        mask = cv2.inRange(hsv, low, high)

        # 形態學操作去雜訊
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions: list[ColorRegion] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"]) + offset_x
                cy = int(M["m01"] / M["m00"]) + offset_y
            else:
                cx = x + w // 2 + offset_x
                cy = y + h // 2 + offset_y

            regions.append(ColorRegion(
                x=x + offset_x, y=y + offset_y,
                w=w, h=h,
                area=int(area),
                center=(cx, cy),
                contour=cnt,
            ))

        regions.sort(key=lambda r: r.area, reverse=True)
        logger.debug(f"🎨 色彩偵測: 找到 {len(regions)} 個區域 (HSV {hsv_low}~{hsv_high})")
        return regions

    # ── 進度條分析 ─────────────────────────────────────────

    def read_progress_bar(
        self,
        image: np.ndarray | Image.Image,
        region: tuple[int, int, int, int],
        bar_hsv_low: tuple[int, int, int],
        bar_hsv_high: tuple[int, int, int],
        direction: str = "horizontal",
    ) -> float:
        """
        讀取進度條數值 (0.0 ~ 1.0)

        Args:
            region: (x, y, w, h) 進度條區域
            bar_hsv_low: 進度條色彩 HSV 下界
            bar_hsv_high: 進度條色彩 HSV 上界
            direction: "horizontal" 或 "vertical"

        Returns:
            0.0 ~ 1.0 的進度值
        """
        hsv = self._to_hsv(image)
        rx, ry, rw, rh = region
        roi = hsv[ry:ry + rh, rx:rx + rw]

        low = np.array(bar_hsv_low, dtype=np.uint8)
        high = np.array(bar_hsv_high, dtype=np.uint8)
        mask = cv2.inRange(roi, low, high)

        if direction == "horizontal":
            # 每列的色彩像素比例
            col_ratio = mask.mean(axis=0) / 255.0
            # 找最右邊仍有色彩的位置
            filled_cols = np.where(col_ratio > 0.3)[0]
            if len(filled_cols) == 0:
                progress = 0.0
            else:
                progress = float((filled_cols.max() + 1) / rw)
        else:
            # 垂直：從底部往上
            row_ratio = mask.mean(axis=1) / 255.0
            filled_rows = np.where(row_ratio > 0.3)[0]
            if len(filled_rows) == 0:
                progress = 0.0
            else:
                progress = float((rh - filled_rows.min()) / rh)

        progress = max(0.0, min(1.0, progress))
        logger.debug(f"📊 進度條: {progress:.1%} (region={region})")
        return progress

    # ── 像素比對 ──────────────────────────────────────────

    def pixel_color(
        self,
        image: np.ndarray | Image.Image,
        x: int,
        y: int,
        color_space: str = "bgr",
    ) -> tuple[int, ...]:
        """
        取得指定座標的顏色

        Args:
            color_space: "bgr", "rgb", "hsv"

        Returns:
            顏色 tuple
        """
        bgr = self._to_bgr(image)
        if y >= bgr.shape[0] or x >= bgr.shape[1]:
            raise IndexError(f"座標 ({x}, {y}) 超出圖片範圍 ({bgr.shape[1]}x{bgr.shape[0]})")

        pixel = bgr[y, x]
        if color_space == "rgb":
            return (int(pixel[2]), int(pixel[1]), int(pixel[0]))
        elif color_space == "hsv":
            hsv = cv2.cvtColor(bgr[y:y + 1, x:x + 1], cv2.COLOR_BGR2HSV)
            p = hsv[0, 0]
            return (int(p[0]), int(p[1]), int(p[2]))
        else:
            return (int(pixel[0]), int(pixel[1]), int(pixel[2]))

    def pixel_matches(
        self,
        image: np.ndarray | Image.Image,
        x: int,
        y: int,
        color: tuple[int, int, int],
        tolerance: int = 10,
        color_space: str = "bgr",
    ) -> bool:
        """
        檢查指定座標的顏色是否匹配

        Args:
            color: 目標顏色
            tolerance: 容差（每個通道）
        """
        actual = self.pixel_color(image, x, y, color_space)
        return all(abs(a - e) <= tolerance for a, e in zip(actual, color))

    # ── 圖片差異 ──────────────────────────────────────────

    def image_diff(
        self,
        img1: np.ndarray | Image.Image,
        img2: np.ndarray | Image.Image,
        region: tuple[int, int, int, int] | None = None,
        threshold: int = 30,
    ) -> float:
        """
        計算兩張圖片的差異度

        Args:
            region: 只比較特定區域
            threshold: 差異閾值

        Returns:
            0.0 (完全相同) ~ 1.0 (完全不同)
        """
        bgr1 = self._to_bgr(img1)
        bgr2 = self._to_bgr(img2)

        if region:
            rx, ry, rw, rh = region
            bgr1 = bgr1[ry:ry + rh, rx:rx + rw]
            bgr2 = bgr2[ry:ry + rh, rx:rx + rw]

        # 確保尺寸相同
        if bgr1.shape != bgr2.shape:
            bgr2 = cv2.resize(bgr2, (bgr1.shape[1], bgr1.shape[0]))

        diff = cv2.absdiff(bgr1, bgr2)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        changed_pixels = np.sum(gray_diff > threshold)
        total_pixels = gray_diff.size
        ratio = float(changed_pixels / total_pixels)

        logger.debug(f"📐 圖片差異: {ratio:.2%}")
        return ratio

    def is_screen_static(
        self,
        screenshot_fn,
        interval: float = 0.5,
        threshold: float = 0.02,
        region: tuple[int, int, int, int] | None = None,
    ) -> bool:
        """
        判斷畫面是否靜止（連續兩張截圖比較）

        Args:
            screenshot_fn: 截圖函式
            interval: 兩次截圖間隔
            threshold: 差異度閾值（低於此值視為靜止）
        """
        import time
        img1 = screenshot_fn()
        time.sleep(interval)
        img2 = screenshot_fn()
        diff = self.image_diff(img1, img2, region=region)
        is_static = diff < threshold
        logger.debug(f"🖼️ 畫面{'靜止' if is_static else '變動中'} (diff={diff:.3f})")
        return is_static
