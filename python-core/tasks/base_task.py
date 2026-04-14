"""基礎任務類別 — 所有遊戲任務腳本的父類別

支援:
- 優先級排序
- 前置條件檢查
- 執行中斷偵測（彈窗、斷線等）
- 重試 + 錯誤恢復
- 任務鏈組合
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TYPE_CHECKING

from loguru import logger

from core import AdbController, ScreenMatcher, InputSimulator, OcrReader

if TYPE_CHECKING:
    from core.anti_detect import AntiDetect
    from core.scene_detector import SceneDetector


class TaskState(Enum):
    """任務狀態"""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    FAILED = auto()
    INTERRUPTED = auto()


class TaskPriority(Enum):
    """任務優先級"""
    LOW = 0
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100  # 最高優先（例如斷線重連）


class BaseTask(ABC):
    """
    遊戲任務基底類別

    繼承後實作 execute() 方法即可
    提供截圖、比對、點擊等常用快捷方法

    使用範例:
        class DailyQuest(BaseTask):
            name = "每日任務"
            priority = TaskPriority.NORMAL

            def precondition(self) -> bool:
                return self.is_scene("main_menu")

            def execute(self):
                self.tap_template("daily_btn.png")
                self.wait(2)
                if self.find("reward_icon.png"):
                    self.tap_template("claim_btn.png")
    """

    name: str = "BaseTask"
    max_retries: int = 3
    priority: TaskPriority = TaskPriority.NORMAL
    tags: list[str] = []  # 分類標籤
    estimated_duration: float = 0.0  # 預估耗時（秒）

    def __init__(
        self,
        adb: AdbController,
        matcher: ScreenMatcher,
        input_sim: InputSimulator,
        ocr: OcrReader | None = None,
        anti_detect: AntiDetect | None = None,
        scene_detector: SceneDetector | None = None,
    ):
        self.adb = adb
        self.matcher = matcher
        self.input = input_sim
        self.ocr = ocr
        self.anti_detect = anti_detect
        self.scene_detector = scene_detector
        self.state = TaskState.IDLE
        self._retry_count = 0
        self._start_time: float = 0
        self._interrupt_handlers: list[tuple[str, callable, callable]] = []

    # ── 生命週期 ──────────────────────────────────────────

    def run(self) -> bool:
        """執行任務（帶重試和中斷處理）"""
        # 前置條件檢查
        if not self.precondition():
            logger.warning(f"⚠️ 前置條件不滿足: {self.name}")
            return False

        logger.info(f"▶️ 開始任務: {self.name} (priority={self.priority.name})")
        self.state = TaskState.RUNNING
        self._start_time = time.time()

        while self._retry_count < self.max_retries:
            try:
                self.execute()
                self.state = TaskState.COMPLETED
                elapsed = time.time() - self._start_time
                logger.info(f"✅ 任務完成: {self.name} ({elapsed:.1f}s)")
                return True
            except InterruptedError as e:
                self.state = TaskState.INTERRUPTED
                logger.warning(f"⚡ 任務中斷: {self.name} - {e}")
                if not self._handle_interrupt(str(e)):
                    return False
                # 中斷處理後重試
                self.state = TaskState.RUNNING
                self._retry_count += 1
            except Exception as e:
                self._retry_count += 1
                logger.error(f"❌ 任務失敗 ({self._retry_count}/{self.max_retries}): {e}")
                if self._retry_count < self.max_retries:
                    logger.info("🔄 重試中...")
                    self.on_retry()
                    time.sleep(2)

        self.state = TaskState.FAILED
        logger.error(f"💀 任務最終失敗: {self.name}")
        return False

    @abstractmethod
    def execute(self) -> None:
        """實際任務邏輯，子類別必須實作"""
        ...

    def precondition(self) -> bool:
        """
        前置條件檢查

        覆寫此方法以檢查是否滿足執行條件
        例如：是否在正確的場景、資源是否足夠等
        """
        return True

    def on_retry(self) -> None:
        """重試前的清理動作，可覆寫"""
        pass

    # ── 中斷處理 ──────────────────────────────────────────

    def register_interrupt(
        self,
        name: str,
        detector: callable,
        handler: callable,
    ) -> None:
        """
        註冊中斷處理器

        Args:
            name: 中斷名稱
            detector: 偵測函式，回傳 True 表示觸發
            handler: 處理函式
        """
        self._interrupt_handlers.append((name, detector, handler))

    def check_interrupts(self) -> None:
        """
        檢查所有中斷（在 execute 中適時呼叫）

        如果偵測到中斷，會 raise InterruptedError
        """
        for name, detector, handler in self._interrupt_handlers:
            try:
                if detector():
                    logger.warning(f"⚡ 偵測到中斷: {name}")
                    raise InterruptedError(name)
            except InterruptedError:
                raise
            except Exception as e:
                logger.debug(f"中斷偵測錯誤 [{name}]: {e}")

    def _handle_interrupt(self, interrupt_name: str) -> bool:
        """
        處理中斷

        Returns:
            True = 已處理，可以重試
            False = 無法處理
        """
        for name, _, handler in self._interrupt_handlers:
            if name == interrupt_name:
                try:
                    handler()
                    logger.info(f"✅ 中斷 [{name}] 已處理")
                    return True
                except Exception as e:
                    logger.error(f"中斷處理失敗 [{name}]: {e}")
                    return False

        logger.warning(f"⚠️ 沒有對應的中斷處理器: {interrupt_name}")
        return False

    # ── 快捷方法 ──────────────────────────────────────────

    def screenshot(self):
        """截圖"""
        return self.adb.screenshot()

    def find(self, template_name: str, threshold: float | None = None):
        """截圖並尋找模板"""
        screen = self.screenshot()
        return self.matcher.find(screen, template_name, threshold)

    def exists(self, template_name: str, threshold: float | None = None) -> bool:
        """檢查模板是否存在"""
        screen = self.screenshot()
        return self.matcher.exists(screen, template_name, threshold)

    def wait_for(self, template_name: str, timeout: float = 10.0, interval: float = 0.5):
        """等待模板出現"""
        return self.matcher.wait_for(
            self.adb.screenshot,
            template_name,
            timeout=timeout,
            interval=interval,
        )

    def wait_gone(self, template_name: str, timeout: float = 10.0, interval: float = 0.5) -> bool:
        """等待模板消失"""
        return self.matcher.wait_until_gone(
            self.adb.screenshot,
            template_name,
            timeout=timeout,
            interval=interval,
        )

    def tap_template(self, template_name: str, threshold: float | None = None, timeout: float = 5.0) -> bool:
        """找到模板就點擊"""
        match = self.wait_for(template_name, timeout=timeout)
        if match:
            self.input.tap_match(match)
            # 防偵測
            if self.anti_detect:
                self.anti_detect.after_action(self.input)
            return True
        logger.warning(f"⚠️ 找不到 [{template_name}] 無法點擊")
        return False

    def tap(self, x: int, y: int) -> None:
        """點擊座標"""
        self.input.tap(x, y)
        if self.anti_detect:
            self.anti_detect.after_action(self.input)

    def wait(self, seconds: float = 1.0) -> None:
        """等待（帶防偵測）"""
        if self.anti_detect:
            self.anti_detect.wait(seconds * 0.8, seconds * 1.3)
        else:
            self.input.wait(seconds)

    def read_text(self, x: int = 0, y: int = 0, w: int = 0, h: int = 0) -> list:
        """OCR 辨識文字，可指定區域"""
        if not self.ocr:
            raise RuntimeError("OCR 未初始化")
        screen = self.screenshot()
        if w and h:
            return self.ocr.read_region(screen, x, y, w, h)
        return self.ocr.read(screen)

    def find_text(self, target: str, fuzzy: bool = False):
        """尋找特定文字"""
        if not self.ocr:
            raise RuntimeError("OCR 未初始化")
        screen = self.screenshot()
        return self.ocr.find_text(screen, target, fuzzy=fuzzy)

    def is_scene(self, scene_name: str) -> bool:
        """判斷是否在指定場景"""
        if not self.scene_detector:
            raise RuntimeError("場景偵測器未初始化")
        screen = self.screenshot()
        return self.scene_detector.is_scene(screen, scene_name)

    def current_scene(self) -> str | None:
        """取得當前場景名稱"""
        if not self.scene_detector:
            return None
        screen = self.screenshot()
        return self.scene_detector.detect_name(screen)


class TaskChain:
    """
    任務鏈 — 依序執行多個任務

    使用:
        chain = TaskChain([LoginTask(...), DailyQuestTask(...), ArenaBattleTask(...)])
        chain.run()
    """

    def __init__(self, tasks: list[BaseTask], stop_on_fail: bool = True):
        self.tasks = tasks
        self.stop_on_fail = stop_on_fail
        self._results: list[tuple[str, bool]] = []

    def run(self) -> bool:
        """依序執行所有任務"""
        logger.info(f"📋 開始任務鏈 ({len(self.tasks)} 個任務)")
        all_ok = True

        for task in self.tasks:
            success = task.run()
            self._results.append((task.name, success))

            if not success:
                all_ok = False
                if self.stop_on_fail:
                    logger.error(f"❌ 任務鏈中斷: {task.name} 失敗")
                    break

        success_count = sum(1 for _, ok in self._results if ok)
        logger.info(
            f"📋 任務鏈完成: {success_count}/{len(self._results)} 成功"
        )
        return all_ok

    @property
    def results(self) -> list[tuple[str, bool]]:
        return self._results

