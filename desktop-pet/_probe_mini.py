"""Debug: why does the per-task timer not switch the mini window to countup?"""

import os
import sys
import time

os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
pump(900)
mw._on_start_pet()
pump(400)

mw._todo_widget._input.setText("调试任务")
mw._todo_widget._on_add()
pump(300)

print("mini_timer_enabled 设置:", mw.settings.mini_timer_enabled)

mw.enter_flow_mode()
pump(1000)
fw = mw._flow_window
print("进入心流后 mw._mini_timer:", mw._mini_timer,
      "| fw 是否自持小窗:", hasattr(fw, "_mini"))

fw.toggle_task_timer("调试任务")
pump(800)
print("toggle 后 fw._active_task:", fw._active_task)
print("mw._mini_timer:", mw._mini_timer)
if mw._mini_timer is not None:
    print("小窗模式:", mw._mini_timer._mode, "| 标题:", mw._mini_timer._title)

# 直接调用看一下
mw.show_mini_timer("测试标题", "countup")
pump(600)
print("手动调用后模式:", mw._mini_timer._mode, "| 标题:", mw._mini_timer._title)

mw.exit_flow_mode()
pump(300)
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos if t.text != "调试任务"]
    mw._todo_widget._save_todos()
except Exception:
    pass
sys.stdout.flush()
os._exit(0)
