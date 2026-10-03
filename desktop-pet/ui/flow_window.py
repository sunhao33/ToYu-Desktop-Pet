"""心流模式：独立顶层窗口。

设计要点：
  * 它是**独立的窗口**（有自己的头部、状态栏、标签栏），不是主窗口的子页。
  * 但它**不持有任何数据**：settings / 宠物实例 / 计时器实例 / 工具中枢 /
    屏幕统计全部取自主窗口，所以两边完全互通、切换不丢状态。
  * 计时器是同一个实例（在主窗口与心流窗口之间搬移），因此专注计时
    在两端天然同步，切回来不会重置。
"""

import os
import json
from datetime import date

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QScrollArea, QCheckBox, QLineEdit
)

FOCUS_PRESETS = (25, 45, 60, 90)
SPRITE_BOX = 150
TIMER_MIN_HEIGHT = 300
# 尺寸与主窗口保持一致（方案 A：由实测内容需求决定）
MIN_SIZE = (980, 850)
START_SIZE = (1120, 880)
ICON_SIZE = 34
RESOURCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
# 每个计划项的累计计时（按日期 + 任务文本记录，可跨窗口/重启保留）
FLOW_TIMER_FILE = os.path.join(
    os.path.expanduser("~"), "AppData", "Roaming", "ToYu", "flow_timers.json")


def load_flow_timers():
    """读取 {日期: {任务文本: 累计秒数}}。"""
    try:
        if os.path.exists(FLOW_TIMER_FILE):
            with open(FLOW_TIMER_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_flow_timers(data):
    try:
        os.makedirs(os.path.dirname(FLOW_TIMER_FILE), exist_ok=True)
        tmp = FLOW_TIMER_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, FLOW_TIMER_FILE)
    except Exception:
        pass


