"""JSON-RPC 2.0 引擎入口 — 透過 stdin/stdout 與 Tauri 後端通信"""

import json
import sys
import traceback
from pathlib import Path

# 確保可以引用 core 和 tasks
sys.path.insert(0, str(Path(__file__).parent))

from core import (
    AdbController, ScreenMatcher, InputSimulator,
    OcrReader, PixelAnalyzer, SceneDetector, AntiDetect, AntiDetectConfig,
)
from tasks import TaskScheduler
from tasks.dynamic_task import DynamicTask

import base64
import io


class GameEngine:
    """遊戲自動化引擎 — 包裝所有核心功能"""

    def __init__(self):
        self.adb = None
        self.matcher = None
        self.input_sim = None
        self.ocr = None
        self.scheduler = None
        self.connected = False

    def handle_request(self, method: str, params: dict) -> dict:
        """路由 JSON-RPC 方法到對應處理器"""
        handlers = {
            "device.connect": self._device_connect,
            "device.disconnect": self._device_disconnect,
            "device.status": self._device_status,
            "screenshot.capture": self._screenshot_capture,
            "screenshot.capture_highres": self._screenshot_highres,
            "match.template": self._match_template,
            "ocr.recognize": self._ocr_recognize,
            "input.tap": self._input_tap,
            "input.swipe": self._input_swipe,
            "task.start": self._task_start,
            "task.stop": self._task_stop,
            "task.status": self._task_status,
            "ping": self._ping,
        }

        handler = handlers.get(method)
        if not handler:
            raise ValueError(f"未知的方法: {method}")

        return handler(params)

    def _ping(self, _params):
        return {"status": "ok", "engine": "game-bot-python"}

    def _device_connect(self, params):
        serial = params.get("serial", "127.0.0.1:5555")
        mode = params.get("mode", "adb")

        self.adb = AdbController(serial=serial, cap_method=mode)
        self.adb.connect()

        self.matcher = ScreenMatcher(assets_dir="assets")
        self.input_sim = InputSimulator(adb=self.adb)
        self.ocr = OcrReader()
        self.connected = True

        return {"connected": True, "serial": serial}

    def _device_disconnect(self, _params):
        self.connected = False
        self.adb = None
        return {"connected": False}

    def _device_status(self, _params):
        return {"connected": self.connected}

    def _screenshot_capture(self, _params):
        if not self.adb:
            raise RuntimeError("裝置未連線")

        img = self.adb.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        b64 = base64.b64encode(buf.getvalue()).decode()

        return {"image_b64": b64, "width": img.width, "height": img.height}

    def _screenshot_highres(self, _params):
        if not self.adb:
            raise RuntimeError("裝置未連線")

        img = self.adb.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode()

        return {"image_b64": b64, "width": img.width, "height": img.height}

    def _match_template(self, params):
        if not self.adb or not self.matcher:
            raise RuntimeError("裝置未連線")

        target = params.get("target")
        threshold = params.get("threshold", 0.85)

        img = self.adb.screenshot()
        result = self.matcher.find(img, target, threshold=threshold)

        if result:
            return {
                "found": True,
                "x": result.center_x,
                "y": result.center_y,
                "confidence": result.confidence,
            }
        return {"found": False}

    def _ocr_recognize(self, params):
        if not self.adb or not self.ocr:
            raise RuntimeError("裝置未連線")

        img = self.adb.screenshot()
        x = params.get("x", 0)
        y = params.get("y", 0)
        w = params.get("w", 0)
        h = params.get("h", 0)

        results = self.ocr.read(img, x, y, w, h)
        return {"texts": [{"text": r.text, "confidence": r.confidence} for r in results]}

    def _input_tap(self, params):
        if not self.input_sim:
            raise RuntimeError("裝置未連線")

        x = params.get("x", 0)
        y = params.get("y", 0)
        self.input_sim.tap(x, y)
        return {"success": True}

    def _input_swipe(self, params):
        if not self.input_sim:
            raise RuntimeError("裝置未連線")

        x1 = params.get("x1", 0)
        y1 = params.get("y1", 0)
        x2 = params.get("x2", 0)
        y2 = params.get("y2", 0)
        duration = params.get("duration", 300)
        self.input_sim.swipe(x1, y1, x2, y2, duration)
        return {"success": True}

    def _task_start(self, params):
        # TODO: 實作完整任務啟動
        return {"status": "started", "script_id": params.get("script_id")}

    def _task_stop(self, params):
        # TODO: 實作任務停止
        return {"status": "stopped"}

    def _task_status(self, _params):
        # TODO: 回傳任務狀態
        return {"tasks": []}


def main():
    """主迴圈：從 stdin 讀取 JSON-RPC 請求，處理後寫入 stdout"""
    engine = GameEngine()

    # 通知 Tauri 引擎已就緒
    ready_msg = json.dumps({"jsonrpc": "2.0", "method": "engine.ready", "params": {}})
    sys.stdout.write(ready_msg + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            req_id = request.get("id", 0)
            method = request.get("method", "")
            params = request.get("params", {})

            result = engine.handle_request(method, params)

            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }

        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id", 0) if 'request' in dir() else 0,
                "error": {
                    "code": -32000,
                    "message": str(e),
                    "data": traceback.format_exc(),
                },
            }

        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
