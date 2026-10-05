import sys
import os
import ctypes
import time
import traceback
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

LOG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "ToYu")
LOG_PATH = os.path.join(LOG_DIR, "errors.log")
MAX_LOG_BYTES = 512 * 1024

def _log_path():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        return None
    return LOG_PATH

def _write_error(lines):
    path = _log_path()
    if not path:
        return
    try:
        if os.path.exists(path) and os.path.getsize(path) > MAX_LOG_BYTES:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(lines)
    except OSError:
        pass

def _install_crash_guard():
    """PyQt6 aborts the whole process when a slot raises, and a windowed exe has no
    console to show why. Keep the traceback, stay alive instead of dying silently."""
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        _write_error("\n===== %s =====\n%s" % (stamp, text))

        window = getattr(_install_crash_guard, "window", None)
        if window is not None:
            try:
                brief = "%s: %s" % (exc_type.__name__, exc_value)
                _write_error("(已忽略，程序继续运行)\n")
                window._on_tools_notify("crash", "⚠️ 出了点小问题，已自动恢复",
                                        brief[:120])
            except Exception:
                pass

    sys.excepthook = _hook
    return _hook

def _resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

def main():
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ToYu.DesktopPet")

    _install_crash_guard()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(_resource_path("resources/toyu_icon.ico")))
    app.setApplicationName("ToYu Desktop Pet")
    app.setApplicationDisplayName("ToYu — 桌面土豆宠物")

    from ui.main_window import MainWindow
    window = MainWindow()
    _install_crash_guard.window = window
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
