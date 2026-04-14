"""場景偵測器 — 判斷當前遊戲畫面屬於哪個場景

透過 YAML 定義場景規則（模板、文字、色彩），
自動判斷目前在主選單 / 戰鬥 / 背包 / 商店 等畫面。

場景定義檔範例 (scenes/main_menu.yaml):
    name: main_menu
    display_name: 主選單
    indicators:
      - type: template
        name: "logo.png"
        region: [0, 0, 300, 100]
        threshold: 0.8
      - type: text
        content: "開始遊戲"
        fuzzy: true
      - type: color
        hsv_low: [0, 100, 100]
        hsv_high: [10, 255, 255]
        region: [500, 200, 100, 50]
        min_area: 200
    min_score: 2  # 至少需要 2 個 indicator 匹配

使用方式:
    detector = SceneDetector(matcher, ocr, pixel_analyzer)
    detector.load_scenes("scenes/")
    scene = detector.detect(screenshot)  # -> "main_menu"
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field

import yaml
from loguru import logger
from PIL import Image
import numpy as np


@dataclass
class SceneIndicator:
    """場景判定指標"""

    type: str  # template | text | color
    # template 類型
    name: str | None = None
    threshold: float | None = None
    # text 類型
    content: str | None = None
    fuzzy: bool = False
    # color 類型
    hsv_low: tuple[int, int, int] | None = None
    hsv_high: tuple[int, int, int] | None = None
    min_area: int = 100
    # 通用
    region: tuple[int, int, int, int] | None = None
    weight: float = 1.0  # 權重


@dataclass
class SceneConfig:
    """場景定義"""

    name: str
    display_name: str = ""
    indicators: list[SceneIndicator] = field(default_factory=list)
    min_score: float = 1.0  # 最低匹配分數


@dataclass
class SceneDetectResult:
    """場景偵測結果"""

    scene_name: str
    display_name: str
    score: float
    matched_indicators: list[str]

    def __bool__(self) -> bool:
        return bool(self.scene_name)


class SceneDetector:
    """場景偵測引擎"""

    def __init__(
        self,
        matcher=None,
        ocr=None,
        pixel_analyzer=None,
    ):
        """
        Args:
            matcher: ScreenMatcher 實例
            ocr: OcrReader 實例（可選）
            pixel_analyzer: PixelAnalyzer 實例（可選）
        """
        self.matcher = matcher
        self.ocr = ocr
        self.pixel_analyzer = pixel_analyzer
        self._scenes: dict[str, SceneConfig] = {}
        self._last_scene: str | None = None

    @property
    def last_scene(self) -> str | None:
        return self._last_scene

    @property
    def scene_names(self) -> list[str]:
        return list(self._scenes.keys())

    # ── 場景載入 ──────────────────────────────────────────

    def load_scenes(self, path: str | Path) -> None:
        """從目錄載入所有場景定義 YAML"""
        path = Path(path)
        if path.is_file():
            self._load_scene_file(path)
        elif path.is_dir():
            for f in sorted(path.glob("*.yaml")):
                self._load_scene_file(f)
            for f in sorted(path.glob("*.yml")):
                self._load_scene_file(f)
        else:
            logger.warning(f"場景路徑不存在: {path}")
            return

        logger.info(f"📋 載入 {len(self._scenes)} 個場景定義")

    def _load_scene_file(self, path: Path) -> None:
        """載入單一場景定義檔"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "name" not in data:
            logger.warning(f"無效的場景定義: {path}")
            return

        indicators = []
        for ind_data in data.get("indicators", []):
            region = ind_data.get("region")
            if region and isinstance(region, list) and len(region) == 4:
                region = tuple(region)

            hsv_low = ind_data.get("hsv_low")
            if hsv_low and isinstance(hsv_low, list):
                hsv_low = tuple(hsv_low)

            hsv_high = ind_data.get("hsv_high")
            if hsv_high and isinstance(hsv_high, list):
                hsv_high = tuple(hsv_high)

            indicators.append(SceneIndicator(
                type=ind_data["type"],
                name=ind_data.get("name"),
                threshold=ind_data.get("threshold"),
                content=ind_data.get("content"),
                fuzzy=ind_data.get("fuzzy", False),
                hsv_low=hsv_low,
                hsv_high=hsv_high,
                min_area=ind_data.get("min_area", 100),
                region=region,
                weight=ind_data.get("weight", 1.0),
            ))

        scene = SceneConfig(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            indicators=indicators,
            min_score=data.get("min_score", 1.0),
        )
        self._scenes[scene.name] = scene

    def add_scene(self, config: SceneConfig) -> None:
        """程式碼方式新增場景"""
        self._scenes[config.name] = config

    # ── 場景偵測 ──────────────────────────────────────────

    def detect(
        self,
        screenshot: np.ndarray | Image.Image,
    ) -> SceneDetectResult | None:
        """
        偵測當前場景

        Returns:
            最佳匹配場景，或 None（全部未達門檻）
        """
        best_result: SceneDetectResult | None = None
        best_score = 0.0

        for scene in self._scenes.values():
            score, matched = self._evaluate_scene(screenshot, scene)
            if score >= scene.min_score and score > best_score:
                best_score = score
                best_result = SceneDetectResult(
                    scene_name=scene.name,
                    display_name=scene.display_name,
                    score=score,
                    matched_indicators=matched,
                )

        if best_result:
            self._last_scene = best_result.scene_name
            logger.debug(
                f"🎬 場景: {best_result.display_name} "
                f"(score={best_result.score:.1f}, "
                f"matched={best_result.matched_indicators})"
            )
        else:
            logger.debug("🎬 場景: 未知")

        return best_result

    def detect_name(self, screenshot: np.ndarray | Image.Image) -> str | None:
        """偵測場景，只回傳名稱"""
        result = self.detect(screenshot)
        return result.scene_name if result else None

    def is_scene(
        self,
        screenshot: np.ndarray | Image.Image,
        scene_name: str,
    ) -> bool:
        """判斷是否在指定場景"""
        if scene_name not in self._scenes:
            logger.warning(f"未定義的場景: {scene_name}")
            return False

        scene = self._scenes[scene_name]
        score, _ = self._evaluate_scene(screenshot, scene)
        return score >= scene.min_score

    def _evaluate_scene(
        self,
        screenshot: np.ndarray | Image.Image,
        scene: SceneConfig,
    ) -> tuple[float, list[str]]:
        """
        評估截圖與場景的匹配度

        Returns:
            (score, matched_indicator_names)
        """
        score = 0.0
        matched: list[str] = []

        for indicator in scene.indicators:
            try:
                if indicator.type == "template" and self.matcher:
                    hit = self._check_template(screenshot, indicator)
                elif indicator.type == "text" and self.ocr:
                    hit = self._check_text(screenshot, indicator)
                elif indicator.type == "color" and self.pixel_analyzer:
                    hit = self._check_color(screenshot, indicator)
                else:
                    continue

                if hit:
                    score += indicator.weight
                    desc = indicator.name or indicator.content or "color"
                    matched.append(f"{indicator.type}:{desc}")
            except Exception as e:
                logger.debug(f"指標檢查失敗: {indicator.type} - {e}")

        return score, matched

    def _check_template(self, screenshot, indicator: SceneIndicator) -> bool:
        """檢查模板指標"""
        return self.matcher.find(
            screenshot,
            indicator.name,
            threshold=indicator.threshold,
            region=indicator.region,
        ) is not None

    def _check_text(self, screenshot, indicator: SceneIndicator) -> bool:
        """檢查文字指標"""
        if isinstance(screenshot, np.ndarray):
            img = Image.fromarray(screenshot[:, :, ::-1])
        else:
            img = screenshot

        if indicator.region:
            rx, ry, rw, rh = indicator.region
            results = self.ocr.read_region(img, rx, ry, rw, rh)
        else:
            results = self.ocr.read(img)

        for r in results:
            if indicator.fuzzy:
                if indicator.content in r.text:
                    return True
            else:
                if r.text == indicator.content:
                    return True
        return False

    def _check_color(self, screenshot, indicator: SceneIndicator) -> bool:
        """檢查色彩指標"""
        regions = self.pixel_analyzer.find_color_region(
            screenshot,
            hsv_low=indicator.hsv_low,
            hsv_high=indicator.hsv_high,
            min_area=indicator.min_area,
            region=indicator.region,
        )
        return len(regions) > 0
