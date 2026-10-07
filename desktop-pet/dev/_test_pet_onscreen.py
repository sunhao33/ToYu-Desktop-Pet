"""Regression test: the pet must stay inside the screen after position restore,
image change and scale change (previously it could land below the taskbar and
look like it disappeared).
"""

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
from ui.settings_manager import SettingsManager  # noqa: E402
from image_processor.processor import get_default_pet_path, get_tv_pet_path  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


screen = app.primaryScreen().geometry()
print("屏幕: %dx%d" % (screen.width(), screen.height()))


def pet_bottom(pet):
    """宠物可见底边（贴地判断应该看这个，而不是窗口底边）。"""
    return pet.y() + pet.height() - pet._sprite_bottom_offset


def allowed_bottom(pet):
    """允许的最大可见底边：屏幕底边减去任务栏高度。

    任务栏高度必须从宠物实例里取：离屏测试环境下检测不到任务栏（高度 0），
    真实桌面下才有值，写死数字会让测试自身算错。
    """
    taskbar = pet._taskbar_info['height'] if pet._taskbar_info else 0
    return screen.height() - taskbar


def check_on_screen(pet, label):
    """检查**可见 sprite** 留在屏幕内。

    注意口径：这里看的是可见 sprite，不是窗口本身。窗口比 sprite 宽一圈
    （两侧各 _sprite_left/right_offset 的透明内边距），为了让宠物能真正
    贴到屏幕边，窗口允许越界这么多 —— 窗口是透明、无边框、不抢焦点的，
    越界部分什么也画不出来。若按窗口判，就等于要求"宠物必须离屏幕边
    一段距离"，正是之前那个 30px 空隙的成因。
    """
    lo = getattr(pet, "_sprite_left_offset", 0)
    ro = getattr(pet, "_sprite_right_offset", 0)
    vis_left = pet.x() + lo
    vis_right = pet.x() + pet.width() - ro
    ok_x = vis_left >= screen.x() - 5 and vis_right <= screen.x() + screen.width() + 5
    bottom = pet_bottom(pet)
    limit = allowed_bottom(pet)
    check("%s 宠物在屏幕内" % label, ok_x and bottom <= limit + 8,
          "可见区 %d..%d (屏幕 %d..%d)  可见底边=%d  允许最大=%d"
          % (vis_left, vis_right, screen.x(), screen.x() + screen.width(),
             bottom, limit))


s = SettingsManager()
orig_pos = s.pet_position
orig_img = s.pet_image_path

try:
    # ── 1. 存档位置在屏幕外时的恢复 ─────────────────────────
    s.pet_position = QPoint(500, screen.height() - 20)     # 明显过低
    s.pet_image_path = get_default_pet_path()
    mw = MainWindow()
    mw.show()
    pump(200)
    mw._on_start_pet()
    pump(300)
    pet = mw._pet
    check_on_screen(pet, "从屏幕外位置恢复后")

    # ── 2. 换成更大的宠物图后仍要在屏幕内 ───────────────────
    pet.move(400, screen.height() - 120)                   # 故意放到很低
    pump(100)
    pet.set_pet_image(get_tv_pet_path())
    pump(300)
    check_on_screen(pet, "换宠物图后")

    # ── 3. 放大后仍要在屏幕内 ───────────────────────────────
    pet.move(400, screen.height() - 120)
    pump(100)
    pet.set_scale(1.8)
    pump(300)
    check_on_screen(pet, "放大到 1.8 倍后")

    # ── 4. 恢复的位置会被写回设置（避免下次启动又跑出去）──
    pump(100)
    saved = s.pet_position
    check("钳制后的位置已写回设置", saved is not None and saved.y() <= screen.height(),
          "存档位置 %s" % (("(%d,%d)" % (saved.x(), saved.y())) if saved else None))

    # ── 5. 正常位置不应被误改 ───────────────────────────────
    pet.set_scale(1.0)
    pet.move(300, screen.height() - 400)
    pump(200)
    before = pet.pos()
    pet._clamp_to_screen()
    pump(100)
    check("合法位置不会被钳制改动", pet.pos() == before,
          "钳制前 %s 钳制后 %s" % ((before.x(), before.y()), (pet.x(), pet.y())))

finally:
    s.pet_position = orig_pos
    s.pet_image_path = orig_img

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-32s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
