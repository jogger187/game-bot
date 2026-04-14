import time
from typing import List, Dict, Any
from loguru import logger
from .base_task import BaseTask, TaskPriority

class DynamicTask(BaseTask):
    """
    動態腳本執行器。
    透過讀取 JSON 格式的規則來決定它的執行邏輯，實現「無程式碼」外掛引擎。
    """
    
    def __init__(self, adb, matcher, input_sim, script_id: str, script_name: str, rules: List[Dict[str, Any]], ocr=None, **kwargs):
        super().__init__(adb, matcher, input_sim, ocr, **kwargs)
        self.script_id = script_id
        self._name = script_name
        self.rules = rules
        self.priority = TaskPriority.NORMAL

    @property
    def name(self) -> str:
        return self._name

    def execute(self) -> bool:
        """
        遍歷規則並依序執行。只要其中一條規則被觸發（例如條件成立），
        就立刻回傳 True 表示需要繼續檢查。如果所有規則都不成立，回傳 False 代表畫面無變化或任務做完。
        """
        # 截取當下畫面供所有檢查使用，避免重複擷取浪費時間
        try:
            screen = self.screenshot()
        except Exception as e:
            logger.error(f"[{self.name}] 截圖失敗: {e}")
            return False

        action_taken = False

        for rule in self.rules:
            condition = rule.get("condition", {})
            action = rule.get("action", {})

            # --- 判斷條件 ---
            is_match = False
            match_result = None

            cond_type = condition.get("type")
            if cond_type == "image_match":
                target_img = condition.get("target") # e.g. "skip_btn.png"
                threshold = condition.get("threshold", 0.8)
                if not target_img:
                    continue
                
                match_result = self.matcher.find(screen, target_img, threshold=threshold)
                if match_result:
                    is_match = True
            
            elif cond_type == "always_true":
                is_match = True
                
            # (未來可擴充字串辨識 OCR condition 等)
            
            if not is_match:
                continue

            # --- 執行對應的動作 ---
            action_type = action.get("type")
            
            if action_type == "click_match":
                if match_result:
                    logger.info(f"[{self.name}] 🎯 觸發規則: 點擊圖片 {condition.get('target')}")
                    self.input.tap_match(match_result)
                    
            elif action_type == "click_coord":
                x = action.get("x", 0)
                y = action.get("y", 0)
                logger.info(f"[{self.name}] 🎯 觸發規則: 點擊座標 ({x}, {y})")
                self.input.tap(x, y)
                
            elif action_type == "wait":
                duration = action.get("duration", 1.0)
                logger.info(f"[{self.name}] ⏳ 觸發規則: 等待 {duration} 秒")
                # 這邊只是一個純粹強制等待的動作，通常不單獨使用
            
            else:
                logger.warning(f"[{self.name}] 未知的動作類型: {action_type}")

            # 執行完動作後，強制休眠一下避免連點太快
            post_delay = action.get("post_delay", 1.5)
            if post_delay > 0:
                self.wait(post_delay)

            action_taken = True
            # **策略**：只要觸發了一個動作，就中斷規則遍歷，讓外層排程器進到下一個循環（重新思考與截圖）。
            # 這樣能保證畫面狀態變更後，不會錯誤執行舊畫面下的規則。
            break 

        if not action_taken:
            logger.debug(f"[{self.name}] 💤 目前沒有任何符合的觸發規則")
            # 微小休眠避免迴圈過快
            self.wait(1.0)
            
        return action_taken
