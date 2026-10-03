"""Regression test for main-window tab switching.

防止再犯：切换动画复用了会被 Qt 删除的效果对象，
导致第二次点击标签时抛 RuntimeError、页面切不过去。
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


mw = MainWindow()
mw.show()
app.processEvents()

ORDER = ["宠物", "功能", "工具", "AI"]
expect_index = {label: i for i, label in enumerate(ORDER)}

# 页面顺序必须与按钮顺序一致，否则点击会切到别的页
check("页数 = 按钮数", mw._page_stack.count() == len(ORDER),
      "页 %d / 按钮 %d" % (mw._page_stack.count(), len(ORDER)))
check("按钮名称与预期一致", list(mw._page_btns.keys()) == ORDER, str(list(mw._page_btns.keys())))

def pump(ms):
    """让事件循环真正跑起来（不能用 sleep 顶替，否则动画永远走不到结束）。"""
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)


# 连点三轮：第一轮会触发效果对象创建，第二轮起验证复用是否安全
mismatch = []
no_fade = []
for round_no in range(3):
    for label in ORDER:
        mw._page_btns[label].click()
        pump(350)                 # 跑满动画时长 + 兜底定时器
        if mw._page_stack.currentIndex() != expect_index[label]:
            mismatch.append((round_no + 1, label, mw._page_stack.currentIndex()))
        widget = mw._page_stack.currentWidget()
        effect = widget.graphicsEffect()
        if effect is not None and effect.opacity() < 1.0:
            no_fade.append((round_no + 1, label, round(effect.opacity(), 2)))

check("三轮点击后页面都正确切换", not mismatch, str(mismatch))
check("动画结束后不透明度恢复 1.0", not no_fade, str(no_fade))

# 高亮互斥
checked = [k for k, b in mw._page_btns.items() if b.isChecked()]
check("只有一个标签处于选中态", len(checked) == 1, str(checked))

# 工具页内部子标签顺序（曾被插错位置导致点「数据面板」跳到「桌面工具」）
labels = [b.text() for b in mw._tools_tab_btns.values()]
expected_sub = ["📋 效率工具", "🖥 桌面工具", "📊 数据面板"]
check("工具页子标签顺序", labels == expected_sub, str(labels))

types = []
for i in range(3):
    mw._switch_tools_page(i)
    app.processEvents()
    types.append(type(mw._tools_stack.currentWidget()).__name__)
check("子标签索引与内容对应", types[1] == "DesktopToolsPage" and types[0] != types[1] != types[2],
      str(types))

# 快速连点（不等待动画）也不能出问题
fast_errors = []
for _ in range(5):
    for label in ORDER:
        try:
            mw._page_btns[label].click()
            app.processEvents()
        except Exception as exc:  # noqa: BLE001
            fast_errors.append("%s: %s" % (label, exc))
check("快速连点无异常", not fast_errors, str(fast_errors[:3]))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-30s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
# 直接终止进程：Python 解释器退出时会做完整 teardown，
# 而 Qt 在 offscreen 模式下此时回收窗口容易触发段错误，会污染退出码
os._exit(1 if fails else 0)
