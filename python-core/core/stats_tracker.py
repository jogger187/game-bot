"""統計追蹤 — 記錄和分析 bot 運行數據

追蹤:
- 任務成功/失敗次數
- 截圖/比對/OCR 延遲
- 資源收集進度
- 操作時間分佈
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from loguru import logger


@dataclass
class TimingStats:
    """單一指標的延遲統計"""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    def record(self, duration_ms: float) -> None:
        self.count += 1
        self.total_ms += duration_ms
        self.min_ms = min(self.min_ms, duration_ms)
        self.max_ms = max(self.max_ms, duration_ms)

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "avg_ms": round(self.avg_ms, 1),
            "min_ms": round(self.min_ms, 1) if self.min_ms != float("inf") else 0,
            "max_ms": round(self.max_ms, 1),
        }


class StatsTracker:
    """統計追蹤管理器"""

    def __init__(
        self,
        export_path: str | Path = "logs/stats.json",
        export_interval: float = 300.0,
    ):
        self._export_path = Path(export_path)
        self._export_interval = export_interval
        self._start_time = time.time()
        self._last_export = time.time()
        self._lock = Lock()

        # 計數器
        self._counters: dict[str, int] = defaultdict(int)
        # 延遲統計
        self._timings: dict[str, TimingStats] = defaultdict(TimingStats)
        # 資源追蹤
        self._resources: dict[str, list[tuple[float, int]]] = defaultdict(list)
        # 事件日誌
        self._events: list[dict] = []

    # ── 計數 ──────────────────────────────────────────────

    def count(self, key: str, increment: int = 1) -> None:
        """增加計數器"""
        with self._lock:
            self._counters[key] += increment

    def get_count(self, key: str) -> int:
        return self._counters.get(key, 0)

    # ── 延遲追蹤 ──────────────────────────────────────────

    def time_it(self, key: str):
        """
        延遲追蹤裝飾器 / context manager

        使用方式:
            with stats.time_it("screenshot"):
                img = adb.screenshot()

            @stats.time_it("ocr")
            def read_text():
                ...
        """
        return _TimingContext(self, key)

    def record_timing(self, key: str, duration_ms: float) -> None:
        """手動記錄延遲"""
        with self._lock:
            self._timings[key].record(duration_ms)

    # ── 資源追蹤 ──────────────────────────────────────────

    def track_resource(self, name: str, value: int) -> None:
        """記錄資源數量"""
        with self._lock:
            self._resources[name].append((time.time(), value))
            # 只保留最近 1000 筆
            if len(self._resources[name]) > 1000:
                self._resources[name] = self._resources[name][-500:]

    def get_resource_delta(self, name: str) -> int:
        """取得資源的變化量（最新值 - 最早值）"""
        history = self._resources.get(name, [])
        if len(history) < 2:
            return 0
        return history[-1][1] - history[0][1]

    # ── 事件日誌 ──────────────────────────────────────────

    def log_event(self, event_type: str, data: dict | None = None) -> None:
        """記錄事件"""
        with self._lock:
            self._events.append({
                "time": time.time(),
                "type": event_type,
                "data": data or {},
            })
            # 只保留最近 500 筆
            if len(self._events) > 500:
                self._events = self._events[-250:]

    # ── 匯出 ──────────────────────────────────────────────

    def export(self) -> dict:
        """匯出所有統計數據"""
        with self._lock:
            data = {
                "run_time_minutes": round((time.time() - self._start_time) / 60, 1),
                "counters": dict(self._counters),
                "timings": {k: v.to_dict() for k, v in self._timings.items()},
                "resources": {
                    name: {
                        "current": history[-1][1] if history else 0,
                        "delta": self.get_resource_delta(name),
                        "history_count": len(history),
                    }
                    for name, history in self._resources.items()
                },
                "recent_events": self._events[-20:],
            }
        return data

    def save(self) -> None:
        """儲存到檔案"""
        self._export_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.export()
        with open(self._export_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.debug(f"📊 統計已匯出: {self._export_path}")

    def maybe_auto_save(self) -> None:
        """自動定期儲存"""
        if time.time() - self._last_export >= self._export_interval:
            self.save()
            self._last_export = time.time()

    # ── 報告 ──────────────────────────────────────────────

    def report(self) -> str:
        """產生文字報告"""
        data = self.export()
        lines = [
            f"═══ Bot 統計報告 ═══",
            f"運行時間: {data['run_time_minutes']} 分鐘",
            "",
            "【計數器】",
        ]
        for k, v in data["counters"].items():
            lines.append(f"  {k}: {v}")

        lines.append("\n【延遲統計】")
        for k, v in data["timings"].items():
            lines.append(f"  {k}: avg={v['avg_ms']:.0f}ms min={v['min_ms']:.0f}ms max={v['max_ms']:.0f}ms ({v['count']}次)")

        lines.append("\n【資源追蹤】")
        for k, v in data["resources"].items():
            lines.append(f"  {k}: {v['current']} (Δ{v['delta']:+d})")

        return "\n".join(lines)

    def reset(self) -> None:
        """重置所有統計"""
        with self._lock:
            self._counters.clear()
            self._timings.clear()
            self._resources.clear()
            self._events.clear()
            self._start_time = time.time()


class _TimingContext:
    """延遲追蹤 context manager"""

    def __init__(self, tracker: StatsTracker, key: str):
        self._tracker = tracker
        self._key = key
        self._start = 0.0

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, *args):
        duration_ms = (time.time() - self._start) * 1000
        self._tracker.record_timing(self._key, duration_ms)

    def __call__(self, func):
        """也可當裝飾器用"""
        import functools

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return wrapper
