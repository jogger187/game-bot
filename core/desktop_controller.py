"""桌面應用視窗擷取 + 輸入控制（macOS Quartz）

支援：
- 指定視窗名稱 / window ID 擷取畫面
- 背景截圖（視窗不需要在最前面）
- 背景滑鼠/鍵盤事件（透過 CGEvent → 指定 PID）
- 與 AdbController 相同介面，可直接替換

使用方式：
    from core.desktop_controller import DesktopController

    dc = DesktopController(window_title="BlueStacks")
    dc.connect()
    img = dc.screenshot()
    dc.tap(100, 200)
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger
from PIL import Image

# macOS Quartz — lazy import
_Quartz = None


def _ensure_quartz():
    """延遲載入 Quartz，避免在非 macOS 環境直接報錯"""
    global _Quartz
    if _Quartz is not None:
        return

    if platform.system() != "Darwin":
        raise RuntimeError("DesktopController 目前僅支援 macOS")

    import Quartz  # pyobjc-framework-Quartz（包含 CoreGraphics）

    _Quartz = Quartz


@dataclass
class DesktopWindow:
    """偵測到的桌面視窗"""

    window_id: int
    owner_name: str  # app 名稱
    window_name: str  # 視窗標題
    pid: int
    bounds: dict  # {X, Y, Width, Height}
    layer: int = 0

    @property
    def width(self) -> int:
        return int(self.bounds.get("Width", 0))

    @property
    def height(self) -> int:
        return int(self.bounds.get("Height", 0))

    @property
    def x(self) -> int:
        return int(self.bounds.get("X", 0))

    @property
    def y(self) -> int:
        return int(self.bounds.get("Y", 0))

    def to_dict(self) -> dict:
        return {
            "window_id": self.window_id,
            "owner_name": self.owner_name,
            "window_name": self.window_name,
            "pid": self.pid,
            "width": self.width,
            "height": self.height,
            "x": self.x,
            "y": self.y,
        }


class DesktopController:
    """桌面視窗擷取與控制 — 與 AdbController 相同介面

    macOS 實作：
    - 截圖：CGWindowListCreateImage（可背景擷取）
    - 輸入：CGEvent POST 到指定 PID（背景操作）
    """

    def __init__(
        self,
        window_title: str | None = None,
        window_id: int | None = None,
        capture_fps: int = 10,
    ):
        self._window_title = window_title
        self._window_id = window_id
        self._capture_fps = capture_fps

        self._target_window: DesktopWindow | None = None
        self._connected = False
        self._last_scale = 1.0  # 用於紀錄 Retina 截圖與 bounds(points) 的縮放比例

    # ── 視窗偵測 ──────────────────────────────────────────

    @staticmethod
    def list_windows(include_offscreen: bool = False) -> list[DesktopWindow]:
        """列舉所有可見的桌面視窗

        Args:
            include_offscreen: 是否包含離屏 / 最小化的視窗
        """
        _ensure_quartz()

        options = _Quartz.kCGWindowListOptionOnScreenOnly
        if include_offscreen:
            options = _Quartz.kCGWindowListOptionAll

        window_list = _Quartz.CGWindowListCopyWindowInfo(
            options | _Quartz.kCGWindowListExcludeDesktopElements,
            _Quartz.kCGNullWindowID,
        )

        results: list[DesktopWindow] = []
        for win in window_list or []:
            owner = win.get(_Quartz.kCGWindowOwnerName, "")
            name = win.get(_Quartz.kCGWindowName, "")
            bounds = win.get(_Quartz.kCGWindowBounds, {})
            w = int(bounds.get("Width", 0))
            h = int(bounds.get("Height", 0))
            layer = int(win.get(_Quartz.kCGWindowLayer, 0))

            # 過濾無尺寸或系統內部視窗
            if w < 50 or h < 50:
                continue
            if layer < 0:
                continue
            # 跳過自己 (Python)
            if owner in ("Python", "python3", "Terminal", "iTerm2"):
                continue

            results.append(
                DesktopWindow(
                    window_id=int(win.get(_Quartz.kCGWindowNumber, 0)),
                    owner_name=owner,
                    window_name=name,
                    pid=int(win.get(_Quartz.kCGWindowOwnerPID, 0)),
                    bounds=dict(bounds),
                    layer=layer,
                )
            )

        return results

    def _find_window(self) -> DesktopWindow | None:
        """根據 window_title 或 window_id 找到目標視窗"""
        windows = self.list_windows(include_offscreen=True)

        if self._window_id is not None:
            for w in windows:
                if w.window_id == self._window_id:
                    return w
            return None

        if self._window_title:
            title_lower = self._window_title.lower()
            # 精確匹配 owner_name 或 window_name
            exact = [w for w in windows
                     if title_lower == w.owner_name.lower() or title_lower == w.window_name.lower()]
            if exact:
                # 多個匹配時，選最大的（最可能是主視窗）
                return max(exact, key=lambda w: w.width * w.height)
            # 模糊匹配
            fuzzy = [w for w in windows
                     if title_lower in w.owner_name.lower() or title_lower in w.window_name.lower()]
            if fuzzy:
                return max(fuzzy, key=lambda w: w.width * w.height)

        return None

    # ── 連線管理 ──────────────────────────────────────────

    def connect(self, serial: str | None = None) -> None:
        """找到目標視窗並準備擷取

        Args:
            serial: 忽略（保持與 AdbController 介面相容）
        """
        _ensure_quartz()

        win = self._find_window()
        if win is None:
            available = self.list_windows()
            names = [f"  {w.owner_name}: {w.window_name} (id={w.window_id})" for w in available[:10]]
            raise RuntimeError(
                f"找不到視窗: title={self._window_title!r}, id={self._window_id}\n"
                f"可用視窗:\n" + "\n".join(names)
            )

        self._target_window = win
        self._connected = True
        logger.info(
            f"✅ 桌面視窗已連線: {win.owner_name} - {win.window_name} "
            f"(id={win.window_id}, {win.width}x{win.height}, pid={win.pid})"
        )

    def connect_tcp(self, host: str = "127.0.0.1", port: int = 5555) -> None:
        """不適用 — 保持介面相容"""
        self.connect()

    @property
    def device(self) -> Any:
        """模擬 adb.device — 回傳自身，讓 device.shell() 不 crash"""
        return self

    @property
    def serial(self) -> str:
        """模擬 device.serial"""
        if self._target_window:
            return f"desktop:{self._target_window.window_id}"
        return "desktop:unknown"

    def shell(self, cmd: str) -> str:
        """模擬 device.shell — 桌面模式不支援，靜默忽略"""
        logger.debug(f"⚠️ Desktop mode: shell 指令已忽略: {cmd}")
        return ""

    @property
    def screen_size(self) -> tuple[int, int]:
        """回傳 (width, height)"""
        self._refresh_bounds()
        if self._target_window:
            return (self._target_window.width, self._target_window.height)
        return (0, 0)

    def _refresh_bounds(self) -> None:
        """重新取得視窗位置（因為使用者可能移動視窗）"""
        if not self._target_window:
            return
        win = self._find_window()
        if win:
            self._target_window = win

    # ── 截圖 ──────────────────────────────────────────────

    def screenshot(self) -> Image.Image:
        """截取目標視窗畫面

        擷取策略（依序嘗試）：
        1. CGWindowListCreateImage 單視窗模式（可背景擷取）
        2. 全螢幕截圖 + crop 到視窗 bounds（視窗需在螢幕上）
        3. screencapture CLI fallback（最通用）
        """
        if not self._connected or not self._target_window:
            raise RuntimeError("尚未連線，請先呼叫 connect()")

        _ensure_quartz()
        self._refresh_bounds()

        wid = self._target_window.window_id

        # ── 策略 1: 單視窗擷取（可背景）──
        cg_image = _Quartz.CGWindowListCreateImage(
            _Quartz.CGRectNull,
            _Quartz.kCGWindowListOptionIncludingWindow,
            wid,
            _Quartz.kCGWindowImageBoundsIgnoreFraming,
        )

        img = None
        if cg_image is not None:
            img = self._cgimage_to_pil(cg_image)
            logger.debug(f"📸 桌面截圖完成 [單視窗] ({img.width}x{img.height})")

        # ── 策略 2: 全螢幕 + crop（Metal/GPU app fallback）──
        if img is None:
            img = self._screenshot_fullscreen_crop()
            if img is not None:
                logger.debug(f"📸 桌面截圖完成 [全螢幕crop] ({img.width}x{img.height})")

        # ── 策略 3: screencapture CLI ──
        if img is None:
            img = self._screenshot_cli()
            if img is not None:
                logger.debug(f"📸 桌面截圖完成 [CLI] ({img.width}x{img.height})")

        if img is None:
            raise RuntimeError(
                f"截圖失敗：視窗 id={wid}，三種方式皆失敗。\n"
                f"請確認：1) 視窗未最小化 2) 已授權螢幕錄製權限"
            )

        if img.width < 200 or img.height < 200:
            raise RuntimeError(
                f"截圖尺寸異常小 ({img.width}x{img.height})。\n"
                f"請確認目標應用【沒有被最小化到 Dock】（可以被其他視窗遮擋，但不能使用黃色按鈕縮小）。"
            )

        # 紀錄截圖與 bounds 的比例 (Retina 螢幕可能為 2.0)
        bounds_w = self._target_window.width
        if bounds_w > 0:
            self._last_scale = img.width / bounds_w

        return img

    def _cgimage_to_pil(self, cg_image) -> Image.Image:
        """將 CGImage 轉換為 PIL Image"""
        width = _Quartz.CGImageGetWidth(cg_image)
        height = _Quartz.CGImageGetHeight(cg_image)
        bytes_per_row = _Quartz.CGImageGetBytesPerRow(cg_image)

        data_provider = _Quartz.CGImageGetDataProvider(cg_image)
        raw_data = _Quartz.CGDataProviderCopyData(data_provider)

        # macOS CGImage 是 BGRA 格式
        arr = np.frombuffer(raw_data, dtype=np.uint8)
        arr = arr.reshape((height, bytes_per_row // 4, 4))
        arr = arr[:height, :width, :]  # 去掉 row padding

        # BGRA → RGB
        return Image.fromarray(arr[:, :, [2, 1, 0]], "RGB")

    def _screenshot_fullscreen_crop(self) -> Image.Image | None:
        """全螢幕截圖後 crop 到視窗 bounds（適用 Metal/GPU 渲染的 app）"""
        try:
            cg_image = _Quartz.CGWindowListCreateImage(
                _Quartz.CGRectInfinite,
                _Quartz.kCGWindowListOptionOnScreenOnly,
                _Quartz.kCGNullWindowID,
                _Quartz.kCGWindowImageDefault,
            )
            if cg_image is None:
                return None

            full_img = self._cgimage_to_pil(cg_image)

            # Retina 螢幕：CGImage pixel 尺寸可能是 bounds 的 2x
            screen_w = _Quartz.CGDisplayPixelsWide(_Quartz.CGMainDisplayID())
            img_w = full_img.width
            scale = img_w / screen_w if screen_w > 0 else 1.0

            b = self._target_window.bounds
            x = int(b.get("X", 0) * scale)
            y = int(b.get("Y", 0) * scale)
            w = int(b.get("Width", 0) * scale)
            h = int(b.get("Height", 0) * scale)

            if w <= 0 or h <= 0:
                return None

            cropped = full_img.crop((x, y, x + w, y + h))
            return cropped
        except Exception as e:
            logger.debug(f"全螢幕 crop 失敗: {e}")
            return None

    def _screenshot_cli(self) -> Image.Image | None:
        """使用 macOS screencapture 命令擷取指定視窗"""
        import subprocess
        import tempfile

        if not self._target_window:
            return None

        wid = self._target_window.window_id
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp_path = f.name

            # screencapture -l<windowid> 可以擷取指定視窗（含 Metal）
            result = subprocess.run(
                ["screencapture", "-x", f"-l{wid}", tmp_path],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                img = Image.open(tmp_path).convert("RGB")
                return img
            return None
        except Exception as e:
            logger.debug(f"screencapture CLI 失敗: {e}")
            return None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def screenshot_np(self) -> np.ndarray:
        """截圖並回傳 numpy array (BGR for OpenCV)"""
        img = self.screenshot()
        arr = np.array(img)
        return arr[:, :, ::-1].copy()

    def save_screenshot(self, path: str | Path) -> Path:
        """截圖並儲存到檔案"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img = self.screenshot()
        img.save(str(path))
        logger.debug(f"💾 截圖已存: {path}")
        return path

    # ── 座標轉換 ──────────────────────────────────────────

    def _to_screen_coords(self, x: int, y: int) -> tuple[float, float]:
        """將視窗相對座標轉換為螢幕絕對座標
        注意：傳入的 x, y 通常是基於截圖像素大小的座標
        我們必須根據 self._last_scale 轉換回 points
        """
        self._refresh_bounds()
        if not self._target_window:
            raise RuntimeError("視窗未連線")
            
        point_x = x / self._last_scale
        point_y = y / self._last_scale
        
        sx = self._target_window.x + point_x
        sy = self._target_window.y + point_y
        logger.debug(f"📐 座標轉換: pixel({x}, {y}) -> scale({self._last_scale}) -> point({point_x}, {point_y}) -> screen({sx}, {sy})")
        return float(sx), float(sy)

    # ── 輸入操作（背景 CGEvent → 指定 PID）──────────────

    def _post_mouse_event(
        self,
        event_type: int,
        x: int,
        y: int,
        click_count: int = 1,
    ) -> None:
        """發送滑鼠事件到目標視窗（安全模式：activate + global post）

        策略：先將目標 app 拉到前景，再用 CGEventPost 全域注入。
        注意：不使用 CGEventPostToPid，因為它會對 sandboxed app 發送 SIGBUS，
        而 SIGBUS 是 OS 信號，Python try/except 無法攔截。
        """
        _ensure_quartz()

        if not self._target_window:
            raise RuntimeError("視窗未連線")

        sx, sy = self._to_screen_coords(x, y)
        point = _Quartz.CGPointMake(sx, sy)

        event = _Quartz.CGEventCreateMouseEvent(
            None,
            event_type,
            point,
            _Quartz.kCGMouseButtonLeft,
        )

        if click_count > 1:
            _Quartz.CGEventSetIntegerValueField(
                event, _Quartz.kCGMouseEventClickState, click_count
            )

        # 1. 先將目標 app 拉到前景
        self._activate_app()

        # 2. 安全的全域事件注入（官方 API，不會 crash）
        _Quartz.CGEventPost(_Quartz.kCGHIDEventTap, event)

    def tap(self, x: int, y: int, hold_ms: int = 0) -> None:
        """點擊視窗座標（背景操作）"""
        self._post_mouse_event(_Quartz.kCGEventLeftMouseDown, x, y)
        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)
        else:
            time.sleep(0.02)
        self._post_mouse_event(_Quartz.kCGEventLeftMouseUp, x, y)
        logger.debug(f"👆 桌面點擊 ({x}, {y}){f' 長按 {hold_ms}ms' if hold_ms > 0 else ''}")

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 500,
    ) -> None:
        """滑動（背景操作）"""
        _ensure_quartz()

        if not self._target_window:
            raise RuntimeError("視窗未連線")

        steps = max(10, duration_ms // 20)
        interval = duration_ms / steps / 1000.0

        # Mouse down at start
        self._post_mouse_event(_Quartz.kCGEventLeftMouseDown, x1, y1)

        # Drag
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)

            sx, sy = self._to_screen_coords(cx, cy)
            point = _Quartz.CGPointMake(sx, sy)

            event = _Quartz.CGEventCreateMouseEvent(
                None,
                _Quartz.kCGEventLeftMouseDragged,
                point,
                _Quartz.kCGMouseButtonLeft,
            )
            _Quartz.CGEventPost(_Quartz.kCGHIDEventTap, event)
            time.sleep(interval)

        # Mouse up at end
        self._post_mouse_event(_Quartz.kCGEventLeftMouseUp, x2, y2)
        logger.debug(f"👉 桌面滑動 ({x1},{y1}) → ({x2},{y2}) {duration_ms}ms")

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """長按"""
        self._post_mouse_event(_Quartz.kCGEventLeftMouseDown, x, y)
        time.sleep(duration_ms / 1000.0)
        self._post_mouse_event(_Quartz.kCGEventLeftMouseUp, x, y)
        logger.debug(f"👇 桌面長按 ({x}, {y}) {duration_ms}ms")

    def _activate_app(self) -> None:
        """將目標 app 拉到前景"""
        if not self._target_window:
            return
        import AppKit
        app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(
            self._target_window.pid
        )
        if app:
            app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
            time.sleep(0.03)

    def _post_keyboard_event(self, event) -> None:
        """安全發送鍵盤事件（與 _post_mouse_event 同策略）"""
        _Quartz.CGEventPost(_Quartz.kCGHIDEventTap, event)

    def input_text(self, text: str) -> None:
        """輸入文字"""
        _ensure_quartz()

        if not self._target_window:
            raise RuntimeError("視窗未連線")

        # 確保 app 在前景
        self._activate_app()

        for char in text:
            event_down = _Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            event_up = _Quartz.CGEventCreateKeyboardEvent(None, 0, False)

            _Quartz.CGEventKeyboardSetUnicodeString(
                event_down, len(char), char
            )
            _Quartz.CGEventKeyboardSetUnicodeString(
                event_up, len(char), char
            )

            self._post_keyboard_event(event_down)
            time.sleep(0.01)
            self._post_keyboard_event(event_up)
            time.sleep(0.02)

        logger.debug(f"⌨️ 桌面輸入: {text}")

    def key_event(self, keycode: int | str) -> None:
        """發送按鍵事件

        keycode: macOS virtual keycode 或特殊名稱
        常用 keycode:
        - 36 = Return
        - 51 = Delete
        - 53 = Escape
        - 123/124/125/126 = 左右下上方向鍵
        """
        _ensure_quartz()

        if not self._target_window:
            raise RuntimeError("視窗未連線")

        if isinstance(keycode, str):
            keycode = _KEYCODE_MAP.get(keycode.upper(), 0)

        self._activate_app()

        event_down = _Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
        event_up = _Quartz.CGEventCreateKeyboardEvent(None, keycode, False)

        self._post_keyboard_event(event_down)
        time.sleep(0.02)
        self._post_keyboard_event(event_up)
        logger.debug(f"🔘 桌面按鍵: {keycode}")

    def back(self) -> None:
        """模擬返回 (Escape)"""
        self.key_event(53)  # Escape

    def home(self) -> None:
        """模擬 Home (Cmd+H)"""
        _ensure_quartz()
        if not self._target_window:
            return

        # Cmd+H
        event = _Quartz.CGEventCreateKeyboardEvent(None, 4, True)  # 4 = 'h'
        _Quartz.CGEventSetFlags(event, _Quartz.kCGEventFlagMaskCommand)
        self._post_keyboard_event(event)

        event_up = _Quartz.CGEventCreateKeyboardEvent(None, 4, False)
        self._post_keyboard_event(event_up)

    # ── App 控制（桌面不適用，保持介面相容）──────────────

    def launch_app(self, package: str, activity: str | None = None) -> None:
        """不適用"""
        logger.debug(f"⚠️ Desktop mode: launch_app 不適用 ({package})")

    def kill_app(self, package: str) -> None:
        """不適用"""
        logger.debug(f"⚠️ Desktop mode: kill_app 不適用 ({package})")

    def current_app(self) -> str:
        """回傳目標視窗 app 名稱"""
        if self._target_window:
            return self._target_window.owner_name
        return ""

    # ── 生命週期 ──────────────────────────────────────────

    def cleanup(self) -> None:
        """清理資源"""
        self._target_window = None
        self._connected = False

    def __del__(self):
        self.cleanup()


# macOS virtual keycode 對照表（常用）
_KEYCODE_MAP = {
    "RETURN": 36,
    "ENTER": 36,
    "TAB": 48,
    "SPACE": 49,
    "DELETE": 51,
    "BACKSPACE": 51,
    "ESCAPE": 53,
    "ESC": 53,
    "LEFT": 123,
    "RIGHT": 124,
    "DOWN": 125,
    "UP": 126,
    "F1": 122,
    "F2": 120,
    "F3": 99,
    "F4": 118,
    "F5": 96,
    "F6": 97,
    "F7": 98,
    "F8": 100,
    "F9": 101,
    "F10": 109,
    "F11": 103,
    "F12": 111,
    # Android-like mapping for compatibility
    "KEYCODE_BACK": 53,  # → Escape
    "KEYCODE_HOME": 115,  # → Home key
    "4": 53,  # Android BACK → Escape
    "3": 115,  # Android HOME → Home
}
