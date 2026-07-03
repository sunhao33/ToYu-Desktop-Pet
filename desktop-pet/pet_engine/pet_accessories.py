"""Accessory overlay system — independent sprites attached to pet visible bounds."""

import os
import math
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QWidget


# ── Anchor Points ────────────────────────────────────────────

class Anchor:
    """Attachment point relative to pet visible content area."""
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    CENTER = "center"
    HAND_RIGHT = "hand_right"


# Offsets relative to visible content (ratios from content edges)
# These are fine-tuned to stay within the sprite's actual pixels
CONTENT_ANCHORS = {
    # (content_x_ratio, content_y_ratio) — 0.0 = content start, 1.0 = content end
    Anchor.TOP:         (0.5, -0.08),   # just above content top center
    Anchor.BOTTOM:      (0.5, 1.05),    # just below content bottom
    Anchor.LEFT:        (-0.15, 0.4),   # left of content, mid height
    Anchor.RIGHT:       (1.1, 0.4),     # right of content, mid height
    Anchor.TOP_LEFT:    (0.2, -0.05),
    Anchor.TOP_RIGHT:   (0.8, -0.05),
    Anchor.CENTER:      (0.5, 0.45),
    Anchor.HAND_RIGHT:  (0.95, 0.6),
}


# ── Accessory ────────────────────────────────────────────────

class Accessory:
    """A single accessory sprite with position, animation, and lifecycle."""

    def __init__(self, pixmap: QPixmap, anchor: str, scale=1.0,
                 offset_x=0, offset_y=0, bobbing=False, duration=0):
        self.pixmap = pixmap
        self.anchor = anchor
        self.scale = scale
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.bobbing = bobbing
        self.duration = duration
        self.opacity = 1.0
        self._age = 0.0
        self._alive = True

    def tick(self, dt: float):
        self._age += dt
        if self.duration > 0 and self._age >= self.duration:
            remaining = self.duration - self._age + 0.5
            if remaining <= 0:
                self._alive = False
                return
            self.opacity = max(0, remaining / 0.5)

    @property
    def alive(self):
        return self._alive

    def get_draw_rect(self, content_x, content_y, content_w, content_h):
        """Calculate draw rect based on content-relative anchor."""
        ax_ratio, ay_ratio = CONTENT_ANCHORS.get(self.anchor, (0.5, 0.5))

        # Anchor point in content-local coordinates
        ax = content_x + content_w * ax_ratio
        ay = content_y + content_h * ay_ratio

        # Bobbing animation
        bob = 0
        if self.bobbing:
            bob = math.sin(self._age * 2.5) * 3

        # Final position (centered on anchor)
        w = self.pixmap.width() * self.scale
        h = self.pixmap.height() * self.scale
        x = ax - w / 2 + self.offset_x
        y = ay - h / 2 + self.offset_y + bob

        return QRectF(x, y, w, h)


# ── Accessory Layer ──────────────────────────────────────────

class AccessoryLayer(QWidget):
    """Transparent overlay that renders accessories on top of the pet."""

    def __init__(self):
        super().__init__(None)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.accessories = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(33)
        self._resource_dir = ""
        self._content_ratio = {'top': 0.15, 'bottom': 0.05, 'left': 0.1, 'right': 0.1}
        self.hide()

    def set_resource_dir(self, path: str):
        self._resource_dir = path

    def set_content_ratio(self, ratio: dict):
        """Update the content ratio from sprite bounds detection."""
        self._content_ratio = ratio

    def add_accessory(self, name_or_pixmap, anchor=Anchor.TOP, scale=1.0,
                      offset_x=0, offset_y=0, bobbing=False, duration=0):
        if isinstance(name_or_pixmap, str):
            path = name_or_pixmap
            if self._resource_dir and not os.path.isabs(path):
                path = os.path.join(self._resource_dir, path)
            pix = QPixmap(path)
            if pix.isNull():
                print(f"[AccessoryLayer] Failed to load: {path}")
                return None
        else:
            pix = name_or_pixmap

        acc = Accessory(pix, anchor, scale, offset_x, offset_y, bobbing, duration)
        self.accessories.append(acc)

        if not self._timer.isActive():
            self._timer.start()
        self.show()
        self.update()
        return acc

    def remove_accessory(self, acc: Accessory):
        if acc in self.accessories:
            acc._alive = False

    def clear_all(self):
        self.accessories.clear()
        self._timer.stop()
        self.hide()

    def clear_by_anchor(self, anchor: str):
        for acc in self.accessories:
            if acc.anchor == anchor:
                acc._alive = False

    def update_geometry(self, pet_global_x, pet_global_y, pet_w, pet_h):
        """Update overlay position to match pet window."""
        margin = 100
        ox = pet_global_x - margin
        oy = pet_global_y - margin
        ow = pet_w + margin * 2
        oh = pet_h + margin * 2
        self.setGeometry(ox, oy, ow, oh)
        self._pet_local_x = margin
        self._pet_local_y = margin
        self._pet_local_w = pet_w
        self._pet_local_h = pet_h

    def _get_content_rect(self):
        """Get the actual visible content area within the overlay."""
        px = self._pet_local_x
        py = self._pet_local_y
        pw = self._pet_local_w
        ph = self._pet_local_h
        r = self._content_ratio

        # Content area = pet rect inset by content ratios
        cx = px + pw * r['left']
        cy = py + ph * r['top']
        cw = pw * (1.0 - r['left'] - r['right'])
        ch = ph * (1.0 - r['top'] - r['bottom'])

        # Clamp minimum size
        cw = max(cw, 20)
        ch = max(ch, 20)

        return (cx, cy, cw, ch)

    def _tick(self):
        dt = 0.033
        for acc in self.accessories:
            acc.tick(dt)
        self.accessories = [a for a in self.accessories if a.alive]
        if not self.accessories:
            self._timer.stop()
            self.hide()
            return
        self.update()

    def paintEvent(self, event):
        if not self.accessories:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        cx, cy, cw, ch = self._get_content_rect()

        for acc in self.accessories:
            painter.setOpacity(acc.opacity)
            rect = acc.get_draw_rect(cx, cy, cw, ch)
            painter.drawPixmap(rect.toRect(), acc.pixmap)

        painter.setOpacity(1.0)
        painter.end()
