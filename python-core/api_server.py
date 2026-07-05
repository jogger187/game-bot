"""
Python HTTP API 伺服器 — 使用 SQLite 持久化儲存
讓前端在瀏覽器開發模式下能直接操作，所有資料永久保存
"""
import asyncio
import base64
import json
import subprocess
import sys
from pathlib import Path
from aiohttp import web
from aiohttp.web import middleware

import database as db

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ASSETS_DIR = PROJECT_ROOT / "assets"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ASSETS_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)

# 全域 DB 連線（啟動時初始化）
conn = None

# 裝置狀態（仍為記憶體，因為是即時狀態）
device_state = {
    "connected": False,
    "serial": "",
    "mode": "adb",
    "emulator_type": "auto",
    "resolution": [0, 0],
}


def add_log(msg: str, level: str = "info", source: str = "system", job_id=None):
    """新增日誌（寫入 DB + 終端輸出）"""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    try:
        db.log_add(conn, msg, level=level, source=source, job_id=job_id)
    except Exception as e:
        print(f"⚠️ 日誌寫入失敗: {e}")


def run_adb(*args, serial=None):
    """執行 ADB 命令"""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except FileNotFoundError:
        return "ERROR: adb not found"


# ═══════════════════════════════════════════
#  CORS 中間件
# ═══════════════════════════════════════════
@middleware
async def cors_middleware(request, handler):
    """處理 CORS 跨域請求"""
    if request.method == "OPTIONS":
        response = web.Response()
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ═══════════════════════════════════════════
#  裝置 API
# ═══════════════════════════════════════════
async def device_list(request):
    """列出所有 ADB 裝置"""
    output = run_adb("devices")
    devices = []
    for line in output.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) == 2:
            devices.append({"serial": parts[0], "status": parts[1]})
    return web.json_response({"devices": devices})


async def device_connect(request):
    """連接指定裝置"""
    data = await request.json()
    serial = data.get("serial", "").strip()

    if not serial:
        # 自動選擇第一個可用裝置
        output = run_adb("devices")
        for line in output.splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) == 2 and parts[1] == "device":
                serial = parts[0]
                break

    if not serial:
        return web.json_response({"error": "找不到可用裝置"}, status=400)

    # 取得螢幕解析度
    size_output = run_adb("shell", "wm", "size", serial=serial)
    resolution = [0, 0]
    if "Physical size:" in size_output:
        try:
            wh = size_output.split("Physical size:")[-1].strip().split("x")
            resolution = [int(wh[0]), int(wh[1])]
        except (ValueError, IndexError):
            pass

    device_state["connected"] = True
    device_state["serial"] = serial
    device_state["resolution"] = resolution
    device_state["emulator_type"] = data.get("emulator_type", "auto")

    add_log(f"✅ 已連接裝置: {serial} ({resolution[0]}x{resolution[1]})", source="device")
    return web.json_response(device_state)


async def device_disconnect(request):
    """斷開裝置"""
    old_serial = device_state["serial"]
    device_state["connected"] = False
    device_state["serial"] = ""
    device_state["resolution"] = [0, 0]
    _clear_desktop_cache()
    add_log(f"🔌 已斷開裝置: {old_serial}", source="device")
    return web.json_response({"ok": True})


async def device_status(request):
    """取得裝置狀態"""
    return web.json_response(device_state)


