"""Cute calendar widget for ToYu desktop pet — with colored date annotations."""

import json
import os
import datetime
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QAction
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QSizePolicy, QMenu, QScrollArea, QFrame, QDialog,
                              QLineEdit, QDialogButtonBox)

ACCENT = "#FF6B47"
ACCENT_LIGHT = "#FFD4C4"
TODAY_BG = "#FFF0E6"
WEEKDAY = "#8B6914"
WEEKEND = "#E74C3C"
NORMAL = "#5A3E18"
OTHER_MONTH = "#CCB89A"
HEADER = "#FF6B47"
BTN_HOVER = "#FFEEE0"

EVENT_COLORS = {
    "yellow": ("#F5A623", "#FFF8E1"),
    "blue":   ("#4A90D9", "#E3F2FD"),
    "green":  ("#2ECC71", "#E8F5E9"),
}
DEFAULT_EVENT_COLOR = "yellow"
SUCCESS = "#4CAF50"

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
                    f" border: 3px solid #5A3E18; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {dot_color}; border-radius: 14px;"
                    f" border: 3px solid transparent; }}"
                    f"QPushButton:hover {{ border-color: #5A3E18; }}"
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
        self._today_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: {TODAY_BG};"
            f" border-radius: 8px; padding: 4px 14px; font-size: 12px;"
            f" border: 1px solid {ACCENT_LIGHT}; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: white; }}"
        )
        self._today_btn.clicked.connect(self._go_today)
        info_row.addWidget(self._today_btn)

        self._info_lbl = QLabel()
        self._info_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._info_lbl.setStyleSheet(f"color: #8B6914; font-size: 11px;")
        info_row.addWidget(self._info_lbl, 1)

        layout.addLayout(info_row)

        week_row = QHBoxLayout()
        week_row.setSpacing(0)
        for day in ["一", "二", "三", "四", "五", "六", "日"]:
            lbl = QLabel(day)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            lbl.setFixedHeight(24)
            color = WEEKEND if day in ["六", "日"] else WEEKDAY
            lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
            week_row.addWidget(lbl)
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

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {ACCENT_LIGHT}; margin: 4px 0;")
        layout.addWidget(sep)

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
        btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: {TODAY_BG};"
            f" border-radius: 18px; font-size: 16px; font-weight: bold;"
            f" border: 2px solid {ACCENT_LIGHT}; }}"
            f"QPushButton:hover {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}"
        )
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

    def _on_right_click(self, row, col, pos):
        idx = row * 7 + col
        btn = self._day_btns[idx]
        date = btn.property("date")
        if not date:
            return

        key = date.toString("yyyy-MM-dd")
        existing = self._events.get(key, [])

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: white; border: 1px solid #FFD4C4;"
            " border-radius: 8px; padding: 6px; }"
            "QMenu::item { padding: 6px 20px; color: #5A3E18; border-radius: 4px; }"
            "QMenu::item:selected { background: #FFF0E6; color: #FF6B47; }"
        )

        add_action = menu.addAction("📌 添加标注")

        if existing:
            menu.addSeparator()
            for evt in existing:
                text = evt["text"] if isinstance(evt, dict) else evt
                color = evt.get("color", DEFAULT_EVENT_COLOR) if isinstance(evt, dict) else DEFAULT_EVENT_COLOR
                dot = EVENT_COLORS.get(color, EVENT_COLORS[DEFAULT_EVENT_COLOR])[0]
                del_action = menu.addAction(f"● {text}")
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
            base = (
                f"QPushButton {{ color: white; background: {ACCENT_LIGHT};"
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
