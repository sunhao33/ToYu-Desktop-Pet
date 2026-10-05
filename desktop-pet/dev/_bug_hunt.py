"""Bug hunt probe: exercise suspicious paths and report concrete defects (temporary tool)."""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtGui import QMouseEvent, QShowEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui.main_window import MainWindow  # noqa: E402
from ui.settings_manager import SettingsManager  # noqa: E402
from ui.tools import hub as hub_mod  # noqa: E402

found = []


def defect(severity, title, detail):
    found.append((severity, title, detail))
    print("  [%s] %s\n      %s" % (severity, title, detail))


def ok(msg):
    print("  ok  %s" % msg)


print("\n=== B1. 启动时宠物是否自动出现 ===")
s = SettingsManager()
has_saved = bool(s.pet_image_path) and os.path.exists(s.pet_image_path)
print("  已保存宠物路径:", s.pet_image_path, "| 文件存在:", has_saved)
mw = MainWindow()
mw.show()
app.processEvents()
mw.showEvent(QShowEvent())  # 模拟真实显示流程
app.processEvents()
time.sleep(0.5)
app.processEvents()
if mw._pet is None:
    auto = "未自动启动"
else:
    auto = "已自动启动"
print("  显示主窗口后:", auto)
if has_saved and mw._pet is None:
    defect("中", "老用户启动后宠物不出现，也没有任何提示",
           "_restore_state 里 _first_launch 只在无保存路径时为 True，"
           "而有保存路径时 showEvent 不会调用 _on_start_pet，用户会以为程序坏了")
elif mw._pet is None:
    ok("无保存路径场景符合预期（首启自动启动）")

if mw._pet is None:
    mw._on_start_pet()
    app.processEvents()
pet = mw._pet
print("  手动启动后 pet:", pet is not None)

print("\n=== B2. 右键气泡的「显示/隐藏」是否触发两次 ===")
if pet is not None:
    from pet_engine.pet_bubble import PetFunctionBubble

    calls = {"n": 0}
    orig = pet.toggle_visibility

    def counting():
        calls["n"] += 1
        orig()

    pet.toggle_visibility = counting
    before_vis = pet.isVisible()
    pet._show_function_bubble(QPoint(500, 500))
    app.processEvents()
    bubble = pet._bubble
    if bubble is None:
        defect("高", "右键功能气泡未创建", "pet._bubble 为 None")
    else:
        bubble.toggle_visibility.emit()
        app.processEvents()
        print("  可见性 before=%s after=%s | toggle 调用次数=%d"
              % (before_vis, pet.isVisible(), calls["n"]))
        if calls["n"] > 1:
            defect("中", "点气泡里的「显示/隐藏」会调用两次 toggle_visibility",
                   "调两次等于没切换，用户会看到按钮没反应")
        else:
            ok("只触发一次")
    pet.toggle_visibility = orig

print("\n=== B3. 剪贴板历史写入注册表是否会因体积过大而静默失败 ===")
s2 = SettingsManager()
short_hist = [{"text": "x" * 200, "time": "10-03 12:00"} for _ in range(5)]
s2.clipboard_history = short_hist
r1 = SettingsManager().clipboard_history
print("  小数据(5×200字符) 回读条数:", len(r1))

big_hist = [{"text": "y" * 1000, "time": "10-03 12:00"} for _ in range(100)]
s2.clipboard_history = big_hist
r2 = SettingsManager().clipboard_history
print("  大数据(100×1000字符) 回读条数:", len(r2), "（写入 100 条）")
if len(r2) != 100:
    defect("高", "剪贴板历史超过注册表单值上限后整段丢失",
           "QSettings 单值有大小限制，长文本×100 条会写失败；"
           "实测回读 %d 条（写入 100 条）" % len(r2))
else:
    ok("大数据读写正常")

# 复原
s2.clipboard_history = []

print("\n=== B4. 护眼提醒：过期后重开是否重复补偿 ===")
s3 = SettingsManager()
s3.eye_care_deadline = time.time() - 3600  # 一小时前就该提醒了
ev = []
eye = hub_mod.EyeCareReminder(s3, on_rest=lambda m, c: ev.append(("rest", m, c)))
eye.set_enabled(True)
print("  启用后立刻 tick 触发的事件:", ev)
if ev:
    defect("低", "关机/休眠期间过期的护眼提醒会在启动瞬间补弹",
           "用户开机就被弹提醒，容易被当成 bug")
else:
    ok("过期不补偿，重新计时")

print("\n=== B5. 屏幕时间统计的有效性 ===")
from ui.screen_time_tracker import ScreenTimeTracker

tracker = ScreenTimeTracker()
today = tracker.get_today_data()
print("  今日记录到 %d 个应用" % len(today))
print("  小时分布（应全为 0 = 未实现）:", set(tracker.get_hourly_data()))
if set(tracker.get_hourly_data()) == {0.0}:
    defect("中", "屏幕时间的「小时分布」是空实现",
           "get_hourly_data 直接 return [0.0]*24，导致「几点学的」根本查不出来")
print("  数据文件:", os.path.join(os.path.expanduser("~"), ".desktop_pet", "screen_time.json"))
app_dir = "%APPDATA%\\ToYu"
print("  而剪贴板/错误日志在:", app_dir)
defect("低", "两套数据目录并存", "~/.desktop_pet 与 %APPDATA%/ToYu，用户找不到自己的数据")

print("\n===== 汇总 =====")
for sev, title, _detail in found:
    print("[%s] %s" % (sev, title))
print("共发现 %d 项" % len(found))
