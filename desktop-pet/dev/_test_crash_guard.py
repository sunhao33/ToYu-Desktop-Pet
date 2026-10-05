"""Verify the crash guard: an exception thrown from a timer slot must not kill the app."""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# main.py 内的崩溃防护（不启动真窗口）
import main as toyu_main  # noqa: E402

hook = toyu_main._install_crash_guard()

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

LOG = toyu_main.LOG_PATH
before = os.path.getsize(LOG) if os.path.exists(LOG) else 0

STATE = {"ticks": 0, "raised": 0}


def ticking():
    STATE["ticks"] += 1
    if STATE["ticks"] in (2, 5, 9):
        STATE["raised"] += 1
        raise RuntimeError("模拟槽函数异常 #%d" % STATE["raised"])


timer = QTimer()
timer.timeout.connect(ticking)
timer.start(60)

RESULT = {}


def wrap_up():
    timer.stop()
    after = os.path.getsize(LOG) if os.path.exists(LOG) else 0
    RESULT["log_grew"] = after > before
    RESULT["ticks"] = STATE["ticks"]
    RESULT["raised"] = STATE["raised"]
    app.quit()


QTimer.singleShot(1500, wrap_up)
app.exec()

print("ticks survived :", RESULT["ticks"])
print("exceptions     :", RESULT["raised"])
print("errors.log     :", "已写入" if RESULT["log_grew"] else "未写入", LOG)
ok = RESULT["ticks"] > 12 and RESULT["raised"] == 3 and RESULT["log_grew"]
print("\n结果:", "PASS — 异常后进程继续运行且已记录" if ok else "FAIL")
sys.stdout.flush()
os._exit(0 if ok else 1)
