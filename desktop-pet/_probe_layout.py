"""Resize health check: shrink the main window and find widgets clipped out of
their parent (which is exactly what "内容框里的内容看不见" looks like).
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QWidget, QScrollArea, QLabel, QPushButton, QFrame, QStackedWidget
)

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402


def pump(ms=120):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
pump(300)

SIZES = [(720, 800), (700, 760), (680, 700), (640, 680), (600, 640)]


def page_widgets():
    pages = {}
    for i, label in enumerate(("宠物", "功能", "工具", "AI")):
        pages[label] = mw._page_stack.widget(i)
    return pages


def clipped_children(root, limit=12):
    """找出几何上超出父容器可见区域的直接子控件。"""
    out = []
    for child in root.findChildren(QWidget, options=__import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.FindChildOption.FindDirectChildrenOnly):
        if not child.isVisible() or child.width() <= 1 or child.height() <= 1:
            continue
        # 允许 8px 余量（布局边距/阴影）
        parent_rect = root.rect().adjusted(-8, -8, 8, 8)
        cg = child.geometry()
        if not parent_rect.contains(cg):
            over_r = cg.right() - root.rect().right()
            over_b = cg.bottom() - root.rect().bottom()
            out.append((type(child).__name__, getattr(child, "objectName", "") or "-",
                        cg.x(), cg.y(), cg.width(), cg.height(), over_r, over_b))
        if len(out) >= limit:
            break
    return out


print("=" * 100)
print("缩放体检：不同窗口尺寸下被截断的控件")
print("=" * 100)

found = {}
for w, h in SIZES:
    mw.resize(w, h)
    pump(220)
    print("\n### 窗口 %dx%d （实际 %dx%d，最小 %dx%d）"
          % (w, h, mw.width(), mw.height(), mw.minimumWidth(), mw.minimumHeight()))
    for label, page in page_widgets().items():
        mw._on_page_switch(("宠物", "功能", "工具", "AI").index(label), label)
        pump(200)
        issues = clipped_children(page) if page else []
        # 滚动区域是否开启了横向滚动（内容比可视区宽时会隐藏右侧内容）
        hbars = []
        for area in (page.findChildren(QScrollArea) if page else []):
            if area.horizontalScrollBar().maximum() > 0:
                hbars.append("横向需滚动 +%d px" % area.horizontalScrollBar().maximum())
        if issues or hbars:
            print("  [%s页]" % label)
            for t, name, x, y, cw, ch, over_r, over_b in issues:
                print("     被截断: %-14s %-12s 位置(%4d,%4d) 尺寸%4dx%-4d 右溢出%3d 下溢出%3d"
                      % (t, name, x, y, cw, ch, over_r, over_b))
                found.setdefault(label, []).append((t, name, over_r, over_b))
            for hb in hbars:
                print("     %s" % hb)
                found.setdefault(label, []).append(("QScrollArea", hb, 0, 0))
        else:
            print("  [%s页] 正常" % label)

print("\n" + "=" * 100)
print("汇总：%s" % ("未发现截断问题" if not found else "存在问题的页面：" + ", ".join(found)))
for label, items in found.items():
    print("  %s页：%d 处" % (label, len(items)))
    seen = set()
    for t, name, over_r, over_b in items:
        key = (t, name)
        if key in seen:
            continue
        seen.add(key)
        print("     - %s %s" % (t, name))

sys.stdout.flush()
os._exit(1 if found else 0)
