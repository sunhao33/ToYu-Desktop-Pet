"""Main control window - polished UI for ToYu Desktop Pet."""

import os
import sys
import subprocess
import re
import threading
from datetime import datetime
from PyQt6.QtCore import Qt, QSize, QTimer, QObject, pyqtSignal


class ReportAISignal(QObject):
    """跨线程回调用的信号载体。

    为什么需要它：AI 分析跑在工作线程里，算完必须回主线程更新界面
    （Qt 控件只能在主线程碰）。**不能用 QTimer.singleShot 从子线程
    回主线程** —— 它会把回调投递给「调用它的那个线程」的事件循环，
    而工作线程没有事件循环，回调永远不会执行，界面就卡在"分析中"。
    信号由 Qt 负责排队到接收者所在线程，是正确做法。
    """

    done = pyqtSignal(str, dict)
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
from ui.widgets.progress_ring import ProgressRing
from ui.widgets.report_view import AIPanel, ReportView
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
        """Store the original pixmap and scale to current width.

        pixmap 传 None 表示清空图表（例如所选日期没有数据），
        此时也要把已显示的旧图清掉，否则界面上会残留上一次的图。
        """
        self._src_pixmap = pixmap
        if pixmap is None:
            self._clear_pixmap()
        else:
            self._do_scale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._do_scale()

    def _clear_pixmap(self):
        """丢弃当前显示的图，并顺带清掉文本。

        注意 QLabel.setPixmap(空) 会把文本一起清空，所以这里同时清文本；
        调用方若需要显示提示文字，应在清图之后再 setText()。
        """
        self._src_pixmap = None
        super().setPixmap(QPixmap())
        self.setText("")

    def _do_scale(self):
        # 没有源图时什么都不做：这里若去清 pixmap 会把提示文本一起清掉，
        # 而本方法会被 resizeEvent 频繁调用（文字刚设置好就被抹掉）
        if self._src_pixmap is None:
            return
        if not self._src_pixmap.isNull():
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
HOVER_BG = "#FFF3E0"      # 悬停底（浅色）
PRESS_BG = "#FFE0B2"      # 按下底（浅色）
DISABLE_BG = "#F0F0F0"    # 禁用底
DISABLE_FG = "#BBBBBB"    # 禁用文字
DISABLE_BDR = "#E0E0E0"   # 禁用描边

