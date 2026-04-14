"""輸入模擬器 — 帶隨機抖動的人類化操作

支援:
- 隨機偏移 + 延遲的基礎人類化
- Bezier 曲線滑動軌跡（非線性）
- 觸控壓力隨機變化
- 操作節奏模式（casual / focused / random）
- 拖放、縮放等複合手勢
"""

from __future__ import annotations

import math
import random
import time
from enum import Enum, auto

from loguru import logger

from .adb_controller import AdbController


class Rhythm(Enum):
    """操作節奏模式"""
    CASUAL = auto()   # 慢、停頓多（掛機場景）
    FOCUSED = auto()  # 快、精準（戰鬥場景）
    RANDOM = auto()   # 混合模式


# 節奏參數表
RHYTHM_PARAMS = {
    Rhythm.CASUAL: {
        "tap_delay": (0.08, 0.25),
        "action_delay": (1.2, 2.5),
        "swipe_duration_factor": 1.3,
    },
    Rhythm.FOCUSED: {
        "tap_delay": (0.02, 0.08),
        "action_delay": (0.4, 0.8),
        "swipe_duration_factor": 0.7,
    },
    Rhythm.RANDOM: {
        "tap_delay": (0.03, 0.2),
        "action_delay": (0.5, 2.0),
        "swipe_duration_factor": 1.0,
    },
}


