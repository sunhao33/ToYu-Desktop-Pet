"""Regression test: 心流模式计划项的独立计时。

要点：
  * 每个计划项有独立的计时开关与累计时长
  * 同一时刻只跑一项（切换时上一项停止增长）
  * 用量持久化到 %APPDATA%\\ToYu\\flow_timers.json
  * 勾选完成时把该项计时写进今日历史
"""

import json
import os
import sys
import time
from datetime import date

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication, QPushButton  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402
from ui.flow_window import FLOW_TIMER_FILE  # noqa: E402

HIST = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
TODO_FILE = os.path.join(os.path.expanduser("~"), ".desktop_pet", "todos.json")
hist_before = open(HIST, encoding="utf-8").read() if os.path.exists(HIST) else None
todo_before = open(TODO_FILE, encoding="utf-8").read() if os.path.exists(TODO_FILE) else None
timer_before = open(FLOW_TIMER_FILE, encoding="utf-8").read() if os.path.exists(FLOW_TIMER_FILE) else None

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


A = "任务A-独立计时测试"
B = "任务B-独立计时测试"
mw = MainWindow()
mw.show()
pump(500)
mw._on_start_pet()
pump(400)

try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos if t.text not in (A, B)]
    mw._todo_widget._save_todos()
except Exception:
    pass

mw.enter_flow_mode()
pump(900)
fw = mw._flow_window
fw._plan_input.setText(A)
fw._on_add_task()
pump(500)
fw._plan_input.setText(B)
fw._on_add_task()
pump(500)

check("两项都在计划栏", fw._plan_list.count() - 1 == 2, "%d 行" % (fw._plan_list.count() - 1))

# ── 1. 每项有独立的计时按钮 ─────────────────────────────────
buttons = [b for b in fw._plan_container.findChildren(QPushButton) if "计时" in b.text()]
check("每个计划项都有计时按钮", len(buttons) == 2, "%d 个：%s" % (len(buttons), [b.text() for b in buttons]))

# ── 2. 开始给 A 计时 ────────────────────────────────────────
fw.toggle_task_timer(A)
pump(3200)
a_secs = fw._task_secs(A)
check("A 项开始累计用时", a_secs >= 2, "A=%d 秒" % a_secs)
check("当前计时项为 A", fw._active_task == A, str(fw._active_task))
check("B 项仍为 0", fw._task_secs(B) == 0, "B=%d" % fw._task_secs(B))

active_btns = [b for b in fw._plan_container.findChildren(QPushButton) if "计时中" in b.text()]
check("计时中的那项按钮高亮为「计时中」", len(active_btns) == 1,
      [b.text() for b in active_btns])

# ── 3. 切到 B，A 应停止增长 ─────────────────────────────────
fw.toggle_task_timer(B)
pump(300)
a_after_switch = fw._task_secs(A)
pump(2200)
check("切换到 B 后当前项为 B", fw._active_task == B, str(fw._active_task))
check("切换后 A 不再增长", fw._task_secs(A) == a_after_switch,
      "切换时 %d -> 现在 %d" % (a_after_switch, fw._task_secs(A)))
check("B 开始累计", fw._task_secs(B) >= 1, "B=%d 秒" % fw._task_secs(B))

# ── 4. 再点同一项 = 暂停 ────────────────────────────────────
fw.toggle_task_timer(B)
b_paused = fw._task_secs(B)
pump(2200)
check("再点一次即暂停", fw._active_task is None, str(fw._active_task))
check("暂停后不再增长", fw._task_secs(B) == b_paused,
      "%d -> %d" % (b_paused, fw._task_secs(B)))

# ── 5. 落盘 ─────────────────────────────────────────────────
fw._flush_timers()
pump(300)
saved = json.load(open(FLOW_TIMER_FILE, encoding="utf-8")) if os.path.exists(FLOW_TIMER_FILE) else {}
today_saved = saved.get(date.today().isoformat(), {})
check("计时进度已落盘", A in today_saved or B in today_saved, str(today_saved))

# ── 6. 勾选完成后把该项计时写进今日历史 ─────────────────────
hist_now = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else {}
before_n = len(hist_now.get(date.today().isoformat(), []))
a_before = fw._task_secs(A)

boxes = [b for b in fw._plan_container.findChildren(type(buttons[0])) if b.text() == ""]
target_todo = next((t for t in mw._todo_widget.todos if t.text == A), None)
check("找到 A 的待办对象", target_todo is not None)
if target_todo is not None:
    fw._on_toggle_task(target_todo, True)
    pump(700)
    hist_after = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else {}
    today_after = hist_after.get(date.today().isoformat(), [])
    check("完成后写入历史", len(today_after) == before_n + 1,
          "%d -> %d" % (before_n, len(today_after)))
    rec = [x for x in today_after if x.get("text") == A]
    check("历史里带上了该项的计时", rec and rec[0].get("duration", 0) == a_before,
          "duration=%s，A 累计=%d" % ([x.get("duration") for x in rec], a_before))

fw._flush_timers()
mw.exit_flow_mode()
pump(400)

# 清理
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos if t.text not in (A, B)]
    mw._todo_widget._save_todos()
except Exception:
    pass
if hist_before is not None:
    open(HIST, "w", encoding="utf-8").write(hist_before)
if todo_before is not None:
    open(TODO_FILE, "w", encoding="utf-8").write(todo_before)
if timer_before is not None:
    open(FLOW_TIMER_FILE, "w", encoding="utf-8").write(timer_before)
elif os.path.exists(FLOW_TIMER_FILE):
    os.remove(FLOW_TIMER_FILE)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-36s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
