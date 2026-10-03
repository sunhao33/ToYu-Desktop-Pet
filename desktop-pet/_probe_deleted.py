"""Probe: is `if self._pet:` safe after the pet window is closed/destroyed?"""

import gc
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6 import sip  # noqa: E402
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
mw._on_start_pet()
app.processEvents()
pet = mw._pet

check("启动后 _pet 有效", pet is not None and not sip.isdeleted(pet))

# 场景 1：关闭宠物窗口（closeEvent 里只 stop 定时器，不销毁对象）
pet.close()
app.processEvents()
check("close() 之后 Python 引用仍可访问", not sip.isdeleted(pet),
      "isdeleted=%s" % sip.isdeleted(pet))
try:
    pet.toggle_visibility()
    check("close() 之后仍能调用方法", True)
except RuntimeError as exc:
    check("close() 之后仍能调用方法", False, str(exc))

# 场景 2：显式销毁底层对象（模拟窗口被 Qt 回收）
mw._pet = pet
pet.deleteLater()
app.processEvents()
gc.collect()
app.processEvents()
destroyed = sip.isdeleted(pet)
print("  deleteLater 后 sip.isdeleted =", destroyed)
if destroyed:
    # 这正是 `if self._pet:` 判断失效的场景
    truthy = bool(pet)
    print("  已销毁对象的真值判断结果:", truthy)
    check("已销毁的 Qt 对象真值判断应为 False（当前实现为 %s）" % truthy, not truthy,
          "`if self._pet:` 会误判为存在，随后调用方法将抛 RuntimeError")
    try:
        pet.toggle_visibility()
        check("对已销毁对象调用方法被安全拦住", True)
    except RuntimeError as exc:
        check("对已销毁对象调用方法被安全拦住", False, "RuntimeError: %s" % exc)
else:
    check("deleteLater 立即销毁（用于验证后续判断）", True, "对象未立即销毁，跳过真值验证")

# 场景 3：主窗口各处以 self._pet 为真的分支，是否会在此状态下崩
mw._pet = pet
for label, fn in (
    ("_on_toggle_visibility", mw._on_toggle_visibility),
    ("_pulse_status", mw._pulse_status),
    ("_on_settings_scale_change", lambda: mw._on_settings_scale_change(1.2)),
):
    try:
        fn()
        check("%s 在宠物销毁后不抛异常" % label, True)
    except RuntimeError as exc:
        check("%s 在宠物销毁后不抛异常" % label, False, "RuntimeError: %s" % exc)
    except Exception as exc:  # noqa: BLE001
        check("%s 在宠物销毁后不抛异常" % label, False, "%s: %s" % (type(exc).__name__, exc))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-40s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