# ═══════════════════════════════════════════
#  桌面視窗 API
# ═══════════════════════════════════════════
async def desktop_windows(request):
    """列出所有桌面視窗"""
    try:
        from core.desktop_controller import DesktopController
        windows = DesktopController.list_windows(include_offscreen=True)
        return web.json_response([w.to_dict() for w in windows])
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def desktop_pick_window(request):
    """進入選取模式，擷取下一次滑鼠點擊的視窗"""
    try:
        script_path = PROJECT_ROOT / "python-core" / "pick_window.py"
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 等待最多 15 秒
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        except asyncio.TimeoutError:
            proc.terminate()
            return web.json_response({"error": "等待超時，請在 15 秒內點擊目標視窗"}, status=408)
            
        if proc.returncode == 0:
            return web.json_response(json.loads(stdout.decode().strip()))
        else:
            return web.json_response({"error": stderr.decode().strip() or stdout.decode().strip()}, status=500)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def desktop_connect(request):
    """連接桌面視窗"""
    data = await request.json()
    window_id = data.get("window_id")
    window_title = data.get("window_title")

    try:
        from core.desktop_controller import DesktopController
        dc = DesktopController(window_id=window_id, window_title=window_title)
        dc.connect()
        
        win = dc._target_window
        device_state["connected"] = True
        device_state["serial"] = dc.serial
        device_state["mode"] = "desktop"
        device_state["resolution"] = [win.width, win.height] if win else [0, 0]
        device_state["window_id"] = win.window_id if win else None
        
        add_log(f"✅ 已連接桌面視窗: {win.owner_name} - {win.window_name} ({device_state['resolution'][0]}x{device_state['resolution'][1]})", source="device")
        return web.json_response(device_state)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════
#  截圖 API
# ═══════════════════════════════════════════

# Desktop controller 單例快取（避免每次截圖重建）
_desktop_controller_cache = {}


def _get_desktop_controller(wid: int):
    """取得或建立 DesktopController（快取，避免重複 connect）"""
    if wid not in _desktop_controller_cache:
        from core.desktop_controller import DesktopController
        dc = DesktopController(window_id=wid)
        dc.connect()
        _desktop_controller_cache[wid] = dc
    return _desktop_controller_cache[wid]


def _clear_desktop_cache():
    """清除快取（裝置斷線時呼叫）"""
    _desktop_controller_cache.clear()


def _do_desktop_screenshot(wid: int) -> tuple:
    """同步截圖（在 executor thread 執行，避免 block event loop）"""
    import io
    dc = _get_desktop_controller(wid)
    try:
        img = dc.screenshot()
    except Exception:
        # 可能 window ID 失效，清快取重試一次
        _desktop_controller_cache.pop(wid, None)
        dc = _get_desktop_controller(wid)
        img = dc.screenshot()
    width, height = img.size
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return b64, width, height


