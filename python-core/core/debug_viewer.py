"""除錯視覺化 — 本地 Web UI 監控 bot 狀態

提供:
- 即時截圖直播（WebSocket）
- 模板比對結果標註
- OCR 辨識結果覆蓋
- 任務/場景狀態面板
- 模板截圖工具

使用方式:
    viewer = DebugViewer(adb, matcher, stats)
    viewer.start(port=8765)  # 非阻塞
    # ... bot 運行中 ...
    viewer.stop()
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import threading
import time
from pathlib import Path

from loguru import logger

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


class CropRequest(BaseModel):
    name: str
    image_b64: str

class DebugViewer:
    """Web UI 除錯監控"""

    def __init__(
        self,
        adb=None,
        matcher=None,
        stats=None,
        fsm=None,
        scheduler=None,
        screenshot_interval: float = 1.0,
        annotate_matches: bool = True,
    ):
        self.adb = adb
        self.matcher = matcher
        self.stats = stats
        self.fsm = fsm
        self.scheduler = scheduler
        self._screenshot_interval = screenshot_interval
        self._annotate = annotate_matches
        self._running = False
        self._thread: threading.Thread | None = None
        self._clients: list = []
        self._latest_screenshot_b64: str = ""

    def start(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        """啟動 Web UI（非阻塞）"""
        if not HAS_FASTAPI:
            logger.warning("⚠️ FastAPI 未安裝，Web UI 不可用。執行: pip install 'game-bot[web]'")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_server, args=(host, port), daemon=True
        )
        self._thread.start()
        logger.info(f"🖥️ Web UI 控制台: http://127.0.0.1:{port}")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _run_server(self, host: str, port: int) -> None:
        """在背景 thread 運行 FastAPI"""
        app = self._create_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    def _create_app(self) -> FastAPI:
        app = FastAPI(title="Game-Bot Control Panel")

        # 確保 assets 資料夾存在並 mount 靜態資源
        assets_dir = Path("assets")
        assets_dir.mkdir(exist_ok=True)
        app.mount("/assets-img", StaticFiles(directory="assets"), name="assets")

        @app.get("/", response_class=HTMLResponse)
        async def index():
            template_path = Path("core/templates/index.html")
            if template_path.exists():
                return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>Error: templates/index.html 不存在</h1>")

        @app.get("/api/status")
        async def status():
            data = {
                "running": self._running,
                "time": time.time(),
            }
            if self.scheduler:
                data["tasks"] = self.scheduler.status()
            if self.stats:
                data["stats"] = self.stats.export()
            if self.fsm:
                data["fsm"] = self.fsm.state_info()
            return data

        @app.get("/api/assets")
        async def list_assets():
            """回傳全部的範本圖片名稱"""
            files = [f.name for f in assets_dir.glob("*.png")]
            return files

        @app.post("/api/assets/crop")
        async def save_crop(req: CropRequest):
            """儲存前端送來的 base64 裁切圖片"""
            try:
                # 拿掉 data:image/png;base64, 前綴
                b64_data = req.image_b64.split(",", 1)[-1]
                img_data = base64.b64decode(b64_data)
                
                filepath = assets_dir / req.name
                filepath.write_bytes(img_data)
                logger.success(f"💾 前端透過 UI 儲存了物件: {req.name}")
                return {"success": True, "file": req.name}
            except Exception as e:
                logger.error(f"❌ 儲存物件失敗: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        scripts_file = Path("scripts.json")

        def _load_scripts():
            if not scripts_file.exists():
                scripts_file.write_text("[]", encoding="utf-8")
            try:
                return json.loads(scripts_file.read_text(encoding="utf-8"))
            except:
                return []

        def _save_scripts(scripts):
            scripts_file.write_text(json.dumps(scripts, ensure_ascii=False, indent=2), encoding="utf-8")

        @app.get("/api/scripts")
        async def get_scripts():
            """取得所有保存的腳本"""
            return _load_scripts()
            
        from typing import List, Dict
        @app.post("/api/scripts")
        async def save_scripts(data: List[Dict]):
            """完整儲存覆寫腳本列表"""
            _save_scripts(data)
            return {"success": True}

        # --- Jobs Queue API ---
        
        @app.get("/api/jobs")
        async def get_jobs():
            """取得執行佇列狀態"""
            if not self.scheduler: return []
            return self.scheduler.status()

        from pydantic import BaseModel
        import uuid
        
        class JobAddRequest(BaseModel):
            script_id: str
            run_mode: str
            max_runs: int = 0

        @app.post("/api/jobs/add")
        async def add_job(req: JobAddRequest):
            """發派任務"""
            if not self.scheduler: return {"success": False}
            scripts = _load_scripts()
            script = next((s for s in scripts if s["id"] == req.script_id), None)
            if not script:
                return {"success": False, "error": "Script not found"}
                
            from tasks.dynamic_task import DynamicTask
            job_id = str(uuid.uuid4())
            self.scheduler.add_task(
                DynamicTask,
                interval=script.get("interval", 3.0),
                job_id=job_id,
                max_runs=req.max_runs if req.run_mode == "fixed" else 0,
                script_id=script["id"],
                script_name=script["name"],
                rules=script.get("rules", [])
            )
            return {"success": True, "job_id": job_id}

        @app.post("/api/jobs/{job_id}/pause")
        async def toggle_job(job_id: str):
            """暫停或繼續任務"""
            if not self.scheduler: return {"success": False}
            st = self.scheduler.get_task_by_job_id(job_id)
            if st:
                st.enabled = not st.enabled
                return {"success": True, "enabled": st.enabled}
            return {"success": False}

        @app.delete("/api/jobs/{job_id}")
        async def remove_job(job_id: str):
            """徹底刪除任務"""
            if not self.scheduler: return {"success": False}
            success = self.scheduler.remove_task(job_id=job_id)
            return {"success": success}

        @app.get("/api/screenshot/highres")
        async def get_highres_screenshot():
            """取得高畫質原始截圖（供前端裁切使用）"""
            if not self.adb:
                return JSONResponse(status_code=500, content={"error": "ADB 未連線"})
            
            try:
                # 直接截取原始大小
                img = self.adb.screenshot()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                b64 = base64.b64encode(buf.getvalue()).decode()
                return {"image": b64, "width": img.width, "height": img.height}
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

        @app.websocket("/ws/screen")
        async def ws_screen(websocket: WebSocket):
            await websocket.accept()
            try:
                while self._running:
                    if self.adb:
                        try:
                            # 監視用的低畫質低幀率截圖
                            img = self.adb.screenshot()
                            buf = io.BytesIO()
                            img.save(buf, format="JPEG", quality=60)
                            b64 = base64.b64encode(buf.getvalue()).decode()
                            await websocket.send_json({
                                "type": "frame",
                                "image": b64,
                                "time": time.time(),
                            })
                        except Exception as e:
                            await websocket.send_json({"type": "error", "message": str(e)})
                    await asyncio.sleep(self._screenshot_interval)
            except WebSocketDisconnect:
                pass

        return app
