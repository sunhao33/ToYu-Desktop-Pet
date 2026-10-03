"""Reproduce the empty study-statistics charts and surface the real exception."""

import os
import sys
import traceback

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()
mw.show()
app.processEvents()

print("=== 1. matplotlib 是否可用 ===")
try:
    import matplotlib
    print("  matplotlib 版本:", matplotlib.__version__)
except Exception as exc:  # noqa: BLE001
    print("  导入失败:", type(exc).__name__, exc)

print("\n=== 2. 图表控件初始状态 ===")
pie, bar = mw._pie_label, mw._bar_label
print("  _pie_label 文本:", repr(pie.text()))
print("  _bar_label 文本:", repr(bar.text()))
print("  控件尺寸:", pie.width(), "x", pie.height(), "|", bar.width(), "x", bar.height())

print("\n=== 3. 直接调用 _update_charts（用带数据的日期）===")
tasks = [
    {"text": "写竞赛文档", "done_at": "2026-10-03 10:20:00", "elapsed": 1800},
    {"text": "改 bug", "done_at": "2026-10-03 14:05:00", "elapsed": 900},
    {"text": "看论文", "done_at": "2026-10-03 16:40:00", "elapsed": 2700},
]
try:
    mw._update_charts("2026-10-03", tasks)
    print("  调用成功，无异常")
except Exception as exc:  # noqa: BLE001
    print("  ✗ 抛出异常:", type(exc).__name__, exc)
    traceback.print_exc()

print("\n=== 4. 调用后控件是否真的有图 ===")
def describe(label, w):
    pix = getattr(w, "_src_pixmap", None)
    if pix is None:
        print("  %s: 无 pixmap（只有文字: %r）" % (label, w.text()[:40]))
        return False
    print("  %s: pixmap %dx%d, isNull=%s" % (label, pix.width(), pix.height(), pix.isNull()))
    return not pix.isNull()

ok_pie = describe("_pie_label", pie)
ok_bar = describe("_bar_label", bar)

print("\n=== 5. 走真实入口：_refresh_charts_for_date ===")
os.makedirs(os.path.expanduser("~/.desktop_pet"), exist_ok=True)
hist = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
print("  历史文件:", hist, "存在:", os.path.exists(hist))
mw._refresh_charts_for_date("2026-10-03")
app.processEvents()
describe("_pie_label(刷新后)", pie)
describe("_bar_label(刷新后)", bar)

print("\n=== 6. 切换统计子页 ===")
try:
    mw._switch_stat_tab(0)
    app.processEvents()
    print("  切到「学习统计」子页: 当前 index =", mw._stat_stack.currentIndex())
    mw._switch_stat_tab(1)
    app.processEvents()
    print("  切到「屏幕时间」子页: 当前 index =", mw._stat_stack.currentIndex())
    mw._switch_stat_tab(0)
    app.processEvents()
except Exception as exc:  # noqa: BLE001
    print("  切换抛异常:", type(exc).__name__, exc)

print("\n=== 7. 结论 ===")
if not (ok_pie and ok_bar):
    print("  图表未生成 → 上面的异常/信息就是原因")
else:
    print("  图表生成正常，问题可能出在刷新时机或尺寸为 0")
print("  _pie_label 尺寸:", pie.width(), pie.height(), "（宽高为 0 时 _ScaledLabel 无法缩放）")
