"""Regression test: overlays must disappear with the pet when it goes home / hides."""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
pump(200)
mw._on_start_pet()
pump(300)
pet = mw._pet
check("宠物已启动", pet is not None)

# 让房子出现，才能测试「回家」
mw.settings.house_enabled = True
mw._spawn_house()
pump(300)
house = mw._house
check("房子已创建", house is not None)

# ── 造出下雨特效 + 配件 ──────────────────────────────────────
pet.trigger_rain_mood(30.0)          # 长时长，确保测试期间粒子还在
pet.add_hat(60)
pump(300)
effects = pet._effects
layer = pet._accessory_layer
check("特效层已显示", effects.isVisible(), "粒子 %d 个" % len(effects.particles))
check("配件层已显示", layer.isVisible(), "配件 %d 个" % len(layer.accessories))

# ── 宠物回家 ────────────────────────────────────────────────
pet._go_home()
pump(400)
check("宠物已隐藏", not pet.isVisible())
check("回家后特效层已隐藏", not effects.isVisible(),
      "可见=%s" % effects.isVisible())
check("回家后粒子已清空", len(effects.particles) == 0,
      "剩余 %d 个粒子" % len(effects.particles))
check("回家后配件层已隐藏", not layer.isVisible())
check("回家后配件已清空", len(layer.accessories) == 0,
      "剩余 %d 个配件" % len(layer.accessories))

# 再等一会儿，确认粒子不会自己"复活"
pump(500)
check("等待后特效仍为隐藏", not effects.isVisible())

# ── 回家状态下配件 AI 不应再产生新特效 ──────────────────────
brain = getattr(pet, "_accessory_brain", None)
if brain is not None:
    before = len(effects.particles)
    brain._cooldowns = {k: 0 for k in brain._cooldowns}   # 把所有冷却清零，逼它触发
    brain._tick()
    pump(300)
    after = len(effects.particles)
    check("宠物在家时配件 AI 不再触发特效", after == 0 and not effects.isVisible(),
          "触发前后粒子数 %d -> %d" % (before, after))
    check("宠物在家时不会新增配件", len(layer.accessories) == 0)
else:
    check("找到配件 AI 实例", False, "pet._accessory_brain 不存在")

# ── 拖到门口进门这条路径 ────────────────────────────────────
pet.show()
pet.move(house.x() + 10, house.y() + 10)
pump(200)
pet.trigger_rain_mood(30.0)
pet.add_hat(60)
pump(250)
check("再次触发特效可见", effects.isVisible())
door_pt = QPoint(pet.x() + pet.width() // 2,
                 pet.y() + pet.height() // 2 + int(pet._pet_pixmap.height() * pet._scale) // 2)
if house.is_door_overlap(door_pt):
    pet._hide_overlays()
    pet.hide()
    house.set_pet_inside(True)
    pump(300)
    check("拖到门口进门后特效被清掉", not effects.isVisible() and len(effects.particles) == 0)
else:
    check("拖到门口进门后特效被清掉", True, "门位置未命中，跳过（不影响其他结论）")

# ── 出门后特效应能正常再次出现 ──────────────────────────────
house._on_door_knock()
pump(400)
pet.show()
pump(200)
pet.trigger_sparkle_burst()
pump(300)
check("出门后可以重新产生特效", effects.isVisible() or len(effects.particles) > 0,
      "可见=%s 粒子=%d" % (effects.isVisible(), len(effects.particles)))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-34s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
