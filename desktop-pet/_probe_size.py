"""Measure the true required size of every page: find the smallest window size at
which no page (and no tool sub-page) needs horizontal scrolling, and no widget
gets squeezed below its minimum.
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QScrollArea  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

PAGES = ["宠物", "功能", "工具", "AI"]


def pump(ms=250):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def open_page(mw, label, sub=None):
    idx = PAGES.index(label)
    mw._on_page_switch(idx, label)
    pump(250)
    if label == "工具" and sub is not None:
        mw._switch_tools_page(sub)
        pump(300)


def overflow_at(mw, width, height=820):
    """把窗口设为指定尺寸，返回各页面/子页的横向溢出与过窄控件。"""
    mw.setMinimumSize(200, 200)          # 临时解除限制以便测试
    mw.resize(width, height)
    pump(450)
    problems = []
    for label in PAGES:
        subs = range(3) if label == "工具" else [None]
        for sub in subs:
            open_page(mw, label, sub)
            if label == "工具":
                holder = mw._tools_stack.currentWidget()
            else:
                holder = mw._page_stack.currentWidget()
            tag = "%s%s" % (label, ("子页%d" % sub) if sub is not None else "")
            for area in holder.findChildren(QScrollArea):
                m = area.horizontalScrollBar().maximum()
                if m > 0:
                    problems.append((tag, "横向滚动 %d px" % m))
            # 控件被压到低于自身最小宽度（内容会被画掉）
            for area in holder.findChildren(QScrollArea):
                inner = area.widget()
                if inner is None:
                    continue
                need = inner.minimumSizeHint().width()
                if inner.width() < need - 2:
                    problems.append((tag, "内容被压缩 %d < %d" % (inner.width(), need)))
    return problems


mw = MainWindow()
mw.show()
pump(600)

print("=" * 90)
print("逐尺寸测量：找到「所有页面都不裁内容」的最小宽度")
print("=" * 90)
good = None
for width in (900, 960, 1000, 1040, 1080, 1120, 1160, 1200, 1240, 1280):
    problems = overflow_at(mw, width)
    status = "OK" if not problems else "有问题 %d 处" % len(problems)
    print("  宽 %4d : %s" % (width, status))
    if problems:
        for tag, msg in problems[:4]:
            print("        [%s] %s" % (tag, msg))
    elif good is None:
        good = width

print("\n结论：不裁内容的最小宽度 = %s" % (good if good else ">1280，需要更宽"))

# 再看高度需求
if good:
    print("\n逐高度测量（宽固定 %d）：" % good)
    for height in (600, 640, 680, 720, 760, 800):
        mw.setMinimumSize(200, 200)
        mw.resize(good, height)
        pump(400)
        open_page(mw, "工具", 0)
        holder = mw._tools_stack.currentWidget()
        v_over = 0
        for area in holder.findChildren(QScrollArea):
            v_over = max(v_over, area.verticalScrollBar().maximum())
        print("  高 %4d : 工具页纵向滚动 %d px" % (height, v_over))

sys.stdout.flush()
os._exit(0)
