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
from datetime import date, datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QStackedWidget, QScrollArea, QCheckBox, QLineEdit
)

FOCUS_PRESETS = (25, 45, 60, 90)
# 宠物区域：够看清动作即可，过高会把计时面板挤扁
SPRITE_BOX = 118
TIMER_MIN_HEIGHT = 268
# 专注结束后自动进入的休息时长
BREAK_MINUTES = 5
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
        self._last_task = None
        self._plan_time_labels = {}
        self._timer_dirty = False
        # 番茄轮次与专注段落记账
        from pet_engine.focus_log import FocusLog
        self._focus_log = FocusLog()
        self._focus_started_at = None       # 当前这段专注/休息的开始时刻
        self._focus_task = ""               # 这段专注对应的任务名
        self._round_kind = "focus"          # 当前这一轮是 focus 还是 break
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
            # 暂停后小窗改为显示"已暂停"，不再显示倒计时
            self.show_mini_timer("计划计时 · %s" % text[:16], "countup",
                                 pause=self.pause_task_timer,
                                 resume=self.resume_last_task_timer,
                                 stop=self.stop_task_timer)
        else:
            self._active_task = text
            self._last_task = text
            self._status.setText("正在计时：%s" % text[:20])
            self._maybe_show_mini(
                "计划计时 · %s" % text[:16], "countup",
                pause=self.pause_task_timer,
                resume=self.resume_last_task_timer,
                stop=self.stop_task_timer)
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
        layout.setSpacing(10)

        self._stage = _PetStage(self)
        layout.addWidget(self._stage)

        # 计时面板占满中间剩余空间：不要额外的 stretch，否则面板被压成
        # 固定高度、上下出现两块不均匀的空白（之前就是这样）。
        self._timer_holder = QStackedWidget()
        self._timer_holder.setStyleSheet("QStackedWidget { background: transparent; }")
        self._timer_holder.setMinimumHeight(TIMER_MIN_HEIGHT)
        layout.addWidget(self._timer_holder, 1)

        # ── 番茄轮次 ──
        # 一轮 = 一次专注 + 它的休息。轮次是天然的成就感来源，
        # 也让"休息"有了归处（以前专注结束什么都不发生）。
        rounds_row = QHBoxLayout()
        rounds_row.setSpacing(8)
        self._rounds_label = QLabel("第 1 轮")
        self._rounds_label.setStyleSheet(
            f"color: {self._c('accent')}; font-size: 11px; font-weight: bold;"
            " background: transparent;")
        rounds_row.addWidget(self._rounds_label)
        self._rounds_dots = QLabel("")
        self._rounds_dots.setStyleSheet(
            f"color: {self._c('accent')}; font-size: 11px; background: transparent;")
        self._rounds_dots.setToolTip("每个圆点代表完成的一轮专注")
        rounds_row.addWidget(self._rounds_dots)
        rounds_row.addStretch()
        # 本轮时长：倒计时一跑起来显示的就是"还剩多少"（25 分钟会立刻显示
        # 24:5x），容易被误认为"选 25 却跳成 24"。这里标明选的是多久。
        self._round_len_label = QLabel("")
        self._round_len_label.setStyleSheet(
            f"color: {self._c('text')}; font-size: 11px; background: transparent;")
        rounds_row.addWidget(self._round_len_label)
        self._rounds_total = QLabel("今日 0 轮")
        self._rounds_total.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        rounds_row.addWidget(self._rounds_total)
        layout.addLayout(rounds_row)

        # ── 今日专注时间轴 ──
        from ui.widgets.focus_timeline import FocusTimeline
        self._timeline = FocusTimeline(self._c)
        layout.addWidget(self._timeline)

        # 状态提示：只在需要说明时显示（空闲时不重复计时面板里的"准备开始"）
        self._state_label = QLabel("")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setWordWrap(True)
        self._state_label.setVisible(False)
        self._state_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(self._state_label)

        # 时长按钮：4 个预设一行，休息单独一行 —— 5 个挤一行时
        # 文字会被压缩到显示不全
        layout.addLayout(self._build_duration_row())
        layout.addLayout(self._build_break_row())

        return card

    def _build_duration_row(self):
        row = QHBoxLayout()
        row.setSpacing(6)
        for minutes in FOCUS_PRESETS:
            b = QPushButton("%d 分钟" % minutes)
            b.setObjectName("secondaryBtn")
            b.setFixedHeight(32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip("立即开始 %d 分钟专注" % minutes)
            b.clicked.connect(lambda checked=False, m=minutes: self.start_focus(m))
            row.addWidget(b, 1)
        return row

    def _build_break_row(self):
        row = QHBoxLayout()
        row.setSpacing(6)
        # 休息按钮：专注结束后会自动进休息，也可以手动提前休息
        # （不用 ☕ 这类 emoji：在部分 Windows 上会渲染成空心方块/圆点）
        self._break_btn = QPushButton("休息 %d 分钟" % BREAK_MINUTES)
        self._break_btn.setObjectName("secondaryBtn")
        self._break_btn.setFixedHeight(30)
        self._break_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._break_btn.setToolTip("现在开始一段 %d 分钟休息；"
                                   "专注结束后也会自动进入休息" % BREAK_MINUTES)
        self._break_btn.clicked.connect(lambda: self.start_break(BREAK_MINUTES))
        row.addWidget(self._break_btn, 1)
        return row

    # ── 右：今日概况 ────────────────────────────────────────
    def _build_stats_card(self):
        card = self._make_card("📈 今日概况")
        layout = card.layout()
        layout.setSpacing(10)

        # 每日目标进度环（与主页共用同一个 tracker，数据一致）
        goal_row = QHBoxLayout()
        goal_row.setSpacing(10)
        from ui.widgets.progress_ring import ProgressRing
        self._goal_ring = ProgressRing(size=76, thickness=7)
        self._goal_ring.setToolTip("今日学习目标进度")
        goal_row.addWidget(self._goal_ring)
        self._goal_text = QLabel("统计中…")
        self._goal_text.setWordWrap(True)
        self._goal_text.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        goal_row.addWidget(self._goal_text, 1)
        layout.addLayout(goal_row)

        layout.addWidget(self._make_sep())

        self._big_focus = QLabel("0 分钟")
        self._big_focus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._big_focus.setStyleSheet(
            f"color: {self._c('accent')}; font-size: 30px; font-weight: bold;"
            " background: transparent;")
        layout.addWidget(self._big_focus)

        cap = QLabel("今日完成的任务累计时长")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setWordWrap(True)
        cap.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 10px; background: transparent;")
        layout.addWidget(cap)

        layout.addWidget(self._make_sep())

        # 统计行：给固定行高与紧凑间距，避免右栏拉高后行距被撑开显得松散
        rows_box = QVBoxLayout()
        rows_box.setSpacing(7)
        self._stat_rows = {}
        for key, label in (("done", "已完成任务"), ("left", "未完成待办"),
                           ("screen", "今日屏幕时间"), ("sessions", "记录段数"),
                           ("rounds", "专注轮次")):
            row = QHBoxLayout()
            row.setSpacing(8)
            tag = QLabel(label)
            tag.setStyleSheet(
                f"color: {self._c('text')}; font-size: 11px; background: transparent;")
            row.addWidget(tag)
            row.addStretch()
            val = QLabel("-")
            val.setStyleSheet(
                f"color: {self._c('mid')}; font-size: 12px; font-weight: bold;"
                " background: transparent;")
            row.addWidget(val)
            rows_box.addLayout(row)
            self._stat_rows[key] = val
        layout.addLayout(rows_box)

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
    # ── 每日目标 ────────────────────────────────────────────
    def refresh_goal(self, info: dict = None):
        """刷新心流窗口里的目标环。info 为 None 时自己取一次。"""
        ring = getattr(self, "_goal_ring", None)
        if ring is None:
            return
        if info is None:
            tracker = getattr(self._main, "_goal_tracker", None)
            if tracker is None:
                return
            try:
                info = tracker.progress()
            except Exception:  # noqa: BLE001
                return

        accent = self._c('accent')
        track = self._c('border')
        fg = self._c('text')
        if info.get("has_goal"):
            ratio = info.get("ratio", 0.0)
            ring.set_state(ratio, "%d%%" % round(ratio * 100), accent, track, fg,
                           font_size=16,
                           full_color="#4CAF50" if info.get("reached") else None)
            if info.get("reached"):
                self._goal_text.setText("今日目标已达成 🎉\n学习 %d 分钟"
                                        % info.get("study_minutes", 0))
            else:
                self._goal_text.setText(
                    "学习 %d / %d 分钟\n还差 %d 分钟"
                    % (info.get("study_minutes", 0), info.get("goal_minutes", 0),
                       info.get("remaining_minutes", 0)))
        else:
            ring.set_state(0.0, "未设", accent, track, fg, font_size=14, dim=True)
            self._goal_text.setText("今日学习 %d 分钟\n（还没设每日目标）"
                                    % info.get("study_minutes", 0))

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

    # ── 状态提示 ────────────────────────────────────────────
    def _set_state(self, text: str, color: str = None):
        """设置中间栏的状态提示。空文本时隐藏整行。

        空闲时不显示 —— 计时面板里本来就有"准备开始"，
        两处重复显示显得啰嗦。
        """
        label = getattr(self, "_state_label", None)
        if label is None:
            return
        text = text or ""
        label.setText(text)
        label.setVisible(bool(text))
        label.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;"
            % (color or self._c("text2")))

    def start_focus(self, minutes):
        self._main.start_focus_session(minutes)
        self._focus_started_at = datetime.now()
        self._focus_task = getattr(self, "_active_task", "") or ""
        self._round_kind = "focus"
        self._round_len_label.setText("本轮 %d 分钟" % minutes)
        self._set_state("专注中 · 已选 %d 分钟" % minutes)
        self._refresh_rounds()
        self._maybe_show_mini(
            "专注倒计时", "countdown",
            pause=self._main.pause_focus_session,
            resume=self._main.resume_focus_session,
            stop=self._main.stop_focus_session)

    # ── 番茄休息 ────────────────────────────────────────────
    def start_break(self, minutes: int = BREAK_MINUTES):
        """开始一段休息。专注结束后会自动调用，也可以手动提前休息。"""
        timer = getattr(self._main, "_timer_widget", None)
        if timer is None:
            return
        # 先把还没记账的专注段落盘（否则这段时间白专注了）
        self._record_session()
        try:
            timer._set_preset(minutes)
            timer._on_start()
        except Exception:  # noqa: BLE001
            try:
                timer._on_start()
            except Exception:  # noqa: BLE001
                pass
        self._focus_started_at = datetime.now()
        self._focus_task = ""
        self._round_kind = "break"
        self._round_len_label.setText("休息 %d 分钟" % minutes)
        self._set_state("休息中 · %d 分钟（离开屏幕活动一下）" % minutes,
                        color=self._c("success"))
        self._status.setText("休息中 · %d 分钟" % minutes)
        self._maybe_show_mini(
            "休息倒计时", "countdown",
            pause=self._main.pause_focus_session,
            resume=self._main.resume_focus_session,
            stop=self._main.stop_focus_session)
        self._refresh_rounds()

    # ── 专注段记账 ──────────────────────────────────────────
    def _record_session(self):
        """把刚结束的一段专注/休息写进日志。

        只有超过 1 分钟才算数（误点开始又立刻停的不该污染统计）。
        """
        started = getattr(self, "_focus_started_at", None)
        if started is None:
            return
        self._focus_started_at = None
        seconds = (datetime.now() - started).total_seconds()
        kind = "break" if getattr(self, "_round_kind", "focus") == "break" else "focus"
        record = self._focus_log.add(kind, seconds,
                                     task=getattr(self, "_focus_task", ""),
                                     started=started)
        if not record:
            return
        if kind == "focus":
            self._status.setText(
                "已完成 1 段专注：%d 分钟%s"
                % (record["minutes"],
                   ("（" + record["task"] + "）") if record["task"] else ""))
        self.refresh_timeline()
        self._refresh_rounds()

    def _on_focus_complete(self):
        """倒计时自然结束的回调。

        值得注意：这里**不处理计划项计时**（那是另一套机制），
        也不在休息结束时自动开始下一轮 —— 自动开始专注会让人措手不及
        （可能正好离开座位）。休息结束后只提示，由用户决定何时开始。
        """
        kind = getattr(self, "_round_kind", "focus")
        self._record_session()
        if kind == "break":
            self._status.setText("休息结束 · 可以从上面选一个时长开始下一轮")
            self._set_state("休息结束 · 可以开始下一轮")
            self._round_kind = "focus"
            self._refresh_rounds()
            pet = getattr(self._main, "_pet", None)
            if pet is not None:
                try:
                    pet.trigger_celebrate(1.6)
                except (RuntimeError, AttributeError):
                    pass
            return
        # 专注结束 → 自动进休息
        self._status.setText("专注结束 · 正在进入休息")
        self.start_break(BREAK_MINUTES)

    def _refresh_rounds(self):
        """刷新轮次显示。"""
        done = self._focus_log.rounds_today()
        current = 1 if getattr(self, "_round_kind", "focus") == "focus" else 0
        if done == 0 and current:
            self._rounds_label.setText("第 1 轮")
        elif current:
            self._rounds_label.setText("第 %d 轮" % (done + 1))
        else:
            self._rounds_label.setText("休息中")
        # 圆点：最多画 8 个，多了用 +N 表示
        shown = min(done, 8)
        dots = "●" * shown + ("＋%d" % (done - 8) if done > 8 else "")
        self._rounds_dots.setText(dots)
        self._rounds_total.setText("今日 %d 轮" % done)

    def refresh_timeline(self):
        """刷新今日专注时间轴。"""
        timeline = getattr(self, "_timeline", None)
        if timeline is None:
            return
        try:
            timeline.set_records(self._focus_log.segments())
        except Exception as exc:  # noqa: BLE001
            print("[Flow] 时间轴刷新失败: %s" % exc)

    def pause_task_timer(self):
        """外部（悬浮小窗）要求暂停计划项计时。"""
        if self._active_task:
            self._active_task = None
            self._refresh_plan()

    def resume_last_task_timer(self):
        text = getattr(self, "_last_task", None)
        if not text:
            return False
        # 直接置为激活项：避免再次走 toggle 的"弹小窗"分支造成递归
        self._active_task = text
        self._status.setText("正在计时：%s" % text[:20])
        self._refresh_plan()
        return True

    def stop_task_timer(self, flush=True):
        self._active_task = None
        self._refresh_plan()
        if flush:
            self._flush_timers()
        # 计划项计时结束，让倒计时（若还在跑）重新接管悬浮小窗
        refresh = getattr(self._main, "refresh_mini_timer", None)
        if refresh is not None:
            refresh()

    # ── 悬浮计时小窗 ────────────────────────────────────────
    def _maybe_show_mini(self, title, mode, **actions):
        """弹出悬浮计时小窗（统一由主窗口持有，避免出现两个小窗）。"""
        self.show_mini_timer(title, mode, **actions)

    def show_mini_timer(self, title, mode, pause=None, resume=None, stop=None):
        self._main.show_mini_timer(title, mode, pause=pause, resume=resume,
                                   stop=stop)

    def hide_mini_timer(self):
        self._main.hide_mini_timer()

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
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
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
            is_break = getattr(self, "_round_kind", "focus") == "break"
            if timer.get_is_running():
                # 倒计时本身就在面板上显示剩余时间，这里只说清"在做什么"
                self._set_state("休息中 · 到点会自动提示" if is_break
                                else "专注中 · 加油",
                                color=self._c("success") if is_break else None)
            elif timer.get_remaining_seconds() > 0:
                self._set_state("已暂停")
            else:
                # 空闲不显示状态行：面板里已有"准备开始"，重复显得啰嗦
                self._set_state("")
        self._tick_task_timer()
        self._stage.refresh()
        self._refresh_stats()
        self.refresh_goal()
        # 时间轴只画过去与"现在"的位置，每秒重绘代价很低；
        # 但没必要每秒都重画，2 秒一次足够看出当前时刻在走。
        self._timeline_counter = (getattr(self, "_timeline_counter", 0) + 1) % 2
        if self._timeline_counter == 0:
            self.refresh_timeline()

    def _refresh_stats(self):
        tasks = self._today_history()
        self._big_focus.setText(_fmt_duration(sum(t.get("duration", 0) for t in tasks)))
        self._stat_rows["done"].setText(str(len(tasks)))

        # 今日专注轮次（来自番茄记账，与"已完成任务"是两套统计）
        try:
            self._stat_rows["rounds"].setText(str(self._focus_log.rounds_today()))
        except Exception:  # noqa: BLE001
            self._stat_rows["rounds"].setText("-")

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
                                         % (pet.affection.level,                                            pet.companion.get_status_text()))
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
        # 目标环随每秒刷新，学完一段就能看到进度动
        self.refresh_goal()
        # 轮次与时间轴在窗口打开时要先出一次（否则要等 2 秒才画）
        self._refresh_rounds()
        self.refresh_timeline()

    def _refresh_goal_lightweight(self):
        """_tick 里用的轻量刷新：只更新目标环，不重建计划栏。"""
        self.refresh_goal()

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
