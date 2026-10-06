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
    """读持久化的深色模式开关。

    独立窗口（拼豆编辑器、导入对话框等）拿不到主窗口的 _is_dark_mode，
    但它们需要跟当前主题一致，所以从 settings 读。
    """
    if settings is None:
        try:
            from ui.settings_manager import SettingsManager
            settings = SettingsManager()
        except Exception:      # noqa: BLE001
            return False
    for attr in ("dark_mode", "is_dark_mode", "dark"):
        val = getattr(settings, attr, None)
        if isinstance(val, bool):
            return val
    try:
        return bool(settings.get("dark_mode", False))
    except Exception:          # noqa: BLE001
        return False
