"""Regression test: 心流模式（入口按钮、双向切换、数据与状态共享）。

要点：
  * 头部「重新启动」右侧有【心流模式】按钮
  * 进入后切到心流面板、子页标签栏隐藏、按钮文案变为「回到 ToYu」
  * 计时器是同一个实例（状态不重置）
  * 宠物、设置、待办数据全部共享
  * 退出后回到主页且计时仍在继续
  * 模式状态持久化
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

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
pump(400)
mw._on_start_pet()
pump(400)

# ── 1. 入口按钮存在且位置在「重新启动」右侧 ─────────────────
check("头部有【心流模式】按钮", hasattr(mw, "_flow_btn") and mw._flow_btn is not None)
header = mw._start_btn.parentWidget()
lay = header.layout()
idx_start = lay.indexOf(mw._start_btn)
idx_flow = lay.indexOf(mw._flow_btn)
check("心流按钮在「重新启动」右侧", idx_flow > idx_start,
      "重新启动 idx=%d, 心流 idx=%d" % (idx_start, idx_flow))

# ── 2. 进入心流：切换子页、隐藏子页标签、按钮文案 ────────────
timer_before = mw._timer_widget
pet_before = mw._pet
mw.enter_flow_mode()
pump(500)
check("已进入心流模式标记", mw._flow_active is True)
check("切到心流子页", mw._tools_stack.currentIndex() == mw.FLOW_SUBPAGE_INDEX,
      "当前子页 %d" % mw._tools_stack.currentIndex())
# 注意：判断「是否被显式隐藏」要用 isHidden()，不能用 isVisible()——
# 控件所在页面被切走时 isVisible() 恒为 False，会造成误判
check("子页标签栏已隐藏（显式）", mw._tools_tab_bar.isHidden() is True)
check("按钮文案变为「回到 ToYu」", "回到" in mw._flow_btn.text(), mw._flow_btn.text())
check("当前页是「工具」页", mw._page_stack.currentIndex() == 2)

# ── 3. 状态共享：计时器实例、宠物实例保持不变 ────────────────
check("计时器是同一个实例（未重建）", mw._timer_widget is timer_before)
check("计时器现在挂在心流面板里",
      mw._timer_widget.parentWidget() is not None
      and mw._flow_panel._timer_holder.indexOf(mw._timer_widget) >= 0,
      "父控件=%s" % (type(mw._timer_widget.parentWidget()).__name__
                    if mw._timer_widget.parentWidget() else None))
check("宠物实例未被重建", mw._pet is pet_before)

# ── 4. 在心流页启动计时，切回主页后应继续运行 ────────────────
mw._flow_panel._start_focus(25)
pump(600)
check("心流页可启动专注计时", mw._timer_widget.get_is_running() is True)
remaining_in_flow = mw._timer_widget.get_remaining_seconds()

mw.exit_flow_mode()
pump(600)
check("已退出心流模式标记", mw._flow_active is False)
check("子页标签栏已恢复（不再显式隐藏）", mw._tools_tab_bar.isHidden() is False)
check("按钮文案恢复", "心流" in mw._flow_btn.text(), mw._flow_btn.text())
check("回到宠物页", mw._page_stack.currentIndex() == 0)
check("计时器回到主页的工具页",
      mw._timer_slot_layout.indexOf(mw._timer_widget) >= 0)
check("切回后计时仍在继续", mw._timer_widget.get_is_running() is True)
remaining_after = mw._timer_widget.get_remaining_seconds()
check("切回后剩余时间没有重置", remaining_after <= remaining_in_flow,
      "切换前 %ds -> 切换后 %ds" % (remaining_in_flow, remaining_after))

# ── 5. 数据共享：待办数量与今日统计能读到同一份数据 ──────────
mw._todo_widget._input.setText("心流测试任务")
mw._todo_widget._on_add()
pump(400)
todo_count = mw._todo_widget.get_incomplete_count()
mw.enter_flow_mode()
pump(600)
plan_rows = mw._flow_panel._plan_list.count() - 1     # 减去 stretch
check("心流页读到主页待办", plan_rows >= 1, "计划行数 %d（待办 %d 条）" % (plan_rows, todo_count))
check("心流页统计可读取", mw._flow_panel._stat_rows["left"].text() != "-",
      "未完成显示 %s" % mw._flow_panel._stat_rows["left"].text())
mw.exit_flow_mode()
pump(300)

# ── 6. 模式状态持久化 ──────────────────────────────────────
mw.enter_flow_mode()
pump(300)
check("进入后设置里记录为已启用", mw.settings.flow_mode_enabled is True)
mw.exit_flow_mode()
pump(300)
check("退出后设置里记录为已关闭", mw.settings.flow_mode_enabled is False)

# ── 7. 重复进入/退出不应出问题 ─────────────────────────────
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
check("反复进出后计时器仍在正确位置",
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
    print("%-4s %-38s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
