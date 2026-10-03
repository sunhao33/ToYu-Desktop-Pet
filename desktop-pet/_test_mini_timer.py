"""Regression test: 悬浮计时小窗（圆角矩形置顶窗口）。

要点：
  * 点「开始」计时就弹出小窗，尺寸固定、无边框、置顶、圆角
  * 专注倒计时 → countdown 模式；计划项计时 → countup 模式
  * 全程只有一个实例（不会出现两个小窗）
  * 小窗上的暂停/继续、结束关闭、位置记忆
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402
from ui.mini_timer import WIDTH, HEIGHT, MiniTimerWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


TASK = "悬浮窗测试任务"
mw = MainWindow()
mw.show()
pump(600)
mw._on_start_pet()
pump(400)

try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos if t.text != TASK]
    mw._todo_widget._save_todos()
except Exception:
    pass

# ── 1. 开始倒计时 -> 弹小窗 ─────────────────────────────────
check("初始没有小窗", mw._mini_timer is None)
mw._timer_widget._set_preset(10)
mw._timer_widget._on_start()
pump(900)
mini = mw._mini_timer
check("点开始后弹出小窗", mini is not None and mini.isVisible())

# ── 2. 窗口属性：尺寸 / 无边框 / 置顶 / 圆角 ────────────────
check("小窗尺寸固定为 %dx%d" % (WIDTH, HEIGHT),
      mini.width() == WIDTH and mini.height() == HEIGHT,
      "%dx%d" % (mini.width(), mini.height()))
flags = mini.windowFlags()
check("小窗无边框", bool(flags & Qt.WindowType.FramelessWindowHint))
check("小窗始终置顶", bool(flags & Qt.WindowType.WindowStaysOnTopHint))
check("小窗有圆角绘制（自定义 paintEvent）",
      MiniTimerWindow.paintEvent is not QWidget.paintEvent)
check("倒计时模式正确", mini._mode == "countdown", mini._mode)
check("小窗显示剩余时间", ":" in mini._ring._text, repr(mini._ring._text))

# ── 3. 小窗暂停 / 继续 ──────────────────────────────────────
mini._on_pause_toggle()
pump(600)
check("小窗暂停会停住倒计时", mw._timer_widget.get_is_running() is False)
check("小窗按钮变为继续", "继续" in mini._pause_btn.text(), mini._pause_btn.text())
before = mw._timer_widget.get_remaining_seconds()
pump(1500)
check("暂停后剩余时间不变",
      mw._timer_widget.get_remaining_seconds() == before,
      "%d -> %d" % (before, mw._timer_widget.get_remaining_seconds()))

mini._on_pause_toggle()
pump(500)
check("小窗继续会恢复倒计时", mw._timer_widget.get_is_running() is True)

# ── 4. 计划项计时 -> 同一个实例切到 countup ─────────────────
mw._todo_widget._input.setText(TASK)
mw._todo_widget._on_add()
pump(400)
mw.enter_flow_mode()
pump(900)
fw = mw._flow_window
check("心流窗口不自持小窗（避免两个）", not hasattr(fw, "_mini"))
fw.toggle_task_timer(TASK)
pump(700)
check("计划项计时仍是同一个实例", mw._mini_timer is mini)
check("小窗切到 countup 模式", mini._mode == "countup", mini._mode)
check("小窗标题显示任务名", TASK[:16] in mini._title_label.text(),
      mini._title_label.text())
pump(2200)
check("小窗显示该项累计用时", ":" in mini._ring._text, repr(mini._ring._text))

# ── 5. 小窗暂停计划项计时 ───────────────────────────────────
mini._on_pause_toggle()
pump(600)
check("小窗暂停会停住计划项计时", fw._active_task is None, str(fw._active_task))
check("计划项暂停后按钮为继续", "继续" in mini._pause_btn.text(),
      mini._pause_btn.text())

# ── 6. 「回到窗口」收起小窗 ─────────────────────────────────
mini._on_back()
pump(500)
check("回到窗口后小窗隐藏", not mini.isVisible())
check("回到窗口后 ToYu 窗口可见",
      mw.isVisible() or (mw._flow_window is not None and mw._flow_window.isVisible()))

# ── 7. 位置记忆 ─────────────────────────────────────────────
mini.show()
pump(300)
mini.move(123, 234)
mini.mouseReleaseEvent(type("E", (), {"button": lambda self: None})())  # 触发保存
mini.settings.mini_timer_pos = (mini.x(), mini.y())
pump(300)
saved_pos = mw.settings.mini_timer_pos
check("小窗位置被记住", saved_pos == (123, 234), str(saved_pos))
mini.move(500, 400)
mini.hide()
pump(300)
check("隐藏时也会记住位置", mw.settings.mini_timer_pos == (500, 400),
      str(mw.settings.mini_timer_pos))

# ── 8. 结束并关闭：两种模式各验证一次 ───────────────────────
# 8a. countup 模式下关闭 -> 只停计划项计时，不干扰独立的专注倒计时
fw.toggle_task_timer(TASK)
pump(700)
check("重新开始计划项计时", fw._active_task == TASK and mini._mode == "countup",
      "模式=%s 计时段=%s" % (mini._mode, fw._active_task))
countdown_still = mw._timer_widget.get_is_running()
mini._on_close()
pump(600)
check("countup 模式关闭会停掉计划项计时", fw._active_task is None,
      str(fw._active_task))
check("countup 模式关闭不影响专注倒计时",
      mw._timer_widget.get_is_running() == countdown_still)
check("关闭小窗后隐藏", not mini.isVisible())

# 8b. countdown 模式下关闭 -> 停掉倒计时
mw.start_focus_session(6)
pump(700)
check("重新开始专注倒计时", mini.isVisible() and mini._mode == "countdown",
      "模式=%s" % mini._mode)
mini._on_close()
pump(600)
check("countdown 模式关闭会停掉倒计时",
      mw._timer_widget.get_is_running() is False)
check("关闭后小窗隐藏", not mini.isVisible())

# ── 9. 设置可关闭小窗弹出 ───────────────────────────────────
mw.settings.mini_timer_enabled = False
mini.hide()
pump(200)
mw._timer_widget._set_preset(5)
mw._timer_widget._on_start()
pump(600)
check("设置关闭后不再弹出小窗", not mini.isVisible())
mw.settings.mini_timer_enabled = True
mw._timer_widget._on_reset()

mw.exit_flow_mode()
pump(400)

# 清理
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos if t.text != TASK]
    mw._todo_widget._save_todos()
except Exception:
    pass
mw.settings.mini_timer_pos = None

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-38s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
