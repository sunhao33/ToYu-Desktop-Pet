"""Settings dialog for YoTu desktop pet."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QSlider, QCheckBox, QComboBox, QPushButton,
    QGroupBox, QSpinBox, QDoubleSpinBox, QFrame, QScrollArea,
    QLineEdit
)

ACCENT = "#C49A3C"
DARK = "#3E2723"
LIGHT_BG = "#FFF8F0"
CARD_BG = "#FFFFFF"
TEXT = "#2C1810"
TEXT_SEC = "#8B7355"
BORDER = "#E8D5C0"

class SettingsDialog(QDialog):
    """Settings dialog with tabbed interface."""

    scale_changed = pyqtSignal(float)
    speed_changed = pyqtSignal(float)
    dark_mode_changed = pyqtSignal(bool)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("⚙️ 设置")
        self.setMinimumSize(500, 550)
        self.resize(520, 580)
        self.setStyleSheet(f"""
            QDialog {{
                background: {LIGHT_BG};
            }}
            QTabWidget::pane {{
                border: 1px solid {BORDER};
                border-radius: 8px;
                background: {CARD_BG};
            }}
            QTabBar::tab {{
                background: #F5EDE0;
                color: {TEXT_SEC};
                border: 1px solid {BORDER};
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                padding: 8px 16px;
                margin-right: 2px;
                font-size: 12px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {CARD_BG};
                color: {TEXT};
                border-bottom: 1px solid {CARD_BG};
            }}
            QGroupBox {{
                font-size: 12px;
                font-weight: bold;
                color: {DARK};
                border: 1px solid {BORDER};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }}
            QLabel {{
                color: {TEXT};
                font-size: 11px;
            }}
            QCheckBox {{
                spacing: 6px;
                font-size: 11px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid {BORDER};
                background: white;
            }}
            QCheckBox::indicator:checked {{
                background: {ACCENT};
                border-color: {ACCENT};
            }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: {BORDER};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                border: none;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT};
                border-radius: 3px;
            }}
            QSpinBox, QDoubleSpinBox, QComboBox {{
                padding: 4px 8px;
                border: 1px solid {BORDER};
                border-radius: 6px;
                background: white;
                color: {TEXT};
                font-size: 11px;
            }}
            QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
                border-color: {ACCENT};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background: white;
                color: {TEXT};
                border: 1px solid {BORDER};
                selection-background-color: #FFF3E0;
                selection-color: {TEXT};
                outline: none;
                font-size: 11px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 8px;
                min-height: 24px;
            }}
            QPushButton {{
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("⚙️ YoTu 设置")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {DARK};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._create_display_tab(), "🎨 显示")
        tabs.addTab(self._create_behavior_tab(), "🐾 行为")
        tabs.addTab(self._create_interaction_tab(), "💬 交互")
        tabs.addTab(self._create_advanced_tab(), "⚡ 高级")
        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("🔄 恢复默认")
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: #95A5A6;
                color: white;
            }}
            QPushButton:hover {{
                background: #7F8C8D;
            }}
        """)
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {BORDER};
                color: {TEXT};
            }}
            QPushButton:hover {{
                background: #D4C4A8;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT};
                color: white;
            }}
            QPushButton:hover {{
                background: #D4AE50;
            }}
        """)
        save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _create_display_tab(self):
        """显示设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        size_group = QGroupBox("宠物大小")
        size_layout = QVBoxLayout(size_group)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("缩放比例:"))

        self._scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._scale_slider.setRange(50, 200)
        self._scale_slider.setValue(100)
        self._scale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._scale_slider.setTickInterval(25)
        self._scale_slider.valueChanged.connect(self._on_scale_change)
        scale_row.addWidget(self._scale_slider)

        self._scale_label = QLabel("100%")
        self._scale_label.setStyleSheet(f"font-weight: bold; color: {ACCENT}; min-width: 45px;")
        scale_row.addWidget(self._scale_label)

        size_layout.addLayout(scale_row)

        hint = QLabel("💡 50% ~ 200%，建议 100%")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        size_layout.addWidget(hint)

        layout.addWidget(size_group)

        window_group = QGroupBox("窗口")
        window_layout = QVBoxLayout(window_group)

        self._always_on_top = QCheckBox("始终置顶（宠物窗口永远在最前面）")
        window_layout.addWidget(self._always_on_top)

        self._dark_mode = QCheckBox("深色模式（夜间护眼）")
        self._dark_mode.stateChanged.connect(lambda s: self.dark_mode_changed.emit(s == Qt.CheckState.Checked.value))
        window_layout.addWidget(self._dark_mode)

        layout.addWidget(window_group)

        opacity_group = QGroupBox("透明度")
        opacity_layout = QVBoxLayout(opacity_group)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("窗口透明度:"))

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(30, 100)
        self._opacity_slider.setValue(100)
        self._opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._opacity_slider.setTickInterval(10)
        self._opacity_slider.valueChanged.connect(self._on_opacity_change)
        opacity_row.addWidget(self._opacity_slider)

        self._opacity_label = QLabel("100%")
        self._opacity_label.setStyleSheet(f"font-weight: bold; color: {ACCENT}; min-width: 45px;")
        opacity_row.addWidget(self._opacity_label)

        opacity_layout.addLayout(opacity_row)

        hint = QLabel("💡 降低透明度可以让宠物半透明")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        opacity_layout.addWidget(hint)

        layout.addWidget(opacity_group)

        layout.addStretch()
        return widget

    def _create_behavior_tab(self):
        """行为设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        speed_group = QGroupBox("移动速度")
        speed_layout = QVBoxLayout(speed_group)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("最大速度:"))

        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(1, 10)
        self._speed_slider.setValue(3)
        self._speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._speed_slider.setTickInterval(1)
        self._speed_slider.valueChanged.connect(self._on_speed_change)
        speed_row.addWidget(self._speed_slider)

        self._speed_label = QLabel("3")
        self._speed_label.setStyleSheet(f"font-weight: bold; color: {ACCENT}; min-width: 20px;")
        speed_row.addWidget(self._speed_label)

        speed_layout.addLayout(speed_row)

        hint = QLabel("💡 1=慢悠悠，5=正常，10=飞快")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        speed_layout.addWidget(hint)

        layout.addWidget(speed_group)

        idle_group = QGroupBox("发呆时间")
        idle_layout = QVBoxLayout(idle_group)

        idle_form = QHBoxLayout()
        idle_form.setSpacing(8)

        lbl1 = QLabel("最短:")
        lbl1.setFixedWidth(36)
        lbl1.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        idle_form.addWidget(lbl1)
        self._idle_min = QSpinBox()
        self._idle_min.setRange(1, 30)
        self._idle_min.setValue(3)
        self._idle_min.setSuffix(" 秒")
        self._idle_min.setFixedWidth(80)
        idle_form.addWidget(self._idle_min)

        idle_form.addSpacing(16)

        lbl2 = QLabel("最长:")
        lbl2.setFixedWidth(36)
        lbl2.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        idle_form.addWidget(lbl2)
        self._idle_max = QSpinBox()
        self._idle_max.setRange(5, 60)
        self._idle_max.setValue(15)
        self._idle_max.setSuffix(" 秒")
        self._idle_max.setFixedWidth(80)
        idle_form.addWidget(self._idle_max)

        idle_form.addStretch()
        idle_layout.addLayout(idle_form)

        hint = QLabel("💡 宠物走路间隙的休息时间")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        idle_layout.addWidget(hint)

        layout.addWidget(idle_group)

        mode_group = QGroupBox("互动模式")
        mode_layout = QVBoxLayout(mode_group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems([
            "自由漫步 - 宠物自己到处走",
            "跟随鼠标 - 宠物跟着鼠标走",
            "原地待命 - 宠物待在原地不动"
        ])
        mode_layout.addWidget(self._mode_combo)

        hint = QLabel("💡 跟随模式下宠物会追着鼠标走")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        mode_layout.addWidget(hint)

        layout.addWidget(mode_group)

        time_group = QGroupBox("时间感知")
        time_layout = QVBoxLayout(time_group)

        self._time_awareness = QCheckBox("启用时间感知（宠物会根据时间打招呼）")
        time_layout.addWidget(self._time_awareness)

        hint = QLabel("💡 早上说早安，晚上说晚安，还会提醒你休息")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        time_layout.addWidget(hint)

        layout.addWidget(time_group)

        layout.addStretch()
        return widget

    def _create_interaction_tab(self):
        """交互设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        affection_group = QGroupBox("好感度系统")
        affection_layout = QVBoxLayout(affection_group)

        self._affection_enabled = QCheckBox("启用好感度系统")
        affection_layout.addWidget(self._affection_enabled)

        decay_row = QHBoxLayout()
        decay_row.addWidget(QLabel("衰减速度:"))
        self._decay_speed = QComboBox()
        self._decay_speed.addItems(["慢速 (每5分钟-1)", "正常 (每3分钟-1)", "快速 (每1分钟-1)"])
        self._decay_speed.setCurrentIndex(1)
        decay_row.addWidget(self._decay_speed)
        affection_layout.addLayout(decay_row)

        hint = QLabel("💡 好感度越高，宠物越开心！多互动可以提升好感度")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        affection_layout.addWidget(hint)

        layout.addWidget(affection_group)

        feed_group = QGroupBox("喂食")
        feed_layout = QVBoxLayout(feed_group)

        cooldown_row = QHBoxLayout()
        cooldown_row.addWidget(QLabel("喂食冷却:"))
        self._feed_cooldown = QSpinBox()
        self._feed_cooldown.setRange(10, 120)
        self._feed_cooldown.setValue(30)
        self._feed_cooldown.setSuffix(" 秒")
        cooldown_row.addWidget(self._feed_cooldown)
        feed_layout.addLayout(cooldown_row)

        hint = QLabel("💡 两次喂食之间的最短间隔")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        feed_layout.addWidget(hint)

        layout.addWidget(feed_group)

        house_group = QGroupBox("小房子")
        house_layout = QVBoxLayout(house_group)

        self._house_enabled = QCheckBox("显示小房子（宠物的家）")
        house_layout.addWidget(self._house_enabled)

        hint = QLabel("💡 宠物走累了会回房子里休息")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        house_layout.addWidget(hint)

        layout.addWidget(house_group)

        layout.addStretch()
        return widget

    def _create_advanced_tab(self):
        """高级设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        pomo_group = QGroupBox("番茄钟")
        pomo_layout = QVBoxLayout(pomo_group)

        self._pomo_enabled = QCheckBox("启用番茄钟提醒")
        pomo_layout.addWidget(self._pomo_enabled)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("提醒间隔:"))
        self._pomo_interval = QSpinBox()
        self._pomo_interval.setRange(5, 120)
        self._pomo_interval.setValue(25)
        self._pomo_interval.setSuffix(" 分钟")
        interval_row.addWidget(self._pomo_interval)
        pomo_layout.addLayout(interval_row)

        hint = QLabel("💡 工作一段时间后，宠物会提醒你休息")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        pomo_layout.addWidget(hint)

        layout.addWidget(pomo_group)

        startup_group = QGroupBox("启动")
        startup_layout = QVBoxLayout(startup_group)

        self._auto_start = QCheckBox("开机自启动")
        startup_layout.addWidget(self._auto_start)

        self._auto_start_pet = QCheckBox("启动程序时自动开始宠物")
        startup_layout.addWidget(self._auto_start_pet)

        hint = QLabel("💡 开机后自动启动，省去每次手动开启")
        hint.setStyleSheet(f"color: {TEXT_SEC}; font-size: 10px;")
        startup_layout.addWidget(hint)

        layout.addWidget(startup_group)

        about_group = QGroupBox("关于")
        about_layout = QVBoxLayout(about_group)

        about_text = QLabel(
            "🥔 YoTu 桌面宠物 v0.35\n"
            "一个可爱的像素风桌面宠物\n\n"
            "功能：喂食、散步、番茄钟、拼豆编辑、好感度系统\n"
            "数据存储：~/.desktop_pet/"
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px; line-height: 1.5;")
        about_layout.addWidget(about_text)

        layout.addWidget(about_group)

        layout.addStretch()
        return widget

    def _on_scale_change(self, value):
        self._scale_label.setText(f"{value}%")
        self.scale_changed.emit(value / 100.0)

    def _on_speed_change(self, value):
        self._speed_label.setText(str(value))
        self.speed_changed.emit(float(value))

    def _on_opacity_change(self, value):
        self._opacity_label.setText(f"{value}%")

    def _load_settings(self):
        """从设置加载当前值"""
        scale = self.settings.animation_scale
        self._scale_slider.setValue(int(scale * 100))
        self._always_on_top.setChecked(self.settings.always_on_top)

        speed = self.settings.walking_speed_max
        self._speed_slider.setValue(int(speed))

        mode = self.settings.interaction_mode
        mode_map = {"free": 0, "follow": 1, "stay": 2}
        self._mode_combo.setCurrentIndex(mode_map.get(mode, 0))

        self._time_awareness.setChecked(self.settings.time_awareness_enabled)

        self._house_enabled.setChecked(self.settings.house_enabled)

        self._pomo_enabled.setChecked(self.settings.pomodoro_enabled)
        self._pomo_interval.setValue(self.settings.pomodoro_interval)

        self._auto_start.setChecked(self.settings.auto_start)

    def _save_settings(self):
        """保存设置"""
        self.settings.animation_scale = self._scale_slider.value() / 100.0
        self.settings.always_on_top = self._always_on_top.isChecked()

        speed = float(self._speed_slider.value())
        self.settings.walking_speed_max = speed
        self.settings.walking_speed_min = max(0.3, speed * 0.3)

        mode_map = {0: "free", 1: "follow", 2: "stay"}
        self.settings.interaction_mode = mode_map.get(self._mode_combo.currentIndex(), "free")

        self.settings.time_awareness_enabled = self._time_awareness.isChecked()

        self.settings.house_enabled = self._house_enabled.isChecked()

        self.settings.pomodoro_enabled = self._pomo_enabled.isChecked()
        self.settings.pomodoro_interval = self._pomo_interval.value()

        self.settings.auto_start = self._auto_start.isChecked()

    def _reset_defaults(self):
        """恢复默认设置"""
        self._scale_slider.setValue(100)
        self._speed_slider.setValue(3)
        self._always_on_top.setChecked(True)
        self._mode_combo.setCurrentIndex(0)
        self._time_awareness.setChecked(True)
        self._house_enabled.setChecked(False)
        self._pomo_enabled.setChecked(False)
        self._pomo_interval.setValue(25)
        self._auto_start.setChecked(False)
        self._opacity_slider.setValue(100)

    def _save_and_close(self):
        """保存并关闭"""
        self._save_settings()
        self.accept()

    def get_opacity(self):
        """获取透明度值"""
        return self._opacity_slider.value() / 100.0

    def is_dark_mode(self):
        """获取深色模式状态"""
        return self._dark_mode.isChecked()
