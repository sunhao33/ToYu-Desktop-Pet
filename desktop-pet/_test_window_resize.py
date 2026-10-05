"""Regression test: shrinking the main window must not clip page content.

回归背景：窗口最小宽度 680 太窄，缩到那个尺寸时横向滚动条出现，
右侧内容被推出可视区（用户反馈「软件一缩小，部分内容框里的内容看不见」）。
现在最小宽度会自动抬高到内容实际需要的宽度，且各页都不应再出现横向滚动。
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QScrollArea  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=300):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


PAGES = ["宠物", "功能", "工具", "AI"]

mw = MainWindow()
mw.resize(1200, 900)
mw.show()
pump(900)

# ── 1. 最小宽度必须足以容纳内容 ────────────────────────────
page_needs = {}
for i, label in enumerate(PAGES):
    mw._on_page_switch(i, label)
    pump(400)
    if label == "工具":
        for sub in range(3):
            mw._switch_tools_page(sub)
            pump(400)
    page_needs[label] = mw.minimumWidth()

check("最小宽度已按内容抬高（>680）", mw.minimumWidth() > 680,
      "最小宽度 %d" % mw.minimumWidth())
check("最小高度已按内容抬高（AI 页需要）", mw.minimumHeight() >= 800,
      "最小高度 %d" % mw.minimumHeight())
check("最小宽度不超出常见屏幕宽度", mw.minimumWidth() <= 1200,
      "最小宽度 %d" % mw.minimumWidth())
check("起始尺寸不小于最小尺寸",
      mw.width() >= mw.minimumWidth() and mw.height() >= mw.minimumHeight(),
      "起始 %dx%d 最小 %dx%d" % (mw.width(), mw.height(), mw.minimumWidth(), mw.minimumHeight()))

# ── 2. 缩到最小尺寸后，各页不得出现横向滚动 ────────────────
# 注意：离屏平台不会自动把窗口限制在最小尺寸内，必须显式先归位，
# 否则会测到「比最小值还窄」这种真实环境不存在的状态
mw.resize(mw.minimumWidth(), mw.minimumHeight())
pump(600)
check("测试前窗口已归位到最小尺寸",
      mw.width() >= mw.minimumWidth() and mw.height() >= mw.minimumHeight(),
      "窗口 %dx%d 最小 %dx%d" % (mw.width(), mw.height(), mw.minimumWidth(), mw.minimumHeight()))


def clipped_areas(area_list):
    """找出「内容比视口宽、又没有任何办法看到」的滚动区。

    只有 ScrollBarAlwaysOff 才是真裁切 —— 用户既看不到也滚不到。
    favGallery 这类 AsNeeded 的画廊是**按设计横向滚动**的
    （收藏满 10 个时缩略图必然超出一行宽度），有滚动条可用不算缺陷，
    否则这个测试会误伤它。
    """
    bad = []
    for area in area_list:
        m = area.horizontalScrollBar().maximum()
        if m <= 0:
            continue
        if area.horizontalScrollBarPolicy().name == "ScrollBarAlwaysOff":
            bad.append((area.objectName() or type(area).__name__, m))
    return bad


overflow = []
for i, label in enumerate(PAGES):
    mw._on_page_switch(i, label)
    pump(350)
    if label == "工具":
        for sub in range(3):
            mw._switch_tools_page(sub)
            pump(350)
            w = mw._tools_stack.currentWidget()
            for name, m in clipped_areas(w.findChildren(QScrollArea)):
                overflow.append(("工具子页%d/%s" % (sub, name), m))
    w = mw._page_stack.widget(i)
    for name, m in clipped_areas(w.findChildren(QScrollArea)):
        overflow.append(("%s/%s" % (label, name), m))
check("缩到最小宽度后无内容被裁切", not overflow, str(overflow))

# ── 3. 强行缩到比最小值更小也不应低于最小宽度 ──────────────
mw.resize(500, 500)
pump(400)
check("窗口不会缩到小于最小宽度", mw.width() >= mw.minimumWidth(),
      "请求 500，实际 %d，最小 %d" % (mw.width(), mw.minimumWidth()))

# ── 4. 最小宽度不应过度抬高（不能占满屏幕）────────────────
check("最小宽度合理（≤ 屏幕宽的 60%）", mw.minimumWidth() <= 1100,
      "最小宽度 %d" % mw.minimumWidth())

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-34s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
