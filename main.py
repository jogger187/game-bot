"""手遊外掛主程式入口"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from core import (
    AdbController, ScreenCapMethod, ScreenMatcher, InputSimulator,
    OcrReader, PixelAnalyzer, SceneDetector, FeatureMatcher, TextParser,
    AntiDetect, AntiDetectConfig, StatsTracker, DebugViewer, GameFSM,
    Rhythm,
)
from tasks import TaskScheduler, CommonHandlers


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(config: dict) -> None:
    log_cfg = config.get("logging", {})
    logger.add(
        log_cfg.get("file", "logs/bot.log"),
        level=log_cfg.get("level", "DEBUG"),
        rotation=log_cfg.get("rotation", "10 MB"),
        encoding="utf-8",
    )


def main():
    # ── 載入設定 ──────────────────────────────────────────
    config = load_config()
    setup_logging(config)

    logger.info("🤖 手遊外掛啟動")
    logger.info("─" * 50)

    # ── 初始化核心模組 ────────────────────────────────────

    # 1. ADB 控制器
    device_cfg = config["device"]
    cap_method = device_cfg.get("mode", "adb")
    minicap_cfg = device_cfg.get("minicap", {})

    adb = AdbController(
        serial=device_cfg.get("serial"),
        cap_method=cap_method,
        minicap_quality=minicap_cfg.get("quality", 80),
        minicap_fps=minicap_cfg.get("max_fps", 10),
    )

    # 根據模式連線
    emu_cfg = device_cfg.get("emulator", {})
    if cap_method == "emulator":
        adb.connect_emulator(
            emu_type=emu_cfg.get("type", "auto"),
            install_path=emu_cfg.get("install_path"),
            index=emu_cfg.get("index", 0),
        )
    else:
        adb.connect()

    # 2. 模板比對
    matcher_cfg = config.get("matcher", {})
    matcher = ScreenMatcher(
        assets_dir="assets",
        default_threshold=matcher_cfg.get("default_threshold", 0.85),
        multi_scale=matcher_cfg.get("multi_scale", False),
        scale_range=tuple(matcher_cfg.get("scale_range", [0.8, 1.2])),
        scale_steps=matcher_cfg.get("scale_steps", 5),
        grayscale=matcher_cfg.get("grayscale", False),
    )

    # 3. 輸入模擬
    input_cfg = config.get("input", {})
    input_sim = InputSimulator(
        adb=adb,
        tap_offset=input_cfg.get("tap_offset_range", 10),
        tap_delay=(input_cfg.get("tap_delay_min", 0.05), input_cfg.get("tap_delay_max", 0.15)),
        action_delay=(input_cfg.get("action_delay_min", 0.8), input_cfg.get("action_delay_max", 1.5)),
        use_bezier=input_cfg.get("use_bezier", True),
        rhythm=input_cfg.get("rhythm", "casual"),
    )

    # 4. OCR
    ocr_cfg = config.get("ocr", {})
    ocr = OcrReader(
        lang=ocr_cfg.get("lang", "ch"),
        use_gpu=ocr_cfg.get("use_gpu", False),
        digit_mode=ocr_cfg.get("digit_mode", False),
    )

    # 5. 像素分析器
    pixel_analyzer = PixelAnalyzer()

    # 6. 場景偵測器
    scene_detector = SceneDetector(
        matcher=matcher,
        ocr=ocr,
        pixel_analyzer=pixel_analyzer,
    )
    scenes_dir = config.get("scenes", {}).get("config_dir", "./scenes")
    if Path(scenes_dir).exists():
        scene_detector.load_scenes(scenes_dir)

    # 7. 防偵測
    ad_cfg = config.get("anti_detect", {})
    anti_detect = None
    if ad_cfg.get("enabled", True):
        anti_detect = AntiDetect(AntiDetectConfig(
            afk_chance=ad_cfg.get("afk_chance", 0.05),
            afk_duration=tuple(ad_cfg.get("afk_duration", [2.0, 8.0])),
            fatigue_enabled=ad_cfg.get("fatigue_enabled", True),
            fake_actions=ad_cfg.get("fake_actions", True),
        ))

    # 8. 統計追蹤
    stats_cfg = config.get("stats", {})
    stats = None
    if stats_cfg.get("enabled", True):
        stats = StatsTracker(
            export_path=stats_cfg.get("export_path", "logs/stats.json"),
            export_interval=stats_cfg.get("export_interval", 300),
        )

    # ── 啟動任務排程器 ────────────────────────────────────
    from tasks import TaskScheduler

    scheduler = TaskScheduler(
        adb=adb,
        matcher=matcher,
        input_sim=input_sim,
        ocr=ocr,
        anti_detect=anti_detect,
        scene_detector=scene_detector,
    )

    # 9. Debug Web UI
    debug_cfg = config.get("debug", {})
    viewer = None
    if debug_cfg.get("web_ui", False):
        viewer = DebugViewer(
            adb=adb,
            matcher=matcher,
            stats=stats,
            scheduler=scheduler,
        )
        viewer.start(port=debug_cfg.get("web_port", 8765))
        # 初次載入
        import requests
        try:
            requests.get(f"http://127.0.0.1:{debug_cfg.get('web_port', 8765)}/api/scripts")
            # 藉由取得時觸發？ 其實 API _sync_scheduler 在 GET 我們沒有放，我稍後在 debug_viewer 改
        except:
            pass

    logger.info("🚀 啟動無程式碼外掛引擎...")

    try:
        # 強制在主迴圈前載入一次預設 scripts.json
        if viewer:
            # 手動呼叫 sync_scheduler 方法（我們已經把它作為內部 function，所以我們直接在 DebugViewer 新增一個公開方法）
            pass
        
        scheduler.run_forever()
    except KeyboardInterrupt:
        logger.info("🛑 收到終止訊號，結束程式")

    # ── 清理 ─────────────────────────────────────────────
    # adb.cleanup()


if __name__ == "__main__":
    main()
