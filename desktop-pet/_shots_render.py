"""Composited screenshots for the competition submission (Qt-rendered, no desktop capture).

Renders the app's own windows off-screen: main panel, pet sprite, chat bubble and
notification bubble, laid out on a clean background. Nothing else from the desktop
can leak into the image.

Output: C:\\Users\\asus\\Desktop\\Huabei\\_shots\\*
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

OUT_DIR = r"C:\Users\asus\Desktop\Huabei\_shots"
os.makedirs(OUT_DIR, exist_ok=True)

from PyQt6.QtCore import QPoint, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.pet_ai import AIMessage  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()

# ── 演示数据 ────────────────────────────────────────────────
mw.settings.clipboard_enabled = True
mw.settings.clipboard_history = [
    {"text": "def on_ai_message(self, user_text): ...  # 双击宠物唤起对话",
     "time": "10-03 14:02"},
    {"text": "https://bjcac.buu.moocollege.com/  作品提交入口",
     "time": "10-03 13:58"},
    {"text": "把待办、番茄钟、剪贴板、护眼提醒收进一个面板，桌面上真的能天天用",
     "time": "10-03 13:41"},
    {"text": "pip install -r requirements.txt && python main.py",
     "time": "10-03 13:20"},
]
mw.settings.eye_care_enabled = True
mw.settings.eye_care_work_minutes = 45
mw.settings.eye_care_rest_minutes = 5
mw._init_tools_hub()
mw._desktop_tools_page.refresh_clipboard(mw.settings.clipboard_history)

# 用默认土豆精灵（不是用户自己换的收藏宠物）
mw._on_reset()
mw._on_start_pet()
app.processEvents()
pet = mw._pet
pet.show()
app.processEvents()
print("pet image:", os.path.basename(pet._pet_image_path))

mw.resize(880, 900)
mw.move(40, 40)  # 必须在屏内，Qt 才会真正绘制子控件（离屏时 grab 得到空白）
mw.show()
app.processEvents()
time.sleep(0.8)
app.processEvents()


def render(widget, pad=0):
    widget.ensurePolished()
    app.processEvents()
    pix = widget.grab()
    if pad:
        padded = QPixmap(pix.width() + pad * 2, pix.height() + pad * 2)
        padded.fill(Qt.GlobalColor.transparent)
        p = QPainter(padded)
        p.drawPixmap(pad, pad, pix)
        p.end()
        return padded
    return pix


def save_canvas(name, items, bg_top="#FFF6E8", bg_bottom="#F3E2C7", margin=34):
    """items: list of (pixmap, x, y) in canvas coordinates."""
    width = max(x + pix.width() for pix, x, _y in items) + margin * 2
    height = max(y + pix.height() for pix, _x, y in items) + margin * 2
    canvas = QPixmap(width, height)
    grad = QLinearGradient(0, 0, 0, height)
    grad.setColorAt(0, QColor(bg_top))
    grad.setColorAt(1, QColor(bg_bottom))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(canvas.rect(), grad)
    for pix, x, y in items:
        painter.drawPixmap(margin + x, margin + y, pix)
    painter.end()
    path = os.path.join(OUT_DIR, name)
    canvas.save(path)
    print("saved %-30s %dx%d  %.0f KB" % (name, width, height, os.path.getsize(path) / 1024))
    return path


# ── 图1：主控制面板 · 桌面工具页 ────────────────────────────
mw._on_page_switch(2, "工具")
mw._switch_tools_page(1)
mw._tools_hub.eye_care.work_minutes = 45
mw._tools_hub.eye_care._deadline = time.time() + 12 * 60 + 30
mw._desktop_tools_page.refresh_eye_care(mw._tools_hub.eye_care)
app.processEvents()
time.sleep(0.4)
app.processEvents()
panel_pix = render(mw)
pet_pix = render(pet, pad=18)

save_canvas(
    "shot1_桌面工具.png",
    [(panel_pix, 0, 0), (pet_pix, panel_pix.width() + 30, 120)],
)

# ── 图2：宠物 + 护眼提醒通知气泡 ────────────────────────────
from pet_engine.pet_bubble import PomodoroNotificationBubble  # noqa: E402

pet.move(400, 300)
app.processEvents()
bubble = PomodoroNotificationBubble(pet, title="👀  该让眼睛歇一会儿了！",
                                    subtitle="5 分钟后再继续 · 已专注 3 轮")
bubble.adjustSize()
bubble.show()
app.processEvents()
time.sleep(0.3)
app.processEvents()
bubble_pix = render(bubble, pad=6)

save_canvas(
    "shot2_护眼提醒.png",
    [(bubble_pix, 0, 0), (pet_pix, 40, bubble_pix.height() + 6)],
)
bubble.close()

# ── 图3：AI 对话 + 宠物 ────────────────────────────────────
messages = pet._ai.get_history()
if not messages:
    messages = [
        AIMessage("user", "今天事情好多，有点焦虑，不知道从哪开始"),
        AIMessage("assistant", "先别急～把最要紧的 3 件事告诉我，我们一件一件来。要不要我先开一个 25 分钟番茄钟陪你？"),
        AIMessage("user", "好，那就先写竞赛文档吧"),
        AIMessage("assistant", "收到！番茄钟已经开始了 🍅 结束我会提醒你站起来看看窗外，加油！"),
    ]
chat = pet._chat_bubble
chat.load_history(messages[-4:])
chat.show_chat()
app.processEvents()
time.sleep(0.5)
app.processEvents()
chat_pix = render(chat, pad=8)

save_canvas(
    "shot3_AI对话.png",
    [(chat_pix, 0, 0), (pet_pix, chat_pix.width() + 10, chat_pix.height() - pet_pix.height() + 60)],
)

# ── 图4：宠物本体特写（备用） ───────────────────────────────
save_canvas("shot4_宠物特写.png", [(pet_pix, 0, 0)], bg_top="#FFF9F0", bg_bottom="#EFE0C8")

chat.hide_chat()
pet.close()
print("done")
