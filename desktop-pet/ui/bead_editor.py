"""Perler bead pixel-art editor for creating custom desktop pets."""

import os
import json
from datetime import datetime
from enum import Enum
from PyQt6.QtCore import Qt, QPoint, QSize, QRect, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QBrush, QPen, QMouseEvent, QPixmap, QImage, QIcon, QPainterPath
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QScrollArea, QFrame,
    QComboBox, QColorDialog, QButtonGroup, QToolTip
)
from PIL import Image
from resources.generate_toyu import render_pixel_art

class Tool(Enum):
    PEN = "pen"
    ERASER = "eraser"
    LINE = "line"
    RECT = "rect"
    ELLIPSE = "ellipse"
    FILL = "fill"

def _make_tool_icon(tool: Tool, size=24) -> QPixmap:
    """Draw a cute pixel-art icon using small grid → scaled up."""
    GRIDS = {
        Tool.PEN: [
            "............",
            "...........g",
            "..........gg",
            ".........gy.",
            "........gyy.",
            ".......gyy..",
            "......gyy...",
            ".....gyy....",
            "....gyy.....",
            "...gyy......",
            "..gg........",
            ".g..........",
        ],
        Tool.ERASER: [
            "............",
            "............",
            "....llllll..",
            "...llLLLLll.",
            "..llLLLLLLl.",
            "..lLLLLLLLl.",
            "..lDDDDDDDl.",
            "..lDDDDDDDl.",
            "..lDDDDDDDl.",
            "...dddddddd.",
            "............",
            "............",
        ],
        Tool.LINE: [
            "............",
            "..........cc",
            ".........c..",
            "........c...",
            ".......c....",
            "......c.....",
            ".....c......",
            "....c.......",
            "...c........",
            "..c.........",
            "cc..........",
            "............",
        ],
        Tool.RECT: [
            "............",
            "..bbbbbbbb..",
            "..b......b..",
            "..b......b..",
            "..b......b..",
            "..b......b..",
            "..b......b..",
            "..b......b..",
            "..b......b..",
            "..bbbbbbbb..",
            "............",
            "............",
        ],
        Tool.ELLIPSE: [
            "............",
            "....gggg....",
            "...g....g...",
            "..g......g..",
            "..g......g..",
            "..g......g..",
            "..g......g..",
            "..g......g..",
            "...g....g...",
            "....gggg....",
            "............",
            "............",
        ],
        Tool.FILL: [
            "............",
            "....bb......",
            "...b..b.....",
            "...bbbb.....",
            "...bBBb.....",
            "...bBBb.....",
            "...bBBb.....",
            "...bBBb.....",
            "...bBBb.y...",
            "....bByyy...",
            ".....yyy....",
            "............",
        ],
    }

    COLORS = {
        Tool.PEN: {
            'g': QColor(100, 80, 60),   # dark brown tip
            'y': QColor(255, 220, 100),  # yellow body
        },
        Tool.ERASER: {
            'l': QColor(255, 200, 220),  # light pink highlight
            'L': QColor(255, 180, 200),  # medium pink
            'D': QColor(220, 140, 170),  # dark pink
            'd': QColor(200, 120, 150),  # shadow
        },
        Tool.LINE: {
            'c': QColor(196, 154, 60),   # gold
        },
        Tool.RECT: {
            'b': QColor(80, 150, 220),   # blue
        },
        Tool.ELLIPSE: {
            'g': QColor(80, 180, 100),   # green
        },
        Tool.FILL: {
            'b': QColor(180, 130, 70),   # bucket outline
            'B': QColor(230, 190, 110),   # bucket fill
            'y': QColor(196, 154, 60),   # paint
        },
    }

    grid = GRIDS.get(tool, GRIDS[Tool.PEN])
    colors = COLORS.get(tool, {})
    grid_h = len(grid)
    grid_w = max(len(row) for row in grid)

    img = QImage(grid_w, grid_h, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    for gy, row in enumerate(grid):
        for gx, ch in enumerate(row):
            if ch != '.' and ch in colors:
                img.setPixelColor(gx, gy, colors[ch])

    from PyQt6.QtCore import Qt as QtCore
    scaled = img.scaled(size, size,
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.FastTransformation)
    return QPixmap.fromImage(scaled)

BEAD_PALETTE = {
    'W': ("纯白", QColor(255, 255, 255)),
    'w': ("奶油白", QColor(255, 248, 230)),
    'C': ("米色", QColor(255, 230, 200)),
    'c': ("浅米色", QColor(255, 240, 220)),
    'h': ("浅灰", QColor(210, 210, 210)),
    'H': ("灰色", QColor(170, 170, 170)),
    'z': ("深灰", QColor(100, 100, 100)),
    'Z': ("炭灰", QColor(55, 55, 55)),
    'K': ("黑色", QColor(30, 30, 30)),
    'F': ("肤色", QColor(255, 210, 170)),
    'f': ("深肤色", QColor(220, 170, 130)),
    'D': ("深棕", QColor(80, 50, 20)),
    'd': ("红棕", QColor(160, 80, 40)),
    'B': ("棕色", QColor(140, 100, 50)),
    'b': ("咖啡", QColor(120, 70, 30)),
    'T': ("浅棕", QColor(200, 160, 100)),
    't': ("沙色", QColor(220, 190, 140)),
    'r': ("深红", QColor(180, 30, 30)),
    'R': ("红色", QColor(220, 50, 50)),
    'x': ("亮红", QColor(255, 70, 70)),
    'M': ("玫红", QColor(230, 50, 130)),
    'm': ("桃红", QColor(255, 130, 130)),
    'P': ("粉色", QColor(255, 150, 180)),
    'p': ("亮粉", QColor(255, 180, 200)),
    'q': ("浅粉", QColor(255, 210, 230)),
    'o': ("深橙", QColor(230, 110, 30)),
    'O': ("橙色", QColor(255, 150, 50)),
    'j': ("浅橙", QColor(255, 180, 100)),
    'G': ("金色", QColor(220, 180, 60)),
    'Y': ("黄色", QColor(255, 240, 50)),
    'y': ("浅黄", QColor(255, 250, 150)),
    'g': ("奶油黄", QColor(255, 245, 180)),
    'E': ("深绿", QColor(30, 120, 40)),
    'e': ("橄榄绿", QColor(100, 130, 40)),
    'N': ("绿色", QColor(80, 180, 50)),
    'n': ("翠绿", QColor(50, 200, 100)),
    'L': ("浅绿", QColor(160, 220, 100)),
    'l': ("黄绿", QColor(180, 230, 60)),
    'i': ("薄荷绿", QColor(100, 210, 160)),
    'u': ("深蓝", QColor(30, 60, 180)),
    'U': ("蓝色", QColor(50, 100, 220)),
    'A': ("浅蓝", QColor(130, 180, 255)),
    'a': ("天蓝", QColor(100, 200, 255)),
    'J': ("湖蓝", QColor(60, 180, 210)),
    'Q': ("青色", QColor(50, 200, 200)),
    'I': ("浅青", QColor(150, 230, 230)),
    'v': ("深紫", QColor(100, 20, 160)),
    'V': ("紫色", QColor(150, 60, 200)),
    'S': ("浅紫", QColor(190, 130, 240)),
    's': ("薰衣草", QColor(210, 180, 250)),
    'X': ("品红", QColor(200, 50, 180)),
    '.': ("透明", QColor(0, 0, 0, 0)),
}

PALETTE_SECTIONS = [
    ("中性色 · 白色/米色", ['W', 'w', 'C', 'c']),
    ("中性色 · 灰色/黑色", ['h', 'H', 'z', 'Z', 'K']),
    ("肤色", ['F', 'f']),
    ("棕色系", ['D', 'd', 'B', 'b', 'T', 't']),
    ("红色系", ['r', 'R', 'x', 'M', 'm']),
    ("粉色系", ['P', 'p', 'q']),
    ("橙色系", ['o', 'O', 'j']),
    ("黄色/金色系", ['G', 'Y', 'y', 'g']),
    ("绿色系", ['E', 'e', 'N', 'n', 'L', 'l', 'i']),
    ("蓝色系", ['u', 'U', 'A', 'a', 'J']),
    ("青色系", ['Q', 'I']),
    ("紫色系", ['v', 'V', 'S', 's', 'X']),
    ("", ['.']),
]

GRID_SIZE = 32
CELL_SIZE = 16  # pixels per cell on canvas
CANVAS_SIZE = GRID_SIZE * CELL_SIZE  # 512
GRID_SIZES = [16, 32, 48]

class BeadCanvas(QWidget):
    """Pixel-art drawing grid with configurable dimensions."""

    MAX_CANVAS = 512

    def __init__(self, parent=None, grid_size=32):
        super().__init__(parent)
        self._grid_size = grid_size
        self._cell_size = max(8, self.MAX_CANVAS // grid_size)
        self._canvas_px = self._cell_size * grid_size
        self.setFixedSize(self._canvas_px, self._canvas_px)
        self.setMouseTracking(True)
        self._grid = [['.' for _ in range(grid_size)] for _ in range(grid_size)]
        self._current_color = 'K'
        self._current_tool = Tool.PEN
        self._drawing = False
        self._erasing = False
        self._undo_stack = []
        self._is_dirty = False
        self._shape_start = None  # QPoint cell coords
        self._shape_preview = None  # list of (x, y) cells to preview

    @property
    def grid_size(self):
        return self._grid_size

    def set_tool(self, tool: Tool):
        self._current_tool = tool

    def resize_grid(self, new_size):
        if new_size == self._grid_size:
            return
        old_grid = self._grid
        old_size = self._grid_size
        self._grid_size = new_size
        self._cell_size = max(8, self.MAX_CANVAS // new_size)
        self._canvas_px = self._cell_size * new_size
        self.setFixedSize(self._canvas_px, self._canvas_px)
        self._grid = [['.' for _ in range(new_size)] for _ in range(new_size)]
        scale = new_size / old_size
        for y in range(new_size):
            for x in range(new_size):
                ox = int(x / scale)
                oy = int(y / scale)
                if 0 <= ox < old_size and 0 <= oy < old_size:
                    self._grid[y][x] = old_grid[oy][ox]
        self._undo_stack.clear()
        self._is_dirty = True
        self.update()

    def set_color(self, key):
        self._current_color = key

    @property
    def grid(self):
        return self._grid

    @grid.setter
    def grid(self, g):
        self._grid = g
        self.update()

    def clear_grid(self):
        self._undo_stack.append([row[:] for row in self._grid])
        self._grid = [['.' for _ in range(self._grid_size)] for _ in range(self._grid_size)]
        self._is_dirty = True
        self.update()

    def undo(self):
        if self._undo_stack:
            self._grid = self._undo_stack.pop()
            self.update()

    def _push_undo(self):
        self._undo_stack.append([row[:] for row in self._grid])
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _cell_at(self, pos):
        x = pos.x() // self._cell_size
        y = pos.y() // self._cell_size
        if 0 <= x < self._grid_size and 0 <= y < self._grid_size:
            return x, y
        return None

    def mark_clean(self):
        self._is_dirty = False

    def mark_dirty(self):
        self._is_dirty = True

    @property
    def is_dirty(self):
        return self._is_dirty

    def mousePressEvent(self, event: QMouseEvent):
        cell = self._cell_at(event.position().toPoint())
        if cell is None:
            return
        self._push_undo()
        self._is_dirty = True
        tool = self._current_tool

        if tool == Tool.FILL:
            if event.button() == Qt.MouseButton.LeftButton:
                self._flood_fill(cell[0], cell[1], self._current_color)
            elif event.button() == Qt.MouseButton.RightButton:
                self._flood_fill(cell[0], cell[1], '.')
            self.update()
            return

        if tool in (Tool.PEN, Tool.ERASER):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drawing = True
                color = '.' if tool == Tool.ERASER else self._current_color
                self._grid[cell[1]][cell[0]] = color
            elif event.button() == Qt.MouseButton.RightButton:
                self._erasing = True
                self._grid[cell[1]][cell[0]] = '.'
        elif tool in (Tool.LINE, Tool.RECT, Tool.ELLIPSE):
            if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
                self._drawing = True
                self._shape_start = cell
                self._shape_preview = None
                self._erasing = (event.button() == Qt.MouseButton.RightButton)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        cell = self._cell_at(event.position().toPoint())
        if cell is None:
            return
        tool = self._current_tool

        if tool in (Tool.PEN, Tool.ERASER) and (self._drawing or self._erasing):
            color = '.' if tool == Tool.ERASER or self._erasing else self._current_color
            self._grid[cell[1]][cell[0]] = color
            self.update()
        elif tool in (Tool.LINE, Tool.RECT, Tool.ELLIPSE) and self._drawing and self._shape_start:
            self._shape_preview = self._get_shape_cells(
                self._shape_start, cell, tool
            )
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        tool = self._current_tool

        if tool in (Tool.LINE, Tool.RECT, Tool.ELLIPSE) and self._drawing:
            if self._shape_preview:
                color = '.' if self._erasing else self._current_color
                for x, y in self._shape_preview:
                    if 0 <= x < self._grid_size and 0 <= y < self._grid_size:
                        self._grid[y][x] = color
            self._shape_start = None
            self._shape_preview = None
            self._erasing = False

        self._drawing = False
        self._erasing = False
        self.update()

    def _get_shape_cells(self, start, end, tool):
        """Get list of (x, y) cells for a shape from start to end."""
        x0, y0 = start
        x1, y1 = end
        cells = []

        if tool == Tool.LINE:
            cells = self._bresenham_line(x0, y0, x1, y1)
        elif tool == Tool.RECT:
            xmin, xmax = min(x0, x1), max(x0, x1)
            ymin, ymax = min(y0, y1), max(y0, y1)
            for x in range(xmin, xmax + 1):
                cells.append((x, ymin))
                cells.append((x, ymax))
            for y in range(ymin + 1, ymax):
                cells.append((xmin, y))
                cells.append((xmax, y))
        elif tool == Tool.ELLIPSE:
            cells = self._midpoint_ellipse(x0, y0, x1, y1)
        return cells

    @staticmethod
    def _bresenham_line(x0, y0, x1, y1):
        """Bresenham's line algorithm."""
        cells = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            cells.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
        return cells

    @staticmethod
    def _midpoint_ellipse(x0, y0, x1, y1):
        """Midpoint ellipse algorithm for pixel-art ellipse outline."""
        xmin, xmax = min(x0, x1), max(x0, x1)
        ymin, ymax = min(y0, y1), max(y0, y1)
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        rx = (xmax - xmin) / 2
        ry = (ymax - ymin) / 2
        if rx < 0.5 and ry < 0.5:
            return [(round(cx), round(cy))]
        if rx < 0.5:
            return [(round(cx), y) for y in range(ymin, ymax + 1)]
        if ry < 0.5:
            return [(x, round(cy)) for x in range(xmin, xmax + 1)]

        cells = set()
        steps = max(int(max(rx, ry) * 8), 32)
        import math
        for i in range(steps):
            angle = 2 * math.pi * i / steps
            x = round(cx + rx * math.cos(angle))
            y = round(cy + ry * math.sin(angle))
            cells.add((x, y))
        return list(cells)

    def _flood_fill(self, sx, sy, fill_color):
        """Flood fill from (sx, sy) with fill_color."""
        target = self._grid[sy][sx]
        if target == fill_color:
            return
        stack = [(sx, sy)]
        visited = set()
        while stack:
            x, y = stack.pop()
            if (x, y) in visited:
                continue
            if not (0 <= x < self._grid_size and 0 <= y < self._grid_size):
                continue
            if self._grid[y][x] != target:
                continue
            visited.add((x, y))
            self._grid[y][x] = fill_color
            stack.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])

    def paintEvent(self, event):
        painter = QPainter(self)
        gs = self._grid_size
        cs = self._cell_size
        for cy in range(gs):
            for cx in range(gs):
                x = cx * cs
                y = cy * cs
                key = self._grid[cy][cx]
                if key == '.':
                    light = (cx + cy) % 2 == 0
                    painter.fillRect(x, y, cs, cs,
                                     QColor(220, 220, 220) if light else QColor(255, 255, 255))
                else:
                    color = BEAD_PALETTE.get(key, (None, QColor(0, 0, 0)))[1]
                    painter.fillRect(x, y, cs, cs, color)

        if self._shape_preview and self._drawing:
            preview_color = QColor(196, 154, 60, 120)  # Gold semi-transparent
            for px, py in self._shape_preview:
                if 0 <= px < gs and 0 <= py < gs:
                    painter.fillRect(px * cs, py * cs, cs, cs, preview_color)

        pen = QPen(QColor(200, 200, 200), 1)
        painter.setPen(pen)
        for i in range(gs + 1):
            p = i * cs
            painter.drawLine(0, p, self._canvas_px, p)
            painter.drawLine(p, 0, p, self._canvas_px)

        if self._current_tool in (Tool.LINE, Tool.RECT, Tool.ELLIPSE):
            pen = QPen(QColor(196, 154, 60, 80), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(0, 0, self._canvas_px - 1, self._canvas_px - 1)

        painter.end()

class BeadEditor(QMainWindow):
    """Perler bead pixel-art editor window."""

    def __init__(self, parent=None, on_export=None, on_showcase_save=None):
        super().__init__(parent)
        self._export_callback = on_export
        self._showcase_save_callback = on_showcase_save
        self._palette_btns = {}
        self._custom_color = QColor(255, 255, 255)
        self._init_ui()
        self._update_title()

    def _init_ui(self):
        self.setWindowTitle("拼豆编辑器 — 设计你的像素宠物")
        self.setMinimumSize(800, 680)
        self.resize(860, 720)
        self.setStyleSheet("""
            QComboBox {
                padding: 3px 8px;
                border: 1px solid #E8D5C0;
                border-radius: 4px;
                background: #FFFFFF;
                color: #2C1810;
                font-size: 11px;
            }
            QComboBox:hover { border-color: #C49A3C; }
            QComboBox::drop-down { border: none; width: 18px; }
            QComboBox QAbstractItemView {
                background: #FFFFFF;
                color: #2C1810;
                selection-background-color: #FFF3E0;
                selection-color: #2C1810;
                border: 1px solid #E8D5C0;
                outline: none;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        canvas_frame = QFrame()
        canvas_frame.setObjectName("canvasFrame")
        canvas_frame.setStyleSheet(
            "QFrame#canvasFrame { background: #FAFAFA; border: 1px solid #E8D5C0; "
            "border-radius: 8px; }"
        )
        canvas_frame_layout = QVBoxLayout(canvas_frame)
        canvas_frame_layout.setContentsMargins(12, 12, 12, 12)
        self._canvas = BeadCanvas(grid_size=GRID_SIZE)
        canvas_frame_layout.addWidget(self._canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        left_col.addWidget(canvas_frame)

        tools_bar = QHBoxLayout()
        tools_bar.setSpacing(4)

        tool_label = QLabel("工具:")
        tool_label.setStyleSheet("font-size: 11px; color: #8B7355; font-weight: bold;")
        tools_bar.addWidget(tool_label)

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_btns = {}

        tool_defs = [
            (Tool.PEN, "铅笔", "P"),
            (Tool.ERASER, "橡皮", "E"),
            (Tool.LINE, "直线", "L"),
            (Tool.RECT, "矩形", "R"),
            (Tool.ELLIPSE, "椭圆", "O"),
            (Tool.FILL, "填充", "F"),
        ]

        for i, (tool, label, key) in enumerate(tool_defs):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setToolTip(f"{label} ({key})")
            btn.setCheckable(True)
            btn.setChecked(tool == Tool.PEN)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(QIcon(_make_tool_icon(tool, 20)))
            btn.setIconSize(QSize(20, 20))
            btn.setStyleSheet("""
                QPushButton {
                    background: #FFFFFF;
                    border: 2px solid #E8D5C0;
                    border-radius: 6px;
                    padding: 2px;
                }
                QPushButton:checked {
                    background: #FFF3E0;
                    border-color: #C49A3C;
                }
                QPushButton:hover {
                    border-color: #C49A3C;
                    background: #FFF8F0;
                }
            """)
            btn.clicked.connect(lambda checked, t=tool: self._on_tool_selected(t))
            self._tool_group.addButton(btn, i)
            self._tool_btns[tool] = btn
            tools_bar.addWidget(btn)

        tools_bar.addStretch()
        left_col.addLayout(tools_bar)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._canvas.clear_grid)
        clear_btn.setToolTip("清空画布")
        toolbar.addWidget(clear_btn)

        undo_btn = QPushButton("撤销")
        undo_btn.clicked.connect(self._canvas.undo)
        undo_btn.setToolTip("撤销 (Ctrl+Z)")
        toolbar.addWidget(undo_btn)

        showcase_btn = QPushButton("保存到作品集")
        showcase_btn.clicked.connect(self._on_save_to_showcase)
        toolbar.addWidget(showcase_btn)

        toolbar.addStretch()

        grid_label = QLabel("网格:")
        grid_label.setStyleSheet("font-size: 11px; color: #8B7355; font-weight: bold;")
        toolbar.addWidget(grid_label)
        self._grid_combo = QComboBox()
        self._grid_combo.addItems([f"{s}×{s}" for s in GRID_SIZES])
        self._grid_combo.setCurrentText(f"{GRID_SIZE}×{GRID_SIZE}")
        self._grid_combo.setFixedWidth(64)
        self._grid_combo.currentTextChanged.connect(self._on_grid_size_change)
        toolbar.addWidget(self._grid_combo)

        toolbar.addSpacing(8)

        save_btn = QPushButton("保存拼豆")
        save_btn.clicked.connect(self._on_save)
        save_btn.setToolTip("保存到文件 (Ctrl+S)")
        toolbar.addWidget(save_btn)

        load_btn = QPushButton("加载拼豆")
        load_btn.clicked.connect(self._on_load)
        toolbar.addWidget(load_btn)

        export_btn = QPushButton("导出宠物")
        export_btn.setStyleSheet(
            "QPushButton { background: #C49A3C; color: white; font-weight: bold; "
            "border-radius: 6px; padding: 6px 14px; } "
            "QPushButton:hover { background: #D4AE50; }"
        )
        export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(export_btn)

        left_col.addLayout(toolbar)
        root.addLayout(left_col, stretch=4)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        preview_card = QFrame()
        preview_card.setFixedHeight(90)
        preview_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 2px solid #E8D5C0;
                border-radius: 10px;
                padding: 4px;
            }
        """)
        preview_inner = QHBoxLayout(preview_card)
        preview_inner.setContentsMargins(8, 4, 8, 4)
        preview_inner.setSpacing(8)

        self._preview = QLabel()
        self._preview.setFixedSize(74, 74)
        self._preview.setStyleSheet(
            "border: 1px solid #E8D5C0; border-radius: 4px; "
            "background: #FAFAFA;"
        )
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_inner.addWidget(self._preview, alignment=Qt.AlignmentFlag.AlignVCenter)

        preview_info = QVBoxLayout()
        preview_info.setSpacing(2)
        preview_title = QLabel("实时预览")
        preview_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #5C3D1E;")
        preview_info.addWidget(preview_title)
        self._preview_info_label = QLabel("32×32 像素 · 4 色")
        self._preview_info_label.setStyleSheet(
            "font-size: 10px; color: #8B7355;"
        )
        preview_info.addWidget(self._preview_info_label)
        preview_info.addStretch()
        preview_inner.addLayout(preview_info)

        self._update_preview()
        right_col.addWidget(preview_card)

        palette_card = QFrame()
        palette_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 2px solid #E8D5C0;
                border-radius: 10px;
                padding: 6px;
            }
        """)
        palette_card_inner = QVBoxLayout(palette_card)
        palette_card_inner.setContentsMargins(6, 6, 6, 6)
        palette_card_inner.setSpacing(4)

        palette_label = QLabel("调色板")
        palette_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #5C3D1E;")
        palette_card_inner.addWidget(palette_label)

        palette_scroll = QScrollArea()
        palette_scroll.setWidgetResizable(True)
        palette_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        palette_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        palette_widget = QWidget()
        palette_widget.setStyleSheet("background: transparent;")
        palette_layout = QVBoxLayout(palette_widget)
        palette_layout.setContentsMargins(2, 2, 2, 2)
        palette_layout.setSpacing(2)

        self._build_palette(palette_layout)

        palette_layout.addStretch()
        palette_scroll.setWidget(palette_widget)
        palette_card_inner.addWidget(palette_scroll)
        right_col.addWidget(palette_card, stretch=1)

        root.addLayout(right_col, stretch=1)  # Right takes 1/4 of space

        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(300)

    def _build_palette(self, layout):
        """Build palette grid with section labels from PALETTE_SECTIONS."""
        row_len = 6
        for section_name, section_keys in PALETTE_SECTIONS:
            if section_name:
                lbl = QLabel(section_name)
                lbl.setStyleSheet(
                    "font-size: 10px; color: #8B7355; font-weight: bold; "
                    "padding-top: 6px; padding-bottom: 1px;"
                )
                layout.addWidget(lbl)

            for r in range(0, len(section_keys), row_len):
                row = QHBoxLayout()
                row.setSpacing(3)
                for c in range(row_len):
                    idx = r + c
                    if idx >= len(section_keys):
                        break
                    key = section_keys[idx]
                    name, color = BEAD_PALETTE[key]
                    btn = QPushButton()
                    btn.setFixedSize(28, 28)
                    btn.setToolTip(f"{name} [{key}]")
                    if key == '.':
                        btn.setStyleSheet(
                            "QPushButton { border: 2px solid #ccc; border-radius: 4px; "
                            "background: #fafafa; } "
                            "QPushButton:hover { border-color: #C49A3C; }"
                        )
                        btn.setText("✕")
                    else:
                        border = "#C49A3C" if key == self._canvas._current_color else "#ddd"
                        btn.setStyleSheet(
                            f"QPushButton {{ border: 2px solid {border}; border-radius: 4px; "
                            f"background: {color.name()}; }} "
                            f"QPushButton:hover {{ border-color: #C49A3C; }}"
                        )
                    btn.clicked.connect(lambda checked, k=key: self._select_color(k))
                    self._palette_btns[key] = btn
                    row.addWidget(btn)
                row.addStretch()
                layout.addLayout(row)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(3)
        custom_lbl = QLabel("自定义")
        custom_lbl.setStyleSheet(
            "font-size: 10px; color: #8B7355; font-weight: bold; "
            "padding-top: 6px; padding-bottom: 1px;"
        )
        layout.addWidget(custom_lbl)
        picker_btn = QPushButton("+")
        picker_btn.setFixedSize(28, 28)
        picker_btn.setToolTip("自定义颜色…")
        picker_btn.setStyleSheet(
            "QPushButton { border: 2px dashed #C49A3C; border-radius: 4px; "
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #ff0000, stop:0.25 #00ff00, stop:0.5 #0000ff, stop:1 #ff00ff); "
            "color: white; font-weight: bold; font-size: 14px; } "
            "QPushButton:hover { border-color: #D4AE50; }"
        )
        picker_btn.clicked.connect(self._on_pick_custom_color)
        custom_row.addWidget(picker_btn)
        custom_row.addStretch()
        layout.addLayout(custom_row)

        self._select_color(self._canvas._current_color)

    def _select_color(self, key):
        self._canvas.set_color(key)
        for k, btn in self._palette_btns.items():
            if k == '.':
                continue
            name, color = BEAD_PALETTE[k]
            border = "#C49A3C" if k == key else "#ddd"
            btn.setStyleSheet(
                f"QPushButton {{ border: 2px solid {border}; border-radius: 4px; "
                f"background: {color.name()}; }} "
                f"QPushButton:hover {{ border-color: #C49A3C; }}"
            )

    def _on_tool_selected(self, tool: Tool):
        self._canvas.set_tool(tool)

    def _on_grid_size_change(self, text):
        try:
            new_size = int(text.split("×")[0])
        except ValueError:
            return
        self._canvas.resize_grid(new_size)
        self._update_title()
        self._preview_timer.stop()
        self._update_preview()
        self._preview_timer.start(300)

    def _update_title(self):
        gs = self._canvas.grid_size
        self.setWindowTitle(f"拼豆编辑器 — {gs}×{gs} 像素宠物")

    def _show_info(self, title, text):
        """Show a styled info message box."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Information)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet("""
            QMessageBox { background: #FFF8F0; }
            QLabel { color: #2C1810; font-size: 12px; }
            QPushButton {
                background: #FFFFFF; border: 2px solid #E8D5C0;
                border-radius: 6px; padding: 4px 14px;
                color: #2C1810; font-weight: bold; min-width: 60px;
            }
            QPushButton:hover { border-color: #C49A3C; background: #FFF3E0; }
        """)
        box.exec()

    def _ask_yes_no_cancel(self, title, text):
        """Show a styled question box. Returns StandardButton."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        box.setStyleSheet("""
            QMessageBox { background: #FFF8F0; }
            QLabel { color: #2C1810; font-size: 12px; }
            QPushButton {
                background: #FFFFFF; border: 2px solid #E8D5C0;
                border-radius: 6px; padding: 4px 14px;
                color: #2C1810; font-weight: bold; min-width: 60px;
            }
            QPushButton:hover { border-color: #C49A3C; background: #FFF3E0; }
        """)
        return box.exec()

    def _style_message_box(self):
        """No-op kept for compatibility."""
        pass

    def _on_pick_custom_color(self):
        dlg = QColorDialog(self._custom_color, self)
        dlg.setWindowTitle("选择自定义颜色")
        dlg.setStyleSheet("""
            QColorDialog {
                background: #FFF8F0;
                color: #2C1810;
            }
            QColorDialog QWidget {
                background: #FFF8F0;
                color: #2C1810;
            }
            QPushButton {
                background: #FFFFFF;
                border: 2px solid #E8D5C0;
                border-radius: 6px;
                padding: 4px 10px;
                color: #2C1810;
                font-weight: bold;
            }
            QPushButton:hover {
                border-color: #C49A3C;
                background: #FFF3E0;
            }
            QSpinBox, QLineEdit, QComboBox {
                background: #FFFFFF;
                border: 1px solid #E8D5C0;
                border-radius: 4px;
                color: #2C1810;
                padding: 2px;
            }
            QTabWidget::pane {
                border: 1px solid #E8D5C0;
                background: #FFF8F0;
            }
            QTabBar::tab {
                background: #F5EFE5;
                border: 1px solid #E8D5C0;
                padding: 4px 8px;
                color: #5C3D1E;
            }
            QTabBar::tab:selected {
                background: #FFF8F0;
                border-bottom-color: #FFF8F0;
                color: #2C1810;
            }
            QLabel {
                color: #2C1810;
            }
            QGroupBox {
                color: #2C1810;
                border: 1px solid #E8D5C0;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 6px;
            }
            QGroupBox::title {
                color: #5C3D1E;
            }
        """)
        if dlg.exec() != QColorDialog.DialogCode.Accepted:
            return
        color = dlg.selectedColor()
        if not color.isValid():
            return
        self._custom_color = color
        key = '*'
        name = "自定义"
        BEAD_PALETTE[key] = (name, color)
        self._select_color(key)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self._canvas.undo()
                return
            elif event.key() == Qt.Key.Key_S:
                self._on_save()
                return
        key_map = {
            Qt.Key.Key_P: Tool.PEN, Qt.Key.Key_E: Tool.ERASER,
            Qt.Key.Key_L: Tool.LINE, Qt.Key.Key_R: Tool.RECT,
            Qt.Key.Key_O: Tool.ELLIPSE, Qt.Key.Key_F: Tool.FILL,
        }
        tool = key_map.get(event.key())
        if tool and not event.modifiers():
            self._on_tool_selected(tool)
            self._tool_btns[tool].setChecked(True)
            return
        super().keyPressEvent(event)

    def _update_preview(self):
        rgba = self._render_to_rgba()
        if rgba is None:
            return
        gs = self._canvas.grid_size
        preview_size = max(60, min(160, gs * 5))
        qimg = QImage(rgba.tobytes(), rgba.width, rgba.height,
                       rgba.width * 4, QImage.Format.Format_RGBA8888)
        pix = QPixmap.fromImage(qimg).scaled(
            preview_size, preview_size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self._preview.setPixmap(pix)
        self._preview_info_label.setText(f"{gs}×{gs} 像素 · {self._count_colors()} 色")

    def _count_colors(self):
        colors = set()
        for row in self._canvas.grid:
            for ch in row:
                if ch != '.':
                    colors.add(ch)
        return len(colors)

    def _render_to_rgba(self, scale=5):
        palette = {k: (v[1].red(), v[1].green(), v[1].blue(),
                       255 if k != '.' else 0) for k, v in BEAD_PALETTE.items()}
        return render_pixel_art(self._canvas.grid, palette, scale=scale)

    def _save_to_showcase_dir(self):
        """Save grid as JSON + render PNG to showcase directory.
        Returns (json_path, png_path, name) or None if grid is empty."""
        gs = self._canvas.grid_size
        has_content = any(
            self._canvas.grid[y][x] != '.'
            for y in range(gs) for x in range(gs)
        )
        if not has_content:
            return None

        name = f"bead_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        creations_dir = os.path.join(os.path.expanduser("~"), ".desktop_pet", "bead_creations")
        os.makedirs(creations_dir, exist_ok=True)

        json_path = os.path.join(creations_dir, f"{name}.json")
        png_path = os.path.join(creations_dir, f"{name}.png")

        data = {
            "grid": self._canvas.grid,
            "grid_size": self._canvas.grid_size,
            "version": "1.1",
            "name": name,
            "created_at": datetime.now().isoformat()
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)

        img = self._render_to_rgba(scale=5)
        img.save(png_path, "PNG")

        return json_path, png_path, name

    def _on_save_to_showcase(self, checked=False):
        result = self._save_to_showcase_dir()
        if result is None:
            self._show_info("提示", "请先画点什么吧！")
            return
        json_path, png_path, name = result
        if self._showcase_save_callback:
            self._showcase_save_callback(json_path, png_path, name)
        self._canvas.mark_clean()
        self._show_info("已保存", f"作品「{name}」已保存到作品集！")

    def _on_export(self, checked=False):
        result = self._save_to_showcase_dir()
        if result is None:
            self._show_info("提示", "请先画点什么吧！")
            return

        json_path, png_path, name = result
        if self._export_callback:
            self._export_callback(json_path, png_path, name)
        self._canvas.mark_clean()
        self.close()
        self._show_info("完成", f"宠物已导出!\n{png_path}")

    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存拼豆文件",
            os.path.expanduser("~/Documents/bead_pet.json"),
            "拼豆文件 (*.json)"
        )
        if path:
            data = {
                "grid": self._canvas.grid,
                "grid_size": self._canvas.grid_size,
                "version": "1.1"
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            self._canvas.mark_clean()

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载拼豆文件",
            os.path.expanduser("~/Documents"),
            "拼豆文件 (*.json)"
        )
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                saved_size = data.get("grid_size", GRID_SIZE)
                if saved_size != self._canvas.grid_size:
                    self._canvas.resize_grid(saved_size)
                    self._grid_combo.setCurrentText(f"{saved_size}×{saved_size}")
                self._canvas.grid = data.get("grid", self._canvas.grid)
                self._canvas.mark_clean()
                self._canvas.update()
                self._update_preview()
            except Exception as e:
                self._show_info("错误", f"加载失败: {e}")

    def closeEvent(self, event):
        if self._canvas.is_dirty:
            reply = self._ask_yes_no_cancel(
                "未保存的更改",
                "还有未保存的更改，是否保存到作品集后再关闭？"
            )
            if reply == QMessageBox.StandardButton.Yes:
                result = self._save_to_showcase_dir()
                if result:
                    json_path, png_path, name = result
                    if self._showcase_save_callback:
                        self._showcase_save_callback(json_path, png_path, name)
                    self._canvas.mark_clean()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
