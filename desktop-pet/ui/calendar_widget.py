"""Cute calendar widget for ToYu desktop pet — with colored date annotations."""

import json
import os
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QAction
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QSizePolicy, QMenu, QScrollArea, QFrame, QDialog,
                              QLineEdit, QDialogButtonBox)

from ui.theme import Palette

# ── 日历配色 ──────────────────────────────────────────────
# 原来这套是**独立的橙色系**（#FF6B47 / #FFD4C4），跟软件主色（土豆金
# #C49A3C）不是一家人；而且全部写死浅色，主窗口切深色后日历仍是白底 +
# 白圆按钮，非常突兀。
#
# 现在改成「浅色/深色两套」，由 apply_palette(dark) 在运行时切换。
# 仍然用模块级常量名（ACCENT、HEADER…）是因为它们在这个文件里被引用了
# 40 次，逐个改成 self._p.xxx 改动面太大、容易漏；这里用「换值不换名」
# 的办法，改一处就全局生效，风险最小。
#
# 浅色这套同时把色相从橙色往品牌金靠拢，和主界面统一。
_LIGHT = {
    "ACCENT":       "#C49A3C",   # 品牌土豆金（原 #FF6B47 橙）
    "ACCENT_LIGHT": "#E8D5C0",   # 暖米色描边（原 #FFD4C4 橙粉）
    "TODAY_BG":     "#FFF3E0",
    "WEEKDAY":      "#8B7355",
    "WEEKEND":      "#C0392B",
    "NORMAL":       "#2C1810",
    "OTHER_MONTH":  "#BCAAA4",
    "HEADER":       "#C49A3C",
    "BTN_HOVER":    "#FFF3E0",
    "SUCCESS":      "#6B9B37",
}

_DARK = {
    "ACCENT":       "#D2A44A",   # 冷底上提亮，保证可读
    "ACCENT_LIGHT": "#33383F",
    "TODAY_BG":     "#2A2E34",
    "WEEKDAY":      "#959DA6",
    "WEEKEND":      "#E06C75",   # 深色下的语义红（原 #E74C3C 对比不足）
    "NORMAL":       "#E4E7EB",
    "OTHER_MONTH":  "#5F6670",
    "HEADER":       "#D2A44A",
    "BTN_HOVER":    "#2C3036",
    "SUCCESS":      "#7FB069",
}

# 事件标注色：浅色/深色各一套（深色下的浅底要换暗底，否则白得刺眼）
_EVENT_LIGHT = {
    "yellow": ("#F5A623", "#FFF8E1"),
    "blue":   ("#4A90D9", "#E3F2FD"),
    "green":  ("#2ECC71", "#E8F5E9"),
}
_EVENT_DARK = {
    "yellow": ("#E0B05A", "#3A3222"),
    "blue":   ("#5AA9E6", "#1F2C38"),
    "green":  ("#7FB069", "#243325"),
}
EVENT_COLORS = dict(_EVENT_LIGHT)
DEFAULT_EVENT_COLOR = "yellow"

# 当前生效的一整套（由 apply_palette 改写）
ACCENT = _LIGHT["ACCENT"]
ACCENT_LIGHT = _LIGHT["ACCENT_LIGHT"]
TODAY_BG = _LIGHT["TODAY_BG"]
WEEKDAY = _LIGHT["WEEKDAY"]
WEEKEND = _LIGHT["WEEKEND"]
NORMAL = _LIGHT["NORMAL"]
OTHER_MONTH = _LIGHT["OTHER_MONTH"]
HEADER = _LIGHT["HEADER"]
BTN_HOVER = _LIGHT["BTN_HOVER"]
SUCCESS = _LIGHT["SUCCESS"]

_IS_DARK = False


