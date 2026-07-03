"""Main control window - polished UI for ToYu Desktop Pet."""

import os
import sys
import subprocess
import re
from datetime import datetime
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import (
    QPixmap, QImage, QDragEnterEvent, QDropEvent,
    QPainter, QColor, QBrush, QFont, QIcon, QAction
)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QCheckBox, QGroupBox, QFileDialog,
    QFrame, QApplication, QMessageBox, QSpinBox,
    QSystemTrayIcon, QSizePolicy, QGridLayout,
    QComboBox, QRadioButton, QButtonGroup, QScrollArea, QMenu,
    QStackedWidget, QLineEdit, QDoubleSpinBox
)

from image_processor.processor import process_and_save, get_default_pet_path, get_tv_pet_path, get_house_path, process_bead_image
from pet_engine.pet_window import PetWindow
from pet_engine.pet_state_machine import InteractionMode
from pet_engine.pet_house import HouseWindow
from pet_engine.pet_ai import AICompanion
from ui.settings_manager import SettingsManager
from ui.tray_icon import TrayIcon
from ui.screen_time_tracker import ScreenTimeTracker

class _ScaledLabel(QLabel):
    """QLabel that auto-scales its pixmap to fill width on resize."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._src_pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setPixmap(self, pixmap):
        self._src_pixmap = pixmap

    def setRawPixmap(self, pixmap):
        """Store the original pixmap and scale to current width."""
        self._src_pixmap = pixmap
        self._do_scale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._do_scale()

    def _do_scale(self):
        if self._src_pixmap and not self._src_pixmap.isNull():
            w = max(self.width() - 4, 60)
            scaled = self._src_pixmap.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
            super().setPixmap(scaled)

ACCENT = "#C49A3C"        # potato gold
ACCENT_HOVER = "#D4AE50"  # lighter gold
DARK = "#3E2723"          # dark brown
MID = "#5C3D1E"           # medium brown
LIGHT_BG = "#FFF8F0"      # warm cream
CARD_BG = "#FFFFFF"       # white cards
TEXT = "#2C1810"          # near-black brown
TEXT_SEC = "#8B7355"      # muted brown
BORDER = "#E8D5C0"        # warm beige border
SUCCESS = "#6B9B37"       # earthy green
DANGER = "#C0392B"        # red

DARK_BG = "#2A1F14"       # warm dark brown background
DARK_CARD = "#3A2A1A"     # warm card background
DARK_TEXT = "#E8D5C0"     # warm light text
DARK_TEXT_SEC = "#A08B6E" # warm secondary text
DARK_BORDER = "#4A3525"   # warm dark border
DARK_HEADER = "#1E150D"   # warm dark header

CHECKER_SVG = """
<svg width="16" height="16" xmlns="http://www.w3.org/2000/svg">
  <rect width="16" height="16" fill="#f0f0f0"/>
  <rect width="8" height="8" fill="#d0d0d0"/>
  <rect x="8" y="8" width="8" height="8" fill="#d0d0d0"/>
</svg>
"""

class DropZone(QLabel):
    """Clickable drop zone with transparency checkerboard background."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(180, 180)
        self.setFixedSize(200, 200)
        self._callback = None
        self._has_image = False
        self._dark = False
        self._apply_style()

    def set_dark(self, dark):
        self._dark = dark
        self._apply_style(has_image=self._has_image)

    def _apply_style(self, hover=False, has_image=False):
        if has_image:
            border = "none"
            bg = "transparent"
            text = ""
        elif hover:
            border = f"3px dashed {'#D4AE50' if self._dark else '#C49A3C'}"
            bg = '#4A3525' if self._dark else '#FFF3E0'
            text = "释放图片"
        else:
            border = f"3px dashed {'#4A3525' if self._dark else '#D7CCC8'}"
            bg = '#3A2A1A' if self._dark else '#FAFAFA'
            text = "拖放图片到这里\n或 点击选择"

        self.setStyleSheet(f"""
            QLabel {{
                border: {border};
                border-radius: 16px;
                background: {bg};
                color: {'#A08B6E' if self._dark else '#8D6E63'};
                font-size: 13px;
            }}
        """)
        if not has_image:
            self.setText(text)

    def set_callback(self, cb):
        self._callback = cb

    def show_pixmap(self, pixmap):
        scaled = pixmap.scaled(196, 196, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)
        self._has_image = True
        self._apply_style(has_image=True)

    def mousePressEvent(self, event):
        if self._callback:
            self._callback()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._apply_style(hover=True)

    def dragLeaveEvent(self, event):
        self._apply_style(has_image=self._has_image)

    def dropEvent(self, event: QDropEvent):
        self._apply_style(has_image=self._has_image)
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            path = url.toLocalFile()
            if path and self._callback:
                self._callback(path)
                self._flash_success()

    def _flash_success(self):
        """拖入图片成功后的绿色闪烁反馈"""
        from PyQt6.QtCore import QTimer
        original_style = self.styleSheet()
        if self._dark:
            self.setStyleSheet("""
                QLabel {
                    border: 3px solid #4CAF50;
                    border-radius: 16px;
                    background: #2E4A2E;
                    color: #81C784;
                    font-size: 13px;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    border: 3px solid #4CAF50;
                    border-radius: 16px;
                    background: #E8F5E9;
                    color: #2E7D32;
                    font-size: 13px;
                }
            """)
        QTimer.singleShot(500, lambda: self.setStyleSheet(original_style))

