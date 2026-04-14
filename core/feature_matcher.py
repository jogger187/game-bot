"""特徵點匹配 — 用 ORB/SIFT 做視角/尺度不變的目標辨識

適用場景:
- UI 元素位移、縮放後仍需辨識
- 模板解析度與截圖不同
- 需要估算目標旋轉角度

使用方式:
    fm = FeatureMatcher()
    result = fm.find(screenshot, "hero_icon.png")
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import cv2
import numpy as np
from loguru import logger
from PIL import Image


@dataclass
class FeatureMatchResult:
    """特徵匹配結果"""

    x: int  # 中心點 x
    y: int  # 中心點 y
    confidence: float  # 匹配品質 (0~1)
    corners: list[tuple[int, int]]  # 四個角的座標
    num_matches: int  # 匹配的特徵點數
    template_name: str

    def __bool__(self) -> bool:
        return self.confidence > 0 and self.num_matches > 0


class FeatureMatcher:
    """ORB/SIFT 特徵點匹配引擎"""

    def __init__(
        self,
        assets_dir: str | Path = "assets",
        method: str = "orb",
        min_matches: int = 10,
        good_ratio: float = 0.75,
    ):
        """
        Args:
            method: "orb" 或 "sift"
            min_matches: 最少匹配特徵點數
            good_ratio: Lowe's ratio test 閾值
        """
        self.assets_dir = Path(assets_dir)
        self.min_matches = min_matches
        self.good_ratio = good_ratio

        # 建立特徵偵測器
        if method == "sift":
            self._detector = cv2.SIFT_create()
            self._matcher = cv2.BFMatcher(cv2.NORM_L2)
        else:
            self._detector = cv2.ORB_create(nfeatures=1000)
            self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

        self._method = method
        self._template_cache: dict[str, tuple[list, np.ndarray, tuple[int, int]]] = {}

    def _load_template(self, name: str) -> tuple[list, np.ndarray, tuple[int, int]]:
        """
        載入模板並計算特徵點（帶快取）

        Returns:
            (keypoints, descriptors, (height, width))
        """
        if name in self._template_cache:
            return self._template_cache[name]

        path = self.assets_dir / name
        if not path.exists():
            raise FileNotFoundError(f"模板不存在: {path}")

        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(f"無法讀取模板: {path}")

        kp, des = self._detector.detectAndCompute(img, None)
        if des is None or len(kp) < 4:
            raise ValueError(f"模板特徵點太少 ({len(kp) if kp else 0}): {name}")

        # cv2.KeyPoint 不能 pickle，轉存必要屬性
        kp_data = [(p.pt, p.size, p.angle, p.response, p.octave) for p in kp]
        self._template_cache[name] = (kp_data, des, img.shape[:2])
        return kp_data, des, img.shape[:2]

    def _rebuild_keypoints(self, kp_data: list) -> list:
        """從快取資料重建 KeyPoint 物件"""
        return [
            cv2.KeyPoint(x=pt[0], y=pt[1], size=size, angle=angle, response=resp, octave=oct)
            for (pt, size, angle, resp, oct) in kp_data
        ]

    def _to_gray(self, image: np.ndarray | Image.Image) -> np.ndarray:
        if isinstance(image, Image.Image):
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def find(
        self,
        screenshot: np.ndarray | Image.Image,
        template_name: str,
        min_matches: int | None = None,
    ) -> FeatureMatchResult | None:
        """
        在截圖中用特徵點匹配尋找模板

        Args:
            screenshot: 截圖
            template_name: 模板檔名
            min_matches: 最少匹配數，None 用預設

        Returns:
            FeatureMatchResult 或 None
        """
        min_m = min_matches or self.min_matches
        screen_gray = self._to_gray(screenshot)

        # 截圖特徵點
        kp_screen, des_screen = self._detector.detectAndCompute(screen_gray, None)
        if des_screen is None or len(kp_screen) < 4:
            logger.debug(f"❌ 截圖特徵點不足 ({len(kp_screen) if kp_screen else 0})")
            return None

        # 模板特徵點
        kp_data, des_tmpl, (th, tw) = self._load_template(template_name)
        kp_tmpl = self._rebuild_keypoints(kp_data)

        # KNN 匹配 + Lowe's ratio test
        try:
            raw_matches = self._matcher.knnMatch(des_tmpl, des_screen, k=2)
        except cv2.error:
            return None

        good_matches = []
        for m_pair in raw_matches:
            if len(m_pair) == 2:
                m, n = m_pair
                if m.distance < self.good_ratio * n.distance:
                    good_matches.append(m)

        if len(good_matches) < min_m:
            logger.debug(
                f"❌ [{template_name}] 特徵匹配不足 "
                f"({len(good_matches)}/{min_m})"
            )
            return None

        # 計算 Homography
        src_pts = np.float32(
            [kp_tmpl[m.queryIdx].pt for m in good_matches]
        ).reshape(-1, 1, 2)
        dst_pts = np.float32(
            [kp_screen[m.trainIdx].pt for m in good_matches]
        ).reshape(-1, 1, 2)

        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if M is None:
            logger.debug(f"❌ [{template_name}] Homography 計算失敗")
            return None

        # 透視變換模板四角
        corners_tmpl = np.float32([
            [0, 0], [tw, 0], [tw, th], [0, th]
        ]).reshape(-1, 1, 2)
        corners_screen = cv2.perspectiveTransform(corners_tmpl, M)
        corners = [(int(c[0][0]), int(c[0][1])) for c in corners_screen]

        # 計算中心點
        cx = int(np.mean([c[0] for c in corners]))
        cy = int(np.mean([c[1] for c in corners]))

        # 品質評估：inlier ratio
        inliers = int(mask.sum()) if mask is not None else len(good_matches)
        confidence = inliers / len(good_matches)

        result = FeatureMatchResult(
            x=cx, y=cy,
            confidence=confidence,
            corners=corners,
            num_matches=len(good_matches),
            template_name=template_name,
        )
        logger.debug(
            f"🎯 特徵匹配 [{template_name}] "
            f"matches={len(good_matches)} inliers={inliers} "
            f"位置=({cx}, {cy})"
        )
        return result

    def clear_cache(self) -> None:
        """清除模板快取"""
        self._template_cache.clear()
