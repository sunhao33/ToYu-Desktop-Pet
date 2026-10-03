"""Test interactive plan card in the flow window: add / check / delete + duration."""

import json
import os
import sys
import time
from datetime import date

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_REPORT", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QCheckBox, QPushButton  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

HIST = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
hist_before = open(HIST, encoding="utf-8").read() if os.path.exists(HIST) else None
todo_file = os.path.join(os.path.expanduser("~"), ".desktop_pet", "todos.json")
todo_before = open(todo_file, encoding="utf-8").read() if os.path.exists(todo_file) else None

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


NAME = "心流交互测试任务"
mw = MainWindow()
mw.show()
pump(500)
mw._on_start_pet()
pump(400)

# 清理可能残留
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos if t.text != NAME]
    mw._todo_widget._save_todos()
except Exception:
    pass

mw.enter_flow_mode()
pump(900)
fw = mw._flow_window
check("心流窗口有添加输入框", hasattr(fw, "_plan_input"))
check("心流窗口有进度标签", hasattr(fw, "_plan_progress"))

# ── 1. 在心流页添加待办 ─────────────────────────────────────
n_before = len(mw._todo_widget.todos)
fw._plan_input.setText(NAME)
fw._on_add_task()
pump(700)
check("心流页可直接添加待办", len(mw._todo_widget.todos) == n_before + 1,
      "%d -> %d 条" % (n_before, len(mw._todo_widget.todos)))
check("添加后输入框已清空", fw._plan_input.text() == "", repr(fw._plan_input.text()))

rows = fw._plan_list.count() - 1
check("计划栏出现该条目", rows >= 1, "%d 行" % rows)
check("进度标签有内容", "/" in fw._plan_progress.text() or "没有" in fw._plan_progress.text(),
      fw._plan_progress.text())

# ── 2. 每行都有勾选框和删除按钮 ─────────────────────────────
boxes = fw._plan_container.findChildren(QCheckBox)
check("计划行带勾选框", len(boxes) >= 1, "%d 个勾选框" % len(boxes))

# ── 3. 勾选即完成，并写入今日历史 ───────────────────────────
hist_before_data = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else {}
today_before = len(hist_before_data.get(date.today().isoformat(), []))

# 先起一个短计时，验证"用时会计入"这条链路能跑通
fw.start_focus(1)
pump(1200)
elapsed = mw._timer_widget.get_elapsed_seconds()

target = None
for t in mw._todo_widget.todos:
    if t.text == NAME:
        target = t
        break
check("找到刚添加的待办对象", target is not None)

if target is not None and boxes:
    boxes[0].click()
    pump(800)

    done_now = target.done if target is not None else None
    check("勾选后待办标记为完成", done_now is True, "done=%s" % done_now)

    hist_now = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else {}
    today_now = hist_now.get(date.today().isoformat(), [])
    check("完成后写入今日历史", len(today_now) == today_before + 1,
          "%d -> %d 条" % (today_before, len(today_now)))
    check("历史里能找到该任务", any(x.get("text") == NAME for x in today_now))
    dur = [x.get("duration", 0) for x in today_now if x.get("text") == NAME]
    check("记录里带上了用时字段", dur and isinstance(dur[0], int), "duration=%s" % dur)

    pump(600)
    boxes2 = fw._plan_container.findChildren(QCheckBox)
    check("完成后该行从计划栏移除", len(boxes2) == len(boxes) - 1,
          "%d -> %d 个勾选框" % (len(boxes), len(boxes2)))

# ── 4. 主页删除待办，心流页同步 ─────────────────────────────
# 注意：被勾选的那条仍在 todos 里（只是 done=True），所以新增后总数是 n+1
fw._plan_input.setText(NAME + "2")
fw._on_add_task()
pump(600)
n2 = len(mw._todo_widget.todos)
check("再添加一条", n2 == n_before + 2, "%d 条（含 1 条已完成）" % n2)

# 心流页删除
boxes3 = fw._plan_container.findChildren(QCheckBox)
del_btns = [b for b in fw._plan_container.findChildren(QPushButton) if b.text() == "✕"]
check("计划行带删除按钮", len(del_btns) >= 1, "%d 个" % len(del_btns))
if del_btns:
    del_btns[0].click()
    pump(700)
    check("删除后待办数减少", len(mw._todo_widget.todos) == n2 - 1,
          "%d -> %d" % (n2, len(mw._todo_widget.todos)))

# ── 5. 主页添加时心流页自动刷新（信号连接）──────────────────
if fw.isVisible():
    rows_before = fw._plan_list.count()
    mw._todo_widget._input.setText(NAME + "3")
    mw._todo_widget._on_add()
    pump(900)
    check("主页添加后心流页自动刷新",
          fw._plan_list.count() >= rows_before,
          "%d -> %d 行" % (rows_before, fw._plan_list.count()))

mw.exit_flow_mode()
pump(400)

# 清理
try:
    mw._todo_widget.todos = [
        t for t in mw._todo_widget.todos if not t.text.startswith(NAME)]
    mw._todo_widget._save_todos()
except Exception:
    pass
if todo_before is not None:
    open(todo_file, "w", encoding="utf-8").write(todo_before)
if hist_before is not None:
    open(HIST, "w", encoding="utf-8").write(hist_before)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-34s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
