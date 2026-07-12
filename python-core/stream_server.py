"""
即時畫面串流 + 操作錄製 — WebSocket 伺服器模組

使用 adbutils 高頻截圖實現串流（相容 Python 3.9+，零額外依賴）。
經過最佳化：僅在畫面變化時才進行 JPEG 編碼。

WebSocket 協議：
- 前端 → 後端 (JSON):
    {"type": "start_stream"}
    {"type": "stop_stream"}
    {"type": "tap", "x": 500, "y": 1000}
    {"type": "swipe", "from_x": 500, "from_y": 1000, "to_x": 500, "to_y": 300, "duration": 300}
    {"type": "start_recording"}
    {"type": "stop_recording"}
    {"type": "save_recording", "script_id": "xxx", "name": "我的錄製"}
- 後端 → 前端:
    Binary: JPEG frame bytes
    JSON: {"type": "stream_started", "width": W, "height": H}
    JSON: {"type": "stream_stopped"}
    JSON: {"type": "recording_status", "recording": true/false, "action_count": N}
    JSON: {"type": "recording_saved", "recording_id": "xxx"}
    JSON: {"type": "error", "message": "..."}
"""
from __future__ import annotations

import asyncio
import io
import json
import subprocess
import time
import threading
from typing import Optional

import adbutils
from aiohttp import web