def apply_palette(dark):
    """切换日历用的整套配色（模块级常量就地改写）。"""
    global ACCENT, ACCENT_LIGHT, TODAY_BG, WEEKDAY, WEEKEND, NORMAL
    global OTHER_MONTH, HEADER, BTN_HOVER, SUCCESS, EVENT_COLORS, _IS_DARK
    src = _DARK if dark else _LIGHT
    ACCENT = src["ACCENT"]
    ACCENT_LIGHT = src["ACCENT_LIGHT"]
    TODAY_BG = src["TODAY_BG"]
    WEEKDAY = src["WEEKDAY"]
    WEEKEND = src["WEEKEND"]
    NORMAL = src["NORMAL"]
    OTHER_MONTH = src["OTHER_MONTH"]
    HEADER = src["HEADER"]
    BTN_HOVER = src["BTN_HOVER"]
    SUCCESS = src["SUCCESS"]
    EVENT_COLORS = dict(_EVENT_DARK if dark else _EVENT_LIGHT)
    _IS_DARK = bool(dark)

SAVE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "calendar_events.json")
TASK_HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")

class EventDialog(QDialog):
    """Custom dialog for adding event annotations."""

    def __init__(self, date_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📌 添加标注")
        self.setFixedSize(300, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._selected_color = DEFAULT_EVENT_COLOR

        container = QWidget(self)
        container.setGeometry(10, 10, 280, 180)
        container.setStyleSheet(
            "QWidget { background: white; border-radius: 16px;"
            " border: 2px solid #FFD4C4; }"
        )

        lay = QVBoxLayout(container)
        lay.setContentsMargins(16, 16, 16, 12)
        lay.setSpacing(10)

        title = QLabel(f"📌 给 {date_str} 添加标注")
        title.setStyleSheet("color: #FF6B47; font-size: 14px; font-weight: bold;")
        lay.addWidget(title)

        self._input = QLineEdit()
        self._input.setPlaceholderText("输入事件名称...")
        self._input.setStyleSheet(
            "QLineEdit { border: 2px solid #FFD4C4; border-radius: 8px;"
            " padding: 8px 12px; font-size: 13px; color: #5A3E18;"
            " background: #FFF5EE; }"
            "QLineEdit:focus { border-color: #FF6B47; }"
        )
        lay.addWidget(self._input)

        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        color_label = QLabel("颜色：")
        color_label.setStyleSheet("color: #8B6914; font-size: 12px;")
        color_row.addWidget(color_label)

        self._color_btns = {}
        for name, (dot_color, _) in EVENT_COLORS.items():
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {dot_color}; border-radius: 14px;"
                f" border: 3px solid transparent; }}"
                f"QPushButton:hover {{ border-color: #5A3E18; }}"
            )
            btn.clicked.connect(lambda checked, n=name: self._pick_color(n))
            color_row.addWidget(btn)
            self._color_btns[name] = btn

        color_row.addStretch()
        lay.addLayout(color_row)

        self._pick_color(DEFAULT_EVENT_COLOR)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(
            "QPushButton { color: #8B6914; background: #FFF5EE;"
            " border-radius: 8px; padding: 6px 20px; font-size: 12px;"
            " border: 1px solid #FFD4C4; }"
            "QPushButton:hover { background: #FFD4C4; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet(
            "QPushButton { color: white; background: #FF6B47;"
            " border-radius: 8px; padding: 6px 20px; font-size: 12px;"
            " font-weight: bold; border: none; }"
            "QPushButton:hover { background: #FF8B67; }"
        )
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)

        lay.addLayout(btn_row)

        self._input.setFocus()

    def _pick_color(self, name):
        self._selected_color = name
        for n, btn in self._color_btns.items():
            dot_color = EVENT_COLORS[n][0]
            if n == name:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {dot_color}; border-radius: 14px;"
                    f" border: 3px solid {NORMAL}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {dot_color}; border-radius: 14px;"
                    f" border: 3px solid transparent; }}"
                    f"QPushButton:hover {{ border-color: {NORMAL}; }}"
                )

    def get_result(self):
        text = self._input.text().strip()
        if text:
            return text, self._selected_color
        return None, None

