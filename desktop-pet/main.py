import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon


def _resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller bundle."""
    import sys as _sys
    if getattr(_sys, 'frozen', False):
        base = _sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def main():
    # Set AppUserModelID so Windows taskbar shows our icon instead of Python's
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ToYu.DesktopPet")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(_resource_path("resources/toyu_icon.ico")))
    app.setApplicationName("ToYu Desktop Pet")
    app.setApplicationDisplayName("ToYu — 桌面土豆宠物")

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
