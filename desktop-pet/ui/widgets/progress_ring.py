"""进度环 —— QPainter 直绘，供悬浮计时小窗与每日目标共用。

刻意不用 matplotlib：画一个环 import matplotlib 要几百毫秒，
而 QPainter 直绘是微秒级 —— 这个环会随每秒刷新与界面重绘被调用很多次。

环的语义由调用方决定：
  * 计时小窗：表示"已走完的比例"
  * 每日目标：表示"已完成的进度"
所以这里只接收 0~1 的 ratio，不假定方向。
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

DEFAULT_SIZE = 74
DEFAULT_THICKNESS = 5


class ProgressRing(QWidget):
    """圆环进度指示器，中间显示文字。"""

    def __init__(self, parent=None, size: int = DEFAULT_SIZE,
                 thickness: int = DEFAULT_THICKNESS):
        super().__init__(parent)
        self._size = size
        self._thickness = thickness
        self.setFixedSize(size, size)
        self._ratio = 0.0
        self._text = ""
        self._font_size = 13
        self._accent = QColor("#C49A3C")
        self._track = QColor("#E8D5C0")
        self._fg = QColor("#2C1810")
        # 达成/紧张状态用不同颜色（由调用方通过 set_state 传入）
        self._full_color = None
        # 空环时是否把所有颜色调淡（未设目标时用）
        self._dim = False

    # ── 接口 ────────────────────────────────────────────────
    def set_state(self, ratio: float, text: str = "", accent=None, track=None,
                  fg=None, font_size: int | None = None, dim: bool = False,
                  full_color=None):
        """更新显示。

        ratio      0~1
        full_color 当 ratio >= 1 时替换 accent（用于"已达成"变绿/变亮）
        dim        整环调淡（用于"未设目标"这类空状态）
        """
        try:
            self._ratio = max(0.0, min(1.0, float(ratio)))
        except (TypeError, ValueError):
            self._ratio = 0.0
        self._text = text or ""
        if accent is not None:
            self._accent = QColor(accent)
        if track is not None:
            self._track = QColor(track)
        if fg is not None:
            self._fg = QColor(fg)
        if font_size is not None:
            self._font_size = font_size
        self._dim = dim
        self._full_color = QColor(full_color) if full_color else None
        self.update()

    def ratio(self) -> float:
        return self._ratio

    # ── 绘制 ────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pad = self._thickness / 2 + 2
        rect = QRectF(pad, pad, self.width() - 2 * pad, self.height() - 2 * pad)

        track = QColor(self._track)
        accent = QColor(self._accent)
        fg = QColor(self._fg)
        if self._dim:
            track.setAlpha(90)
            accent.setAlpha(90)
            fg.setAlpha(130)

        # 底环
        pen = QPen(track, self._thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        # 进度弧（从 12 点方向顺时针）
        if self._ratio > 0:
            color = accent
            if self._ratio >= 1.0 and self._full_color is not None:
                color = QColor(self._full_color)
            pen = QPen(color, self._thickness)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._ratio))

        # 中间文字
        if self._text:
            painter.setPen(fg)
            font = QFont()
            font.setBold(True)
            font.setFamily("Consolas")
            font.setPointSize(self._font_size if len(self._text) <= 6
                              else max(8, self._font_size - 2))
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
