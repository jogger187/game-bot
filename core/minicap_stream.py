"""MiniCap 高速截圖串流 — 透過 socket 持續接收螢幕畫面

MiniCap 是 Android 上的原生截圖工具，延遲約 30-50ms，
遠優於 adb screencap 的 300-500ms。

使用方式:
    stream = MiniCapStream(device_serial="emulator-5554")
    stream.start()
    frame = stream.latest_frame  # PIL Image
    stream.stop()
"""

from __future__ import annotations

import io
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from loguru import logger
from PIL import Image


@dataclass
class MiniCapBanner:
    """MiniCap socket 連線後的 banner 資訊"""

    version: int
    length: int
    pid: int
    real_width: int
    real_height: int
    virtual_width: int
    virtual_height: int
    orientation: int
    quirks: int


class MiniCapStream:
    """
    MiniCap 串流客戶端

    自動處理:
    1. push minicap binary + .so 到裝置
    2. 啟動 minicap server
    3. 透過 adb forward + socket 接收 JPEG frames
    """

    MINICAP_DIR = Path(__file__).parent.parent / "vendor" / "minicap"

    def __init__(
        self,
        device_serial: str | None = None,
        quality: int = 80,
        max_fps: int = 10,
        local_port: int = 1717,
    ):
        self._serial = device_serial
        self._quality = quality
        self._max_fps = max_fps
        self._local_port = local_port

        self._process: subprocess.Popen | None = None
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

        self._latest_frame: Image.Image | None = None
        self._frame_count = 0
        self._banner: MiniCapBanner | None = None

    @property
    def latest_frame(self) -> Image.Image | None:
        """取得最新一幀畫面"""
        with self._lock:
            return self._latest_frame

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def is_running(self) -> bool:
        return self._running

    # ── ADB 輔助 ──────────────────────────────────────────

    def _adb_cmd(self, *args: str) -> str:
        cmd = ["adb"]
        if self._serial:
            cmd += ["-s", self._serial]
        cmd += list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()

    def _adb_shell(self, command: str) -> str:
        return self._adb_cmd("shell", command)

    def _get_device_abi(self) -> str:
        return self._adb_shell("getprop ro.product.cpu.abi")

    def _get_sdk_version(self) -> int:
        return int(self._adb_shell("getprop ro.build.version.sdk"))

    def _get_screen_info(self) -> tuple[int, int, int]:
        """回傳 (width, height, rotation)"""
        size_str = self._adb_shell("wm size")
        size_part = size_str.split(":")[-1].strip()
        w, h = size_part.split("x")

        rotation_str = self._adb_shell(
            "dumpsys input | grep SurfaceOrientation | head -1"
        )
        rotation = 0
        if "SurfaceOrientation" in rotation_str:
            try:
                rotation = int(rotation_str.strip()[-1])
            except (ValueError, IndexError):
                rotation = 0

        return int(w), int(h), rotation

    # ── MiniCap 安裝 ──────────────────────────────────────

    def _check_minicap_installed(self) -> bool:
        result = self._adb_shell("ls /data/local/tmp/minicap 2>/dev/null")
        return "minicap" in result and "No such file" not in result

    def _install_minicap(self) -> None:
        """推送 minicap binary 和 .so 到裝置"""
        abi = self._get_device_abi()
        sdk = self._get_sdk_version()

        bin_path = self.MINICAP_DIR / "bin" / abi / "minicap"
        so_path = self.MINICAP_DIR / "shared" / f"android-{sdk}" / abi / "minicap.so"

        if not bin_path.exists():
            raise FileNotFoundError(
                f"MiniCap binary 不存在: {bin_path}\n"
                f"請從 https://github.com/DeviceFarmer/minicap 下載並放到 vendor/minicap/"
            )
        if not so_path.exists():
            raise FileNotFoundError(
                f"MiniCap .so 不存在: {so_path}\n"
                f"裝置 ABI={abi}, SDK={sdk}"
            )

        self._adb_cmd("push", str(bin_path), "/data/local/tmp/minicap")
        self._adb_cmd("push", str(so_path), "/data/local/tmp/minicap.so")
        self._adb_shell("chmod 755 /data/local/tmp/minicap")
        logger.info(f"📦 MiniCap 已安裝 (abi={abi}, sdk={sdk})")

    # ── 啟動/停止 ─────────────────────────────────────────

    def start(self) -> None:
        """啟動 MiniCap 串流"""
        if self._running:
            logger.warning("MiniCap 已在運行")
            return

        # 確保 minicap 已安裝
        if not self._check_minicap_installed():
            self._install_minicap()

        w, h, rotation = self._get_screen_info()
        display = f"{w}x{h}@{w}x{h}/{rotation * 90}"

        # 啟動 minicap server
        cmd = ["adb"]
        if self._serial:
            cmd += ["-s", self._serial]
        cmd += [
            "shell",
            f"LD_LIBRARY_PATH=/data/local/tmp "
            f"/data/local/tmp/minicap "
            f"-P {display} "
            f"-Q {self._quality} "
            f"-r {self._max_fps}",
        ]

        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        time.sleep(1)  # 等待 minicap 啟動

        # 建立 adb forward
        self._adb_cmd(
            "forward", f"tcp:{self._local_port}", "localabstract:minicap"
        )

        # 連線 socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect(("127.0.0.1", self._local_port))

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

        logger.info(
            f"🎬 MiniCap 串流啟動 ({w}x{h}, Q={self._quality}, FPS={self._max_fps})"
        )

    def stop(self) -> None:
        """停止 MiniCap 串流"""
        self._running = False

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
            self._process = None

        # 移除 adb forward
        try:
            self._adb_cmd("forward", "--remove", f"tcp:{self._local_port}")
        except Exception:
            pass

        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

        logger.info(f"⏹️ MiniCap 串流已停止 (共 {self._frame_count} 幀)")

    # ── 接收迴圈 ──────────────────────────────────────────

    def _recv_exact(self, n: int) -> bytes:
        """確保接收到 n 個 byte"""
        buf = b""
        while len(buf) < n:
            chunk = self._socket.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("MiniCap 連線中斷")
            buf += chunk
        return buf

    def _read_banner(self) -> MiniCapBanner:
        """讀取 MiniCap banner (24 bytes)"""
        data = self._recv_exact(24)
        banner = MiniCapBanner(
            version=data[0],
            length=data[1],
            pid=struct.unpack("<I", data[2:6])[0],
            real_width=struct.unpack("<I", data[6:10])[0],
            real_height=struct.unpack("<I", data[10:14])[0],
            virtual_width=struct.unpack("<I", data[14:18])[0],
            virtual_height=struct.unpack("<I", data[18:22])[0],
            orientation=data[22],
            quirks=data[23],
        )
        logger.debug(
            f"📋 MiniCap Banner: {banner.real_width}x{banner.real_height} "
            f"orientation={banner.orientation}"
        )
        return banner

    def _read_loop(self) -> None:
        """持續接收 JPEG frames"""
        try:
            self._banner = self._read_banner()

            while self._running:
                # 讀取 frame 長度 (4 bytes, little-endian)
                length_data = self._recv_exact(4)
                frame_length = struct.unpack("<I", length_data)[0]

                if frame_length == 0:
                    continue

                # 讀取 JPEG data
                jpeg_data = self._recv_exact(frame_length)

                # 解碼為 PIL Image
                try:
                    img = Image.open(io.BytesIO(jpeg_data))
                    with self._lock:
                        self._latest_frame = img.copy()
                    self._frame_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ JPEG 解碼失敗: {e}")

        except ConnectionError:
            if self._running:
                logger.error("❌ MiniCap 連線中斷")
        except Exception as e:
            if self._running:
                logger.error(f"❌ MiniCap 讀取錯誤: {e}")
        finally:
            self._running = False

    # ── 便捷方法 ──────────────────────────────────────────

    def screenshot(self) -> Image.Image:
        """取得最新截圖，如果串流未啟動則自動啟動"""
        if not self._running:
            self.start()
            # 等待第一幀
            deadline = time.time() + 5
            while self._latest_frame is None and time.time() < deadline:
                time.sleep(0.05)

        frame = self.latest_frame
        if frame is None:
            raise RuntimeError("MiniCap 無法取得畫面")
        return frame

    def screenshot_np(self) -> np.ndarray:
        """取得最新截圖的 numpy array (BGR)"""
        img = self.screenshot()
        arr = np.array(img)
        if arr.ndim == 3 and arr.shape[2] >= 3:
            return arr[:, :, ::-1].copy()
        return arr

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __del__(self):
        if self._running:
            self.stop()
