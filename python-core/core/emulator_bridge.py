"""模擬器橋接 — 偵測並直連各種 Android 模擬器

支援:
- MuMu (網易)
- LDPlayer (雷電)
- BlueStacks
- Nox (夜神)
- MEmu (逍遙)

使用方式:
    bridge = EmulatorBridge.auto_detect()
    bridge.connect()
    img = bridge.screenshot()
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum, auto

from loguru import logger

try:
    import psutil
except ImportError:
    psutil = None


class EmulatorType(Enum):
    MUMU = auto()
    LDPLAYER = auto()
    BLUESTACKS = auto()
    NOX = auto()
    MEMU = auto()
    UNKNOWN = auto()


@dataclass
class EmulatorInstance:
    """偵測到的模擬器實例"""

    type: EmulatorType
    name: str
    pid: int | None = None
    adb_port: int | None = None
    install_path: Path | None = None
    index: int = 0  # 多開索引
    extra: dict = field(default_factory=dict)

    @property
    def adb_serial(self) -> str | None:
        if self.adb_port:
            return f"127.0.0.1:{self.adb_port}"
        return None


class EmulatorDetector:
    """偵測系統上運行的模擬器"""

    # 模擬器進程名稱對照
    PROCESS_MAP: dict[str, EmulatorType] = {
        # MuMu
        "MuMuPlayer": EmulatorType.MUMU,
        "MuMuVMMHeadless": EmulatorType.MUMU,
        "NemuPlayer": EmulatorType.MUMU,
        "MuMuPlayer.exe": EmulatorType.MUMU,
        # LDPlayer
        "dnplayer": EmulatorType.LDPLAYER,
        "LdVBoxHeadless": EmulatorType.LDPLAYER,
        "dnplayer.exe": EmulatorType.LDPLAYER,
        # BlueStacks
        "HD-Player": EmulatorType.BLUESTACKS,
        "BlueStacks": EmulatorType.BLUESTACKS,
        "HD-Player.exe": EmulatorType.BLUESTACKS,
        # Nox
        "Nox": EmulatorType.NOX,
        "NoxVMHandle": EmulatorType.NOX,
        "Nox.exe": EmulatorType.NOX,
        # MEmu
        "MEmu": EmulatorType.MEMU,
        "MEmuHeadless": EmulatorType.MEMU,
        "MEmu.exe": EmulatorType.MEMU,
    }

    # 模擬器預設 ADB port
    DEFAULT_ADB_PORTS: dict[EmulatorType, list[int]] = {
        EmulatorType.MUMU: [7555, 16384, 16416],
        EmulatorType.LDPLAYER: [5555, 5557, 5559, 5561],
        EmulatorType.BLUESTACKS: [5555, 5565, 5575, 5585],
        EmulatorType.NOX: [62001, 62025, 62026],
        EmulatorType.MEMU: [21503, 21513, 21523],
    }

    @classmethod
    def detect_all(cls) -> list[EmulatorInstance]:
        """偵測所有運行中的模擬器"""
        if psutil is None:
            logger.warning("psutil 未安裝，無法偵測模擬器進程")
            return cls._detect_via_adb()

        instances: list[EmulatorInstance] = []
        seen_pids: set[int] = set()

        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                name = proc.info["name"] or ""
                matched_type = None

                for proc_name, emu_type in cls.PROCESS_MAP.items():
                    if proc_name.lower() in name.lower():
                        matched_type = emu_type
                        break

                if matched_type and proc.info["pid"] not in seen_pids:
                    pid = proc.info["pid"]
                    seen_pids.add(pid)

                    exe_path = proc.info.get("exe")
                    install_path = Path(exe_path).parent if exe_path else None

                    # 從命令列參數推斷多開索引
                    index = cls._parse_instance_index(
                        proc.info.get("cmdline", []), matched_type
                    )

                    # 推斷 ADB port
                    adb_port = cls._guess_adb_port(matched_type, index)

                    instances.append(
                        EmulatorInstance(
                            type=matched_type,
                            name=f"{matched_type.name}_{index}",
                            pid=pid,
                            adb_port=adb_port,
                            install_path=install_path,
                            index=index,
                        )
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if instances:
            logger.info(f"🔍 偵測到 {len(instances)} 個模擬器實例")
            for inst in instances:
                logger.info(
                    f"   {inst.name} (PID={inst.pid}, ADB={inst.adb_serial})"
                )
        else:
            logger.info("🔍 未偵測到模擬器進程，嘗試透過 ADB 偵測...")
            instances = cls._detect_via_adb()

        return instances

    @classmethod
    def _detect_via_adb(cls) -> list[EmulatorInstance]:
        """透過 adb devices 偵測"""
        try:
            result = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=5
            )
            instances = []
            for line in result.stdout.strip().split("\n")[1:]:
                line = line.strip()
                if not line or "offline" in line:
                    continue
                serial = line.split("\t")[0]

                # 猜測模擬器類型
                emu_type = EmulatorType.UNKNOWN
                port = None
                port_match = re.search(r":(\d+)", serial)
                if port_match:
                    port = int(port_match.group(1))
                    for t, ports in cls.DEFAULT_ADB_PORTS.items():
                        if port in ports:
                            emu_type = t
                            break

                instances.append(
                    EmulatorInstance(
                        type=emu_type,
                        name=serial,
                        adb_port=port,
                    )
                )
            return instances
        except Exception as e:
            logger.error(f"ADB 偵測失敗: {e}")
            return []

    @classmethod
    def _parse_instance_index(
        cls, cmdline: list[str], emu_type: EmulatorType
    ) -> int:
        """從命令列參數解析多開索引"""
        if not cmdline:
            return 0
        cmd_str = " ".join(cmdline)

        # LDPlayer: --index N
        match = re.search(r"--index\s+(\d+)", cmd_str)
        if match:
            return int(match.group(1))

        # MuMu: -v N
        match = re.search(r"-v\s+(\d+)", cmd_str)
        if match:
            return int(match.group(1))

        return 0

    @classmethod
    def _guess_adb_port(cls, emu_type: EmulatorType, index: int) -> int | None:
        """根據模擬器類型和索引推算 ADB port"""
        ports = cls.DEFAULT_ADB_PORTS.get(emu_type, [])
        if index < len(ports):
            return ports[index]
        if not ports:
            return None
        # 推算規則
        base = ports[0]
        step = ports[1] - ports[0] if len(ports) > 1 else 2
        return base + step * index


class BaseEmulatorBridge(ABC):
    """模擬器橋接基底類別"""

    def __init__(self, instance: EmulatorInstance):
        self.instance = instance

    @abstractmethod
    def connect(self) -> None:
        """連線到模擬器"""
        ...

    @abstractmethod
    def screenshot(self):
        """截取螢幕畫面 -> PIL Image"""
        ...

    @abstractmethod
    def tap(self, x: int, y: int) -> None:
        """點擊"""
        ...

    @abstractmethod
    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int
    ) -> None:
        """滑動"""
        ...

    def disconnect(self) -> None:
        """斷開連線"""
        pass


class AdbEmulatorBridge(BaseEmulatorBridge):
    """透過 ADB 連接模擬器的通用橋接（所有模擬器皆可用）"""

    def __init__(self, instance: EmulatorInstance):
        super().__init__(instance)
        self._serial = instance.adb_serial or instance.name
        self._connected = False

    def connect(self) -> None:
        serial = self._serial
        # 嘗試 adb connect（針對 TCP 連線的模擬器）
        if ":" in serial:
            result = subprocess.run(
                ["adb", "connect", serial],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "connected" in result.stdout.lower() or "already" in result.stdout.lower():
                self._connected = True
                logger.info(f"✅ ADB 已連線: {serial}")
            else:
                raise ConnectionError(f"ADB 連線失敗: {result.stdout} {result.stderr}")
        else:
            self._connected = True
            logger.info(f"✅ ADB 使用 USB: {serial}")

    def _adb_shell(self, cmd: str) -> str:
        result = subprocess.run(
            ["adb", "-s", self._serial, "shell", cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()

    def screenshot(self):
        from PIL import Image
        import io

        result = subprocess.run(
            ["adb", "-s", self._serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"截圖失敗: {result.stderr.decode()}")
        return Image.open(io.BytesIO(result.stdout))

    def tap(self, x: int, y: int) -> None:
        self._adb_shell(f"input tap {x} {y}")

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500
    ) -> None:
        self._adb_shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")


class LDPlayerBridge(BaseEmulatorBridge):
    """雷電模擬器專用橋接 — 使用 ldconsole API"""

    def __init__(self, instance: EmulatorInstance):
        super().__init__(instance)
        self._console_path: Path | None = None
        self._index = instance.index

    def _find_console(self) -> Path:
        """尋找 ldconsole 執行檔"""
        if self.instance.install_path:
            candidate = self.instance.install_path / "ldconsole"
            if candidate.exists():
                return candidate
            candidate = self.instance.install_path / "ldconsole.exe"
            if candidate.exists():
                return candidate

        # macOS / Windows 常見路徑
        common_paths = [
            Path("/Applications/LDPlayer9.app/Contents/MacOS/ldconsole"),
            Path(os.path.expandvars(r"%LOCALAPPDATA%\LDPlayer\LDPlayer9\ldconsole.exe")),
            Path(os.path.expandvars(r"%PROGRAMFILES%\LDPlayer\LDPlayer9\ldconsole.exe")),
        ]
        for p in common_paths:
            if p.exists():
                return p

        raise FileNotFoundError("找不到 ldconsole，請在 config 中指定 install_path")

    def _run_console(self, *args: str) -> str:
        if not self._console_path:
            self._console_path = self._find_console()
        cmd = [str(self._console_path)] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()

    def connect(self) -> None:
        self._console_path = self._find_console()
        logger.info(f"✅ LDPlayer 橋接就緒 (index={self._index})")

    def screenshot(self):
        from PIL import Image
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_path = f.name

        try:
            self._run_console(
                "screencap", "--index", str(self._index), "--file", tmp_path
            )
            return Image.open(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def tap(self, x: int, y: int) -> None:
        self._run_console(
            "adb", "--index", str(self._index), "--command",
            f"shell input tap {x} {y}"
        )

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500
    ) -> None:
        self._run_console(
            "adb", "--index", str(self._index), "--command",
            f"shell input swipe {x1} {y1} {x2} {y2} {duration_ms}"
        )


class MuMuBridge(BaseEmulatorBridge):
    """MuMu 模擬器專用橋接 — 使用 MuMuManager API"""

    def __init__(self, instance: EmulatorInstance):
        super().__init__(instance)
        self._manager_path: Path | None = None
        self._index = instance.index

    def _find_manager(self) -> Path:
        """尋找 MuMuManager"""
        common_paths = [
            Path("/Applications/MuMuPlayer.app/Contents/MacOS/MuMuManager"),
            Path(os.path.expandvars(r"%PROGRAMFILES%\MuMu\emulator\shell\MuMuManager.exe")),
            Path(os.path.expandvars(r"%LOCALAPPDATA%\MuMuPlayerGlobal\shell\MuMuManager.exe")),
        ]
        if self.instance.install_path:
            common_paths.insert(0, self.instance.install_path / "MuMuManager")

        for p in common_paths:
            if p.exists():
                return p

        raise FileNotFoundError("找不到 MuMuManager")

    def connect(self) -> None:
        self._manager_path = self._find_manager()
        logger.info(f"✅ MuMu 橋接就緒 (index={self._index})")

    def screenshot(self):
        # MuMu 走 ADB
        from PIL import Image
        import io

        serial = self.instance.adb_serial or "127.0.0.1:7555"
        result = subprocess.run(
            ["adb", "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=10,
        )
        return Image.open(io.BytesIO(result.stdout))

    def tap(self, x: int, y: int) -> None:
        serial = self.instance.adb_serial or "127.0.0.1:7555"
        subprocess.run(
            ["adb", "-s", serial, "shell", f"input tap {x} {y}"],
            capture_output=True,
            timeout=10,
        )

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500
    ) -> None:
        serial = self.instance.adb_serial or "127.0.0.1:7555"
        subprocess.run(
            ["adb", "-s", serial, "shell",
             f"input swipe {x1} {y1} {x2} {y2} {duration_ms}"],
            capture_output=True,
            timeout=10,
        )


class EmulatorBridge:
    """模擬器橋接工廠 — 自動偵測並建立對應橋接"""

    BRIDGE_MAP: dict[EmulatorType, type[BaseEmulatorBridge]] = {
        EmulatorType.LDPLAYER: LDPlayerBridge,
        EmulatorType.MUMU: MuMuBridge,
        # BlueStacks / Nox / MEmu 走通用 ADB
    }

    @classmethod
    def auto_detect(cls, index: int = 0) -> BaseEmulatorBridge:
        """
        自動偵測模擬器並建立橋接

        Args:
            index: 多開時選第幾個實例（0-based）
        """
        instances = EmulatorDetector.detect_all()
        if not instances:
            raise RuntimeError("找不到任何模擬器實例")

        if index >= len(instances):
            raise IndexError(
                f"索引 {index} 超出範圍，共偵測到 {len(instances)} 個實例"
            )

        instance = instances[index]
        return cls.create(instance)

    @classmethod
    def create(cls, instance: EmulatorInstance) -> BaseEmulatorBridge:
        """根據模擬器實例建立對應橋接"""
        bridge_cls = cls.BRIDGE_MAP.get(instance.type, AdbEmulatorBridge)
        bridge = bridge_cls(instance)
        logger.info(
            f"🔌 建立橋接: {instance.type.name} "
            f"(bridge={bridge_cls.__name__})"
        )
        return bridge

    @classmethod
    def create_by_type(
        cls,
        emu_type: EmulatorType | str,
        adb_port: int | None = None,
        install_path: str | None = None,
        index: int = 0,
    ) -> BaseEmulatorBridge:
        """手動指定模擬器類型建立橋接"""
        if isinstance(emu_type, str):
            emu_type = EmulatorType[emu_type.upper()]

        instance = EmulatorInstance(
            type=emu_type,
            name=f"{emu_type.name}_{index}",
            adb_port=adb_port or EmulatorDetector._guess_adb_port(emu_type, index),
            install_path=Path(install_path) if install_path else None,
            index=index,
        )
        return cls.create(instance)
