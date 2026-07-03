"""Timer widget for ToYu Desktop Pet."""

import os
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QFrame, QGridLayout, QSizePolicy, QMessageBox
)

# Theme colors
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


class TimerWidget(QWidget):
    """Countdown timer widget with pet notifications."""
    
    # Signal emitted when timer completes
    timer_complete = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = False
        self._remaining_seconds = 0
        self._total_seconds = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Timer display
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
        
        # Time display
        self._time_display = QLabel("00:00:00")
        self._time_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        
        # Status label
        self._status_label = QLabel("准备开始")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("""
            QLabel {
                color: #A0A0A0;
                font-size: 12px;
                background: transparent;
            }
        """)
        display_layout.addWidget(self._status_label)
        
        layout.addWidget(display_frame)
        
        # Preset buttons
        preset_label = QLabel("快捷设置")
        preset_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        layout.addWidget(preset_label)
        
        preset_grid = QGridLayout()
        preset_grid.setSpacing(8)
        
        presets = [
            ("1分钟", 1), ("3分钟", 3), ("5分钟", 5),
            ("10分钟", 10), ("15分钟", 15), ("25分钟", 25),
            ("30分钟", 30), ("45分钟", 45), ("60分钟", 60)
        ]
        
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
        
        layout.addLayout(preset_grid)
        
        # Custom time input
        custom_label = QLabel("自定义时间")
        custom_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; font-weight: bold;")
        layout.addWidget(custom_label)
        
        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        
        # Hours
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
        
        # Minutes
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
        
        # Seconds
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
        
        layout.addLayout(custom_row)
        
        # Control buttons
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
        
        # Progress bar
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
        """Set timer to preset minutes."""
        self._hour_spin.setValue(0)
        self._min_spin.setValue(minutes)
        self._sec_spin.setValue(0)
        self._update_display(minutes * 60)
    
    def _on_start(self):
        """Start the timer."""
        if self._is_running:
            return
        
        # Calculate total seconds
        hours = self._hour_spin.value()
        minutes = self._min_spin.value()
        seconds = self._sec_spin.value()
        total = hours * 3600 + minutes * 60 + seconds
        
        if total <= 0:
            QMessageBox.information(self, "提示", "请设置时间")
            return
        
        self._total_seconds = total
        self._remaining_seconds = total
        self._is_running = True
        
        self._start_btn.setEnabled(False)
        self._pause_btn.setEnabled(True)
        self._status_label.setText("倒计时中...")
        
        self._timer.start(1000)  # Update every second
    
    def _on_pause(self):
        """Pause the timer."""
        if not self._is_running:
            return
        
        self._timer.stop()
        self._is_running = False
        
        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._status_label.setText("已暂停")
    
    def _on_reset(self):
        """Reset the timer."""
        self._timer.stop()
        self._is_running = False
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
            
            # Update display
            self._update_display(0)
            self._progress_fill.setFixedWidth(self._progress_bar.width())
            
            # Emit signal (no popup, let parent handle notification)
            self.timer_complete.emit()
        else:
            self._update_display(self._remaining_seconds)
            
            # Update progress bar
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
        
        # Change color when low time
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
