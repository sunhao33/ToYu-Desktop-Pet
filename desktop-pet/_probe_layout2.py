"""Find which widgets force the horizontal overflow on the pet / tools pages."""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget, QScrollArea, QLabel  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402


def pump(ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
mw.resize(680, 700)
pump(400)


def walk(widget, depth=0, max_depth=3):
    """打印控件树与最小尺寸，找出撑宽布局的元凶。"""
    lines = []
    for child in widget.findChildren(QWidget, "", Qt.FindChildOption.FindDirectChildrenOnly):
        if not child.isVisible():
            continue
        hint = child.minimumSizeHint()
        ms = child.minimumSize()
        lines.append("%s%-16s minHint=%4dx%-4d minSize=%4dx%-4d size=%4dx%-4d  %s"
                     % ("  " * depth, type(child).__name__,
                        hint.width(), hint.height(), ms.width(), ms.height(),
                        child.width(), child.height(),
                        (child.objectName() or "")))
        if depth < max_depth:
            lines.extend(walk(child, depth + 1, max_depth))
    return lines


def report(title, area_or_widget):
    print("\n" + "=" * 96)
    print(title)
    print("=" * 96)
    if isinstance(area_or_widget, QScrollArea):
        inner = area_or_widget.widget()
        vw = area_or_widget.viewport().width()
        print("  视口宽 %d | 内容最小宽 %d | 横向需滚动 %d px"
              % (vw, inner.minimumSizeHint().width(),
                 area_or_widget.horizontalScrollBar().maximum()))
        print("  内容控件: %s" % type(inner).__name__)
        for line in walk(inner, 0, 3):
            print("  " + line)


# 宠物页
mw._on_page_switch(0, "宠物")
pump(300)
report("宠物页（外层 QScrollArea）", mw._page_stack.widget(0))

# 工具页三个子页
mw._on_page_switch(2, "工具")
pump(300)
tools_page = mw._page_stack.widget(2)
for i in range(3):
    mw._switch_tools_page(i)
    pump(300)
    sub = mw._tools_stack.widget(i)
    areas = sub.findChildren(QScrollArea)
    print("\n" + "=" * 96)
    print("工具页子页 %d：%s   子页最小宽 %d"
          % (i, type(sub).__name__, sub.minimumSizeHint().width()))
    print("=" * 96)
    print("  子页直接子控件:")
    for line in walk(sub, 1, 2):
        print("  " + line)
    for a in areas:
        if a.horizontalScrollBar().maximum() > 0:
            report("  -> 该子页内出现横向滚动的区域", a)

sys.stdout.flush()
os._exit(0)
