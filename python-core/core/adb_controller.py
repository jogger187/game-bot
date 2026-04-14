"""ADB 控制器 — 負責設備連線、截圖、基礎指令

支援三種截圖模式:
- ADB_SCREENCAP: 標準 adb screencap (~300-500ms)
- MINICAP: MiniCap 串流 (~30-50ms)
- EMULATOR: 模擬器直連 API
"""

from __future__ import annotations

import time
from enum import Enum, auto
from pathlib import Path

import adbutils
import numpy as np
from loguru import logger
from PIL import Image


class ScreenCapMethod(Enum):
    """截圖方式"""
    ADB_SCREENCAP = auto()  # 標準 adb（慢但通用）
    MINICAP = auto()        # MiniCap 串流（快）
    EMULATOR = auto()       # 模擬器 API 直連


class AdbController:
    """封裝 adbutils，提供截圖、點擊、滑動等操作"""

    # config 字串 → enum 對照
    _CAP_METHOD_MAP = {
        "adb": ScreenCapMethod.ADB_SCREENCAP,
        "adb_screencap": ScreenCapMethod.ADB_SCREENCAP,
        "minicap": ScreenCapMethod.MINICAP,
        "emulator": ScreenCapMethod.EMULATOR,
    }

    def __init__(
        self,
        serial: str | None = None,
        cap_method: ScreenCapMethod | str = ScreenCapMethod.ADB_SCREENCAP,
        minicap_quality: int = 80,
        minicap_fps: int = 10,
    ):
        self._client = adbutils.AdbClient()
        self._device: adbutils.AdbDevice | None = None
        self._serial = serial
        self._screen_size: tuple[int, int] | None = None

        # 延遲初始化（放在 cap_method 解析前，避免 __del__ crash）
        self._minicap_stream = None
        self._emulator_bridge = None

        # 截圖模式
        if isinstance(cap_method, str):
            cap_method = self._CAP_METHOD_MAP.get(
                cap_method.lower(), ScreenCapMethod.ADB_SCREENCAP
            )
        self._cap_method = cap_method
        self._minicap_quality = minicap_quality
        self._minicap_fps = minicap_fps

    @property
    def cap_method(self) -> ScreenCapMethod:
        return self._cap_method

    @cap_method.setter
    def cap_method(self, method: ScreenCapMethod | str) -> None:
        if isinstance(method, str):
            method = ScreenCapMethod[method.upper()]
        if method != self._cap_method:
            # 停止舊的串流
            if self._cap_method == ScreenCapMethod.MINICAP and self._minicap_stream:
                self._minicap_stream.stop()
                self._minicap_stream = None
            self._cap_method = method
            logger.info(f"📷 截圖模式切換: {method.name}")

    # ── 連線管理 ──────────────────────────────────────────

    def connect(self, serial: str | None = None) -> None:
        """連線到設備（USB 或已知 serial）"""
        serial = serial or self._serial

        # TCP serial（模擬器）自動先 connect
        if serial and ":" in serial:
            host, port = serial.rsplit(":", 1)
            self.connect_tcp(host, int(port))

        devices = self._client.device_list()

        if not devices:
            raise RuntimeError("❌ 找不到任何 ADB 設備，請確認 USB 偵錯已開啟或模擬器已啟動")

        if serial:
            self._device = self._client.device(serial)
        else:
            self._device = devices[0]

        info = self._device.info
        logger.info(f"✅ 已連線: {self._device.serial} ({info.get('brand', '?')} {info.get('model', '?')})")

    def connect_tcp(self, host: str = "127.0.0.1", port: int = 5555) -> None:
        """透過 TCP 連線到模擬器"""
        serial = f"{host}:{port}"
        try:
            self._client.connect(serial)
        except Exception as e:
            logger.warning(f"adbutils connect 失敗，嘗試 subprocess: {e}")
            import subprocess
            result = subprocess.run(
                ["adb", "connect", serial],
                capture_output=True, text=True, timeout=10,
            )
            if "connected" not in result.stdout.lower() and "already" not in result.stdout.lower():
                raise ConnectionError(f"ADB TCP 連線失敗: {result.stdout} {result.stderr}")

        self._serial = serial
        self._device = self._client.device(serial)
        logger.info(f"✅ TCP 已連線: {serial}")

    def connect_emulator(
        self,
        emu_type: str = "auto",
        install_path: str | None = None,
        index: int = 0,
    ) -> None:
        """透過模擬器橋接連線"""
        from .emulator_bridge import EmulatorBridge, EmulatorType

        if emu_type == "auto":
            self._emulator_bridge = EmulatorBridge.auto_detect(index=index)
        else:
            self._emulator_bridge = EmulatorBridge.create_by_type(
                emu_type=emu_type,
                install_path=install_path,
                index=index,
            )
        self._emulator_bridge.connect()
        self._cap_method = ScreenCapMethod.EMULATOR

        # 同時建立 ADB 連線（部分操作仍需要）
        if self._emulator_bridge.instance.adb_serial:
            try:
                self.connect_tcp(
                    *self._emulator_bridge.instance.adb_serial.split(":")
                )
            except Exception as e:
                logger.warning(f"模擬器 ADB 連線失敗（非致命）: {e}")

    @property
    def device(self) -> adbutils.AdbDevice:
        if self._device is None:
            raise RuntimeError("尚未連線，請先呼叫 connect()")
        return self._device

    @property
    def screen_size(self) -> tuple[int, int]:
        """回傳 (width, height)"""
        if self._screen_size is None:
            output = self.device.shell("wm size")
            # "Physical size: 1080x2400"
            size_str = output.strip().split(":")[-1].strip()
            w, h = size_str.split("x")
            self._screen_size = (int(w), int(h))
        return self._screen_size

    # ── 截圖 ──────────────────────────────────────────────

    def screenshot(self) -> Image.Image:
        """截圖並回傳 PIL Image（根據當前模式自動選擇方式）"""
        try:
            if self._cap_method == ScreenCapMethod.MINICAP:
                return self._screenshot_minicap()
            elif self._cap_method == ScreenCapMethod.EMULATOR:
                return self._screenshot_emulator()
            else:
                return self._screenshot_adb()
        except Exception as e:
            if self._cap_method != ScreenCapMethod.ADB_SCREENCAP:
                logger.warning(f"⚠️ {self._cap_method.name} 截圖失敗，降級到 ADB: {e}")
                return self._screenshot_adb()
            raise

    def _screenshot_adb(self) -> Image.Image:
        """標準 ADB 截圖"""
        img = self.device.screenshot()
        logger.debug(f"📸 ADB 截圖完成 ({img.size[0]}x{img.size[1]})")
        return img

    def _screenshot_minicap(self) -> Image.Image:
        """MiniCap 串流截圖"""
        if self._minicap_stream is None:
            from .minicap_stream import MiniCapStream
            self._minicap_stream = MiniCapStream(
                device_serial=self._serial,
                quality=self._minicap_quality,
                max_fps=self._minicap_fps,
            )
            self._minicap_stream.start()
        img = self._minicap_stream.screenshot()
        logger.debug(f"📸 MiniCap 截圖 (frame #{self._minicap_stream.frame_count})")
        return img

    def _screenshot_emulator(self) -> Image.Image:
        """模擬器 API 截圖"""
        if self._emulator_bridge is None:
            raise RuntimeError("模擬器橋接未初始化，請先呼叫 connect_emulator()")
        img = self._emulator_bridge.screenshot()
        logger.debug(f"📸 模擬器截圖完成 ({img.size[0]}x{img.size[1]})")
        return img

    def screenshot_np(self) -> np.ndarray:
        """截圖並回傳 numpy array (BGR for OpenCV)"""
        img = self.screenshot()
        arr = np.array(img)
        # PIL 是 RGB，OpenCV 要 BGR
        return arr[:, :, ::-1].copy()

    def save_screenshot(self, path: str | Path) -> Path:
        """截圖並儲存到檔案"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img = self.screenshot()
        img.save(str(path))
        logger.debug(f"💾 截圖已存: {path}")
        return path

    # ── 輸入操作 ──────────────────────────────────────────

    def _safe_shell(self, cmd: str) -> None:
        """安全執行 shell 指令，改用原生 subprocess 避免 BlueStacks 斷線"""
        import subprocess
        if not self.device:
            return
        try:
            # 直接使用原生 adb 指令，最穩定
            subprocess.run(
                ["adb", "-s", self.device.serial, "shell"] + cmd.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
        except Exception as e:
            logger.warning(f"ADB subprocess error: {e}")

    def tap(self, x: int, y: int) -> None:
        """點擊螢幕座標"""
        if self._emulator_bridge and self._cap_method == ScreenCapMethod.EMULATOR:
            self._emulator_bridge.tap(x, y)
        else:
            self._safe_shell(f"input tap {x} {y}")
        logger.debug(f"👆 點擊 ({x}, {y})")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500) -> None:
        """滑動"""
        if self._emulator_bridge and self._cap_method == ScreenCapMethod.EMULATOR:
            self._emulator_bridge.swipe(x1, y1, x2, y2, duration_ms)
        else:
            self._safe_shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        logger.debug(f"👉 滑動 ({x1},{y1}) → ({x2},{y2}) {duration_ms}ms")

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """長按"""
        self._safe_shell(f"input swipe {x} {y} {x} {y} {duration_ms}")
        logger.debug(f"👇 長按 ({x}, {y}) {duration_ms}ms")

    def input_text(self, text: str) -> None:
        """輸入文字（英數限定，中文需其他方式）"""
        self._safe_shell(f"input text '{text}'")
        logger.debug(f"⌨️ 輸入: {text}")

    def key_event(self, keycode: int | str) -> None:
        """發送按鍵事件 (例如 KEYCODE_BACK=4, KEYCODE_HOME=3)"""
        self._safe_shell(f"input keyevent {keycode}")
        logger.debug(f"🔘 按鍵: {keycode}")

    def back(self) -> None:
        self.key_event(4)

    def home(self) -> None:
        self.key_event(3)

    # ── App 控制 ──────────────────────────────────────────

    def launch_app(self, package: str, activity: str | None = None) -> None:
        """啟動 App"""
        if activity:
            self.device.shell(f"am start -n {package}/{activity}")
        else:
            self.device.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
        logger.info(f"🚀 啟動 App: {package}")

    def kill_app(self, package: str) -> None:
        """強制關閉 App"""
        self.device.shell(f"am force-stop {package}")
        logger.info(f"💀 關閉 App: {package}")

    def current_app(self) -> str:
        """取得目前前景 App package name"""
        output = self.device.shell("dumpsys activity activities | grep mResumedActivity")
        return output.strip()

    # ── 生命週期 ──────────────────────────────────────────

    def cleanup(self) -> None:
        """清理資源"""
        if self._minicap_stream:
            self._minicap_stream.stop()
            self._minicap_stream = None
        if self._emulator_bridge:
            self._emulator_bridge.disconnect()
            self._emulator_bridge = None

    def __del__(self):
        self.cleanup()