class Toggle(QCheckBox):
    """Styled toggle switch."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = SettingsManager()
        self._pet = None
        self._house = None
        self._tray = None
        self._input_path = ""
        self._first_launch = False
        self._bead_editor = None
        self._pulse_phase = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_status)
        self._app_data_dir = os.path.join(
            os.path.expanduser("~"), ".desktop_pet", "images"
        )
        self._is_dark_mode = False

        self._init_ui()
        self._init_tray()
        self._restore_state()

        self._screen_tracker = ScreenTimeTracker()
        self._screen_tracker.start()

    def _restore_state(self):
        saved = self.settings.pet_image_path
        if saved and os.path.exists(saved):
            self._input_path = saved
            pix = QPixmap(saved)
            if not pix.isNull():
                self._drop_zone.show_pixmap(pix)
            self._start_btn.setEnabled(True)
        else:
            self._first_launch = True
            default = get_default_pet_path()
            self._input_path = default
            pix = QPixmap(default)
            if not pix.isNull():
                self._drop_zone.show_pixmap(pix)
            self._start_btn.setEnabled(True)
            self._status.setText("欢迎!ToYu 已就绪")

        self._cleanup_favorites()
        self._seed_default_favorites()
        self._refresh_favorites()
        self._refresh_bead_creations()
        self._update_time_period_label()

    def _update_time_period_label(self):
        if self.settings.time_awareness_enabled:
            from datetime import datetime
            hour = datetime.now().hour
            if 22 <= hour or hour < 6:
                period = "🌙 夜晚"
                mood = "😴 困了"
            elif 6 <= hour < 10:
                period = "☀ 清晨"
                mood = "😊 精神"
            elif 10 <= hour < 18:
                period = "☀ 白天"
                mood = "😄 开心"
            else:
                period = "🌅 傍晚"
                mood = "😌 放松"
            self._time_period_label.setText(f"{period} · {mood}")
        else:
            self._time_period_label.setText("")

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_launch and self._pet is None:
            self._first_launch = False
            self._on_start_pet()

    def _c(self, key):
        """Return color for current mode. Keys: bg, card, text, text2, border, header, accent, accent_h, mid, success, danger"""
        m = {
            'bg':       (LIGHT_BG,    DARK_BG),
            'card':     (CARD_BG,     DARK_CARD),
            'text':     (TEXT,        DARK_TEXT),
            'text2':    (TEXT_SEC,    DARK_TEXT_SEC),
            'border':   (BORDER,      DARK_BORDER),
            'header':   (DARK,        DARK_HEADER),
            'accent':   (ACCENT,      ACCENT),
            'accent_h': (ACCENT_HOVER, ACCENT_HOVER),
            'mid':      (MID,         ACCENT),
            'success':  (SUCCESS,     SUCCESS),
            'danger':   (DANGER,      DANGER),
            'hover_bg': ('#FFF3E0',   '#4A3525'),
            'press_bg': ('#FFE0B2',   '#5A4535'),
            'input_bg': ('#FAFAFA',   '#3A2A1A'),
            'disable_bg': ('#f0f0f0', '#2A1F14'),
            'disable_fg': ('#bbb',    '#6B5A48'),
            'disable_bdr': ('#e0e0e0', '#3A2A1A'),
            'tab_bg':   ('#FFF8E1',   '#3A2A1A'),
            'handle':   ('#D7CCC8',   '#4A3525'),
            'handle_h': ('#BCAAA4',   '#5A4535'),
            'name_fg':  ('#2C1810',   DARK_TEXT),
        }
        pair = m.get(key, (TEXT, DARK_TEXT))
        return pair[1] if self._is_dark_mode else pair[0]

    def _s(self, template, **extra):
        """Build a styled string with current-mode colors.
        Use {c:key} placeholders, e.g. _s('color: {c:text}; border: 1px solid {c:border};')"""
        colors = {k: self._c(k) for k in (
            'bg','card','text','text2','border','header','accent','accent_h',
            'mid','success','danger','hover_bg','press_bg','input_bg',
            'disable_bg','disable_fg','disable_bdr','tab_bg','handle','handle_h','name_fg'
        )}
        colors.update(extra)
        return template.format(c=colors)

    def _init_ui(self):
        self.setWindowTitle("ToYu · 桌面土豆宠物")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "toyu_icon.ico")))
        self.setMinimumSize(680, 700)
        self.resize(720, 800)
        self.setStyleSheet(self._global_stylesheet())

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(80)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 14, 24, 14)

        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(12)
        
        logo_icon = QLabel("🥔")
        logo_icon.setStyleSheet("font-size: 32px; background: transparent;")
        logo_icon.setFixedSize(48, 48)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(logo_icon)
        
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        title = QLabel("ToYu")
        title.setObjectName("headerTitle")
        title_layout.addWidget(title)
        subtitle = QLabel("桌面土豆宠物  ·  像素伙伴")
        subtitle.setObjectName("headerSub")
        title_layout.addWidget(subtitle)
        logo_layout.addLayout(title_layout)
        
        header_layout.addLayout(logo_layout)
        header_layout.addStretch()

        self._dark_mode_btn = QPushButton("🌙 浅色")
        self._dark_mode_btn.setObjectName("darkModeBtn")
        self._dark_mode_btn.setFixedHeight(32)
        self._dark_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dark_mode_btn.setToolTip("切换深色/浅色模式")
        self._dark_mode_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._c('hover_bg')};
                border: 1px solid {self._c('accent')};
                font-size: 12px;
                font-weight: bold;
                color: {self._c('mid')};
                border-radius: 8px;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background: {self._c('press_bg')};
                border-color: {self._c('accent_h')};
            }}
        """)
        self._dark_mode_btn.clicked.connect(self._toggle_dark_mode)
        header_layout.addWidget(self._dark_mode_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._settings_btn = QPushButton("⚙️ 设置")
        self._settings_btn.setFixedHeight(32)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setToolTip("打开设置面板")
        self._settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._c('hover_bg')};
                border: 1px solid {self._c('accent')};
                font-size: 12px;
                font-weight: bold;
                color: {self._c('mid')};
                border-radius: 8px;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background: {self._c('press_bg')};
                border-color: {self._c('accent_h')};
            }}
        """)
        self._settings_btn.clicked.connect(self._on_open_settings)
        header_layout.addWidget(self._settings_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self._start_btn = QPushButton("启动 ToYu")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._on_start_pet)
        self._start_btn.setFixedWidth(120)
        self._start_btn.setFixedHeight(38)
        header_layout.addWidget(self._start_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        root.addWidget(header)

        root.addWidget(self._h_separator())

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(24, 10, 24, 0)
        tab_row.setSpacing(0)

        self._page_btns = {}
        self._page_stack = QStackedWidget()
        self._page_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._page_stack.setStyleSheet("QStackedWidget { background: transparent; }")

        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {self._c('text2')};
                border: none;
                border-bottom: 3px solid transparent;
                font-size: 13px;
                font-weight: bold;
                padding: 4px 16px;
                border-radius: 0;
            }}
            QPushButton:hover {{
                color: {self._c('text')};
                background: {self._c('hover_bg')};
            }}
            QPushButton:checked {{
                color: {self._c('text')};
                border-bottom: 3px solid {self._c('accent')};
            }}
        """
        for i, (label, icon) in enumerate([("宠物", "🐾"), ("功能", "⚙"), ("工具", "🛠"), ("AI", "🤖")]):
            btn = QPushButton(f"  {icon}  {label}  ")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.setStyleSheet(btn_style)
            btn.clicked.connect(lambda checked, idx=i, lbl=label: self._on_page_switch(idx, lbl))
            tab_row.addWidget(btn)
            self._page_btns[label] = btn

        tab_row.addStretch()
        root.addLayout(tab_row)

        pet_page = QScrollArea()
        pet_page.setWidgetResizable(True)
        pet_page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pet_page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        pet_page.setFrameShape(QFrame.Shape.NoFrame)
        pet_page.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')}; border-radius: 3px; min-height: 20px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        pet_widget = QWidget()
        pet_widget.setStyleSheet("background: transparent;")
        pet_layout = QHBoxLayout(pet_widget)
        pet_layout.setSpacing(0)
        pet_layout.setContentsMargins(20, 16, 20, 14)

        pet_left = QVBoxLayout()
        pet_left.setSpacing(10)

        preview_card = self._make_card("宠物预览")
        preview_card_layout = preview_card.layout()
        preview_card_layout.setSpacing(10)
        self._drop_zone = DropZone()
        self._drop_zone.set_callback(self._on_select_image)
        preview_card_layout.addWidget(self._drop_zone, alignment=Qt.AlignmentFlag.AlignCenter)
        select_btn = QPushButton("选择图片...")
        select_btn.setObjectName("secondaryBtn")
        select_btn.clicked.connect(self._on_select_image)
        preview_card_layout.addWidget(select_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        pet_left.addWidget(preview_card)

        bead_card = QFrame()
        bead_card.setObjectName("beadCard")
        self._bead_card = bead_card
        bead_card.setStyleSheet(f"""
            QFrame#beadCard {{
                background: {self._c('tab_bg')};
                border: 1px solid {self._c('border')};
                border-radius: 10px;
            }}
        """)
        bead_card_layout = QHBoxLayout(bead_card)
        bead_card_layout.setContentsMargins(12, 10, 12, 10)
        bead_card_layout.setSpacing(12)
        bead_label = QLabel("🎨 像素创作")
        bead_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {self._c('mid')}; "
            f"border-right: 1px solid {self._c('border')}; padding-right: 8px;"
        )
        bead_card_layout.addWidget(bead_label)
        bead_editor_btn = QPushButton("✏️ 拼豆编辑器")
        bead_editor_btn.setObjectName("secondaryBtn")
        bead_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bead_editor_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._c('card')};
                border: 1px solid {self._c('border')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                color: {self._c('text')};
            }}
            QPushButton:hover {{
                border-color: {self._c('accent')};
                background: {self._c('hover_bg')};
            }}
        """)
        bead_editor_btn.clicked.connect(self._on_open_bead_editor)
        bead_card_layout.addWidget(bead_editor_btn)
        bead_import_btn = QPushButton("📥 拼豆图导入")
        bead_import_btn.setObjectName("secondaryBtn")
        bead_import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bead_import_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._c('card')};
                border: 1px solid {self._c('border')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                color: {self._c('text')};
            }}
            QPushButton:hover {{
                border-color: {self._c('accent')};
                background: {self._c('hover_bg')};
            }}
        """)
        bead_import_btn.clicked.connect(self._on_import_bead_image)
        bead_card_layout.addWidget(bead_import_btn)
        bead_card_layout.addStretch()
        pet_left.addWidget(bead_card)

        self._fav_label = QLabel("收藏夹 (0/10)")
        self._fav_label.setObjectName("sectionLabel")
        pet_left.addWidget(self._fav_label)

        self._fav_scroll = QScrollArea()
        self._fav_scroll.setObjectName("favGallery")
        self._fav_scroll.setFixedHeight(82)
        self._fav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fav_scroll.setWidgetResizable(True)
        self._fav_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 6px; background: transparent; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)
        self._fav_container = QWidget()
        self._fav_container.setStyleSheet("background: transparent;")
        self._fav_layout = QHBoxLayout(self._fav_container)
        self._fav_layout.setContentsMargins(0, 0, 0, 0)
        self._fav_layout.setSpacing(6)
        self._fav_layout.addStretch()
        self._fav_scroll.setWidget(self._fav_container)

        self._fav_thumb_group = QButtonGroup(self)
        self._fav_thumb_group.setExclusive(True)
        self._bead_thumb_group = QButtonGroup(self)
        self._bead_thumb_group.setExclusive(True)

        self._fav_add_btn = QPushButton("+")
        self._fav_add_btn.setFixedSize(48, 48)
        self._fav_add_btn.setStyleSheet(f"""
            QPushButton {{
                border: 2px dashed {self._c('border')};
                border-radius: 8px;
                background: {self._c('input_bg')};
                color: {self._c('text2')};
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {self._c('accent')};
                background: {self._c('hover_bg')};
                color: {self._c('accent')};
            }}
        """)
        self._fav_add_btn.setToolTip("收藏当前宠物")
        self._fav_add_btn.clicked.connect(self._on_add_favorite)
        self._fav_layout.addWidget(self._fav_add_btn)
        self._fav_placeholder = QLabel("还没有收藏的宠物")
        self._fav_placeholder.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px; padding: 18px 10px;")
        self._fav_layout.addWidget(self._fav_placeholder)
        pet_left.addWidget(self._fav_scroll)

        pet_layout.addLayout(pet_left)
        pet_layout.addSpacing(24)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet(f"background: {self._c('border')}; max-width: 1px;")
        pet_layout.addWidget(divider)
        pet_layout.addSpacing(24)

        pet_right = QVBoxLayout()
        pet_right.setSpacing(12)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)
        self._show_btn = QPushButton("显示 / 隐藏")
        self._show_btn.setObjectName("actionBtn")
        self._show_btn.setEnabled(False)
        self._show_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._show_btn.clicked.connect(self._on_toggle_visibility)
        ctrl_row.addWidget(self._show_btn)
        self._reset_btn = QPushButton("恢复 ToYu")
        self._reset_btn.setObjectName("actionBtn")
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_btn.clicked.connect(self._on_reset)
        ctrl_row.addWidget(self._reset_btn)
        self._screen_btn = QPushButton("📊 屏幕统计")
        self._screen_btn.setObjectName("actionBtn")
        self._screen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._screen_btn.setCheckable(True)
        self._screen_btn.setChecked(True)
        self._screen_btn.clicked.connect(self._on_toggle_screen_tracker)
        ctrl_row.addWidget(self._screen_btn)
        ctrl_row.addStretch()
        pet_right.addLayout(ctrl_row)

        self._showcase_card = self._make_showcase_card()
        self._showcase_card_ref = self._showcase_card
        pet_right.addWidget(self._showcase_card)

        house_row = QHBoxLayout()
        house_row.setSpacing(10)

        house_thumb = QLabel()
        house_pix = QPixmap(get_house_path())
        if not house_pix.isNull():
            house_thumb.setPixmap(house_pix.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))
        house_thumb.setFixedSize(52, 52)
        house_thumb.setStyleSheet("background: transparent; border: none;")
        house_row.addWidget(house_thumb)

        house_text_layout = QVBoxLayout()
        house_text_layout.setSpacing(2)
        house_title = QLabel("宠物小屋")
        house_title.setStyleSheet(f"color: {self._c('mid')}; font-size: 11px; font-weight: bold; background: transparent;")
        house_text_layout.addWidget(house_title)

        self._house_check = QCheckBox("启用")
        self._house_check.setChecked(self.settings.house_enabled)
        self._house_check.setToolTip("为宠物提供一间可以进出的小房子")
        self._house_check.toggled.connect(self._on_house_toggle)
        self._house_check.setStyleSheet(f"color: {self._c('text')}; font-size: 11px; font-weight: bold; background: transparent;")
        house_text_layout.addWidget(self._house_check)
        house_row.addLayout(house_text_layout)
        house_row.addStretch()

        pet_right.addLayout(house_row)

        status_card = self._make_card("🐾 宠物状态")
        status_card_layout = status_card.layout()
        status_card_layout.setSpacing(8)

        action_row = QHBoxLayout()
        action_label = QLabel("当前动作:")
        action_label.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        action_row.addWidget(action_label)
        self._action_status = QLabel("待机中")
        self._action_status.setStyleSheet(f"color: {self._c('text')}; font-size: 11px; font-weight: bold; background: transparent;")
        action_row.addWidget(self._action_status)
        action_row.addStretch()
        status_card_layout.addLayout(action_row)

        mood_row = QHBoxLayout()
        mood_label = QLabel("心情:")
        mood_label.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        mood_row.addWidget(mood_label)
        self._mood_status = QLabel("😊 开心")
        self._mood_status.setStyleSheet(f"color: {self._c('text')}; font-size: 11px; font-weight: bold; background: transparent;")
        mood_row.addWidget(self._mood_status)
        mood_row.addStretch()
        status_card_layout.addLayout(mood_row)

        affection_row = QHBoxLayout()
        affection_label = QLabel("好感度:")
        affection_label.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        affection_row.addWidget(affection_label)
        self._affection_status = QLabel("0/100")
        self._affection_status.setStyleSheet(f"color: {self._c('accent')}; font-size: 11px; font-weight: bold; background: transparent;")
        affection_row.addWidget(self._affection_status)
        affection_row.addStretch()
        status_card_layout.addLayout(affection_row)

        pet_right.addWidget(status_card)

        auto_home_card = self._make_card("🏠 自动回家")
        auto_home_layout = auto_home_card.layout()
        auto_home_layout.setSpacing(10)

        auto_home_desc = QLabel("宠物长时间没有互动时,会自己回家休息")
        auto_home_desc.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        auto_home_desc.setWordWrap(True)
        auto_home_layout.addWidget(auto_home_desc)

        timeout_row = QHBoxLayout()
        timeout_row.setSpacing(8)
        timeout_label = QLabel("无互动")
        timeout_label.setStyleSheet(f"color: {self._c('text')}; font-size: 12px; background: transparent;")
        timeout_row.addWidget(timeout_label)

        self._auto_home_spin = QSpinBox()
        self._auto_home_spin.setRange(0, 120)
        self._auto_home_spin.setSuffix(" 分钟")
        self._auto_home_spin.setSpecialValueText("关闭")
        self._auto_home_spin.setValue(self.settings.auto_home_timeout)
        self._auto_home_spin.setFixedWidth(100)
        self._auto_home_spin.setStyleSheet(f"""
            QSpinBox {{
                background: {self._c('card')};
                border: 1px solid {self._c('border')};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                color: {self._c('text')};
            }}
            QSpinBox:focus {{
                border-color: {self._c('accent')};
            }}
        """)
        self._auto_home_spin.valueChanged.connect(self._on_auto_home_changed)
        timeout_row.addWidget(self._auto_home_spin)

        timeout_label2 = QLabel("后自动回家")
        timeout_label2.setStyleSheet(f"color: {self._c('text')}; font-size: 12px; background: transparent;")
        timeout_row.addWidget(timeout_label2)
        timeout_row.addStretch()
        auto_home_layout.addLayout(timeout_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self._auto_home_presets = []
        for mins in [5, 10, 15, 30, 60]:
            btn = QPushButton(f"{mins}分钟")
            btn.setProperty("modeToggle", True)
            btn.setCheckable(True)
            btn.setChecked(self.settings.auto_home_timeout == mins)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {self._c('card')};
                    border: 1px solid {self._c('border')};
                    border-radius: 14px;
                    padding: 2px 12px;
                    font-size: 11px;
                    color: {self._c('text')};
                }}
                QPushButton:checked {{
                    background: {self._c('accent')};
                    color: white;
                    border-color: {self._c('accent')};
                }}
                QPushButton:hover {{
                    border-color: {self._c('accent')};
                }}
            """)
            btn.clicked.connect(lambda checked, m=mins: self._on_auto_home_preset(m))
            btn.setProperty("_mins", mins)
            self._auto_home_presets.append(btn)
            preset_row.addWidget(btn)
        preset_row.addStretch()
        auto_home_layout.addLayout(preset_row)

        pet_right.addWidget(auto_home_card)

        pet_right.addStretch()

        pet_layout.addLayout(pet_right)
        pet_page.setWidget(pet_widget)
        self._page_stack.addWidget(pet_page)

        feat_page = QScrollArea()
        feat_page.setWidgetResizable(True)
        feat_page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        feat_page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        feat_page.setFrameShape(QFrame.Shape.NoFrame)
        feat_page.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')}; border-radius: 3px; min-height: 20px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        feat_widget = QWidget()
        feat_widget.setStyleSheet("background: transparent;")
        feat_layout = QGridLayout(feat_widget)
        feat_layout.setContentsMargins(20, 16, 20, 14)
        feat_layout.setSpacing(12)

        proc_card = self._make_card("图片处理设置")
        proc_layout = proc_card.layout()
        proc_layout.setSpacing(10)
        thresh, thresh_cap = self._make_slider_row("白色阈值", 150, 250, 200,
            self._on_threshold_change, "数值越高移除的背景白色越多,越低越保留浅色边缘")
        proc_layout.addLayout(thresh)
        proc_layout.addWidget(thresh_cap)
        self._thresh_value_label = thresh.itemAt(2).widget()
        ai_row = QHBoxLayout()
        self._ai_check = QCheckBox("使用 AI 智能抠图")
        self._ai_check.setToolTip("首次使用需下载模型 (~100MB),效果更好")
        self._ai_check.toggled.connect(self._on_ai_toggle)
        ai_row.addWidget(self._ai_check)
        ai_row.addStretch()
        proc_layout.addLayout(ai_row)
        feat_layout.addWidget(proc_card, 0, 0)  # 左上

        behav_card = self._make_card("宠物行为")
        behav_layout = behav_card.layout()
        behav_layout.setSpacing(10)
        speed, speed_cap = self._make_slider_row("行走速度", 1, 10, 3,
            self._on_speed_change, "数值越大宠物移动越快,1=缓慢 10=疾跑")
        self._speed_slider = speed.itemAt(1).widget()
        self._speed_label = speed.itemAt(2).widget()
        self._speed_label.setText("3")
        behav_layout.addLayout(speed)
        behav_layout.addWidget(speed_cap)
        size, size_cap = self._make_slider_row("宠物大小", 50, 200, 100,
            self._on_size_change, "调整宠物在桌面上的显示尺寸,支持 50%~200% 缩放")
        size.itemAt(2).widget().setText("100%")
        self._size_value_label = size.itemAt(2).widget()
        behav_layout.addLayout(size)
        behav_layout.addWidget(size_cap)

        self._autostart_check = QCheckBox("开机自启")
        self._autostart_check.setChecked(self.settings.auto_start)
        self._autostart_check.toggled.connect(self._on_auto_start_toggle)
        behav_layout.addWidget(self._autostart_check)

        mode_label = QLabel("互动模式")
        mode_label.setObjectName("cardTitle")
        behav_layout.addWidget(mode_label)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self._mode_btns = {}
        for text, val in [("自由漫步", "free"), ("跟随鼠标", "follow"), ("原地待机", "stay")]:
            btn = QPushButton(text)
            btn.setProperty("modeToggle", True)
            btn.setFixedHeight(34)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, v=val: self._on_mode_change_val(v))
            mode_row.addWidget(btn)
            self._mode_btns[val] = btn
        mode_row.addStretch()
        behav_layout.addLayout(mode_row)

        saved_mode = self.settings.interaction_mode
        if saved_mode in self._mode_btns:
            self._on_mode_change_val(saved_mode)
        else:
            self._on_mode_change_val("free")

        self._ontop_check = QCheckBox("宠物始终置顶")
        self._ontop_check.setChecked(True)
        behav_layout.addWidget(self._ontop_check)

        self._time_aware_check = QCheckBox("启用时间感知 (随早晚改变行为)")
        self._time_aware_check.setChecked(self.settings.time_awareness_enabled)
        self._time_aware_check.toggled.connect(self._on_time_awareness_toggle)
        self._time_aware_check.setToolTip(
            "夜晚22-6点宠物变暗、行动缓慢;清晨6-10点更活跃"
        )
        behav_layout.addWidget(self._time_aware_check)
        feat_layout.addWidget(behav_card, 0, 1)  # 右上

        pomodoro_card = self._make_card("番茄钟 · 休息提醒")
        pomodoro_layout = pomodoro_card.layout()
        pomodoro_layout.setSpacing(10)
        self._pomodoro_enable_check = QCheckBox("开启定时休息提醒")
        self._pomodoro_enable_check.setChecked(self.settings.pomodoro_enabled)
        self._pomodoro_enable_check.toggled.connect(self._on_pomodoro_toggle)
        pomodoro_layout.addWidget(self._pomodoro_enable_check)
        interval_label = QLabel("提醒间隔:")
        interval_label.setStyleSheet(f"color: {self._c('text')}; font-size: 12px;")
        pomodoro_layout.addWidget(interval_label)
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        self._pomodoro_presets = {}
        for mins in [15, 25, 35, 45, 60]:
            btn = QPushButton(f"{mins}分钟")
            btn.setProperty("modeToggle", True)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, m=mins: self._on_pomodoro_preset(m))
            preset_row.addWidget(btn)
            self._pomodoro_presets[mins] = btn
        preset_row.addStretch()
        pomodoro_layout.addLayout(preset_row)
        custom_row = QHBoxLayout()
        custom_row.setSpacing(8)
        custom_label = QLabel("自定义:")
        custom_label.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px;")
        custom_row.addWidget(custom_label)
        self._pomodoro_spin = QSpinBox()
        self._pomodoro_spin.setRange(5, 120)
        self._pomodoro_spin.setValue(self.settings.pomodoro_interval)
        self._pomodoro_spin.setSuffix(" 分钟")
        self._pomodoro_spin.valueChanged.connect(self._on_pomodoro_custom_interval)
        custom_row.addWidget(self._pomodoro_spin)
        custom_row.addStretch()
        pomodoro_layout.addLayout(custom_row)
        self._update_pomodoro_preset_highlight()
        self._pomodoro_status = QLabel("")
        self._pomodoro_status.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px;")
        pomodoro_layout.addWidget(self._pomodoro_status)
        self._update_pomodoro_status()
        feat_layout.addWidget(pomodoro_card, 1, 0, 1, 2)  # 底部跨两列

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        feat_layout.addWidget(spacer, 2, 0, 1, 2)
        feat_page.setWidget(feat_widget)
        self._page_stack.addWidget(feat_page)

        tools_page = QWidget()
        tools_page.setStyleSheet("background: transparent;")
        tools_main_layout = QVBoxLayout(tools_page)
        tools_main_layout.setContentsMargins(0, 0, 0, 0)
        tools_main_layout.setSpacing(0)

        tools_tab_bar = QWidget()
        tools_tab_bar.setFixedHeight(36)
        tools_tab_layout = QHBoxLayout(tools_tab_bar)
        tools_tab_layout.setContentsMargins(20, 0, 20, 0)
        tools_tab_layout.setSpacing(4)
        self._tools_tab_btns = {}
        self._tools_stack = QStackedWidget()
        self._tools_stack.setStyleSheet("QStackedWidget { background: transparent; }")

        sub_btn_style = """
            QPushButton {
                color: #8B6914; background: transparent; border: none;
                padding: 6px 16px; font-size: 12px; border-radius: 6px;
            }
            QPushButton:hover { background: rgba(255,107,71,0.1); }
            QPushButton:checked {
                color: #FF6B47; background: rgba(255,107,71,0.12);
                font-weight: bold;
            }
        """
        for idx, (name, icon) in enumerate([("效率工具", "📋"), ("数据面板", "📊")]):
            btn = QPushButton(f"{icon} {name}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(sub_btn_style)
            btn.clicked.connect(lambda checked, i=idx: self._switch_tools_page(i))
            tools_tab_layout.addWidget(btn)
            self._tools_tab_btns[idx] = btn
        tools_tab_layout.addStretch()
        tools_main_layout.addWidget(tools_tab_bar)

        tools_p1 = QWidget()
        tools_p1.setStyleSheet("background: transparent;")
        tools_layout = QHBoxLayout(tools_p1)
        tools_layout.setSpacing(16)
        tools_layout.setContentsMargins(20, 16, 20, 14)

        todo_card = self._make_card("📝 待办事项")
        todo_card_layout = todo_card.layout()
        todo_card_layout.setSpacing(8)

        from ui.todo_widget import TodoWidget
        self._todo_widget = TodoWidget()
        self._todo_widget.task_completed.connect(self._on_task_completed)
        self._todo_widget.task_added.connect(self._on_task_added)
        todo_card_layout.addWidget(self._todo_widget)
        tools_layout.addWidget(todo_card, 1)  # stretch=1

        timer_card = self._make_card("⏱ 倒计时器")
        timer_card_layout = timer_card.layout()
        timer_card_layout.setSpacing(8)

        from ui.timer_widget import TimerWidget
        self._timer_widget = TimerWidget()
        self._timer_widget.timer_complete.connect(self._on_timer_complete)
        timer_card_layout.addWidget(self._timer_widget)
        tools_layout.addWidget(timer_card, 1)  # stretch=1

        self._tools_stack.addWidget(tools_p1)

        tools_p2 = QWidget()
        tools_p2.setStyleSheet("background: transparent;")
        tools_p2_layout = QHBoxLayout(tools_p2)
        tools_p2_layout.setSpacing(12)
        tools_p2_layout.setContentsMargins(20, 16, 20, 14)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        left_top_card = self._make_card("📈 统计分析")
        left_top_layout = left_top_card.layout()
        left_top_layout.setSpacing(6)

        stat_tabs = QHBoxLayout()
        stat_tabs.setSpacing(6)
        self._stat_tab_study = QPushButton("学习统计")
        self._stat_tab_screen = QPushButton("屏幕时间")
        for btn in (self._stat_tab_study, self._stat_tab_screen):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setStyleSheet(
                "QPushButton { background: #F0E6D6; border: none; border-radius: 6px;"
                " font-size: 11px; padding: 0 10px; }"
                "QPushButton:checked { background: #C49A3C; color: white; }"
            )
            stat_tabs.addWidget(btn)
        self._stat_tab_study.setChecked(True)
        self._stat_tab_study.clicked.connect(lambda: self._switch_stat_tab(0))
        self._stat_tab_screen.clicked.connect(lambda: self._switch_stat_tab(1))
        stat_tabs.addStretch()
        left_top_layout.addLayout(stat_tabs)

        self._stat_stack = QStackedWidget()
        left_top_layout.addWidget(self._stat_stack, 1)

        charts_widget = QWidget()
        charts_widget.setStyleSheet("background: transparent;")
        charts_row = QHBoxLayout(charts_widget)
        charts_row.setSpacing(8)
        charts_row.setContentsMargins(0, 0, 0, 0)
        self._pie_label = _ScaledLabel("点击日历查看统计")
        self._pie_label.setStyleSheet(f"color: {self._c('text2')}; font-size: 12px;")
        charts_row.addWidget(self._pie_label, 1)
        self._bar_label = _ScaledLabel("")
        self._bar_label.setStyleSheet(f"color: {self._c('text2')}; font-size: 12px;")
        charts_row.addWidget(self._bar_label, 1)
        self._stat_stack.addWidget(charts_widget)

        screen_widget = QWidget()
        screen_widget.setStyleSheet("background: transparent;")
        screen_layout = QVBoxLayout(screen_widget)
        screen_layout.setContentsMargins(0, 0, 0, 0)
        screen_layout.setSpacing(4)
        self._screen_time_list = QScrollArea()
        self._screen_time_list.setWidgetResizable(True)
        self._screen_time_list.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #E8D5C0; border-radius: 2px; }"
        )
        screen_layout.addWidget(self._screen_time_list)
        self._stat_stack.addWidget(screen_widget)

        left_col.addWidget(left_top_card, 1)  # 1/4

        left_bot_card = self._make_card("📋 日期已做")
        left_bot_layout = left_bot_card.layout()
        left_bot_layout.setSpacing(8)

        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 4px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #E8D5C0; border-radius: 2px; }"
        )
        init_container = QWidget()
        init_container.setStyleSheet("background: transparent;")
        init_layout = QVBoxLayout(init_container)
        init_layout.setContentsMargins(0, 0, 0, 0)
        init_layout.setSpacing(4)
        init_empty = QLabel("点击日历中的日期查看完成记录")
        init_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        init_empty.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 12px; padding: 20px;"
        )
        init_layout.addWidget(init_empty)
        init_layout.addStretch()
        self._history_scroll.setWidget(init_container)
        left_bot_layout.addWidget(self._history_scroll)

        left_col.addWidget(left_bot_card, 1)  # 1/4

        tools_p2_layout.addLayout(left_col, 1)  # left half = 1/2

        right_card = self._make_card("📅 日历")
        right_card_layout = right_card.layout()
        right_card_layout.setSpacing(8)

        from ui.calendar_widget import CuteCalendar
        self._calendar = CuteCalendar()
        self._calendar.date_selected.connect(self._on_calendar_date_selected)
        right_card_layout.addWidget(self._calendar)

        tools_p2_layout.addWidget(right_card, 1)  # right half = 1/2

        self._tools_stack.addWidget(tools_p2)

        self._tools_tab_btns[0].setChecked(True)
        tools_main_layout.addWidget(self._tools_stack, 1)

        self._page_stack.addWidget(tools_page)

        ai_page = QWidget()
        ai_page.setStyleSheet("background: transparent;")
        ai_layout = QVBoxLayout(ai_page)
        ai_layout.setSpacing(12)
        ai_layout.setContentsMargins(20, 16, 20, 14)

        from pet_engine.pet_ai import AIConfig, PERSONALITIES
        self._ai_config = AIConfig()
        self._ai_config.load()

        ai_enable_card = self._make_card("🤖 AI 伴侣")
        ai_enable_layout = ai_enable_card.layout()
        self._ai_enabled_check = QCheckBox("启用 AI 伴侣功能")
        self._ai_enabled_check.setChecked(self._ai_config.enabled)
        self._ai_enabled_check.setStyleSheet(f"color: {self._c('text')}; font-size: 13px;")
        ai_enable_layout.addWidget(self._ai_enabled_check)

        hint = QLabel("双击宠物打开聊天窗口，和你的 AI 伴侣对话")
        hint.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px;")
        ai_enable_layout.addWidget(hint)
        ai_layout.addWidget(ai_enable_card)

        api_card = self._make_card("🔗 API 配置")
        api_layout = api_card.layout()
        api_layout.setSpacing(8)

        api_layout.addWidget(QLabel("API 地址:"))
        self._ai_api_base_input = QLineEdit(self._ai_config.api_base)
        self._ai_api_base_input.setPlaceholderText("https://api.deepseek.com/v1")
        self._ai_api_base_input.setStyleSheet(f"""
            QLineEdit {{
                color: {self._c('text')}; background: {self._c('input_bg')};
                border: 1px solid {self._c('border')}; border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }}
        """)
        api_layout.addWidget(self._ai_api_base_input)

        api_layout.addWidget(QLabel("API Key:"))
        self._ai_api_key_input = QLineEdit(self._ai_config.api_key)
        self._ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_api_key_input.setPlaceholderText("sk-...")
        self._ai_api_key_input.setStyleSheet(f"""
            QLineEdit {{
                color: {self._c('text')}; background: {self._c('input_bg')};
                border: 1px solid {self._c('border')}; border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }}
        """)
        api_layout.addWidget(self._ai_api_key_input)

        api_layout.addWidget(QLabel("模型名称:"))
        self._ai_model_input = QLineEdit(self._ai_config.model)
        self._ai_model_input.setPlaceholderText("deepseek-chat")
        self._ai_model_input.setStyleSheet(f"""
            QLineEdit {{
                color: {self._c('text')}; background: {self._c('input_bg')};
                border: 1px solid {self._c('border')}; border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }}
        """)
        api_layout.addWidget(self._ai_model_input)

        ai_layout.addWidget(api_card)

        persona_card = self._make_card("💕 性格设置")
        persona_layout = persona_card.layout()
        persona_layout.setSpacing(8)

        persona_layout.addWidget(QLabel("宠物名字:"))
        self._ai_name_input = QLineEdit(self._ai_config.name)
        self._ai_name_input.setStyleSheet(f"""
            QLineEdit {{
                color: {self._c('text')}; background: {self._c('input_bg')};
                border: 1px solid {self._c('border')}; border-radius: 6px;
                padding: 6px 10px; font-size: 12px;
            }}
        """)
        persona_layout.addWidget(self._ai_name_input)

        persona_layout.addWidget(QLabel("性格:"))
        self._ai_personality_combo = QComboBox()
        for name, desc in PERSONALITIES.items():
            self._ai_personality_combo.addItem(f"{name} — {desc[:15]}...", name)
        current_idx = list(PERSONALITIES.keys()).index(self._ai_config.personality)
        if current_idx >= 0:
            self._ai_personality_combo.setCurrentIndex(current_idx)
        self._ai_personality_combo.setStyleSheet(
            f"QComboBox {{ color: {self._c('text')}; background: {self._c('input_bg')}; border: 1px solid {self._c('border')}; border-radius: 6px; padding: 6px 10px; font-size: 12px; }}"
            f"QComboBox QAbstractItemView {{ color: {self._c('text')}; background: {self._c('input_bg')}; border: 1px solid {self._c('border')}; selection-background-color: {self._c('accent')}; selection-color: white; }}"
        )
        persona_layout.addWidget(self._ai_personality_combo)

        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("创造力:"))
        self._ai_temp_spin = QDoubleSpinBox()
        self._ai_temp_spin.setRange(0.0, 2.0)
        self._ai_temp_spin.setSingleStep(0.1)
        self._ai_temp_spin.setValue(self._ai_config.temperature)
        self._ai_temp_spin.setStyleSheet(f"""
            QDoubleSpinBox {{
                color: {self._c('text')}; background: {self._c('input_bg')};
                border: 1px solid {self._c('border')}; border-radius: 6px;
                padding: 4px 8px; font-size: 12px;
            }}
        """)
        temp_row.addWidget(self._ai_temp_spin)
        persona_layout.addLayout(temp_row)

        ai_layout.addWidget(persona_card)

        save_ai_btn = QPushButton("💾 保存 AI 设置")
        save_ai_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._c('accent')};
                color: white;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {self._c('accent_h')};
            }}
        """)
        save_ai_btn.clicked.connect(self._save_ai_settings)
        ai_layout.addWidget(save_ai_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        ai_layout.addStretch()
        self._page_stack.addWidget(ai_page)

        self._page_btns["宠物"].setChecked(True)
        self._page_stack.setCurrentIndex(0)

        root.addWidget(self._page_stack, 1)  # stretch=1 to fill available space

        root.addWidget(self._h_separator())
        status_bar = QWidget()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(36)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(24, 0, 24, 0)
        status_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._status = QLabel("选择图片或直接启动 ToYu")
        self._status.setObjectName("statusText")
        status_layout.addWidget(self._status)

        self._time_period_label = QLabel("")
        self._time_period_label.setObjectName("timePeriodLabel")
        self._time_period_label.setStyleSheet(
            f"font-size: 12px; color: {self._c('accent')}; font-weight: bold;"
            f"background: {self._c('tab_bg')}; border-radius: 4px; padding: 2px 8px; margin-left: 10px;"
        )
        status_layout.addWidget(self._time_period_label)

        status_layout.addStretch()

        affection_bar, affection_bg, affection_fill, affection_value = self._create_affection_bar()
        status_layout.addWidget(affection_bar)
        self._affection_bar = affection_fill
        self._affection_value = affection_value

        pet_status = QLabel("")
        pet_status.setObjectName("petStatus")
        status_layout.addWidget(pet_status)
        self._pet_status = pet_status

        self._affection_label = QLabel("")
        self._affection_label.setObjectName("affectionLabel")
        self._affection_label.setStyleSheet(
            f"font-size: 12px; color: {ACCENT}; font-weight: bold; margin-left: 14px;"
        )
        status_layout.addWidget(self._affection_label)

        root.addWidget(status_bar)

    def _make_card(self, title):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("cardTitle")
        layout.addWidget(label)
        return card

    def _make_slider_row(self, name, min_v, max_v, default, callback, caption=""):
        """Return (row, caption_label) - caption is placed below the row."""
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(name + ":")
        label.setFixedWidth(70)
        row.addWidget(label)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(default)
        if callback:
            slider.valueChanged.connect(callback)
        row.addWidget(slider)
        val = QLabel(str(default))
        val.setFixedWidth(36)
        val.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(val)
        caption_lbl = QLabel(caption)
        caption_lbl.setStyleSheet(f"color: {self._c('text2')}; font-size: 10px; padding-left: 80px;")
        return row, caption_lbl

    def _h_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {self._c('border')}; max-height: 1px;")
        return sep

    def _create_affection_bar(self):
        """创建好感度进度条组件"""
        bar_widget = QWidget()
        bar_widget.setStyleSheet("background: transparent;")
        bar_layout = QHBoxLayout(bar_widget)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(8)

        icon_label = QLabel("❤")
        icon_label.setStyleSheet("font-size: 14px; background: transparent;")
        bar_layout.addWidget(icon_label)

        bar_bg = QWidget()
        bar_bg.setFixedHeight(8)
        bar_bg.setMinimumWidth(100)
        bar_bg.setStyleSheet(f"""
            QWidget {{
                background: {self._c('border')};
                border-radius: 4px;
            }}
        """)

        bar_fill = QWidget(bar_bg)
        bar_fill.setGeometry(0, 0, 0, 8)
        bar_fill.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #C49A3C, stop:1 #D4AE50);
                border-radius: 4px;
            }
        """)

        bar_layout.addWidget(bar_bg)

        value_label = QLabel("0/100")
        value_label.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; background: transparent;")
        bar_layout.addWidget(value_label)

        return bar_widget, bar_bg, bar_fill, value_label

    def _update_affection_display(self, value):
        """更新好感度进度条显示"""
        if hasattr(self, '_affection_bar') and hasattr(self, '_affection_value'):
            bar_width = min(value, 100)
            self._affection_bar.setFixedWidth(bar_width)
            self._affection_value.setText(f"{value}/100")

            if value >= 100:
                color = "#FF69B4"  # 粉色 - 满好感
            elif value >= 50:
                color = "#C49A3C"  # 金色 - 高好感
            elif value >= 10:
                color = "#D4AE50"  # 浅金色 - 中好感
            else:
                color = "#BCAAA4"  # 灰色 - 低好感

            self._affection_bar.setStyleSheet(f"""
                QWidget {{
                    background: {color};
                    border-radius: 4px;
                }}
            """)

    def _init_tray(self):
        self._tray = TrayIcon(None, self.settings)
        self._tray._on_change_pet = self._on_select_image
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()

    def _on_select_image(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, "选择宠物图片",
                os.path.expanduser("~/Pictures"),
                "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)"
            )
        if path:
            self._input_path = path
            self._bead_import_mode = False  # Reset bead import flag
            pix = QPixmap(path)
            if not pix.isNull():
                self._drop_zone.show_pixmap(pix)
            self._start_btn.setEnabled(True)
            self._status.setText(f"已选择: {os.path.basename(path)}")
            self._start_btn.setText("启动宠物")

    def _on_threshold_change(self, value):
        self._thresh_value_label.setText(str(value))

    def _on_ai_toggle(self, checked):
        pass  # Handled at processing time

    def _on_size_change(self, value):
        self._size_value_label.setText(f"{value}%")
        scale = value / 100.0
        self.settings.animation_scale = scale
        if self._pet:
            self._pet.set_scale(scale)

    def _on_speed_change(self, value):
        self._speed_label.setText(str(value))

    def _on_auto_start_toggle(self, checked):
        self.settings.auto_start = checked
        link = os.path.join(
            os.getenv("APPDATA", ""),
            "Microsoft\\Windows\\Start Menu\\Programs\\Startup",
            "ToYu.lnk"
        )
        if checked:
            exe = sys.executable
            ps = (
                f'"$s=(New-Object -COM WScript.Shell).CreateShortcut(\'{link}\');'
                f'$s.TargetPath=\'{exe}\';$s.Save()"'
            )
            subprocess.Popen(["powershell", "-Command", ps],
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            try:
                if os.path.exists(link):
                    os.remove(link)
            except Exception:
                pass

    MAX_FAVORITES = 10
    MAX_BEAD_CREATIONS = 20

    def _seed_default_favorites(self):
        """Ensure default pets are always in favorites."""
        favs = self.settings.favorites
        defaults = [
            (get_default_pet_path(), "ToYu"),
            (get_tv_pet_path(), "TV小电视"),
        ]
        changed = False
        for path, name in defaults:
            if os.path.exists(path) and not any(f["path"] == path for f in favs):
                favs.insert(0, {"path": path, "name": name})
                changed = True
        if changed:
            self.settings.favorites = favs

    def _cleanup_favorites(self):
        """Remove stale temp paths, duplicates, and enforce MAX_FAVORITES."""
        favs = self.settings.favorites
        if not favs:
            return

        seen = set()
        cleaned = []
        for f in favs:
            path = f.get("path", "")
            if "_MEI" in path:
                continue
            if not os.path.exists(path):
                continue
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen:
                continue
            seen.add(norm)
            cleaned.append(f)

        if len(cleaned) > self.MAX_FAVORITES:
            cleaned = cleaned[:self.MAX_FAVORITES]

        if len(cleaned) != len(favs):
            self.settings.favorites = cleaned

    def _refresh_favorites(self):
        for btn in list(self._fav_thumb_group.buttons()):
            self._fav_thumb_group.removeButton(btn)
            pw = btn.parent()
            if pw and pw is not self._fav_container:
                idx = self._fav_layout.indexOf(pw)
                if idx >= 0:
                    self._fav_layout.takeAt(idx)
                    pw.deleteLater()
            else:
                idx = self._fav_layout.indexOf(btn)
                if idx >= 0:
                    self._fav_layout.takeAt(idx)
                    btn.deleteLater()

        for i in reversed(range(self._fav_layout.count())):
            item = self._fav_layout.itemAt(i)
            if item.widget() is None and item.spacerItem() is not None:
                self._fav_layout.takeAt(i)

        favs = self.settings.favorites
        has_favs = bool(favs)
        self._fav_placeholder.setVisible(not has_favs)
        self._fav_label.setText(f"收藏夹 ({len(favs)}/{self.MAX_FAVORITES})")
        current_path = self.settings.pet_image_path

        if has_favs:
            insert_at = 0
            for item in favs:
                p = item["path"] if isinstance(item, dict) else item
                name = item.get("name", "") if isinstance(item, dict) else ""
                if not os.path.exists(p):
                    continue
                pix = QPixmap(p)
                if pix.isNull():
                    continue
                scaled = pix.scaled(42, 42, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)

                wrapper = QWidget()
                wrapper.setStyleSheet("background: transparent;")
                wrap_layout = QVBoxLayout(wrapper)
                wrap_layout.setContentsMargins(0, 0, 0, 0)
                wrap_layout.setSpacing(2)

                btn = QPushButton()
                btn.setProperty("petThumb", True)
                btn.setFixedSize(48, 48)
                btn.setIcon(QIcon(scaled))
                btn.setIconSize(QSize(42, 42))
                btn.setCheckable(True)
                btn.setToolTip(f"{name}\n{p}\n左键切换 | 右键菜单")
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.clicked.connect(lambda checked, p=p: self._on_favorite_thumb_click(p))
                btn.customContextMenuRequested.connect(
                    lambda pos, p=p, b=btn: self._on_fav_thumb_context_menu(pos, p, b))
                self._fav_thumb_group.addButton(btn)
                wrap_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

                name_lbl = QLabel(name)
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_lbl.setFixedWidth(68)
                name_lbl.setStyleSheet(
                    f"color: {self._c('name_fg')}; font-size: 10px; "
                    "font-weight: bold; background: transparent;"
                )
                name_lbl.setWordWrap(False)
                wrap_layout.addWidget(name_lbl)

                self._fav_layout.insertWidget(insert_at, wrapper)
                insert_at += 1
                if p == current_path:
                    btn.setChecked(True)

        for w in (self._fav_add_btn, self._fav_placeholder):
            if self._fav_layout.indexOf(w) == -1:
                self._fav_layout.addWidget(w)
        has_stretch = False
        for i in range(self._fav_layout.count()):
            if self._fav_layout.itemAt(i).spacerItem() is not None:
                has_stretch = True
                break
        if not has_stretch:
            add_idx = self._fav_layout.indexOf(self._fav_add_btn)
            if add_idx >= 0:
                self._fav_layout.insertStretch(add_idx)
            else:
                self._fav_layout.addStretch()

        self._fav_scroll.setFixedHeight(72)

    def _on_favorite_thumb_click(self, path):
        if path and os.path.exists(path) and self._pet:
            self._pet.set_pet_image(path)
            self._input_path = path
            self.settings.pet_image_path = path
            pix = QPixmap(path)
            if not pix.isNull():
                self._drop_zone.show_pixmap(pix)
            self._status.setText(f"已切换: {os.path.basename(path)}")
            for btn in self._fav_thumb_group.buttons():
                btn.setChecked(False)
            sender = self.sender()
            if sender:
                sender.setChecked(True)

    def _on_fav_thumb_context_menu(self, pos, path, btn):
        menu = QMenu(self)
        favs = self.settings.favorites
        item = next((f for f in favs if f["path"] == path), None)
        current_name = item["name"] if item else os.path.basename(path)

        rename_action = QAction("修改名字", menu)
        rename_action.triggered.connect(lambda: self._on_rename_favorite(path))
        menu.addAction(rename_action)

        menu.addSeparator()

        remove_action = QAction("移除收藏", menu)
        remove_action.triggered.connect(lambda: self._on_remove_favorite(path))
        menu.addAction(remove_action)

        menu.exec(btn.mapToGlobal(pos))
        menu.deleteLater()

    def _on_rename_favorite(self, path):
        from PyQt6.QtWidgets import QInputDialog
        favs = self.settings.favorites
        item = next((f for f in favs if f["path"] == path), None)
        if item is None:
            return
        old_name = item.get("name", "")
        new_name, ok = QInputDialog.getText(
            self, "修改名字", "为新宠物取个名字吧:", text=old_name
        )
        if ok and new_name.strip():
            item["name"] = new_name.strip()
            self.settings.favorites = favs
            self._refresh_favorites()
            self._status.setText(f"已改名: {new_name.strip()}")

    def _on_remove_favorite(self, path):
        favs = self.settings.favorites
        favs = [f for f in favs if f["path"] != path]
        self.settings.favorites = favs
        self._refresh_favorites()
        self._status.setText(f"已移除: {os.path.basename(path)}")

    def _on_add_favorite(self):
        if not self._input_path or not os.path.exists(self._input_path):
            QMessageBox.information(self, "提示", "请先启动一个宠物!")
            return
        favs = self.settings.favorites
        if any(f["path"] == self._input_path for f in favs):
            QMessageBox.information(self, "提示", "已在收藏夹中 :)")
            return
        if len(favs) >= self.MAX_FAVORITES:
            QMessageBox.information(self, "提示",
                f"收藏夹已满!最多 {self.MAX_FAVORITES} 只宠物\n请先移除一些再添加")
            return
        name = self.settings._path_to_name(self._input_path)
        favs.append({"path": self._input_path, "name": name})
        self.settings.favorites = favs
        self._refresh_favorites()
        self._status.setText(f"已收藏: {name}")

    def _make_showcase_card(self):
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(130)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        self._showcase_label = QLabel("作品集 (0/20)")
        self._showcase_label.setObjectName("cardTitle")
        layout.addWidget(self._showcase_label)

        self._showcase_scroll = QScrollArea()
        self._showcase_scroll.setObjectName("showcaseGallery")
        self._showcase_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._showcase_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._showcase_scroll.setWidgetResizable(True)

        self._showcase_container = QWidget()
        self._showcase_container.setStyleSheet("background: transparent;")
        self._showcase_layout = QHBoxLayout(self._showcase_container)
        self._showcase_layout.setContentsMargins(0, 0, 0, 0)
        self._showcase_layout.setSpacing(6)
        self._showcase_layout.addStretch()

        self._showcase_add_btn = QPushButton("+")
        self._showcase_add_btn.setFixedSize(64, 64)
        self._showcase_add_btn.setStyleSheet(f"""
            QPushButton {{
                border: 2px dashed {self._c('border')};
                border-radius: 8px;
                background: {self._c('input_bg')};
                color: {self._c('text2')};
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {self._c('accent')};
                background: {self._c('hover_bg')};
                color: {self._c('accent')};
            }}
        """)
        self._showcase_add_btn.setToolTip("打开拼豆编辑器")
        self._showcase_add_btn.clicked.connect(self._on_open_bead_editor)
        self._showcase_layout.addWidget(self._showcase_add_btn)

        self._showcase_placeholder = QLabel("还没有作品,打开拼豆编辑器开始创作吧!")
        self._showcase_placeholder.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; padding: 18px 10px;"
        )
        self._showcase_layout.addWidget(self._showcase_placeholder)

        self._showcase_scroll.setWidget(self._showcase_container)
        layout.addWidget(self._showcase_scroll)
        return card

    def _refresh_bead_creations(self):
        for btn in list(self._bead_thumb_group.buttons()):
            self._bead_thumb_group.removeButton(btn)
            pw = btn.parent()
            if pw and pw is not self._showcase_container:
                idx = self._showcase_layout.indexOf(pw)
                if idx >= 0:
                    self._showcase_layout.takeAt(idx)
                    pw.deleteLater()
            else:
                idx = self._showcase_layout.indexOf(btn)
                if idx >= 0:
                    self._showcase_layout.takeAt(idx)
                    btn.deleteLater()

        for i in reversed(range(self._showcase_layout.count())):
            item = self._showcase_layout.itemAt(i)
            if item.widget() is None and item.spacerItem() is not None:
                self._showcase_layout.takeAt(i)

        creations = self.settings.bead_creations
        valid = []
        for c in creations:
            png = c.get("png_path", "")
            if png and os.path.exists(png):
                valid.append(c)
        if len(valid) != len(creations):
            self.settings.bead_creations = valid
            creations = valid

        has_items = bool(creations)
        self._showcase_placeholder.setVisible(not has_items)
        self._showcase_label.setText(f"作品集 ({len(creations)}/{self.MAX_BEAD_CREATIONS})")
        current_path = self.settings.pet_image_path

        if has_items:
            insert_at = 0
            for c in creations:
                png_path = c.get("png_path", "")
                if not png_path or not os.path.exists(png_path):
                    continue
                pix = QPixmap(png_path)
                if pix.isNull():
                    continue
                scaled = pix.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)

                wrapper = QWidget()
                wrapper.setStyleSheet("background: transparent;")
                wrap_layout = QVBoxLayout(wrapper)
                wrap_layout.setContentsMargins(0, 0, 0, 0)
                wrap_layout.setSpacing(2)

                btn = QPushButton()
                btn.setProperty("showcaseThumb", True)
                btn.setFixedSize(64, 64)
                btn.setIcon(QIcon(scaled))
                btn.setIconSize(QSize(56, 56))
                btn.setCheckable(True)
                name = c.get("display_name") or c.get("name", "")
                btn.setToolTip(f"{name}\n右键菜单")
                btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                btn.clicked.connect(
                    lambda checked, c=c: self._on_showcase_thumb_click(c))
                btn.customContextMenuRequested.connect(
                    lambda pos, c=c, b=btn: self._on_showcase_context_menu(pos, c, b))
                self._bead_thumb_group.addButton(btn)
                wrap_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

                name_lbl = QLabel(name)
                name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_lbl.setFixedWidth(68)
                name_lbl.setStyleSheet(
                    f"color: {self._c('name_fg')}; font-size: 10px; "
                    "font-weight: bold; background: transparent;"
                )
                name_lbl.setWordWrap(False)
                wrap_layout.addWidget(name_lbl)

                self._showcase_layout.insertWidget(insert_at, wrapper)
                insert_at += 1
                if png_path == current_path:
                    btn.setChecked(True)

        for w in (self._showcase_add_btn, self._showcase_placeholder):
            if self._showcase_layout.indexOf(w) == -1:
                self._showcase_layout.addWidget(w)
        has_stretch = False
        for i in range(self._showcase_layout.count()):
            if self._showcase_layout.itemAt(i).spacerItem() is not None:
                has_stretch = True
                break
        if not has_stretch:
            add_idx = self._showcase_layout.indexOf(self._showcase_add_btn)
            if add_idx >= 0:
                self._showcase_layout.insertStretch(add_idx)
            else:
                self._showcase_layout.addStretch()

    def _on_showcase_thumb_click(self, creation):
        png_path = creation.get("png_path", "")
        if not png_path or not os.path.exists(png_path):
            return
        self._input_path = png_path
        self.settings.pet_image_path = png_path
        pix = QPixmap(png_path)
        if not pix.isNull():
            self._drop_zone.show_pixmap(pix)
        self._start_btn.setEnabled(True)
        self._status.setText(f"已应用作品: {creation.get('name', '')}")
        if self._pet:
            self._pet.set_pet_image(png_path)
        for btn in self._bead_thumb_group.buttons():
            btn.setChecked(False)
        sender = self.sender()
        if sender:
            sender.setChecked(True)

    def _on_showcase_context_menu(self, pos, creation, btn):
        menu = QMenu(self)
        png_path = creation.get("png_path", "")
        json_path = creation.get("json_path", "")
        name = creation.get("display_name") or creation.get("name", "")

        apply_action = QAction("应用为宠物", menu)
        apply_action.triggered.connect(
            lambda: self._on_showcase_thumb_click(creation))
        menu.addAction(apply_action)

        menu.addSeparator()

        rename_action = QAction("修改名字", menu)
        rename_action.triggered.connect(
            lambda: self._on_rename_bead_creation(creation))
        menu.addAction(rename_action)

        menu.addSeparator()

        export_img_action = QAction("导出图片...", menu)
        export_img_action.triggered.connect(
            lambda: self._on_export_creation_image(png_path))
        menu.addAction(export_img_action)

        export_json_action = QAction("导出拼豆文件...", menu)
        export_json_action.triggered.connect(
            lambda: self._on_export_creation_json(json_path))
        menu.addAction(export_json_action)

        copy_action = QAction("复制图片", menu)
        copy_action.triggered.connect(
            lambda: self._on_copy_creation_image(png_path))
        menu.addAction(copy_action)

        menu.addSeparator()

        delete_action = QAction("删除", menu)
        delete_action.triggered.connect(
            lambda: self._on_delete_bead_creation(creation))
        menu.addAction(delete_action)

        menu.exec(btn.mapToGlobal(pos))
        menu.deleteLater()

    def _on_export_creation_image(self, png_path):
        if not png_path or not os.path.exists(png_path):
            return
        default_name = os.path.basename(png_path)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出图片", default_name, "PNG图片 (*.png)"
        )
        if save_path:
            import shutil
            shutil.copy2(png_path, save_path)
            self._status.setText(f"图片已导出: {os.path.basename(save_path)}")

    def _on_export_creation_json(self, json_path):
        if not json_path or not os.path.exists(json_path):
            return
        default_name = os.path.basename(json_path)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出拼豆文件", default_name, "拼豆文件 (*.json)"
        )
        if save_path:
            import shutil
            shutil.copy2(json_path, save_path)
            self._status.setText(f"拼豆文件已导出: {os.path.basename(save_path)}")

    def _on_copy_creation_image(self, png_path):
        if not png_path or not os.path.exists(png_path):
            return
        pixmap = QPixmap(png_path)
        if not pixmap.isNull():
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(pixmap)
            self._status.setText("图片已复制到剪贴板")

    def _on_rename_bead_creation(self, creation):
        from PyQt6.QtWidgets import QInputDialog
        old_name = creation.get("display_name") or creation.get("name", "")
        new_name, ok = QInputDialog.getText(
            self, "修改名字", "为这个作品取个名字吧:", text=old_name
        )
        if ok and new_name.strip():
            creation["display_name"] = new_name.strip()
            creations = self.settings.bead_creations
            for c in creations:
                if c.get("name") == creation.get("name"):
                    c["display_name"] = new_name.strip()
                    break
            self.settings.bead_creations = creations
            self._refresh_bead_creations()
            self._status.setText(f"已改名: {new_name.strip()}")

    def _on_delete_bead_creation(self, creation):
        name = creation.get("display_name") or creation.get("name", "")
        reply = QMessageBox.question(
            self, "删除作品",
            f"确定要删除作品「{name}」吗?\n\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for p in [creation.get("json_path", ""), creation.get("png_path", "")]:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            creations = self.settings.bead_creations
            creations = [c for c in creations if c.get("name") != name]
            self.settings.bead_creations = creations
            self._refresh_bead_creations()
            self._status.setText(f"已删除: {name}")

    def _switch_tools_page(self, idx):
        """Switch between tools sub-pages."""
        self._tools_stack.setCurrentIndex(idx)
        for i, btn in self._tools_tab_btns.items():
            btn.setChecked(i == idx)

    def _on_page_switch(self, idx, label):
        """Switch page and enforce mutually exclusive tab highlighting."""
        current_widget = self._page_stack.currentWidget()
        new_widget = self._page_stack.widget(idx)

        if current_widget != new_widget:
            new_widget.setGraphicsEffect(None)
            from PyQt6.QtWidgets import QGraphicsOpacityEffect
            from PyQt6.QtCore import QPropertyAnimation

            opacity_effect = QGraphicsOpacityEffect(new_widget)
            opacity_effect.setOpacity(0.0)
            new_widget.setGraphicsEffect(opacity_effect)

            animation = QPropertyAnimation(opacity_effect, b"opacity", self)
            animation.setDuration(200)  # 200ms
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.start()

            animation.finished.connect(lambda: new_widget.setGraphicsEffect(None))

        self._page_stack.setCurrentIndex(idx)
        for lbl, btn in self._page_btns.items():
            btn.setChecked(lbl == label)

    def _on_mode_change_val(self, mode_val):
        self.settings.interaction_mode = mode_val
        for v, btn in self._mode_btns.items():
            btn.setChecked(v == mode_val)
        if self._pet:
            mode_map = {"free": InteractionMode.FREE,
                        "follow": InteractionMode.FOLLOW,
                        "stay": InteractionMode.STAY}
            self._pet.state_machine.set_mode(mode_map.get(mode_val, InteractionMode.FREE))

    def _on_start_pet(self):
        if not self._input_path:
            QMessageBox.warning(self, "提示", "请先选择一张图片!")
            return

        self._status.setText("正在处理...")
        self._start_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            prev_pet_path = self.settings.pet_image_path
            prev_pet = self._pet

            if getattr(self, '_bead_import_mode', False):
                processed_path = self._input_path
            else:
                threshold = self._thresh_value_label.text()
                threshold = int(threshold) if threshold.isdigit() else 200
                use_ai = self._ai_check.isChecked()

                processed_path = process_and_save(
                    self._input_path, self._app_data_dir,
                    threshold=threshold, use_ai=use_ai
                )

            if self._pet:
                self._pet.close()
                self._pet = None
                self._pulse_timer.stop()
            self._close_house()

            scale = self._size_value_label.text().replace("%", "")
            scale = int(scale) / 100.0 if scale.isdigit() else 1.0
            speed_val = int(self._speed_label.text()) if self._speed_label.text().isdigit() else 3
            self.settings.walking_speed_max = float(speed_val)
            self.settings.walking_speed_min = max(0.3, float(speed_val) * 0.3)
            self.settings.pet_image_path = processed_path

            self._pet = PetWindow(self.settings)
            self._pet.start_accessory_brain(self.settings)
            self._pet.set_pet_image(processed_path)
            self._pet.set_scale(scale)

            if self._tray:
                self._tray._pet = self._pet
                self._pet.set_bubble_callbacks(
                    show_hide_cb=self._on_toggle_visibility,
                    change_cb=self._on_select_image,
                    exit_cb=self._on_app_exit,
                    show_main_window_cb=self._on_show_main_window,
                )

            self._pet.show()
            if self.settings.house_enabled:
                self._spawn_house()
            self._show_btn.setEnabled(True)
            self._start_btn.setText("重新启动")
            self._start_btn.setEnabled(True)
            self._status.setText("ToYu 运行中")
            self._pet_status.setText("● 运行中")
            self._pulse_phase = 0.0
            self._pulse_timer.start(50)

            favs = self.settings.favorites
            if not any(f["path"] == processed_path for f in favs):
                if len(favs) < self.MAX_FAVORITES:
                    favs.append({"path": processed_path, "name": self.settings._path_to_name(processed_path)})
                    self.settings.favorites = favs
            self._refresh_favorites()

            mode_val = self.settings.interaction_mode
            mode_map = {"free": InteractionMode.FREE,
                        "follow": InteractionMode.FOLLOW,
                        "stay": InteractionMode.STAY}
            self._pet.state_machine.set_mode(mode_map.get(mode_val, InteractionMode.FREE))
            self._pet.set_time_awareness(self.settings.time_awareness_enabled)

        except Exception as e:
            if prev_pet:
                try:
                    self._pet = prev_pet
                    self._pet.show()
                    self.settings.pet_image_path = prev_pet_path
                except Exception:
                    pass
            QMessageBox.critical(self, "错误", f"处理失败: {str(e)[:200]}\n\n已恢复上次的宠物状态。")
            self._status.setText("处理失败,已恢复")
            self._start_btn.setEnabled(True)

    def _on_toggle_visibility(self):
        if self._pet:
            self._pet.toggle_visibility()
            if self._pet.isVisible():
                self._show_btn.setText("显示 / 隐藏")
            else:
                self._show_btn.setText("显示宠物")

    def _pulse_status(self):
        import math
        self._pulse_phase += 0.12
        t = (math.sin(self._pulse_phase) + 1) / 2  # 0..1
        r = int(107 + t * 20)
        g = int(155 + t * 40)
        b = int(55 + t * 10)
        self._pet_status.setStyleSheet(
            f"color: rgb({r},{g},{b}); font-weight: bold;"
        )
        self._update_time_period_label()

        if self._pet and hasattr(self._pet, 'affection'):
            affection_level = self._pet.affection.level
            self._affection_label.setText(self._pet.affection.display_text)
            self._affection_status.setText(f"{affection_level}/100")
            self._update_affection_display(affection_level)
        else:
            self._affection_label.setText("")
            self._affection_status.setText("0/100")
            self._update_affection_display(0)

    def _on_app_exit(self):
        self._screen_tracker.stop()
        if self._pet:
            self._pet.close()
        QApplication.quit()

    def _on_reset(self):
        default = get_default_pet_path()
        self._input_path = default
        pix = QPixmap(default)
        if not pix.isNull():
            self._drop_zone.show_pixmap(pix)
        self._start_btn.setEnabled(True)
        self._status.setText("已恢复 ToYu - 默认土豆宠物")
        self._pulse_timer.stop()
        self._pet_status.setText("")
        self._pet_status.setStyleSheet("")
        self._affection_label.setText("")
        self._time_period_label.setText("")

    def _on_toggle_screen_tracker(self, checked):
        """Toggle screen time tracker on/off."""
        if checked:
            self._screen_tracker.start()
            self._screen_btn.setText("📊 屏幕统计")
            self._status.setText("屏幕统计已开启")
        else:
            self._screen_tracker.stop()
            self._screen_btn.setText("📊 已关闭")
            self._status.setText("屏幕统计已关闭")

    def _on_show_main_window(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def _on_house_toggle(self, checked):
        self.settings.house_enabled = checked
        if checked:
            if self._pet:
                self._spawn_house()
        else:
            self._close_house()

    def _on_time_awareness_toggle(self, checked):
        self.settings.time_awareness_enabled = checked
        self._update_time_period_label()
        if self._pet:
            self._pet.set_time_awareness(checked)

    def _spawn_house(self):
        if self._house:
            self._house.close()
        self._house = HouseWindow(self.settings, self._pet)
        self._pet.set_house(self._house)
        self._house.set_bubble_callbacks(
            show_hide_cb=self._on_toggle_visibility,
            change_cb=self._on_select_image,
            exit_cb=self._on_app_exit,
            show_main_window_cb=self._on_show_main_window,
        )
        self._house.show()
        if self._pet and self._pet._time_awareness_enabled:
            from datetime import datetime
            hour = datetime.now().hour
            if 22 <= hour or hour < 6:
                self._house.set_night_glow(True)

    def _close_house(self):
        if self._house:
            self._house.close()
            self._house = None

    def _on_pomodoro_toggle(self, checked):
        self.settings.pomodoro_enabled = checked
        if checked:
            import time
            self.settings.pomodoro_last_fired = time.time()
        self._update_pomodoro_status()

    def _on_pomodoro_preset(self, mins):
        self.settings.pomodoro_interval = mins
        self._pomodoro_spin.blockSignals(True)
        self._pomodoro_spin.setValue(mins)
        self._pomodoro_spin.blockSignals(False)
        self._update_pomodoro_preset_highlight()
        self._update_pomodoro_status()

    def _on_pomodoro_custom_interval(self, value):
        self.settings.pomodoro_interval = value
        self._update_pomodoro_preset_highlight()

    def _update_pomodoro_preset_highlight(self):
        current = self.settings.pomodoro_interval
        for mins, btn in self._pomodoro_presets.items():
            btn.setChecked(mins == current)

    def _update_pomodoro_status(self):
        if not self.settings.pomodoro_enabled:
            self._pomodoro_status.setText("番茄钟已关闭")
            return
        interval = self.settings.pomodoro_interval
        self._pomodoro_status.setText(f"每 {interval} 分钟提醒休息")

    def _on_timer_complete(self):
        """Handle timer completion with pet bubble notification."""
        self._status.setText("⏰ 倒计时结束!")
        if self._pet:
            from pet_engine.pet_bubble import PomodoroNotificationBubble
            self._timer_notif = PomodoroNotificationBubble(
                title="⏰  时间到!",
                subtitle="倒计时结束啦~"
            )
            self._timer_notif.show_near(self._pet)
        date = getattr(self, '_selected_chart_date', '')
        if date:
            self._refresh_charts_for_date(date)

    def _on_task_completed(self):
        """Handle task completion - notify pet companion."""
        try:
            if self._pet and hasattr(self._pet, 'on_task_complete'):
                self._pet.on_task_complete()
        except Exception as e:
            print(f"Task completed error: {e}")
        date = getattr(self, '_selected_chart_date', '')
        if date:
            self._refresh_charts_for_date(date)

    def _on_task_added(self):
        """Handle new task - notify pet companion."""
        try:
            if self._pet and hasattr(self._pet, 'companion'):
                message = self._pet.companion.on_task_add()
                self._pet._show_companion_bubble(message)
        except Exception as e:
            print(f"Task added error: {e}")

    def _on_calendar_date_selected(self, date_str):
        """Show completed tasks for the selected calendar date."""
        self._selected_chart_date = date_str
        old = self._history_scroll.takeWidget()
        if old:
            old.deleteLater()

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        import json, os
        history_file = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
        history = {}
        try:
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
        except Exception:
            pass

        tasks = history.get(date_str, [])

        if not tasks:
            empty_lbl = QLabel(f"{date_str} 暂无完成记录")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(
                f"color: {self._c('text2')}; font-size: 12px; padding: 20px;"
            )
            layout.addWidget(empty_lbl)
            layout.addStretch()
            self._history_scroll.setWidget(container)
            return

        CARD_BG = "#FFFFFF"
        BORDER = "#E8D5C0"
        TEXT = "#2C1810"
        TEXT_SEC = "#8B7355"
        DONE_GREEN = "#4CAF50"

        for t in tasks:
            text = t.get("text", "")
            tm = t.get("time", "")
            dur = t.get("duration", 0)

            if dur >= 3600:
                h = dur // 3600
                m = (dur % 3600) // 60
                dur_str = f"{h}h{m}m"
            elif dur >= 60:
                m = dur // 60
                s = dur % 60
                dur_str = f"{m}m{s}s"
            elif dur > 0:
                dur_str = f"{dur}s"
            else:
                dur_str = ""

            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: {CARD_BG}; border: 1px solid {BORDER};"
                f" border-radius: 8px; }}"
            )
            row = QHBoxLayout(card)
            row.setContentsMargins(10, 6, 10, 6)
            row.setSpacing(6)

            check = QLabel("✓")
            check.setStyleSheet(f"color: {DONE_GREEN}; font-size: 14px; font-weight: bold; background: transparent;")
            row.addWidget(check)

            name_lbl = QLabel(text)
            name_lbl.setWordWrap(True)
            name_lbl.setStyleSheet(f"color: {TEXT}; font-size: 12px; background: transparent;")
            row.addWidget(name_lbl, 1)

            parts = []
            if tm:
                parts.append(tm)
            if dur_str:
                parts.append(dur_str)
            time_lbl = QLabel(" · ".join(parts))
            time_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px; background: transparent;")
            row.addWidget(time_lbl)

            layout.addWidget(card)

        layout.addStretch()
        self._history_scroll.setWidget(container)

        try:
            self._update_charts(date_str, tasks)
        except Exception as e:
            print(f"Chart update error: {e}")

    def _switch_stat_tab(self, idx):
        """Switch between study stats and screen time."""
        self._stat_stack.setCurrentIndex(idx)
        self._stat_tab_study.setChecked(idx == 0)
        self._stat_tab_screen.setChecked(idx == 1)
        if idx == 1:
            self._refresh_screen_time()

    def _refresh_screen_time(self):
        """Refresh screen time display."""
        data = self._screen_tracker.get_today_data()

        old = self._screen_time_list.takeWidget()
        if old:
            old.deleteLater()

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        if not data:
            empty = QLabel("暂无屏幕使用记录\n使用软件一段时间后这里会显示统计")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {self._c('text2')}; font-size: 12px; padding: 20px;"
            )
            layout.addWidget(empty)
            layout.addStretch()
            self._screen_time_list.setWidget(container)
            return

        summary = QFrame()
        summary.setStyleSheet(
            "QFrame { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 #FFF8F0, stop:1 #F0E6D6); border-radius: 8px; }"
        )
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(4)

        total_secs = sum(s for _, s in data)
        total_lbl = QLabel(f"🖥️ 今日总使用: {self._fmt_dur(total_secs)}")
        total_lbl.setStyleSheet(
            "color: #2C1810; font-size: 14px; font-weight: bold;"
        )
        summary_layout.addWidget(total_lbl)

        today_s, yesterday_s = self._screen_tracker.get_today_vs_yesterday()
        if yesterday_s > 0:
            diff = today_s - yesterday_s
            pct_change = (diff / yesterday_s) * 100
            if diff > 0:
                cmp_text = f"📈 比昨天多用了 {self._fmt_dur(abs(int(diff)))} ({pct_change:+.0f}%)"
                cmp_clr = "#FF6B6B"
            elif diff < 0:
                cmp_text = f"📉 比昨天少用了 {self._fmt_dur(abs(int(diff)))} ({pct_change:+.0f}%)"
                cmp_clr = "#4ECDC4"
            else:
                cmp_text = "➡️ 和昨天一样"
                cmp_clr = "#8B7355"
            cmp_lbl = QLabel(cmp_text)
            cmp_lbl.setStyleSheet(f"color: {cmp_clr}; font-size: 11px;")
            summary_layout.addWidget(cmp_lbl)

        app_count = len(data)
        count_lbl = QLabel(f"📱 使用了 {app_count} 个应用")
        count_lbl.setStyleSheet("color: #8B7355; font-size: 11px;")
        summary_layout.addWidget(count_lbl)

        layout.addWidget(summary)

        list_title = QLabel("应用排行")
        list_title.setStyleSheet(
            "color: #2C1810; font-size: 12px; font-weight: bold; padding: 4px 0;"
        )
        layout.addWidget(list_title)

        max_secs = data[0][1] if data else 1
        colors = ['#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#FF6B6B',
                  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']

        app_icons = {
            'chrome': '🌐', 'firefox': '🌐', 'edge': '🌐', 'brave': '🌐',
            'code': '💻', 'pycharm': '💻', 'idea': '💻', 'vscode': '💻',
            'explorer': '📁', 'notepad': '📝', 'word': '📄', 'excel': '📊',
            'spotify': '🎵', 'netease': '🎵', 'cloudmusic': '🎵',
            'discord': '💬', 'wechat': '💬', 'telegram': '💬', 'slack': '💬',
            'photoshop': '🎨', 'figma': '🎨', 'paint': '🎨',
            'steam': '🎮', 'epic': '🎮', 'bilibili': '📺', 'youtube': '📺',
        }

        for i, (app, secs) in enumerate(data[:10]):
            pct = secs / total_secs * 100 if total_secs > 0 else 0
            bar_w = int(secs / max_secs * 100)
            clr = colors[i % len(colors)]
            clean_name = app.replace(".exe", "").lower()

            icon = "📱"
            for key, emoji in app_icons.items():
                if key in clean_name:
                    icon = emoji
                    break

            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background: #FFFFFF; border: 1px solid #E8D5C0;"
                f" border-radius: 8px; }}"
                f"QFrame:hover {{ border-color: {clr}; }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 6, 10, 6)
            card_layout.setSpacing(3)

            top_row = QHBoxLayout()
            rank_lbl = QLabel(f"{i+1}")
            rank_lbl.setFixedWidth(20)
            rank_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_lbl.setStyleSheet(
                f"color: {clr}; font-size: 13px; font-weight: bold;"
            )
            top_row.addWidget(rank_lbl)

            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(20)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            top_row.addWidget(icon_lbl)

            name_lbl = QLabel(app.replace(".exe", "").title())
            name_lbl.setStyleSheet(
                "color: #2C1810; font-size: 12px; font-weight: bold;"
            )
            top_row.addWidget(name_lbl, 1)

            pct_lbl = QLabel(f"{self._fmt_dur(secs)}  {pct:.0f}%")
            pct_lbl.setStyleSheet("color: #8B7355; font-size: 11px;")
            top_row.addWidget(pct_lbl)
            card_layout.addLayout(top_row)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(5)
            bar_bg.setStyleSheet(
                "QFrame { background: #F0E6D6; border-radius: 2px; }"
            )
            bar_fill = QFrame(bar_bg)
            bar_fill.setGeometry(0, 0, max(bar_w, 3), 5)
            bar_fill.setStyleSheet(
                f"QFrame {{ background: {clr}; border-radius: 2px; }}"
            )
            card_layout.addWidget(bar_bg)

            layout.addWidget(card)

        layout.addStretch()
        self._screen_time_list.setWidget(container)

    @staticmethod
    @staticmethod
    def _fmt_dur(sec):
        """Format seconds to human readable duration (Chinese)."""
        sec = int(sec)
        if sec >= 3600:
            h = sec // 3600
            m = (sec % 3600) // 60
            return f"{h}小时{m}分钟" if m > 0 else f"{h}小时"
        if sec >= 60:
            m = sec // 60
            s = sec % 60
            return f"{m}分钟{s}秒" if s > 0 else f"{m}分钟"
        return f"{sec}秒"

    def _refresh_charts_for_date(self, date_str):
        """Reload task_history.json and update charts for the given date."""
        import json, os
        history_file = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
        try:
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                tasks = history.get(date_str, [])
            else:
                tasks = []
        except Exception:
            tasks = []
        try:
            self._update_charts(date_str, tasks)
        except Exception as e:
            print(f"Chart refresh error: {e}")

    def _update_charts(self, date_str, tasks):
        """Update pie and bar charts for the selected date."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from PyQt6.QtGui import QPixmap, QImage
        import io, json, os
        from collections import Counter, defaultdict
        from datetime import datetime, timedelta

        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False

        CARD_W = max(self._pie_label.width(), 130)
        pie_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
                      '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']
        bar_color_active = '#4ECDC4'
        bar_color_inactive = '#E8E8E8'

        def fmt(sec):
            if sec >= 3600: return f"{sec//3600}h{(sec%3600)//60}m"
            if sec >= 60: return f"{sec//60}m{sec%60}s"
            return f"{sec}s"

        if not tasks:
            self._pie_label.setText(f"{date_str}\n暂无数据")
            self._bar_label.setText("")
            return

        task_time = defaultdict(int)
        for t in tasks:
            task_time[t.get('text', '未知')] += t.get('duration', 0)
        names = list(task_time.keys())
        times = [task_time[n] for n in names]
        clrs = [pie_colors[i % len(pie_colors)] for i in range(len(names))]

        fig1, ax1 = plt.subplots(figsize=(4.0, 3.2), dpi=300)
        fig1.patch.set_alpha(0)
        ax1.set_facecolor('none')

        if sum(times) > 0:
            wedges, _ = ax1.pie(
                times, labels=None, colors=clrs,
                startangle=90, pctdistance=0.8,
                wedgeprops={'width': 0.35, 'edgecolor': '#FFFFFF', 'linewidth': 2}
            )
            ax1.text(0, 0, fmt(sum(times)), ha='center', va='center',
                     fontsize=18, fontweight='bold', color='#2C1810')
            ax1.legend(
                [f"{n} {fmt(t)}" for n, t in zip(names, times)],
                loc='lower center', bbox_to_anchor=(0.5, -0.12),
                fontsize=10, frameon=False, ncol=min(len(names), 2),
                handlelength=0.8, handletextpad=0.3
            )
        else:
            ax1.text(0.5, 0.5, '暂无', ha='center', va='center', fontsize=14, color='#8B7355')
        ax1.set_title(f'{date_str}', fontsize=12, color='#8B7355', pad=10)
        fig1.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.15)

        buf1 = io.BytesIO()
        fig1.savefig(buf1, format='png', transparent=True)
        plt.close(fig1)
        buf1.seek(0)
        self._pie_label.setRawPixmap(QPixmap.fromImage(QImage.fromData(buf1.getvalue())))

        fig2, ax2 = plt.subplots(figsize=(4.0, 3.2), dpi=300)
        fig2.patch.set_alpha(0)
        ax2.set_facecolor('none')

        today = datetime.strptime(date_str, '%Y-%m-%d')
        days = [(today - timedelta(days=i)).strftime('%m/%d') for i in range(6, -1, -1)]
        day_keys = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]

        history_file = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
        history = {}
        try:
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
        except Exception:
            pass

        day_minutes = []
        for dk in day_keys:
            day_data = history.get(dk, [])
            day_minutes.append(sum(t.get('duration', 0) for t in day_data) / 60)

        bar_clrs = [bar_color_active if d == date_str else bar_color_inactive for d in day_keys]
        bars = ax2.bar(days, day_minutes, color=bar_clrs, width=0.55,
                       edgecolor='none', zorder=2)

        for i, (bar, dk) in enumerate(zip(bars, day_keys)):
            cnt = len(history.get(dk, []))
            if cnt > 0:
                ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                         str(cnt), ha='center', va='bottom', fontsize=9,
                         fontweight='bold', color='#2C1810')

        ax2.set_title('近7天', fontsize=12, color='#8B7355', pad=10)
        ax2.tick_params(axis='x', labelsize=10, colors='#8B7355', length=0, pad=8)
        ax2.tick_params(axis='y', labelsize=9, colors='#8B7355', length=0)
        for s in ax2.spines.values(): s.set_visible(False)
        ax2.yaxis.grid(True, color='#E0E0E0', linewidth=0.5, zorder=0)
        ax2.set_axisbelow(True)
        fig2.subplots_adjust(left=0.1, right=0.95, top=0.88, bottom=0.12)

        buf2 = io.BytesIO()
        fig2.savefig(buf2, format='png', transparent=True)
        plt.close(fig2)
        buf2.seek(0)
        self._bar_label.setRawPixmap(QPixmap.fromImage(QImage.fromData(buf2.getvalue())))

    def _on_open_bead_editor(self):
        from ui.bead_editor import BeadEditor
        if self._bead_editor is not None and self._bead_editor.isVisible():
            self._bead_editor.raise_()
            self._bead_editor.activateWindow()
            return
        self._bead_editor = BeadEditor(
            parent=self,
            on_export=lambda j, p, n: self._on_bead_export(j, p, n),
            on_showcase_save=lambda j, p, n: self._on_bead_showcase_save(j, p, n)
        )
        self._bead_editor.show()

    def _on_bead_showcase_save(self, json_path, png_path, name):
        creations = self.settings.bead_creations
        if not any(c.get("name") == name for c in creations):
            creations.append({
                "name": name,
                "json_path": json_path,
                "png_path": png_path,
                "created_at": datetime.now().isoformat()
            })
            if len(creations) > self.MAX_BEAD_CREATIONS:
                creations = creations[-self.MAX_BEAD_CREATIONS:]
            self.settings.bead_creations = creations
            self._refresh_bead_creations()
        self._status.setText(f"作品已保存到作品集: {name}")

    def _on_bead_export(self, json_path, png_path, name):
        if png_path and os.path.exists(png_path):
            self._input_path = png_path
            pix = QPixmap(png_path)
            if not pix.isNull():
                self._drop_zone.show_pixmap(pix)
            self._start_btn.setEnabled(True)
            self._status.setText(f"拼豆宠物已就绪: {name}")
            self.settings.pet_image_path = png_path

            creations = self.settings.bead_creations
            if not any(c.get("name") == name for c in creations):
                creations.append({
                    "name": name,
                    "json_path": json_path,
                    "png_path": png_path,
                    "created_at": datetime.now().isoformat()
                })
                if len(creations) > self.MAX_BEAD_CREATIONS:
                    creations = creations[-self.MAX_BEAD_CREATIONS:]
                self.settings.bead_creations = creations

            self._refresh_bead_creations()
            self._refresh_favorites()

    def _on_import_bead_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择拼豆照片",
            os.path.expanduser("~/Pictures"),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        self._status.setText("正在转换拼豆图...")
        QApplication.processEvents()
        try:
            img = process_bead_image(path)
            if img is None:
                QMessageBox.critical(self, "错误", "无法处理该图片,请换一张试试。")
                self._status.setText("拼豆图转换失败")
                return
            out_dir = os.path.join(os.path.expanduser("~"), ".desktop_pet", "images")
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, "bead_import.png")
            img.save(out_path, "PNG")
            final_path = os.path.join(out_dir, "bead_import_final.png")
            img.save(final_path, "PNG")
            self._input_path = final_path
            self.settings.pet_image_path = final_path
            self._bead_import_mode = True  # Flag to skip re-processing
            pix = QPixmap(out_path)
            if not pix.isNull():
                self._drop_zone.show_pixmap(pix)
            self._start_btn.setEnabled(True)
            self._status.setText(f"拼豆图已导入: {os.path.basename(path)} - 点击「启动 ToYu」开始")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"拼豆图处理失败: {str(e)[:200]}")
            self._status.setText("拼豆图转换失败")

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    @staticmethod
    def _global_stylesheet():
        return f"""
            QMainWindow {{
                background: {LIGHT_BG};
            }}

            /* Header */
            QWidget#header {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DARK}, stop:1 #4E342E);
            }}
            QLabel#headerTitle {{
                font-size: 24px;
                font-weight: bold;
                color: {ACCENT};
                font-family: "Segoe UI", "Microsoft YaHei";
            }}
            QLabel#headerSub {{
                font-size: 11px;
                color: #C9B99A;
            }}

            /* Section labels */
            QLabel#sectionLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {TEXT};
            }}

            /* Cards */
            QFrame#card {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            QFrame#card QLabel#cardTitle {{
                font-size: 12px;
                font-weight: bold;
                color: {MID};
                padding-bottom: 6px;
                border-bottom: 1px solid {BORDER};
            }}

            /* Bead tools card */
            QFrame#beadCard {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}

            /* Buttons */
            QPushButton {{
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid {BORDER};
                background: {CARD_BG};
                color: {TEXT};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: #FFF3E0;
                border-color: {ACCENT};
            }}
            QPushButton:pressed {{
                background: #FFE0B2;
            }}
            QPushButton:disabled {{
                background: #f0f0f0;
                color: #bbb;
                border-color: #e0e0e0;
            }}

            QPushButton#startBtn {{
                background: {ACCENT};
                color: white;
                border: none;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
            }}
            QPushButton#startBtn:hover {{
                background: {ACCENT_HOVER};
            }}
            QPushButton#startBtn:disabled {{
                background: #ddd;
                color: #aaa;
            }}

            QPushButton#actionBtn {{
                background: #FFF3E0;
                border: 1px solid {ACCENT};
                color: {MID};
                font-size: 12px;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 6px;
            }}
            QPushButton#actionBtn:hover {{
                background: #FFE0B2;
                border-color: {ACCENT_HOVER};
            }}
            QPushButton#actionBtn:disabled {{
                background: #f0f0f0;
                color: #bbb;
                border-color: #e0e0e0;
            }}

            /* Sliders */
            QSlider::groove:horizontal {{
                height: 5px;
                background: #E8DDD2;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                background: {ACCENT};
                border-radius: 8px;
                margin: -6px 0;
            }}
            QSlider::handle:horizontal:hover {{
                background: {ACCENT_HOVER};
            }}

            /* Checkboxes */
            QCheckBox {{
                spacing: 8px;
                color: {TEXT};
                font-size: 12px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #BCAAA4;
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border-color: {ACCENT};
            }}

            /* Status bar */
            QWidget#statusBar {{
                background: {CARD_BG};
                border-top: 1px solid {BORDER};
            }}
            QLabel#statusText {{
                font-size: 11px;
                color: {TEXT_SEC};
            }}
            QLabel#petStatus {{
                font-size: 11px;
                font-weight: bold;
            }}

            /* Mode toggle buttons */
            QPushButton[modeToggle="true"] {{
                padding: 7px 14px;
                border-radius: 6px;
                border: 2px solid {BORDER};
                background: {CARD_BG};
                color: {TEXT};
                font-size: 12px;
            }}
            QPushButton[modeToggle="true"]:hover {{
                background: #FFF3E0;
            }}
            QPushButton[modeToggle="true"]:checked {{
                background: #FFF3E0;
                border-color: {ACCENT};
                color: {MID};
                font-weight: bold;
            }}

            /* Scrollbars */
            QScrollBar:horizontal {{
                height: 6px;
                background: transparent;
            }}
            QScrollBar::handle:horizontal {{
                background: #D7CCC8;
                border-radius: 3px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: #BCAAA4;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            /* Pet thumbnails */
            QPushButton[petThumb="true"] {{
                border: 2px solid {BORDER};
                border-radius: 8px;
                background: #FAFAFA;
            }}
            QPushButton[petThumb="true"]:hover {{
                border-color: {ACCENT};
                background: #FFF3E0;
            }}
            QPushButton[petThumb="true"]:checked {{
                border: 3px solid {ACCENT};
                background: #FFF3E0;
            }}

            /* Favorites scroll area */
            QScrollArea#favGallery {{
                border: none;
                background: transparent;
            }}

            /* Showcase thumbnails */
            QPushButton[showcaseThumb="true"] {{
                border: 2px solid {BORDER};
                border-radius: 8px;
                background: #FAFAFA;
            }}
            QPushButton[showcaseThumb="true"]:hover {{
                border-color: {ACCENT};
                background: #FFF3E0;
            }}
            QPushButton[showcaseThumb="true"]:checked {{
                border: 3px solid {ACCENT};
                background: #FFF3E0;
            }}

            /* Showcase scroll area */
            QScrollArea#showcaseGallery {{
                border: none;
                background: transparent;
            }}

            /* ComboBox */
            QComboBox {{
                padding: 3px 8px;
                border: 1px solid {BORDER};
                border-radius: 4px;
                background: {CARD_BG};
                color: {TEXT};
                font-size: 11px;
            }}
            QComboBox:hover {{
                border-color: {ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}

            /* Generic labels & inputs */
            QLabel {{
                color: {TEXT};
                font-size: 11px;
            }}
            QSpinBox, QDoubleSpinBox {{
                padding: 4px 8px;
                border: 1px solid {BORDER};
                border-radius: 6px;
                background: white;
                color: {TEXT};
                font-size: 11px;
            }}
            QGroupBox {{
                color: {DARK};
                border: 1px solid {BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                color: {DARK};
            }}
        """

    def _on_open_settings(self):
        """打开设置对话框"""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.settings, self)

        dialog.scale_changed.connect(self._on_settings_scale_change)
        dialog.speed_changed.connect(self._on_settings_speed_change)
        dialog.dark_mode_changed.connect(self._on_settings_dark_mode)

        if dialog.exec():
            self._apply_settings(dialog)

    def _on_settings_scale_change(self, scale):
        """实时预览缩放"""
        if self._pet:
            self._pet.set_scale(scale)

    def _on_settings_speed_change(self, speed):
        """实时预览速度"""
        self.settings.walking_speed_max = speed
        self.settings.walking_speed_min = max(0.3, speed * 0.3)

    def _on_settings_dark_mode(self, enabled):
        """实时预览深色模式"""
        self._is_dark_mode = enabled
        if enabled:
            self._dark_mode_btn.setText("☀️ 浅色")
            self.setStyleSheet(self._dark_stylesheet())
        else:
            self._dark_mode_btn.setText("🌙 深色")
            self.setStyleSheet(self._global_stylesheet())
        self._refresh_inline_styles()

    def _on_auto_home_changed(self, value):
        """自动回家时间变更"""
        self.settings.auto_home_timeout = value
        for btn in self._auto_home_presets:
            mins = btn.property("_mins")
            btn.setChecked(mins == value)
        if self._pet and hasattr(self._pet, '_auto_home_timer'):
            if value > 0:
                self._pet._auto_home_timer.start(value * 60 * 1000)
            else:
                self._pet._auto_home_timer.stop()

    def _on_auto_home_preset(self, mins):
        """Preset button clicked"""
        self._auto_home_spin.setValue(mins)

    def _apply_settings(self, dialog):
        """应用设置"""
        if self._pet:
            self._pet.set_scale(self.settings.animation_scale)
            self._pet.set_time_awareness(self.settings.time_awareness_enabled)

            from pet_engine.pet_state_machine import InteractionMode
            mode_map = {"free": InteractionMode.FREE,
                        "follow": InteractionMode.FOLLOW,
                        "stay": InteractionMode.STAY}
            self._pet.state_machine.set_mode(
                mode_map.get(self.settings.interaction_mode, InteractionMode.FREE)
            )

            flags = self._pet.windowFlags()
            if self.settings.always_on_top:
                flags |= Qt.WindowType.WindowStaysOnTopHint
            else:
                flags &= ~Qt.WindowType.WindowStaysOnTopHint
            self._pet.setWindowFlags(flags)
            self._pet.show()

            self._pet.setWindowOpacity(dialog.get_opacity())

            if self.settings.house_enabled and not self._house_window:
                self._spawn_house()
            elif not self.settings.house_enabled and self._house_window:
                self._close_house()

            if hasattr(self._pet, '_pomodoro_timer'):
                if self.settings.pomodoro_enabled:
                    self._pet._pomodoro_interval = self.settings.pomodoro_interval * 60 * 1000
                    self._pet._pomodoro_timer.start(self._pet._pomodoro_interval)
                else:
                    self._pet._pomodoro_timer.stop()

            if hasattr(self._pet, '_ai_config'):
                self._pet._ai_config.load()
                self._pet._ai = AICompanion(self._pet._ai_config)

    def _save_ai_settings(self):
        """Save AI settings from the AI page."""
        try:
            from pet_engine.pet_ai import AIConfig, AICompanion
            config = AIConfig()
            config.enabled = self._ai_enabled_check.isChecked()
            config.api_base = self._ai_api_base_input.text().strip()
            config.api_key = self._ai_api_key_input.text().strip()
            config.model = self._ai_model_input.text().strip()
            config.name = self._ai_name_input.text().strip() or "ToYu"
            persona_data = self._ai_personality_combo.currentData()
            if persona_data:
                config.personality = persona_data
            config.temperature = self._ai_temp_spin.value()
            config.save()

            if self._pet:
                self._pet._ai_config = config
                self._pet._ai.config = config
                if hasattr(self._pet, '_proactive'):
                    self._pet._proactive._ai = self._pet._ai

            self._status.setText("✅ AI 设置已保存")
        except Exception as e:
            self._status.setText(f"❌ 保存失败: {e}")

    def _toggle_dark_mode(self):
        """切换深色模式"""
        self._is_dark_mode = not self._is_dark_mode
        if self._is_dark_mode:
            self._dark_mode_btn.setText("☀️ 浅色")
            self._dark_mode_btn.setToolTip("切换到浅色模式")
            self.setStyleSheet(self._dark_stylesheet())
        else:
            self._dark_mode_btn.setText("🌙 深色")
            self._dark_mode_btn.setToolTip("切换到深色模式")
            self.setStyleSheet(self._global_stylesheet())
        self._refresh_inline_styles()

    def _refresh_inline_styles(self):
        """Re-apply all inline styles after dark mode toggle."""
        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {self._c('text2')};
                border: none;
                border-bottom: 3px solid transparent;
                font-size: 13px;
                font-weight: bold;
                padding: 4px 16px;
                border-radius: 0;
            }}
            QPushButton:hover {{
                color: {self._c('text')};
                background: {self._c('hover_bg')};
            }}
            QPushButton:checked {{
                color: {self._c('text')};
                border-bottom: 3px solid {self._c('accent')};
            }}
        """
        for btn in self._page_btns.values():
            btn.setStyleSheet(btn_style)

        sb_style = f"QScrollBar::handle:vertical {{ background: {self._c('handle')}; border-radius: 3px; min-height: 20px; }}"
        for scroll in self.findChildren(QScrollArea):
            old = scroll.styleSheet()
            if 'QScrollBar::handle:vertical' in old:
                new = re.sub(r'QScrollBar::handle:vertical \{[^}]*\}',
                             f'QScrollBar::handle:vertical {{ background: {self._c("handle")}; border-radius: 3px; min-height: 20px; }}',
                             old)
                scroll.setStyleSheet(new)

        if hasattr(self, '_bead_card'):
            self._bead_card.setStyleSheet(f"""
                QFrame#beadCard {{
                    background: {self._c('tab_bg')};
                    border: 1px solid {self._c('border')};
                    border-radius: 10px;
                }}
            """)

        for sep in self.findChildren(QFrame):
            if sep.frameShape() == QFrame.Shape.VLine:
                sep.setStyleSheet(f"background: {self._c('border')}; max-width: 1px;")
            elif sep.frameShape() == QFrame.Shape.HLine:
                sep.setStyleSheet(f"background: {self._c('border')}; max-height: 1px;")

        for attr in ('_house_check', '_action_status', '_mood_status', '_affection_status'):
            w = getattr(self, attr, None)
            if w:
                key = 'accent' if attr == '_affection_status' else 'text'
                w.setStyleSheet(f"color: {self._c(key)}; font-size: 11px; font-weight: bold; background: transparent;")

        for attr in ('_fav_placeholder', '_showcase_placeholder', '_pomodoro_status'):
            w = getattr(self, attr, None)
            if w:
                w.setStyleSheet(f"color: {self._c('text2')}; font-size: 11px; padding: 18px 10px;" if 'placeholder' in attr
                               else f"color: {self._c('text2')}; font-size: 11px;")

        if hasattr(self, '_auto_home_spin'):
            self._auto_home_spin.setStyleSheet(f"""
                QSpinBox {{
                    background: {self._c('card')};
                    border: 1px solid {self._c('border')};
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-size: 12px;
                    color: {self._c('text')};
                }}
                QSpinBox:focus {{
                    border-color: {self._c('accent')};
                }}
            """)

        for btn in getattr(self, '_auto_home_presets', []):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {self._c('card')};
                    border: 1px solid {self._c('border')};
                    border-radius: 14px;
                    padding: 2px 12px;
                    font-size: 11px;
                    color: {self._c('text')};
                }}
                QPushButton:checked {{
                    background: {self._c('accent')};
                    color: white;
                    border-color: {self._c('accent')};
                }}
                QPushButton:hover {{
                    border-color: {self._c('accent')};
                }}
            """)

        if hasattr(self, '_fav_add_btn'):
            self._fav_add_btn.setStyleSheet(f"""
                QPushButton {{
                    border: 2px dashed {self._c('border')};
                    border-radius: 8px;
                    background: {self._c('input_bg')};
                    color: {self._c('text2')};
                    font-size: 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {self._c('accent')};
                    background: {self._c('hover_bg')};
                    color: {self._c('accent')};
                }}
            """)
        if hasattr(self, '_showcase_add_btn'):
            self._showcase_add_btn.setStyleSheet(f"""
                QPushButton {{
                    border: 2px dashed {self._c('border')};
                    border-radius: 8px;
                    background: {self._c('input_bg')};
                    color: {self._c('text2')};
                    font-size: 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {self._c('accent')};
                    background: {self._c('hover_bg')};
                    color: {self._c('accent')};
                }}
            """)

        if hasattr(self, '_time_period_label'):
            self._time_period_label.setStyleSheet(
                f"font-size: 12px; color: {self._c('accent')}; font-weight: bold;"
                f"background: {self._c('tab_bg')}; border-radius: 4px; padding: 2px 8px; margin-left: 10px;"
            )

        for child in self.findChildren(QPushButton):
            if child.text() in ('✏️ 拼豆编辑器', '📥 拼豆图导入'):
                child.setStyleSheet(f"""
                    QPushButton {{
                        background: {self._c('card')};
                        border: 1px solid {self._c('border')};
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-size: 11px;
                        color: {self._c('text')};
                    }}
                    QPushButton:hover {{
                        border-color: {self._c('accent')};
                        background: {self._c('hover_bg')};
                    }}
                """)

        for lbl in self.findChildren(QLabel):
            ss = lbl.styleSheet()
            if 'font-size: 10px' in ss and 'font-weight: bold' in ss:
                lbl.setStyleSheet(
                    f"color: {self._c('name_fg')}; font-size: 10px; "
                    "font-weight: bold; background: transparent;"
                )

        if hasattr(self, '_affection_bar'):
            bg_widget = self._affection_bar.parent()
            if bg_widget:
                bg_widget.setStyleSheet(f"""
                    QWidget {{
                        background: {self._c('border')};
                        border-radius: 4px;
                    }}
                """)

        if hasattr(self, '_drop_zone'):
            self._drop_zone.set_dark(self._is_dark_mode)

        self.update()

    def _dark_stylesheet(self):
        """深色模式样式表"""
        return f"""
            QMainWindow {{
                background: {DARK_BG};
            }}

            /* Header */
            QWidget#header {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {DARK_HEADER}, stop:1 #2A1F14);
            }}
            QLabel#headerTitle {{
                font-size: 24px;
                font-weight: bold;
                color: {ACCENT};
                font-family: "Segoe UI", "Microsoft YaHei";
            }}
            QLabel#headerSub {{
                font-size: 11px;
                color: #A08B6E;
            }}

            /* Section labels */
            QLabel#sectionLabel {{
                font-size: 13px;
                font-weight: bold;
                color: {DARK_TEXT};
            }}

            /* Cards */
            QFrame#card {{
                background: {DARK_CARD};
                border: 1px solid {DARK_BORDER};
                border-radius: 10px;
            }}
            QFrame#card QLabel#cardTitle {{
                font-size: 12px;
                font-weight: bold;
                color: {ACCENT};
                padding-bottom: 6px;
                border-bottom: 1px solid {DARK_BORDER};
            }}

            /* Bead tools card */
            QFrame#beadCard {{
                background: {DARK_CARD};
                border: 1px solid {DARK_BORDER};
                border-radius: 8px;
            }}

            /* Buttons */
            QPushButton {{
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid {DARK_BORDER};
                background: {DARK_CARD};
                color: {DARK_TEXT};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: #4A3525;
                border-color: {ACCENT};
            }}
            QPushButton:pressed {{
                background: #5A4535;
            }}
            QPushButton:disabled {{
                background: #2A1F14;
                color: #6B5A48;
                border-color: #3A2A1A;
            }}

            QPushButton#startBtn {{
                background: {ACCENT};
                color: white;
                border: none;
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
            }}
            QPushButton#startBtn:hover {{
                background: {ACCENT_HOVER};
            }}
            QPushButton#startBtn:disabled {{
                background: #3A2A1A;
                color: #6B5A48;
            }}

            QPushButton#actionBtn {{
                background: #3A2A1A;
                border: 1px solid {ACCENT};
                color: {DARK_TEXT};
                font-size: 12px;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 6px;
            }}
            QPushButton#actionBtn:hover {{
                background: #4A3525;
                border-color: {ACCENT_HOVER};
            }}
            QPushButton#actionBtn:disabled {{
                background: #2A1F14;
                color: #6B5A48;
                border-color: #3A2A1A;
            }}

            /* Sliders */
            QSlider::groove:horizontal {{
                height: 5px;
                background: #3A2A1A;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                background: {ACCENT};
                border-radius: 8px;
                margin: -6px 0;
            }}
            QSlider::handle:horizontal:hover {{
                background: {ACCENT_HOVER};
            }}

            /* Checkboxes */
            QCheckBox {{
                spacing: 8px;
                color: {DARK_TEXT};
                font-size: 12px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 2px solid #6B5A48;
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border-color: {ACCENT};
            }}

            /* Status bar */
            QWidget#statusBar {{
                background: {DARK_CARD};
                border-top: 1px solid {DARK_BORDER};
            }}
            QLabel#statusText {{
                font-size: 11px;
                color: {DARK_TEXT_SEC};
            }}
            QLabel#petStatus {{
                font-size: 11px;
                font-weight: bold;
            }}

            /* Mode toggle buttons */
            QPushButton[modeToggle="true"] {{
                padding: 7px 14px;
                border-radius: 6px;
                border: 2px solid {DARK_BORDER};
                background: {DARK_CARD};
                color: {DARK_TEXT};
                font-size: 12px;
            }}
            QPushButton[modeToggle="true"]:hover {{
                background: #4A3525;
            }}
            QPushButton[modeToggle="true"]:checked {{
                background: #4A3525;
                border-color: {ACCENT};
                color: {ACCENT};
                font-weight: bold;
            }}

            /* Scrollbars */
            QScrollBar:horizontal {{
                height: 6px;
                background: transparent;
            }}
            QScrollBar::handle:horizontal {{
                background: #4A3525;
                border-radius: 3px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: #5A4535;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: #4A3525;
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #5A4535;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            /* Pet thumbnails */
            QPushButton[petThumb="true"] {{
                border: 2px solid {DARK_BORDER};
                border-radius: 8px;
                background: #3A2A1A;
            }}
            QPushButton[petThumb="true"]:hover {{
                border-color: {ACCENT};
                background: #4A3525;
            }}
            QPushButton[petThumb="true"]:checked {{
                border: 3px solid {ACCENT};
                background: #4A3525;
            }}

            /* Favorites scroll area */
            QScrollArea#favGallery {{
                border: none;
                background: transparent;
            }}

            /* Showcase thumbnails */
            QPushButton[showcaseThumb="true"] {{
                border: 2px solid {DARK_BORDER};
                border-radius: 8px;
                background: #3A2A1A;
            }}
            QPushButton[showcaseThumb="true"]:hover {{
                border-color: {ACCENT};
                background: #4A3525;
            }}
            QPushButton[showcaseThumb="true"]:checked {{
                border: 3px solid {ACCENT};
                background: #4A3525;
            }}

            /* Showcase scroll area */
            QScrollArea#showcaseGallery {{
                border: none;
                background: transparent;
            }}

            /* ComboBox */
            QComboBox {{
                padding: 3px 8px;
                border: 1px solid {DARK_BORDER};
                border-radius: 4px;
                background: {DARK_CARD};
                color: {DARK_TEXT};
                font-size: 11px;
            }}
            QComboBox:hover {{
                border-color: {ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}

            /* Generic labels & inputs for dark mode */
            QLabel {{
                color: {DARK_TEXT};
                font-size: 11px;
            }}
            QSpinBox, QDoubleSpinBox {{
                padding: 4px 8px;
                border: 1px solid {DARK_BORDER};
                border-radius: 6px;
                background: {DARK_CARD};
                color: {DARK_TEXT};
                font-size: 11px;
            }}
            QGroupBox {{
                color: {DARK_TEXT};
                border: 1px solid {DARK_BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                color: {DARK_TEXT};
            }}
        """
