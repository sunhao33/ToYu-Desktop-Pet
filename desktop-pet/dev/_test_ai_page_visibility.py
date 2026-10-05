"""回归测试：AI 页可见性与保存反馈。

背景（真实反馈）：
  用户点「保存 AI 设置」觉得"没反应"。排查发现两件事：
    1) 保存其实成功了，但反馈只有底部状态栏一行小灰字，太不显眼
    2) AI 页内容高度超过可视区却没有滚动区 —— Qt 会把卡片压缩到
       小于最小高度，下方内容（记忆卡片、指标卡片）被压掉看不见

本测试锁住这两点：
  * 内容会溢出的页面都必须是滚动区，且内容能被完整访问
  * 保存后有**看得见**的提示（toast），并且会自动消失
  * 各个按钮在可视区内、能真正被点中（不会被别的控件盖住）
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QPushButton, QScrollArea, QWidget,
)

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=200):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


PAGES = ("宠物", "功能", "工具", "AI")

mw = MainWindow()
mw.show()
pump(700)
mw._on_start_pet()
pump(700)

# ══════════════════════════════════════════════════════════
# 1. 会溢出的页面必须可滚动
# ══════════════════════════════════════════════════════════
scrolled = {}
for i, name in enumerate(PAGES):
    widget = mw._page_stack.widget(i)
    scrolled[name] = isinstance(widget, QScrollArea)
    check("%s页是滚动区" % name, isinstance(widget, QScrollArea),
          type(widget).__name__)

# AI 页内容确实超过可视区 -> 必须有滚动条可滚
ai_area = mw._page_stack.widget(3)
ai_inner = ai_area.widget()
check("AI 页内容高于可视区（确实需要滚动）",
      ai_inner.sizeHint().height() > ai_area.viewport().height(),
      "内容 %d vs 可视 %d" % (ai_inner.sizeHint().height(),
                              ai_area.viewport().height()))
pump(300)
check("AI 页出现纵向滚动条",
      ai_area.verticalScrollBar().maximum() > 0,
      "可滚动范围 %d" % ai_area.verticalScrollBar().maximum())

# 没有页面在水平方向需要滚动（横向滚动 = 内容被裁）
# 注意：必须**先切到该页**再测量 —— Qt 会把隐藏页面保持在一个很小的
# 默认尺寸，在隐藏状态下测出来的横向溢出是假象（真实踩过这个坑）
h_over = []
for i, name in enumerate(PAGES):
    mw._on_page_switch(i, name)
    pump(400)
    w = mw._page_stack.widget(i)
    if isinstance(w, QScrollArea) and w.horizontalScrollBar().maximum() > 0:
        h_over.append((name, w.horizontalScrollBar().maximum()))
check("没有页面需要横向滚动", not h_over, str(h_over))

# ══════════════════════════════════════════════════════════
# 2. 卡片不再被压缩到小于最小高度
# ══════════════════════════════════════════════════════════
mw._page_btns["AI"].click()
pump(500)
squeezed = []
for card in ai_inner.findChildren(QWidget):
    if card.layout() is None or not card.isVisible():
        continue
    need = card.minimumSizeHint().height()
    if need > 0 and card.height() > 0 and card.height() + 2 < need:
        squeezed.append((type(card).__name__, card.height(), need))
check("AI 页没有被压缩的卡片", not squeezed, str(squeezed[:3]))

# ══════════════════════════════════════════════════════════
# 3. 保存按钮在可视区内、可点中
# ══════════════════════════════════════════════════════════
save_btn = None
for btn in ai_inner.findChildren(QPushButton):
    if "保存" in btn.text() and "AI" in btn.text():
        save_btn = btn
        break
check("找到保存按钮", save_btn is not None)

if save_btn is not None:
    tl = save_btn.mapTo(ai_area.viewport(), QPoint(0, 0))
    visible = 0 <= tl.y() and tl.y() + save_btn.height() <= ai_area.viewport().height()
    check("保存按钮在可视区内", visible,
          "y=%d..%d 可视 h=%d" % (tl.y(), tl.y() + save_btn.height(),
                                  ai_area.viewport().height()))
    # 滚动到底部后仍在（说明滚动不会把它弄丢）
    ai_area.verticalScrollBar().setValue(ai_area.verticalScrollBar().maximum())
    pump(300)
    tl2 = save_btn.mapTo(ai_area.viewport(), QPoint(0, 0))
    check("滚动到底部后按钮仍可见",
          tl2.y() + save_btn.height() > 0 and tl2.y() < ai_area.viewport().height(),
          "y=%d" % tl2.y())
    ai_area.verticalScrollBar().setValue(0)
    pump(200)

# ══════════════════════════════════════════════════════════
# 4. 保存后有看得见的提示
# ══════════════════════════════════════════════════════════
check("初始没有 toast", getattr(mw, "_toast_label", None) is None
      or not mw._toast_label.isVisible())

mw._save_ai_settings()
pump(400)
toast = getattr(mw, "_toast_label", None)
check("保存后弹出 toast", toast is not None and toast.isVisible())
check("toast 文案说明已保存", toast is not None and "已保存" in toast.text(),
      toast.text() if toast else "")
check("状态栏也同步更新", "已保存" in mw._status.text(), mw._status.text()[:40])
check("toast 在窗口内", toast is not None
      and 0 <= toast.x() and toast.x() + toast.width() <= mw.width(),
      "x=%d w=%d 窗口宽=%d" % (toast.x(), toast.width(), mw.width())
      if toast else "")
check("toast 有可见的样式（不是透明）",
      toast is not None and "background" in toast.styleSheet(),
      toast.styleSheet()[:60] if toast else "")

# 自动消失
timer = getattr(mw, "_toast_timer", None)
check("toast 带自动消失定时器", timer is not None and timer.isActive())
mw._hide_toast()
pump(200)
check("toast 可被隐藏", toast is not None and not toast.isVisible())

# 失败时也有明显提示（构造一个必然失败的情况）
orig_input = mw._ai_api_base_input


class _Boom:
    def text(self):
        raise RuntimeError("模拟读取失败")


mw._ai_api_base_input = _Boom()
mw._save_ai_settings()
pump(300)
check("保存失败时也弹明显提示",
      mw._toast_label is not None and mw._toast_label.isVisible()
      and "失败" in mw._toast_label.text(),
      mw._toast_label.text()[:50] if mw._toast_label else "")
mw._ai_api_base_input = orig_input

# ══════════════════════════════════════════════════════════
# 5. 记忆与指标卡片都能滚到（之前被压缩看不见）
# ══════════════════════════════════════════════════════════
check("记忆卡片存在", getattr(mw, "_memory_card", None) is not None)
check("指标卡片存在", getattr(mw, "_metrics_card", None) is not None)
check("记忆卡片没有被子控件裁掉（高度合理）",
      mw._memory_card.height() >= mw._memory_card.minimumSizeHint().height() - 2,
      "h=%d 最小=%d" % (mw._memory_card.height(),
                        mw._memory_card.minimumSizeHint().height()))
check("指标卡片没有被子控件裁掉（高度合理）",
      mw._metrics_card.height() >= mw._metrics_card.minimumSizeHint().height() - 2,
      "h=%d 最小=%d" % (mw._metrics_card.height(),
                        mw._metrics_card.minimumSizeHint().height()))

# ══════════════════════════════════════════════════════════
# 6. 窗口缩到最小尺寸时依然可用
# ══════════════════════════════════════════════════════════
mw.resize(mw.minimumWidth(), mw.minimumHeight())
pump(500)
mw._page_btns["AI"].click()
pump(400)
ai_area2 = mw._page_stack.widget(3)
check("最小尺寸下 AI 页仍可滚动",
      ai_area2.verticalScrollBar().maximum() > 0,
      "可滚动 %d" % ai_area2.verticalScrollBar().maximum())
save_btn2 = None
for btn in ai_area2.widget().findChildren(QPushButton):
    if "保存" in btn.text() and "AI" in btn.text():
        save_btn2 = btn
        break
check("最小尺寸下保存按钮仍存在", save_btn2 is not None)

# 同样要先切过去再量
h_over2 = []
for i, name in enumerate(PAGES):
    mw._on_page_switch(i, name)
    pump(400)
    w = mw._page_stack.widget(i)
    if isinstance(w, QScrollArea) and w.horizontalScrollBar().maximum() > 0:
        h_over2.append((name, w.horizontalScrollBar().maximum()))
check("最小尺寸下也没有横向溢出", not h_over2, str(h_over2))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-40s %s" % (status, name, extra[:52]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
