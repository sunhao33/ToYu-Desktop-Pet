"""Inspect the AI page and the timer widget at the current minimum window size,
looking for widgets squeezed to nothing / text not visible.
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QComboBox,
    QScrollArea, QSpinBox, QCheckBox, QTextEdit, QPlainTextEdit
)

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


INPUT_TYPES = (QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit)

mw = MainWindow()
mw.show()
pump(700)
mw.resize(mw.minimumWidth(), 839)
pump(600)
print("窗口: %dx%d  最小宽 %d" % (mw.width(), mw.height(), mw.minimumWidth()))

# ── AI 页 ──────────────────────────────────────────────────
mw._on_page_switch(3, "AI")
pump(500)
page = mw._page_stack.widget(3)
print("\n=== AI 页（可见区域 %dx%d）===" % (page.width(), page.height()))
tiny = []
for w in page.findChildren(QWidget):
    if not w.isVisible():
        continue
    if isinstance(w, INPUT_TYPES):
        ok = w.width() >= 80 and w.height() >= 18
        flag = "" if ok else "   <== 过小！"
        txt = ""
        if isinstance(w, QLabel):
            txt = w.text()[:20]
        elif hasattr(w, "currentText"):
            txt = w.currentText()[:20]
        elif hasattr(w, "text"):
            try:
                txt = w.text()[:20]
            except Exception:
                txt = ""
        print("   %-14s %4dx%-3d x=%-4d %s%s" % (type(w).__name__, w.width(), w.height(),
                                                w.x(), repr(txt), flag))
        if not ok:
            tiny.append((type(w).__name__, w.width(), w.height(), txt))
    elif isinstance(w, QLabel) and w.text():
        if w.width() < 30 or w.height() < 12:
            tiny.append(("QLabel", w.width(), w.height(), w.text()[:24]))

print("  过小控件: %s" % (tiny if tiny else "无"))

# ── 工具页 → 效率工具 → 倒计时器 ───────────────────────────
mw._on_page_switch(2, "工具")
pump(300)
mw._switch_tools_page(0)
pump(500)
holder = mw._tools_stack.widget(0)
timer = mw._timer_widget
print("\n=== 效率工具页（可见 %dx%d）===" % (holder.width(), holder.height()))
print("  倒计时器控件: %dx%d 可见=%s" % (timer.width(), timer.height(), timer.isVisible()))
for w in timer.findChildren(QWidget):
    if not w.isVisible():
        continue
    txt = ""
    if isinstance(w, QLabel):
        txt = w.text()[:28]
    elif hasattr(w, "text"):
        try:
            txt = w.text()[:28]
        except Exception:
            txt = ""
    if isinstance(w, (QLabel,) + INPUT_TYPES) or w.height() < 20:
        print("   %-14s %4dx%-3d x=%-4d y=%-4d %s" % (type(w).__name__, w.width(), w.height(),
                                                      w.x(), w.y(), repr(txt)))

# 时间显示标签是否被压没
cands = [w for w in timer.findChildren(QLabel) if w.isVisible()]
print("\n  倒计时器里的文字标签：")
for w in cands:
    fm = w.fontMetrics()
    need = fm.horizontalAdvance(w.text()) + 4
    print("     %-22s 宽=%4d 需要=%4d %s" % (repr(w.text()[:20]), w.width(), need,
                                             "<== 文字被裁！" if w.width() < need and w.text() else ""))

sys.stdout.flush()
os._exit(0)
