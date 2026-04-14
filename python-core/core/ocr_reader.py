"""OCR 文字辨識 — 用 PaddleOCR 辨識遊戲截圖中的文字

支援:
- 標準中英文辨識
- 數字專用模式（傷害數字、金幣、倒數計時等）
- 預處理 pipeline（灰階、二值化、放大、銳化）
- 區域快取（只辨識有變化的區域）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from loguru import logger
from PIL import Image


@dataclass
class OcrResult:
    """單一 OCR 辨識結果"""
    text: str
    confidence: float
    box: list[list[int]]  # 4 個角的座標 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]

    @property
    def center(self) -> tuple[int, int]:
        """文字區域中心"""
        xs = [p[0] for p in self.box]
        ys = [p[1] for p in self.box]
        return int(sum(xs) / 4), int(sum(ys) / 4)


# ── 預處理 Pipeline ──────────────────────────────────────


class PreprocessStep(ABC):
    """預處理步驟基底"""

    @abstractmethod
    def apply(self, img: np.ndarray) -> np.ndarray:
        ...

    def __repr__(self) -> str:
        return self.__class__.__name__


class Grayscale(PreprocessStep):
    """轉灰階"""

    def apply(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img


class Threshold(PreprocessStep):
    """二值化"""

    def __init__(self, value: int = 127, method: str = "binary"):
        self.value = value
        self.method = method

    def apply(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self.method == "otsu":
            _, result = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif self.method == "adaptive":
            result = cv2.adaptiveThreshold(
                img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        else:
            _, result = cv2.threshold(img, self.value, 255, cv2.THRESH_BINARY)
        return result


class Resize(PreprocessStep):
    """縮放"""

    def __init__(self, scale: float = 2.0):
        self.scale = scale

    def apply(self, img: np.ndarray) -> np.ndarray:
        if self.scale == 1.0:
            return img
        h, w = img.shape[:2]
        new_w = int(w * self.scale)
        new_h = int(h * self.scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


class Sharpen(PreprocessStep):
    """銳化"""

    def apply(self, img: np.ndarray) -> np.ndarray:
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        return cv2.filter2D(img, -1, kernel)


class Invert(PreprocessStep):
    """反色"""

    def apply(self, img: np.ndarray) -> np.ndarray:
        return cv2.bitwise_not(img)


class Denoise(PreprocessStep):
    """去雜訊"""

    def __init__(self, strength: int = 10):
        self.strength = strength

    def apply(self, img: np.ndarray) -> np.ndarray:
        if len(img.shape) == 2:
            return cv2.fastNlMeansDenoising(img, None, self.strength)
        return cv2.fastNlMeansDenoisingColored(img, None, self.strength, self.strength)


# ── 數字專用預處理 ────────────────────────────────────────

DIGIT_PREPROCESS = [
    Grayscale(),
    Threshold(method="otsu"),
    Resize(scale=2.0),
    Sharpen(),
]


class OcrReader:
    """PaddleOCR 封裝 — 支援多種模式與預處理"""

    def __init__(
        self,
        lang: str = "ch",
        use_gpu: bool = False,
        digit_mode: bool = False,
    ):
        self._lang = lang
        self._use_gpu = use_gpu
        self._digit_mode = digit_mode
        self._engine = None  # lazy init
        self._digit_engine = None  # 數字專用引擎
        self._region_cache: dict[str, np.ndarray] = {}  # 區域變化偵測快取

    def _get_engine(self):
        if self._engine is None:
            from paddleocr import PaddleOCR
            self._engine = PaddleOCR(
                use_angle_cls=True,
                lang=self._lang,
                use_gpu=self._use_gpu,
                show_log=False,
            )
            logger.info(f"🔤 PaddleOCR 初始化完成 (lang={self._lang}, gpu={self._use_gpu})")
        return self._engine

    def _get_digit_engine(self):
        """數字專用 OCR 引擎（白名單限定）"""
        if self._digit_engine is None:
            from paddleocr import PaddleOCR
            self._digit_engine = PaddleOCR(
                use_angle_cls=False,
                lang="en",
                use_gpu=self._use_gpu,
                show_log=False,
                # 數字 + 常見符號白名單
                rec_char_dict_path=None,
            )
            logger.info("🔢 數字專用 OCR 初始化完成")
        return self._digit_engine

    def _preprocess(self, image: np.ndarray, steps: list[PreprocessStep]) -> np.ndarray:
        """套用預處理 pipeline"""
        result = image.copy()
        for step in steps:
            result = step.apply(result)
        return result

    def _to_numpy(self, image: np.ndarray | Image.Image | str | Path) -> np.ndarray:
        """統一轉換為 numpy array"""
        if isinstance(image, Image.Image):
            return np.array(image)
        elif isinstance(image, (str, Path)):
            return cv2.imread(str(image))
        return image

    def read(
        self,
        image: np.ndarray | Image.Image | str | Path,
        preprocess: list[PreprocessStep] | None = None,
        digit_mode: bool | None = None,
    ) -> list[OcrResult]:
        """
        辨識圖片中的文字

        Args:
            image: numpy array (BGR), PIL Image, 或圖片路徑
            preprocess: 預處理步驟列表，None 則不做預處理
            digit_mode: 數字專用模式，None 用預設

        Returns:
            OcrResult 列表
        """
        use_digit = digit_mode if digit_mode is not None else self._digit_mode
        img = self._to_numpy(image)

        # 預處理
        if use_digit and preprocess is None:
            preprocess = DIGIT_PREPROCESS
        if preprocess:
            img = self._preprocess(img, preprocess)

        # 選擇引擎
        if use_digit:
            engine = self._get_digit_engine()
        else:
            engine = self._get_engine()

        raw = engine.ocr(img, cls=not use_digit)
        results: list[OcrResult] = []

        if not raw or not raw[0]:
            return results

        for line in raw[0]:
            box, (text, conf) = line

            # 數字模式：過濾非數字字元
            if use_digit:
                text = "".join(c for c in text if c.isdigit() or c in ".,:%/-+")
                if not text:
                    continue

            results.append(OcrResult(
                text=text,
                confidence=conf,
                box=[[int(p[0]), int(p[1])] for p in box],
            ))

        logger.debug(f"🔤 辨識到 {len(results)} 段文字{'（數字模式）' if use_digit else ''}")
        return results

    def read_region(
        self,
        image: np.ndarray | Image.Image,
        x: int, y: int, w: int, h: int,
        preprocess: list[PreprocessStep] | None = None,
        digit_mode: bool | None = None,
        skip_unchanged: bool = False,
    ) -> list[OcrResult]:
        """
        辨識圖片指定區域的文字

        Args:
            skip_unchanged: 如果區域沒變化就跳過（用快取）
        """
        img = self._to_numpy(image)
        region = img[y:y + h, x:x + w]

        # 區域變化偵測
        if skip_unchanged:
            cache_key = f"{x}_{y}_{w}_{h}"
            if cache_key in self._region_cache:
                prev = self._region_cache[cache_key]
                if prev.shape == region.shape:
                    diff = cv2.absdiff(prev, region)
                    if np.mean(diff) < 5:
                        logger.debug(f"⏭️ 區域 ({x},{y},{w},{h}) 無變化，跳過 OCR")
                        return []
            self._region_cache[cache_key] = region.copy()

        return self.read(region, preprocess=preprocess, digit_mode=digit_mode)

    def find_text(
        self,
        image: np.ndarray | Image.Image,
        target: str,
        fuzzy: bool = False,
        preprocess: list[PreprocessStep] | None = None,
    ) -> OcrResult | None:
        """
        在圖片中尋找特定文字

        Args:
            target: 要找的文字
            fuzzy: 是否模糊比對（包含即可）
        """
        results = self.read(image, preprocess=preprocess)
        for r in results:
            if fuzzy and target in r.text:
                return r
            elif r.text == target:
                return r
        return None

    def find_all_text(
        self,
        image: np.ndarray | Image.Image,
        target: str,
        fuzzy: bool = False,
    ) -> list[OcrResult]:
        """找出所有包含目標文字的結果"""
        results = self.read(image)
        matched = []
        for r in results:
            if fuzzy and target in r.text:
                matched.append(r)
            elif r.text == target:
                matched.append(r)
        return matched

    def read_number(
        self,
        image: np.ndarray | Image.Image,
        region: tuple[int, int, int, int] | None = None,
    ) -> int | None:
        """
        讀取數字（便捷方法）

        Returns:
            解析出的整數，或 None
        """
        if region:
            x, y, w, h = region
            results = self.read_region(image, x, y, w, h, digit_mode=True)
        else:
            results = self.read(image, digit_mode=True)

        if not results:
            return None

        # 取信心最高的
        best = max(results, key=lambda r: r.confidence)
        text = best.text.replace(",", "").replace(".", "").replace(" ", "")
        try:
            return int(text)
        except ValueError:
            logger.debug(f"⚠️ 數字解析失敗: '{best.text}'")
            return None

    def clear_cache(self) -> None:
        """清除區域快取"""
        self._region_cache.clear()

