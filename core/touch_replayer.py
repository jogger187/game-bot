"""觸控操作錄製/回放 — 錄製真人操作並帶微量抖動回放

使用方式:
    recorder = TouchRecorder(adb)
    recording = recorder.record(duration=10)  # 錄 10 秒
    recording.save("swipe_pattern.json")

    replayer = TouchReplayer(adb)
    replayer.replay(recording, jitter=5)
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from .adb_controller import AdbController


@dataclass
class TouchEvent:
    """單一觸控事件"""

    timestamp: float  # 相對時間（秒）
    event_type: str  # "down" | "move" | "up"
    x: int
    y: int
    pressure: int = 50

    def to_dict(self) -> dict:
        return {
            "t": round(self.timestamp, 4),
            "type": self.event_type,
            "x": self.x,
            "y": self.y,
            "p": self.pressure,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TouchEvent:
        return cls(
            timestamp=data["t"],
            event_type=data["type"],
            x=data["x"],
            y=data["y"],
            pressure=data.get("p", 50),
        )


@dataclass
class TouchRecording:
    """一次完整的觸控操作錄製"""

    events: list[TouchEvent] = field(default_factory=list)
    screen_size: tuple[int, int] = (0, 0)
    duration: float = 0.0
    name: str = ""

    def save(self, path: str | Path) -> None:
        """儲存錄製到 JSON"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "screen_size": list(self.screen_size),
            "duration": round(self.duration, 3),
            "events": [e.to_dict() for e in self.events],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 錄製已儲存: {path} ({len(self.events)} 事件)")

    @classmethod
    def load(cls, path: str | Path) -> TouchRecording:
        """從 JSON 載入錄製"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        recording = cls(
            name=data.get("name", ""),
            screen_size=tuple(data.get("screen_size", [0, 0])),
            duration=data.get("duration", 0),
            events=[TouchEvent.from_dict(e) for e in data.get("events", [])],
        )
        logger.info(f"📂 錄製已載入: {path} ({len(recording.events)} 事件)")
        return recording


class TouchRecorder:
    """錄製真人觸控操作"""

    def __init__(self, adb: AdbController):
        self.adb = adb

    def record(self, duration: float = 10.0, name: str = "") -> TouchRecording:
        """
        錄製觸控操作

        透過 adb getevent 擷取觸控事件
        """
        logger.info(f"🎬 開始錄製 ({duration}s)，請在裝置上操作...")

        import subprocess

        cmd = ["adb"]
        serial = getattr(self.adb, '_serial', None)
        if serial:
            cmd += ["-s", serial]
        cmd += ["shell", "getevent", "-lt"]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        events: list[TouchEvent] = []
        start_time = time.time()
        current_x = 0
        current_y = 0
        is_touching = False

        try:
            while time.time() - start_time < duration:
                line = process.stdout.readline()
                if not line:
                    break

                line = line.decode("utf-8", errors="ignore").strip()
                elapsed = time.time() - start_time

                # 解析 getevent 輸出
                # 格式: [timestamp] /dev/input/eventX: type code value
                if "ABS_MT_POSITION_X" in line:
                    try:
                        val = line.split()[-1]
                        current_x = int(val, 16) if val.startswith("0") else int(val)
                    except (ValueError, IndexError):
                        pass

                elif "ABS_MT_POSITION_Y" in line:
                    try:
                        val = line.split()[-1]
                        current_y = int(val, 16) if val.startswith("0") else int(val)
                    except (ValueError, IndexError):
                        pass

                elif "ABS_MT_TRACKING_ID" in line:
                    try:
                        val = line.split()[-1]
                        tracking_id = int(val, 16) if val.startswith("0") else int(val)
                    except (ValueError, IndexError):
                        tracking_id = -1

                    if tracking_id >= 0 and not is_touching:
                        is_touching = True
                        events.append(TouchEvent(
                            timestamp=elapsed,
                            event_type="down",
                            x=current_x,
                            y=current_y,
                        ))
                    elif tracking_id < 0 and is_touching:
                        is_touching = False
                        events.append(TouchEvent(
                            timestamp=elapsed,
                            event_type="up",
                            x=current_x,
                            y=current_y,
                        ))

                elif "SYN_REPORT" in line and is_touching:
                    events.append(TouchEvent(
                        timestamp=elapsed,
                        event_type="move",
                        x=current_x,
                        y=current_y,
                    ))

        finally:
            process.terminate()
            process.wait(timeout=3)

        recording = TouchRecording(
            events=events,
            screen_size=self.adb.screen_size,
            duration=time.time() - start_time,
            name=name,
        )

        logger.info(f"✅ 錄製完成: {len(events)} 事件, {recording.duration:.1f}s")
        return recording


class TouchReplayer:
    """回放觸控操作"""

    def __init__(self, adb: AdbController):
        self.adb = adb

    def replay(
        self,
        recording: TouchRecording,
        jitter: int = 5,
        speed: float = 1.0,
        offset: tuple[int, int] = (0, 0),
    ) -> None:
        """
        回放錄製的觸控操作

        Args:
            jitter: 座標隨機偏移量
            speed: 回放速度倍率 (2.0 = 2倍速)
            offset: 座標偏移 (x, y)
        """
        if not recording.events:
            logger.warning("錄製為空")
            return

        logger.info(
            f"▶️ 回放: {recording.name or '未命名'} "
            f"({len(recording.events)} 事件, speed={speed}x)"
        )

        # 計算座標縮放（如果錄製的解析度不同）
        scale_x, scale_y = 1.0, 1.0
        if recording.screen_size[0] > 0 and recording.screen_size[1] > 0:
            current_size = self.adb.screen_size
            scale_x = current_size[0] / recording.screen_size[0]
            scale_y = current_size[1] / recording.screen_size[1]

        prev_time = recording.events[0].timestamp

        for event in recording.events:
            # 等待間隔
            wait = (event.timestamp - prev_time) / speed
            if wait > 0:
                time.sleep(wait)
            prev_time = event.timestamp

            # 計算座標
            x = int(event.x * scale_x) + offset[0] + random.randint(-jitter, jitter)
            y = int(event.y * scale_y) + offset[1] + random.randint(-jitter, jitter)

            # 執行事件
            if event.event_type == "down":
                # 觸控按下 = 移動到該點
                pass  # 在 move/up 時才發送
            elif event.event_type == "up":
                # 如果是單次 tap（down 後很快 up）
                self.adb.tap(x, y)
            elif event.event_type == "move":
                # 移動事件在 swipe 場景中處理
                pass

        logger.info("⏹️ 回放完成")

    def replay_as_swipes(
        self,
        recording: TouchRecording,
        jitter: int = 3,
        speed: float = 1.0,
    ) -> None:
        """
        將錄製轉換為 swipe 指令回放

        比 replay 更可靠（不需要 sendevent 權限）
        """
        if not recording.events:
            return

        # 把事件分組：每個 down→up 為一組
        groups: list[list[TouchEvent]] = []
        current_group: list[TouchEvent] = []

        for event in recording.events:
            current_group.append(event)
            if event.event_type == "up":
                groups.append(current_group)
                current_group = []

        for group in groups:
            if len(group) < 2:
                continue

            start = group[0]
            end = group[-1]
            duration = end.timestamp - start.timestamp

            sx = start.x + random.randint(-jitter, jitter)
            sy = start.y + random.randint(-jitter, jitter)
            ex = end.x + random.randint(-jitter, jitter)
            ey = end.y + random.randint(-jitter, jitter)

            duration_ms = max(50, int(duration * 1000 / speed))

            if abs(sx - ex) < 10 and abs(sy - ey) < 10:
                # 幾乎沒移動 → tap
                self.adb.tap(sx, sy)
            else:
                self.adb.swipe(sx, sy, ex, ey, duration_ms)

            time.sleep(random.uniform(0.05, 0.15))
