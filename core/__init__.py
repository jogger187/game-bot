from .adb_controller import AdbController, ScreenCapMethod
from .screen_matcher import ScreenMatcher, MatchResult
from .ocr_reader import OcrReader, OcrResult, Grayscale, Threshold, Resize, Sharpen, Invert, Denoise
from .input_simulator import InputSimulator, Rhythm
from .feature_matcher import FeatureMatcher, FeatureMatchResult
from .pixel_analyzer import PixelAnalyzer, ColorRegion
from .scene_detector import SceneDetector, SceneConfig, SceneIndicator
from .text_parser import TextParser
from .minicap_stream import MiniCapStream
from .emulator_bridge import EmulatorBridge, EmulatorDetector, EmulatorType
from .state_machine import GameFSM
from .anti_detect import AntiDetect, AntiDetectConfig
from .touch_replayer import TouchRecorder, TouchReplayer, TouchRecording
from .stats_tracker import StatsTracker
from .debug_viewer import DebugViewer

__all__ = [
    # 核心
    "AdbController", "ScreenCapMethod",
    "ScreenMatcher", "MatchResult",
    "OcrReader", "OcrResult",
    "InputSimulator", "Rhythm",
    # 影像分析
    "FeatureMatcher", "FeatureMatchResult",
    "PixelAnalyzer", "ColorRegion",
    "SceneDetector", "SceneConfig", "SceneIndicator",
    "TextParser",
    # 預處理
    "Grayscale", "Threshold", "Resize", "Sharpen", "Invert", "Denoise",
    # 裝置
    "MiniCapStream",
    "EmulatorBridge", "EmulatorDetector", "EmulatorType",
    # 任務框架
    "GameFSM",
    "AntiDetect", "AntiDetectConfig",
    "TouchRecorder", "TouchReplayer", "TouchRecording",
    # 監控
    "StatsTracker",
    "DebugViewer",
]
