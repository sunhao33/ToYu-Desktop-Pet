"""Regression test: 心流模式（独立窗口版）。

要求：头部「重新启动」右侧有入口按钮；点击后**主窗口关闭、打开独立的心流窗口**，
尺寸与主窗口一致；两个页面双向互通；共用一套数据池，宠物与计时状态全保留。
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=250):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
pump(500)
mw._on_start_pet()
pump(500)

# ── 1. 入口按钮 ────────────────────────────────────────────
check("头部有【心流模式】按钮", isinstance(getattr(mw, "_flow_btn", None), QPushButton))
lay = mw._start_btn.parentWidget().layout()
check("心流按钮在「重新启动」右侧",
      lay.indexOf(mw._flow_btn) > lay.indexOf(mw._start_btn),
      "重新启动 idx=%d, 心流 idx=%d" % (lay.indexOf(mw._start_btn), lay.indexOf(mw._flow_btn)))

main_geo_before = mw.geometry()
timer_before = mw._timer_widget
pet_before = mw._pet

# ── 2. 进入：主窗口关闭、心流独立窗口出现 ───────────────────
mw.enter_flow_mode()
pump(700)
flow = mw._flow_window
check("心流窗口已创建", flow is not None)
check("心流是独立顶层窗口", flow is not None and flow.parent() is None and flow.isWindow())
check("主窗口已关闭（隐藏）", not mw.isVisible())
check("心流窗口已打开", flow.isVisible())
check("心流窗口标题正确", "心流" in flow.windowTitle(), flow.windowTitle())

# ── 3. 尺寸一致 ────────────────────────────────────────────
check("心流窗口尺寸与主窗口一致",
      flow.size() == main_geo_before.size(),
      "主窗口 %dx%d / 心流 %dx%d" % (main_geo_before.width(), main_geo_before.height(),
                                    flow.width(), flow.height()))
check("心流窗口位置与主窗口一致",
      (flow.x(), flow.y()) == (main_geo_before.x(), main_geo_before.y()),
      "主 (%d,%d) / 心流 (%d,%d)" % (main_geo_before.x(), main_geo_before.y(),
                                     flow.x(), flow.y()))

# ── 4. 状态共享 ────────────────────────────────────────────
check("计时器实例未重建", mw._timer_widget is timer_before)
check("计时器已搬到心流窗口",
      flow._timer_holder.indexOf(mw._timer_widget) >= 0,
      "父控件=%s" % (type(mw._timer_widget.parentWidget()).__name__
                    if mw._timer_widget.parentWidget() else None))
check("宠物实例未重建", mw._pet is pet_before)
check("心流窗口有独立的头部/状态栏", flow._back_btn is not None and flow._status is not None)

# ── 5. 在心流窗口启动专注，切回主窗口后继续 ─────────────────
flow.start_focus(25)
pump(700)
check("心流窗口可启动专注", mw._timer_widget.get_is_running() is True)
remaining_in_flow = mw._timer_widget.get_remaining_seconds()

flow._back_btn.click()
pump(700)
check("已退出心流模式", mw._flow_active is False)
check("心流窗口已关闭", not flow.isVisible())
check("主窗口已重新出现", mw.isVisible())
check("计时器回到主窗口",
      mw._timer_slot_layout.indexOf(mw._timer_widget) >= 0)
check("主窗口尺寸沿用退出时的窗口",
      mw.size() == main_geo_before.size(),
      "主窗口 %dx%d" % (mw.width(), mw.height()))
check("切回后计时仍在继续", mw._timer_widget.get_is_running() is True)
check("切回后剩余时间未重置",
      mw._timer_widget.get_remaining_seconds() <= remaining_in_flow,
      "%ds -> %ds" % (remaining_in_flow, mw._timer_widget.get_remaining_seconds()))

# ── 6. 数据共享：待办 → 心流计划栏 ──────────────────────────
mw._todo_widget._input.setText("心流测试任务")
mw._todo_widget._on_add()
pump(400)
mw.enter_flow_mode()
pump(700)
plan_rows = mw._flow_window._plan_list.count() - 1
check("心流窗口读到主页待办", plan_rows >= 1, "计划行数 %d" % plan_rows)
check("心流窗口统计可读取",
      mw._flow_window._stat_rows["left"].text() != "-",
      "未完成 %s" % mw._flow_window._stat_rows["left"].text())

# ── 7. 心流窗口内的跳转按钮 ────────────────────────────────
mw._flow_window._goto_main("工具", sub=2)
pump(700)
check("跳转后已回到主窗口", mw.isVisible() and not mw._flow_window.isVisible())
check("跳转后停在数据面板",
      mw._page_stack.currentIndex() == 2 and mw._tools_stack.currentIndex() == 2,
      "主页 %d / 子页 %d" % (mw._page_stack.currentIndex(), mw._tools_stack.currentIndex()))

# ── 8. 直接关掉心流窗口应等价于返回主窗口 ───────────────────
mw.enter_flow_mode()
pump(500)
mw._flow_window.close()
pump(600)
check("关闭心流窗口后回到主窗口", mw.isVisible() and not mw._flow_active)

# ── 9. 模式持久化 + 反复切换 ───────────────────────────────
mw.enter_flow_mode()
pump(300)
check("进入后设置记录为已启用", mw.settings.flow_mode_enabled is True)
mw.exit_flow_mode()
pump(300)
check("退出后设置记录为已关闭", mw.settings.flow_mode_enabled is False)

errs = []
for _ in range(3):
    try:
        mw.enter_flow_mode()
        pump(250)
        mw.exit_flow_mode()
        pump(250)
    except Exception as exc:  # noqa: BLE001
        errs.append("%s: %s" % (type(exc).__name__, exc))
check("反复进出无异常", not errs, str(errs[:2]))
check("反复进出后计时器在主窗口",
      mw._timer_slot_layout.indexOf(mw._timer_widget) >= 0)

# 清理测试待办
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos if t.text != "心流测试任务"]
    mw._todo_widget._save_todos()
except Exception:
    pass

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-40s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
