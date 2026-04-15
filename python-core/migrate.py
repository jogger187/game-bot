"""
資料遷移工具 — 將現有 JSON 檔案資料匯入 SQLite 資料庫
執行: python python-core/migrate.py
"""
import json
import sys
from pathlib import Path

# 確保可以 import database 模組
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_db, get_connection, DB_PATH,
    asset_upsert, log_add,
)

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ASSETS_DIR = PROJECT_ROOT / "assets"


def migrate_scripts(conn):
    """將 scripts/*.json 匯入資料庫"""
    if not SCRIPTS_DIR.exists():
        print("⚠️  scripts/ 資料夾不存在，跳過")
        return 0

    count = 0
    for f in sorted(SCRIPTS_DIR.glob("*.json")):
        try:
            script = json.loads(f.read_text("utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ❌ 讀取失敗: {f.name} — {e}")
            continue

        script_id = script.get("id", f.stem)
        name = script.get("name", "未命名")

        conn.execute(
            """INSERT OR REPLACE INTO scripts
               (id, name, version, nodes, edges, settings, rules, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                script_id,
                name,
                script.get("version", 1),
                json.dumps(script.get("nodes", [])),
                json.dumps(script.get("edges", [])),
                json.dumps(script.get("settings", {})),
                json.dumps(script.get("rules", [])),
                script.get("created_at", ""),
                script.get("updated_at", ""),
            ),
        )
        count += 1
        print(f"  ✅ 已匯入腳本: {name} ({script_id[:8]}...)")

    conn.commit()
    return count


def migrate_assets(conn):
    """將 assets/ 中的圖片 metadata 匯入資料庫"""
    if not ASSETS_DIR.exists():
        print("⚠️  assets/ 資料夾不存在，跳過")
        return 0

    count = 0
    for f in sorted(ASSETS_DIR.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            asset_upsert(
                conn,
                name=f.name,
                file_path=str(f),
                file_size=f.stat().st_size,
            )
            count += 1
            print(f"  ✅ 已匯入資源: {f.name} ({f.stat().st_size} bytes)")

    return count


def migrate_legacy_scripts_json(conn):
    """匯入舊版 scripts.json（如果存在）"""
    legacy_path = PROJECT_ROOT / "scripts.json"
    if not legacy_path.exists():
        return 0

    try:
        scripts = json.loads(legacy_path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0

    count = 0
    for script in scripts:
        script_id = script.get("id", "")
        if not script_id:
            continue

        name = script.get("name", "未命名")
        conn.execute(
            """INSERT OR IGNORE INTO scripts
               (id, name, version, nodes, edges, settings, rules, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                script_id,
                name,
                script.get("version", 1),
                json.dumps(script.get("nodes", [])),
                json.dumps(script.get("edges", [])),
                json.dumps(script.get("settings", {})),
                json.dumps(script.get("rules", [])),
                script.get("created_at", ""),
                script.get("updated_at", ""),
            ),
        )
        count += 1
        print(f"  ✅ 已匯入舊版腳本: {name}")

    conn.commit()
    return count


def main():
    print("=" * 50)
    print("  Game Bot 資料遷移工具")
    print("=" * 50)
    print(f"\n📁 資料庫位置: {DB_PATH}")

    # 初始化資料庫
    conn = init_db()

    # 遷移腳本
    print("\n📝 遷移腳本...")
    script_count = migrate_scripts(conn)
    legacy_count = migrate_legacy_scripts_json(conn)
    print(f"   共匯入 {script_count + legacy_count} 個腳本")

    # 遷移資源
    print("\n🖼️  遷移資源...")
    asset_count = migrate_assets(conn)
    print(f"   共匯入 {asset_count} 個資源")

    # 記錄遷移日誌
    log_add(conn, f"📦 資料遷移完成: {script_count} 個腳本, {asset_count} 個資源")

    conn.close()

    print(f"\n✅ 遷移完成！資料庫: {DB_PATH}")
    print(f"   檔案大小: {DB_PATH.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