def app_icon():
    """程序图标：优先用 128px 版本，回退到 ico。

    心流窗口头部与主窗口「心流模式」按钮共用这一个图标，
    保证两处视觉一致。
    """
    for name in ("toyu_128.png", "toyu_icon.ico", "icon.ico"):
        path = os.path.join(RESOURCE_DIR, name)
        if os.path.exists(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon
    return QIcon()


# 兼容旧调用名
_app_icon = app_icon


def _fmt_duration(seconds):
    seconds = int(max(0, seconds))
    if seconds >= 3600:
        return "%d 小时 %d 分" % (seconds // 3600, (seconds % 3600) // 60)
    if seconds >= 60:
        return "%d 分钟" % (seconds // 60)
    return "%d 秒" % seconds


def _fmt_clock(seconds):
    """计划项用时：紧凑的 时:分:秒 形式。"""
    seconds = int(max(0, seconds))
    return "%02d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


class _PetStage(QLabel):
    """宠物可视化：直接从 PetWindow 取当前精灵图，跟随宠物状态实时更新。"""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window_ref = window
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(SPRITE_BOX)
        self.setStyleSheet("background: transparent;")

    def refresh(self):
        pet = getattr(self.window_ref._main, "_pet", None)
        if pet is None or getattr(pet, "_pet_pixmap", None) is None:
            self.setText("宠物还没启动\n回到 ToYu 点「启动 ToYu」即可")
            self.setStyleSheet(
                f"color: {self.window_ref._c('text2')}; font-size: 12px;"
                " background: transparent;")
            return
        try:
            pix = pet._pet_pixmap
            if pix.isNull():
                return
            super().setPixmap(pix.scaled(
                SPRITE_BOX, SPRITE_BOX,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation))
            self.setText("")
        except RuntimeError:
            pass


class FlowWindow(QMainWindow):
    """心流模式独立窗口。"""

    def __init__(self, main_window):
        super().__init__()
        self._main = main_window
        self.settings = main_window.settings
        # 计划项独立计时：{日期: {任务文本: 累计秒数}}，以及当前正在计时的项
        self._flow_timers = load_flow_timers()
        self._active_task = None
        self._plan_time_labels = {}
        self._timer_dirty = False
        self.setWindowTitle("心流模式 · ToYu")
        self.setWindowIcon(_app_icon())
        self.setMinimumSize(*MIN_SIZE)
        self.resize(*START_SIZE)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())
        root.addWidget(self._make_sep())

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        row = QHBoxLayout(body)
        row.setSpacing(14)
        row.setContentsMargins(20, 16, 20, 10)
        # 计划栏有「勾选框 + 任务名 + 计时 + 两个按钮」，比另两栏更需要宽度
        row.addWidget(self._build_plan_card(), 4)
        row.addWidget(self._build_focus_card(), 4)
        row.addWidget(self._build_stats_card(), 3)
        root.addWidget(body, 1)

        root.addWidget(self._make_sep())
        root.addWidget(self._build_statusbar())

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._tick)
        self._refresh_timer.start(1000)

        # 待办在主页被增删改时，计划栏要跟着刷新
        self._connect_todo_signals()

    # ── 取色（与主窗口同一套）────────────────────────────────
    def _c(self, key):
        return self._main._c(key)

    def _make_sep(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {self._c('border')}; max-height: 1px;")
        return sep

    def _make_card(self, title):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        layout.addWidget(label)
        return card

    # ── 头部 ────────────────────────────────────────────────
    def _build_header(self):
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(80)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(24, 14, 24, 14)

        # 用 ToYu 自己的图标，不用 emoji（emoji 在不同系统上渲染差异大、也不统一）
        logo = QLabel()
        logo.setFixedSize(48, 48)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background: transparent;")
        logo_pix = _app_icon().pixmap(ICON_SIZE, ICON_SIZE)
        if not logo_pix.isNull():
            logo.setPixmap(logo_pix)
        else:
            logo.setText("🥔")
            logo.setStyleSheet("font-size: 28px; background: transparent;")
        lay.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        t = QLabel("心流模式")
        t.setObjectName("headerTitle")
        title_box.addWidget(t)
        s = QLabel("专注当下 · ToYu 陪你")
        s.setObjectName("headerSub")
        title_box.addWidget(s)
        lay.addLayout(title_box)
        lay.addStretch()

        self._dark_btn = QPushButton("🌙 深色")
        self._dark_btn.setFixedHeight(32)
        self._dark_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dark_btn.setToolTip("切换深色/浅色模式（与 ToYu 共用设置）")
        self._dark_btn.setStyleSheet(self._header_btn_style())
        self._dark_btn.clicked.connect(self._on_toggle_dark)
        lay.addWidget(self._dark_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._back_btn = QPushButton("↩ 回到 ToYu")
        self._back_btn.setObjectName("startBtn")
        self._back_btn.setFixedHeight(38)
        self._back_btn.setMinimumWidth(140)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setToolTip("关闭心流模式，回到 ToYu 主窗口")
        self._back_btn.clicked.connect(self._main.exit_flow_mode)
        lay.addWidget(self._back_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        return header

    def _header_btn_style(self):
        return f"""
            QPushButton {{
                background: {self._c('hover_bg')};
                border: 1px solid {self._c('accent')};
                font-size: 12px;
                font-weight: bold;
                color: {self._c('mid')};
                border-radius: 8px;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background: {self._c('press_bg')};
                border-color: {self._c('accent_h')};
            }}
        """

    # ── 左：今日计划（可交互）────────────────────────────────
    def _build_plan_card(self):
        card = self._make_card("🎯 今日计划")
        layout = card.layout()
        layout.setSpacing(8)

        self._plan_hint = QLabel("点「▶ 计时」给某一项单独计时，同一时刻只跑一项；勾选完成会把该项用时记入今日统计")
        self._plan_hint.setWordWrap(True)
        self._plan_hint.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(self._plan_hint)

        # 就地添加待办，不用跑回主页
        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        self._plan_input = QLineEdit()
        self._plan_input.setPlaceholderText("添加待办…")
        self._plan_input.setFixedHeight(34)
        # 明确给出边框与底色：默认样式在浅色卡片上几乎看不见
        self._plan_input.setStyleSheet(f"""
            QLineEdit {{
                background: {self._c('input_bg')};
                border: 1px solid {self._c('border')};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 12px;
                color: {self._c('text')};
            }}
            QLineEdit:focus {{
                border-color: {self._c('accent')};
            }}
        """)
        self._plan_input.returnPressed.connect(self._on_add_task)
        add_row.addWidget(self._plan_input, 1)
        self._plan_add_btn = QPushButton("＋")
        self._plan_add_btn.setObjectName("secondaryBtn")
        self._plan_add_btn.setFixedSize(34, 34)
        self._plan_add_btn.setToolTip("添加这条待办（Enter 也可以）")
        self._plan_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._plan_add_btn.clicked.connect(self._on_add_task)
        add_row.addWidget(self._plan_add_btn)
        layout.addLayout(add_row)

        self._plan_progress = QLabel("")
        self._plan_progress.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(self._plan_progress)

        self._plan_scroll = QScrollArea()
        self._plan_scroll.setWidgetResizable(True)
        self._plan_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._plan_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')};"
            " border-radius: 3px; min-height: 20px; }")
        self._plan_container = QWidget()
        self._plan_container.setStyleSheet("background: transparent;")
        self._plan_list = QVBoxLayout(self._plan_container)
        self._plan_list.setContentsMargins(0, 0, 0, 0)
        self._plan_list.setSpacing(6)
        self._plan_list.addStretch()
        self._plan_scroll.setWidget(self._plan_container)
        layout.addWidget(self._plan_scroll, 1)

        tip = QLabel("提示：先选中一条待办再开始专注，完成后勾选会把专注用时一起记上")
        tip.setWordWrap(True)
        tip.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 10px; background: transparent;")
        layout.addWidget(tip)
        return card

    def _on_add_task(self):
        text = self._plan_input.text().strip()
        if not text:
            return
        todo = getattr(self._main, "_todo_widget", None)
        if todo is None:
            return
        try:
            todo._input.setText(text)
            todo._on_add()
            self._plan_input.clear()
        except RuntimeError:
            return
        QTimer.singleShot(200, self._refresh_plan)

    # ── 计划项计时 ──────────────────────────────────────────
    def _task_secs(self, text):
        """该任务今天的累计用时（秒）。"""
        return int(self._flow_timers.get(date.today().isoformat(), {}).get(text, 0))

    def _add_task_secs(self, text, secs):
        day = date.today().isoformat()
        bucket = self._flow_timers.setdefault(day, {})
        bucket[text] = int(bucket.get(text, 0)) + int(secs)
        save_flow_timers(self._flow_timers)

    def toggle_task_timer(self, text):
        """开始/暂停某个计划项的计时。

        同一时刻只跑一个任务：点另一个任务会自动把上一个暂停
        （避免两个任务同时累加时间，那会让统计失真）。
        """
        if self._active_task == text:
            self._active_task = None
            self._status.setText("已暂停计时")
        else:
            self._active_task = text
            self._status.setText("正在计时：%s" % text[:20])
        self._refresh_plan()

    def _tick_task_timer(self):
        """每秒给当前计时的计划项累加 1 秒。"""
        if not self._active_task:
            return
        day = date.today().isoformat()
        bucket = self._flow_timers.setdefault(day, {})
        bucket[self._active_task] = int(bucket.get(self._active_task, 0)) + 1
        self._timer_dirty = True
        for text, label in self._plan_time_labels.items():
            if text == self._active_task:
                label.setText(_fmt_clock(bucket[self._active_task]))
                if not label.isVisible():
                    label.setVisible(True)
        # 定期落盘：程序异常退出时不至于丢掉未保存的计时
        self._since_save = getattr(self, "_since_save", 0) + 1
        if self._since_save >= 15:
            self._flush_timers()

    def _flush_timers(self):
        if getattr(self, "_timer_dirty", False):
            save_flow_timers(self._flow_timers)
            self._timer_dirty = False
            self._since_save = 0

    def _on_toggle_task(self, todo, checked):
        """勾选完成/取消完成，并同步到主页待办。

        完成时优先记该计划项自己的计时（累计用时的**新增部分**），
        没有用过计划项计时才退回共享计时器的已用时长。
        """
        widget = getattr(self._main, "_todo_widget", None)
        if widget is None:
            return
        try:
            if bool(todo.done) != bool(checked):
                if checked:
                    elapsed = self._task_secs(todo.text)
                    if elapsed <= 0:
                        timer = getattr(self._main, "_timer_widget", None)
                        if timer is not None:
                            elapsed = timer.get_elapsed_seconds()
                    if self._active_task == todo.text:
                        self._active_task = None
                    widget._toggle_todo_by_ref(todo, elapsed_seconds=elapsed)
                else:
                    widget._toggle_todo_by_ref(todo)
        except RuntimeError:
            return
        QTimer.singleShot(200, self._refresh_plan)

    def _on_delete_task(self, todo):
        widget = getattr(self._main, "_todo_widget", None)
        if widget is None:
            return
        try:
            widget._delete_todo_by_ref(todo)
        except RuntimeError:
            return
        QTimer.singleShot(200, self._refresh_plan)

    # ── 中：专注 ────────────────────────────────────────────
    def _build_focus_card(self):
        card = self._make_card("⏱ 专注")
        layout = card.layout()
        layout.setSpacing(8)

        self._stage = _PetStage(self)
        layout.addWidget(self._stage)

        self._timer_holder = QStackedWidget()
        self._timer_holder.setStyleSheet("QStackedWidget { background: transparent; }")
        self._timer_holder.setMinimumHeight(TIMER_MIN_HEIGHT)
        layout.addWidget(self._timer_holder, 1)

        self._state_label = QLabel("准备开始")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 12px; background: transparent;")
        layout.addWidget(self._state_label)

        # 心流模式自带的快捷按钮（计时器里的 9 个预设会被隐藏，避免两套并存）
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for minutes in FOCUS_PRESETS:
            b = QPushButton("%d 分钟" % minutes)
            b.setObjectName("secondaryBtn")
            b.setFixedHeight(30)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip("立即开始 %d 分钟专注" % minutes)
            b.clicked.connect(lambda checked=False, m=minutes: self.start_focus(m))
            preset_row.addWidget(b)
        layout.addLayout(preset_row)

        tip = QLabel("计时与 ToYu 共用同一份状态，来回切换不会中断")
        tip.setWordWrap(True)
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 10px; background: transparent;")
        layout.addWidget(tip)
        return card

    # ── 右：今日概况 ────────────────────────────────────────
    def _build_stats_card(self):
        card = self._make_card("📈 今日概况")
        layout = card.layout()
        layout.setSpacing(10)

        self._big_focus = QLabel("0 分钟")
        self._big_focus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._big_focus.setStyleSheet(
            f"color: {self._c('accent')}; font-size: 30px; font-weight: bold;"
            " background: transparent;")
        layout.addWidget(self._big_focus)

        cap = QLabel("已完成任务累计时长")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(cap)

        self._stat_rows = {}
        for key, label in (("done", "已完成任务"), ("left", "未完成待办"),
                           ("screen", "今日屏幕时间"), ("sessions", "记录段数")):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.itemAt(0).widget().setStyleSheet(
                f"color: {self._c('text')}; font-size: 12px; background: transparent;")
            row.addStretch()
            val = QLabel("-")
            val.setStyleSheet(
                f"color: {self._c('mid')}; font-size: 12px; font-weight: bold;"
                " background: transparent;")
            row.addWidget(val)
            layout.addLayout(row)
            self._stat_rows[key] = val

        layout.addWidget(self._make_sep())

        self._mood_label = QLabel("")
        self._mood_label.setWordWrap(True)
        self._mood_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(self._mood_label)
        layout.addStretch()

        btn = QPushButton("查看完整统计")
        btn.setObjectName("secondaryBtn")
        btn.setFixedHeight(28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._goto_main("工具", sub=2))
        layout.addWidget(btn)
        return card

    # ── 状态栏 ──────────────────────────────────────────────
    def _build_statusbar(self):
        bar = QWidget()
        bar.setObjectName("statusBar")
        bar.setFixedHeight(30)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        self._status = QLabel("心流模式 · 专注中")
        self._status.setStyleSheet(
            f"color: {self._c('accent')}; font-size: 11px; font-weight: bold;"
            " background: transparent;")
        lay.addWidget(self._status)
        lay.addStretch()
        self._affection = QLabel("")
        self._affection.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        lay.addWidget(self._affection)
        return bar

    # ── 行为 ────────────────────────────────────────────────
    def _goto_main(self, label, sub=None):
        self._main.exit_flow_mode()
        self._main._page_btns[label].click()
        if sub is not None:
            self._main._switch_tools_page(sub)

    def start_focus(self, minutes):
        timer = getattr(self._main, "_timer_widget", None)
        if timer is None:
            return
        timer._set_preset(minutes)
        timer._on_start()
        self._state_label.setText("专注中 · %d 分钟" % minutes)
        pet = getattr(self._main, "_pet", None)
        if pet is not None:
            try:
                pet.trigger_dance(2.0)
            except RuntimeError:
                pass

    def _on_toggle_dark(self):
        self._main._toggle_dark_mode()
        self.apply_theme()

    def apply_theme(self):
        """深浅色切换后刷新本窗口的样式（跟随主窗口模式）。"""
        self.setStyleSheet(self._main._global_stylesheet()
                           if not self._main._is_dark_mode
                           else self._main._dark_stylesheet())
        self._dark_btn.setText("☀️ 浅色" if self._main._is_dark_mode else "🌙 深色")
        self._dark_btn.setStyleSheet(self._header_btn_style())
        self._status.setStyleSheet(
            f"color: {self._c('accent')}; font-size: 11px; font-weight: bold;"
            " background: transparent;")
        self._affection.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        self._big_focus.setStyleSheet(
            f"color: {self._c('accent')}; font-size: 30px; font-weight: bold;"
            " background: transparent;")
        self._plan_hint.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        self._plan_progress.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        self._plan_input.setStyleSheet(f"""
            QLineEdit {{
                background: {self._c('input_bg')};
                border: 1px solid {self._c('border')};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 12px;
                color: {self._c('text')};
            }}
            QLineEdit:focus {{
                border-color: {self._c('accent')};
            }}
        """)
        self._state_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 12px; background: transparent;")
        self._mood_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        self.refresh_all()

    # ── 刷新 ────────────────────────────────────────────────
    def _today_history(self):
        import json
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r", encoding="utf-8") as fh:
                    return json.load(fh).get(date.today().isoformat(), [])
        except Exception:
            pass
        return []

    def _tick(self):
        timer = getattr(self._main, "_timer_widget", None)
        if timer is not None:
            if timer.get_is_running():
                self._state_label.setText(
                    "专注中 · 剩余 %s" % _fmt_duration(timer.get_remaining_seconds()))
            elif timer.get_remaining_seconds() > 0:
                self._state_label.setText(
                    "已暂停 · 剩余 %s" % _fmt_duration(timer.get_remaining_seconds()))
            else:
                self._state_label.setText("准备开始")
        self._tick_task_timer()
        self._stage.refresh()
        self._refresh_stats()

    def _refresh_stats(self):
        tasks = self._today_history()
        self._big_focus.setText(_fmt_duration(sum(t.get("duration", 0) for t in tasks)))
        self._stat_rows["done"].setText(str(len(tasks)))

        todo = getattr(self._main, "_todo_widget", None)
        if todo is not None:
            try:
                self._stat_rows["left"].setText(str(todo.get_incomplete_count()))
            except RuntimeError:
                self._stat_rows["left"].setText("-")

        tracker = getattr(self._main, "_screen_tracker", None)
        if tracker is not None:
            try:
                self._stat_rows["screen"].setText(
                    _fmt_duration(sum(s for _a, s in tracker.get_today_data())))
                self._stat_rows["sessions"].setText(str(len(tracker.get_sessions())))
            except Exception:
                self._stat_rows["sessions"].setText("-")

        pet = getattr(self._main, "_pet", None)
        if pet is not None:
            try:
                self._mood_label.setText("宠物状态：好感度 %d · %s"
                                         % (pet.affection.level,
                                            pet.companion.get_status_text()))
                self._affection.setText("❤ %d/100" % pet.affection.level)
            except (RuntimeError, AttributeError):
                self._mood_label.setText("")
        else:
            self._mood_label.setText("宠物尚未启动")
            self._affection.setText("")

    def _clear_plan_rows(self):
        """清空计划栏里的行。

        必须先 takeAt 把控件从布局摘掉、再 setParent(None)，
        只用 deleteLater() 的话控件在重绘前仍可见，会出现"渲染两份"的残影。
        """
        self._plan_time_labels = {}
        while self._plan_list.count() > 1:
            item = self._plan_list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _refresh_plan(self):
        self._clear_plan_rows()

        todo = getattr(self._main, "_todo_widget", None)
        pending, done_count, total = [], 0, 0
        if todo is not None:
            try:
                all_todos = list(todo.todos)
                total = len(all_todos)
                done_count = sum(1 for t in all_todos if t.done)
                pending = [t for t in all_todos if not t.done]
            except RuntimeError:
                pending = []

        if total:
            self._plan_progress.setText("进度 %d/%d 已完成" % (done_count, total))
        else:
            self._plan_progress.setText("还没有待办")

        if not pending:
            empty = QLabel("全部完成啦 🎉" if total else "还没有待办，上面加一条试试")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color: {self._c('text2')}; font-size: 12px; padding: 20px;"
                " background: transparent;")
            self._plan_list.insertWidget(0, empty)
            return

        for i, item in enumerate(pending[:30]):
            frame = QFrame()
            frame.setStyleSheet(
                f"QFrame {{ background: {self._c('tab_bg')};"
                f" border: 1px solid {self._c('border')}; border-radius: 8px; }}")
            row = QHBoxLayout(frame)
            row.setContentsMargins(8, 5, 6, 5)
            row.setSpacing(6)

            box = QCheckBox()
            box.setChecked(False)
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.setToolTip("标记为已完成（会把这项的计时一起记入今日统计）")
            box.clicked.connect(
                lambda checked=False, t=item: self._on_toggle_task(t, checked))
            row.addWidget(box)

            text = QLabel(item.text)
            text.setWordWrap(True)
            text.setStyleSheet(
                f"color: {self._c('text')}; font-size: 12px; background: transparent;")
            row.addWidget(text, 1)

            # 每个计划项自己的计时开关与累计用时（没有用时就不占位）
            active = self._active_task == item.text
            secs = self._task_secs(item.text)

            time_label = QLabel(_fmt_clock(secs) if (secs or active) else "")
            time_label.setVisible(bool(secs or active))
            time_label.setStyleSheet(
                f"color: {self._c('accent') if active else self._c('text2')};"
                " font-size: 11px; background: transparent;")
            time_label.setToolTip("这一项今天累计专注的时长")
            row.addWidget(time_label)
            self._plan_time_labels[item.text] = time_label

            t_btn = QPushButton("⏸ 计时中" if active else "▶ 计时")
            t_btn.setFixedHeight(24)
            t_btn.setMinimumWidth(64 if not active else 74)
            t_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            t_btn.setToolTip("暂停这一项的计时" if active else "开始给这一项单独计时")
            t_btn.setStyleSheet(
                "QPushButton {"
                f" background: {self._c('accent') if active else 'transparent'};"
                f" border: 1px solid {self._c('accent') if active else self._c('border')};"
                " border-radius: 6px; padding: 2px 6px;"
                f" color: {'#FFFFFF' if active else self._c('text2')};"
                " font-size: 11px; }"
                f"QPushButton:hover {{ border-color: {self._c('accent_h')};"
                f" color: {'#FFFFFF' if active else self._c('accent')}; }}")
            t_btn.clicked.connect(
                lambda checked=False, t=item.text: self.toggle_task_timer(t))
            row.addWidget(t_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(20, 20)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("删除这条待办")
            del_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none;"
                f" color: {self._c('text2')}; font-size: 11px; }}"
                "QPushButton:hover { color: #D9534F; }")
            del_btn.clicked.connect(lambda checked=False, t=item: self._on_delete_task(t))
            row.addWidget(del_btn)
            self._plan_list.insertWidget(i, frame)

    def _connect_todo_signals(self):
        """待办变化时自动刷新计划栏（主页添加/删除也会同步过来）。"""
        todo = getattr(self._main, "_todo_widget", None)
        if todo is None:
            return
        for sig in ("task_added", "task_completed"):
            s = getattr(todo, sig, None)
            if s is not None:
                try:
                    s.connect(self._refresh_plan)
                except TypeError:
                    pass

    def refresh_all(self):
        self._stage.refresh()
        self._refresh_plan()
        self._refresh_stats()

    def attach_timer(self, timer):
        """接管共享计时器实例（不复制，状态自然延续）。"""
        if timer is None:
            return
        timer.setParent(None)
        self._timer_holder.addWidget(timer)
        timer.show()
        # 心流页自带快捷按钮，隐藏计时器里那 9 个预设与自定义时间输入
        setter = getattr(timer, "set_compact_mode", None)
        if setter is not None:
            setter(True)

    def detach_timer(self):
        timer = getattr(self._main, "_timer_widget", None)
        if timer is not None:
            setter = getattr(timer, "set_compact_mode", None)
            if setter is not None:
                setter(False)      # 还给主页时恢复完整模式
            self._timer_holder.removeWidget(timer)
            timer.setParent(None)
        return timer

    def closeEvent(self, event):
        """关掉心流窗口等于回到 ToYu（用户按 X 时不能把程序留成"没有窗口"）。"""
        self._flush_timers()
        if self._main._flow_active:
            event.ignore()
            self._main.exit_flow_mode()
            return
        super().closeEvent(event)

    def hideEvent(self, event):
        """隐藏时也要落盘：切回主窗口时正在计时的进度不能丢。"""
        self._flush_timers()
        super().hideEvent(event)
