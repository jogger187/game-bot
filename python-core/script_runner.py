"""
腳本執行器 — 讀取視覺化腳本 JSON，遍歷節點圖並執行動作
支援的節點類型：start, end, find_image, wait_image, click, swipe,
wait, type_text, key_press, condition, loop, set_variable,
log, random_delay, ocr, pixel_check
"""
import asyncio
import json
import subprocess
import time
import random
import base64
import io
from pathlib import Path
from datetime import datetime

# 嘗試載入 OpenCV
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"


class ScriptRunner:
    """執行視覺化腳本的引擎"""

    def __init__(self, serial: str, on_log=None):
        self.serial = serial
        self.on_log = on_log or print
        self.variables = {}  # 腳本變數
        self.running = False
        self.paused = False
        self.run_count = 0
        self._last_match_pos = None  # 最後一次找圖的匹配位置

    def log(self, msg: str):
        """記錄日誌"""
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.on_log(entry)

    # ═══════════════════════════════════════════
    #  ADB 工具
    # ═══════════════════════════════════════════
    def adb(self, *args) -> str:
        """執行 ADB 命令"""
        cmd = ["adb", "-s", self.serial] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return result.stdout.strip()
        except Exception:
            return ""

    def adb_raw(self, *args) -> bytes:
        """執行 ADB 命令（返回原始 bytes）"""
        cmd = ["adb", "-s", self.serial] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            return result.stdout
        except Exception:
            return b""

    def tap(self, x: int, y: int, hold_ms: int = 0):
        """點擊座標"""
        if hold_ms > 0:
            self.adb("shell", "input", "swipe", str(x), str(y), str(x), str(y), str(hold_ms))
        else:
            self.adb("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300):
        """滑動"""
        self.adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration))

    def type_text(self, text: str):
        """輸入文字"""
        self.adb("shell", "input", "text", text.replace(" ", "%s"))

    def key_event(self, keycode: str):
        """按鍵事件"""
        key_map = {
            "back": "4", "home": "3", "recent": "187",
            "enter": "66", "power": "26", "volume_up": "24", "volume_down": "25",
        }
        code = key_map.get(keycode, keycode)
        self.adb("shell", "input", "keyevent", code)

    def screenshot_cv(self):
        """擷取截圖並轉為 OpenCV 格式"""
        if not HAS_CV2:
            return None
        png_data = self.adb_raw("exec-out", "screencap", "-p")
        if not png_data:
            return None
        arr = np.frombuffer(png_data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    # ═══════════════════════════════════════════
    #  模板匹配
    # ═══════════════════════════════════════════
    def find_template(self, template_name: str, threshold: float = 0.8,
                      region: dict = None, timeout: float = 5) -> dict:
        """
        在螢幕上搜尋模板圖片
        返回 { found, x, y, confidence } 或 { found: False }
        """
        if not HAS_CV2:
            self.log("❌ 缺少 OpenCV，無法執行找圖")
            return {"found": False}

        template_path = ASSETS_DIR / template_name
        if not template_path.exists():
            self.log(f"❌ 模板圖片不存在: {template_name}")
            return {"found": False}

        template = cv2.imread(str(template_path))
        if template is None:
            self.log(f"❌ 無法讀取模板: {template_name}")
            return {"found": False}

        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.running:
                return {"found": False}

            screen = self.screenshot_cv()
            if screen is None:
                time.sleep(0.5)
                continue

            # 區域裁切
            search_area = screen
            offset_x, offset_y = 0, 0
            if region and region.get("w", 0) > 0 and region.get("h", 0) > 0:
                rx, ry = region["x"], region["y"]
                rw, rh = region["w"], region["h"]
                search_area = screen[ry:ry+rh, rx:rx+rw]
                offset_x, offset_y = rx, ry

            # 模板匹配
            result = cv2.matchTemplate(search_area, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                th, tw = template.shape[:2]
                cx = max_loc[0] + tw // 2 + offset_x
                cy = max_loc[1] + th // 2 + offset_y
                return {"found": True, "x": cx, "y": cy, "confidence": round(max_val, 3)}

            time.sleep(0.5)

        return {"found": False}

    # ═══════════════════════════════════════════
    #  節點執行器
    # ═══════════════════════════════════════════
    def execute_node(self, node: dict) -> str:
        """
        執行單一節點，返回下一個輸出端口
        'default' = 正常輸出, 'true'/'false' = 條件分支
        """
        node_type = node.get("type", "")
        data = node.get("data", {})
        node_id = node.get("id", "")

        if node_type == "start":
            self.log("▶️ 腳本開始執行")
            return "default"

        elif node_type == "end":
            self.log("⏹️ 腳本執行結束")
            return "end"

        elif node_type == "find_image":
            template = data.get("template", "")
            threshold = data.get("threshold", 0.8)
            timeout = data.get("timeout", 5)
            region = data.get("region") if data.get("region_enabled") else None
            variable = data.get("variable", "match_result")

            self.log(f"🔍 找圖: {template} (信心度≥{threshold}, 超時{timeout}s)")
            result = self.find_template(template, threshold, region, timeout)

            self.variables[variable] = result
            if result["found"]:
                self._last_match_pos = (result["x"], result["y"])
                self.log(f"  ✅ 找到! ({result['x']}, {result['y']}) 信心度={result['confidence']}")
                return "true"
            else:
                self._last_match_pos = None
                self.log(f"  ❌ 未找到 {template}")
                return "false"

        elif node_type == "wait_image":
            template = data.get("template", "")
            threshold = data.get("threshold", 0.8)
            timeout = data.get("timeout", 30)
            interval = data.get("check_interval", 1)

            self.log(f"⏳ 等待圖片: {template} (超時{timeout}s)")
            start = time.time()
            while time.time() - start < timeout and self.running:
                result = self.find_template(template, threshold, timeout=2)
                if result["found"]:
                    self._last_match_pos = (result["x"], result["y"])
                    self.log(f"  ✅ 圖片出現! ({result['x']}, {result['y']})")
                    return "true"
                time.sleep(interval)

            self.log(f"  ⏰ 等待超時")
            return "false"

        elif node_type == "click":
            mode = data.get("mode", "coordinate")
            rand_range = data.get("random_range", 3)
            hold_ms = data.get("hold_ms", 0)
            repeat = data.get("repeat", 1)
            repeat_interval = data.get("repeat_interval", 100)

            if mode == "match_center" and self._last_match_pos:
                x, y = self._last_match_pos
            elif mode == "coordinate":
                x = data.get("x", 0)
                y = data.get("y", 0)
            else:
                # match_center 但沒有上次匹配結果
                if self._last_match_pos:
                    x, y = self._last_match_pos
                else:
                    self.log(f"  ⚠️ 點擊模式為 match_center 但無匹配結果，跳過")
                    return "default"

            # 隨機偏移（防檢測）
            dx = random.randint(-rand_range, rand_range)
            dy = random.randint(-rand_range, rand_range)

            for i in range(repeat):
                tx, ty = x + dx, y + dy
                self.log(f"👆 點擊 ({tx}, {ty}){f' 長按{hold_ms}ms' if hold_ms > 0 else ''}")
                self.tap(tx, ty, hold_ms)
                if i < repeat - 1:
                    time.sleep(repeat_interval / 1000.0)

            return "default"

        elif node_type == "swipe":
            x1, y1 = data.get("x1", 0), data.get("y1", 0)
            x2, y2 = data.get("x2", 0), data.get("y2", 0)
            duration = data.get("duration", 300)
            self.log(f"👉 滑動 ({x1},{y1}) → ({x2},{y2}) {duration}ms")
            self.swipe(x1, y1, x2, y2, duration)
            return "default"

        elif node_type == "wait":
            ms = data.get("ms", 1000)
            self.log(f"⏱️ 等待 {ms}ms")
            time.sleep(ms / 1000.0)
            return "default"

        elif node_type == "type_text":
            text = data.get("text", "")
            self.log(f"⌨️ 輸入文字: {text}")
            self.type_text(text)
            return "default"

        elif node_type == "key_press":
            key = data.get("key", "back")
            self.log(f"🔘 按鍵: {key}")
            self.key_event(key)
            return "default"

        elif node_type == "condition":
            cond_type = data.get("condition_type", "find_image")
            # 簡化處理：根據條件類型判斷
            if cond_type == "find_image":
                template = data.get("template", "")
                threshold = data.get("threshold", 0.8)
                result = self.find_template(template, threshold, timeout=3)
                if result["found"]:
                    self._last_match_pos = (result["x"], result["y"])
                passed = result["found"]
            elif cond_type == "variable_check":
                var_name = data.get("variable", "")
                expected = data.get("expected_value", "")
                actual = str(self.variables.get(var_name, ""))
                passed = actual == expected
            else:
                passed = False

            self.log(f"❓ 條件判斷 ({cond_type}): {'True' if passed else 'False'}")
            return "true" if passed else "false"

        elif node_type == "loop":
            # 迴圈由 graph traversal 處理
            return "default"

        elif node_type == "set_variable":
            var_name = data.get("name", "var")
            var_value = data.get("value", "")
            self.variables[var_name] = var_value
            self.log(f"📦 設定變數: {var_name} = {var_value}")
            return "default"

        elif node_type == "log":
            message = data.get("message", "")
            level = data.get("level", "info")
            # 變數替換
            for k, v in self.variables.items():
                message = message.replace(f"{{{k}}}", str(v))
            self.log(f"📋 [{level}] {message}")
            return "default"

        elif node_type == "random_delay":
            min_ms = data.get("min_ms", 500)
            max_ms = data.get("max_ms", 2000)
            delay = random.randint(min_ms, max_ms)
            self.log(f"🎲 隨機延遲: {delay}ms")
            time.sleep(delay / 1000.0)
            return "default"

        elif node_type == "ocr":
            self.log("🔤 OCR 辨識（尚未完整實作）")
            return "default"

        elif node_type == "pixel_check":
            self.log("🎨 像素檢查（尚未完整實作）")
            return "default"

        else:
            self.log(f"⚠️ 未知節點類型: {node_type}，跳過")
            return "default"

    # ═══════════════════════════════════════════
    #  圖遍歷執行
    # ═══════════════════════════════════════════
    def build_graph(self, script: dict) -> dict:
        """建立節點圖的鄰接表"""
        nodes = {n["id"]: n for n in script.get("nodes", [])}
        # 邊：source → [(target, sourceHandle)]
        adjacency = {}
        for edge in script.get("edges", []):
            src = edge["source"]
            tgt = edge["target"]
            handle = edge.get("sourceHandle", "default")
            if src not in adjacency:
                adjacency[src] = []
            adjacency[src].append({"target": tgt, "handle": handle})
        return nodes, adjacency

    def get_next_node(self, adjacency: dict, current_id: str, output_port: str) -> str:
        """根據當前節點和輸出端口，找到下一個節點"""
        edges = adjacency.get(current_id, [])

        if not edges:
            return None

        # 如果只有一條邊，直接跟隨
        if len(edges) == 1:
            return edges[0]["target"]

        # 多條邊：根據 handle 匹配
        for edge in edges:
            handle = edge.get("handle", "default")
            if handle == output_port:
                return edge["target"]
            # handle 可能是 "source-true", "source-false" 等格式
            if output_port in handle:
                return edge["target"]

        # 如果找不到匹配的，取第一條
        return edges[0]["target"] if edges else None

    def run_script(self, script: dict):
        """執行完整腳本（單次）"""
        nodes, adjacency = self.build_graph(script)

        # 找 start 節點
        start_node = None
        for nid, node in nodes.items():
            if node.get("type") == "start":
                start_node = nid
                break

        if not start_node:
            self.log("❌ 找不到 Start 節點")
            return

        # 從 start 開始遍歷
        current_id = start_node
        max_steps = 500  # 安全上限防止無限迴圈
        step = 0

        while current_id and self.running and step < max_steps:
            step += 1
            node = nodes.get(current_id)
            if not node:
                self.log(f"❌ 節點不存在: {current_id}")
                break

            # 暫停處理
            while self.paused and self.running:
                time.sleep(0.5)

            # 執行節點
            output_port = self.execute_node(node)

            if output_port == "end":
                break

            # 找下一個節點
            current_id = self.get_next_node(adjacency, current_id, output_port)

        if step >= max_steps:
            self.log("⚠️ 達到最大步數限制 (500)，停止執行")

    def run(self, script: dict):
        """執行腳本（包含迴圈設定）"""
        self.running = True
        self.run_count = 0
        settings = script.get("settings", {})
        loop_enabled = settings.get("loop_enabled", False)
        max_runs = settings.get("max_runs", 0)
        interval = settings.get("interval", 3)

        self.log(f"🎮 開始執行腳本: {script.get('name', '未命名')}")
        self.log(f"   迴圈: {'是' if loop_enabled else '否'}, 最大次數: {max_runs or '無限'}, 間隔: {interval}s")

        try:
            while self.running:
                self.run_count += 1
                self.log(f"\n{'='*40}")
                self.log(f"🔄 第 {self.run_count} 次執行")
                self.log(f"{'='*40}")

                self.run_script(script)

                if not loop_enabled:
                    break

                if max_runs > 0 and self.run_count >= max_runs:
                    self.log(f"✅ 已達最大執行次數 ({max_runs})")
                    break

                if self.running:
                    self.log(f"⏳ 等待 {interval}s 後開始下一輪...")
                    time.sleep(interval)
        except Exception as e:
            self.log(f"❌ 執行錯誤: {e}")
        finally:
            self.running = False
            self.log(f"🏁 腳本執行完畢，共執行 {self.run_count} 次")

    def stop(self):
        """停止執行"""
        self.running = False
        self.log("🛑 停止腳本")

    def toggle_pause(self):
        """暫停/繼續"""
        self.paused = not self.paused
        self.log(f"{'⏸️ 暫停' if self.paused else '▶️ 繼續'}執行")
