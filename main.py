"""独立桌宠启动入口

用法：双击「启动桌宠.bat」，或执行 python main.py
操作：
    左键拖动  移动位置
    左键单击  戳一下（随机表情）
    Ctrl+滚轮 缩放
    右键      切换动作 / 打开素材目录 / 关闭桌宠
"""
import sys

from PyQt6.QtWidgets import QApplication

from media_pet import MediaPet
from system_state import SystemStateWatcher


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("桌宠")

    pet = MediaPet()
    watcher = SystemStateWatcher(pet)
    pet.attach_watcher(watcher)
    watcher.start()

    pet.closed.connect(app.quit)
    pet.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
