"""统一的主题色与状态样式。

**为什么要有这个模块**

原来 `ACCENT` / `LIGHT_BG` / `CARD_BG` / `BORDER` 这些常量在 6 个文件里
各抄了一份（main_window、settings_dialog、timer_widget、todo_widget、
pet_bubble、calendar_widget），而 bead_editor 里一份都没有 —— 结果拼豆
编辑器在深色模式下**整个窗口还是白底**，跟主界面完全脱节。

这里把调色板集中一处，并提供 `colors()` 给独立窗口/对话框用。
主窗口的 `_c(key)` 语义保持不变（它还要负责主题切换时的自动重刷），
但取色逻辑委托到这里，避免两份定义漂移。

设计原则：
  · 深色底用**接近中性的冷灰**（饱和 9~11%），颜色只留给强调处
  · 强调色保留品牌土豆金；语义色在深色下提亮，保证 WCAG AA
"""

# ── 浅色主题 ────────────────────────────────────────────────
ACCENT = "#C49A3C"          # 土豆金
ACCENT_HOVER = "#D4AE50"
DARK_BROWN = "#3E2723"
MID = "#5C3D1E"
LIGHT_BG = "#FFF8F0"        # 暖奶油底
CARD_BG = "#FFFFFF"
TEXT = "#2C1810"
TEXT_SEC = "#8B7355"
BORDER = "#E8D5C0"
SUCCESS = "#6B9B37"
DANGER = "#C0392B"
HOVER_BG = "#FFF3E0"
PRESS_BG = "#FFE0B2"
DISABLE_BG = "#F0F0F0"
DISABLE_FG = "#BBBBBB"
DISABLE_BDR = "#E0E0E0"
INPUT_BG = "#FAFAFA"
TAB_BG = "#FFF8E1"
HANDLE = "#D7CCC8"
HANDLE_HOVER = "#BCAAA4"
WARN = "#B8860B"

# ── 深色主题 ────────────────────────────────────────────────
# 实测对比度：正文/卡片 12.7、次要 5.8、金色 6.9、成功 6.3、危险 4.9，
# 全部达到 WCAG AA（正文需 4.5）。
DARK_BG = "#16181B"         # 主背景（冷灰，饱和仅 10%）
DARK_CARD = "#202327"       # 卡片
DARK_TEXT = "#E4E7EB"       # 正文
DARK_TEXT_SEC = "#959DA6"   # 次要文字
DARK_BORDER = "#33383F"     # 描边
DARK_HEADER = "#1E2126"     # 头部
DARK_INPUT = "#1A1D21"      # 输入框底
DARK_TAB = "#2A2E34"        # 标签底
DARK_HOVER = "#2C3036"
DARK_PRESS = "#353A41"
DARK_ACCENT = "#D2A44A"     # 冷底上要更亮才醒目
DARK_ACCENT_HOVER = "#E0B65F"
DARK_SUCCESS = "#7FB069"
DARK_WARNING = "#E0B05A"
DARK_DANGER = "#E06C75"

# 深色下"浅色主题专属"颜色的替代值
DARK_DISABLE_FG = "#5F6670"
DARK_HANDLE_HOVER = "#454B54"

# ── 键 → (浅色, 深色) 映射 ─────────────────────────────────
# 与 main_window._c() 的键完全一致，主窗口也走这张表。
PAIRS = {
    "bg":          (LIGHT_BG, DARK_BG),
    "card":        (CARD_BG, DARK_CARD),
    "text":        (TEXT, DARK_TEXT),
    "text2":       (TEXT_SEC, DARK_TEXT_SEC),
    "border":      (BORDER, DARK_BORDER),
    "header":      (DARK_BROWN, DARK_HEADER),
    "accent":      (ACCENT, DARK_ACCENT),
    "accent_h":    (ACCENT_HOVER, DARK_ACCENT_HOVER),
    "mid":         (MID, DARK_ACCENT),
    "success":     (SUCCESS, DARK_SUCCESS),
    "danger":      (DANGER, DARK_DANGER),
    "hover_bg":    (HOVER_BG, DARK_HOVER),
    "press_bg":    (PRESS_BG, DARK_PRESS),
    "input_bg":    (INPUT_BG, DARK_INPUT),
    "disable_bg":  (DISABLE_BG, DARK_BG),
    "disable_fg":  (DISABLE_FG, DARK_DISABLE_FG),
    "disable_bdr": (DISABLE_BDR, DARK_CARD),
    "tab_bg":      (TAB_BG, DARK_TAB),
    "handle":      (HANDLE, DARK_BORDER),
    "handle_h":    (HANDLE_HOVER, DARK_HANDLE_HOVER),
    "warn":        (WARN, DARK_WARNING),
    "name_fg":     (TEXT, DARK_TEXT),
}


