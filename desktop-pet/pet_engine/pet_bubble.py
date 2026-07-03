"""Function bubble and pomodoro notification popups for the desktop pet."""

from PyQt6.QtCore import (
    Qt, QPoint, QTimer, pyqtSignal, QSize,
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QPointF, QRectF, QEvent
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush, QLinearGradient
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsOpacityEffect, QApplication,
    QWidget, QLineEdit, QSizePolicy
)

BG_CREAM = "#FFFDF7"
BORDER_SOFT = "#E8DDD2"
ACCENT = "#C49A3C"
ACCENT_HOVER = "#D4AE50"
TEXT_DARK = "#2C1810"
TEXT_SEC = "#8B7355"
DANGER = "#C0392B"

BUBBLE_BG = "#FFF8F0"
BUBBLE_BG_TOP = "#FFF5EE"
BUBBLE_BG_BOTTOM = "#FFEEE0"
BUBBLE_BORDER = "#F5D5C8"
BUBBLE_TAIL_SIZE = 12

_BUBBLE_FLAGS = (
    Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
)

class PetFunctionBubble(QFrame):
    """Styled floating bubble — 'pet' mode shows status, 'house' mode shows settings."""

    pomodoro_toggle = pyqtSignal()
    pomodoro_settings = pyqtSignal()
    feed_pet = pyqtSignal()
    zoom_in = pyqtSignal()
    zoom_out = pyqtSignal()
    change_pet = pyqtSignal()
    toggle_visibility = pyqtSignal()
    exit_app = pyqtSignal()
    go_home = pyqtSignal()

    def __init__(self, mode="pet", parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setWindowFlags(_BUBBLE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)

        self._pomodoro_active = False
        self._pet_visible = True

        self._init_ui()
        self._apply_style()
        QApplication.instance().installEventFilter(self)

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        """Close this popup when clicking outside."""
        if (event.type() == QEvent.Type.MouseButtonPress
                and self.isVisible()
                and not self.underMouse()):
            self.hide()
        return super().eventFilter(obj, event)

    def _emit_and_hide(self, signal):
        self.hide()
        signal.emit()

    def _sep(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"QFrame {{ color: {BUBBLE_BORDER}; max-height: 1px; margin: 4px 12px; }}")
        return sep

    def _init_ui(self):
        self._outer = QFrame(self)
        self._outer.setObjectName("bubbleCard")
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._outer)

        layout = QVBoxLayout(self._outer)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(2)

        if self._mode == "house":
            self._pomo_btn = self._make_btn("⏱  开启番茄钟")
            self._pomo_btn.clicked.connect(lambda: self._emit_and_hide(self.pomodoro_toggle))
            layout.addWidget(self._pomo_btn)

        self._feed_btn = self._make_btn("🍙  喂食")
        self._feed_btn.clicked.connect(lambda: self._emit_and_hide(self.feed_pet))
        layout.addWidget(self._feed_btn)

        self._affection_lbl = QLabel("😊 0")
        self._affection_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._affection_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 14px; font-weight: bold;"
            "background: transparent; padding: 6px 0;"
        )
        layout.addWidget(self._affection_lbl)

        self._mood_lbl = QLabel("")
        self._mood_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mood_lbl.setStyleSheet(
            f"color: {TEXT_SEC}; font-size: 11px; background: transparent; padding: 2px 0;"
        )
        layout.addWidget(self._mood_lbl)

        if self._mode == "house":
            layout.addWidget(self._sep())
            zoom_row = QHBoxLayout()
            zoom_row.setSpacing(4)
            zoom_row.setContentsMargins(4, 0, 4, 0)
            zoom_out_btn = self._make_small_btn("− 缩小")
            zoom_out_btn.clicked.connect(lambda: self._emit_and_hide(self.zoom_out))
            zoom_row.addWidget(zoom_out_btn)
            zoom_in_btn = self._make_small_btn("+ 放大")
            zoom_in_btn.clicked.connect(lambda: self._emit_and_hide(self.zoom_in))
            zoom_row.addWidget(zoom_in_btn)
            layout.addLayout(zoom_row)
            change_btn = self._make_btn("🖼  更换宠物")
            change_btn.clicked.connect(lambda: self._emit_and_hide(self.change_pet))
            layout.addWidget(change_btn)

        if self._mode == "pet":
            layout.addWidget(self._sep())
            self._visibility_btn = self._make_btn("👁  隐藏宠物")
            self._visibility_btn.clicked.connect(lambda: self._emit_and_hide(self.toggle_visibility))
            layout.addWidget(self._visibility_btn)

        layout.addWidget(self._sep())

        if self._mode == "pet":
            home_btn = self._make_btn("🏠  回家")
            home_btn.clicked.connect(lambda: self._emit_and_hide(self.go_home))
            layout.addWidget(home_btn)
            self._exit_btn = home_btn
        else:
            exit_btn = self._make_btn("✕  退出")
            exit_btn.setStyleSheet(self._btn_style("exit"))
            exit_btn.clicked.connect(lambda: self._emit_and_hide(self.exit_app))
            layout.addWidget(exit_btn)
            self._exit_btn = exit_btn

        self.setFixedWidth(210)

    def _make_btn(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setFixedHeight(36)
        font = btn.font()
        font.setPointSize(10)
        btn.setFont(font)
        btn.setStyleSheet(self._btn_style())
        return btn

    def _make_small_btn(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setFixedHeight(32)
        btn.setStyleSheet(self._btn_style("small"))
        return btn

    def _btn_style(self, variant="normal"):
        if variant == "small":
            return (
                "QPushButton {\n"
                f"  color: {TEXT_DARK}; background: #FFF0E6;\n"
                "  border-radius: 10px; padding: 4px 12px; font-size: 11px;\n"
                "  border: 1px solid #F5D5C8;\n"
                "}\n"
                "QPushButton:hover {\n"
                f"  background: {ACCENT}; color: white; border-color: {ACCENT};\n"
                "}"
            )
        elif variant == "exit":
            return (
                "QPushButton {\n"
                f"  color: {TEXT_SEC}; background: transparent;\n"
                "  border-radius: 10px; padding: 4px 12px;\n"
                "  border: none; font-size: 11px;\n"
                "}\n"
                "QPushButton:hover {\n"
                f"  background: #FDEDED; color: {DANGER};\n"
                "}"
            )
        else:
            return (
                "QPushButton {\n"
                f"  color: {TEXT_DARK}; background: transparent;\n"
                "  border-radius: 10px; padding: 6px 14px;\n"
                "  border: none; text-align: left;\n"
                "}\n"
                "QPushButton:hover {\n"
                "  background: #FFF0E6;\n"
                "}"
            )

    def _apply_style(self):
        self._outer.setStyleSheet(f"""
            QFrame#bubbleCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {BUBBLE_BG_TOP}, stop:1 {BUBBLE_BG_BOTTOM});
                border: 1.5px solid {BUBBLE_BORDER};
                border-radius: 18px;
            }}
        """)

    def _on_pomodoro_toggle(self):
        self._pomodoro_active = not self._pomodoro_active
        self._pomo_btn.setText("⏱  关闭番茄钟" if self._pomodoro_active else "⏱  开启番茄钟")
        self.pomodoro_toggle.emit()

    def _on_visibility_toggle(self):
        self.toggle_visibility.emit()

    def set_pomodoro_active(self, active):
        self._pomodoro_active = active
        if hasattr(self, '_pomo_btn'):
            self._pomo_btn.setText("⏱  关闭番茄钟" if active else "⏱  开启番茄钟")

    def set_feed_cooldown(self, seconds):
        if seconds > 0:
            self._feed_btn.setText(f"🍙  喂食 ({seconds}s)")
            self._feed_btn.setEnabled(False)
        else:
            self._feed_btn.setText("🍙  喂食")
            self._feed_btn.setEnabled(True)

    def set_affection(self, level):
        from .pet_affection import LEVEL_EMOJIS
        emoji = "😊"
        for threshold, e in reversed(LEVEL_EMOJIS):
            if level >= threshold:
                emoji = e
                break
        self._affection_lbl.setText(f"{emoji} {level}")

    def set_mood(self, period=None, affection_level=0):
        parts = []
        if period:
            period_val = period.value if hasattr(period, 'value') else str(period)
            moods = {
                "night": "😴 夜深了，好困…",
                "morning": "⚡ 清晨元气满满！",
                "day": "😊 今天天气真好",
                "evening": "🌅 悠闲的傍晚时光",
            }
            parts.append(moods.get(period_val, ""))
        if affection_level < 20:
            parts.append("🍙 有点饿了…")
        elif affection_level >= 80:
            parts.append("💖 好幸福呀！")
        self._mood_lbl.setText("  ".join(parts) if parts else "")

    def set_visibility_text(self, visible):
        self._pet_visible = visible
        if hasattr(self, '_visibility_btn'):
            self._visibility_btn.setText("👁  隐藏宠物" if visible else "👁  显示宠物")

    def show_at(self, global_point):
        self.adjustSize()
        w = self.width()
        h = self.height()
        screen = QApplication.primaryScreen().availableGeometry()
        x = global_point.x() - w - 16
        y = global_point.y() - h // 2
        x = max(screen.x(), min(x, screen.x() + screen.width() - w))
        y = max(screen.y() + 4, min(y, screen.y() + screen.height() - h - 4))
        self.move(QPoint(x, y))

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)
        self.show()

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(200)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()
        self._fade_anim.finished.connect(self._clear_opacity_effect)

    def _clear_opacity_effect(self):
        self.setGraphicsEffect(None)

class PomodoroNotificationBubble(QWidget):
    """Small notification that appears when the pomodoro timer fires.
    Top-level window positioned above the pet, follows pet movement."""

    def __init__(self, pet_window=None, title="☕  该休息一下啦！", subtitle="看看窗外，活动一下吧"):
        super().__init__(None)  # No parent — top-level window
        self.setWindowFlags(_BUBBLE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._pet_window = pet_window

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        inner = QFrame()
        inner.setObjectName("notifCard")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(22, 16, 22, 16)

        label = QLabel(title)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: {TEXT_DARK}; font-size: 14px; font-weight: bold;"
            "background: transparent;"
        )
        inner_layout.addWidget(label)

        sub = QLabel(subtitle)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color: {TEXT_SEC}; font-size: 11px; background: transparent;"
        )
        inner_layout.addWidget(sub)

        inner.setStyleSheet(f"""
            QFrame#notifCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {BUBBLE_BG_TOP}, stop:1 {BUBBLE_BG_BOTTOM});
                border: 1.5px solid {BUBBLE_BORDER};
                border-radius: 16px;
            }}
        """)

        layout.addWidget(inner)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)

        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_out)
        self._fade_elapsed = 0.0
        self._fade_duration = 3.0

    def show_near(self, pet_window):
        """Show notification above the pet at global position."""
        self._pet_window = pet_window
        self.adjustSize()
        self._position_above_pet()
        self.show()
        self.raise_()
        self._fade_elapsed = 0.0
        self._opacity.setOpacity(1.0)
        self._fade_timer.start(80)

    def _position_above_pet(self):
        """Position this window centered above the pet sprite at global coordinates."""
        if not self._pet_window:
            return
        from pet_engine.sprite_bounds import get_sprite_frame_size
        frame = get_sprite_frame_size(self._pet_window.geometry())
        sprite_top = frame['sprite_top']
        cx = self._pet_window.x() + self._pet_window.width() // 2
        x = cx - self.width() // 2
        y = int(sprite_top) - self.height() - 10
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.x(), min(x, screen.x() + screen.width() - self.width()))
        y = max(screen.y(), min(y, screen.y() + screen.height() - self.height()))
        self.move(QPoint(x, y))

    def _fade_out(self):
        self._fade_elapsed += 0.08
        progress = min(self._fade_elapsed / self._fade_duration, 1.0)
        self._opacity.setOpacity(1.0 - progress)
        if progress >= 1.0:
            self._fade_timer.stop()
            self.close()

