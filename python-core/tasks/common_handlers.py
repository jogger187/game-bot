"""通用中斷處理器 — 處理遊戲中的彈窗、斷線、crash 等

提供可複用的中斷偵測與處理函式，
可直接註冊到 BaseTask 的 interrupt_handlers。

使用方式:
    task = MyTask(adb, matcher, input_sim)
    handlers = CommonHandlers(adb, matcher, input_sim)
    handlers.register_all(task)
"""

from __future__ import annotations

import time

from loguru import logger

from .base_task import BaseTask


class CommonHandlers:
    """通用中斷處理器集合"""

    def __init__(self, adb, matcher, input_sim, ocr=None):
        self.adb = adb
        self.matcher = matcher
        self.input = input_sim
        self.ocr = ocr

    def register_all(self, task: BaseTask) -> None:
        """一次註冊所有通用處理器"""
        self.register_popup_handler(task)
        self.register_disconnect_handler(task)
        self.register_crash_handler(task)

    # ── 彈窗處理 ──────────────────────────────────────────

    def register_popup_handler(
        self,
        task: BaseTask,
        close_templates: list[str] | None = None,
    ) -> None:
        """
        註冊彈窗處理器

        預設偵測: close_btn.png, cancel_btn.png, confirm_btn.png
        """
        templates = close_templates or [
            "close_btn.png",
            "cancel_btn.png",
            "confirm_btn.png",
            "ok_btn.png",
            "x_btn.png",
        ]

        def detect_popup() -> bool:
            screen = self.adb.screenshot()
            for tmpl in templates:
                try:
                    if self.matcher.exists(screen, tmpl, threshold=0.8):
                        return True
                except FileNotFoundError:
                    continue
            return False

        def handle_popup() -> None:
            screen = self.adb.screenshot()
            for tmpl in templates:
                try:
                    match = self.matcher.find(screen, tmpl, threshold=0.8)
                    if match:
                        logger.info(f"🔲 關閉彈窗: {tmpl}")
                        self.input.tap_match(match)
                        time.sleep(0.5)
                        return
                except FileNotFoundError:
                    continue
            # fallback: 按返回鍵
            logger.info("🔲 彈窗處理: 按返回鍵")
            self.adb.back()
            time.sleep(0.5)

        task.register_interrupt("popup", detect_popup, handle_popup)

    # ── 斷線重連 ──────────────────────────────────────────

    def register_disconnect_handler(
        self,
        task: BaseTask,
        disconnect_templates: list[str] | None = None,
        reconnect_templates: list[str] | None = None,
        game_package: str | None = None,
    ) -> None:
        """
        註冊斷線重連處理器

        偵測: 「連線中斷」「網路異常」等文字或模板
        """
        dc_templates = disconnect_templates or [
            "disconnect_dialog.png",
            "network_error.png",
            "reconnect_btn.png",
        ]
        rc_templates = reconnect_templates or [
            "reconnect_btn.png",
            "retry_btn.png",
            "confirm_btn.png",
        ]

        def detect_disconnect() -> bool:
            screen = self.adb.screenshot()
            # 模板偵測
            for tmpl in dc_templates:
                try:
                    if self.matcher.exists(screen, tmpl, threshold=0.8):
                        return True
                except FileNotFoundError:
                    continue
            # 文字偵測
            if self.ocr:
                keywords = ["斷線", "連線中斷", "網路異常", "重新連線", "disconnect", "network error"]
                for kw in keywords:
                    if self.ocr.find_text(screen, kw, fuzzy=True):
                        return True
            return False

        def handle_disconnect() -> None:
            logger.warning("📡 偵測到斷線，嘗試重連...")
            screen = self.adb.screenshot()

            # 嘗試點重連按鈕
            for tmpl in rc_templates:
                try:
                    match = self.matcher.find(screen, tmpl, threshold=0.8)
                    if match:
                        logger.info(f"🔄 點擊重連: {tmpl}")
                        self.input.tap_match(match)
                        time.sleep(5)  # 等待重連
                        return
                except FileNotFoundError:
                    continue

            # 文字按鈕
            if self.ocr:
                for label in ["重新連線", "重試", "確認", "OK"]:
                    result = self.ocr.find_text(screen, label, fuzzy=True)
                    if result:
                        self.input.tap(result.center[0], result.center[1])
                        time.sleep(5)
                        return

            # 最後手段：重啟遊戲
            if game_package:
                logger.warning(f"🔄 重啟遊戲: {game_package}")
                self.adb.kill_app(game_package)
                time.sleep(2)
                self.adb.launch_app(game_package)
                time.sleep(10)

        task.register_interrupt("disconnect", detect_disconnect, handle_disconnect)

    # ── App Crash 處理 ────────────────────────────────────

    def register_crash_handler(
        self,
        task: BaseTask,
        game_package: str | None = None,
        max_restarts: int = 3,
    ) -> None:
        """
        註冊 crash 處理器

        偵測 App 是否還在前台
        """
        restart_count = {"value": 0}

        def detect_crash() -> bool:
            if not game_package:
                return False
            try:
                current = self.adb.current_app()
                return game_package not in current
            except Exception:
                return True

        def handle_crash() -> None:
            if restart_count["value"] >= max_restarts:
                raise RuntimeError(f"Crash 重啟次數超過上限 ({max_restarts})")

            restart_count["value"] += 1
            logger.warning(
                f"💥 App crash 偵測! 重啟 #{restart_count['value']}/{max_restarts}"
            )

            if game_package:
                try:
                    self.adb.kill_app(game_package)
                except Exception:
                    pass
                time.sleep(2)
                self.adb.launch_app(game_package)
                time.sleep(10)

        task.register_interrupt("crash", detect_crash, handle_crash)

    # ── 自訂中斷 ──────────────────────────────────────────

    def register_template_interrupt(
        self,
        task: BaseTask,
        name: str,
        detect_template: str,
        action_template: str | None = None,
        action: str = "tap",
        threshold: float = 0.85,
    ) -> None:
        """
        快速註冊模板觸發的中斷

        detect_template: 偵測到此模板就觸發
        action_template: 點擊此模板處理（None 則點擊偵測到的）
        action: "tap" | "back" | "home"
        """

        def detect() -> bool:
            screen = self.adb.screenshot()
            try:
                return self.matcher.exists(screen, detect_template, threshold)
            except FileNotFoundError:
                return False

        def handle() -> None:
            if action == "back":
                self.adb.back()
            elif action == "home":
                self.adb.home()
            else:
                screen = self.adb.screenshot()
                target = action_template or detect_template
                try:
                    match = self.matcher.find(screen, target, threshold)
                    if match:
                        self.input.tap_match(match)
                except FileNotFoundError:
                    self.adb.back()
            time.sleep(0.5)

        task.register_interrupt(name, detect, handle)
