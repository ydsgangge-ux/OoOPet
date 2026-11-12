"""电脑运行状态 → 桌宠动作 的联动器

优先级（高 → 低）：
  低电量 > 高负载 > 长时间无操作 > 深夜 > 开会 > 工作 > 娱乐 > 待机

规则：
  - 每 2 秒采集一次；同一状态要持续 HOLD 秒才生效，避免抖动
  - 只读取标题/占用率，不联网、不落盘
  - 切换动作由 MediaPet 排到当前动画播完一整遍之后
"""
import ctypes
import sys
import time
from datetime import datetime

import psutil
from PyQt6.QtCore import QObject, QTimer

from config import load_config, save_config

# ── 阈值 ──────────────────────────────────────────
POLL_MS = 2000
HOLD_SECONDS = 6.0

CPU_BUSY = 85.0          # CPU 占用率 %
MEM_BUSY = 90.0          # 内存占用率 %
DISK_BUSY = 0.8          # 磁盘读写时间占比（0~1）
BATTERY_LOW = 20         # 低于此电量且未充电 → 低电量
BATTERY_CHARGING = 30    # 低于此电量且正在充电 → 充电
IDLE_SLEEP_SECONDS = 180 # 键鼠无操作多久 → 困了
NIGHT_START, NIGHT_END = 23, 6

MEETING_WORDS = (
    "zoom", "teams", "webex", "google meet", "腾讯会议", "钉钉会议",
    "飞书会议", "视频会议", "会议室",
)
WORK_WORDS = (
    "visual studio", "vscode", "vs code", "pycharm", "intellij", "idea",
    "cursor", "sublime", "terminal", "powershell", "命令提示符",
    "jupyter", "notebook", "word", "excel", "powerpoint", "wps",
    "notion", "obsidian", "typora", "xmind",
)
FUN_WORDS = (
    "bilibili", "哔哩哔哩", "youtube", "netflix", "爱奇艺", "腾讯视频",
    "优酷", "抖音", "douyin", "tiktok", "steam", "原神", "英雄联盟",
    "potplayer", "vlc", "media player",
)


# ── Windows 原生信息 ──────────────────────────────
class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    """距离最后一次键鼠操作的秒数；非 Windows 返回 0"""
    if sys.platform != "win32":
        return 0.0
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        elapsed = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, elapsed / 1000.0)
    except Exception:
        return 0.0


def foreground_title() -> str:
    """当前前台窗口标题；失败返回空串"""
    if sys.platform != "win32":
        return ""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


class SystemStateWatcher(QObject):
    """把电脑状态映射成桌宠动作，带防抖和优先级"""

    def __init__(self, pet, parent=None):
        super().__init__(parent)
        self._pet = pet
        cfg = load_config()
        self.enabled = bool(cfg.get("state_hook", True))
        self.hold_seconds = float(cfg.get("state_hold_seconds", HOLD_SECONDS) or HOLD_SECONDS)

        self._candidate = None
        self._candidate_since = 0.0
        self._last_state = None
        self._disk_prev = None
        self._disk_prev_at = None

        psutil.cpu_percent(None)   # 第一次调用只做基线
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._tick)

    # ── 生命周期 ──
    @property
    def last_state(self) -> str:
        """最近一次生效的状态（拖拽松手后用来迅速回到正确动作）"""
        return self._last_state or "idle"

    def start(self):
        if self.enabled:
            self._timer.start()

    def stop(self):
        self._timer.stop()

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        self._candidate = None
        self._candidate_since = 0.0
        if self.enabled:
            self._timer.start()
        else:
            self._timer.stop()
        try:
            cfg = load_config()
            cfg["state_hook"] = self.enabled
            save_config(cfg)
        except Exception:
            pass

    # ── 采集 ──
    def _tick(self):
        if not self.enabled:
            return
        state = self._evaluate()
        now = time.monotonic()
        if state != self._candidate:
            self._candidate = state
            self._candidate_since = now
            return
        if now - self._candidate_since < self.hold_seconds:
            return
        self._last_state = state
        try:
            # 每个周期都请求一次：手动表情保护期结束后能自动恢复联动
            self._pet.request_ambient(state)
        except Exception as e:
            print(f"[State] 应用状态失败: {e}", flush=True)

    def _evaluate(self) -> str:
        # 1. 电量
        try:
            battery = psutil.sensors_battery()
        except Exception:
            battery = None
        if battery is not None:
            if not battery.power_plugged and battery.percent <= BATTERY_LOW:
                return "lowbattery"
            if battery.power_plugged and battery.percent <= BATTERY_CHARGING:
                return "charging"

        # 2. 资源占用
        if self._busy():
            return "busy"

        # 3. 长时间无操作
        if idle_seconds() >= IDLE_SLEEP_SECONDS:
            return "sleepy"

        # 4. 深夜
        hour = datetime.now().hour
        if hour >= NIGHT_START or hour < NIGHT_END:
            return "sleepy"

        # 5. 前台窗口类型
        title = foreground_title().lower()
        if title:
            if any(w in title for w in MEETING_WORDS):
                return "meeting"
            if any(w in title for w in WORK_WORDS):
                return "working"
            if any(w in title for w in FUN_WORDS):
                return "fun"

        return "idle"

    def _busy(self) -> bool:
        try:
            cpu = psutil.cpu_percent(None)
            mem = psutil.virtual_memory().percent
        except Exception:
            return False
        if cpu >= CPU_BUSY or mem >= MEM_BUSY:
            return True

        # 磁盘：按读写时间占比判断真实负载（容量占用不作为"忙"）
        try:
            io = psutil.disk_io_counters()
            if io is None:
                return False
            now = time.monotonic()
            prev, prev_at = self._disk_prev, self._disk_prev_at
            self._disk_prev = (io.read_time, io.write_time)
            self._disk_prev_at = now
            if prev is None or prev_at is None:
                return False
            elapsed_ms = (now - prev_at) * 1000.0
            if elapsed_ms <= 0:
                return False
            busy_ms = max(io.read_time - prev[0], io.write_time - prev[1])
            return busy_ms / elapsed_ms >= DISK_BUSY
        except Exception:
            return False
