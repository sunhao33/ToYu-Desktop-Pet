"""Pixel-art house window — pet can enter and exit via door interaction."""

import sys
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QTimer, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import QPixmap, QPainter, QMouseEvent, QTransform, QCursor, QColor
from PyQt6.QtWidgets import QMainWindow, QApplication

from image_processor.processor import get_house_path, get_knock_path
from .pet_bubble import PetFunctionBubble


class HouseWindow(QMainWindow):
    """A draggable pixel-art house that the pet can enter and exit."""

    def __init__(self, settings, pet_window=None):
        super().__init__()
        self.settings = settings
        self._pet_window = pet_window
        self._pet_inside = False
        self._dragging = False
        self._drag_offset = QPoint()
        self._knock_scale_x = 1.0
        self._knock_scale_y = 1.0
        self._knock_phase = -1
        self._night_glow = False
        self._bubble = None
        self._bubble_callbacks = {
            "show_hide": None, "change": None, "exit": None, "show_main_window": None,
        }

        self._house_pixmap = QPixmap(get_house_path())
        self._knock_path = get_knock_path()

        self._init_ui()
        self._restore_position()

    def _init_ui(self):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAutoFillBackground(False)
        self.setFixedSize(160, 160)

    def _restore_position(self):
        saved = self.settings.house_position
        if saved is not None:
            self.move(saved)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            x = screen.x() + screen.width() - 200
            y = screen.y() + screen.height() - 200
            self.move(QPoint(x, y))

    def set_pet_window(self, pet_window):
        self._pet_window = pet_window

    def set_bubble_callbacks(self, show_hide_cb=None, change_cb=None, exit_cb=None, show_main_window_cb=None):
        self._bubble_callbacks = {
            "show_hide": show_hide_cb,
            "change": change_cb,
            "exit": exit_cb,
            "show_main_window": show_main_window_cb,
        }

    def set_pet_inside(self, inside):
        self._pet_inside = inside

    @property
    def pet_inside(self):
        return self._pet_inside

    def set_night_glow(self, enabled):
        self._night_glow = enabled
        self.update()

    # ── Door region detection ──

    def _door_rect(self):
        """Door area in local coordinates (cols 13-18, rows 22-26 at 5x scale)."""
        return QRect(65, 110, 30, 25)

    def _is_door_click(self, local_pos):
        return self._door_rect().contains(local_pos)

    def is_door_overlap(self, sprite_bottom_center):
        """Check if the pet sprite's bottom-center overlaps the house door (screen coords)."""
        door_local = self._door_rect()
        door_screen = QRect(
            self.x() + door_local.x(),
            self.y() + door_local.y(),
            door_local.width(),
            door_local.height(),
        )
        expanded = door_screen.adjusted(-20, -15, 20, 25)
        return expanded.contains(sprite_bottom_center)

    # ── Mouse events ──

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            self._show_function_bubble(event.globalPosition().toPoint())
        elif event.button() == Qt.MouseButton.LeftButton:
            if self._is_door_click(event.pos()) and self._pet_inside:
                self._on_door_knock()
            else:
                self._dragging = True
                self._drag_offset = event.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            global_pos = event.globalPosition().toPoint()
            new_pos = global_pos - self._drag_offset
            self.move(new_pos)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.settings.house_position = QPoint(self.x(), self.y())

    # ── Door knock ──

    def _on_door_knock(self):
        # Play knock sound
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(self._knock_path, winsound.SND_ASYNC)

        # Shake animation
        self._knock_phase = 0
        if not hasattr(self, '_shake_timer') or self._shake_timer is None:
            self._shake_timer = QTimer(self)
            self._shake_timer.timeout.connect(self._shake_tick)
        self._shake_timer.start(16)

        # Release pet
        self._pet_inside = False
        if self._pet_window:
            new_x = self.x() + self.width() + 12
            new_y = self.y() + self.height() - 40
            self._pet_window.move_to(new_x, new_y)
            self._pet_window.show()
            # Show come-out popup
            self._pet_window._show_come_out_popup()

    def _shake_tick(self):
        self._knock_phase += 1
        if self._knock_phase <= 4:
            self._knock_scale_x = 0.92
            self._knock_scale_y = 1.08
        elif self._knock_phase <= 8:
            self._knock_scale_x = 1.08
            self._knock_scale_y = 0.92
        else:
            self._knock_scale_x = 1.0
            self._knock_scale_y = 1.0
            self._shake_timer.stop()
            self._knock_phase = -1
        self.update()

    # ── Rendering ──

    def paintEvent(self, event):
        if not self._house_pixmap:
            return
        painter = QPainter(self)
        cx = self.width() / 2
        cy = self.height() / 2
        transform = QTransform()
        transform.translate(cx, cy)
        transform.scale(self._knock_scale_x, self._knock_scale_y)
        transform.translate(-cx, -cy)
        painter.setTransform(transform)
        painter.drawPixmap(0, 0, self._house_pixmap)

        if self._night_glow:
            painter.resetTransform()
            painter.setOpacity(0.25)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 180, 80))
            door = self._door_rect()
            glow = door.adjusted(-20, -20, 20, 20)
            painter.drawEllipse(glow)
            painter.setOpacity(1.0)

        painter.end()

    # ── Function bubble ──

    def _show_function_bubble(self, global_pos):
        if self._bubble is None:
            self._bubble = PetFunctionBubble(mode="house")
            if self._pet_window:
                self._bubble.zoom_in.connect(lambda: self._pet_window.set_scale(self._pet_window._scale + 0.1))
                self._bubble.zoom_out.connect(lambda: self._pet_window.set_scale(self._pet_window._scale - 0.1))
            cb_change = self._bubble_callbacks.get("change")
            if cb_change:
                self._bubble.change_pet.connect(cb_change)
            cb_show = self._bubble_callbacks.get("show_hide")
            if cb_show:
                self._bubble.toggle_visibility.connect(cb_show)
            cb_exit = self._bubble_callbacks.get("exit")
            if cb_exit:
                self._bubble.exit_app.connect(cb_exit)
            cb_main = self._bubble_callbacks.get("show_main_window")
            if cb_main:
                self._bubble.pomodoro_settings.connect(cb_main)
            if self._pet_window:
                self._bubble.pomodoro_toggle.connect(self._pet_window._toggle_pomodoro)
                self._bubble.feed_pet.connect(self._pet_window._on_feed_pet)

        self._bubble.set_pomodoro_active(self.settings.pomodoro_enabled)
        if self._pet_window:
            self._bubble.set_affection(self._pet_window.affection.level)
            self._bubble.set_visibility_text(self._pet_window.isVisible())
            period = self._pet_window._current_time_period if self._pet_window._time_awareness_enabled else None
            self._bubble.set_mood(period, self._pet_window.affection.level)
            import time
            remaining = max(0, int(self._pet_window._feed_cooldown_end - time.time()))
            self._bubble.set_feed_cooldown(remaining)
            if remaining > 0 and not self._pet_window._feed_cooldown_timer.isActive():
                self._pet_window._feed_cooldown_timer.start(1000)
        self._bubble.show_at(global_pos)

    # ── Window management ──

    def closeEvent(self, event):
        self.settings.house_position = QPoint(self.x(), self.y())
        if hasattr(self, '_shake_timer') and self._shake_timer:
            self._shake_timer.stop()
        super().closeEvent(event)
