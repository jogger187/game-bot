"""防偵測策略 — 讓自動化操作更難被遊戲偵測

策略:
1. 隨機 AFK（模擬看手機/分心）
2. 疲勞模擬（操作速度隨時間遞減）
3. 無意義操作（偶爾滑一下又滑回來）
4. 非均勻延遲分佈（Gaussian / Poisson）
5. 操作時段模擬（凌晨操作頻率低）
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from enum import Enum, auto

from loguru import logger


class DelayDistribution(Enum):
    """延遲分佈類型"""
    UNIFORM = auto()
    GAUSSIAN = auto()
    POISSON = auto()


@dataclass
class AntiDetectConfig:
    """防偵測設定"""

    # AFK 模擬
    afk_chance: float = 0.05  # 每次操作後 AFK 的機率
    afk_duration: tuple[float, float] = (2.0, 8.0)  # AFK 持續時間範圍

    # 疲勞模擬
    fatigue_enabled: bool = True
    fatigue_base_multiplier: float = 1.0  # 初始速度倍率
    fatigue_growth_per_minute: float = 0.02  # 每分鐘增加的延遲倍率
    fatigue_max_multiplier: float = 2.0  # 最大延遲倍率

    # 無意義操作
    fake_action_chance: float = 0.03  # 每次操作後做假動作的機率
    fake_actions: bool = True

    # 延遲分佈
    delay_distribution: DelayDistribution = DelayDistribution.GAUSSIAN

    # 操作時段
    time_aware: bool = False  # 根據時段調整操作速度


class AntiDetect:
    """防偵測管理器"""

    def __init__(self, config: AntiDetectConfig | None = None):
        self.config = config or AntiDetectConfig()
        self._start_time = time.time()
        self._operation_count = 0
        self._total_afk_time = 0.0

    @property
    def elapsed_minutes(self) -> float:
        """運行了多少分鐘"""
        return (time.time() - self._start_time) / 60.0

    @property
    def fatigue_multiplier(self) -> float:
        """目前的疲勞倍率"""
        if not self.config.fatigue_enabled:
            return 1.0
        mult = (
            self.config.fatigue_base_multiplier
            + self.elapsed_minutes * self.config.fatigue_growth_per_minute
        )
        return min(mult, self.config.fatigue_max_multiplier)

    # ── 延遲生成 ──────────────────────────────────────────

    def random_delay(
        self,
        base_min: float = 0.5,
        base_max: float = 1.5,
    ) -> float:
        """
        產生隨機延遲（考慮疲勞和分佈）

        Returns:
            延遲秒數
        """
        dist = self.config.delay_distribution
        fatigue = self.fatigue_multiplier

        if dist == DelayDistribution.GAUSSIAN:
            mean = (base_min + base_max) / 2.0
            std = (base_max - base_min) / 4.0
            delay = max(base_min * 0.5, random.gauss(mean, std))
        elif dist == DelayDistribution.POISSON:
            lam = (base_min + base_max) / 2.0
            delay = random.expovariate(1.0 / lam)
            delay = max(base_min * 0.5, min(delay, base_max * 3))
        else:  # UNIFORM
            delay = random.uniform(base_min, base_max)

        # 套用疲勞
        delay *= fatigue

        # 時段感知
        if self.config.time_aware:
            delay *= self._time_factor()

        return delay

    def wait(self, base_min: float = 0.5, base_max: float = 1.5) -> None:
        """帶防偵測的等待"""
        delay = self.random_delay(base_min, base_max)
        time.sleep(delay)

    # ── 操作攔截 ──────────────────────────────────────────

    def before_action(self) -> None:
        """
        每次操作前呼叫

        可能觸發:
        1. AFK 休息
        2. 無意義操作（回傳 True 表示已插入假動作）
        """
        self._operation_count += 1

        # AFK 模擬
        if random.random() < self.config.afk_chance:
            self._do_afk()

    def after_action(self, input_sim=None) -> None:
        """
        每次操作後呼叫

        可能插入假動作
        """
        if (
            self.config.fake_actions
            and input_sim is not None
            and random.random() < self.config.fake_action_chance
        ):
            self._do_fake_action(input_sim)

    # ── 內部方法 ──────────────────────────────────────────

    def _do_afk(self) -> None:
        """模擬 AFK"""
        duration = random.uniform(*self.config.afk_duration)
        self._total_afk_time += duration
        logger.info(f"😴 AFK {duration:.1f}s (第 {self._operation_count} 次操作後)")
        time.sleep(duration)

    def _do_fake_action(self, input_sim) -> None:
        """執行無意義的假動作"""
        action = random.choice(["tiny_swipe", "hesitate", "micro_scroll"])

        if action == "tiny_swipe":
            # 微小的來回滑動
            try:
                w, h = input_sim.adb.screen_size
                cx = random.randint(w // 4, w * 3 // 4)
                cy = random.randint(h // 4, h * 3 // 4)
                dx = random.randint(-30, 30)
                dy = random.randint(-30, 30)
                input_sim.adb.swipe(cx, cy, cx + dx, cy + dy, 200)
                time.sleep(random.uniform(0.1, 0.3))
                input_sim.adb.swipe(cx + dx, cy + dy, cx, cy, 200)
                logger.debug("🎭 假動作: 微小來回滑動")
            except Exception:
                pass

        elif action == "hesitate":
            # 停頓一下（模擬猶豫）
            duration = random.uniform(0.3, 1.0)
            logger.debug(f"🎭 假動作: 猶豫 {duration:.1f}s")
            time.sleep(duration)

        elif action == "micro_scroll":
            # 微小的捲動
            try:
                w, h = input_sim.adb.screen_size
                cx = w // 2
                cy = h // 2
                dy = random.choice([-50, 50])
                input_sim.adb.swipe(cx, cy, cx, cy + dy, 150)
                logger.debug("🎭 假動作: 微捲動")
            except Exception:
                pass

    def _time_factor(self) -> float:
        """根據時段調整速度"""
        import datetime
        hour = datetime.datetime.now().hour

        if 0 <= hour < 6:
            # 凌晨：很慢（不太正常在玩）
            return random.uniform(1.5, 2.5)
        elif 6 <= hour < 9:
            # 早上：稍慢
            return random.uniform(1.0, 1.5)
        elif 9 <= hour < 12:
            # 上午：正常
            return random.uniform(0.9, 1.1)
        elif 12 <= hour < 14:
            # 午休：正常偏快
            return random.uniform(0.8, 1.0)
        elif 14 <= hour < 18:
            # 下午：正常
            return random.uniform(0.9, 1.1)
        elif 18 <= hour < 22:
            # 晚上：正常偏快（黃金時段）
            return random.uniform(0.8, 1.0)
        else:
            # 深夜：稍慢
            return random.uniform(1.2, 1.8)

    # ── 報告 ──────────────────────────────────────────────

    def report(self) -> dict:
        """輸出統計報告"""
        return {
            "elapsed_minutes": round(self.elapsed_minutes, 1),
            "operation_count": self._operation_count,
            "total_afk_time": round(self._total_afk_time, 1),
            "fatigue_multiplier": round(self.fatigue_multiplier, 2),
        }

    def reset(self) -> None:
        """重置計時器（例如切換任務時）"""
        self._start_time = time.time()
        self._operation_count = 0
        self._total_afk_time = 0.0
        logger.debug("🔄 防偵測計時器已重置")
