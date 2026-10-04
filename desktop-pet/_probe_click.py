"""Debug: does a real click actually reach the 保存 AI 设置 button?"""

import os
import sys
import time

os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QPoint, Qt  # noqa: E402
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
mw._page_btns["AI"].click()
pump(600)

page = mw._page_stack.widget(3)
save_btn = next(b for b in page.findChildren(QPushButton) if "保存" in b.text())

# 记录信号是否真的触发
fired = []
orig = mw._save_ai_settings


def spy():
    fired.append(True)
    return orig()


mw._save_ai_settings = spy
# 注意：clicked 连的是原函数对象，重新赋值不影响连接；这里用另一种方式验证
save_btn.click()
pump(300)
print("按钮 click() 后状态栏:", mw._status.text()[:60])

# 关键：看按钮中心的实际落点是谁
center = save_btn.mapToGlobal(QPoint(save_btn.width() // 2, save_btn.height() // 2))
print("\n按钮中心全局坐标:", center.x(), center.y())
print("按钮全局矩形:", save_btn.mapToGlobal(QPoint(0, 0)).x(),
      save_btn.mapToGlobal(QPoint(0, 0)).y(),
      save_btn.width(), save_btn.height())

# 该位置最顶层的控件是谁？
top = app.widgetAt(center)
print("该坐标最顶层控件:", type(top).__name__ if top else None,
      repr(top.text()[:30]) if top is not None and hasattr(top, "text") else "")
print("是否就是保存按钮:", top is save_btn)

if top is not save_btn and top is not None:
    # 一路往上找，看它属于哪个卡片
    w = top
    chain = []
    while w is not None and w is not page:
        chain.append("%s(%s)" % (type(w).__name__, w.objectName() or "-"))
        w = w.parentWidget()
    print("顶层控件祖先链:", " ← ".join(chain[:6]))

# 页面被压缩的情况：对比各卡片的期望高度与实际高度
print("\nAI 页里的卡片高度（实际 vs 需要）：")
from PyQt6.QtWidgets import QFrame  # noqa: E402
for i, card in enumerate(page.findChildren(QFrame)):
    if card.objectName() == "card" or card.layout() is not None:
        title = ""
        for lb in card.findChildren(type(save_btn).__mro__[0]):
            pass
        need = card.minimumSizeHint().height()
        if card.height() > 0:
            flag = "  ← 被压缩" if card.height() + 2 < need else ""
            print("    %-28s 实际 h=%-4d 最小 h=%-4d%s"
                  % (type(card).__name__, card.height(), need, flag))

sys.stdout.flush()
os._exit(0)
