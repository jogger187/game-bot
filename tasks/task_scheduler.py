"""任務排程器 — 管理多任務優先級和時間觸發

支援:
- Cron-like 排程
- 固定間隔排程
- 優先級佇列
- 中斷處理（彈窗偵測 → 暫停當前 → 處理 → 恢復）

使用方式:
    scheduler = TaskScheduler(adb, matcher, input_sim, ocr)
    scheduler.add_task(DailyQuestTask, cron="0 8 * * *")
    scheduler.add_task(ArenaBattleTask, interval=7200)
    scheduler.run_forever()
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Type

from loguru import logger

from .base_task import BaseTask, TaskPriority


@dataclass
class ScheduledTask:
    """排程任務項目"""

    task_class: Type[BaseTask]
    task_kwargs: dict = field(default_factory=dict)

    # 排程設定
    cron: str | None = None  # cron 表達式
    interval: float | None = None  # 間隔秒數
    run_once: bool = False  # 只執行一次

    # 狀態
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    fail_count: int = 0
    enabled: bool = True

    @property
    def name(self) -> str:
        return self.task_class.name

    @property
    def priority(self) -> TaskPriority:
        return self.task_class.priority


class TaskScheduler:
    """任務排程管理器"""

    def __init__(
        self,
        adb,
        matcher,
        input_sim,
        ocr=None,
        anti_detect=None,
        scene_detector=None,
    ):
        self.adb = adb
        self.matcher = matcher
        self.input_sim = input_sim
        self.ocr = ocr
        self.anti_detect = anti_detect
        self.scene_detector = scene_detector

        self._scheduled_tasks: list[ScheduledTask] = []
        self._running = False
        self._current_task: BaseTask | None = None
        self._lock = threading.Lock()

    def add_task(
        self,
        task_class: Type[BaseTask],
        cron: str | None = None,
        interval: float | None = None,
        run_once: bool = False,
        delay: float = 0.0,
        **kwargs,
    ) -> ScheduledTask:
        """
        新增排程任務

        Args:
            task_class: 任務類別
            cron: Cron 表達式 (簡化版: "分 時 * * *")
            interval: 執行間隔（秒）
            run_once: 只執行一次
            delay: 首次執行延遲（秒）
            **kwargs: 傳給任務建構式的額外參數
        """
        scheduled = ScheduledTask(
            task_class=task_class,
            task_kwargs=kwargs,
            cron=cron,
            interval=interval,
            run_once=run_once,
            next_run=time.time() + delay,
        )
        self._scheduled_tasks.append(scheduled)
        logger.info(
            f"📅 排程已加入: {task_class.name} "
            f"(interval={interval}s, cron={cron})"
        )
        return scheduled

    def remove_task(self, task_name: str) -> bool:
        """移除排程任務"""
        for i, st in enumerate(self._scheduled_tasks):
            if st.name == task_name:
                self._scheduled_tasks.pop(i)
                logger.info(f"🗑️ 排程已移除: {task_name}")
                return True
        return False

    # ── 執行 ──────────────────────────────────────────────

    def run_forever(self, tick_interval: float = 1.0) -> None:
        """
        主迴圈：持續檢查並執行排程任務

        Args:
            tick_interval: 檢查間隔（秒）
        """
        self._running = True
        logger.info(f"🚀 排程器啟動 ({len(self._scheduled_tasks)} 個任務)")

        try:
            while self._running:
                self._tick()
                time.sleep(tick_interval)
        except KeyboardInterrupt:
            logger.info("⏹️ 收到中斷信號，排程器停止")
        finally:
            self._running = False
            logger.info("⏹️ 排程器已停止")

    def stop(self) -> None:
        self._running = False

    def run_once(self) -> None:
        """執行一輪（非持續）"""
        self._tick()

    def _tick(self) -> None:
        """每個 tick 檢查哪些任務該執行"""
        now = time.time()
        pending: list[ScheduledTask] = []

        for st in self._scheduled_tasks:
            if not st.enabled:
                continue

            if st.run_once and st.run_count > 0:
                continue

            should_run = False

            if st.interval and now >= st.next_run:
                should_run = True
            elif st.cron and self._cron_matches(st.cron, now) and now - st.last_run > 60:
                should_run = True
            elif st.next_run > 0 and now >= st.next_run and st.run_count == 0:
                should_run = True

            if should_run:
                pending.append(st)

        # 按優先級排序
        pending.sort(key=lambda s: s.priority.value, reverse=True)

        for st in pending:
            self._execute_scheduled(st)

    def _execute_scheduled(self, scheduled: ScheduledTask) -> None:
        """執行排程任務"""
        task = scheduled.task_class(
            adb=self.adb,
            matcher=self.matcher,
            input_sim=self.input_sim,
            ocr=self.ocr,
            anti_detect=self.anti_detect,
            scene_detector=self.scene_detector,
            **scheduled.task_kwargs,
        )

        with self._lock:
            self._current_task = task

        success = task.run()

        with self._lock:
            self._current_task = None

        scheduled.last_run = time.time()
        scheduled.run_count += 1
        if not success:
            scheduled.fail_count += 1

        # 計算下次執行
        if scheduled.interval:
            scheduled.next_run = time.time() + scheduled.interval

    # ── Cron 解析 ─────────────────────────────────────────

    @staticmethod
    def _cron_matches(cron: str, timestamp: float) -> bool:
        """
        簡化版 cron 比對

        格式: "分 時 日 月 週幾"
        支援: * (任意), 數字, 逗號分隔
        """
        import datetime
        dt = datetime.datetime.fromtimestamp(timestamp)

        parts = cron.split()
        if len(parts) < 5:
            parts += ["*"] * (5 - len(parts))

        checks = [
            (parts[0], dt.minute),
            (parts[1], dt.hour),
            (parts[2], dt.day),
            (parts[3], dt.month),
            (parts[4], dt.weekday()),  # 0=Monday
        ]

        for pattern, value in checks:
            if pattern == "*":
                continue
            # 逗號分隔
            allowed = set()
            for p in pattern.split(","):
                p = p.strip()
                if "-" in p:
                    start, end = p.split("-")
                    allowed.update(range(int(start), int(end) + 1))
                elif "/" in p:
                    # */5 = 每 5 分鐘
                    step = int(p.split("/")[1])
                    allowed.update(range(0, 60, step))
                else:
                    allowed.add(int(p))

            if value not in allowed:
                return False

        return True

    # ── 查詢 ──────────────────────────────────────────────

    def status(self) -> list[dict]:
        """取得所有排程任務狀態"""
        return [
            {
                "name": st.name,
                "priority": st.priority.name,
                "enabled": st.enabled,
                "run_count": st.run_count,
                "fail_count": st.fail_count,
                "last_run": st.last_run,
                "next_run": st.next_run,
            }
            for st in self._scheduled_tasks
        ]