# ── 深色主题 ────────────────────────────────────────────────
# 这套配色解决的是"看着不舒服"，而不只是对比度：原深色底色的**饱和度**
# 高达 33~38%（一整片浓棕），暗色带高饱和会显得发浑、发闷；
# 各元素色相全挤在 26~41°，也谈不上层次。
# 现在基底改为**接近中性的冷灰**（饱和 9~11%），颜色只用在强调处；
# 强调色仍保留品牌土豆金，暖色点缀落在冷底上反而更醒目。
# 实测：正文/卡片 12.7、次要 5.8、金色 6.9、成功 6.3、危险 4.9，
# 全部达到 WCAG AA（正文需 4.5）；卡片/背景 1.13、头部/背景 1.10、
# 标签底/卡片 1.16，层次清晰不突兀。
DARK_BG = "#16181B"       # 主背景（冷灰，饱和仅 10%）
DARK_CARD = "#202327"     # 卡片
DARK_TEXT = "#E4E7EB"     # 正文（12.7:1）
DARK_TEXT_SEC = "#959DA6" # 次要文字（5.8:1）
DARK_BORDER = "#33383F"   # 描边
DARK_HEADER = "#1E2126"   # 头部（比背景略亮，不再"倒挂"）
DARK_INPUT = "#1A1D21"    # 输入框底（比卡片略暗，形成内凹感）
DARK_TAB = "#2A2E34"      # 标签底
DARK_HOVER = "#2C3036"    # 悬停底
DARK_PRESS = "#353A41"    # 按下底
# 深色下的土豆金：冷底上需要更亮一点才醒目
DARK_ACCENT = "#D2A44A"
DARK_ACCENT_HOVER = "#E0B65F"
# 语义色
DARK_SUCCESS = "#7FB069"
DARK_WARNING = "#E0B05A"
DARK_DANGER = "#E06C75"

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
        # 深色侧引用色板常量，别再写死（写死后调色板改了这边不跟着变）
        if has_image:
            border = "none"
            bg = "transparent"
            text = ""
        elif hover:
            border = f"3px dashed {DARK_ACCENT_HOVER if self._dark else ACCENT}"
            bg = DARK_HOVER if self._dark else HOVER_BG
            text = "释放图片"
        else:
            border = f"3px dashed {DARK_BORDER if self._dark else '#D7CCC8'}"
            bg = DARK_INPUT if self._dark else '#FAFAFA'
            text = "拖放图片到这里\n或 点击选择"

        self.setStyleSheet(f"""
            QLabel {{
                border: {border};
                border-radius: 16px;
                background: {bg};
                color: {DARK_TEXT_SEC if self._dark else '#8D6E63'};
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
        self._tools_hub = None
        self._pulse_phase = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_status)
        self._app_data_dir = os.path.join(
            os.path.expanduser("~"), ".desktop_pet", "images"
        )
        self._is_dark_mode = False
        # 主题重刷用：构建期记录用到的配色键，构建完捕获样式模板
        self._theme_keys_used = set()
        self._theme_styles = []
        self._capturing_theme = False
        self._flow_active = False
        self._flow_window = None          # 心流模式是一个独立的顶层窗口
        self._mini_timer = None           # 悬浮计时小窗
        # 懒加载组件显式置空：它们原来只在宠物**启动成功**后才被创建，
        # 而 AI 页的按钮（如「全部忘掉」）从程序一打开就能点 ——
        # 属性不存在时会抛 AttributeError 冲出 Qt 槽（可能终止进程），
        # 或被 except 吞成"点了没反应"。这里先建好名字，各处置空判断才成立。
        self._memory_store = None
        self._memory_extractor = None
        self._goal_tracker = None
        self._report_builder = None
        self._report_ai_signal = None

        self._capturing_theme = True
        self._init_ui()
        self._capturing_theme = False
        self._capture_theme_styles()
        self._init_tray()
        self._restore_state()
        self._apply_content_minimum_width()

        self._screen_tracker = ScreenTimeTracker()
        self._screen_tracker.start()

        self._init_tools_hub()

        # 上次退出时若停在心流模式，就回到心流模式
        if self.settings.flow_mode_enabled:
            QTimer.singleShot(400, self.enter_flow_mode)

    def _apply_content_minimum_width(self):
        """最小尺寸必须容得下内容，否则窗口缩小时内容会被裁掉。

        宽度：各页内容需要 780~1000 不等（数据面板最宽），
              而 _init_ui 里设的 680 太窄 → 出现横向滚动条把右侧推出可视区。
        高度：AI 页内容约 800 高（API 配置 + 性格设置 + 保存按钮），
              而最小高度设的 700 太矮 → 底部内容被裁掉（实测 AI 页底部被切）。

        隐藏页面的 minimumSizeHint() 是过期值（未重新布局），
        所以这里先做两次延迟估算，并在每次切页时用「已显示页面」的实测值复核。
        """
        self._content_min_width = self.MIN_SIZE[0]
        self._content_min_height = self.MIN_SIZE[1]
        self.setMinimumSize(*self.MIN_SIZE)
        self._page_stack.currentChanged.connect(lambda _i: self._update_content_min_width())
        QTimer.singleShot(120, self._update_content_min_width)
        QTimer.singleShot(700, self._update_content_min_width)

    def _update_content_min_width(self):
        """用当前可见页面实测所需尺寸，必要时抬高窗口最小尺寸。

        高度用 sizeHint()（内容自然高度）而不是 minimumSizeHint()：
        后者对普通容器往往很小，无法反映「AI 页要 800 高才放得下」这类需求。
        """
        try:
            page = self._page_stack.currentWidget()
            if page is None:
                return
            hint = page.sizeHint()
            min_hint = page.minimumSizeHint()
            need_w = max(hint.width(), min_hint.width())
            need_h = max(hint.height(), min_hint.height())

            # 工具页内部还有子页，取当前子页
            # 页面若被包在滚动区里，QScrollArea 的 sizeHint 不反映内部内容宽度
            # （它只报一个很小值），必须取内部控件的尺寸，否则窗口最小宽度
            # 会算得太小、内容在横向被裁（功能页/工具页真实踩过）
            def _inner_hint(widget):
                if isinstance(widget, QScrollArea):
                    inner = widget.widget()
                    if inner is not None:
                        return inner.sizeHint(), inner.minimumSizeHint()
                return widget.sizeHint(), widget.minimumSizeHint()

            p_hint, p_min = _inner_hint(page)
            need_w = max(need_w, p_hint.width(), p_min.width())
            need_h = max(need_h, p_hint.height(), p_min.height())

            if self._tools_stack.count():
                sub = self._tools_stack.currentWidget()
                if sub is not None:
                    s_hint, s_min = _inner_hint(sub)
                    need_w = max(need_w, s_hint.width(), s_min.width())
                    need_h = max(need_h, s_hint.height(), s_min.height())

            need_w = max(self.MIN_SIZE[0], min(need_w + 40, 1200))
            # 头部(80) + 标签栏(46) + 状态栏(30) + 页内边距，约 190
            need_h = max(self.MIN_SIZE[1], min(need_h + 190, 1150))

            changed = False
            if need_w > self._content_min_width:
                self._content_min_width = need_w
                changed = True
            if need_h > self._content_min_height:
                self._content_min_height = need_h
                changed = True
            if changed:
                self.setMinimumSize(int(self._content_min_width),
                                    int(self._content_min_height))
                if self.width() < self._content_min_width or self.height() < self._content_min_height:
                    self.resize(max(self.width(), int(self._content_min_width)),
                                max(self.height(), int(self._content_min_height)))
        except RuntimeError:
            pass

    def _restore_state(self):
        saved = self.settings.pet_image_path
        if saved and os.path.exists(saved):
            self._input_path = saved
            pix = QPixmap(saved)
            if not pix.isNull():
                self._drop_zone.show_pixmap(pix)
            self._start_btn.setEnabled(True)
            # 有历史宠物也要自动启动：以前只在首次运行时自动启动，
            # 老用户打开软件后宠物一直不出现，会以为程序坏了
            self._first_launch = True
            self._status.setText("正在启动宠物...")
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
        # 构建界面时记录"这个控件用了哪些配色键"。
        # 用途见 _capture_theme_styles()：切主题时据此自动重刷，
        # 避免每个控件都要手工登记（漏一个就会在深色下留着浅色）。
        if getattr(self, "_capturing_theme", False):
            try:
                self._theme_keys_used.add(key)
            except AttributeError:
                pass
        m = {
            'bg':       (LIGHT_BG,    DARK_BG),
            'card':     (CARD_BG,     DARK_CARD),
            'text':     (TEXT,        DARK_TEXT),
            'text2':    (TEXT_SEC,    DARK_TEXT_SEC),
            'border':   (BORDER,      DARK_BORDER),
            'header':   (DARK,        DARK_HEADER),
            # accent / success / danger 在深色下用**提亮版**：
            # 原来的颜色直接放到暗底上对比度不足（危险红仅 2.53:1，
            # 错误提示与"时间不足"这类小字几乎看不见）
            'accent':   (ACCENT,      DARK_ACCENT),
            'accent_h': (ACCENT_HOVER, DARK_ACCENT_HOVER),
            'mid':      (MID,         DARK_ACCENT),
            'success':  (SUCCESS,     DARK_SUCCESS),
            'danger':   (DANGER,      DARK_DANGER),
            'hover_bg': (HOVER_BG,   DARK_HOVER),
            'press_bg': (PRESS_BG,   DARK_PRESS),
            'input_bg': ('#FAFAFA',   DARK_INPUT),
            'disable_bg': (DISABLE_BG, DARK_BG),
            'disable_fg': (DISABLE_FG, '#5F6670'),
            'disable_bdr': (DISABLE_BDR, DARK_CARD),
            'tab_bg':   ('#FFF8E1',   DARK_TAB),
            'handle':   ('#D7CCC8',   DARK_BORDER),
            'handle_h': ('#BCAAA4',   '#454B54'),
            'warn':     ('#B8860B',   DARK_WARNING),
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
        # 起始尺寸与最小尺寸：由实测内容需求决定（见 _apply_content_minimum_width）
        #   AI 页最宽最高：约 962×844（API 配置 + 性格设置 + 保存按钮）
        #   数据面板/效率工具：约 840×830
        # 最小尺寸留一点余量避免贴边，起始尺寸给更宽松的初始视野
        self.MIN_SIZE = (980, 850)
        self.START_SIZE = (1120, 880)
        self.setMinimumSize(*self.MIN_SIZE)
        self.resize(*self.START_SIZE)
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
        
        logo_icon = QLabel()
        logo_icon.setFixedSize(48, 48)
        logo_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_icon.setStyleSheet("background: transparent;")
        # 用程序自己的图标，和心流模式、窗口图标保持一致（emoji 渲染因系统而异）
        _icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "resources", "toyu_128.png")
        _logo_pix = QPixmap(_icon_path)
        if not _logo_pix.isNull():
            logo_icon.setPixmap(_logo_pix.scaled(
                34, 34, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            logo_icon.setText("🥔")
            logo_icon.setStyleSheet("font-size: 32px; background: transparent;")
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

        # 心流模式：切换到一个只看专注与进度的工作台（与主页共用同一套数据）
        # 图标用 ToYu 自己的图，与心流窗口头部保持一致
        self._flow_btn = QPushButton(" 心流模式")
        self._flow_btn.setObjectName("flowModeBtn")
        self._flow_btn.setFixedHeight(38)
        try:
            from ui.flow_window import app_icon
            _flow_icon = app_icon()
            if not _flow_icon.isNull():
                self._flow_btn.setIcon(_flow_icon)
                self._flow_btn.setIconSize(QSize(20, 20))
        except Exception:
            # 图标加载失败时退回 emoji，保证按钮不出现空白
            self._flow_btn.setText("🥔 心流模式")
        self._flow_btn.setToolTip("进入心流工作台：专注计时 + 今日进度，宠物状态保持不变")
        self._flow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._flow_btn.setStyleSheet(f"""
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
        self._flow_btn.clicked.connect(self.enter_flow_mode)
        header_layout.addWidget(self._flow_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

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
        # 横向滚动条常显（缩略图多了要能滚），但**滚动区本身不能参与最小宽度**
        # —— 否则收藏夹装满 10 个时会把整页最小宽度顶大，导致宠物页在
        # 最小宽度下出现横向溢出（本该滚动却把窗口撑宽）。
        # 关键是把宽度尺寸策略设为 Ignored：QScrollArea 的 sizeHint 会跟着
        # 内部内容宽度涨，Ignored 让这个提示不向上传递。
        self._fav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._fav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._fav_scroll.setWidgetResizable(True)
        self._fav_scroll.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Fixed)
        self._fav_scroll.setMinimumWidth(0)
        self._fav_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 6px; background: transparent; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        """)
        self._fav_container = QWidget()
        self._fav_container.setStyleSheet("background: transparent;")
        self._fav_container.setMinimumWidth(0)
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

        # 每日目标进度环（点一下可以改目标）
        goal_row = QHBoxLayout()
        goal_row.setSpacing(10)
        self._goal_ring = ProgressRing(size=64, thickness=6)
        # 先铺主题色：环的默认底槽是浅色，深色模式下没刷新过时
        # 会变成一个刺眼的白项圈
        self._goal_ring.set_colors(self._c('accent'), self._c('border'),
                                   self._c('text'))
        self._goal_ring.setToolTip("今日学习目标进度 · 点一下可以设置目标")
        self._goal_ring.setCursor(Qt.CursorShape.PointingHandCursor)
        self._goal_ring.mousePressEvent = lambda event: self._prompt_goal()  # type: ignore
        goal_row.addWidget(self._goal_ring)
        goal_box = QVBoxLayout()
        goal_box.setSpacing(2)
        goal_title = QLabel("今日学习目标")
        goal_title.setStyleSheet(
            f"color: {self._c('text')}; font-size: 11px; font-weight: bold;"
            " background: transparent;")
        goal_box.addWidget(goal_title)
        self._goal_label = QLabel("统计中…")
        self._goal_label.setWordWrap(True)
        self._goal_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        goal_box.addWidget(self._goal_label)
        goal_row.addLayout(goal_box, 1)
        status_card_layout.addLayout(goal_row)

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
        for idx, (name, icon) in enumerate([("效率工具", "📋"), ("桌面工具", "🖥"), ("数据面板", "📊")]):
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
        # 从倒计时器直接点「开始」也要弹出悬浮小窗，并且暂停/继续要接上真实逻辑
        self._timer_widget.started.connect(
            lambda: self.show_mini_timer(
                "专注倒计时", "countdown",
                pause=self.pause_focus_session,
                resume=self.resume_focus_session,
                stop=self.stop_focus_session))
        # 放进容器里，方便心流模式把同一个实例借走（共用状态，不复制）
        self._timer_slot = QWidget()
        self._timer_slot.setStyleSheet("background: transparent;")
        self._timer_slot_layout = QVBoxLayout(self._timer_slot)
        self._timer_slot_layout.setContentsMargins(0, 0, 0, 0)
        self._timer_slot_layout.addWidget(self._timer_widget)
        timer_card_layout.addWidget(self._timer_slot)
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
                f"QPushButton {{ background: {self._c('tab_bg')}; border: none;"
                  " border-radius: 6px;"
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
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')};"
                  " border-radius: 2px; }"
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
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')};"
                  " border-radius: 2px; }"
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

        # 每日目标卡（放在数据面板左栏底部，一眼看到今天进度）
        left_col.addWidget(self._build_goal_card())

        tools_p2_layout.addLayout(left_col, 1)  # left half = 1/2

        right_card = self._make_card("📅 日历")
        right_card_layout = right_card.layout()
        right_card_layout.setSpacing(8)

        from ui.calendar_widget import CuteCalendar
        self._calendar = CuteCalendar()
        self._calendar.date_selected.connect(self._on_calendar_date_selected)
        right_card_layout.addWidget(self._calendar)

        # 数据面板右栏：上面放学习/工作报告，下面放日历。
        # 分配 46:29 的高度份额，并让日历**可收缩**（它有 340px 的固定倾向，
        # 不让步就会把报告挤到内容重叠）。日历实际需要的最小高度约 250px。
        right_card.setSizePolicy(QSizePolicy.Policy.Preferred,
                                 QSizePolicy.Policy.Ignored)
        right_card.setMinimumHeight(250)
        right_col = QWidget()
        right_col.setStyleSheet("background: transparent;")
        right_col_layout = QVBoxLayout(right_col)
        right_col_layout.setContentsMargins(0, 0, 0, 0)
        right_col_layout.setSpacing(12)
        right_col_layout.addWidget(self._build_report_card(), 46)
        right_col_layout.addWidget(right_card, 29)

        tools_p2_layout.addWidget(right_col, 1)  # right half = 1/2

        from ui.tools.desktop_tools_page import DesktopToolsPage
        self._desktop_tools_page = DesktopToolsPage(self)
        self._tools_stack.addWidget(self._desktop_tools_page)

        self._tools_stack.addWidget(tools_p2)

        self._tools_tab_btns[0].setChecked(True)
        tools_main_layout.addWidget(self._tools_stack, 1)
        self._tools_tab_bar = tools_tab_bar

        self._page_stack.addWidget(self._wrap_in_scroll(tools_page))

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
        # index() 找不到时会抛 ValueError（不会返回 -1），而 personality
        # 来自可手工编辑的 ai_config.json —— 值不在内置列表里就会让整个
        # 主窗口构造失败、程序起不来。这里先判存在再取下标。
        _names = list(PERSONALITIES.keys())
        _cur = self._ai_config.personality
        self._ai_personality_combo.setCurrentIndex(
            _names.index(_cur) if _cur in _names else 0)
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

        # ── 它记住了什么 ────────────────────────────────────
        # 长期记忆必须**可见、可删、可清空**：用户有权知道 AI 记住了什么，
        # 也有权让它忘掉（对应评审表里的"精准遗忘与隐私保护"）
        self._memory_card = self._make_card("🧠 它记住了什么")
        memory_layout = self._memory_card.layout()
        memory_layout.setSpacing(8)

        self._memory_summary = QLabel("正在加载…")
        self._memory_summary.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        memory_layout.addWidget(self._memory_summary)

        self._memory_scroll = QScrollArea()
        self._memory_scroll.setWidgetResizable(True)
        self._memory_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._memory_scroll.setMinimumHeight(120)
        self._memory_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')};"
            " border-radius: 3px; min-height: 20px; }")
        self._memory_container = QWidget()
        self._memory_container.setStyleSheet("background: transparent;")
        self._memory_list = QVBoxLayout(self._memory_container)
        self._memory_list.setContentsMargins(0, 0, 0, 0)
        self._memory_list.setSpacing(6)
        self._memory_list.addStretch()
        self._memory_scroll.setWidget(self._memory_container)
        memory_layout.addWidget(self._memory_scroll, 1)

        memory_btns = QHBoxLayout()
        memory_btns.setSpacing(8)
        self._refresh_memory_btn = QPushButton("刷新")
        self._refresh_memory_btn.setObjectName("secondaryBtn")
        self._refresh_memory_btn.setFixedHeight(28)
        self._refresh_memory_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_memory_btn.clicked.connect(self._refresh_memory_card)
        memory_btns.addWidget(self._refresh_memory_btn)

        self._clear_memory_btn = QPushButton("全部忘掉")
        self._clear_memory_btn.setObjectName("secondaryBtn")
        self._clear_memory_btn.setFixedHeight(28)
        self._clear_memory_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_memory_btn.setToolTip("清空所有记忆（会先自动备份）")
        self._clear_memory_btn.clicked.connect(self._forget_all_memories)
        memory_btns.addWidget(self._clear_memory_btn)
        memory_btns.addStretch()
        memory_layout.addLayout(memory_btns)

        hint = QLabel("置信度由证据文本推算（有「以后都…」这类明确表达才会记）；"
                      "点 ✕ 可以单独忘掉某一条")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 10px; background: transparent;")
        memory_layout.addWidget(hint)

        ai_layout.addWidget(self._memory_card)

        # ── 运行指标 ────────────────────────────────────────
        # 这些数字是"用数据论证效果"用的：工具成功率、记忆命中率、延迟
        self._metrics_card = self._make_card("📊 运行指标")
        metrics_layout = self._metrics_card.layout()
        metrics_layout.setSpacing(8)

        self._metrics_label = QLabel("正在统计…")
        self._metrics_label.setWordWrap(True)
        self._metrics_label.setStyleSheet(
            f"color: {self._c('text')}; font-size: 11px; background: transparent;"
            "line-height: 150%;")
        metrics_layout.addWidget(self._metrics_label)

        metrics_btns = QHBoxLayout()
        metrics_btns.setSpacing(8)
        refresh_metrics = QPushButton("刷新统计")
        refresh_metrics.setObjectName("secondaryBtn")
        refresh_metrics.setFixedHeight(28)
        refresh_metrics.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_metrics.clicked.connect(self._refresh_metrics_card)
        metrics_btns.addWidget(refresh_metrics)

        clear_metrics = QPushButton("清空记录")
        clear_metrics.setObjectName("secondaryBtn")
        clear_metrics.setFixedHeight(28)
        clear_metrics.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_metrics.setToolTip("删除全部指标记录")
        clear_metrics.clicked.connect(self._clear_metrics)
        metrics_btns.addWidget(clear_metrics)
        metrics_btns.addStretch()
        metrics_layout.addLayout(metrics_btns)

        ai_layout.addWidget(self._metrics_card)

        ai_layout.addStretch()
        # 包一层滚动区：AI 页内容（API 配置 + 性格 + 记忆 + 指标）高度
        # 会超过可视区，不包的话 Qt 会把卡片压扁、按钮被挤掉
        self._page_stack.addWidget(self._wrap_in_scroll(ai_page))

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
        if idx == 1:
            self._refresh_desktop_tools()
            # 子页内容比主页更宽时也要抬高下限，避免右侧被切
            self._update_content_min_width()
        elif idx == 2:
            # 进数据面板就把学习统计的图先画出来，不用再点日历才有图
            self._ensure_study_charts()
            # 学习/工作报告与目标环也一起刷新（数据可能已经变了）
            self._refresh_report_preview()
            self._refresh_goal()
            self._update_content_min_width()

    # ── 桌面工具（剪贴板历史 / 护眼提醒）────────────────────
    def _init_tools_hub(self):
        from ui.tools.hub import DesktopToolsHub

        self._tools_hub = DesktopToolsHub(
            self.settings,
            notify=self._on_tools_notify,
            pet=self._pet,
        )
        self._tools_hub.set_listeners(
            clipboard_cb=lambda history: self._desktop_tools_page.refresh_clipboard(history),
            eyedata_cb=lambda eye_care: self._desktop_tools_page.refresh_eye_care(eye_care),
        )
        self._tools_hub.start()
        self._desktop_tools_page.refresh_clipboard(self._tools_hub.clipboard.history)
        self._desktop_tools_page.refresh_eye_care(self._tools_hub.eye_care)

    def attach_tools_hub_pet(self, pet):
        """Let the hub talk to the pet so reminders pop above it."""
        if self._tools_hub:
            self._tools_hub.pet = pet

    def _refresh_desktop_tools(self):
        if not self._tools_hub:
            return
        self._desktop_tools_page.refresh_clipboard(self._tools_hub.clipboard.history)
        self._desktop_tools_page.refresh_eye_care(self._tools_hub.eye_care)

    def _on_tools_notify(self, kind, title, body):
        pet = self._pet if self._pet and self._pet.isVisible() else None
        if not pet:
            self._status.setText(f"{title} {body}")
            return
        from pet_engine.pet_bubble import PomodoroNotificationBubble

        bubble = PomodoroNotificationBubble(pet, title=title, subtitle=body)
        bubble.show_near(pet)
        setattr(self, f"_notify_bubble_{kind}", bubble)
        if kind == "eye_rest":
            pet.trigger_dance(2.5)
        elif kind == "eye_resume":
            pet.trigger_sparkle_burst()

    def _on_page_switch(self, idx, label):
        """Switch page and enforce mutually exclusive tab highlighting."""
        current_widget = self._page_stack.currentWidget()
        new_widget = self._page_stack.widget(idx)

        if current_widget != new_widget:
            from PyQt6.QtWidgets import QGraphicsOpacityEffect
            from PyQt6.QtCore import QPropertyAnimation

            # 每个页面各自持有一个常驻效果对象：既避免每次切换新建导致堆积，
            # 也避免复用同一个对象时被 setGraphicsEffect(None) 删除后失效
            effect = getattr(new_widget, "_page_fade_effect", None)
            if effect is None:
                effect = QGraphicsOpacityEffect(new_widget)
                effect.setOpacity(1.0)
                new_widget.setGraphicsEffect(effect)
                new_widget._page_fade_effect = effect

            anim = getattr(self, "_page_fade_anim", None)
            if anim is None:
                anim = QPropertyAnimation(effect, b"opacity", self)
                anim.setDuration(200)
                anim.setStartValue(0.0)
                anim.setEndValue(1.0)
                self._page_fade_anim = anim
                self._page_fade_anim.finished.connect(self._on_page_fade_finished)
            else:
                if anim.state() == QPropertyAnimation.State.Running:
                    anim.stop()
                anim.setTargetObject(effect)

            self._page_fade_widget = new_widget
            effect.setOpacity(0.0)
            anim.start()
            # 兜底：万一 finished 没触发（页面被隐藏、动画被打断），
            # 也要把不透明度恢复，否则页面会一直停在看不见的状态
            QTimer.singleShot(400, self._on_page_fade_finished)

        self._page_stack.setCurrentIndex(idx)
        for lbl, btn in self._page_btns.items():
            btn.setChecked(lbl == label)

    def _on_page_fade_finished(self):
        """切换动画结束后把页面恢复为完全不透明（效果对象保留，供下次复用）。"""
        widget = getattr(self, "_page_fade_widget", None)
        effect = getattr(widget, "_page_fade_effect", None) if widget is not None else None
        if effect is not None:
            effect.setOpacity(1.0)

    # ── 心流模式（独立窗口）──────────────────────────────────
    def enter_flow_mode(self):
        """关闭主窗口，打开心流模式独立窗口。

        两个窗口共用同一套数据：settings / 宠物实例 / 计时器实例 /
        工具中枢 / 屏幕统计，所以切换不丢任何状态。
        """
        if self._flow_active:
            return
        self._flow_active = True
        self.settings.flow_mode_enabled = True

        if self._flow_window is None:
            from ui.flow_window import FlowWindow
            self._flow_window = FlowWindow(self)

        # 尺寸与位置沿用主窗口，视觉上是"同一个窗口换了内容"
        geo = self.geometry()
        self._flow_window.resize(geo.size())
        self._flow_window.move(geo.topLeft())

        # 计时器实例搬进心流窗口：计时状态自然延续，不会重置
        self._timer_slot_layout.removeWidget(self._timer_widget)
        self._flow_window.attach_timer(self._timer_widget)

        self._flow_window.apply_theme()
        self._flow_window.refresh_all()
        self.hide()
        self._flow_window.show()
        self._flow_window.raise_()
        self._flow_window.activateWindow()
        self._flow_btn.setText(" 已进入心流模式")

    def exit_flow_mode(self):
        """关闭心流窗口，回到 ToYu 主窗口（计时与宠物状态继续保留）。"""
        if not self._flow_active:
            return
        self._flow_active = False
        self.settings.flow_mode_enabled = False

        if self._flow_window is not None:
            # 计划项计时的进度先落盘，再切回主页
            flush = getattr(self._flow_window, "_flush_timers", None)
            if flush is not None:
                flush()
            timer = self._flow_window.detach_timer()
            if timer is not None:
                self._timer_slot_layout.addWidget(timer)
                timer.show()
            geo = self._flow_window.geometry()
            self._flow_window.hide()
            self.setGeometry(geo)          # 位置尺寸交还给主窗口

        self.show()
        self.raise_()
        self.activateWindow()
        self._flow_btn.setText(" 心流模式")
        self._status.setText("ToYu 运行中")

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
            # 给宠物内置的 AI 伴侣注入工具能力（加待办 / 开计时 / 查学习数据）
            self._bind_agent_tools()

            if self._tray:
                self._tray._pet = self._pet
                self._pet.set_bubble_callbacks(
                    show_hide_cb=self._on_toggle_visibility,
                    change_cb=self._on_select_image,
                    exit_cb=self._on_app_exit,
                    show_main_window_cb=self._on_show_main_window,
                )

            self._pet.show()
            self.attach_tools_hub_pet(self._pet)
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
        if self._tools_hub:
            self._tools_hub.flush()
            self._tools_hub.stop()
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

    # ── 计时控制（主页 / 心流窗口 / 悬浮小窗共用同一套逻辑）────
    def start_focus_session(self, minutes):
        """开始一段专注倒计时，并按设置弹出悬浮小窗。"""
        timer = getattr(self, "_timer_widget", None)
        if timer is None:
            return
        timer._set_preset(minutes)
        timer._on_start()
        pet = getattr(self, "_pet", None)
        if pet is not None:
            try:
                pet.trigger_dance(2.0)
            except RuntimeError:
                pass
        # 小窗的暂停/继续必须接上真实计时逻辑，否则按钮点了没反应
        self.show_mini_timer(
            "专注倒计时", "countdown",
            pause=self.pause_focus_session,
            resume=self.resume_focus_session,
            stop=self.stop_focus_session)

    def pause_focus_session(self):
        timer = getattr(self, "_timer_widget", None)
        if timer is not None and timer.get_is_running():
            timer._on_pause()

    def resume_focus_session(self):
        timer = getattr(self, "_timer_widget", None)
        if timer is not None and not timer.get_is_running() \
                and timer.get_remaining_seconds() > 0:
            timer._on_start()

    def stop_focus_session(self):
        timer = getattr(self, "_timer_widget", None)
        if timer is not None:
            timer._on_reset()
        self.hide_mini_timer()
        # 提前停止也要记账：用户实际专注了的那段时间不该白做。
        # （不足 1 分钟的会被 FocusLog 忽略，避免误点开始又立刻停也计入）
        flow = getattr(self, "_flow_window", None)
        if flow is not None:
            record = getattr(flow, "_record_session", None)
            if callable(record):
                try:
                    record()
                except Exception as exc:  # noqa: BLE001
                    print("[Flow] 提前停止记账失败: %s" % exc)

    # ── 悬浮计时小窗 ────────────────────────────────────────
    def show_mini_timer(self, title, mode, **actions):
        """弹出圆角矩形悬浮计时小窗（唯一入口，避免多处各建一个）。

        小窗同一时间只显示一件事：切入新计时时先停掉旧的刷新回调，
        避免上一个计时的暂停/结束回调被误触发。
        """
        if not self.settings.mini_timer_enabled:
            return None
        if self._mini_timer is None:
            from ui.mini_timer import MiniTimerWindow
            self._mini_timer = MiniTimerWindow(
                self, restore_cb=self._restore_main_window)
        self._mini_timer.configure(title, mode, **actions)
        self._mini_timer.show()
        self._mini_timer.raise_()
        return self._mini_timer

    def hide_mini_timer(self):
        if self._mini_timer is not None:
            self._mini_timer.hide()

    def refresh_mini_timer(self):
        """计划项计时结束后，让倒计时（若还在跑）重新接管小窗。"""
        if self._mini_timer is None or not self._mini_timer.isVisible():
            return
        timer = getattr(self, "_timer_widget", None)
        if timer is not None and (timer.get_is_running()
                                  or timer.get_remaining_seconds() > 0):
            self.show_mini_timer("专注倒计时", "countdown")
        else:
            self.hide_mini_timer()

    def _restore_main_window(self):
        """小窗上的「回到窗口」：收起小窗并把 ToYu 主窗口带到前台。"""
        self.hide_mini_timer()
        if self._flow_active and self._flow_window is not None:
            self._flow_window.show()
            self._flow_window.raise_()
            self._flow_window.activateWindow()
            return
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_timer_complete(self):
        """Handle timer completion with pet bubble notification."""
        self._status.setText("⏰ 倒计时结束!")
        # 通知心流窗口：它负责番茄记账（专注段落盘 + 自动进入休息）
        flow = getattr(self, "_flow_window", None)
        if flow is not None:
            handler = getattr(flow, "_on_focus_complete", None)
            if callable(handler):
                try:
                    handler()
                except RuntimeError:
                    pass
                except Exception as exc:  # noqa: BLE001
                    print("[Flow] 番茄记账失败: %s" % exc)
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
            # 不能在这里 return：图表更新在函数末尾，提前返回会让两幅图保持上一次的
            # 内容甚至一直空着（用户看到的就是"图不显示了"）
            self._finish_calendar_selection(date_str, tasks)
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

        self._finish_calendar_selection(date_str, tasks)

    def _finish_calendar_selection(self, date_str, tasks):
        """日历选日期后统一收尾：刷新两张统计图。

        「有记录」和「无记录」两条分支都必须走到这里，
        否则图表会停留在上一次的选择上（表现为图不刷新或一直空白）。
        """
        try:
            self._update_charts(date_str, tasks)
        except Exception as e:
            # 不能只 print：windowed 程序没有控制台，用户只会看到一片空白，
            # 必须把失败原因显示在图表位置上，并交给崩溃防护记入日志
            # 顺序很重要：QLabel.setPixmap(None) 会顺手清空文本，所以先清图再写字
            self._pie_label.setRawPixmap(None)
            self._bar_label.setRawPixmap(None)
            self._bar_label.setText("")
            self._pie_label.setText(f"图表生成失败\n{type(e).__name__}: {str(e)[:80]}")
            raise

    def _switch_stat_tab(self, idx):
        """Switch between study stats and screen time."""
        self._stat_stack.setCurrentIndex(idx)
        self._stat_tab_study.setChecked(idx == 0)
        self._stat_tab_screen.setChecked(idx == 1)
        if idx == 1:
            self._refresh_screen_time()
        else:
            self._ensure_study_charts()

    def _ensure_study_charts(self):
        """切到「学习统计」时自动出图。

        以前必须点日历日期才会画图，刚打开面板只有一行「点击日历查看统计」，
        很容易被当成「图不显示」。现在默认就按已选日期（初始为今天）画一次；
        如果当前选中的日期还没有任何任务，就退回到最近有记录的那一天。
        """
        from datetime import datetime
        import json, os

        if getattr(self, "_study_charts_drawn", False):
            return
        self._study_charts_drawn = True

        date_str = getattr(self, "_selected_chart_date", None) or datetime.now().strftime("%Y-%m-%d")
        history_file = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
        history = {}
        try:
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
        except Exception:
            history = {}

        if not history.get(date_str):
            # 当前日期没有记录时，退回到最近有记录的一天，保证面板不是空的
            dated = sorted([d for d, items in history.items() if items], reverse=True)
            if dated:
                date_str = dated[0]

        tasks = history.get(date_str, [])
        self._finish_calendar_selection(date_str, tasks)

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
            f"color: {self._c('text')}; font-size: 14px; font-weight: bold;"
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
        count_lbl.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px;")
        summary_layout.addWidget(count_lbl)

        layout.addWidget(summary)

        list_title = QLabel("应用排行")
        list_title.setStyleSheet(
            f"color: {self._c('text')}; font-size: 12px; font-weight: bold;"
                " padding: 4px 0;"
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
            # 颜色走主题：这几处原来写死浅色，深色模式下会变成
            # 白底黑字的一块，与整体格格不入
            card.setStyleSheet(
                f"QFrame {{ background: {self._c('card')};"
                f" border: 1px solid {self._c('border')};"
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
                f"color: {self._c('text')}; font-size: 12px; font-weight: bold;"
            )
            top_row.addWidget(name_lbl, 1)

            pct_lbl = QLabel(f"{self._fmt_dur(secs)}  {pct:.0f}%")
            pct_lbl.setStyleSheet(
                f"color: {self._c('text2')}; font-size: 11px;")
            top_row.addWidget(pct_lbl)
            card_layout.addLayout(top_row)

            bar_bg = QFrame()
            bar_bg.setFixedHeight(5)
            bar_bg.setStyleSheet(
                f"QFrame {{ background: {self._c('border')};"
                " border-radius: 2px; }"
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
        # 图表文字颜色跟随主题：图是渲染成 PNG 的，CSS 管不到，
        # 必须把颜色传进绘图调用，否则深色模式下图上文字是深色的、看不清
        _chart_fg = self._c('text')
        _chart_sec = self._c('text2')
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
        # 未选中日的柱子：原来固定浅灰 #E8E8E8，深色模式下是一排刺眼白柱。
        # 改用主题描边色，深浅两模式都合适。
        bar_color_inactive = self._c('border')

        def fmt(sec):
            if sec >= 3600: return f"{sec//3600}h{(sec%3600)//60}m"
            if sec >= 60: return f"{sec//60}m{sec%60}s"
            return f"{sec}s"

        # 判断环形图有没有数据，但不提前返回：
        # 以前这里直接 return，导致两个后果——
        #   1) 上一次的旧图残留在 _ScaledLabel 上，看起来"图不对/不刷新"
        #   2) 连"近 7 天活动"柱状图也一起不画了
        has_pie_data = bool(tasks)
        if not has_pie_data:
            # setRawPixmap(None) 会清掉旧图，避免残留
            self._pie_label.setRawPixmap(None)
            self._pie_label.setText(f"{date_str}\n暂无完成记录\n（完成待办后会出现在这里）")

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
                     fontsize=18, fontweight='bold', color=_chart_fg)
            ax1.legend(
                [f"{n} {fmt(t)}" for n, t in zip(names, times)],
                loc='lower center', bbox_to_anchor=(0.5, -0.12),
                fontsize=10, frameon=False, ncol=min(len(names), 2),
                labelcolor=_chart_fg,
                handlelength=0.8, handletextpad=0.3
            )
        else:
            # 无数据时不要留坐标轴边框和刻度，只显示一句提示
            ax1.axis('off')
            ax1.text(0.5, 0.5, '暂无完成记录', ha='center', va='center',
                     fontsize=13, color=_chart_sec)
        ax1.set_title(f'{date_str}', fontsize=12, color=_chart_sec, pad=10)
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
                         fontweight='bold', color=_chart_fg)

        ax2.set_title('近7天', fontsize=12, color=_chart_sec, pad=10)
        ax2.tick_params(axis='x', labelsize=10, colors=_chart_sec, length=0, pad=8)
        ax2.tick_params(axis='y', labelsize=9, colors=_chart_sec, length=0)
        for s in ax2.spines.values(): s.set_visible(False)
        ax2.yaxis.grid(True, color=self._c('border'), linewidth=0.5, zorder=0)
        ax2.set_axisbelow(True)
        if max(day_minutes) <= 0:
            # 7 天全都没有记录：matplotlib 会给 0.04/0.02 这种无意义刻度，
            # 这里改成固定范围 + 一句说明
            ax2.set_ylim(0, 60)
            ax2.set_yticks([])
            ax2.text(0.5, 0.5, '近 7 天暂无完成记录', transform=ax2.transAxes,
                     ha='center', va='center', fontsize=11, color=_chart_sec)
        else:
            ax2.set_ylim(0, max(day_minutes) * 1.25)
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
        # 关窗口只是收进托盘，必须明确告诉用户怎么唤回，否则会以为程序没关掉
        event.ignore()
        self.hide()
        if self._tray and self._tray.isVisible():
            self._tray.showMessage(
                "ToYu 还在运行",
                "已收起到系统托盘。双击托盘图标可以重新打开这个面板。",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

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
                color: {TEXT_SEC};
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
                background: {HOVER_BG};
                border-color: {ACCENT};
            }}
            QPushButton:pressed {{
                background: {PRESS_BG};
            }}
            QPushButton:disabled {{
                background: {DISABLE_BG};
                color: {DISABLE_FG};
                border-color: {DISABLE_BDR};
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
                background: {HOVER_BG};
                border: 1px solid {ACCENT};
                color: {MID};
                font-size: 12px;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 6px;
            }}
            QPushButton#actionBtn:hover {{
                background: {PRESS_BG};
                border-color: {ACCENT_HOVER};
            }}
            QPushButton#actionBtn:disabled {{
                background: {DISABLE_BG};
                color: {DISABLE_FG};
                border-color: {DISABLE_BDR};
            }}

            /* Sliders */
            QSlider::groove:horizontal {{
                height: 5px;
                background: {BORDER};
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
                background: {HOVER_BG};
            }}
            QPushButton[modeToggle="true"]:checked {{
                background: {HOVER_BG};
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
                background: {HOVER_BG};
            }}
            QPushButton[petThumb="true"]:checked {{
                border: 3px solid {ACCENT};
                background: {HOVER_BG};
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
                background: {HOVER_BG};
            }}
            QPushButton[showcaseThumb="true"]:checked {{
                border: 3px solid {ACCENT};
                background: {HOVER_BG};
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

            # 属性名是 self._house（不是 _house_window）：
            # 写错会让开关恒为"未启用"，于是取消勾选时小屋关不掉、
            # 每次确定都把现有小屋关掉重建一遍。
            if self.settings.house_enabled and not self._house:
                self._spawn_house()
            elif not self.settings.house_enabled and self._house:
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
                # 让 AI 具备工具调用能力（加待办 / 开计时 / 查学习数据）
                self._bind_agent_tools()

    # ── 智能体工具能力 ──────────────────────────────────────
    def _ensure_agent_tools(self):
        """创建工具注册表与执行桥（必须主线程），并注入到 AI 伴侣。

        只在第一次调用时创建：QTimer 依赖主线程事件循环，
        不能在子线程里懒加载。
        """
        if getattr(self, "_tool_runtime", None) is not None:
            return self._tool_runtime
        try:
            from pet_engine.agent import ToolRuntime, build_default_registry
            self._tool_registry = build_default_registry(self)
            self._tool_runtime = ToolRuntime(
                self._tool_registry, parent=self,
                on_trace=self._on_agent_trace)
            if self._pet is not None and getattr(self._pet, "_ai", None) is not None:
                self._pet._ai.set_tools(self._tool_registry, self._tool_runtime)
                self._pet._ai.set_trace_callback(self._on_agent_trace)
            return self._tool_runtime
        except Exception as exc:  # noqa: BLE001 — 工具能力失败不能影响聊天
            print("[Agent] 工具能力初始化失败: %s" % exc)
            self._tool_runtime = None
            return None

    def _on_agent_trace(self, message: str):
        """把工具执行轨迹显示到状态栏（让用户看得见"它在做什么"）。"""
        try:
            self._status.setText(message)
        except RuntimeError:
            pass

    def _bind_agent_tools(self):
        """把工具能力、上下文注入、长期记忆接到当前 AI 实例上。"""
        runtime = self._ensure_agent_tools()
        if self._pet is None:
            return
        ai = getattr(self._pet, "_ai", None)
        if ai is None:
            return
        if runtime is not None:
            ai.set_tools(self._tool_registry, runtime)
        ai.set_trace_callback(self._on_agent_trace)
        # 上下文注入：每次对话实时构建"桌面状态块"（带 400 token 预算）
        ai.set_context_provider(self._build_ai_context)
        # 长期记忆：把记忆块拼进系统提示 + 每轮结束抽取偏好
        ai.set_memory_provider(self._build_memory_block)
        # 指标采集（评审要的量化数据）
        if ai.metrics is None:
            try:
                from pet_engine.agent.metrics import MetricsRecorder
                ai.metrics = MetricsRecorder()
            except Exception as exc:  # noqa: BLE001
                print("[Metrics] 初始化失败: %s" % exc)
        # 打字机效果跟随设置
        self._pet._typing_enabled = bool(getattr(self.settings, "typing_enabled", True))
        store = self._ensure_memory()
        if store is not None:
            self._pet._on_turn_finished = self._extract_memories_async
            self._refresh_memory_card()
        self._refresh_metrics_card()

    def _build_memory_block(self, query: str) -> str:
        """按当前问题召回相关记忆。"""
        if self._memory_store is None:
            return ""
        try:
            from pet_engine.agent.recall import build_memory_block
            return build_memory_block(self._memory_store, query)
        except Exception as exc:  # noqa: BLE001
            print("[Memory] 召回失败: %s" % exc)
            return ""

    def _build_ai_context(self) -> str:
        """构建给 AI 的桌面状态块。"""
        if getattr(self, "_context_builder", None) is None:
            try:
                from pet_engine.agent.context import DesktopContextBuilder
                self._context_builder = DesktopContextBuilder(self, self.settings)
            except Exception as exc:  # noqa: BLE001
                print("[Context] 构建器初始化失败: %s" % exc)
                return ""
        try:
            return self._context_builder.build()
        except Exception as exc:  # noqa: BLE001
            print("[Context] 状态块构建失败: %s" % exc)
            return ""

    # ── 长期记忆 ────────────────────────────────────────────
    def _ensure_memory(self):
        """创建记忆库与抽取器（惰性，失败不影响聊天）。"""
        if getattr(self, "_memory_store", None) is not None:
            return self._memory_store
        try:
            from pet_engine.agent.memory_extract import MemoryExtractor
            from pet_engine.agent.memory_store import MemoryStore
            self._memory_store = MemoryStore()
            self._memory_store.purge_expired()
            self._memory_extractor = MemoryExtractor(
                transport=None, store=self._memory_store,
                on_log=self._on_memory_log)
            self._memory_extractor._transport = self._memory_transport
            return self._memory_store
        except Exception as exc:  # noqa: BLE001
            print("[Memory] 初始化失败: %s" % exc)
            self._memory_store = None
            return None

    def _memory_transport(self, messages):
        """给记忆抽取器用的模型调用（复用用户配置的 API）。"""
        config = getattr(getattr(self, "_pet", None), "_ai_config", None)
        if config is None or not getattr(config, "api_key", ""):
            raise RuntimeError("未配置 API")
        from pet_engine.agent.transport import (
            DEFAULT_TIMEOUT, openai_tool_transport,
        )
        # 抽取不需要工具，用同一套 OpenAI 兼容调用即可
        call = openai_tool_transport(config, max_tokens=600,
                                     timeout=min(30, DEFAULT_TIMEOUT))
        reply = call(messages, [])
        return reply.content

    def _on_memory_log(self, level: str, message: str):
        """记忆模块的日志：ERROR 级别的降级告警要让人看得见。"""
        try:
            if level == "ERROR":
                self._status.setText("⚠ " + message[:60])
            print("[Memory][%s] %s" % (level, message))
        except RuntimeError:
            pass

    def _extract_memories_async(self, user_text: str):
        """一轮对话后异步抽取偏好（不阻塞界面）。

        注意：记忆写盘在子线程（纯文件 IO，安全），但**刷新界面必须回主线程**
        —— Qt 控件不能在子线程碰。这里用 QTimer.singleShot 把刷新派回主线程。
        """
        if self._memory_store is None or self._memory_extractor is None:
            return
        if not getattr(self.settings, "memory_enabled", True):
            return
        text = (user_text or "").strip()
        if len(text) < 4:
            return
        extractor = self._memory_extractor

        def worker():
            try:
                result = extractor.extract(text)
            except Exception as exc:  # noqa: BLE001 — 抽取失败绝不能影响聊天
                print("[Memory] 抽取异常: %s" % exc)
                return
            changed = result.get("added", 0) + result.get("updated", 0)
            if changed:
                # 回到主线程刷新界面
                QTimer.singleShot(0, self._refresh_memory_card)

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_memory_card(self):
        """刷新「它记住了什么」卡片 —— 让用户能看见并管理被记住的内容。"""
        card = getattr(self, "_memory_card", None)
        if card is None:
            return
        try:
            store = self._memory_store
            if store is None:
                self._memory_summary.setText("记忆功能未启用")
                return
            records = store.all()
            stats = store.summary()
            self._memory_summary.setText(
                "已记住 %d 条（偏好 %d · 目标 %d · 事实 %d）"
                % (stats["active"],
                   stats["by_kind"].get("preference", 0),
                   stats["by_kind"].get("goal", 0),
                   stats["by_kind"].get("fact", 0)))
            self._clear_memory_btn.setEnabled(bool(records))
            self._rebuild_memory_rows(records)
        except RuntimeError:
            pass
        except Exception as exc:  # noqa: BLE001
            print("[Memory] 刷新卡片失败: %s" % exc)

    def _rebuild_memory_rows(self, records):
        """重建记忆列表。"""
        from pet_engine.agent.slots import get_slot

        while self._memory_list.count() > 1:
            item = self._memory_list.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        if not records:
            empty = QLabel("还没有记住任何偏好。\n和宠物聊天时说到「以后都…」「我习惯…」，它就会记住。")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {self._c('text2')}; font-size: 11px; padding: 18px;"
                " background: transparent;")
            self._memory_list.insertWidget(0, empty)
            return

        # 按更新时间倒序，最近的在前
        for idx, record in enumerate(
                sorted(records, key=lambda r: r.updated_at, reverse=True)[:60]):
            frame = QFrame()
            frame.setStyleSheet(
                f"QFrame {{ background: {self._c('tab_bg')};"
                f" border: 1px solid {self._c('border')}; border-radius: 8px; }}")
            row = QHBoxLayout(frame)
            row.setContentsMargins(10, 6, 8, 6)
            row.setSpacing(8)

            meta = get_slot(record.slot_id) or {}
            desc = meta.get("description", record.slot_id)
            value = record.value
            if isinstance(value, bool):
                value = "是" if value else "否"
            elif isinstance(value, list):
                value = "、".join(str(v) for v in value)

            text = QLabel("<b>%s</b>：%s" % (desc, value))
            text.setWordWrap(True)
            text.setStyleSheet(
                f"color: {self._c('text')}; font-size: 12px; background: transparent;")
            text.setToolTip("槽位 %s\n置信度 %.2f\n依据：%s"
                            % (record.slot_id, record.confidence, record.evidence))
            row.addWidget(text, 1)

            conf = QLabel("%d%%" % round(record.confidence * 100))
            conf.setStyleSheet(
                f"color: {self._c('text2')}; font-size: 10px; background: transparent;")
            conf.setToolTip("置信度（由证据文本推算，不是模型自报）")
            row.addWidget(conf)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(22, 22)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("忘掉这一条")
            del_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none;"
                f" color: {self._c('text2')}; font-size: 11px; }}"
                "QPushButton:hover { color: #D9534F; }")
            del_btn.clicked.connect(
                lambda checked=False, sid=record.slot_id: self._forget_memory(sid))
            row.addWidget(del_btn)
            self._memory_list.insertWidget(idx, frame)

    def _forget_memory(self, slot_id: str):
        """忘掉单条记忆（精准遗忘）。"""
        if self._memory_store is None:
            return
        try:
            self._memory_store.forget(slot_id)
            self._refresh_memory_card()
            self._status.setText("已忘掉「%s」" % slot_id)
        except Exception as exc:  # noqa: BLE001
            self._status.setText("遗忘失败: %s" % exc)

    def _forget_all_memories(self):
        """一键清空（先备份，避免误操作不可恢复）。"""
        if self._memory_store is None:
            return
        try:
            backup = self._memory_store.backup()
            count = self._memory_store.forget_all()
            self._refresh_memory_card()
            self._status.setText(
                "已清空 %d 条记忆%s" % (count, ("，备份在 " + os.path.basename(backup))
                                       if backup else ""))
        except Exception as exc:  # noqa: BLE001
            self._status.setText("清空失败: %s" % exc)

    def _refresh_metrics_card(self):
        """刷新「运行指标」卡片 —— 评审要的量化数据。"""
        label = getattr(self, "_metrics_label", None)
        if label is None:
            return
        try:
            ai = getattr(getattr(self, "_pet", None), "_ai", None)
            recorder = getattr(ai, "metrics", None) if ai else None
            if recorder is None:
                label.setText("指标采集未启用")
                return
            s = recorder.summary(days=30)
            if not s.get("turns"):
                label.setText("还没有对话记录。和宠物聊几句后这里会显示统计。")
                return
            lines = [
                "近 %d 天共 %d 轮对话，其中 %d 轮触发了工具调用"
                % (s["days"], s["turns"], s["turns_with_tools"]),
                "工具调用 %d 次，成功率 %d%%"
                % (s["tool_calls_total"], round(s["tool_success_rate"] * 100)),
                "平均每轮调用工具 %.2f 次" % s["tool_calls_avg_per_turn"],
                "记忆命中率 %d%%（%d 轮用上了长期记忆）"
                % (round(s["recall_rate"] * 100), s["recall_turns"]),
                "平均模型耗时 %.1f 秒 · 平均工具耗时 %.2f 秒"
                % (s["avg_model_ms"] / 1000.0, s["avg_tool_ms"] / 1000.0),
                "平均端到端延迟 %.1f 秒 · 平均回复 %d 字"
                % (s["avg_perceived_ms"] / 1000.0, s["avg_reply_chars"]),
            ]
            if s["degraded_turns"]:
                lines.append("有 %d 轮走了降级路径（模型不可用时的规则兜底）"
                             % s["degraded_turns"])
            # 记忆抽取的节省情况：没有"稳定偏好"信号的消息会被前置过滤挡下，
            # 不调用模型。这个数字直接反映省了多少次 API 调用。
            extractor = getattr(self, "_memory_extractor", None)
            if extractor is not None:
                st = extractor.health().get("stats", {})
                used = st.get("model", 0) + st.get("rules", 0)
                skipped = st.get("skipped", 0)
                if used or skipped:
                    lines.append("记忆抽取：实际处理 %d 条，前置过滤省下 %d 次"
                                 "模型调用" % (used, skipped))
            label.setText("\n".join(lines))
        except RuntimeError:
            pass
        except Exception as exc:  # noqa: BLE001
            print("[Metrics] 刷新卡片失败: %s" % exc)

    def _clear_metrics(self):
        """清空指标记录。"""
        try:
            ai = getattr(getattr(self, "_pet", None), "_ai", None)
            recorder = getattr(ai, "metrics", None) if ai else None
            if recorder is None:
                return
            recorder.clear()
            self._refresh_metrics_card()
            self._status.setText("指标记录已清空")
        except Exception as exc:  # noqa: BLE001
            self._status.setText("清空失败: %s" % exc)

    def _wrap_in_scroll(self, inner: QWidget) -> QScrollArea:
        """把页面内容包进纵向滚动区。

        为什么需要：AI 页内容高度超过可视区时，Qt 会把卡片**压缩**到小于
        最小高度，按钮和文字会被挤掉；没有滚动区就无法访问被挤出去的部分。
        包一层滚动区后，任何窗口尺寸下所有内容都能滚到。

        背景透明 + 无边框，保证视觉上与原页面一致。
        """
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 8px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')};"
            " border-radius: 4px; min-height: 30px; }"
            f"QScrollBar::handle:vertical:hover {{ background: {self._c('handle_h')}; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical"
            " { height: 0; }")
        inner.setStyleSheet((inner.styleSheet() or "") + "\nbackground: transparent;")
        area.setWidget(inner)
        return area

    def _toast(self, message: str, ms: int = 2600):
        """在窗口内弹一条明显的提示（几秒后自动消失）。

        只靠底部状态栏那一行小灰字，用户经常看不到 —— 保存这类操作
        必须有**看得见**的反馈。
        """
        try:
            label = getattr(self, "_toast_label", None)
            if label is None:
                label = QLabel(self)
                label.setObjectName("toastLabel")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setWordWrap(True)
                self._toast_label = label
                self._toast_timer = QTimer(self)
                self._toast_timer.setSingleShot(True)
                self._toast_timer.timeout.connect(self._hide_toast)

            label.setStyleSheet(f"""
                QLabel#toastLabel {{
                    background: {self._c('accent')};
                    color: #FFFFFF;
                    border-radius: 10px;
                    padding: 10px 22px;
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            label.setText(message)
            label.adjustSize()
            label.setFixedWidth(min(max(label.width(), 200), max(240, self.width() - 120)))
            label.adjustSize()
            # 顶部居中，避开头部按钮
            x = max(10, (self.width() - label.width()) // 2)
            label.move(x, 96)
            label.show()
            label.raise_()
            self._toast_timer.start(ms)
        except Exception as exc:  # noqa: BLE001 — 提示失败不能影响主流程
            print("[Toast] 显示失败: %s" % exc)

    def _hide_toast(self):
        label = getattr(self, "_toast_label", None)
        if label is not None:
            try:
                label.hide()
            except RuntimeError:
                pass

    # ── 每日目标 ────────────────────────────────────────────
    def _ensure_goal_tracker(self):
        """创建每日目标追踪器（惰性）。"""
        if getattr(self, "_goal_tracker", None) is not None:
            return self._goal_tracker
        try:
            from pet_engine.goal import DailyGoalTracker
            self._goal_tracker = DailyGoalTracker(
                settings=self.settings,
                tracker=getattr(self, "_screen_tracker", None),
                memory_store=getattr(self, "_memory_store", None))
        except Exception as exc:  # noqa: BLE001
            print("[Goal] 初始化失败: %s" % exc)
            self._goal_tracker = None
        return self._goal_tracker

    def _refresh_goal(self):
        """刷新所有目标环（主页 / 心流窗口 / 数据面板）。"""
        tracker = self._ensure_goal_tracker()
        if tracker is None:
            return
        try:
            info = tracker.progress()
        except Exception as exc:  # noqa: BLE001
            print("[Goal] 读取进度失败: %s" % exc)
            return

        accent = self._c('accent')
        track = self._c('border')
        fg = self._c('text')
        text2 = self._c('text2')

        if info["has_goal"]:
            ratio = info["ratio"]
            ring_text = "%d%%" % round(ratio * 100)
            detail = tracker.text()
            full = "#4CAF50"          # 达成用绿色
            dim = False
        else:
            ratio = 0.0
            ring_text = "未设"
            detail = tracker.text()
            full = None
            dim = True

        for ring in (getattr(self, "_goal_ring", None),
                     getattr(self, "_data_goal_ring", None)):
            if ring is not None:
                ring.set_state(ratio, ring_text, accent, track, fg,
                               font_size=15, dim=dim, full_color=full)
        self._refresh_goal_history()

        label = getattr(self, "_goal_label", None)
        if label is not None:
            label.setText(detail)
            label.setStyleSheet(
                f"color: {accent if info['reached'] else text2};"
                " font-size: 11px; background: transparent;")
        data_label = getattr(self, "_data_goal_label", None)
        if data_label is not None:
            data_label.setText(detail)
            data_label.setStyleSheet(
                f"color: {accent if info['reached'] else text2};"
                " font-size: 11px; background: transparent;")

        # 心流窗口
        flow = getattr(self, "_flow_window", None)
        if flow is not None and hasattr(flow, "refresh_goal"):
            try:
                flow.refresh_goal(info)
            except RuntimeError:
                pass

        # 达成时庆祝一次（每天只一次）
        if tracker.should_celebrate():
            self._celebrate_goal(info)

    def _celebrate_goal(self, info):
        """达成每日目标：宠物庆祝 + 提示（每天只触发一次）。"""
        pet = getattr(self, "_pet", None)
        if pet is not None:
            try:
                pet.trigger_celebrate(3.0)
            except (RuntimeError, AttributeError):
                pass
        self._toast("🎉 今日目标达成！已学习 %d 分钟" % info["study_minutes"])
        try:
            self._status.setText("🎉 今日学习目标达成（%d 分钟）"
                                 % info["study_minutes"])
        except RuntimeError:
            pass

    def _prompt_goal(self):
        """点击目标环时设置目标（用输入对话框）。"""
        tracker = self._ensure_goal_tracker()
        if tracker is None:
            return
        from PyQt6.QtWidgets import QInputDialog
        current = tracker.goal_minutes() or 120
        minutes, ok = QInputDialog.getInt(
            self, "设置每日学习目标",
            "每天计划学习多少分钟？（填 0 表示不设目标）",
            current, 0, 1440, 15)
        if not ok:
            return
        tracker.set_goal_minutes(minutes)
        self._refresh_goal()
        if minutes:
            self._toast("已设置每日目标：%d 分钟" % minutes)
        else:
            self._toast("已清除每日目标")

    def _build_goal_card(self):
        """数据面板里的每日目标卡片（含 7 天达成情况）。"""
        card = self._make_card("🎯 每日目标")
        layout = card.layout()
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(12)
        self._data_goal_ring = ProgressRing(size=88, thickness=7)
        self._data_goal_ring.set_colors(self._c('accent'), self._c('border'),
                                        self._c('text'))
        self._data_goal_ring.setToolTip("点一下可以设置每日目标")
        self._data_goal_ring.setCursor(Qt.CursorShape.PointingHandCursor)
        self._data_goal_ring.mousePressEvent = lambda event: self._prompt_goal()  # type: ignore
        row.addWidget(self._data_goal_ring)

        box = QVBoxLayout()
        box.setSpacing(4)
        self._data_goal_label = QLabel("统计中…")
        self._data_goal_label.setWordWrap(True)
        self._data_goal_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 11px; background: transparent;")
        box.addWidget(self._data_goal_label)

        self._goal_history_label = QLabel("")
        self._goal_history_label.setWordWrap(True)
        self._goal_history_label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 10px; background: transparent;")
        box.addWidget(self._goal_history_label)
        box.addStretch()
        row.addLayout(box, 1)
        layout.addLayout(row)

        set_btn = QPushButton("设置目标")
        set_btn.setObjectName("secondaryBtn")
        set_btn.setFixedHeight(26)
        set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_btn.clicked.connect(self._prompt_goal)
        layout.addWidget(set_btn)
        return card

    def _refresh_goal_history(self):
        """最近 7 天的达成情况（一眼看出这周状态）。"""
        label = getattr(self, "_goal_history_label", None)
        tracker = getattr(self, "_goal_tracker", None)
        if label is None or tracker is None:
            return
        goal = tracker.goal_minutes()
        if not goal:
            label.setText("设置目标后，这里会显示最近 7 天的达成情况")
            return
        from datetime import date, timedelta
        marks = []
        ok_days = 0
        for i in range(6, -1, -1):
            day = (date.today() - timedelta(days=i)).isoformat()
            info = tracker.progress(day)
            if info["reached"]:
                marks.append("●")
                ok_days += 1
            elif info["study_minutes"] > 0:
                marks.append("○")
            else:
                marks.append("·")
        label.setText("近 7 天：%s  达成 %d/7 天"
                      % (" ".join(marks), ok_days))

    # ── 学习/工作报告 ───────────────────────────────────────
    def _ensure_report(self):
        if getattr(self, "_report_builder", None) is not None:
            return self._report_builder
        try:
            from pet_engine.report import LearningReport
            self._report_builder = LearningReport(
                main_window=self,
                tracker=getattr(self, "_screen_tracker", None),
                todo_widget=getattr(self, "_todo_widget", None),
                goal_tracker=self._ensure_goal_tracker())
        except Exception as exc:  # noqa: BLE001
            print("[Report] 初始化失败: %s" % exc)
            self._report_builder = None
        return self._report_builder

    def _refresh_report_preview(self, period: str = None):
        """刷新报告视图（卡片式渲染）。"""
        view = getattr(self, "_report_view", None)
        builder = self._ensure_report()
        if view is None or builder is None:
            return
        period = period or getattr(self, "_report_period", "today")
        self._report_period = period
        ai_text = getattr(self, "_report_ai_text", "")
        mode = getattr(self, "_report_mode", "basic")
        # 切换周期后 AI 分析就失效了（数据区间变了），必须重新生成
        if mode == "ai" and not ai_text:
            mode = "basic"
        try:
            data = builder.snapshot(period)
            tips = builder.suggestions(data)
        except Exception as exc:  # noqa: BLE001
            print("[Report] 生成失败: %s" % exc)
            return
        try:
            view.show_report(
                data,
                suggestions=tips,
                ai_text=ai_text if mode == "ai" else "",
                ai_busy=bool(getattr(self, "_report_ai_busy", False)),
                ai_error=getattr(self, "_report_ai_error", ""))
        except Exception as exc:  # noqa: BLE001
            print("[Report] 渲染失败: %s" % exc)
        # 同步按钮选中态
        for key, btn in getattr(self, "_report_btns", {}).items():
            btn.setChecked(key == period)
        self._update_ai_btn_state()

    def _on_report_period(self, period: str):
        """切换统计区间。区间变了，之前的 AI 分析就不再对应，清掉。"""
        self._report_ai_text = ""
        self._report_ai_error = ""
        self._refresh_report_preview(period)

    def _set_report_mode(self, mode: str):
        """切换基础版 / AI 版。"""
        self._report_mode = mode
        for key, btn in getattr(self, "_report_mode_btns", {}).items():
            btn.setChecked(key == mode)
        if mode == "ai" and not getattr(self, "_report_ai_text", ""):
            # 切到 AI 版但还没生成过 → 提示并尝试生成
            if not self._ai_key_ready():
                self._toast("AI 版需要先在「AI 页」配置 API Key")
                self._report_mode = "basic"
                self._report_mode_btns["basic"].setChecked(True)
                self._report_mode_btns["ai"].setChecked(False)
            else:
                self._generate_ai_report()
        self._refresh_report_preview()
        self._update_ai_btn_state()

    def _ai_key_ready(self) -> bool:
        """是否已配置可用的 API Key。"""
        config = getattr(getattr(self, "_pet", None), "_ai_config", None)
        return bool(config is not None and getattr(config, "api_key", ""))

    def _update_ai_btn_state(self):
        """AI 分析按钮的可用性与文案。"""
        btn = getattr(self, "_report_ai_btn", None)
        if btn is None:
            return
        if getattr(self, "_report_ai_busy", False):
            btn.setEnabled(False)
            btn.setText("分析中…")
            return
        btn.setEnabled(True)
        btn.setText("✨ 重新分析" if getattr(self, "_report_ai_text", "")
                    else "✨ AI 分析")

    def _report_ai_transport(self):
        """给报告 AI 分析用的模型调用。

        单独抽一层是为了可注入（测试时替换成假的，不发真实请求）。
        默认复用「AI 页」配置的 API。
        """
        injected = getattr(self, "_report_transport_override", None)
        if injected is not None:
            return injected
        return self._memory_transport

    def _report_signal(self):
        """取跨线程回调信号（懒创建并连到主线程槽）。"""
        sig = getattr(self, "_report_ai_signal", None)
        if sig is None:
            sig = ReportAISignal()
            sig.done.connect(self._on_ai_report_done)
            self._report_ai_signal = sig
        return sig

    def _generate_ai_report(self):
        """在后台线程里生成 AI 分析（不能在主线程调用模型，会卡界面）。"""
        if getattr(self, "_report_ai_busy", False):
            return
        builder = self._ensure_report()
        if builder is None:
            return
        if not self._ai_key_ready():
            self._toast("AI 版需要先在「AI 页」配置 API Key")
            return

        period = getattr(self, "_report_period", "today")
        transport = self._report_ai_transport()
        signal = self._report_signal()
        self._report_ai_busy = True
        self._update_ai_btn_state()
        # 视图里显示"分析中"占位（不用整段文字顶替报告内容）
        try:
            self._refresh_report_preview(period)
        except RuntimeError:
            pass

        def worker():
            try:
                result = builder.analyze_with_ai(period, transport=transport)
            except Exception as exc:  # noqa: BLE001
                result = {"ok": False, "text": "",
                          "error": "分析线程异常：%s" % str(exc)[:100]}
            # 用信号回主线程（子线程不能碰 Qt 控件）
            try:
                signal.done.emit(period, result)
            except RuntimeError:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_report_done(self, period: str, result: dict):
        """AI 分析返回后的界面更新。"""
        self._report_ai_busy = False
        if not result.get("ok"):
            self._report_ai_text = ""
            self._report_ai_error = result.get("error", "AI 分析失败")
            self._report_mode = "basic"
            for key, btn in getattr(self, "_report_mode_btns", {}).items():
                btn.setChecked(key == "basic")
            self._toast("❌ %s" % self._report_ai_error)
        else:
            self._report_ai_text = result["text"]
            self._report_ai_error = ""
            self._report_mode = "ai"
            for key, btn in getattr(self, "_report_mode_btns", {}).items():
                btn.setChecked(key == "ai")
            self._toast("✅ AI 分析完成")
        # 期间用户可能切了区间，切过就不覆盖当前预览
        if getattr(self, "_report_period", "today") == period:
            self._refresh_report_preview(period)
        else:
            self._update_ai_btn_state()

    def _open_report_folder(self):
        """在文件资源管理器里打开报告导出目录。

        导出到 %APPDATA%\\ToYu\\reports 这种深层隐藏目录，光靠一条
        几秒就消失的提示，用户很难找到文件 —— 给一个直接打开的入口。
        """
        from pet_engine.report import REPORT_DIR
        try:
            os.makedirs(REPORT_DIR, exist_ok=True)
        except OSError as exc:
            self._toast("❌ 无法创建导出目录：%s" % exc)
            return
        try:
            # 用 explorer 打开；不加 shell=True，避免路径里有空格时被截断
            subprocess.Popen(["explorer", os.path.normpath(REPORT_DIR)])
            self._toast("📁 已打开导出目录")
        except Exception as exc:  # noqa: BLE001
            self._toast("❌ 打开目录失败：%s" % str(exc)[:50])

    def _export_report(self, period: str = None):
        """导出报告文件并提示路径。"""
        builder = self._ensure_report()
        if builder is None:
            self._toast("❌ 报告模块不可用")
            return
        period = period or getattr(self, "_report_period", "today")
        ai_text = getattr(self, "_report_ai_text", "")
        mode = getattr(self, "_report_mode", "basic")
        # 数据太少时先提醒：导出的报告几乎全是 0，用户会以为文件坏了
        sparse = False
        try:
            sparse = builder.is_sparse(builder.snapshot(period))
        except Exception:  # noqa: BLE001
            pass
        try:
            path = builder.export(period, fmt="md", ai_text=ai_text, mode=mode)
        except Exception as exc:  # noqa: BLE001
            self._toast("❌ 导出失败：%s" % str(exc)[:60])
            return
        kind = "AI 版" if (ai_text and mode == "ai") else "基础版"
        if sparse:
            self._toast("✅ 已导出（%s），但该区间数据很少，报告内容会比较简短：%s"
                        % (kind, os.path.basename(path)), 4200)
        else:
            self._toast("✅ 已导出（%s）：%s" % (kind, os.path.basename(path)))
        try:
            self._status.setText("报告已导出到 %s（点「📁」可直接打开目录）" % path)
        except RuntimeError:
            pass

    def _make_report_subtitle(self):
        """报告卡片标题下的说明（一句话讲清两个版本的数据边界）。"""
        label = QLabel("基础版只读本机记录、不联网；"
                       "AI 版会把统计数据（不含聊天记录与文件内容）"
                       "发给你配置的模型做分析。")
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {self._c('text2')}; font-size: 10px;"
            " background: transparent;")
        return label

    def _build_report_card(self):
        """数据面板里的学习/工作报告卡片。"""
        # 版本状态在这里初始化，供 _refresh_report_preview / 导出读取
        self._report_mode = "basic"     # basic | ai
        self._report_ai_text = ""       # AI 分析正文（空表示还没生成）
        self._report_ai_error = ""      # 上次 AI 分析失败的原因
        self._report_ai_busy = False
        self._report_period = "today"

        card = self._make_card("📄 学习/工作报告")
        # 数据边界说明放在标题下方当副标题：
        # 原来放在卡片底部，会被压在滚动区下面与内容重叠。
        card.layout().addWidget(self._make_report_subtitle())
        # 报告段落多（概览/每日/应用/时段/任务 + AI 面板），给足下限，
        # 否则默认窗口下内容会被压到互相重叠。超出的部分卡片内滚动。
        card.setMinimumHeight(470)
        layout = card.layout()
        layout.setSpacing(8)

        # ── 第一行：统计区间 ──
        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        self._report_btns = {}
        for key, text in (("today", "今日"), ("week", "本周"), ("month", "本月")):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {self._c('tab_bg')}; border: none;"
                " border-radius: 6px; font-size: 11px; padding: 0 12px;"
                f" color: {self._c('text')}; }}"
                f"QPushButton:checked {{ background: {self._c('accent')};"
                " color: white; }")
            btn.clicked.connect(lambda checked=False, k=key: self._on_report_period(k))
            tabs.addWidget(btn)
            self._report_btns[key] = btn
        tabs.addStretch()
        layout.addLayout(tabs)

        # ── 第二行：版本切换（基础版 / AI 版）+ 导出 ──
        modes = QHBoxLayout()
        modes.setSpacing(6)
        self._report_mode_btns = {}
        for key, text, tip in (
                ("basic", "基础版", "纯本地统计，不联网、不需要 API Key"),
                ("ai", "AI 版", "在基础统计之上，由大模型深度分析（需要 API Key）")):
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                f"QPushButton {{ background: {self._c('tab_bg')}; border: 1px solid"
                f" {self._c('border')}; border-radius: 6px; font-size: 11px;"
                f" padding: 0 12px; color: {self._c('text')}; }}"
                f"QPushButton:checked {{ background: {self._c('accent')};"
                " color: white; border-color: transparent; }")
            btn.clicked.connect(lambda checked=False, k=key: self._set_report_mode(k))
            modes.addWidget(btn)
            self._report_mode_btns[key] = btn
        self._report_mode_btns["basic"].setChecked(True)
        modes.addStretch()

        self._report_ai_btn = QPushButton("✨ AI 分析")
        self._report_ai_btn.setFixedHeight(26)
        self._report_ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._report_ai_btn.setStyleSheet(
            f"QPushButton {{ background: {self._c('accent')}; color: white;"
            " border: none; border-radius: 6px; font-size: 11px; padding: 0 12px; }"
            "QPushButton:disabled { background: #C9BCA8; }")
        self._report_ai_btn.clicked.connect(self._generate_ai_report)
        modes.addWidget(self._report_ai_btn)

        export_btn = QPushButton("导出")
        export_btn.setObjectName("secondaryBtn")
        export_btn.setFixedHeight(26)
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setToolTip("导出为 Markdown 文件（可直接当周报用）")
        export_btn.clicked.connect(lambda: self._export_report())
        modes.addWidget(export_btn)

        folder_btn = QPushButton("📁")
        folder_btn.setObjectName("secondaryBtn")
        folder_btn.setFixedHeight(26)
        folder_btn.setFixedWidth(34)
        folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        folder_btn.setToolTip("打开导出目录（导出的报告都在这里）")
        folder_btn.clicked.connect(self._open_report_folder)
        modes.addWidget(folder_btn)
        layout.addLayout(modes)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # 高度策略很关键：报告内容（概览+每日+应用+时段+任务+AI）展开后
        # 最小高度会到 900+ px，如果让滚动区跟着内容撑，它就会把整个卡片
        # 顶满、把可视区压到只剩两三行，反而看不到内容。
        # 正确做法是让滚动区**能收缩**，内容高度交给滚动条处理。
        scroll.setMinimumHeight(220)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred,
                             QSizePolicy.Policy.Ignored)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self._c('handle')};"
            " border-radius: 3px; min-height: 20px; }")
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        # 内层容器同样不能把高度要求往上传，否则滚动区又被顶满
        inner.setSizePolicy(QSizePolicy.Policy.Preferred,
                            QSizePolicy.Policy.Ignored)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        # 卡片式报告视图：按数据渲染，不再显示 Markdown 源码
        self._report_view = ReportView(self._c)
        # AI 分析面板固定在滚动区**上方** —— 它是 AI 版的核心价值，
        # 埋在滚动区底部的话用户会以为点了没反应
        self._report_ai_panel = AIPanel(self._c)
        self._report_view.ai_panel = self._report_ai_panel
        layout.addWidget(self._report_ai_panel)
        inner_layout.addWidget(self._report_view)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)
        return card

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
            # 历史条数用当前代码里的默认值（老配置文件里存的是旧值 20，
            # 直接沿用会让"提升到 30"对老用户不生效）
            from pet_engine.pet_ai import AIConfig as _AIConfig
            config.max_history = _AIConfig().max_history
            config.save()

            if self._pet:
                self._pet._ai_config = config
                self._pet._ai.config = config
                self._bind_agent_tools()
                if hasattr(self._pet, '_proactive'):
                    self._pet._proactive._ai = self._pet._ai

            self._status.setText("✅ AI 设置已保存")
            # 只改状态栏那一行小字太不显眼，用户会以为"点了没反应"
            self._toast("✅ AI 设置已保存")
        except Exception as e:
            self._status.setText(f"❌ 保存失败: {e}")
            self._toast("❌ 保存失败：%s" % str(e)[:60])

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

    def _capture_theme_styles(self):
        """构建界面后，把「用到了配色」的控件样式存成可套色的模板。

        做法：记录构建期间屏幕/工具栏总共用过哪些配色键（_theme_keys_used），
        然后逐个控件把样式表里的**当前颜色值**换回 {key} 占位符。
        切主题时用新颜色替换占位符再设回去 —— 这样任何在构建期用
        self._c(...) 上色的控件都会自动跟随主题，
        不需要在 _refresh_inline_styles 里逐个登记（漏登记就会出现
        "深色模式下还留着浅色"）。

        只处理带样式的控件；运行时动态改样式的控件（如按钮选中态）
        本来就会在各自逻辑里重新上色。
        """
        used = getattr(self, "_theme_keys_used", None)
        if not used:
            return
        # 当前颜色值 -> 键名（只在浅色/深色各自取值下匹配）
        value_to_key = {}
        for key in used:
            try:
                value_to_key.setdefault(self._c(key).lower(), key)
            except Exception:  # noqa: BLE001
                continue
        captured = []
        for w in self.findChildren(QWidget):
            try:
                ss = w.styleSheet()
            except RuntimeError:
                continue
            if not ss:
                continue
            template = ss
            hit = False
            for value, key in value_to_key.items():
                if value in template.lower():
                    # 大小写不敏感替换
                    template = re.sub(re.escape(value), "{%s}" % key,
                                      template, flags=re.IGNORECASE)
                    hit = True
            if hit:
                captured.append((w, template))
        self._theme_styles = captured

    def _reapply_theme_styles(self):
        """切主题后，把捕获的模板用新配色重新套一遍。

        用正则逐个替换 {key} 占位符，**不用 str.format** ——
        模板里还留着 CSS 自己的花括号，format 会解析失败。
        """
        keys = getattr(self, "_theme_keys_used", ())
        pattern = re.compile(r"\{(" + "|".join(re.escape(k) for k in keys) + r")\}")
        for w, template in getattr(self, "_theme_styles", []):
            try:
                w.setStyleSheet(pattern.sub(lambda m: self._c(m.group(1)),
                                            template))
            except RuntimeError:
                continue      # 控件已销毁

    def _redraw_charts_for_theme(self):
        """切主题后重画统计图（用当前选中的日期，没有就用今天）。

        图表是 matplotlib 渲染成 PNG 再当 QPixmap 显示的，
        样式表管不到它的文字颜色 —— 不重画就会在暗底上留着深色字。
        """
        # 目标环也在这里刷新：它的颜色是 set_state 传进去的（不是样式表），
        # 切主题不刷新就会留着上一套配色（深色下表现为白圈）
        for ring in (getattr(self, "_goal_ring", None),
                     getattr(self, "_data_goal_ring", None),
                     getattr(self, "_flow_goal_ring", None)):
            if ring is not None:
                try:
                    ring.set_colors(self._c('accent'), self._c('border'),
                                    self._c('text'))
                except (RuntimeError, AttributeError):
                    pass
        if getattr(self, "_goal_tracker", None) is not None:
            try:
                self._refresh_goal()
            except Exception as exc:  # noqa: BLE001
                print("[Goal] 主题切换刷新失败: %s" % exc)

        if not getattr(self, "_study_charts_drawn", False):
            return
        date_str = getattr(self, "_selected_chart_date", "") or \
            datetime.now().strftime("%Y-%m-%d")
        try:
            self._refresh_charts_for_date(date_str)
        except Exception as exc:  # noqa: BLE001
            print("[Charts] 主题切换重画失败: %s" % exc)

    def _refresh_inline_styles(self):
        """Re-apply all inline styles after dark mode toggle."""
        # 先跑自动重刷：覆盖所有在构建期用 self._c(...) 上色的控件
        self._reapply_theme_styles()
        if hasattr(self, "_drop_area"):
            try:
                self._drop_area.set_dark(self._is_dark_mode)
            except (RuntimeError, AttributeError):
                pass
        # 图表是渲染成 PNG 再显示的，CSS 管不到 —— 必须重画才会换色
        self._redraw_charts_for_theme()
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

        if getattr(self, '_desktop_tools_page', None) is not None:
            self._desktop_tools_page.restyle()

        if getattr(self, '_flow_window', None) is not None:
            self._flow_window.apply_theme()

        if getattr(self, '_flow_btn', None) is not None:
            self._flow_btn.setStyleSheet(f"""
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
                    stop:0 {DARK_HEADER}, stop:1 {DARK_BG});
            }}
            QLabel#headerTitle {{
                font-size: 24px;
                font-weight: bold;
                color: {DARK_ACCENT};
                font-family: "Segoe UI", "Microsoft YaHei";
            }}
            QLabel#headerSub {{
                font-size: 11px;
                color: {DARK_TEXT_SEC};
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
                color: {DARK_ACCENT};
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
                background: {DARK_BORDER};
                border-color: {DARK_ACCENT};
            }}
            QPushButton:pressed {{
                background: {DARK_BORDER};
            }}
            QPushButton:disabled {{
                background: {DARK_BG};
                color: {DARK_TEXT_SEC};
                border-color: {DARK_CARD};
            }}

            /* 主按钮在深色下改用描边式：原来是一整块高亮金色，
               在暗底上成为整屏最抢眼的元素，把视线从内容上拉走。
               现在只留金色描边+金字，品牌色还在，但不再喧宾夺主。 */
            QPushButton#startBtn {{
                background: {DARK_BG};
                color: {DARK_ACCENT};
                border: 1px solid {DARK_ACCENT};
                font-weight: bold;
                font-size: 13px;
                border-radius: 8px;
            }}
            QPushButton#startBtn:hover {{
                background: {DARK_HOVER};
                color: {DARK_ACCENT_HOVER};
                border-color: {DARK_ACCENT_HOVER};
            }}
            QPushButton#startBtn:disabled {{
                background: {DARK_CARD};
                color: {DARK_TEXT_SEC};
                border-color: {DARK_BORDER};
            }}

            QPushButton#actionBtn {{
                background: {DARK_CARD};
                border: 1px solid {DARK_ACCENT};
                color: {DARK_TEXT};
                font-size: 12px;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 6px;
            }}
            QPushButton#actionBtn:hover {{
                background: {DARK_BORDER};
                border-color: {DARK_ACCENT_HOVER};
            }}
            QPushButton#actionBtn:disabled {{
                background: {DARK_BG};
                color: {DARK_TEXT_SEC};
                border-color: {DARK_CARD};
            }}

            /* Sliders */
            QSlider::groove:horizontal {{
                height: 5px;
                background: {DARK_CARD};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 16px;
                height: 16px;
                background: {DARK_ACCENT};
                border-radius: 8px;
                margin: -6px 0;
            }}
            QSlider::handle:horizontal:hover {{
                background: {DARK_ACCENT_HOVER};
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
                border: 2px solid {DARK_TEXT_SEC};
            }}
            QCheckBox::indicator:checked {{
                background: {DARK_ACCENT};
                border-color: {DARK_ACCENT};
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
                background: {DARK_BORDER};
            }}
            QPushButton[modeToggle="true"]:checked {{
                background: {DARK_BORDER};
                border-color: {DARK_ACCENT};
                color: {DARK_ACCENT};
                font-weight: bold;
            }}

            /* Scrollbars */
            QScrollBar:horizontal {{
                height: 6px;
                background: transparent;
            }}
            QScrollBar::handle:horizontal {{
                background: {DARK_BORDER};
                border-radius: 3px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {DARK_BORDER};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}

            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {DARK_BORDER};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {DARK_BORDER};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            /* Pet thumbnails */
            QPushButton[petThumb="true"] {{
                border: 2px solid {DARK_BORDER};
                border-radius: 8px;
                background: {DARK_CARD};
            }}
            QPushButton[petThumb="true"]:hover {{
                border-color: {DARK_ACCENT};
                background: {DARK_BORDER};
            }}
            QPushButton[petThumb="true"]:checked {{
                border: 3px solid {DARK_ACCENT};
                background: {DARK_BORDER};
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
                background: {DARK_CARD};
            }}
            QPushButton[showcaseThumb="true"]:hover {{
                border-color: {DARK_ACCENT};
                background: {DARK_BORDER};
            }}
            QPushButton[showcaseThumb="true"]:checked {{
                border: 3px solid {DARK_ACCENT};
                background: {DARK_BORDER};
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
                border-color: {DARK_ACCENT};
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
