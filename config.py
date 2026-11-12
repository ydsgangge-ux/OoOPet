"""独立桌宠的配置与数据目录（与 workingAgent 主程序完全分离）"""
import json
import os
import sys
from pathlib import Path

APP_NAME = "DesktopPet"

if sys.platform == "win32":
    DATA_ROOT = Path(os.environ.get("APPDATA", str(Path.home()))) / "DesktopPet"
else:
    DATA_ROOT = Path.home() / ".desktoppet"

DATA_ROOT.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_ROOT / "config.json"

DEFAULT_CONFIG = {
    "pet_size": 220,     # 窗口边长 (px)：120/160/220/300
    "pet_pos_x": None,   # 上次位置，None 表示默认右下角
    "pet_pos_y": None,
    "state_hook": True,      # 表情跟随电脑运行状态
    "state_hold_seconds": 6, # 状态持续多少秒才切换，防抖动
}


def load_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
            cfg.update(saved)
        except Exception as e:
            print(f"[配置] 读取失败（已回退默认配置）: {e}")
    return cfg


def save_config(cfg: dict):
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