async def screenshot_capture(request):
    """擷取裝置截圖（返回 base64）"""
    if not device_state["connected"]:
        return web.json_response({"error": "裝置未連線"}, status=400)

    serial = device_state["serial"]
    mode = device_state.get("mode", "adb")
    add_log(f"📸 正在擷取截圖... ({serial})", source="device")

    import io
    from PIL import Image

    loop = asyncio.get_event_loop()

    try:
        if mode == "desktop":
            wid = device_state.get("window_id")
            if not wid:
                return web.json_response({"error": "沒有選擇視窗"}, status=400)

            # 用 executor 執行同步 Quartz 截圖，避免 block event loop
            b64, width, height = await asyncio.wait_for(
                loop.run_in_executor(None, _do_desktop_screenshot, wid),
                timeout=15
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                "adb", "-s", serial, "exec-out", "screencap", "-p",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

            if not stdout:
                add_log(f"❌ 截圖失敗: {stderr.decode()}", level="error", source="device")
                return web.json_response({"error": "截圖失敗"}, status=500)

            img = Image.open(io.BytesIO(stdout))
            width, height = img.size
            b64 = base64.b64encode(stdout).decode("utf-8")

        image_b64 = f"data:image/png;base64,{b64}"
        add_log(f"📸 截圖完成: {width}x{height}", source="device")
        return web.json_response({
            "image_b64": image_b64,
            "width": width,
            "height": height,
        })
    except asyncio.TimeoutError:
        add_log("❌ 截圖逾時", level="error", source="device")
        return web.json_response({"error": "截圖逾時"}, status=500)
    except Exception as e:
        add_log(f"❌ 截圖錯誤: {e}", level="error", source="device")
        return web.json_response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════
#  資源 API — 使用 SQLite + 檔案系統
# ═══════════════════════════════════════════
async def api_asset_list(request):
    """列出所有模板圖片"""
    # 同時從檔案系統同步到 DB
    assets = []
    if ASSETS_DIR.exists():
        for f in sorted(ASSETS_DIR.iterdir()):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                db.asset_upsert(conn, name=f.name, file_path=str(f), file_size=f.stat().st_size)
                assets.append({"name": f.name, "size": f.stat().st_size})
    return web.json_response(assets)


async def api_asset_save(request):
    """儲存裁切的模板圖片"""
    data = await request.json()
    name = data.get("name", "")
    image_b64 = data.get("image_b64", "")

    if not name or not image_b64:
        return web.json_response({"error": "缺少 name 或 image_b64"}, status=400)

    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    img_data = base64.b64decode(image_b64)
    filepath = ASSETS_DIR / name
    filepath.write_bytes(img_data)

    # 寫入 DB metadata
    db.asset_upsert(conn, name=name, file_path=str(filepath), file_size=len(img_data))

    add_log(f"💾 已儲存模板: {name} ({len(img_data)} bytes)")
    return web.json_response({"name": name, "size": len(img_data)})


async def api_asset_delete(request):
    """刪除模板圖片"""
    name = request.match_info["name"]
    filepath = ASSETS_DIR / name
    if filepath.exists():
        filepath.unlink()
    db.asset_delete(conn, name)
    add_log(f"🗑️ 已刪除模板: {name}")
    return web.json_response({"ok": True})


async def api_asset_read(request):
    """讀取模板圖片（返回 base64）"""
    name = request.match_info["name"]
    filepath = ASSETS_DIR / name
    if not filepath.exists():
        return web.json_response({"error": "找不到檔案"}, status=404)

    img_data = filepath.read_bytes()
    ext = filepath.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    b64 = base64.b64encode(img_data).decode("utf-8")
    return web.json_response({"image_b64": f"data:image/{ext};base64,{b64}"})


# ═══════════════════════════════════════════
#  腳本 API — 使用 SQLite
# ═══════════════════════════════════════════
async def api_script_list(request):
    """列出所有腳本"""
    scripts = db.script_list(conn)
    return web.json_response(scripts)


async def api_script_create(request):
    """建立新腳本"""
    data = await request.json()
    name = data.get("name", "新腳本")
    script = db.script_create(conn, name)
    add_log(f"📝 已建立腳本: {name} ({script['id'][:8]}...)", source="script")
    return web.json_response(script)


async def api_script_save(request):
    """儲存腳本"""
    script_data = await request.json()
    script_id = script_data.get("id", "")

    if not script_id:
        return web.json_response({"error": "缺少 script id"}, status=400)

    # 如果 DB 中不存在，先建立
    existing = db.script_get(conn, script_id)
    if not existing:
        # 直接 INSERT（用於從 JSON 遷移過來的場景）
        conn.execute(
            """INSERT INTO scripts (id, name, version, nodes, edges, settings, rules, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                script_id,
                script_data.get("name", ""),
                script_data.get("version", 1),
                json.dumps(script_data.get("nodes", [])),
                json.dumps(script_data.get("edges", [])),
                json.dumps(script_data.get("settings", {})),
                json.dumps(script_data.get("rules", [])),
                script_data.get("created_at", ""),
                script_data.get("updated_at", ""),
            ),
        )
        conn.commit()
        result = db.script_get(conn, script_id)
    else:
        result = db.script_save(conn, script_data)

    add_log(f"💾 已儲存腳本: {result['name']} (v{result['version']})", source="script")
    return web.json_response(result)


async def api_script_delete(request):
    """刪除腳本"""
    script_id = request.match_info["script_id"]
    db.script_delete(conn, script_id)
    add_log(f"🗑️ 已刪除腳本: {script_id[:8]}...", source="script")
    return web.json_response({"ok": True})


# ═══════════════════════════════════════════
#  任務執行 API — 使用 SQLite 持久化
# ═══════════════════════════════════════════
import threading
from script_runner import ScriptRunner, emergency_pause, emergency_resume, is_emergency_paused

# 執行中的 runner 實例（記憶體中保存，用於控制執行緒）
active_runners = {}


async def api_task_start(request):
    """啟動一個腳本任務"""
    data = await request.json()
    script_id = data.get("script_id", "")
    script_name = data.get("script_name", "")
    run_mode = data.get("run_mode", "loop")
    max_runs = data.get("max_runs", 0)
    loop_interval = max(0.1, data.get("loop_interval", 3))  # 最低 100ms
    scheduled_times = data.get("scheduled_times", [])  # 每日定時觸發的時間點列表

    if not device_state["connected"]:
        return web.json_response({"error": "裝置未連線"}, status=400)

    # 從 DB 讀取腳本
    script = db.script_get(conn, script_id)
    if not script:
        return web.json_response({"error": f"腳本不存在: {script_id}"}, status=404)

    # 覆蓋執行設定
    settings = script.get("settings", {})
    if run_mode == "scheduled":
        # 每日定時模式：使用定時觸發，每次執行一次
        settings["loop_enabled"] = False
        settings["max_runs"] = 0
        settings["scheduled_times"] = scheduled_times
    elif run_mode == "fixed":
        settings["loop_enabled"] = True
        settings["max_runs"] = max_runs
    elif run_mode == "loop":
        settings["loop_enabled"] = True
        settings["max_runs"] = 0
    else:
        settings["loop_enabled"] = False
    settings["interval"] = loop_interval
    script["settings"] = settings

    # 建立任務記錄到 DB
    task_info = db.task_create(conn, script_id, script_name or script["name"], run_mode, max_runs)
    job_id = task_info["job_id"]

    if run_mode == "scheduled":
        # 定時模式：使用調度器管理
        add_log(f"⏰ 定時任務已建立: {script['name']} (job={job_id}), 觸發時間: {', '.join(scheduled_times)}", source="task", job_id=job_id)
        # TODO: 實作定時調度器
        # 目前先存儲設定，後續可以實作調度器來定時執行
        return web.json_response(task_info)
    else:
        # 循環/固定次數模式：直接啟動執行緒
        runner = ScriptRunner(serial=device_state["serial"], on_log=lambda msg: add_log(msg, source="task", job_id=job_id))

        def run_in_thread():
            try:
                runner.run(script)
            finally:
                db.task_update_count(conn, job_id, runner.run_count)
                db.task_complete(conn, job_id)
                active_runners.pop(job_id, None)

        t = threading.Thread(target=run_in_thread, daemon=True)
        t.start()

        active_runners[job_id] = {"runner": runner, "thread": t}
        add_log(f"🚀 任務已啟動: {script['name']} (job={job_id})", source="task", job_id=job_id)
        return web.json_response(task_info)


async def api_task_list(request):
    """列出所有任務"""
    # 更新執行中任務的 run_count
    for jid, entry in active_runners.items():
        runner = entry["runner"]
        db.task_update_count(conn, jid, runner.run_count)
        # 同步 enabled 狀態
        task = db.task_get(conn, jid)
        if task and not task["completed"]:
            new_enabled = runner.running and not runner.paused
            if new_enabled != task["enabled"]:
                conn.execute(
                    "UPDATE tasks SET enabled = ?, updated_at = ? WHERE job_id = ?",
                    (1 if new_enabled else 0, db._now_iso(), jid),
                )
                conn.commit()

    tasks = db.task_list(conn)
    return web.json_response(tasks)


async def api_task_toggle(request):
    """暫停/繼續任務"""
    job_id = request.match_info["job_id"]

    # 如果有 runner，先操作 runner
    entry = active_runners.get(job_id)
    if entry:
        entry["runner"].toggle_pause()

    task = db.task_toggle(conn, job_id)
    if not task:
        return web.json_response({"error": "任務不存在"}, status=404)

    status_text = "▶️ 任務繼續" if task["enabled"] else "⏸️ 任務暫停"
    add_log(f"{status_text}: {task['script_name']}", source="task", job_id=job_id)
    return web.json_response(task)


async def api_task_stop(request):
    """停止任務"""
    job_id = request.match_info["job_id"]

    # 停止 runner
    entry = active_runners.pop(job_id, None)
    if entry:
        entry["runner"].stop()

    db.task_stop(conn, job_id)
    task = db.task_get(conn, job_id)
    name = task["script_name"] if task else "未知"
    add_log(f"🛑 任務已停止: {name} (job={job_id})", source="task", job_id=job_id)
    return web.json_response({"ok": True})


async def api_task_remove(request):
    """移除任務（從列表刪除）"""
    job_id = request.match_info["job_id"]

    # 確保 runner 已停止
    entry = active_runners.pop(job_id, None)
    if entry:
        entry["runner"].stop()

    task = db.task_get(conn, job_id)
    name = task["script_name"] if task else "未知"
    db.task_remove(conn, job_id)
    add_log(f"🗑️ 已移除任務: {name} (job={job_id})", source="task")
    return web.json_response({"ok": True})

# ═══════════════════════════════════════════
#  緊急暫停 API
# ═══════════════════════════════════════════
async def api_emergency_status(request):
    """取得緊急暫停狀態"""
    return web.json_response({"emergency_paused": is_emergency_paused()})


async def api_emergency_pause(request):
    """觸發緊急暫停"""
    emergency_pause()
    # 同步更新所有 runner 的 paused 狀態
    for jid, entry in active_runners.items():
        runner = entry["runner"]
        if runner.running and not runner.paused:
            runner.paused = True
            db.task_toggle(conn, jid)
    add_log("⏸️ 緊急暫停已觸發（所有任務已暫停）", level="warning")
    return web.json_response({"emergency_paused": True})


async def api_emergency_resume(request):
    """解除緊急暫停"""
    emergency_resume()
    # 同步恢復所有 runner
    for jid, entry in active_runners.items():
        runner = entry["runner"]
        if runner.running and runner.paused:
            runner.paused = False
            db.task_toggle(conn, jid)
    add_log("▶️ 緊急暫停已解除（所有任務已恢復）")
    return web.json_response({"emergency_paused": False})


# ═══════════════════════════════════════════
#  日誌 API — 使用 SQLite
# ═══════════════════════════════════════════
async def api_get_logs(request):
    """取得日誌"""
    limit = int(request.query.get("limit", "200"))
    logs = db.log_list(conn, limit=limit)
    return web.json_response(logs)


# ═══════════════════════════════════════════
#  設定 API
# ═══════════════════════════════════════════
async def api_settings_get(request):
    """取得所有設定"""
    settings = db.settings_all(conn)
    return web.json_response(settings)


async def api_settings_set(request):
    """更新設定"""
    data = await request.json()
    for key, value in data.items():
        db.setting_set(conn, key, value)
    return web.json_response({"ok": True})


# ═══════════════════════════════════════════
#  啟動伺服器
# ═══════════════════════════════════════════
def create_app():
    app = web.Application(middlewares=[cors_middleware])

    # 裝置
    app.router.add_get("/api/devices", device_list)
    app.router.add_post("/api/device/connect", device_connect)
    app.router.add_post("/api/device/disconnect", device_disconnect)
    app.router.add_get("/api/device/status", device_status)

    # 桌面視窗
    app.router.add_get("/api/desktop/windows", desktop_windows)
    app.router.add_post("/api/desktop/connect", desktop_connect)
    app.router.add_post('/api/desktop/pick', desktop_pick_window)

    # 截圖
    app.router.add_post("/api/screenshot", screenshot_capture)

    # 資源
    app.router.add_get("/api/assets", api_asset_list)
    app.router.add_post("/api/assets", api_asset_save)
    app.router.add_delete("/api/assets/{name}", api_asset_delete)
    app.router.add_get("/api/assets/{name}/read", api_asset_read)

    # 腳本
    app.router.add_get("/api/scripts", api_script_list)
    app.router.add_post("/api/scripts", api_script_create)
    app.router.add_put("/api/scripts", api_script_save)
    app.router.add_delete("/api/scripts/{script_id}", api_script_delete)

    # 任務
    app.router.add_post("/api/tasks", api_task_start)
    app.router.add_get("/api/tasks", api_task_list)
    app.router.add_post("/api/tasks/{job_id}/toggle", api_task_toggle)
    app.router.add_post("/api/tasks/{job_id}/stop", api_task_stop)
    app.router.add_delete("/api/tasks/{job_id}", api_task_remove)

    # 日誌
    app.router.add_get("/api/logs", api_get_logs)

    # 設定
    app.router.add_get("/api/settings", api_settings_get)
    app.router.add_put("/api/settings", api_settings_set)

    # 緊急暫停
    app.router.add_get("/api/emergency", api_emergency_status)
    app.router.add_post("/api/emergency/pause", api_emergency_pause)
    app.router.add_post("/api/emergency/resume", api_emergency_resume)

    return app


if __name__ == "__main__":
    import signal

    def _graceful_exit(signum, frame):
        """SIGTERM/SIGINT graceful shutdown — 讓 Python 正常 cleanup，避免 Quartz segfault"""
        print(f"\n[api_server] 收到 signal {signum}，正常關閉...")
        # 停止所有 active runners
        for jid, entry in list(active_runners.items()):
            try:
                entry["runner"].stop()
            except Exception:
                pass
        # flush 日誌緩衝區
        try:
            db.log_flush(conn)
        except Exception:
            pass
        # 清除 desktop controller cache
        _clear_desktop_cache()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _graceful_exit)
    signal.signal(signal.SIGINT, _graceful_exit)

    # 初始化資料庫
    conn = db.init_db()
    add_log("🚀 Game Bot API Server 啟動中...")

    # 啟動全域熱鍵監聽
    try:
        from pynput import keyboard
        def on_press(key):
            if key == keyboard.Key.esc:
                if is_emergency_paused():
                    # 已經是暫停狀態 → 恢復
                    emergency_resume()
                    for jid, entry in active_runners.items():
                        runner = entry["runner"]
                        if runner.running and runner.paused:
                            runner.paused = False
                            db.task_toggle(conn, jid)
                    print("\n[HotKey] 已恢復所有任務 (ESC)")
                    add_log("▶️ ESC 解除緊急暫停，所有任務已恢復")
                else:
                    # 觸發緊急暫停
                    emergency_pause()
                    for jid, entry in active_runners.items():
                        runner = entry["runner"]
                        if runner.running and not runner.paused:
                            runner.paused = True
                            db.task_toggle(conn, jid)
                    print("\n[HotKey] 已暫停所有任務 (ESC)")
                    add_log("⏸️ ESC 緊急暫停，所有任務已暫停", level="warning")

        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()
        add_log("⌨️  全域熱鍵已啟動 (ESC: 暫停所有任務)")
    except ImportError:
        add_log("⚠️  pynput 未安裝，無法使用全域熱鍵功能 (請執行 pip install pynput)")
    except Exception as e:
        add_log(f"⚠️  全域熱鍵啟動失敗: {e}")

    app = create_app()
    print("=" * 50)
    print("  Game Bot Python API Server")
    print(f"  http://localhost:8765")
    print(f"  📁 DB: {db.DB_PATH}")
    print("=" * 50)
    web.run_app(app, host="0.0.0.0", port=8765)