class CuteCalendar(QWidget):
    """A cute calendar widget with colored date annotations."""

    date_selected = pyqtSignal(str)  # emits "yyyy-MM-dd" on day click

    def __init__(self, parent=None):
        super().__init__(parent)
        self._today = QDate.currentDate()
        self._view_year = self._today.year()
        self._view_month = self._today.month()
        self._selected = self._today
        self._events = {}  # {"YYYY-MM-DD": [{"text": "...", "color": "yellow"}]}
        self._task_history = {}  # {"YYYY-MM-DD": [{"text": "...", "time": "HH:MM", "duration": N}]}

        self._load_events()
        self._init_ui()
        self._update_calendar()

    def set_dark(self, dark):
        """切换深色模式：换掉整套配色并重刷。

        原来这个控件写死浅色（白底 + 白色圆形翻页按钮），主窗口切深色后
        它还是白花花一块，和数据面板其它卡片完全不搭。
        """
        apply_palette(dark)
        self._restyle()

    def _restyle(self):
        """按当前配色重刷所有用到颜色的控件（含动态生成的日历格）。"""
        try:
            # 日格样式是在 _update_calendar 里拼字符串生成的，重跑即可
            self._update_calendar()

            if hasattr(self, "_title"):
                self._title.setStyleSheet(
                    f"color: {HEADER}; font-size: 16px; font-weight: bold;"
                    " padding: 2px;")
            for btn in (getattr(self, "_prev_btn", None),
                        getattr(self, "_next_btn", None)):
                if btn is not None:
                    btn.setStyleSheet(self._nav_btn_style())
            if hasattr(self, "_today_btn"):
                self._today_btn.setStyleSheet(self._today_btn_style())
            if hasattr(self, "_info_lbl"):
                self._info_lbl.setStyleSheet(
                    f"color: {WEEKDAY}; font-size: 11px;")
            for i, lbl in enumerate(getattr(self, "_weekday_labels", ())):
                lbl.setStyleSheet(
                    "color: %s; font-size: 13px; font-weight: bold;"
                    % (WEEKEND if i >= 5 else WEEKDAY))
            if getattr(self, "_sep", None) is not None:
                self._sep.setStyleSheet(f"color: {ACCENT_LIGHT}; margin: 4px 0;")
            if hasattr(self, "_events_label"):
                self._events_label.setStyleSheet(
                    f"color: {NORMAL}; font-size: 12px; padding: 4px 0;")
        except (RuntimeError, AttributeError) as exc:
            print("[Calendar] 切主题刷新失败: %s" % exc)

    def _today_btn_style(self):
        return (
            f"QPushButton {{ color: {ACCENT}; background: {TODAY_BG};"
            f" border-radius: 8px; padding: 4px 14px; font-size: 12px;"
            f" border: 1px solid {ACCENT_LIGHT}; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: #FFFFFF; }}")

    def _nav_btn_style(self):
        return (
            f"QPushButton {{ color: {ACCENT}; background: {TODAY_BG};"
            f" border-radius: 18px; font-size: 16px; font-weight: bold;"
            f" border: 2px solid {ACCENT_LIGHT}; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: #FFFFFF;"
            f" border-color: {ACCENT}; }}")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)

        self._prev_btn = self._nav_btn("◀")
        self._prev_btn.clicked.connect(self._prev_month)
        header.addWidget(self._prev_btn)

        self._title = QLabel()
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color: {HEADER}; font-size: 16px; font-weight: bold; padding: 2px;"
        )
        header.addWidget(self._title, 1)

        self._next_btn = self._nav_btn("▶")
        self._next_btn.clicked.connect(self._next_month)
        header.addWidget(self._next_btn)

        layout.addLayout(header)

        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        self._today_btn = QPushButton("📅 今天")
        self._today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._today_btn.setStyleSheet(self._today_btn_style())
        self._today_btn.clicked.connect(self._go_today)
        info_row.addWidget(self._today_btn)

        self._info_lbl = QLabel()
        self._info_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._info_lbl.setStyleSheet(f"color: {WEEKDAY}; font-size: 11px;")
        info_row.addWidget(self._info_lbl, 1)

        layout.addLayout(info_row)

        week_row = QHBoxLayout()
        week_row.setSpacing(0)
        self._weekday_labels = []
        for day in ["一", "二", "三", "四", "五", "六", "日"]:
            lbl = QLabel(day)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            lbl.setFixedHeight(24)
            color = WEEKEND if day in ["六", "日"] else WEEKDAY
            lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
            week_row.addWidget(lbl)
            self._weekday_labels.append(lbl)
        layout.addLayout(week_row)

        self._day_btns = []
        grid = QVBoxLayout()
        grid.setSpacing(2)
        for row in range(6):
            row_layout = QHBoxLayout()
            row_layout.setSpacing(0)
            for col in range(7):
                btn = QPushButton()
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn.setFixedHeight(30)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFlat(True)
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.customContextMenuRequested.connect(
                    lambda pos, r=row, c=col: self._on_right_click(r, c, pos)
                )
                btn.clicked.connect(lambda checked, r=row, c=col: self._on_day_click(r, c))
                row_layout.addWidget(btn)
                self._day_btns.append(btn)
            grid.addLayout(row_layout)
        layout.addLayout(grid)

        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.HLine)
        self._sep.setStyleSheet(f"color: {ACCENT_LIGHT}; margin: 4px 0;")
        layout.addWidget(self._sep)

        self._events_label = QLabel()
        self._events_label.setWordWrap(True)
        self._events_label.setStyleSheet(
            f"color: {NORMAL}; font-size: 12px; padding: 4px 0;"
        )
        self._events_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._events_label)

        layout.addStretch()

    def _nav_btn(self, text):
        btn = QPushButton(text)
        btn.setFixedSize(36, 36)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(self._nav_btn_style())
        return btn

    def _prev_month(self):
        if self._view_month == 1:
            self._view_month = 12
            self._view_year -= 1
        else:
            self._view_month -= 1
        self._update_calendar()

    def _next_month(self):
        if self._view_month == 12:
            self._view_month = 1
            self._view_year += 1
        else:
            self._view_month += 1
        self._update_calendar()

    def _go_today(self):
        self._today = QDate.currentDate()
        self._view_year = self._today.year()
        self._view_month = self._today.month()
        self._selected = self._today
        self._update_calendar()

    def _on_day_click(self, row, col):
        idx = row * 7 + col
        btn = self._day_btns[idx]
        date = btn.property("date")
        if date:
            self._selected = date
            self._update_calendar()
            self.date_selected.emit(date.toString("yyyy-MM-dd"))

    def _menu_style(self):
        """右键菜单样式（跟随主题）。

        原来写死白底 + 橙色高亮，深色模式下弹出一块白色菜单，
        和主界面完全脱节。
        """
        p = Palette(_IS_DARK)
        return (
            "QMenu { background: %(card)s; border: 1px solid %(border)s;"
            " border-radius: 8px; padding: 6px; }"
            "QMenu::item { padding: 6px 20px; color: %(text)s;"
            " border-radius: 4px; }"
            "QMenu::item:selected { background: %(hover_bg)s;"
            " color: %(accent)s; }"
            "QMenu::separator { height: 1px; background: %(border)s;"
            " margin: 4px 8px; }"
            % {"card": p.card, "border": p.border, "text": p.text,
               "hover_bg": p.hover_bg, "accent": p.accent})

    def _dot_icon(self, color_key):
        """画一个该事件颜色的小圆点，用作菜单项图标。

        QAction 不支持富文本，所以不能像工具提示那样写 <span>；
        返回一个 10x10 的圆点图标代替（原来干脆写死黑点 ●）。
        """
        from PyQt6.QtGui import QIcon, QPixmap
        rgb = EVENT_COLORS.get(color_key, EVENT_COLORS[DEFAULT_EVENT_COLOR])[0]
        size = 10
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(rgb)))
        painter.drawEllipse(0, 0, size - 1, size - 1)
        painter.end()
        return QIcon(pm)

    def _on_right_click(self, row, col, pos):
        idx = row * 7 + col
        btn = self._day_btns[idx]
        date = btn.property("date")
        if not date:
            return

        key = date.toString("yyyy-MM-dd")
        existing = self._events.get(key, [])

        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        add_action = menu.addAction("📌 添加标注")

        if existing:
            menu.addSeparator()
            for evt in existing:
                text = evt["text"] if isinstance(evt, dict) else evt
                color = evt.get("color", DEFAULT_EVENT_COLOR) if isinstance(evt, dict) else DEFAULT_EVENT_COLOR
                # 用事件自己的颜色画圆点。
                # 原来这里算出了 dot 却没用，菜单里一律是黑点 ——
                # 同一个文件里的工具提示（_update_upcoming）用的是带颜色的
                # span，两处表现不一致。QAction 不支持富文本，
                # 所以用 setIcon 画一个真正带颜色的圆点。
                del_action = menu.addAction(text)
                try:
                    del_action.setIcon(self._dot_icon(color))
                except Exception:      # noqa: BLE001
                    del_action.setText(f"● {text}")
                del_action.setData(("del", key, evt))

        action = menu.exec(btn.mapToGlobal(pos))

        if action == add_action:
            date_str = date.toString("M月d日")
            dlg = EventDialog(date_str, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                text, color = dlg.get_result()
                if text:
                    if key not in self._events:
                        self._events[key] = []
                    self._events[key].append({"text": text, "color": color})
                    self._save_events()
                    self._update_calendar()
        elif action and action.data():
            data = action.data()
            if data[0] == "del":
                _, k, evt = data
                if k in self._events and evt in self._events[k]:
                    self._events[k].remove(evt)
                    if not self._events[k]:
                        del self._events[k]
                    self._save_events()
                    self._update_calendar()

    def _update_calendar(self):
        months = ["", "1月", "2月", "3月", "4月", "5月", "6月",
                   "7月", "8月", "9月", "10月", "11月", "12月"]
        self._title.setText(f"🌸 {self._view_year}年 {months[self._view_month]}")

        diff = self._today.daysTo(self._selected)
        if diff == 0:
            info = "今天"
        elif diff == 1:
            info = "明天"
        elif diff == -1:
            info = "昨天"
        elif diff > 0:
            info = f"{diff}天后"
        else:
            info = f"{-diff}天前"

        sel_key = self._selected.toString("yyyy-MM-dd")
        if sel_key in self._events:
            names = [e["text"] if isinstance(e, dict) else e for e in self._events[sel_key]]
            info += f"  ·  📌 {', '.join(names)}"
        self._info_lbl.setText(info)

        first = QDate(self._view_year, self._view_month, 1)
        start_day = first.dayOfWeek()
        days_in_month = first.daysInMonth()

        if self._view_month == 1:
            prev_month, prev_year = 12, self._view_year - 1
        else:
            prev_month, prev_year = self._view_month - 1, self._view_year
        days_in_prev = QDate(prev_year, prev_month, 1).daysInMonth()

        for i in range(42):
            btn = self._day_btns[i]
            day_offset = i - (start_day - 1)

            if day_offset < 0:
                day = days_in_prev + day_offset + 1
                date = QDate(prev_year, prev_month, day)
                btn.setText(str(day))
                btn.setProperty("date", date)
                btn.setStyleSheet(self._day_style(OTHER_MONTH, False, False, False, None))
            elif day_offset >= days_in_month:
                day = day_offset - days_in_month + 1
                if self._view_month == 12:
                    next_date = QDate(self._view_year + 1, 1, day)
                else:
                    next_date = QDate(self._view_year, self._view_month + 1, day)
                btn.setText(str(day))
                btn.setProperty("date", next_date)
                btn.setStyleSheet(self._day_style(OTHER_MONTH, False, False, False, None))
            else:
                day = day_offset + 1
                date = QDate(self._view_year, self._view_month, day)
                is_today = (date == self._today)
                is_selected = (date == self._selected)
                is_weekend = (date.dayOfWeek() >= 6)
                color = WEEKEND if is_weekend else NORMAL

                evt_key = date.toString("yyyy-MM-dd")
                evt_color = None
                if evt_key in self._events:
                    evts = self._events[evt_key]
                    if evts:
                        evt_color = evts[0].get("color", DEFAULT_EVENT_COLOR) if isinstance(evts[0], dict) else DEFAULT_EVENT_COLOR

                btn.setText(str(day))
                btn.setProperty("date", date)
                btn.setStyleSheet(self._day_style(color, is_today, is_selected, True, evt_color))

        self._update_upcoming()

    def _update_upcoming(self):
        lines = []
        today = self._today

        for delta in range(0, 31):
            check = today.addDays(delta)
            key = check.toString("yyyy-MM-dd")
            if key in self._events:
                for evt in self._events[key]:
                    text = evt["text"] if isinstance(evt, dict) else evt
                    color = evt.get("color", DEFAULT_EVENT_COLOR) if isinstance(evt, dict) else DEFAULT_EVENT_COLOR
                    dot_color = EVENT_COLORS.get(color, EVENT_COLORS[DEFAULT_EVENT_COLOR])[0]

                    if delta == 0:
                        label = "📍 今天"
                    elif delta == 1:
                        label = "📍 明天"
                    else:
                        label = f"📍 {delta}天后"
                    lines.append(f"<span style='color:{dot_color}'>●</span> {label} · {text}")

        sel_key = self._selected.toString("yyyy-MM-dd")
        self._load_task_history()
        if sel_key in self._task_history:
            tasks = self._task_history[sel_key]
            if tasks:
                lines.append("")
                lines.append(f"<b style='color:{ACCENT}'>✅ {self._selected.toString('M月d日')} 完成的任务：</b>")
                for t in tasks:
                    text = t["text"]
                    tm = t.get("time", "")
                    dur = t.get("duration", 0)
                    if dur > 0:
                        m = dur // 60
                        s = dur % 60
                        dur_str = f" ({m}分{s}秒)" if m > 0 else f" ({s}秒)"
                    else:
                        dur_str = ""
                    lines.append(f"<span style='color:{SUCCESS}'>✓</span> {tm} {text}{dur_str}")

        if lines:
            self._events_label.setText("<br>".join(lines[:12]))
        else:
            self._events_label.setText("<span style='color:#CCB89A'>右键日期可添加标注</span>")

    def _load_task_history(self):
        try:
            if os.path.exists(TASK_HISTORY_FILE):
                with open(TASK_HISTORY_FILE, "r", encoding="utf-8") as f:
                    self._task_history = json.load(f)
        except Exception:
            self._task_history = {}

    def _day_style(self, color, is_today, is_selected, is_current, evt_color):
        # "选中但不是今天"用的是浅色底（ACCENT_LIGHT），白字在上面几乎看不见
        # —— 浅色下它被换成 #E8D5C0 米色，白字对比度不足。按底色明暗选字色。
        on_light = _IS_DARK      # 深色模式下 ACCENT_LIGHT 是深灰，才配白字
        if is_today and is_selected:
            base = (
                f"QPushButton {{ color: white; background: {ACCENT};"
                f" border-radius: 8px; font-size: 13px; font-weight: bold;"
                f" border: none; }}"
            )
        elif is_today:
            base = (
                f"QPushButton {{ color: {ACCENT}; background: {TODAY_BG};"
                f" border-radius: 8px; font-size: 13px; font-weight: bold;"
                f" border: 2px solid {ACCENT}; }}"
            )
        elif is_selected:
            fg = "#FFFFFF" if on_light else NORMAL
            base = (
                f"QPushButton {{ color: {fg}; background: {ACCENT_LIGHT};"
                f" border-radius: 8px; font-size: 13px; font-weight: bold;"
                f" border: none; }}"
            )
        else:
            base = (
                f"QPushButton {{ color: {color}; background: transparent;"
                f" border-radius: 8px; font-size: 13px; border: none; }}"
            )

        if evt_color and evt_color in EVENT_COLORS:
            dot = EVENT_COLORS[evt_color][0]
            base = base.rstrip("}")
            base += f" border-bottom: 3px solid {dot}; }}"

        return base

    def _load_events(self):
        try:
            if os.path.exists(SAVE_FILE):
                with open(SAVE_FILE, "r", encoding="utf-8") as f:
                    self._events = json.load(f)
        except Exception:
            self._events = {}

    def _save_events(self):
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._events, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
