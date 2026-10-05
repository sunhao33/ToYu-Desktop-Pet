"""Render the study-statistics page on-screen and grab it, to see what the user sees."""

import os
import sys
import time

os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

OUT = r"C:\Users\asus\Desktop\Huabei\_work"
mw = MainWindow()
mw.resize(1000, 900)
mw.move(30, 30)          # 屏幕内，才会真正绘制
mw.show()


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


pump(500)

# 不启动宠物（避免写宠物图），直接进数据面板
mw._page_btns["工具"].click()
pump(400)
mw._switch_tools_page(2)          # 数据面板
pump(400)
mw._switch_stat_tab(0)            # 学习统计
pump(300)

print("=== 进入数据面板后的状态 ===")
print("  当前页 index:", mw._page_stack.currentIndex())
print("  工具子页 index:", mw._tools_stack.currentIndex())
print("  统计子页 index:", mw._stat_stack.currentIndex())
print("  _pie_label 可见:", mw._pie_label.isVisible(), "尺寸:", mw._pie_label.width(), "x", mw._pie_label.height())
print("  _bar_label 可见:", mw._bar_label.isVisible(), "尺寸:", mw._bar_label.width(), "x", mw._bar_label.height())

# 点一个日历日期（真实入口）
cal = mw._calendar
target = "2026-10-03"
print("\n=== 模拟点击日历日期 %s ===" % target)
try:
    cal.date_selected.emit(target)
except Exception as exc:  # noqa: BLE001
    print("  触发日期选择失败:", type(exc).__name__, exc)
pump(800)

import builtins
import traceback

# 把被吞掉的打印抓出来（windowed 程序看不到 print）
_captured = []
_orig_print = builtins.print


def _spy(*args, **kwargs):
    _captured.append(" ".join(str(a) for a in args))
    _orig_print(*args, **kwargs)


builtins.print = _spy

# 同时直接调用 _update_charts，绕过 try/except 看真实异常
print("\n=== 直接调用 _update_charts 看真实异常 ===")
try:
    mw._update_charts(target, [])
    print("  直接调用成功")
except Exception as exc:  # noqa: BLE001
    print("  ✗ 真实异常:", type(exc).__name__, exc)
    traceback.print_exc()

print("\n=== 被吞掉的输出 ===")
for line in _captured:
    if "error" in line.lower() or "Error" in line or "Chart" in line:
        print("  捕获:", line)
builtins.print = _orig_print

pie_pix = getattr(mw._pie_label, "_src_pixmap", None)
bar_pix = getattr(mw._bar_label, "_src_pixmap", None)
print("  _pie_label 原始 pixmap:", (pie_pix.width(), pie_pix.height()) if pie_pix else None)
print("  _bar_label 原始 pixmap:", (bar_pix.width(), bar_pix.height()) if bar_pix else None)
print("  _pie_label 当前显示 pixmap:", mw._pie_label.pixmap().width() if not mw._pie_label.pixmap().isNull() else "空")
print("  _bar_label 当前显示 pixmap:", mw._bar_label.pixmap().width() if not mw._bar_label.pixmap().isNull() else "空")

path = os.path.join(OUT, "stats_page.png")
ok = mw.grab().save(path)
print("\n抓图:", path, ok)

# 顺便把整个工具页也抓一张
tools_path = os.path.join(OUT, "stats_page_full.png")
mw._page_stack.currentWidget().grab().save(tools_path)
print("工具页抓图:", tools_path)

# 检查标签自身渲染出来是否空白
pie_only = os.path.join(OUT, "stats_pie_only.png")
mw._pie_label.grab().save(pie_only)
print("仅环形图控件:", pie_only)

mw.close()
print("done")
