"""Particle effects system for the desktop pet — hearts, stars, Zzz, etc."""

import random
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

class Particle:
    """A single floating particle with smooth fade-out."""
    def __init__(self, x, y, char, color, vx=0, vy=-1.5, life=60, size=14):
        self.x = float(x)
        self.y = float(y)
        self.char = char
        self.color = QColor(color)
        self.vx = vx + random.uniform(-1.2, 1.2)
        self.vy = vy + random.uniform(-0.5, 0.1)
        self.life = float(life)
        self.max_life = float(life)
        self.size = max(10, size + random.randint(-2, 2))

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.99
        self.vy *= 0.99
        self.life -= 1
        return self.life > 0

    def paint(self, painter: QPainter):
        t = self.life / self.max_life
        alpha = max(0, min(255, int(255 * t * (2 - t))))  # ease-out curve
        if alpha < 3:
            return
        color = QColor(self.color)
        color.setAlpha(alpha)
        painter.save()
        font = QFont("Segoe UI Emoji", self.size)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QRectF(self.x - 20, self.y - 20, 40, 40),
                        Qt.AlignmentFlag.AlignCenter, self.char)
        painter.restore()

OVERLAY_W = 400
OVERLAY_H = 500

class ParticleSystem(QWidget):
    """Standalone floating overlay that renders particles near the pet."""

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
        self.particles = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(33)
        self.hide()

    def emit_at(self, pet_global_x, pet_global_y, chars, colors, count=5, **kwargs):
        """Position overlay centered on pet, spawn particles at center."""
        ox = pet_global_x - OVERLAY_W // 2
        oy = pet_global_y - int(OVERLAY_H * 0.7)
        self.setGeometry(ox, oy, OVERLAY_W, OVERLAY_H)
        sx = OVERLAY_W // 2
        sy = int(OVERLAY_H * 0.7)
        for _ in range(count):
            char = random.choice(chars) if isinstance(chars, list) else chars
            color = random.choice(colors) if isinstance(colors, list) else colors
            self.particles.append(Particle(sx, sy, char, color, **kwargs))
        if not self._timer.isActive():
            self._timer.start()
        self.show()
        self.update()

    def add_hearts(self, gx, gy, count=6):
        """Floating hearts — feed complete."""
        self.emit_at(gx, gy,
                     ["\u2764\uFE0F", "\U0001F495", "\U0001F496"],
                     ["#FF6B9D", "#FF4081", "#E91E63"], count,
                     vy=-0.6, life=120, size=16)

    def add_stars(self, gx, gy, count=8):
        """Floating stars — task complete."""
        self.emit_at(gx, gy,
                     ["\u2B50", "\u2728", "\U0001F31F"],
                     ["#FFD700", "#FFA000", "#FFEB3B"], count,
                     vy=-0.6, life=130, size=15)

    def add_zzz(self, gx, gy, count=3):
        """Floating Zzz — sleepy."""
        self.emit_at(gx, gy,
                     ["\U0001F4A4", "Z", "z"],
                     ["#9C27B0", "#7B1FA2", "#CE93D8"], count,
                     vy=-0.4, vx=0.2, life=160, size=18)

    def add_fire(self, gx, gy, count=10):
        """Fire burst — combo complete."""
        self.emit_at(gx, gy,
                     ["\U0001F525", "\U0001F4A5", "\u26A1"],
                     ["#FF5722", "#FF9800", "#FFEB3B"], count,
                     vy=-1.5, life=70, size=18)

    def add_sweat(self, gx, gy, count=3):
        """Sweat drops — long work."""
        self.emit_at(gx, gy,
                     ["\U0001F4A7", "\U0001F4A6"],
                     ["#2196F3", "#03A9F4"], count,
                     vy=-1.0, life=60, size=12)

    def add_music_notes(self, gx, gy, count=4):
        """Music notes — listening to music."""
        self.emit_at(gx, gy,
                     ["\u266A", "\u266B", "\U0001F3B5", "\U0001F3B6"],
                     ["#E040FB", "#7C4DFF", "#448AFF", "#18FFFF"], count,
                     vy=-0.8, life=100, size=15)

    def add_sparkles(self, gx, gy, count=8):
        """Sparkles — happiness / excitement."""
        self.emit_at(gx, gy,
                     ["\u2728", "\u2B50", "\U0001F31F", "\u2734\uFE0F"],
                     ["#FFD700", "#FFAB40", "#FF6E40", "#FFFF00"], count,
                     vy=-0.7, life=90, size=14)

    def add_rain(self, gx, gy, count=6):
        """Rain drops — sad / gloomy."""
        self.emit_at(gx, gy,
                     ["\U0001F4A7", "\u2602\uFE0F", "\U0001F327\uFE0F"],
                     ["#607D8B", "#78909C", "#90A4AE"], count,
                     vy=-1.2, life=80, size=13)

    def add_snow(self, gx, gy, count=10):
        """Snowflakes — winter / cold."""
        self.emit_at(gx, gy,
                     ["\u2744\uFE0F", "\u2746\uFE0F", "\u2747\uFE0F"],
                     ["#E3F2FD", "#BBDEFB", "#90CAF9"], count,
                     vy=-0.3, life=150, size=12)

    def _tick(self):
        self.particles = [p for p in self.particles if p.update()]
        if not self.particles:
            self._timer.stop()
            self.hide()
            return
        self.update()

    def paintEvent(self, event):
        if not self.particles:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for p in self.particles:
            p.paint(painter)
        painter.end()