# 嘗試載入 OpenCV (用於 JPEG 編碼)
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# 嘗試載入 PIL（fallback 方案）
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class StreamSession:
    """管理單一 WebSocket 連線的串流會話（使用 adb screencap）"""

    def __init__(self, serial: str, db_conn, on_log=None):
        self.serial = serial
        self.db_conn = db_conn
        self.on_log = on_log or print
        self.streaming = False
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._last_encoded_raw = None
        self._resolution: tuple[int, int] = (0, 0)

        # 錄製狀態
        self.recording = False
        self.recorded_actions: list[dict] = []
        self.recording_start_time: float = 0.0

        # 串流設定
        self.jpeg_quality = 65
        self.target_fps = 10  # adb screencap 極限約 5~15 FPS
        self._frame_interval = 1.0 / self.target_fps

        # 持久化 adb shell（快速點擊用）
        self._shell_proc: Optional[subprocess.Popen] = None

    def log(self, msg: str):
        try:
            self.on_log(msg)
        except TypeError:
            pass

    def _adb_path(self) -> str:
        return adbutils.adb_path()

    def _screencap_jpeg(self) -> Optional[bytes]:
        """高效截圖：adb exec-out screencap → PNG → JPEG 壓縮"""
        try:
            cmd = [self._adb_path(), "-s", self.serial, "exec-out", "screencap", "-p"]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            png_data = result.stdout
            if not png_data or len(png_data) < 100:
                return None

            # 避免對完全相同的畫面重複耗時編碼
            if self._last_encoded_raw == png_data:
                return self._latest_jpeg
            
            self._last_encoded_raw = png_data

            if HAS_CV2:
                # OpenCV 路線：最快
                arr = np.frombuffer(png_data, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    return None
                h, w = img.shape[:2]
                # 降低解析度加速傳輸
                if w > 720:
                    scale = 720 / w
                    img = cv2.resize(img, (720, int(h * scale)), interpolation=cv2.INTER_AREA)
                _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
                self._resolution = (w, h)
                return buf.tobytes()
            elif HAS_PIL:
                # PIL 路線：fallback
                pil_img = Image.open(io.BytesIO(png_data))
                w, h = pil_img.size
                if w > 720:
                    scale = 720 / w
                    pil_img = pil_img.resize((720, int(h * scale)), Image.LANCZOS)
                buf = io.BytesIO()
                pil_img.save(buf, format='JPEG', quality=self.jpeg_quality)
                self._resolution = (w, h)
                return buf.getvalue()
            else:
                # 直接回傳 PNG（不壓縮）
                self._resolution = (0, 0)
                return png_data

        except (subprocess.TimeoutExpired, Exception):
            return None

    def _capture_loop(self):
        """在背景執行緒持續截圖"""
        while not self._stop_event.is_set():
            jpeg_data = self._screencap_jpeg()
            if jpeg_data:
                with self._frame_lock:
                    self._latest_jpeg = jpeg_data
            self._stop_event.wait(self._frame_interval)

    def start_stream(self) -> tuple[int, int]:
        """啟動截圖串流，返回 (width, height)"""
        self.log(f"📡 正在啟動 adb 截圖串流... (serial={self.serial})")
        self._stop_event.clear()
        self.streaming = True

        # 先截一張圖獲取解析度
        jpeg = self._screencap_jpeg()
        if not jpeg:
            raise RuntimeError("截圖失敗：無法從裝置擷取畫面")

        with self._frame_lock:
            self._latest_jpeg = jpeg

        # 啟動背景截圖執行緒
        t = threading.Thread(target=self._capture_loop, daemon=True)
        t.start()

        w, h = self._resolution
        self.log(f"📡 串流已啟動: {w}x{h} (~{self.target_fps} FPS)")
        return w, h

    def stop_stream(self):
        """停止串流"""
        self._stop_event.set()
        self.streaming = False
        self._latest_jpeg = None
        self._cleanup_shell()
        self.log("📡 串流已停止")

    def get_jpeg_frame(self) -> Optional[bytes]:
        """取得最新的 JPEG 畫面"""
        with self._frame_lock:
            return self._latest_jpeg

    # ═══════════════════════════════════════════
    #  裝置操作注入
    # ═══════════════════════════════════════════
    def _ensure_shell(self):
        """確保持久化 adb shell 存在"""
        if self._shell_proc and self._shell_proc.poll() is None:
            return True
        try:
            self._shell_proc = subprocess.Popen(
                [self._adb_path(), "-s", self.serial, "shell"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            self._shell_proc = None
            return False

    def _shell_write(self, cmd: str):
        """向持久化 shell 寫入指令"""
        if self._shell_proc and self._shell_proc.poll() is None:
            try:
                self._shell_proc.stdin.write((cmd + "\n").encode())
                self._shell_proc.stdin.flush()
            except Exception:
                self._shell_proc = None

    def _cleanup_shell(self):
        """清理持久化 shell"""
        if self._shell_proc:
            try:
                self._shell_proc.terminate()
            except Exception:
                pass
            self._shell_proc = None

    def inject_tap(self, x: int, y: int):
        """注入點擊事件"""
        if self._ensure_shell():
            self._shell_write(f"input tap {x} {y}")
        else:
            subprocess.run(
                [self._adb_path(), "-s", self.serial, "shell", "input", "tap", str(x), str(y)],
                timeout=5, capture_output=True,
            )

        if self.recording:
            elapsed = round(time.time() - self.recording_start_time, 3)
            self.recorded_actions.append({
                "time": elapsed,
                "action": "tap",
                "x": x,
                "y": y,
            })

    def inject_swipe(self, from_x: int, from_y: int, to_x: int, to_y: int, duration: int = 300):
        """注入滑動事件"""
        if self._ensure_shell():
            self._shell_write(f"input swipe {from_x} {from_y} {to_x} {to_y} {duration}")
        else:
            subprocess.run(
                [self._adb_path(), "-s", self.serial, "shell", "input", "swipe",
                 str(from_x), str(from_y), str(to_x), str(to_y), str(duration)],
                timeout=5, capture_output=True,
            )

        if self.recording:
            elapsed = round(time.time() - self.recording_start_time, 3)
            self.recorded_actions.append({
                "time": elapsed,
                "action": "swipe",
                "from_x": from_x,
                "from_y": from_y,
                "to_x": to_x,
                "to_y": to_y,
                "duration": duration,
            })

    # ═══════════════════════════════════════════
    #  錄製控制
    # ═══════════════════════════════════════════
    def start_recording(self):
        """開始錄製"""
        self.recording = True
        self.recorded_actions = []
        self.recording_start_time = time.time()
        self.log("⏺️ 開始錄製操作")

    def stop_recording(self) -> list[dict]:
        """停止錄製，返回操作清單"""
        self.recording = False
        actions = self.recorded_actions.copy()
        self.log(f"⏹️ 停止錄製，共 {len(actions)} 個操作")
        return actions

    def save_recording(self, name: str, script_id: Optional[str] = None) -> dict:
        """將錄製結果儲存到資料庫"""
        import database as db
        actions = self.recorded_actions
        duration_ms = int((actions[-1]["time"] * 1000) if actions else 0)
        recording = db.recording_create(
            self.db_conn, name=name, actions=actions,
            duration_ms=duration_ms, script_id=script_id,
        )
        self.log(f"💾 錄製已儲存: {name} ({len(actions)} 個操作)")
        return recording


# ═══════════════════════════════════════════
#  WebSocket Handler
# ═══════════════════════════════════════════

# 全域活躍的串流會話（一次只允許一個）
_active_session: Optional[StreamSession] = None
_session_lock = threading.Lock()


async def ws_stream_handler(request: web.Request) -> web.WebSocketResponse:
    """處理 WebSocket 串流連線"""
    global _active_session

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # 從 app 取得共用資源
    db_conn = request.app.get("db_conn")
    device_state = request.app.get("device_state", {})
    add_log_fn = request.app.get("add_log", print)

    def add_log(msg, source="stream"):
        try:
            add_log_fn(msg, source=source)
        except TypeError:
            add_log_fn(msg)

    serial = device_state.get("serial", "")
    if not serial or not device_state.get("connected"):
        await ws.send_json({"type": "error", "message": "裝置未連線"})
        await ws.close()
        return ws

    add_log(f"📡 WebSocket 串流連線建立 (serial={serial})")

    session: Optional[StreamSession] = None
    frame_push_task: Optional[asyncio.Task] = None

    async def push_frames():
        """持續推送 JPEG 畫面到前端"""
        loop = asyncio.get_event_loop()
        last_sent = None
        while session and session.streaming and not ws.closed:
            try:
                jpeg_data = await loop.run_in_executor(None, session.get_jpeg_frame)
                if jpeg_data and jpeg_data != last_sent and not ws.closed:
                    await ws.send_bytes(jpeg_data)
                    last_sent = jpeg_data
            except (ConnectionResetError, asyncio.CancelledError):
                break
            except Exception:
                pass
            await asyncio.sleep(0.01)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                if msg_type == "start_stream":
                    # 停止舊的全域會話
                    with _session_lock:
                        if _active_session:
                            _active_session.stop_stream()
                        session = StreamSession(serial, db_conn, on_log=lambda m: add_log(m))
                        _active_session = session

                    try:
                        loop = asyncio.get_event_loop()
                        w, h = await loop.run_in_executor(None, session.start_stream)
                        await ws.send_json({"type": "stream_started", "width": w, "height": h})
                        # 啟動畫面推送任務
                        frame_push_task = asyncio.create_task(push_frames())
                    except RuntimeError as e:
                        await ws.send_json({"type": "error", "message": str(e)})
                        session = None

                elif msg_type == "stop_stream":
                    if frame_push_task:
                        frame_push_task.cancel()
                        frame_push_task = None
                    if session:
                        await asyncio.get_event_loop().run_in_executor(None, session.stop_stream)
                        with _session_lock:
                            if _active_session is session:
                                _active_session = None
                        session = None
                    await ws.send_json({"type": "stream_stopped"})

                elif msg_type == "tap":
                    if session:
                        x, y = int(data.get("x", 0)), int(data.get("y", 0))
                        await asyncio.get_event_loop().run_in_executor(None, session.inject_tap, x, y)
                        if session.recording:
                            await ws.send_json({
                                "type": "recording_status",
                                "recording": True,
                                "action_count": len(session.recorded_actions),
                            })

                elif msg_type == "swipe":
                    if session:
                        fx = int(data.get("from_x", 0))
                        fy = int(data.get("from_y", 0))
                        tx = int(data.get("to_x", 0))
                        ty = int(data.get("to_y", 0))
                        dur = int(data.get("duration", 300))
                        await asyncio.get_event_loop().run_in_executor(
                            None, session.inject_swipe, fx, fy, tx, ty, dur
                        )
                        if session.recording:
                            await ws.send_json({
                                "type": "recording_status",
                                "recording": True,
                                "action_count": len(session.recorded_actions),
                            })

                elif msg_type == "start_recording":
                    if session:
                        session.start_recording()
                        await ws.send_json({
                            "type": "recording_status",
                            "recording": True,
                            "action_count": 0,
                        })

                elif msg_type == "stop_recording":
                    if session:
                        actions = session.stop_recording()
                        await ws.send_json({
                            "type": "recording_status",
                            "recording": False,
                            "action_count": len(actions),
                            "actions": actions,
                        })

                elif msg_type == "save_recording":
                    if session:
                        name = data.get("name", "未命名錄製")
                        script_id = data.get("script_id")
                        try:
                            recording = await asyncio.get_event_loop().run_in_executor(
                                None, session.save_recording, name, script_id
                            )
                            await ws.send_json({
                                "type": "recording_saved",
                                "recording_id": recording["id"],
                                "actions": recording["actions"],
                            })
                        except Exception as e:
                            await ws.send_json({"type": "error", "message": f"儲存失敗: {e}"})

            elif msg.type in (web.WSMsgType.ERROR, web.WSMsgType.CLOSE):
                break

    except asyncio.CancelledError:
        pass
    finally:
        # 清理資源
        if frame_push_task:
            frame_push_task.cancel()
        if session:
            session.stop_stream()
            with _session_lock:
                if _active_session is session:
                    _active_session = None
        add_log("📡 WebSocket 串流連線已斷開")

    return ws
