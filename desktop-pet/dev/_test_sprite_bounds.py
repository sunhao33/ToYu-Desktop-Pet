"""Regression test for sprite visible-bounds math (was: QImage.constScan AttributeError)."""

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QPixmap, QPainter, QColor  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from pet_engine.sprite_bounds import (  # noqa: E402
    get_visible_bounds, get_content_rect, get_content_ratio
)

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


# 32x32 画布，内容只画在 x=8..23, y=4..27
W = H = 32
LEFT, RIGHT, TOP, BOTTOM = 8, 23, 4, 27
pm = QPixmap(W, H)
pm.fill(Qt.GlobalColor.transparent)
painter = QPainter(pm)
painter.fillRect(LEFT, TOP, RIGHT - LEFT + 1, BOTTOM - TOP + 1, QColor(200, 120, 40, 255))
painter.end()

top, bottom, left, right = get_visible_bounds(pm)
check("top offset", top == TOP, "got %s want %s" % (top, TOP))
check("bottom offset", bottom == H - 1 - BOTTOM, "got %s want %s" % (bottom, H - 1 - BOTTOM))
check("left offset", left == LEFT, "got %s want %s" % (left, LEFT))
check("right offset", right == W - 1 - RIGHT, "got %s want %s" % (right, W - 1 - RIGHT))

rect = get_content_rect(pm)
check("content rect", rect == (LEFT, TOP, RIGHT - LEFT + 1, BOTTOM - TOP + 1), str(rect))

ratio = get_content_ratio(pm)
check("ratio top", abs(ratio["top"] - TOP / H) < 1e-6, str(ratio))
check("ratio keys", set(ratio) == {"top", "bottom", "left", "right"}, str(ratio))

# 全透明
blank = QPixmap(W, H)
blank.fill(Qt.GlobalColor.transparent)
check("blank bounds", get_visible_bounds(blank) == (0, 0, 0, 0))
check("blank ratio zeros", get_content_ratio(blank) == {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0})

# null pixmap
check("null pixmap safe", get_visible_bounds(QPixmap()) == (0, 0, 0, 0))

# 真实精灵图（走完整链路：加载 → 计算）
from image_processor.processor import get_default_pet_path, get_tv_pet_path  # noqa: E402

for label, path in (("默认土豆", get_default_pet_path()), ("TV 小电视", get_tv_pet_path())):
    real = QPixmap(path)
    if real.isNull():
        check("real sprite %s" % label, False, "pixmap 加载失败: %s" % path)
        continue
    try:
        r = get_content_ratio(real)
        t, b, l, rr = get_visible_bounds(real)
        sane = all(0.0 <= v <= 1.0 for v in r.values()) and (t + b) < real.height() and (l + rr) < real.width()
        check("real sprite %s" % label, sane, "%dx%d -> %s" % (real.width(), real.height(), r))
    except Exception as exc:  # noqa: BLE001
        check("real sprite %s" % label, False, "%s: %s" % (type(exc).__name__, exc))

# 性能：大图不应退化（原来逐像素 pixelColor 是 O(w*h) 次 Python 调用）
import time  # noqa: E402

big = QPixmap(512, 512)
big.fill(Qt.GlobalColor.transparent)
p = QPainter(big)
p.fillRect(100, 60, 300, 380, QColor(10, 200, 10, 255))
p.end()
start = time.perf_counter()
for _ in range(20):
    get_visible_bounds(big)
elapsed = (time.perf_counter() - start) / 20
check("512x512 perf < 20ms", elapsed < 0.02, "%.2f ms/call" % (elapsed * 1000))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-24s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
