"""Timer widget for ToYu Desktop Pet."""

import os
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QFrame, QGridLayout, QSizePolicy, QMessageBox
)

from ui.presets import FOCUS_PRESETS
from ui.theme import ask, is_dark


def _is_dark_now(widget):
    """判断当前是不是深色模式。

    本控件没有主题状态：它跟着主窗口的样式表走。
    优先问主窗口要，拿不到再读设置。
    """
    win = widget.window()
    flag = getattr(win, "_is_dark_mode", None)
    if isinstance(flag, bool):
        return flag
    return is_dark()

ACCENT = "#C49A3C"
ACCENT_HOVER = "#D4AE50"
DARK = "#3E2723"
MID = "#5C3D1E"
LIGHT_BG = "#FFF8F0"
CARD_BG = "#FFFFFF"
TEXT = "#2C1810"
TEXT_SEC = "#8B7355"
BORDER = "#E8D5C0"
SUCCESS = "#6B9B37"
DANGER = "#C0392B"
# 紧凑模式（心流窗口）下的最大高度：大字显示框 + 状态 + 操作按钮 + 进度条
COMPACT_MAX_HEIGHT = 340

class TimerWidget(QWidget):
    """Countdown timer widget with pet notifications."""
    
    timer_complete = pyqtSignal()
    started = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._paused = False          # 区分"暂停"与"结束"：继续时不重算时长
        self._remaining_seconds = 0
        self._total_seconds = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        display_frame = QFrame()
        display_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {DARK}, stop:1 #4E342E);
                border-radius: 16px;
                padding: 20px;
            }}
        """)
        display_layout = QVBoxLayout(display_frame)
        display_layout.setSpacing(8)
        
        self._time_display = QLabel("00:00:00")
        self._time_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 字号 48px，必须给足高度：否则外层竖直空间紧张时标签会被压到 18px 高、
        # 时间文字被整条裁掉（在心流模式这类布局里实测出现，表现为"看不见时间"）
        self._time_display.setMinimumHeight(64)
        self._time_display.setStyleSheet("""
            QLabel {
                color: #C49A3C;
                font-size: 48px;
                font-weight: bold;
                font-family: "Consolas", "Courier New", monospace;
                background: transparent;
            }
        """)
        display_layout.addWidget(self._time_display)
        
        self._status_label = QLabel("准备开始")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setMinimumHeight(18)
        self._status_label.setStyleSheet("""
            QLabel {
                color: #A0A0A0;
                font-size: 12px;
                background: transparent;
            }
        """)
        display_layout.addWidget(self._status_label)
        
        layout.addWidget(display_frame)
        
        preset_label = QLabel("快捷设置")
        preset_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        layout.addWidget(preset_label)
        # 记下引用：心流模式会隐藏这一整块（那边有自己的快捷按钮，
        # 两套预设同时出现会重复占掉一半竖直空间）
        self._preset_label = preset_label
        
        preset_grid = QGridLayout()
        preset_grid.setSpacing(8)
        
        # 预设从 ui/presets.py 取 —— 原来这里和心流模式各写一套，
        # 上限还不同（这里 60 分钟、心流 90 分钟），用户看到的就是
        # "最多只能到 1 小时"以及"两边对不上"。
        presets = [(f"{m}分钟", m) for m in FOCUS_PRESETS]
        
        self._preset_buttons = []
        for i, (text, mins) in enumerate(presets):
            btn = QPushButton(text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: white;
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                    padding: 8px;
                    font-size: 11px;
                    color: {TEXT};
                }}
                QPushButton:hover {{
                    border-color: {ACCENT};
                    background: #FFF3E0;
                }}
                QPushButton:pressed {{
                    background: #FFE0B2;
                }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, m=mins: self._set_preset(m))
            preset_grid.addWidget(btn, i // 3, i % 3)
            self._preset_buttons.append(btn)
        
        layout.addLayout(preset_grid)
        self._preset_grid = preset_grid
        
        custom_label = QLabel("自定义时间")
        custom_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        layout.addWidget(custom_label)
        # 紧凑模式下与预设区一起隐藏（心流模式不需要两套输入）
        self._custom_label = custom_label

        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        
        self._hour_spin = QSpinBox()
        self._hour_spin.setRange(0, 23)
        self._hour_spin.setSuffix(" 时")
        self._hour_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: {TEXT};
                background: white;
            }}
        """)
        custom_row.addWidget(self._hour_spin)
        
        self._min_spin = QSpinBox()
        self._min_spin.setRange(0, 59)
        self._min_spin.setSuffix(" 分")
        self._min_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: {TEXT};
                background: white;
            }}
        """)
        custom_row.addWidget(self._min_spin)
        
        self._sec_spin = QSpinBox()
        self._sec_spin.setRange(0, 59)
        self._sec_spin.setSuffix(" 秒")
        self._sec_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: {TEXT};
                background: white;
            }}
        """)
        custom_row.addWidget(self._sec_spin)

        # 用容器包住自定义时间这一行，紧凑模式下可以整块隐藏
        self._custom_row_widget = QWidget()
        self._custom_row_widget.setStyleSheet("background: transparent;")
        _crl = QHBoxLayout(self._custom_row_widget)
        _crl.setContentsMargins(0, 0, 0, 0)
        _crl.setSpacing(8)
        _crl.addWidget(self._hour_spin)
        _crl.addWidget(self._min_spin)
        _crl.addWidget(self._sec_spin)
        layout.addWidget(self._custom_row_widget)
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        self._start_btn = QPushButton("▶ 开始")
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SUCCESS};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #5A8A2A;
            }}
            QPushButton:disabled {{
                background: #ccc;
            }}
        """)
        self._start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)
        
        self._pause_btn = QPushButton("⏸ 暂停")
        self._pause_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background: #ccc;
            }}
        """)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self._on_pause)
        self._pause_btn.setEnabled(False)
        btn_row.addWidget(self._pause_btn)
        
        self._reset_btn = QPushButton("↺ 重置")
        self._reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: white;
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {DANGER};
                color: {DANGER};
            }}
        """)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(self._reset_btn)
        
        layout.addLayout(btn_row)
        
        self._progress_bar = QFrame()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setStyleSheet(f"""
            QFrame {{
                background: {BORDER};
                border-radius: 3px;
            }}
        """)
        
        self._progress_fill = QFrame(self._progress_bar)
        self._progress_fill.setGeometry(0, 0, 0, 6)
        self._progress_fill.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACCENT}, stop:1 {ACCENT_HOVER});
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self._progress_bar)
        
        layout.addStretch()
    
    def _set_preset(self, minutes):
        """设置倒计时时长（**真正重设**，不只是改输入框）。

        必须**同时**处理小时框：分钟框上限是 59，只设分钟框的话
        60 分钟会被截成 59 分钟、90 分钟也被截成 59 分钟
        （用户选了 90 分钟却只跑 59 分钟，且看不出哪里不对）。

        还要清掉上一段的残留状态 —— 原来只改 spinbox 与显示，不动
        _total_seconds / _remaining_seconds / _paused，于是：

            跑过 25 分钟 -> 暂停 -> 要求 45 分钟

        会走 _on_start 的「暂停继续」分支、沿用旧的 1500 秒：
        输入框写着 45，实际只跑 25 分钟（已实测复现）。
        AI 通过 start_focus(45) 进来时中同样的招 —— 这就是
        「指定时长与计时对不上」的根源。
        """
        minutes = int(minutes)

        # 1) 停掉正在跑的计时，清掉上一段的状态
        try:
            self._timer.stop()
        except (AttributeError, RuntimeError):
            pass
        self._is_running = False
        self._paused = False
        self._remaining_seconds = 0
        self._total_seconds = 0

        # 2) 写入新的时长
        self._hour_spin.setValue(minutes // 60)
        self._min_spin.setValue(minutes % 60)
        self._sec_spin.setValue(0)
        self._update_display(minutes * 60)

        # 3) 按钮与进度条回到「准备开始」的样子
        for attr, enabled in (("_start_btn", True), ("_pause_btn", False)):
            btn = getattr(self, attr, None)
            if btn is not None:
                try:
                    btn.setEnabled(enabled)
                except RuntimeError:
                    pass
        label = getattr(self, "_status_label", None)
        if label is not None:
            try:
                label.setText("准备开始")
            except RuntimeError:
                pass
        fill = getattr(self, "_progress_fill", None)
        if fill is not None:
            try:
                fill.setFixedWidth(0)
            except RuntimeError:
                pass
    
    def _on_start(self):
        """开始计时，或从暂停处继续。

        这两种语义必须区分开：`_on_start` 同时也被"继续"按钮调用。
        原先它无条件用输入框重算 total，于是**暂停后继续 = 从整段时长重跑**
        （跑了 10 分钟、暂停、继续 → 显示跳回 25:00），
        `get_elapsed_seconds()` 也随之归零，专注时长少记。
        """
        if self._is_running:
            return

        # 暂停状态下继续：沿用已算好的总时长与剩余秒数，不重算
        resuming = self._paused and self._remaining_seconds > 0
        if resuming:
            total = self._total_seconds
        else:
            hours = self._hour_spin.value()
            minutes = self._min_spin.value()
            seconds = self._sec_spin.value()
            total = hours * 3600 + minutes * 60 + seconds

            if total <= 0:
                ask(self, "提示", "请设置时间", dark=_is_dark_now(self))
                return

            self._total_seconds = total
            self._remaining_seconds = total
            # 新开一段才复位进度条（否则接着上次的满格跑，像"一开始就完成"）
            if hasattr(self, "_progress_fill") and hasattr(self, "_progress_bar"):
                self._progress_fill.setFixedWidth(0)

        self._paused = False
        self._is_running = True

        self._start_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._status_label.setText("倒计时中...")

        self._update_display(self._remaining_seconds)
        self._timer.start(1000)  # Update every second
        # 通知外部（主窗口据此弹出悬浮计时小窗）
        self.started.emit()

    def _on_pause(self):
        """Pause the timer."""
        if not self._is_running:
            return

        self._timer.stop()
        self._is_running = False
        # 记下"是暂停"而不是"结束"，_on_start 据此走继续分支
        self._paused = self._remaining_seconds > 0

        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._status_label.setText("已暂停")
    
    def _on_reset(self):
        """Reset the timer."""
        self._timer.stop()
        self._is_running = False
        self._paused = False
        self._remaining_seconds = 0
        self._total_seconds = 0
        
        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._status_label.setText("准备开始")
        
        self._update_display(0)
        self._progress_fill.setFixedWidth(0)
    
    def _on_tick(self):
        """Called every second when timer is running."""
        self._remaining_seconds -= 1
        
        if self._remaining_seconds <= 0:
            self._timer.stop()
            self._is_running = False
            self._remaining_seconds = 0
            
            self._start_btn.setEnabled(True)
            self._pause_btn.setEnabled(False)
            self._status_label.setText("⏰ 时间到！")
            
            self._update_display(0)
            self._progress_fill.setFixedWidth(self._progress_bar.width())
            
            self.timer_complete.emit()
        else:
            self._update_display(self._remaining_seconds)
            
            if self._total_seconds > 0:
                progress = 1 - (self._remaining_seconds / self._total_seconds)
                bar_width = int(progress * self._progress_bar.width())
                self._progress_fill.setFixedWidth(bar_width)
    
    def _update_display(self, seconds):
        """Update the time display."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        self._time_display.setText(time_str)
        
        if seconds <= 10 and seconds > 0:
            self._time_display.setStyleSheet("""
                QLabel {
                    color: #FF5252;
                    font-size: 48px;
                    font-weight: bold;
                    font-family: "Consolas", "Courier New", monospace;
                    background: transparent;
                }
            """)
        else:
            self._time_display.setStyleSheet("""
                QLabel {
                    color: #C49A3C;
                    font-size: 48px;
                    font-weight: bold;
                    font-family: "Consolas", "Courier New", monospace;
                    background: transparent;
                }
            """)
    
    def get_is_running(self):
        """Check if timer is running."""
        return self._is_running
    
    def get_remaining_seconds(self):
        """Get remaining seconds."""
        return self._remaining_seconds

    def get_elapsed_seconds(self):
        """已经过的时间（用于记录任务实际用时）。"""
        if self._total_seconds <= 0:
            return 0
        return max(0, int(self._total_seconds - self._remaining_seconds))

    def set_compact_mode(self, compact=True):
        """紧凑模式：隐藏「快捷设置」预设区与「自定义时间」。

        心流模式自带快捷按钮，两套预设同时出现会重复占掉近一半竖直空间，
        所以那边进入时切到紧凑模式。

        注意：布局项被 setVisible(False) 后仍占着原本的 stretch 空间，
        会留下一大片空白。所以这里同时限制自身最大高度，
        让计时器收紧成「大字时间 + 状态 + 操作按钮」这一块。
        """
        for w in getattr(self, "_preset_buttons", []):
            w.setVisible(not compact)
        for name in ("_preset_label", "_custom_label", "_custom_row_widget"):
            w = getattr(self, name, None)
            if w is not None:
                w.setVisible(not compact)

        if compact:
            self.setMaximumHeight(COMPACT_MAX_HEIGHT)
        else:
            self.setMaximumHeight(16777215)      # Qt 默认上限，恢复可伸展