class InputSimulator:
    """
    包裝 AdbController 的輸入操作，加上隨機偏移和延遲
    讓操作看起來更像真人
    """

    def __init__(
        self,
        adb: AdbController,
        tap_offset: int = 10,
        tap_delay: tuple[float, float] = (0.05, 0.15),
        action_delay: tuple[float, float] = (0.8, 1.5),
        use_bezier: bool = True,
        rhythm: Rhythm | str = Rhythm.CASUAL,
    ):
        self.adb = adb
        self.tap_offset = tap_offset
        self.tap_delay = tap_delay
        self.action_delay = action_delay
        self.use_bezier = use_bezier

        if isinstance(rhythm, str):
            rhythm = Rhythm[rhythm.upper()]
        self._rhythm = rhythm
        self._apply_rhythm()

    @property
    def rhythm(self) -> Rhythm:
        return self._rhythm

    @rhythm.setter
    def rhythm(self, value: Rhythm | str) -> None:
        if isinstance(value, str):
            value = Rhythm[value.upper()]
        self._rhythm = value
        self._apply_rhythm()
        logger.info(f"🎵 操作節奏: {value.name}")

    def _apply_rhythm(self) -> None:
        """套用節奏參數"""
        params = RHYTHM_PARAMS[self._rhythm]
        self.tap_delay = params["tap_delay"]
        self.action_delay = params["action_delay"]
        self._swipe_factor = params["swipe_duration_factor"]

    def _jitter(self, value: int, offset: int | None = None) -> int:
        """加隨機偏移"""
        offset = offset or self.tap_offset
        return value + random.randint(-offset, offset)

    def _wait_tap(self) -> None:
        """點擊後短延遲"""
        time.sleep(random.uniform(*self.tap_delay))

    def _wait_action(self) -> None:
        """操作間延遲"""
        time.sleep(random.uniform(*self.action_delay))

    def wait(self, min_sec: float = 0.5, max_sec: float | None = None) -> None:
        """自訂等待"""
        max_sec = max_sec or min_sec * 1.3
        duration = random.uniform(min_sec, max_sec)
        logger.debug(f"⏳ 等待 {duration:.2f}s")
        time.sleep(duration)

    # ── 點擊 ──────────────────────────────────────────────

    def tap(self, x: int, y: int, offset: int | None = None) -> None:
        """帶隨機偏移的點擊"""
        jx = self._jitter(x, offset)
        jy = self._jitter(y, offset)
        self.adb.tap(jx, jy)
        self._wait_tap()

    def tap_match(self, match, offset: int | None = None) -> None:
        """點擊 MatchResult 的位置"""
        self.tap(match.x, match.y, offset)

    def double_tap(self, x: int, y: int) -> None:
        """雙擊"""
        self.tap(x, y)
        time.sleep(random.uniform(0.05, 0.1))
        self.tap(x, y)

    def multi_tap(self, x: int, y: int, count: int = 3, interval: tuple[float, float] = (0.08, 0.15)) -> None:
        """多次點擊"""
        for _ in range(count):
            self.tap(x, y)
            time.sleep(random.uniform(*interval))

    # ── Bezier 曲線計算 ──────────────────────────────────

    @staticmethod
    def _bezier_point(
        t: float,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> tuple[float, float]:
        """計算三次 Bezier 曲線上的點"""
        u = 1 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t

        x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        return (x, y)

    @staticmethod
    def _generate_bezier_path(
        start: tuple[int, int],
        end: tuple[int, int],
        num_points: int = 20,
        curvature: float = 0.3,
    ) -> list[tuple[int, int]]:
        """
        產生 Bezier 曲線路徑

        Args:
            curvature: 彎曲程度 (0=直線, 1=很彎)

        Returns:
            座標點列表
        """
        sx, sy = float(start[0]), float(start[1])
        ex, ey = float(end[0]), float(end[1])

        dx = ex - sx
        dy = ey - sy
        dist = math.sqrt(dx * dx + dy * dy)

        # 隨機控制點（垂直於直線方向偏移）
        offset1 = dist * curvature * random.uniform(-1, 1)
        offset2 = dist * curvature * random.uniform(-1, 1)

        # 控制點在 1/3 和 2/3 位置
        cp1 = (
            sx + dx * 0.33 + (-dy / dist) * offset1 if dist > 0 else sx,
            sy + dy * 0.33 + (dx / dist) * offset1 if dist > 0 else sy,
        )
        cp2 = (
            sx + dx * 0.67 + (-dy / dist) * offset2 if dist > 0 else ex,
            sy + dy * 0.67 + (dx / dist) * offset2 if dist > 0 else ey,
        )

        # 產生路徑點（ease-in-out 速度分佈）
        path = []
        for i in range(num_points):
            # ease-in-out: 3t² - 2t³
            t_linear = i / max(num_points - 1, 1)
            t = 3 * t_linear * t_linear - 2 * t_linear * t_linear * t_linear

            px, py = InputSimulator._bezier_point(
                t, (sx, sy), cp1, cp2, (ex, ey)
            )
            # 加微量抖動
            px += random.gauss(0, 1.5)
            py += random.gauss(0, 1.5)
            path.append((int(px), int(py)))

        return path

    # ── 滑動 ──────────────────────────────────────────────

    def swipe(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        duration_ms: int = 500,
        jitter: bool = True,
        use_bezier: bool | None = None,
    ) -> None:
        """帶抖動的滑動"""
        bezier = use_bezier if use_bezier is not None else self.use_bezier
        duration_ms = int(duration_ms * self._swipe_factor)

        if jitter:
            x1 = self._jitter(x1, 5)
            y1 = self._jitter(y1, 5)
            x2 = self._jitter(x2, 5)
            y2 = self._jitter(y2, 5)
            duration_ms += random.randint(-50, 50)
        duration_ms = max(100, duration_ms)

        if bezier:
            self._swipe_bezier(x1, y1, x2, y2, duration_ms)
        else:
            self.adb.swipe(x1, y1, x2, y2, duration_ms)

        self._wait_tap()

    def _swipe_bezier(
        self,
        x1: int, y1: int,
        x2: int, y2: int,
        duration_ms: int,
    ) -> None:
        """使用 Bezier 曲線的滑動（透過 sendevent 或分段 swipe）"""
        path = self._generate_bezier_path(
            (x1, y1), (x2, y2),
            num_points=max(10, duration_ms // 30),
            curvature=random.uniform(0.1, 0.3),
        )

        # 嘗試用 sendevent（更精確）
        try:
            self._sendevent_path(path, duration_ms)
        except Exception:
            # Fallback: 用多段短 swipe 模擬曲線
            self._multi_segment_swipe(path, duration_ms)

    def _sendevent_path(self, path: list[tuple[int, int]], duration_ms: int) -> None:
        """透過 sendevent 發送觸控軌跡"""
        if len(path) < 2:
            return

        interval = duration_ms / len(path) / 1000.0

        # 取得觸控裝置
        device = self.adb.device
        # 嘗試找到 touchscreen 裝置節點
        event_device = self._find_touch_device()
        if not event_device:
            raise RuntimeError("找不到觸控裝置")

        # 組合 sendevent 指令（批次執行減少延遲）
        commands = []

        # Touch down
        x, y = path[0]
        commands.append(
            f"sendevent {event_device} 3 57 0;"  # ABS_MT_TRACKING_ID
            f"sendevent {event_device} 3 53 {x};"  # ABS_MT_POSITION_X
            f"sendevent {event_device} 3 54 {y};"  # ABS_MT_POSITION_Y
            f"sendevent {event_device} 3 58 {random.randint(40, 60)};"  # ABS_MT_PRESSURE
            f"sendevent {event_device} 0 0 0"  # SYN_REPORT
        )

        # Move
        for x, y in path[1:-1]:
            pressure = random.randint(35, 65)  # 隨機壓力
            commands.append(
                f"sendevent {event_device} 3 53 {x};"
                f"sendevent {event_device} 3 54 {y};"
                f"sendevent {event_device} 3 58 {pressure};"
                f"sendevent {event_device} 0 0 0"
            )

        # Touch up
        commands.append(
            f"sendevent {event_device} 3 57 -1;"  # ABS_MT_TRACKING_ID = -1
            f"sendevent {event_device} 0 0 0"
        )

        # 逐步執行（帶間隔）
        for cmd in commands:
            device.shell(cmd)
            time.sleep(interval)

    def _find_touch_device(self) -> str | None:
        """找到觸控輸入裝置節點"""
        try:
            output = self.adb.device.shell("getevent -pl 2>/dev/null | grep -B5 ABS_MT_POSITION")
            for line in output.split("\n"):
                if "/dev/input/" in line:
                    return line.strip().split(":")[0].strip()
        except Exception:
            pass

        # 常見預設
        for dev in ["/dev/input/event1", "/dev/input/event2", "/dev/input/event0"]:
            try:
                result = self.adb.device.shell(f"getevent -pl {dev} 2>/dev/null | head -1")
                if result.strip():
                    return dev
            except Exception:
                continue

        return None

    def _multi_segment_swipe(self, path: list[tuple[int, int]], duration_ms: int) -> None:
        """用多段短 swipe 模擬曲線（fallback）"""
        if len(path) < 2:
            return

        segment_duration = max(50, duration_ms // (len(path) - 1))
        for i in range(len(path) - 1):
            x1, y1 = path[i]
            x2, y2 = path[i + 1]
            self.adb.swipe(x1, y1, x2, y2, segment_duration)

    # ── 方向滑動 ──────────────────────────────────────────

    def swipe_up(self, distance: int = 800) -> None:
        """往上滑"""
        w, h = self.adb.screen_size
        cx = w // 2
        cy = h // 2
        self.swipe(cx, cy + distance // 2, cx, cy - distance // 2)

    def swipe_down(self, distance: int = 800) -> None:
        """往下滑"""
        w, h = self.adb.screen_size
        cx = w // 2
        cy = h // 2
        self.swipe(cx, cy - distance // 2, cx, cy + distance // 2)

    def swipe_left(self, distance: int = 600) -> None:
        """往左滑"""
        w, h = self.adb.screen_size
        cx = w // 2
        cy = h // 2
        self.swipe(cx + distance // 2, cy, cx - distance // 2, cy)

    def swipe_right(self, distance: int = 600) -> None:
        """往右滑"""
        w, h = self.adb.screen_size
        cx = w // 2
        cy = h // 2
        self.swipe(cx - distance // 2, cy, cx + distance // 2, cy)

    # ── 複合操作 ──────────────────────────────────────────

    def tap_and_wait(self, x: int, y: int, wait: float = 1.0) -> None:
        """點擊後等待指定時間"""
        self.tap(x, y)
        self.wait(wait, wait * 1.3)

    def find_and_tap(self, matcher, screenshot, template_name: str, threshold: float | None = None) -> bool:
        """找到模板就點擊，回傳是否成功"""
        match = matcher.find(screenshot, template_name, threshold)
        if match:
            self.tap_match(match)
            self._wait_action()
            return True
        return False

    def drag_and_drop(
        self,
        from_x: int, from_y: int,
        to_x: int, to_y: int,
        hold_ms: int = 300,
        move_ms: int = 800,
    ) -> None:
        """拖放操作：按住 → 移動 → 放開"""
        fx = self._jitter(from_x, 5)
        fy = self._jitter(from_y, 5)
        tx = self._jitter(to_x, 5)
        ty = self._jitter(to_y, 5)

        total_ms = hold_ms + move_ms
        # 用 long swipe 模擬：起點按住一段時間再移動
        self.adb.swipe(fx, fy, tx, ty, total_ms)
        logger.debug(f"🖐️ 拖放 ({fx},{fy}) → ({tx},{ty})")
        self._wait_tap()

    def pinch_zoom(self, center_x: int, center_y: int, zoom_in: bool = True, distance: int = 200) -> None:
        """
        縮放手勢（模擬雙指）

        注意：需要裝置支援多點觸控 sendevent
        """
        if zoom_in:
            # 兩指從外往內
            d = distance // 2
            self.adb.device.shell(
                f"input swipe {center_x - d} {center_y} {center_x - d // 2} {center_y} 300 & "
                f"input swipe {center_x + d} {center_y} {center_x + d // 2} {center_y} 300"
            )
        else:
            # 兩指從內往外
            d = distance // 4
            self.adb.device.shell(
                f"input swipe {center_x - d} {center_y} {center_x - distance // 2} {center_y} 300 & "
                f"input swipe {center_x + d} {center_y} {center_x + distance // 2} {center_y} 300"
            )
        logger.debug(f"🔍 {'放大' if zoom_in else '縮小'} 中心=({center_x},{center_y})")
        self._wait_tap()

