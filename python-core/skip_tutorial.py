#!/usr/bin/env python3
"""
自動跳過新手教學腳本
策略：
1. 持續截圖
2. 找到 "Skip" 按鈕就點擊
3. 找到教學手指提示就點擊指示位置
4. 找到對話框就點擊繼續
5. 沒有特殊按鈕就點擊畫面中央推進教學
"""
import subprocess
import time
import sys
import io

# 嘗試載入 OpenCV / numpy（用於圖片分析）
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("⚠️ 無 OpenCV，使用純座標模式")

SERIAL = "emulator-5554"
SCREEN_W, SCREEN_H = 1440, 2560

def adb(cmd: str) -> str:
    """執行 ADB 命令"""
    result = subprocess.run(
        f"adb -s {SERIAL} {cmd}",
        shell=True, capture_output=True, timeout=10
    )
    return result.stdout.decode('utf-8', errors='ignore')

def tap(x: int, y: int, desc: str = ""):
    """點擊座標"""
    print(f"  👆 Tap ({x}, {y}) {desc}")
    adb(f"shell input tap {x} {y}")

def screenshot() -> bytes:
    """擷取螢幕截圖（raw PNG bytes）"""
    result = subprocess.run(
        f"adb -s {SERIAL} exec-out screencap -p",
        shell=True, capture_output=True, timeout=10
    )
    return result.stdout

def screenshot_cv():
    """擷取截圖並轉為 OpenCV 格式"""
    png_data = screenshot()
    if not png_data:
        return None
    arr = np.frombuffer(png_data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def find_skip_button(img) -> tuple:
    """
    在截圖中搜尋 "Skip" 按鈕
    Skip 按鈕特徵：右上角、白色文字、深色圓角背景
    搜尋區域：右上角 1/4
    """
    if img is None:
        return None
    h, w = img.shape[:2]

    # 搜尋右上角區域
    roi = img[0:h//4, w//2:w]

    # 轉灰階
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 找亮色區域（Skip 文字通常是白色）
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    # 找輪廓
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 500 < area < 50000:  # Skip 按鈕大小範圍
            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / max(ch, 1)
            if 1.5 < aspect < 6:  # Skip 按鈕是橫向的
                # 轉回全圖座標
                cx = x + cw // 2 + w // 2
                cy = y + ch // 2
                return (cx, cy)

    return None

def find_dialog_arrow(img) -> tuple:
    """
    找對話框的 ▼ 箭頭（通常在畫面下方 1/3）
    """
    if img is None:
        return None
    h, w = img.shape[:2]

    # 對話框通常在下方 1/3
    roi = img[h*2//3:h, w//4:w*3//4]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 找淺色大塊（對話框背景）
    _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
    white_ratio = np.sum(thresh > 0) / thresh.size

    if white_ratio > 0.15:  # 有大片白色 → 可能是對話框
        # 點擊對話框中央
        cx = w // 2
        cy = h * 5 // 6
        return (cx, cy)

    return None

def find_glowing_circle(img) -> tuple:
    """
    找教學指示的綠色/黃色發光圓圈
    """
    if img is None:
        return None
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 搜尋綠色/黃綠色光圈
    lower_green = np.array([30, 80, 80])
    upper_green = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)

    # 形態學處理
    kernel = np.ones((15, 15), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 5000 and area > best_area:  # 要有一定大小
            best = cnt
            best_area = area

    if best is not None:
        M = cv2.moments(best)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            return (cx, cy)

    return None

def run_tutorial_skip(max_steps: int = 60, interval: float = 2.0):
    """
    主迴圈：持續分析畫面並自動點擊跳過教學
    """
    print("=" * 50)
    print("🎮 自動跳過新手教學")
    print(f"   裝置: {SERIAL}")
    print(f"   最大步驟: {max_steps}")
    print(f"   間隔: {interval}s")
    print("=" * 50)

    for step in range(1, max_steps + 1):
        print(f"\n📷 Step {step}/{max_steps} — 截圖分析中...")

        if HAS_CV2:
            img = screenshot_cv()
            if img is None:
                print("  ❌ 截圖失敗，重試...")
                time.sleep(interval)
                continue

            # 優先序：Skip > 對話框 > 發光圈 > 中央點擊
            skip_pos = find_skip_button(img)
            if skip_pos:
                tap(skip_pos[0], skip_pos[1], "⏭ Skip 按鈕")
                time.sleep(interval)
                continue

            dialog_pos = find_dialog_arrow(img)
            if dialog_pos:
                tap(dialog_pos[0], dialog_pos[1], "💬 對話框")
                time.sleep(interval)
                continue

            glow_pos = find_glowing_circle(img)
            if glow_pos:
                tap(glow_pos[0], glow_pos[1], "✨ 指示圓圈")
                time.sleep(interval)
                continue

            # 沒找到特殊元素 → 點擊畫面中央推進
            tap(SCREEN_W // 2, SCREEN_H // 2, "🖱 中央點擊")
        else:
            # 無 OpenCV → 簡單策略
            # 先嘗試點 Skip 位置（右上角）
            tap(1260, 210, "⏭ Skip 位置")
            time.sleep(0.5)
            # 再點擊中央
            tap(SCREEN_W // 2, SCREEN_H // 2, "🖱 中央推進")

        time.sleep(interval)

    print("\n✅ 教學跳過流程結束")

if __name__ == "__main__":
    steps = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    run_tutorial_skip(max_steps=steps, interval=interval)
