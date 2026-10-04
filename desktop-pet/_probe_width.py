"""Find which widgets drive the minimum width of the 功能 / 工具 pages."""

import os
import sys
import time

os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QScrollArea, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
)

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def widest(root, top=6):
    """列出最宽的控件（最小宽度维度）。"""
    rows = []
    for w in root.findChildren(QWidget):
        if not w.isVisible():
            continue
        h = w.minimumSizeHint().width()
        if h > 120:
            rows.append((h, type(w).__name__,
                         (w.text()[:26] if isinstance(w, (QLabel, QPushButton, QLineEdit))
                          else (w.objectName() or ""))))
    rows.sort(reverse=True)
    return rows[:top]


mw = MainWindow()
mw.resize(1120, 880)
mw.show()
pump(900)
mw._on_start_pet()
pump(700)

for idx, name in ((1, "功能"), (2, "工具")):
    mw._on_page_switch(idx, name)
    pump(600)
    area = mw._page_stack.widget(idx)
    inner = area.widget() if isinstance(area, QScrollArea) else area
    print("=== %s页 ===" % name)
    print("  内容 minimumSizeHint 宽 = %d" % inner.minimumSizeHint().width())
    for width, cls, extra in widest(inner):
        print("    minW=%-5d %-14s %s" % (width, cls, extra))

    # 找直接子级的大块
    print("  直接子级：")
    for child in inner.findChildren(QWidget, "", Qt.FindChildOption.FindDirectChildrenOnly):
        if child.isVisible():
            print("    %-14s minW=%-5d 实际宽=%-5d"
                  % (type(child).__name__, child.minimumSizeHint().width(),
                     child.width()))

    if name == "工具":
        for s in range(3):
            mw._switch_tools_page(s)
            pump(500)
            sub = mw._tools_stack.currentWidget()
            print("  --- 工具子页 %d (%s) minW=%d ---"
                  % (s, type(sub).__name__, sub.minimumSizeHint().width()))
            for width, cls, extra in widest(sub, top=4):
                print("      minW=%-5d %-14s %s" % (width, cls, extra))

sys.stdout.flush()
os._exit(0)
