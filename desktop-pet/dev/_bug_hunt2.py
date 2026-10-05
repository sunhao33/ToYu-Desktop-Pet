import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
from ui.main_window import MainWindow
from pet_engine.pet_bubble import PetFunctionBubble

issues = []
mw = MainWindow(); mw.show(); app.processEvents()
mw._on_start_pet(); app.processEvents()
pet = mw._pet

print("=== B6. 托盘图标能否正常加载（失败则关窗口后无法唤回）===")
from ui.tray_icon import TrayIcon
tray = TrayIcon(None, mw.settings)
icon = tray.icon()
print("  托盘图标 isnull:", icon.isNull(), "| 可用尺寸:", icon.availableSizes())
if icon.isNull():
    issues.append(("高", "托盘图标为空，用户关掉主窗口后将无法唤回程序"))
print("  系统托盘是否可用:", tray.isSystemTrayAvailable())

print("\n=== B7. 托盘菜单各项是否都能用 ===")
acts = tray.contextMenu().actions()
for a in acts:
    print("   %-16s enabled=%s" % (a.text(), a.isEnabled()))
if not any(a.isEnabled() and "隐藏" in a.text() for a in acts):
    issues.append(("中", "托盘菜单没有可用的显示/隐藏项"))

print("\n=== B8. 宠物隐藏后还能不能通过气泡唤回 ===")
pet.toggle_visibility()
app.processEvents()
hidden_ok = not pet.isVisible()
pet.toggle_visibility()
app.processEvents()
print("  隐藏→再显示:", hidden_ok, "→", pet.isVisible())
if not (hidden_ok and pet.isVisible()):
    issues.append(("中", "宠物隐藏/显示切换异常"))

print("\n=== B9. 主窗口关闭后是否有提示 ===")
before = mw._status.text()
mw.close(); app.processEvents()
print("  关闭后 status:", repr(mw._status.text()), "| 窗口可见:", mw.isVisible())
if mw._status.text() == before:
    issues.append(("低", "关闭主窗口只是隐藏，但没有告知用户如何唤回"))

print("\n=== B10. 收藏夹项指向的文件是否都还在 ===")
missing = [f for f in mw.settings.favorites if not os.path.exists(f["path"])]
print("  收藏夹 %d 项，失效 %d 项" % (len(mw.settings.favorites), len(missing)))
for f in missing:
    print("   [失效]", f["path"])
if missing:
    issues.append(("低", "收藏夹存在失效路径（点开无反应）", str(len(missing)) + " 项"))

print("\n=== B11. 拼豆作品路径是否有效 ===")
creations = mw.settings.bead_creations
bad = [c for c in creations if c.get("path") and not os.path.exists(c["path"])]
print("  作品 %d 个，失效 %d 个" % (len(creations), len(bad)))

print("\n=== B12. AI 配置状态 ===")
from pet_engine.pet_ai import AIConfig, AICompanion
cfg = AIConfig(); cfg.load()
ai = AICompanion(cfg)
print("  enabled:", cfg.enabled, "| 有 key:", bool(cfg.api_key), "| model:", cfg.model)
print("  is_available:", ai.is_available())
if cfg.enabled and not cfg.api_key:
    issues.append(("中", "AI 已启用但没有 key，点开聊天只会报错"))

print("\n===== 汇总 =====")
for sev, t in [(a, b) for a, b in issues]:
    print("[%s] %s" % (sev, t))
print("共 %d 项" % len(issues))
