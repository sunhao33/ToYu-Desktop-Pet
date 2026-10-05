"""今日专注时间轴。

把一天的专注段画成一条 24 小时时间轴：
  * 色块位置 = 开始时刻，宽度 = 持续时长
  * 色块深浅 = 时长（越长越深），一眼看出主力时段
  * 当前时刻有标记线
  * 悬停显示"09:30-10:15 写竞赛设计文档（45 分钟）"

为什么值得单独画：心流模式中间原本大片空白，而"今天什么时候专注了"
不比"今天一共专注了多久"次要 —— 后者只是个数字，前者能看出节奏与断点。
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from pet_engine.focus_log import KIND_BREAK, KIND_FOCUS

TRACK_HEIGHT = 30
LABEL_HEIGHT = 14
MAX_BAR = 17            # 色块最大高度
MIN_BAR_PX = 3.0        # 色块最小可见宽度
# 色块用实色而不是叠加透明度：24 小时尺度下 5 分钟的休息段只有 1.5px 宽，
# 再叠加半透明就会在浅色背景上彻底看不见。
FOCUS_COLOR = "#C49A3C"
FOCUS_COLOR_LONG = "#8C6A1F"    # 长时段用更深的金棕色，体现"越长越深"
BREAK_COLOR = "#7FB069"


class FocusTimeline(QWidget):
    """24 小时专注时间轴。"""

    def __init__(self, palette_getter, parent=None):
        super().__init__(parent)
        self._c = palette_getter
        self._records = []
        self.setMinimumHeight(TRACK_HEIGHT + LABEL_HEIGHT + 4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    # ── 数据 ────────────────────────────────────────────────
    def set_records(self, records):
        self._records = list(records or [])
        self.update()

    def _now_minute(self) -> float:
        from datetime import datetime
        now = datetime.now()
        return now.hour * 60 + now.minute + now.second / 60.0

    # ── 绘制 ────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        track_y = 4
        track = QRectF(0, track_y, width, TRACK_HEIGHT)

        # 底槽
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._c("border")))
        painter.drawRoundedRect(track, 5, 5)

        # 6 小时一根刻度线
        grid = QColor(self._c("text2"))
        grid.setAlpha(60)
        painter.setPen(QPen(grid, 1, Qt.PenStyle.DotLine))
        for hour in range(0, 25, 6):
            x = width * (hour * 60) / 1440.0
            painter.drawLine(int(x), track_y, int(x), track_y + TRACK_HEIGHT)

        # 专注段
        segments = self._records
        longest = max((int(r.get("minutes", 0)) for r in segments
                       if r.get("kind") == KIND_FOCUS), default=0) or 1

        for rec in segments:
            start = float(rec.get("start_min", 0))
            minutes = max(1, int(rec.get("minutes", 1)))
            x1 = width * start / 1440.0
            x2 = width * min(1440.0, start + minutes) / 1440.0
            # 保证最小可见宽度：否则 5 分钟的休息段在 24 小时尺度下只有 1.5px
            w = max(MIN_BAR_PX, x2 - x1)
            is_break = rec.get("kind") == KIND_BREAK
            if is_break:
                color = QColor(BREAK_COLOR)
                h = MAX_BAR * 0.5
            else:
                # 时长越长颜色越深（两条实色之间插值，不用透明度）
                ratio = min(1.0, minutes / longest)
                c1, c2 = QColor(FOCUS_COLOR), QColor(FOCUS_COLOR_LONG)
                color = QColor(
                    int(c1.red() + (c2.red() - c1.red()) * ratio),
                    int(c1.green() + (c2.green() - c1.green()) * ratio),
                    int(c1.blue() + (c2.blue() - c1.blue()) * ratio))
                h = MAX_BAR - 3 * (1 - ratio)
            y = track_y + (TRACK_HEIGHT - h) / 2
            painter.setBrush(color)
            # 描一圈浅色边：相邻的专注块与休息块颜色接近时，
            # 没有边就会糊成一块，看不出是两段
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.drawRoundedRect(QRectF(x1, y, w, h), 2.5, 2.5)

        # 当前时刻标记
        now_x = width * self._now_minute() / 1440.0
        painter.setPen(QPen(QColor(self._c("danger")), 2))
        painter.drawLine(int(now_x), track_y - 1, int(now_x),
                         track_y + TRACK_HEIGHT + 1)

        # 刻度文字
        painter.setPen(QColor(self._c("text2")))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        label_y = track_y + TRACK_HEIGHT + 1
        for hour, text, align in ((0, "00", Qt.AlignmentFlag.AlignLeft),
                                  (6, "06", Qt.AlignmentFlag.AlignHCenter),
                                  (12, "12", Qt.AlignmentFlag.AlignHCenter),
                                  (18, "18", Qt.AlignmentFlag.AlignHCenter),
                                  (24, "24", Qt.AlignmentFlag.AlignRight)):
            x = width * hour / 24.0
            painter.drawText(QRectF(x - 14, label_y, 28, LABEL_HEIGHT),
                             int(align), text)
        painter.end()

    # ── 悬停提示 ────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        """悬停到某个色块上时显示明细。"""
        pos = event.position()
        width = max(1, self.width())
        minute = pos.x() / width * 1440.0
        hit = None
        for rec in self._records:
            start = float(rec.get("start_min", 0))
            if start <= minute <= start + max(1, int(rec.get("minutes", 1))):
                hit = rec
                break
        if hit is None:
            kinds = ("专注", "休息")
            total = sum(int(r.get("minutes", 0)) for r in self._records)
            if self._records:
                self.setToolTip("今日共 %d 段、合计 %d 分钟（颜色越深＝单段越长）"
                                % (len(self._records), total))
            else:
                self.setToolTip("今天还没有专注记录，点上面的分钟数开始")
            return
        label = "休息" if hit.get("kind") == KIND_BREAK else "专注"
        task = hit.get("task") or ""
        self.setToolTip("%s-%s  %s %d 分钟%s"
                        % (hit.get("start", ""), hit.get("end", ""), label,
                           int(hit.get("minutes", 0)),
                           ("　" + task) if task else ""))