def color(key, dark):
    """按当前模式取色。未知键回退到文字色，与 main_window._c 行为一致。"""
    pair = PAIRS.get(key, (TEXT, DARK_TEXT))
    return pair[1] if dark else pair[0]


class Palette:
    """给独立窗口/对话框用的小包装：一次拿全所有颜色。

    用法::

        p = Palette(dark)
        self.setStyleSheet(f"background: {p.bg}; color: {p.text};")
    """

    __slots__ = tuple(PAIRS.keys()) + ("dark",)

    def __init__(self, dark=False):
        self.dark = bool(dark)
        for key in PAIRS:
            setattr(self, key, color(key, self.dark))

    def __repr__(self):
        return "Palette(dark=%s)" % self.dark


def is_dark(settings=None):
    """读深色模式开关。

    独立窗口（拼豆编辑器、导入对话框等）拿不到主窗口的 _is_dark_mode，
    但它们需要跟当前主题一致，所以从设置里读。

    能接受两种入参：
      · SettingsManager —— 取 dark_mode 属性
      · QSettings        —— 取 ui/dark_mode 键
    """
    if settings is None:
        try:
            from ui.settings_manager import SettingsManager
            return bool(SettingsManager().dark_mode)
        except Exception:      # noqa: BLE001
            return False

    # 1) SettingsManager（正常路径）：dark_mode 是 property
    for attr in ("dark_mode", "is_dark_mode", "dark"):
        val = getattr(settings, attr, None)
        if isinstance(val, bool):
            return val

    # 2) 直接传进来的 QSettings：value() 返回的是字符串 "true"/"false"
    value = getattr(settings, "value", None)
    if callable(value):
        try:
            raw = value("ui/dark_mode", False)
            if isinstance(raw, str):
                return raw.strip().lower() == "true"
            return bool(raw)
        except Exception:      # noqa: BLE001
            return False

    # 3) 带 get() 的映射类对象
    getter = getattr(settings, "get", None)
    if callable(getter):
        try:
            return bool(getter("dark_mode", False))
        except Exception:      # noqa: BLE001
            return False
    return False


def message_box_style(dark):
    """QMessageBox 的样式表。

    为什么需要它：`QMessageBox.information(...)` 这类**静态便捷方法**
    没法设样式，于是走 Qt 默认主题 —— 深色模式下会弹出一块**纯黑**
    的框，跟软件配色完全脱节。

    用法：改用实例化的 QMessageBox，再 setStyleSheet(message_box_style(dark))。
    """
    p = Palette(dark)
    return """
        QMessageBox { background: %(bg)s; }
        QMessageBox QLabel { color: %(text)s; font-size: 12px; }
        QMessageBox QPushButton {
            background: %(card)s; border: 1px solid %(border)s;
            border-radius: 6px; padding: 5px 16px;
            color: %(text)s; font-weight: bold; min-width: 64px;
        }
        QMessageBox QPushButton:hover {
            border-color: %(accent)s; background: %(hover_bg)s;
        }
        QMessageBox QPushButton:default { border-color: %(accent)s; }
    """ % {"bg": p.bg, "card": p.card, "border": p.border,
           "text": p.text, "accent": p.accent, "hover_bg": p.hover_bg}


def ask(parent, title, text, kind="info", dark=False,
        buttons=("ok",), default="ok"):
    """弹一个**跟随主题**的消息框，返回被点击按钮的名字。

    替代 QMessageBox.information / warning / critical / question
    这类静态调用 —— 它们无法设样式，深色模式下是纯黑框。
    """
    from PyQt6.QtWidgets import QMessageBox

    icon_map = {
        "info": QMessageBox.Icon.Information,
        "warning": QMessageBox.Icon.Warning,
        "error": QMessageBox.Icon.Critical,
        "question": QMessageBox.Icon.Question,
    }
    btn_map = {
        "ok": QMessageBox.StandardButton.Ok,
        "yes": QMessageBox.StandardButton.Yes,
        "no": QMessageBox.StandardButton.No,
        "cancel": QMessageBox.StandardButton.Cancel,
    }
    back_map = {
        QMessageBox.StandardButton.Ok: "ok",
        QMessageBox.StandardButton.Yes: "yes",
        QMessageBox.StandardButton.No: "no",
        QMessageBox.StandardButton.Cancel: "cancel",
    }

    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(icon_map.get(kind, QMessageBox.Icon.Information))
    combined = btn_map["ok"] if buttons else QMessageBox.StandardButton.Ok
    for name in buttons:
        if name in btn_map and name != "ok":
            combined |= btn_map[name]
    box.setStandardButtons(combined)
    if default in btn_map:
        box.setDefaultButton(btn_map[default])
    box.setStyleSheet(message_box_style(dark))
    return back_map.get(box.exec(), "ok")
