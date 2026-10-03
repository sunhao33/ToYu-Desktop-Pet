"""Probe: (1) does the crash guard cover signal callbacks? (2) hunt concrete defects."""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as toyu_main  # noqa: E402

log_size_before = os.path.getsize(toyu_main.LOG_PATH) if os.path.exists(toyu_main.LOG_PATH) else 0
toyu_main._install_crash_guard()

from PyQt6.QtCore import QTimer, QPoint, Qt, pyqtSignal, QObject  # noqa: E402
from PyQt6.QtGui import QMouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


# ── 1. 崩溃防护是否覆盖「信号回调」异常 ─────────────────────
class Emitter(QObject):
    fired = pyqtSignal()


box = {"n": 0}


def bad_slot():
    box["n"] += 1
    if box["n"] == 1:
        raise RuntimeError("信号回调里的异常")


em = Emitter()
em.fired.connect(bad_slot)

timer = QTimer()
timer.timeout.connect(lambda: em.fired.emit())
timer.start(20)

# 手动泵事件循环，避免 app.exec() 卡住（也顺带验证异常后循环仍在跑）
deadline = time.time() + 1.2
while time.time() < deadline:
    app.processEvents()
    time.sleep(0.01)
timer.stop()

check("信号回调异常后进程存活", box["n"] >= 5, "回调被调用 %d 次（应 ≥5）" % box["n"])
log_size_after = os.path.getsize(toyu_main.LOG_PATH) if os.path.exists(toyu_main.LOG_PATH) else 0
check("信号回调异常被记入日志", log_size_after > log_size_before,
      "日志 %d -> %d bytes" % (log_size_before, log_size_after))

# ── 2. 桌面工具：QSettings 里存了脏数据会不会崩 ──────────────
from ui.settings_manager import SettingsManager  # noqa: E402

s = SettingsManager()
dirty_cases = [
    ("历史是字符串不是列表", lambda: setattr(s, "clipboard_history", "not-a-list")),
    ("历史里混入 None", lambda: setattr(s, "clipboard_history", [None, {"text": "ok"}])),
    ("历史里混入字符串项", lambda: setattr(s, "clipboard_history", ["plain", {"text": "x"}])),
    ("历史项缺 text", lambda: setattr(s, "clipboard_history", [{"time": "10-03"}])),
    ("历史项是数字", lambda: setattr(s, "clipboard_history", [123, {"text": "y", "time": "t"}])),
]
dirty_errors = []
for label, setter in dirty_cases:
    try:
        setter()
        from ui.tools.hub import ClipboardHistory
        ch = ClipboardHistory(s)
        list(ch.history)
    except Exception as exc:  # noqa: BLE001
        dirty_errors.append("%s -> %s: %s" % (label, type(exc).__name__, exc))
s.clipboard_history = []
check("剪贴板历史脏数据不崩溃", not dirty_errors, str(dirty_errors[:3]))

# ── 3. 桌面工具：启用开关的字符串兼容 ───────────────────────
try:
    s._settings.setValue("tools/clipboard_enabled", "true")
    v1 = s.clipboard_enabled
    s._settings.setValue("tools/clipboard_enabled", "false")
    v2 = s.clipboard_enabled
    s._settings.setValue("tools/clipboard_enabled", True)
    v3 = s.clipboard_enabled
    check("布尔设置兼容字符串/布尔", (v1 is True) and (v2 is False) and (v3 is True),
          "true=%s false=%s bool=%s" % (v1, v2, v3))
except Exception as exc:  # noqa: BLE001
    check("布尔设置兼容字符串/布尔", False, "%s: %s" % (type(exc).__name__, exc))

# ── 4. 主窗口：宠物已存在时再次启动会不会泄漏/串台 ──────────
from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()
mw.show()
app.processEvents()
mw._on_start_pet()
app.processEvents()
first = mw._pet
mw._on_start_pet()          # 再点一次「重新启动」
app.processEvents()
second = mw._pet
check("重复启动会替换宠物实例", first is not second and second is not None,
      "first=%s second=%s" % (first is not None, second is not None))
timer_count = 0
from PyQt6.QtCore import QTimer as QT  # noqa: E402
for w in app.allWidgets():
    timer_count += len(w.findChildren(QT))
check("重复启动后定时器数量未爆增（<80）", timer_count < 80, "定时器 %d 个" % timer_count)

# 旧实例是否已停止（游戏循环应已关闭）
if first is not None:
    still_running = first._game_timer.isActive()
    check("旧宠物实例的游戏循环已停止", not still_running,
          "旧实例 _game_timer.isActive()=%s" % still_running)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-34s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
