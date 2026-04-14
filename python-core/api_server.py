"""
Python HTTP API 伺服器 — 提供 ADB 裝置控制與截圖 REST API
讓前端在瀏覽器開發模式下能直接操作真實模擬器
"""
import asyncio
import base64
import json
import os
import subprocess
import shutil
from pathlib import Path
from aiohttp import web
from aiohttp.web import middleware

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ASSETS_DIR.mkdir(exist_ok=True)
SCRIPTS_DIR.mkdir(exist_ok=True)

# 全域狀態
state = {
    "connected": False,
    "serial": "",
    "mode": "adb",
    "emulator_type": "auto",
    "resolution": [0, 0],
}
logs = []


def add_log(msg: str):
    """新增日誌"""
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    logs.append(entry)
    if len(logs) > 500:
        logs.pop(0)
    print(entry)


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

    state["connected"] = True
    state["serial"] = serial
    state["resolution"] = resolution
    state["emulator_type"] = data.get("emulator_type", "auto")

    add_log(f"✅ 已連接裝置: {serial} ({resolution[0]}x{resolution[1]})")
    return web.json_response(state)


async def device_disconnect(request):
    """斷開裝置"""
    old_serial = state["serial"]
    state["connected"] = False
    state["serial"] = ""
    state["resolution"] = [0, 0]
    add_log(f"🔌 已斷開裝置: {old_serial}")
    return web.json_response({"ok": True})


async def device_status(request):
    """取得裝置狀態"""
    return web.json_response(state)


# ═══════════════════════════════════════════
#  截圖 API
# ═══════════════════════════════════════════
async def screenshot_capture(request):
    """擷取裝置截圖（返回 base64）"""
    if not state["connected"]:
        return web.json_response({"error": "裝置未連線"}, status=400)

    serial = state["serial"]
    add_log(f"📸 正在擷取截圖... ({serial})")

    # 使用 adb screencap
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", "-s", serial, "exec-out", "screencap", "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if not stdout:
            add_log(f"❌ 截圖失敗: {stderr.decode()}")
            return web.json_response({"error": "截圖失敗"}, status=500)

        # 取得圖片尺寸
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(stdout))
        width, height = img.size

        # 轉 base64
        b64 = base64.b64encode(stdout).decode("utf-8")
        image_b64 = f"data:image/png;base64,{b64}"

        add_log(f"📸 截圖完成: {width}x{height}")
        return web.json_response({
            "image_b64": image_b64,
            "width": width,
            "height": height,
        })
    except asyncio.TimeoutError:
        add_log("❌ 截圖逾時")
        return web.json_response({"error": "截圖逾時"}, status=500)
    except Exception as e:
        add_log(f"❌ 截圖錯誤: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════
#  資源 API
# ═══════════════════════════════════════════
async def asset_list(request):
    """列出所有模板圖片"""
    assets = []
    if ASSETS_DIR.exists():
        for f in sorted(ASSETS_DIR.iterdir()):
            if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                assets.append({"name": f.name, "size": f.stat().st_size})
    return web.json_response(assets)


async def asset_save(request):
    """儲存裁切的模板圖片"""
    data = await request.json()
    name = data.get("name", "")
    image_b64 = data.get("image_b64", "")

    if not name or not image_b64:
        return web.json_response({"error": "缺少 name 或 image_b64"}, status=400)

    # 解碼 base64
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]

    img_data = base64.b64decode(image_b64)
    filepath = ASSETS_DIR / name
    filepath.write_bytes(img_data)

    add_log(f"💾 已儲存模板: {name} ({len(img_data)} bytes)")
    return web.json_response({"name": name, "size": len(img_data)})


async def asset_delete(request):
    """刪除模板圖片"""
    name = request.match_info["name"]
    filepath = ASSETS_DIR / name
    if filepath.exists():
        filepath.unlink()
        add_log(f"🗑️ 已刪除模板: {name}")
    return web.json_response({"ok": True})


async def asset_read(request):
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
#  腳本 API
# ═══════════════════════════════════════════
async def script_list(request):
    """列出所有腳本"""
    scripts = []
    if SCRIPTS_DIR.exists():
        for f in sorted(SCRIPTS_DIR.iterdir()):
            if f.suffix == ".json":
                try:
                    data = json.loads(f.read_text("utf-8"))
                    scripts.append(data)
                except (json.JSONDecodeError, OSError):
                    pass
    return web.json_response(scripts)


async def script_create(request):
    """建立新腳本"""
    data = await request.json()
    name = data.get("name", "新腳本")
    from datetime import datetime
    import uuid

    now = datetime.utcnow().isoformat() + "Z"
    script_id = str(uuid.uuid4())

    script = {
        "id": script_id,
        "name": name,
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "nodes": [
            {"id": "start_1", "type": "start", "position": {"x": 100, "y": 200}, "data": {}},
            {"id": "end_1", "type": "end", "position": {"x": 600, "y": 200}, "data": {}},
        ],
        "edges": [],
        "settings": {"loop_enabled": True, "interval": 3, "max_runs": 0},
        "rules": [],
    }

    filepath = SCRIPTS_DIR / f"{script_id}.json"
    filepath.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    add_log(f"📝 已建立腳本: {name} ({script_id})")
    return web.json_response(script)


async def script_save(request):
    """儲存腳本"""
    script = await request.json()
    script_id = script.get("id", "")

    if not script_id:
        return web.json_response({"error": "缺少 script id"}, status=400)

    from datetime import datetime
    script["updated_at"] = datetime.utcnow().isoformat() + "Z"
    script["version"] = script.get("version", 0) + 1

    filepath = SCRIPTS_DIR / f"{script_id}.json"
    filepath.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    add_log(f"💾 已儲存腳本: {script.get('name', '')} (v{script['version']})")
    return web.json_response(script)


async def script_delete(request):
    """刪除腳本"""
    script_id = request.match_info["script_id"]
    filepath = SCRIPTS_DIR / f"{script_id}.json"
    if filepath.exists():
        filepath.unlink()
        add_log(f"🗑️ 已刪除腳本: {script_id}")
    return web.json_response({"ok": True})


# ═══════════════════════════════════════════
#  日誌 API
# ═══════════════════════════════════════════
async def get_logs(request):
    """取得日誌"""
    limit = int(request.query.get("limit", "100"))
    return web.json_response(logs[-limit:])


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

    # 截圖
    app.router.add_post("/api/screenshot", screenshot_capture)

    # 資源
    app.router.add_get("/api/assets", asset_list)
    app.router.add_post("/api/assets", asset_save)
    app.router.add_delete("/api/assets/{name}", asset_delete)
    app.router.add_get("/api/assets/{name}/read", asset_read)

    # 腳本
    app.router.add_get("/api/scripts", script_list)
    app.router.add_post("/api/scripts", script_create)
    app.router.add_put("/api/scripts", script_save)
    app.router.add_delete("/api/scripts/{script_id}", script_delete)

    # 日誌
    app.router.add_get("/api/logs", get_logs)

    return app


if __name__ == "__main__":
    add_log("🚀 Game Bot API Server 啟動中...")
    app = create_app()
    print("=" * 50)
    print("  Game Bot Python API Server")
    print("  http://localhost:8765")
    print("=" * 50)
    web.run_app(app, host="0.0.0.0", port=8765)
