"""Debug: is the 保存 AI 设置 button actually clickable (visible geometry)?"""

import os
import sys
import time

os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

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
pump(600)

# 切到 AI 页
mw._page_btns["AI"].click()
pump(600)
page = mw._page_stack.widget(3)
print("AI 页: 尺寸 %dx%d | 内容 sizeHint %dx%d | 可见 %s"
      % (page.width(), page.height(),
         page.sizeHint().width(), page.sizeHint().height(), page.isVisible()))
print("    最小 sizeHint: %dx%d" % (page.minimumSizeHint().width(),
                                    page.minimumSizeHint().height()))

# 找到保存按钮
save_btn = None
for btn in page.findChildren(QPushButton):
    if "保存" in btn.text():
        save_btn = btn
        break

if save_btn is None:
    print("!! 找不到保存按钮")
else:
    print("\n保存按钮: 文案=%r 几何=%dx%d @(%d,%d) 可见=%s 启用=%s"
          % (save_btn.text(), save_btn.width(), save_btn.height(),
             save_btn.x(), save_btn.y(), save_btn.isVisible(),
             save_btn.isEnabled()))
    # 相对页面的位置 vs 页面可视高度
    top_left = save_btn.mapTo(page, QPoint(0, 0))
    bottom = top_left.y() + save_btn.height()
    print("    相对页面: y=%d..%d | 页面高度=%d | %s"
          % (top_left.y(), bottom, page.height(),
             "在可视区内 ✓" if 0 <= top_left.y() and bottom <= page.height()
             else "★ 超出可视区（点不到）"))

# 列表里所有按钮的位置，看谁被挤出去了
print("\nAI 页里所有按钮的纵向位置：")
for btn in page.findChildren(QPushButton):
    tl = btn.mapTo(page, QPoint(0, 0))
    out = "" if (tl.y() >= 0 and tl.y() + btn.height() <= page.height()) else "  ← 超出"
    print("    %-18s y=%4d..%-4d h=%-3d%s"
          % (btn.text()[:18], tl.y(), tl.y() + btn.height(), btn.height(), out))

# 直接调用一次保存，确认函数本身是否正常
print("\n直接调用 _save_ai_settings：")
try:
    mw._save_ai_settings()
    pump(200)
    print("    状态栏:", mw._status.text()[:80])
except Exception as exc:  # noqa: BLE001
    print("    抛异常:", type(exc).__name__, exc)

sys.stdout.flush()
os._exit(0)
