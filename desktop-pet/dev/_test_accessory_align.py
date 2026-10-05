"""Regression test: 配件层必须与宠物对齐，且换宠物图后要更新内容区比例。

覆盖两个曾经出问题的地方：
  1. 宠物移动后配件层是否跟随（几何同步）
  2. 换上另一张宠物图后，配件层的内容区比例是否更新
     （否则帽子/雨伞会按上一张宠物图的内容区对齐，明显歪掉）
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=200):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
pump(250)
mw._on_start_pet()
pump(300)
pet = mw._pet
layer = pet._accessory_layer


def expected_geometry():
    """按 update_geometry 的规则算出层窗口应该在哪个位置。"""
    g = pet.geometry()
    margin = 100
    return (g.x() - margin, g.y() - margin, g.width() + margin * 2, g.height() + margin * 2)


def actual_geometry():
    g = layer.geometry()
    return (g.x(), g.y(), g.width(), g.height())


pet.add_hat(60)
pump(300)
exp, act = expected_geometry(), actual_geometry()
check("静止时层位置正确", exp == act, "期望 %s 实际 %s" % (exp, act))

pet.move(pet.x() + 150, pet.y() + 60)
pump(300)
exp, act = expected_geometry(), actual_geometry()
check("移动后层位置已同步", exp == act,
      "宠物移到 (%d,%d)，期望层 %s，实际 %s" % (pet.x(), pet.y(), exp, act))

drift = []
for i in range(12):
    pet.move(pet.x() + 12, pet.y())
    pump(60)
    exp, act = expected_geometry(), actual_geometry()
    if exp != act:
        drift.append((i, pet.x(), exp, act))
check("走动过程中无累积偏移", not drift, "偏差次数 %d，首例 %s" % (len(drift), drift[:1]))

from image_processor.processor import get_tv_pet_path  # noqa: E402

before_ratio = dict(pet._sprite_content_ratio)
pet.set_pet_image(get_tv_pet_path())
pump(400)
after_ratio = dict(pet._sprite_content_ratio)
check("换宠物图后重新计算了内容区比例", before_ratio != after_ratio,
      "换图前 %s 换图后 %s" % (before_ratio, after_ratio))
check("配件层内容区比例已同步", layer._content_ratio == after_ratio,
      "层内比例 %s vs 宠物 %s" % (layer._content_ratio, after_ratio))

from pet_engine.sprite_bounds import get_content_rect  # noqa: E402

g = pet.geometry()
cx, cy, cw, ch = get_content_rect(pet._pet_pixmap)
lcx = (g.x() - layer.geometry().x()) + cx
lcy = (g.y() - layer.geometry().y()) + cy
acc = layer.accessories[0] if layer.accessories else None
if acc:
    rect = acc.get_draw_rect(lcx, lcy, cw, ch)
    gap = lcy - rect.bottom()
    check("配件位于宠物内容上方（间距合理）", -30 < gap < 60,
          "配件底边 %.0f，内容顶边 %.0f，间距 %.0f px" % (rect.bottom(), lcy, gap))
else:
    check("内容区比例也能在重设宠物后生效", False, "配件层里没有配件（无法验证绘制位置）")

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-38s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
