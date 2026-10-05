"""Exercises every tab, sub-tab and panel, checking for exceptions and bad states."""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as toyu_main  # noqa: E402

toyu_main._install_crash_guard()
LOG_BEFORE = os.path.getsize(toyu_main.LOG_PATH) if os.path.exists(toyu_main.LOG_PATH) else 0

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QCheckBox, QComboBox, QSlider  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=120):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
pump(300)
mw._on_start_pet()
pump(400)

# ── 1. 遍历四个主页 ─────────────────────────────────────────
page_errors = []
for label in ("宠物", "宠物设置", "工具", "AI"):
    try:
        mw._page_btns[label].click()
        pump(300)
    except Exception as exc:  # noqa: BLE001
        page_errors.append("%s -> %s: %s" % (label, type(exc).__name__, exc))
check("四个主页切换无异常", not page_errors, str(page_errors))

# ── 2. 遍历工具页三个子页 ───────────────────────────────────
mw._page_btns["工具"].click()
pump(200)
sub_errors = []
for i in range(3):
    try:
        mw._switch_tools_page(i)
        pump(250)
    except Exception as exc:  # noqa: BLE001
        sub_errors.append("子页 %d -> %s: %s" % (i, type(exc).__name__, exc))
check("工具页三个子页切换无异常", not sub_errors, str(sub_errors))

# 数据面板的两个统计子页
stat_errors = []
for i in (0, 1):
    try:
        mw._switch_stat_tab(i)
        pump(200)
    except Exception as exc:  # noqa: BLE001
        stat_errors.append("统计页 %d -> %s: %s" % (i, type(exc).__name__, exc))
check("数据面板统计子页切换无异常", not stat_errors, str(stat_errors))

# ── 3. 设置对话框能打开并保存 ───────────────────────────────
try:
    from ui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(mw.settings, mw)
    dlg.show()
    pump(300)
    tabs = dlg.findChildren(QComboBox)
    dlg._save_and_close()
    pump(200)
    check("设置对话框打开并保存无异常", True, "含 %d 个下拉框" % len(tabs))
except Exception as exc:  # noqa: BLE001
    check("设置对话框打开并保存无异常", False, "%s: %s" % (type(exc).__name__, exc))

# ── 4. 各面板关键控件是否有内容（防空面板） ──────────────────
mw._page_btns["工具"].click()
mw._switch_tools_page(0)
pump(300)
todo = mw._todo_widget
check("待办面板可访问未完成数", isinstance(todo.get_incomplete_count(), int),
      "未完成 %s" % todo.get_incomplete_count())
try:
    todo._on_add()
    pump(150)
    check("待办空输入不崩溃", True)
except Exception as exc:  # noqa: BLE001
    check("待办空输入不崩溃", False, "%s: %s" % (type(exc).__name__, exc))

timer = mw._timer_widget
try:
    timer._on_start()
    pump(150)
    running = timer.get_is_running()
    timer._on_reset()
    pump(150)
    check("倒计时器启动/重置无异常", not timer.get_is_running(),
          "启动后 running=%s，重置后 running=%s" % (running, timer.get_is_running()))
except Exception as exc:  # noqa: BLE001
    check("倒计时器启动/重置无异常", False, "%s: %s" % (type(exc).__name__, exc))

cal = mw._calendar
try:
    cal._prev_month()
    pump(120)
    cal._next_month()
    pump(120)
    cal._go_today()
    pump(120)
    check("日历翻月/回今天无异常", True)
except Exception as exc:  # noqa: BLE001
    check("日历翻月/回今天无异常", False, "%s: %s" % (type(exc).__name__, exc))

# ── 5. 深色模式来回切换后各页仍正常 ─────────────────────────
try:
    for _ in range(3):
        mw._toggle_dark_mode()
        pump(150)
    for label in ("宠物", "宠物设置", "工具", "AI"):
        mw._page_btns[label].click()
        pump(120)
    check("深色/浅色来回切换 3 次无异常", True)
except Exception as exc:  # noqa: BLE001
    check("深色/浅色来回切换 3 次无异常", False, "%s: %s" % (type(exc).__name__, exc))

# 深色模式下页面不能不透明（回归：标签切换动画问题）
bad_opacity = []
for label in ("宠物", "宠物设置", "工具", "AI"):
    mw._page_btns[label].click()
    pump(350)
    w = mw._page_stack.currentWidget()
    eff = w.graphicsEffect()
    if eff is not None and eff.opacity() < 1.0:
        bad_opacity.append((label, round(eff.opacity(), 2)))
check("切换后页面完全不透明", not bad_opacity, str(bad_opacity))

# ── 6. 崩溃防护日志是否有新增（产品代码抛异常会记在这里）───
LOG_AFTER = os.path.getsize(toyu_main.LOG_PATH) if os.path.exists(toyu_main.LOG_PATH) else 0
check("全程无未捕获异常写入日志", LOG_AFTER == LOG_BEFORE,
      "日志 %d -> %d bytes" % (LOG_BEFORE, LOG_AFTER))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-36s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
