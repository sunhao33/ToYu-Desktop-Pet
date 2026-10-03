"""Measure the geometry of a plan row in the flow window."""

import os
import sys
import time

os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QPushButton, QLabel, QCheckBox, QWidget  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


LONG = "整理今天的学习记录（这条名字很长用来测宽度）"
mw = MainWindow()
mw.show()
pump(800)
mw._on_start_pet()
pump(400)
for t in ("写竞赛设计文档", LONG):
    mw._todo_widget._input.setText(t)
    mw._todo_widget._on_add()
    pump(250)

mw.enter_flow_mode()
pump(1000)
fw = mw._flow_window
fw.toggle_task_timer("写竞赛设计文档")
pump(2200)

rows = [c for c in fw._plan_container.children()
        if isinstance(c, QWidget) and c.layout() is not None]
print("计划行数:", len(rows))
for f in rows[:2]:
    print("行宽 %d 高 %d:" % (f.width(), f.height()))
    lay = f.layout()
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is None:
            continue
        if isinstance(w, QLabel):
            extra = repr(w.text()[:26])
        elif isinstance(w, (QPushButton, QCheckBox)):
            extra = repr(w.text())
        else:
            extra = ""
        print("   %-12s %3dx%-3d x=%-4d %s"
              % (type(w).__name__, w.width(), w.height(), w.x(), extra))
    print()

print("鼠标可点区域检查（按钮高度应 >= 20）：")
for f in rows[:1]:
    lay = f.layout()
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if isinstance(w, QPushButton):
            ok = "OK" if w.height() >= 20 and w.width() >= 20 else "太小！"
            print("   %s %dx%d %s" % (w.text(), w.width(), w.height(), ok))

mw.exit_flow_mode()
pump(300)
try:
    mw._todo_widget.todos = [
        t for t in mw._todo_widget.todos
        if not t.text.startswith(("写竞赛设计文档", "整理今天的学习记录"))]
    mw._todo_widget._save_todos()
except Exception:
    pass
sys.stdout.flush()
os._exit(0)
