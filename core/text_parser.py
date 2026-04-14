"""結構化文字解析 — 從 OCR 結果中擷取遊戲數據

將 OCR 辨識的原始文字轉換為結構化數據：
- 資源數量：「金幣: 12,345」→ {"金幣": 12345}
- 倒數計時：「03:45:12」→ timedelta
- 傷害數字：浮動文字中的數字
- 座標文字：「(123, 456)」→ (123, 456)
"""

from __future__ import annotations

import re
from datetime import timedelta
from dataclasses import dataclass

from loguru import logger


@dataclass
class ResourceInfo:
    """資源資訊"""
    name: str
    value: int | float
    raw_text: str


class TextParser:
    """從 OCR 結果解析結構化數據"""

    # ── 資源解析 ──────────────────────────────────────────

    @staticmethod
    def parse_number(text: str) -> int | None:
        """
        解析數字文字

        支援格式：
        - "12,345" → 12345
        - "1.2K" → 1200
        - "3.5M" → 3500000
        - "100%" → 100
        """
        text = text.strip().replace(" ", "").replace(",", "")

        # 帶單位的縮寫 (K/M/B)
        match = re.match(r"([\d.]+)\s*([KMBkmb万億])", text)
        if match:
            num = float(match.group(1))
            unit = match.group(2).upper()
            multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "万": 10_000, "億": 100_000_000}
            return int(num * multipliers.get(unit, 1))

        # 百分比
        match = re.match(r"([\d.]+)\s*%", text)
        if match:
            return int(float(match.group(1)))

        # 純數字
        match = re.match(r"[\d.]+", text)
        if match:
            try:
                val = float(match.group())
                return int(val) if val == int(val) else int(val)
            except ValueError:
                return None

        return None

    @staticmethod
    def parse_resource(ocr_results: list) -> dict[str, int]:
        """
        從 OCR 結果解析資源數量

        自動偵測「名稱: 數量」或「名稱 數量」格式

        Returns:
            {"金幣": 12345, "鑽石": 100, ...}
        """
        resources: dict[str, int] = {}

        for r in ocr_results:
            text = r.text.strip()

            # 格式：「金幣: 12,345」或「金幣：12345」
            match = re.match(r"(.+?)[:\：]\s*([\d,.\s]+[KMBkmb万億]?)", text)
            if match:
                name = match.group(1).strip()
                value = TextParser.parse_number(match.group(2))
                if value is not None:
                    resources[name] = value
                    continue

            # 格式：「x123」或「×456」
            match = re.match(r"[x×X]\s*([\d,]+)", text)
            if match:
                value = TextParser.parse_number(match.group(1))
                if value is not None:
                    resources[f"item_{len(resources)}"] = value

        if resources:
            logger.debug(f"📦 解析資源: {resources}")
        return resources

    # ── 時間解析 ──────────────────────────────────────────

    @staticmethod
    def parse_countdown(text: str) -> timedelta | None:
        """
        解析倒數計時文字

        支援格式：
        - "03:45:12" → 3h 45m 12s
        - "45:12" → 45m 12s
        - "12s" → 12s
        - "2d 3h" → 2d 3h
        - "1天23時45分" → 1d 23h 45m
        """
        text = text.strip()

        # 標準 HH:MM:SS
        match = re.match(r"(\d+):(\d+):(\d+)", text)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return timedelta(hours=h, minutes=m, seconds=s)

        # MM:SS
        match = re.match(r"(\d+):(\d+)$", text)
        if match:
            m, s = int(match.group(1)), int(match.group(2))
            return timedelta(minutes=m, seconds=s)

        # 英文格式：2d 3h 45m 12s
        days = hours = minutes = seconds = 0
        for m in re.finditer(r"(\d+)\s*([dhms])", text, re.IGNORECASE):
            val = int(m.group(1))
            unit = m.group(2).lower()
            if unit == "d":
                days = val
            elif unit == "h":
                hours = val
            elif unit == "m":
                minutes = val
            elif unit == "s":
                seconds = val

        if days or hours or minutes or seconds:
            return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

        # 中文格式：1天23時45分30秒
        for m in re.finditer(r"(\d+)\s*([天時分秒日])", text):
            val = int(m.group(1))
            unit = m.group(2)
            if unit in ("天", "日"):
                days = val
            elif unit == "時":
                hours = val
            elif unit == "分":
                minutes = val
            elif unit == "秒":
                seconds = val

        if days or hours or minutes or seconds:
            return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

        return None

    @staticmethod
    def parse_countdown_from_results(ocr_results: list) -> timedelta | None:
        """從 OCR 結果中找到倒數計時"""
        for r in ocr_results:
            td = TextParser.parse_countdown(r.text)
            if td is not None:
                logger.debug(f"⏱️ 倒數計時: {td}")
                return td
        return None

    # ── 傷害/數字解析 ─────────────────────────────────────

    @staticmethod
    def parse_damage(ocr_results: list) -> list[int]:
        """
        從 OCR 結果解析傷害數字

        Returns:
            傷害數值列表（大到小）
        """
        damages: list[int] = []
        for r in ocr_results:
            text = r.text.strip().replace(",", "").replace(" ", "")
            # 提取所有連續數字
            for match in re.finditer(r"\d+", text):
                val = int(match.group())
                if val > 0:
                    damages.append(val)

        damages.sort(reverse=True)
        return damages

    # ── 比例/百分比 ───────────────────────────────────────

    @staticmethod
    def parse_ratio(text: str) -> tuple[int, int] | None:
        """
        解析比例文字

        支援：
        - "3/10" → (3, 10)
        - "HP: 1234/5678" → (1234, 5678)
        """
        match = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None

    @staticmethod
    def parse_percentage(text: str) -> float | None:
        """解析百分比 → 0.0~1.0"""
        match = re.search(r"([\d.]+)\s*%", text)
        if match:
            return float(match.group(1)) / 100.0
        return None

    # ── 座標解析 ──────────────────────────────────────────

    @staticmethod
    def parse_coordinates(text: str) -> tuple[int, int] | None:
        """
        解析座標文字

        支援：「(123, 456)」「X:123 Y:456」
        """
        # (x, y) 格式
        match = re.search(r"\(?\s*(\d+)\s*[,，]\s*(\d+)\s*\)?", text)
        if match:
            return int(match.group(1)), int(match.group(2))

        # X:123 Y:456 格式
        x_match = re.search(r"[Xx]\s*[:\：]\s*(\d+)", text)
        y_match = re.search(r"[Yy]\s*[:\：]\s*(\d+)", text)
        if x_match and y_match:
            return int(x_match.group(1)), int(y_match.group(1))

        return None
