"""Food item and floating text animations for the feeding system."""

import random
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve, pyqtSignal

)
from PyQt6.QtGui import QFont, QMouseEvent, QCursor
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QGraphicsOpacityEffect

FOOD_EMOJIS = ["🍙", "🍪", "🍰"]

class FoodItemWindow(QFrame):
    """Small popup showing a random food emoji near the pet. Can be dragged."""

    food_moved = pyqtSignal(QPoint)

    def __init__(self):
        super().__init__()
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(48, 48)

        self._label = QLabel(random.choice(FOOD_EMOJIS))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(24)
        self._label.setFont(font)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)

        self._consume_timer = None
        self._consume_frame = 0
        self._is_dragging = False
        self._drag_offset = QPoint()
        self._is_consumed = False

    def spawn_near(self, pet_window):
        px = pet_window.x() + pet_window.width() // 2
        py = pet_window.y() + pet_window.height() // 2
        offset_x = random.choice([-1, 1]) * random.randint(80, 200)
        offset_y = random.randint(-100, -50)
        self.move(QPoint(px + offset_x, py + offset_y))
        self.show()

        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(300)
        anim.setStartValue(self.pos())
        anim.setEndValue(self.pos() + QPoint(0, -15))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_offset = event.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging:
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            self.move(new_pos)
            self.food_moved.emit(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            event.accept()

    def consume(self):
        self._consume_frame = 0
        self._consume_timer = QTimer(self)
        self._consume_timer.timeout.connect(self._consume_tick)
        self._consume_timer.start(16)

    def _consume_tick(self):
        self._consume_frame += 1
        progress = self._consume_frame / 18  # ~0.3s at 60fps
        if progress >= 1.0:
            self._consume_timer.stop()
            self.close()
            return
        self._opacity.setOpacity(1.0 - progress)
        geo = self.geometry()
        cx = geo.x() + geo.width() // 2
        cy = geo.y() + geo.height() // 2
        target_x = cx - 12
        target_y = cy + 12
        new_x = int(cx + (target_x - cx) * progress) - geo.width() // 2
        new_y = int(cy + (target_y - cy) * progress) - geo.height() // 2
        scale = 1.0 - progress
        new_w = int(48 * scale)
        new_h = int(48 * scale)
        self.setGeometry(new_x + (48 - new_w) // 2, new_y + (48 - new_h) // 2, new_w, new_h)

class FloatingText(QFrame):
    """+15 heart text that drifts up and fades out."""

    def __init__(self):
        super().__init__()
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(100, 36)

        label = QLabel("+15 ♥")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet("color: #C49A3C; background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(label)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity)

        self._frame = 0
        self._timer = None

    def show_near(self, pet_window):
        px = pet_window.x() + pet_window.width() // 2 - 50
        py = pet_window.y()
        self.move(QPoint(px, py))
        self.show()

        self._frame = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fade_tick)
        self._timer.start(33)  # ~30fps

    def _fade_tick(self):
        self._frame += 1
        total_frames = 45  # ~1.5s
        progress = self._frame / total_frames
        if progress >= 1.0:
            self._timer.stop()
            self.close()
            return
        self._opacity.setOpacity(1.0 - progress)
        self.move(self.x(), self.y() - 1)
