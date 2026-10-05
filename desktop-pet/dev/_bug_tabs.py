"""Reproduce the "can't switch tabs" report: drive the real page buttons and inspect state."""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()
mw.show()
app.processEvents()

ORDER = ["宠物", "宠物设置", "工具", "AI"]
print("页数:", mw._page_stack.count())
print("按钮:", list(mw._page_btns.keys()))

print("\n=== 逐个点击顶部标签（模拟真实点击）===")
for label in ORDER + ORDER:  # 走两轮，看第二次是否失效
    btn = mw._page_btns[label]
    btn.click()          # 触发 clicked 信号，与用户点击等价
    app.processEvents()
    time.sleep(0.35)     # 等淡入动画（200ms）结束
    app.processEvents()
    cur = mw._page_stack.currentIndex()
    widget = mw._page_stack.currentWidget()
    eff = widget.graphicsEffect()
    opacity = eff.opacity() if eff is not None else None
    checked = [k for k, b in mw._page_btns.items() if b.isChecked()]
    print("  点 %-4s -> index=%d  类型=%-18s 效果=%s 不透明度=%s 选中=%s"
          % (label, cur, type(widget).__name__,
             type(eff).__name__ if eff else "None",
             ("%.2f" % opacity) if opacity is not None else "-",
             checked))

print("\n=== 动画对象状态 ===")
anim = getattr(mw, "_page_fade_anim", None)
eff = getattr(mw, "_page_fade_effect", None)
print("  动画存在:", anim is not None, "| 状态:", anim.state() if anim else "-")
print("  效果对象:", eff)
if eff is not None:
    try:
        eff.opacity()          # 访问已删除的 C++ 对象会抛 RuntimeError
        print("  效果对象仍可用: 是")
    except RuntimeError as exc:
        print("  效果对象已被销毁 -> 后续动画目标失效:", exc)

print("\n=== 子标签（工具页内部）切换 ===")
mw._page_btns["工具"].click()
app.processEvents()
time.sleep(0.3)
for i in range(3):
    mw._switch_tools_page(i)
    app.processEvents()
    print("  子页 %d -> 当前 widget: %s" % (i, type(mw._tools_stack.currentWidget()).__name__))