class CompanionBubble(QWidget):
    """Cute speech bubble with tail, attached to pet and moves with it.
    Top-level window repositioned each frame to follow the pet."""

    def __init__(self, parent=None, message="..."):
        super().__init__(None)  # No parent — top-level window
        self.setWindowFlags(_BUBBLE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._pet_window = None

        self._message = message
        self._tail_x = 0

        self._label = QLabel(message, self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._label.setMinimumWidth(80)
        self._label.setMaximumWidth(280)
        self._label.setStyleSheet(
            f"color: {TEXT_DARK}; font-size: 12px; font-weight: bold;"
            "background: transparent; padding: 6px 10px;"
        )

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 10, 14, 10 + BUBBLE_TAIL_SIZE)
        self._layout.addWidget(self._label)

        self.setMinimumWidth(100)
        self.setMaximumWidth(320)
        self.setMinimumHeight(32 + BUBBLE_TAIL_SIZE)
        self.setMaximumHeight(250 + BUBBLE_TAIL_SIZE)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self.hide()

        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_out)
        self._fade_elapsed = 0.0
        self._fade_duration = 1.0
        self._is_showing = False
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade)

        self._bounce_anim = None

    def paintEvent(self, event):
        """Draw the cute speech bubble with tail."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        tail_h = BUBBLE_TAIL_SIZE
        bubble_rect = QRectF(4, 0, w - 8, h - tail_h)
        r = 16

        path = QPainterPath()
        path.addRoundedRect(bubble_rect, r, r)

        tail_cx = self._tail_x if self._tail_x > 0 else w / 2
        tail_cx = max(20, min(tail_cx, w - 20))
        tail_path = QPainterPath()
        tail_path.moveTo(tail_cx - 8, bubble_rect.bottom() - 1)
        tail_path.lineTo(tail_cx, bubble_rect.bottom() + tail_h - 1)
        tail_path.lineTo(tail_cx + 8, bubble_rect.bottom() - 1)
        tail_path.closeSubpath()

        full_path = path.united(tail_path)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(BUBBLE_BG_TOP))
        grad.setColorAt(1.0, QColor(BUBBLE_BG_BOTTOM))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPath(full_path)

        pen = QPen(QColor(BUBBLE_BORDER), 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(full_path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BUBBLE_BORDER))
        dot_y = bubble_rect.bottom() + tail_h // 2 + 1
        painter.drawEllipse(QPointF(tail_cx - 4, dot_y), 2, 2)
        painter.drawEllipse(QPointF(tail_cx + 4, dot_y + 1), 1.5, 1.5)

        painter.end()

    def show_message(self, message, pet_window=None):
        """Show a message attached to the pet's head."""
        self._message = message
        self._label.setText(message)
        self._pet_window = pet_window

        fm = self._label.fontMetrics()
        max_text_w = 260
        text_rect = fm.boundingRect(0, 0, max_text_w, 2000,
                                    Qt.TextFlag.TextWordWrap, message)
        w = min(max(text_rect.width() + 28, 100), 320)
        h = min(max(text_rect.height() + 20 + BUBBLE_TAIL_SIZE, 32 + BUBBLE_TAIL_SIZE), 250 + BUBBLE_TAIL_SIZE)
        self.resize(w, h)

        self._position_above_pet()
        self.show()
        self.raise_()
        self._fade_elapsed = 0.0
        self._opacity.setOpacity(1.0)

        self._bounce_in()

        self._hide_timer.start(3000)
        self._is_showing = True

    def _position_above_pet(self):
        """Position bubble centered above the pet sprite at global coordinates."""
        if not self._pet_window:
            return
        from pet_engine.sprite_bounds import get_sprite_frame_size
        frame = get_sprite_frame_size(self._pet_window.geometry())
        sprite_top = frame['sprite_top']
        cx = self._pet_window.x() + self._pet_window.width() // 2
        bw = self.width()
        x = cx - bw // 2
        y = int(sprite_top) - self.height() + 2
        self.move(QPoint(x, y))
        self._tail_x = bw / 2

    def update_position(self):
        """Re-sync position with pet window (call after pet moves)."""
        if self._pet_window and self._is_showing:
            self._position_above_pet()

    def _bounce_in(self):
        if self._bounce_anim:
            self._bounce_anim.stop()

        self._bounce_anim = QPropertyAnimation(self, b"pos", self)
        start_pos = self.pos()
        bounce_pos = QPoint(start_pos.x(), start_pos.y() - 6)

        self._bounce_anim.setDuration(300)
        self._bounce_anim.setStartValue(bounce_pos)
        self._bounce_anim.setEndValue(start_pos)
        self._bounce_anim.setEasingCurve(QEasingCurve.Type.OutBounce)
        self._bounce_anim.start()

    def _start_fade(self):
        self._fade_timer.start(60)
        self._fade_elapsed = 0.0

    def _fade_out(self):
        self._fade_elapsed += 0.06
        progress = min(self._fade_elapsed / self._fade_duration, 1.0)
        self._opacity.setOpacity(1.0 - progress)
        if progress >= 1.0:
            self._fade_timer.stop()
            self.close()
            self._is_showing = False

