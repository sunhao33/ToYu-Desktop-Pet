"""Regression test: study-statistics charts must refresh for both data and no-data dates.

防止再犯：_on_calendar_date_selected 在没有完成记录时提前 return，
导致两幅统计图从不刷新（表现为图表空白或停留在上一次的选择）。
"""

import json
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 被测的图表失败分支会抛异常，必须先装产品自带的崩溃防护，
# 否则 PyQt6 会直接 abort 进程（这正是防护存在的意义）
import main as toyu_main  # noqa: E402

toyu_main._install_crash_guard()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=250):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


HIST = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
os.makedirs(os.path.dirname(HIST), exist_ok=True)
backup = open(HIST, encoding="utf-8").read() if os.path.exists(HIST) else None

DATA_DATE = "2026-10-03"
EMPTY_DATE = "2026-09-20"
with open(HIST, "w", encoding="utf-8") as fh:
    json.dump({DATA_DATE: [
        {"text": "写竞赛文档", "time": "10:20", "duration": 1800},
        {"text": "修 bug", "time": "14:05", "duration": 900},
        {"text": "看论文", "time": "16:40", "duration": 2700},
    ]}, fh, ensure_ascii=False)

try:
    mw = MainWindow()
    mw.resize(1100, 900)
    mw.move(20, 20)
    mw.show()
    pump(400)
    mw._page_btns["工具"].click()
    pump(250)
    mw._switch_tools_page(2)
    pump(250)
    mw._switch_stat_tab(0)
    pump(200)

    # 记录 _update_charts 的实际调用
    calls = []
    orig = mw._update_charts

    def traced(date_str, tasks):
        calls.append((date_str, len(tasks)))
        return orig(date_str, tasks)

    mw._update_charts = traced

    def pix(name):
        w = getattr(mw, name)
        src = getattr(w, "_src_pixmap", None)
        shown = w.pixmap()
        return src, shown

    # ── 1. 有数据的日期 ─────────────────────────────────────
    mw._calendar.date_selected.emit(DATA_DATE)
    pump(1000)
    check("有数据日期调用了图表更新", (DATA_DATE, 3) in calls, str(calls))
    src, shown = pix("_pie_label")
    check("环形图已生成", src is not None and not src.isNull(),
          "%s" % (("%dx%d" % (src.width(), src.height())) if src else "无"))
    check("环形图已缩放到控件上", not shown.isNull(),
          "%dx%d" % (shown.width(), shown.height()))
    src_bar, shown_bar = pix("_bar_label")
    check("柱状图已生成", src_bar is not None and not src_bar.isNull())
    check("柱状图已缩放到控件上", not shown_bar.isNull())

    # ── 2. 无数据的日期（回归点）────────────────────────────
    calls.clear()
    mw._calendar.date_selected.emit(EMPTY_DATE)
    pump(1000)
    check("无数据日期也调用了图表更新", (EMPTY_DATE, 0) in calls,
          "这是本次修复的核心：以前提前 return，图表完全不刷新 -> %s" % calls)
    src2, shown2 = pix("_pie_label")
    check("无数据时环形图仍会重画（显示暂无提示）", src2 is not None and not src2.isNull())
    check("无数据时柱状图仍会重画（近 7 天趋势）",
          pix("_bar_label")[0] is not None and not pix("_bar_label")[0].isNull())

    # ── 3. 切回有数据日期，图必须跟着换 ──────────────────────
    first_bytes = src2.cacheKey()
    mw._calendar.date_selected.emit(DATA_DATE)
    pump(1000)
    src3, _ = pix("_pie_label")
    check("切回有数据日期后图发生变化", src3 is not None and src3.cacheKey() != first_bytes)

    # ── 4. 柱状图在两种日期下都要有内容 ──────────────────────
    bar_data = pix("_bar_label")[0]
    check("柱状图尺寸正常", bar_data is not None and bar_data.width() > 100,
          "%dx%d" % (bar_data.width(), bar_data.height()) if bar_data else "无")

    # ── 5. 图表失败时必须给出可见提示（而不是空白）──────────
    def boom(date_str, tasks):
        raise RuntimeError("模拟 matplotlib 失败")

    mw._update_charts = boom
    try:
        mw._calendar.date_selected.emit(DATA_DATE)
        pump(400)
    except Exception:
        pass          # 会被崩溃防护接住，这里只关心界面提示
    text = mw._pie_label.text()
    check("图表失败时控件上显示原因", "失败" in text, repr(text[:40]))
    check("失败时旧图被清掉", getattr(mw._pie_label, "_src_pixmap", None) is None)

finally:
    if backup is not None:
        open(HIST, "w", encoding="utf-8").write(backup)
    elif os.path.exists(HIST):
        os.remove(HIST)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-38s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
