"""有限狀態機引擎 — 事件驅動的遊戲流程控制

使用方式:
    fsm = GameFSM()

    fsm.add_state("idle", on_enter=..., on_update=..., on_exit=...)
    fsm.add_state("battle", on_enter=..., on_update=..., on_exit=...)

    fsm.add_transition("idle", "battle", condition=lambda: scene == "battle")
    fsm.add_transition("battle", "idle", condition=lambda: scene == "idle")

    fsm.start("idle")
    while True:
        fsm.tick()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from loguru import logger


@dataclass
class State:
    """FSM 狀態"""

    name: str
    on_enter: Callable[[], None] | None = None
    on_update: Callable[[], None] | None = None
    on_exit: Callable[[], None] | None = None
    data: dict = field(default_factory=dict)  # 狀態私有數據


@dataclass
class Transition:
    """FSM 狀態轉換"""

    from_state: str
    to_state: str
    condition: Callable[[], bool]
    priority: int = 0  # 數字越大優先級越高
    cooldown: float = 0.0  # 轉換冷卻（秒）
    _last_triggered: float = 0.0


class GameFSM:
    """有限狀態機引擎"""

    def __init__(self, name: str = "GameFSM"):
        self.name = name
        self._states: dict[str, State] = {}
        self._transitions: list[Transition] = []
        self._current_state: State | None = None
        self._previous_state: str | None = None
        self._running = False
        self._tick_count = 0
        self._state_enter_time = 0.0

        # 全局 transitions（任何狀態都能觸發）
        self._global_transitions: list[Transition] = []

    @property
    def current_state_name(self) -> str | None:
        return self._current_state.name if self._current_state else None

    @property
    def previous_state_name(self) -> str | None:
        return self._previous_state

    @property
    def state_duration(self) -> float:
        """目前狀態持續時間"""
        if self._state_enter_time == 0:
            return 0.0
        return time.time() - self._state_enter_time

    @property
    def tick_count(self) -> int:
        return self._tick_count

    # ── 建構 ──────────────────────────────────────────────

    def add_state(
        self,
        name: str,
        on_enter: Callable[[], None] | None = None,
        on_update: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> State:
        """新增狀態"""
        state = State(name=name, on_enter=on_enter, on_update=on_update, on_exit=on_exit)
        self._states[name] = state
        return state

    def add_transition(
        self,
        from_state: str,
        to_state: str,
        condition: Callable[[], bool],
        priority: int = 0,
        cooldown: float = 0.0,
    ) -> Transition:
        """新增狀態轉換"""
        transition = Transition(
            from_state=from_state,
            to_state=to_state,
            condition=condition,
            priority=priority,
            cooldown=cooldown,
        )
        self._transitions.append(transition)
        # 按優先級排序（高優先先檢查）
        self._transitions.sort(key=lambda t: t.priority, reverse=True)
        return transition

    def add_global_transition(
        self,
        to_state: str,
        condition: Callable[[], bool],
        priority: int = 100,
        cooldown: float = 0.0,
    ) -> Transition:
        """
        新增全局轉換（任何狀態都能觸發）

        常用於：彈窗處理、斷線重連
        """
        transition = Transition(
            from_state="*",
            to_state=to_state,
            condition=condition,
            priority=priority,
            cooldown=cooldown,
        )
        self._global_transitions.append(transition)
        self._global_transitions.sort(key=lambda t: t.priority, reverse=True)
        return transition

    # ── 執行 ──────────────────────────────────────────────

    def start(self, initial_state: str) -> None:
        """啟動 FSM"""
        if initial_state not in self._states:
            raise ValueError(f"狀態不存在: {initial_state}")

        self._running = True
        self._tick_count = 0
        self._change_state(initial_state)
        logger.info(f"🚀 {self.name} 啟動: {initial_state}")

    def stop(self) -> None:
        """停止 FSM"""
        self._running = False
        if self._current_state and self._current_state.on_exit:
            try:
                self._current_state.on_exit()
            except Exception as e:
                logger.error(f"on_exit 錯誤: {e}")
        logger.info(f"⏹️ {self.name} 停止 (tick #{self._tick_count})")

    def tick(self) -> str | None:
        """
        每幀呼叫：檢查轉換條件 → 執行當前狀態

        Returns:
            轉換到的新狀態名稱，或 None（未轉換）
        """
        if not self._running or not self._current_state:
            return None

        self._tick_count += 1
        now = time.time()

        # 1. 檢查全局轉換（優先）
        for t in self._global_transitions:
            if self._current_state.name == t.to_state:
                continue  # 不轉換到自己
            if now - t._last_triggered < t.cooldown:
                continue
            try:
                if t.condition():
                    t._last_triggered = now
                    old = self._current_state.name
                    self._change_state(t.to_state)
                    logger.info(f"🔄 全局轉換: {old} → {t.to_state}")
                    return t.to_state
            except Exception as e:
                logger.error(f"全局轉換條件錯誤: {e}")

        # 2. 檢查狀態轉換
        for t in self._transitions:
            if t.from_state != self._current_state.name:
                continue
            if now - t._last_triggered < t.cooldown:
                continue
            try:
                if t.condition():
                    t._last_triggered = now
                    old = self._current_state.name
                    self._change_state(t.to_state)
                    logger.debug(f"🔄 狀態轉換: {old} → {t.to_state}")
                    return t.to_state
            except Exception as e:
                logger.error(f"轉換條件錯誤: {e}")

        # 3. 執行當前狀態
        if self._current_state.on_update:
            try:
                self._current_state.on_update()
            except Exception as e:
                logger.error(f"狀態 [{self._current_state.name}] update 錯誤: {e}")

        return None

    def force_state(self, state_name: str) -> None:
        """強制切換狀態（忽略轉換條件）"""
        if state_name not in self._states:
            raise ValueError(f"狀態不存在: {state_name}")
        old = self._current_state.name if self._current_state else None
        self._change_state(state_name)
        logger.info(f"⚡ 強制切換: {old} → {state_name}")

    def _change_state(self, new_state_name: str) -> None:
        """內部狀態切換"""
        if self._current_state:
            self._previous_state = self._current_state.name
            if self._current_state.on_exit:
                try:
                    self._current_state.on_exit()
                except Exception as e:
                    logger.error(f"on_exit [{self._current_state.name}] 錯誤: {e}")

        self._current_state = self._states[new_state_name]
        self._state_enter_time = time.time()

        if self._current_state.on_enter:
            try:
                self._current_state.on_enter()
            except Exception as e:
                logger.error(f"on_enter [{new_state_name}] 錯誤: {e}")

    # ── 查詢 ──────────────────────────────────────────────

    def get_state_data(self, state_name: str | None = None) -> dict:
        """取得狀態的私有數據"""
        name = state_name or (self._current_state.name if self._current_state else None)
        if name and name in self._states:
            return self._states[name].data
        return {}

    def set_state_data(self, key: str, value, state_name: str | None = None) -> None:
        """設定狀態的私有數據"""
        name = state_name or (self._current_state.name if self._current_state else None)
        if name and name in self._states:
            self._states[name].data[key] = value

    def state_info(self) -> dict:
        """目前 FSM 狀態資訊"""
        return {
            "current": self.current_state_name,
            "previous": self.previous_state_name,
            "duration": round(self.state_duration, 1),
            "tick": self._tick_count,
            "running": self._running,
        }

    def __repr__(self) -> str:
        states = ", ".join(self._states.keys())
        return f"GameFSM({self.name}, states=[{states}], current={self.current_state_name})"
