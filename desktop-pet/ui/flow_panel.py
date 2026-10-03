"""心流模式面板：专注计时 + 今日学习概况 + 宠物可视化。

设计要点：
  * 复用主窗口已有的 TimerWidget 实例（不新建），所以计时状态在
    ToYu 主页与心流模式之间天然同步，切换不会重置。
  * 数据全部来自共享的 settings / tools_hub / screen_tracker / todo_widget，
    本面板不持有任何独立数据源。
"""

import os
from datetime import date, datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QStackedWidget, QScrollArea
)

FOCUS_PRESETS = (25, 45, 60, 90)
SPRITE_BOX = 150
# 计时器（48px 大字显示框 + 进度条 + 按钮组）低于这个高度就会看不见时间
TIMER_MIN_HEIGHT = 300
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")


def _fmt_duration(seconds):
    seconds = int(max(0, seconds))
    if seconds >= 3600:
        return "%d 小时 %d 分" % (seconds // 3600, (seconds % 3600) // 60)
    if seconds >= 60:
        return "%d 分钟" % (seconds // 60)
    return "%d 秒" % seconds


class _PetStage(QLabel):
    """宠物可视化：直接从 PetWindow 取当前精灵图，随宠物状态实时更新。"""

    def __init__(self, owner, parent=None):
        super().__init__(parent)
        self.owner = owner
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(SPRITE_BOX)
        self.setStyleSheet("background: transparent;")

    def refresh(self):
        pet = getattr(self.owner._main, "_pet", None)
        if pet is None or getattr(pet, "_pet_pixmap", None) is None:
            self.setText("宠物还没启动\n回到 ToYu 主页点「启动 ToYu」")
            self.setStyleSheet(
                f"color: {self.owner._c('text2')}; font-size: 12px; background: transparent;")
            return
        try:
            pix = pet._pet_pixmap
            if pix.isNull():
                return
            scaled = pix.scaled(SPRITE_BOX, SPRITE_BOX,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.FastTransformation)
            super().setPixmap(scaled)
            self.setText("")
        except RuntimeError:
            pass


class FlowPanel(QWidget):
    """心流模式面板（作为主窗口「工具」页的第三个子页）。

    这样设计的好处：与 ToYu 主页共用同一套数据池（settings / 宠物 / 工具中枢 /
    屏幕统计），切换只是换一个可见子页，所有状态天然保留。
    """

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self._main = owner
        self.setStyleSheet("background: transparent;")

        root = QHBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 16, 20, 14)

        root.addWidget(self._build_plan_card(), 3)
        root.addWidget(self._build_focus_card(), 4)
        root.addWidget(self._build_stats_card(), 3)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._tick)
        self._refresh_timer.start(1000)
        QTimer.singleShot(300, self.refresh_all)

    # ── 左：今日计划 ────────────────────────────────────────
    def _build_plan_card(self):
        card = self._main._make_card("🎯 今日计划")
        layout = card.layout()
        layout.setSpacing(8)

        self._plan_hint = QLabel("在 ToYu 主页「效率工具」里添加待办，这里会实时同步")
        self._plan_hint.setWordWrap(True)
        self._plan_hint.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(self._plan_hint)

        self._plan_scroll = QScrollArea()
        self._plan_scroll.setWidgetResizable(True)
        self._plan_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._plan_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self._main._c('handle')};"
            " border-radius: 3px; min-height: 20px; }"
        )
        self._plan_container = QWidget()
        self._plan_container.setStyleSheet("background: transparent;")
        self._plan_list = QVBoxLayout(self._plan_container)
        self._plan_list.setContentsMargins(0, 0, 0, 0)
        self._plan_list.setSpacing(6)
        self._plan_list.addStretch()
        self._plan_scroll.setWidget(self._plan_container)
        layout.addWidget(self._plan_scroll, 1)

        go_btn = QPushButton("回 ToYu 主页添加待办")
        go_btn.setObjectName("secondaryBtn")
        go_btn.setFixedHeight(28)
        go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        go_btn.clicked.connect(self.owner.exit_flow_mode)
        layout.addWidget(go_btn)
        return card

    # ── 中：专注计时 ────────────────────────────────────────
    def _build_focus_card(self):
        card = self._main._make_card("🧘 专注")
        layout = card.layout()
        layout.setSpacing(8)

        self._stage = _PetStage(self)
        layout.addWidget(self._stage)

        self._timer_holder = QStackedWidget()
        self._timer_holder.setStyleSheet("QStackedWidget { background: transparent; }")
        # 计时器内部有 48px 大字显示框 + 进度条 + 按钮，压缩后会看不见时间，
        # 所以给它一个明确的最小高度
        self._timer_holder.setMinimumHeight(TIMER_MIN_HEIGHT)
        layout.addWidget(self._timer_holder, 1)

        self._state_label = QLabel("准备开始")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 12px; background: transparent;")
        layout.addWidget(self._state_label)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for minutes in FOCUS_PRESETS:
            btn = QPushButton("%d 分钟" % minutes)
            btn.setObjectName("secondaryBtn")
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip("立即开始 %d 分钟专注" % minutes)
            btn.clicked.connect(lambda checked=False, m=minutes: self._start_focus(m))
            preset_row.addWidget(btn)
        layout.addLayout(preset_row)

        self._focus_tip = QLabel("计时与 ToYu 主页共享同一份状态，切换不会中断")
        self._focus_tip.setWordWrap(True)
        self._focus_tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._focus_tip.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 10px; background: transparent;")
        layout.addWidget(self._focus_tip)
        return card

    # ── 右：今日概况 ────────────────────────────────────────
    def _build_stats_card(self):
        card = self._main._make_card("📈 今日概况")
        layout = card.layout()
        layout.setSpacing(10)

        self._big_focus = QLabel("0 分钟")
        self._big_focus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._big_focus.setStyleSheet(
            f"color: {self._main._c('accent')}; font-size: 30px; font-weight: bold;"
            " background: transparent;")
        layout.addWidget(self._big_focus)

        caption = QLabel("已完成任务累计时长")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(caption)

        self._stat_rows = {}
        for key, label in (("done", "已完成任务"), ("left", "未完成待办"),
                           ("screen", "今日屏幕时间"), ("sessions", "记录段数")):
            row = QHBoxLayout()
            row.setSpacing(8)
            name = QLabel(label)
            name.setStyleSheet(
                f"color: {self._main._c('text')}; font-size: 12px; background: transparent;")
            row.addWidget(name)
            row.addStretch()
            value = QLabel("-")
            value.setStyleSheet(
                f"color: {self._main._c('mid')}; font-size: 12px; font-weight: bold;"
                " background: transparent;")
            row.addWidget(value)
            layout.addLayout(row)
            self._stat_rows[key] = value

        sep = self._main._h_separator()
        layout.addWidget(sep)

        self._mood_label = QLabel("")
        self._mood_label.setWordWrap(True)
        self._mood_label.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 11px; background: transparent;")
        layout.addWidget(self._mood_label)

        layout.addStretch()

        open_data = QPushButton("查看完整统计")
        open_data.setObjectName("secondaryBtn")
        open_data.setFixedHeight(28)
        open_data.setCursor(Qt.CursorShape.PointingHandCursor)
        open_data.clicked.connect(lambda: self._goto_main_page("工具", sub=2))
        layout.addWidget(open_data)
        return card

    # ── 行为 ────────────────────────────────────────────────
    def _goto_main_page(self, label, sub=None):
        self.owner.exit_flow_mode()
        self._main._page_btns[label].click()
        if sub is not None:
            self._main._switch_tools_page(sub)

    def _start_focus(self, minutes):
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
            running = timer.get_is_running()
            remaining = timer.get_remaining_seconds()
            if running:
                self._state_label.setText("专注中 · 剩余 %s" % _fmt_duration(remaining))
            elif remaining > 0:
                self._state_label.setText("已暂停 · 剩余 %s" % _fmt_duration(remaining))
            else:
                self._state_label.setText("准备开始")
        self._stage.refresh()
        self._refresh_stats()

    def _refresh_stats(self):
        tasks = self._today_history()
        total = sum(t.get("duration", 0) for t in tasks)
        self._big_focus.setText(_fmt_duration(total))
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
                today_total = sum(s for _a, s in tracker.get_today_data())
                self._stat_rows["screen"].setText(_fmt_duration(today_total))
                self._stat_rows["sessions"].setText(
                    str(len(tracker.get_sessions())))
            except Exception:
                self._stat_rows["sessions"].setText("-")

        pet = getattr(self._main, "_pet", None)
        if pet is not None:
            try:
                self._mood_label.setText(
                    "宠物状态：好感度 %d · %s"
                    % (pet.affection.level, pet.companion.get_status_text()))
            except (RuntimeError, AttributeError):
                self._mood_label.setText("")
        else:
            self._mood_label.setText("宠物尚未启动")

    def _refresh_plan(self):
        while self._plan_list.count() > 1:
            item = self._plan_list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        todo = getattr(self._main, "_todo_widget", None)
        entries = []
        if todo is not None:
            try:
                entries = [t for t in todo.todos if not t.done]
            except RuntimeError:
                entries = []

        if not entries:
            empty = QLabel("暂无未完成待办")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {self._main._c('text2')}; font-size: 12px; padding: 20px;"
                " background: transparent;")
            self._plan_list.insertWidget(0, empty)
            return

        for i, item in enumerate(entries[:20]):
            frame = QFrame()
            frame.setStyleSheet(
                f"QFrame {{ background: {self._main._c('tab_bg')};"
                f" border: 1px solid {self._main._c('border')}; border-radius: 8px; }}")
            row = QHBoxLayout(frame)
            row.setContentsMargins(10, 6, 8, 6)
            row.setSpacing(8)
            mark = QLabel("○")
            mark.setStyleSheet(
                f"color: {self._main._c('accent')}; font-size: 12px; background: transparent;")
            row.addWidget(mark)
            text = QLabel(item.text)
            text.setWordWrap(True)
            text.setStyleSheet(
                f"color: {self._main._c('text')}; font-size: 12px; background: transparent;")
            row.addWidget(text, 1)
            self._plan_list.insertWidget(i, frame)

    def refresh_all(self):
        self._stage.refresh()
        self._refresh_plan()
        self._refresh_stats()

    def restyle(self):
        """深浅色切换后重新取色（结构简单，只刷标题与文字）。"""
        self._plan_hint.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 11px; background: transparent;")
        self._state_label.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 12px; background: transparent;")
        self._big_focus.setStyleSheet(
            f"color: {self._main._c('accent')}; font-size: 30px; font-weight: bold;"
            " background: transparent;")
        self._mood_label.setStyleSheet(
            f"color: {self._main._c('text2')}; font-size: 11px; background: transparent;")
        self.refresh_all()
