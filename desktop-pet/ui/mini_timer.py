"""悬浮计时小窗：圆角矩形的置顶小窗口。

设计要点：
  * 它**不持有任何计时状态**，只按秒读取「当前正在计时的那一件事」并显示 ——
    这样计时精度仍由唯一的计时源（TimerWidget 或计划项计时）负责，
    小窗不会和主界面算出两个不一样的时间。
  * 三种模式：
      countdown —— 专注倒计时（读 TimerWidget 的剩余时间，带进度环）
      countup   —— 计划项正计时（读计划项的累计用时）
      idle      —— 计时已结束
  * 圆角 + 无边框 + 置顶 + 可拖动，位置记在设置里。
"""

import math

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)

from ui.widgets.progress_ring import ProgressRing

WIDTH = 240
HEIGHT = 150
CORNER = 18
RING = 74


def _clock(seconds):
    seconds = int(max(0, seconds))
    return "%02d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def _compact(seconds):
    """剩余时间不足 1 小时时用 mm:ss，更醒目。"""
    seconds = int(max(0, seconds))
    if seconds >= 3600:
        return _clock(seconds)
    return "%02d:%02d" % (seconds // 60, seconds % 60)


class MiniTimerWindow(QWidget):
    """圆角矩形悬浮计时窗。"""

    def __init__(self, main_window, restore_cb=None):
        super().__init__(None)
        self._main = main_window
        self._restore_cb = restore_cb
        self._mode = "idle"
        self._title = ""
        self._pause_cb = None
        self._resume_cb = None
        self._stop_cb = None
        self._paused = False
        self._drag_from = None

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WIDTH, HEIGHT)
        self.setToolTip("拖动可移动位置 · 双击回到窗口")

        self._build_ui()
        self._restore_position()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    # ── 界面 ────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._title_label = QLabel("计时")
        self._title_label.setStyleSheet(
            "color: #8B7355; font-size: 11px; background: transparent;")
        top.addWidget(self._title_label, 1)
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("结束并关闭小窗")
        self._close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            " color: #B0A090; font-size: 12px; border-radius: 10px; }"
            "QPushButton:hover { background: #F0E0D0; color: #D9534F; }")
        self._close_btn.clicked.connect(self._on_close)
        top.addWidget(self._close_btn)
        root.addLayout(top)

        mid = QHBoxLayout()
        mid.setSpacing(10)
        self._ring = ProgressRing(size=RING, thickness=5)
        mid.addWidget(self._ring)

        info = QVBoxLayout()
        info.setSpacing(4)
        self._state_label = QLabel("准备开始")
        self._state_label.setStyleSheet(
            "color: #2C1810; font-size: 12px; font-weight: bold;"
            " background: transparent;")
        info.addWidget(self._state_label)
        self._detail_label = QLabel("")
        self._detail_label.setWordWrap(True)
        self._detail_label.setStyleSheet(
            "color: #8B7355; font-size: 10px; background: transparent;")
        info.addWidget(self._detail_label)
        info.addStretch()
        mid.addLayout(info, 1)
        root.addLayout(mid)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        self._pause_btn = QPushButton("⏸ 暂停")
        self._pause_btn.setFixedHeight(26)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self._on_pause_toggle)
        btns.addWidget(self._pause_btn, 1)
        self._back_btn = QPushButton("↗ 回到窗口")
        self._back_btn.setFixedHeight(26)
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setToolTip("收起小窗并打开 ToYu 窗口")
        self._back_btn.clicked.connect(self._on_back)
        btns.addWidget(self._back_btn, 1)
        root.addLayout(btns)

        self._apply_theme()

    def _apply_theme(self):
        c = self._main._c
        self.setStyleSheet(f"""
            QWidget {{
                background: {c('card')};
                border-radius: {CORNER}px;
            }}
            QLabel {{ background: transparent; }}
            QPushButton {{
                background: {c('hover_bg')};
                border: 1px solid {c('border')};
                border-radius: 8px;
                font-size: 11px;
                color: {c('mid')};
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                background: {c('press_bg')};
                border-color: {c('accent')};
            }}
        """)
        self._title_label.setStyleSheet(
            f"color: {c('text2')}; font-size: 11px; background: transparent;")
        self._state_label.setStyleSheet(
            f"color: {c('text')}; font-size: 12px; font-weight: bold;"
            " background: transparent;")
        self._detail_label.setStyleSheet(
            f"color: {c('text2')}; font-size: 10px; background: transparent;")

    def paintEvent(self, event):
        """自己画圆角背景 + 细边框，保证是圆角矩形而不是方块。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._main._c
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setBrush(QColor(c('card')))
        p.setPen(QPen(QColor(c('border')), 1))
        p.drawRoundedRect(rect, CORNER, CORNER)

    # ── 配置 ────────────────────────────────────────────────
    def configure(self, title, mode, pause=None, resume=None, stop=None):
        self._title = title
        self._mode = mode
        self._pause_cb = pause
        self._resume_cb = resume
        self._stop_cb = stop
        self._title_label.setText(title)
        self._apply_theme()
        self._tick()          # 立刻按真实状态同步按钮文案，不用等下一秒

    # ── 位置 ────────────────────────────────────────────────
    def _restore_position(self):
        pos = getattr(self.settings, "mini_timer_pos", None)
        if pos:
            self.move(pos[0], pos[1])
            self._clamp_into_screen()
            return
        screen = self._main.screen() or None
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 24, geo.top() + 24)
            self._clamp_into_screen()

    @property
    def settings(self):
        return self._main.settings

    def _clamp_into_screen(self):
        screen = self._main.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = min(max(self.x(), geo.left()), geo.right() - self.width())
        y = min(max(self.y(), geo.top()), geo.bottom() - self.height())
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    # ── 每秒刷新 ────────────────────────────────────────────
    def _tick(self):
        if self._mode == "countdown":
            self._tick_countdown()
        elif self._mode == "countup":
            self._tick_countup()
        else:
            accent, track, fg = self._ring_colors()
            self._ring.set_state(0.0, "--:--", accent, track, fg, dim=True)
            self._state_label.setText("计时已结束")

    def _ring_colors(self):
        c = self._main._c
        return c('accent'), c('border'), c('text')

    def _tick_countdown(self):
        timer = getattr(self._main, "_timer_widget", None)
        if timer is None:
            return
        remaining = timer.get_remaining_seconds()
        total = max(1, getattr(timer, "_total_seconds", 0) or 1)
        running = timer.get_is_running()
        # 环形表示"已走完的比例"，从满到空
        ratio = 1.0 - (remaining / total)
        urgent = 0 < remaining <= 10
        accent, track, fg = self._ring_colors()
        self._ring.set_state(ratio, _compact(remaining), accent, track, fg,
                             full_color="#E05A4F" if urgent else None)

        if remaining <= 0 and not running:
            self._state_label.setText("专注完成")
            self._detail_label.setText("休息一下吧")
            self._pause_btn.setText("⏸ 暂停")
            self._mode = "idle"
        elif running:
            self._state_label.setText("专注中")
            self._detail_label.setText("剩余 %s / 共 %d 分钟"
                                       % (_compact(remaining), total // 60))
            self._pause_btn.setText("⏸ 暂停")
            self._paused = False
        else:
            self._state_label.setText("已暂停")
            self._detail_label.setText("剩余 %s" % _compact(remaining))
            self._pause_btn.setText("▶ 继续")
            self._paused = True

    def _tick_countup(self):
        flow = getattr(self._main, "_flow_window", None)
        if flow is None:
            return
        active = flow._active_task
        if active:
            secs = flow._task_secs(active)
            self._state_label.setText("计时中")
            self._detail_label.setText("这一项累计 %s" % _clock(secs))
            self._pause_btn.setText("⏸ 暂停")
            self._paused = False
            acc = self._main._c('accent')
            self._ring.set_state(1.0, _compact(secs), acc, acc,
                                 self._main._c('text'), full_color=acc)
        else:
            last = getattr(flow, "_last_task", None)
            secs = flow._task_secs(last) if last else 0
            self._state_label.setText("已暂停")
            self._detail_label.setText(("「%s」累计 %s" % (last[:12], _clock(secs)))
                                       if last else "未在计时")
            self._pause_btn.setText("▶ 继续")
            self._paused = True

    # ── 按钮 ────────────────────────────────────────────────
    def _on_pause_toggle(self):
        if self._paused:
            if self._resume_cb is not None:
                self._resume_cb()
            self._paused = False
        else:
            if self._pause_cb is not None:
                self._pause_cb()
            self._paused = True
        self._tick()

    def _on_back(self):
        if self._restore_cb is not None:
            self._restore_cb()
        else:
            self.hide()

    def _on_close(self):
        """结束计时并关掉小窗（计时源同时停止，避免后台继续跑）。"""
        if self._stop_cb is not None:
            try:
                self._stop_cb()
            except Exception:
                pass
        self._mode = "idle"
        self.hide()

    # ── 拖动 ────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_from is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_from)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_from is not None:
            self._drag_from = None
            self.settings.mini_timer_pos = (self.x(), self.y())

    def mouseDoubleClickEvent(self, event):
        self._on_back()

    def hideEvent(self, event):
        # 位置变化后隐藏也要记住
        if self.isVisible() is False:
            try:
                self.settings.mini_timer_pos = (self.x(), self.y())
            except Exception:
                pass
        super().hideEvent(event)