class ChatBubble(QWidget):
    """Chat input bubble — appears when clicking the pet, for AI conversations."""

    message_sent = pyqtSignal(str)  # Emits user input when sent

    _RADIUS = 16
    _TAIL_H = 14
    _TAIL_W = 20
    _MARGIN = 10  # gap between window edge and painted bubble

    def __init__(self, pet_window=None):
        super().__init__(None)  # Top-level window
        self.setWindowFlags(_BUBBLE_FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self._pet_window = pet_window
        self._is_visible = False
        self._drag_pos = None
        self._user_dragged = False  # True after user drags the bubble
        self._paint_rect = QRectF()  # updated in paintEvent

        self._init_ui()

        QApplication.instance().installEventFilter(self)

    def closeEvent(self, event):
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            self._MARGIN, self._MARGIN,
            self._MARGIN, self._MARGIN + self._TAIL_H
        )

        card = QFrame()
        card.setObjectName("chatCard")
        root.addWidget(card)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(14, 10, 14, 10)
        inner.setSpacing(4)

        self._header = QLabel("💬 和 ToYu 聊天")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header.setStyleSheet(
            f"color: {TEXT_DARK}; font-size: 12px; font-weight: bold;"
            "background: transparent; padding: 2px 0;"
        )
        self._header.setCursor(Qt.CursorShape.OpenHandCursor)
        inner.addWidget(self._header)

        from PyQt6.QtWidgets import QScrollArea, QSizePolicy as SP
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 4px; }"
            "QScrollBar::handle:vertical { background: #E0C0B0; border-radius: 2px; }"
        )
        self._msg_container = QWidget()
        self._msg_container.setStyleSheet("background: transparent;")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 0, 0, 0)
        self._msg_layout.setSpacing(4)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_container)
        self._scroll.setMinimumHeight(120)
        self._scroll.setMaximumHeight(300)
        inner.addWidget(self._scroll)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("说点什么...")
        self._input.setStyleSheet(f"""
            QLineEdit {{
                color: {TEXT_DARK};
                background: white;
                border: 1.5px solid {BUBBLE_BORDER};
                border-radius: 14px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
        """)
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input)

        send_btn = QPushButton("✈")
        send_btn.setFixedSize(32, 32)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
                border-radius: 16px;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background: {ACCENT_HOVER};
            }}
        """)
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)

        inner.addLayout(input_row)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"color: {TEXT_SEC}; font-size: 10px; background: transparent;"
        )
        self._status.hide()
        inner.addWidget(self._status)

        card.setStyleSheet("QFrame#chatCard { background: transparent; border: none; }")

    def paintEvent(self, event):
        """Paint rounded rect + tail as the window background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        m = self._MARGIN
        body = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m - self._TAIL_H)
        self._paint_rect = body
        r = self._RADIUS

        path = QPainterPath()
        path.addRoundedRect(body, r, r)

        tx = body.right() - 20
        ty = body.bottom()
        tail = QPainterPath()
        tail.moveTo(tx, ty + 1)
        tail.cubicTo(
            QPointF(tx + 3, ty + 8),
            QPointF(tx + 8, ty + 13),
            QPointF(tx + 12, ty + 10)
        )
        tail.cubicTo(
            QPointF(tx + 14, ty + 7),
            QPointF(tx + 10, ty + 1),
            QPointF(tx + 7, ty)
        )
        path = path.united(tail)

        grad = QLinearGradient(0, body.top(), 0, body.bottom())
        grad.setColorAt(0, QColor(BUBBLE_BG_TOP))
        grad.setColorAt(1, QColor(BUBBLE_BG_BOTTOM))
        painter.fillPath(path, QBrush(grad))

        painter.setPen(QPen(QColor(BUBBLE_BORDER), 1.5))
        painter.drawPath(path)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only drag from header area (local coords)
            header_h = self._header.height() + 12  # some padding
            if event.pos().y() < header_h:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()
                self._user_dragged = True  # stop auto-repositioning immediately
                self._header.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._drag_pos = None
            self._user_dragged = True  # user moved it, don't snap back
            self._header.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        """Close when clicking outside."""
        if (event.type() == QEvent.Type.MouseButtonPress
                and self._is_visible
                and not self.underMouse()):
            self.hide_chat()
        return super().eventFilter(obj, event)

    def _on_send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._add_message("user", text)
        self.message_sent.emit(text)
        self.show_status("思考中... ⏳")

    def _add_message(self, role: str, text: str):
        """Add a message bubble to the chat history."""
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setMaximumWidth(240)
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        if role == "user":
            bubble.setStyleSheet(
                f"color: {TEXT_DARK}; background: #FFE4D0; border-radius: 12px;"
                "padding: 6px 10px; font-size: 12px;"
            )
            bubble.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            bubble.setStyleSheet(
                f"color: {TEXT_DARK}; background: #E8F4E8; border-radius: 12px;"
                "padding: 6px 10px; font-size: 12px;"
            )
            bubble.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the message list."""
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def show_response(self, text: str):
        """Show AI response in chat history."""
        self._add_message("ai", text)

    def load_history(self, messages):
        """Load chat history from AI companion."""
        while self._msg_layout.count() > 1:  # Keep the stretch
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for msg in messages:
            role = "user" if msg.role == "user" else "ai"
            self._add_message(role, msg.content)

    def show_status(self, text: str):
        """Show status message (thinking, error, etc)."""
        self._status.setText(text)
        self._status.show()

    def clear_status(self):
        self._status.hide()

    def show_chat(self):
        """Show the chat bubble near the pet."""
        if not self._pet_window:
            return
        self._is_visible = True
        self._user_dragged = False  # reset on show
        self.adjustSize()
        self._position_near_pet()
        self.show()
        self.raise_()
        self._input.setFocus()

    def hide_chat(self):
        """Hide the chat bubble."""
        self._is_visible = False
        self.hide()

    def toggle(self):
        """Toggle chat visibility."""
        if self._is_visible:
            self.hide_chat()
        else:
            self.show_chat()

    def _position_near_pet(self):
        """Position chat bubble to the right of the pet, tail pointing at pet."""
        if not self._pet_window:
            return
        pet_geo = self._pet_window.geometry()
        pet_cx = pet_geo.x() + pet_geo.width() // 2
        x = pet_geo.x() + pet_geo.width() + 10
        y = pet_geo.y() + pet_geo.height() // 2 - self.height() // 2
        screen = QApplication.primaryScreen().availableGeometry()
        if x + self.width() > screen.right():
            x = pet_geo.x() - self.width() - 10
        y = max(screen.top(), min(y, screen.bottom() - self.height()))
        self.move(QPoint(x, y))

    def update_position(self):
        """Re-sync position with pet window (only if not user-dragged)."""
        if self._is_visible and self._pet_window and not self._user_dragged:
            self._position_near_pet()
