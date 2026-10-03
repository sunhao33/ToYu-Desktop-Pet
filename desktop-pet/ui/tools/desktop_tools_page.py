"""Desktop-tools page: clipboard history and eye-care reminder."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCheckBox, QScrollArea, QFrame, QApplication, QSpinBox
)

CLIP_PREVIEW_CHARS = 60
# 预览标签的最小宽度：给它一个明确下限，行宽才不会被长文本撑开
CLIP_PREVIEW_MIN_W = 120


def _preview(text):
    one_line = " ".join(text.split())
    if len(one_line) > CLIP_PREVIEW_CHARS:
        return one_line[:CLIP_PREVIEW_CHARS] + "…"
    return one_line


class _ElideLabel(QLabel):
    """单行显示、超宽自动省略，且最小宽度固定。

    普通 QLabel 的最小宽度由文字长度决定：复制一段长文本就会把整行撑宽，
    进而把卡片撑出可视区（表现为右侧内容看不见）。这里改成按控件宽度省略。
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setMinimumWidth(CLIP_PREVIEW_MIN_W)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

    def setFullText(self, text):
        self._full_text = text
        self.setToolTip(text[:2000])
        self._apply_elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self):
        fm = QFontMetrics(self.font())
        avail = max(self.width() - 4, 40)
        super().setText(fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight, avail))


class DesktopToolsPage(QWidget):
    """Clipboard history + eye-care reminder, driven by DesktopToolsHub."""

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.settings = owner.settings
        self._last_history = []
        self.setStyleSheet("background: transparent;")

        row = QHBoxLayout(self)
        row.setSpacing(16)
        row.setContentsMargins(20, 16, 20, 14)
        row.addWidget(self._build_clipboard_card(), 2)
        row.addWidget(self._build_eye_care_card(), 1)

    def restyle(self):
        """Re-apply themed colors after a light/dark switch."""
        self._clip_toggle.setStyleSheet(
            f"color: {self.owner._c('text')}; background: transparent;"
        )
        self._clip_count.setStyleSheet(
            f"color: {self.owner._c('text2')}; font-size: 11px; background: transparent;"
        )
        self._eye_toggle.setStyleSheet(
            f"color: {self.owner._c('text')}; background: transparent;"
        )
        for label in self._spin_labels:
            label.setStyleSheet(
                f"color: {self.owner._c('text')}; background: transparent;"
            )
        self._eye_status.setStyleSheet(
            f"color: {self.owner._c('accent')}; font-size: 12px; font-weight: bold;"
            " background: transparent; padding-top: 4px;"
        )
        self._eye_note.setStyleSheet(
            f"color: {self.owner._c('text2')}; font-size: 10px; background: transparent;"
        )
        self.refresh_clipboard(self._last_history)

    # ── clipboard ───────────────────────────────────────────
    def _build_clipboard_card(self):
        card = self.owner._make_card("📋 剪贴板历史")
        layout = card.layout()
        layout.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._clip_toggle = QCheckBox("记录剪贴板")
        self._clip_toggle.setChecked(self.settings.clipboard_enabled)
        self._clip_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clip_toggle.setStyleSheet(
            f"color: {self.owner._c('text')}; background: transparent;"
        )
        self._clip_toggle.toggled.connect(self._on_clip_toggle)
        bar.addWidget(self._clip_toggle)

        self._clip_count = QLabel("")
        self._clip_count.setStyleSheet(
            f"color: {self.owner._c('text2')}; font-size: 11px; background: transparent;"
        )
        bar.addWidget(self._clip_count)
        bar.addStretch()

        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("secondaryBtn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFixedHeight(26)
        clear_btn.setToolTip("清空全部剪贴板历史")
        clear_btn.clicked.connect(self._on_clear_clipboard)
        bar.addWidget(clear_btn)
        layout.addLayout(bar)

        self._clip_scroll = QScrollArea()
        self._clip_scroll.setWidgetResizable(True)
        self._clip_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._clip_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background: {self.owner._c('handle')};"
            " border-radius: 3px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        self._clip_container = QWidget()
        self._clip_container.setStyleSheet("background: transparent;")
        self._clip_list = QVBoxLayout(self._clip_container)
        self._clip_list.setContentsMargins(0, 0, 0, 0)
        self._clip_list.setSpacing(6)
        self._clip_list.addStretch()
        self._clip_scroll.setWidget(self._clip_container)
        layout.addWidget(self._clip_scroll, 1)

        self.refresh_clipboard([])
        return card

    def _on_clip_toggle(self, checked):
        hub = self.owner._tools_hub
        if hub:
            hub.clipboard.set_enabled(checked)
        else:
            self.settings.clipboard_enabled = checked

    def _on_clear_clipboard(self):
        hub = self.owner._tools_hub
        if hub:
            hub.clipboard.clear()
        else:
            self.settings.clipboard_history = []
        self.refresh_clipboard([])

    def refresh_clipboard(self, history):
        self._last_history = list(history)
        while self._clip_list.count() > 1:
            item = self._clip_list.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not history:
            empty = QLabel("还没有记录 · 复制任意文字就会出现在这里")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {self.owner._c('text2')}; font-size: 12px; padding: 24px;"
            )
            self._clip_list.insertWidget(0, empty)
            self._clip_count.setText("0 条")
            return

        for index, entry in enumerate(history):
            self._clip_list.insertWidget(index, self._make_clip_row(entry))
        self._clip_count.setText(f"{len(history)} 条")

    def _make_clip_row(self, entry):
        row = QFrame()
        row.setObjectName("clipRow")
        row.setStyleSheet(
            f"QFrame#clipRow {{ background: {self.owner._c('tab_bg')};"
            f" border: 1px solid {self.owner._c('border')}; border-radius: 8px; }}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(8)

        text = entry.get("text", "")
        preview = _ElideLabel(_preview(text))
        preview.setFullText(_preview(text))
        preview.setStyleSheet(f"color: {self.owner._c('text')}; font-size: 12px; background: transparent;")
        layout.addWidget(preview, 1)

        stamp = QLabel(entry.get("time", ""))
        stamp.setStyleSheet(f"color: {self.owner._c('text2')}; font-size: 10px; background: transparent;")
        layout.addWidget(stamp)

        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("secondaryBtn")
        copy_btn.setFixedHeight(24)
        copy_btn.setMinimumWidth(44)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda checked=False, t=text: self._copy_again(t))
        layout.addWidget(copy_btn)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("从历史中删除这一条")
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            f" color: {self.owner._c('text2')}; font-size: 12px; }}"
            f"QPushButton:hover {{ color: #D9534F; }}"
        )
        del_btn.clicked.connect(lambda checked=False, t=text: self._remove_entry(t))
        layout.addWidget(del_btn)
        return row

    def _copy_again(self, text):
        QApplication.clipboard().setText(text)
        if self.owner._status:
            self.owner._status.setText("已复制回剪贴板")

    def _remove_entry(self, text):
        hub = self.owner._tools_hub
        if not hub:
            return
        hub.clipboard._history = [
            item for item in hub.clipboard.history if item["text"] != text
        ]
        hub.clipboard._save()
        self.refresh_clipboard(hub.clipboard.history)

    # ── eye care ────────────────────────────────────────────
    def _build_eye_care_card(self):
        card = self.owner._make_card("👀 护眼提醒")
        layout = card.layout()
        layout.setSpacing(10)

        self._eye_toggle = QCheckBox("定时提醒远眺")
        self._eye_toggle.setChecked(self.settings.eye_care_enabled)
        self._eye_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._eye_toggle.setStyleSheet(
            f"color: {self.owner._c('text')}; background: transparent;"
        )
        self._eye_toggle.toggled.connect(self._on_eye_toggle)
        layout.addWidget(self._eye_toggle)

        self._spin_labels = []
        work_row = QHBoxLayout()
        work_row.setSpacing(6)
        work_label = QLabel("专注")
        work_label.setStyleSheet(f"color: {self.owner._c('text')}; background: transparent;")
        self._spin_labels.append(work_label)
        work_row.addWidget(work_label)
        self._eye_work_spin = QSpinBox()
        self._eye_work_spin.setRange(1, 240)
        self._eye_work_spin.setValue(self.settings.eye_care_work_minutes)
        self._eye_work_spin.setSuffix(" 分钟")
        self._eye_work_spin.valueChanged.connect(self._on_eye_intervals)
        work_row.addWidget(self._eye_work_spin, 1)
        layout.addLayout(work_row)

        rest_row = QHBoxLayout()
        rest_row.setSpacing(6)
        rest_label = QLabel("休息")
        rest_label.setStyleSheet(f"color: {self.owner._c('text')}; background: transparent;")
        self._spin_labels.append(rest_label)
        rest_row.addWidget(rest_label)
        self._eye_rest_spin = QSpinBox()
        self._eye_rest_spin.setRange(1, 60)
        self._eye_rest_spin.setValue(self.settings.eye_care_rest_minutes)
        self._eye_rest_spin.setSuffix(" 分钟")
        self._eye_rest_spin.valueChanged.connect(self._on_eye_intervals)
        rest_row.addWidget(self._eye_rest_spin, 1)
        layout.addLayout(rest_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        for label, work, rest in (("20-20-20", 20, 1), ("45+5", 45, 5), ("60+10", 60, 10)):
            btn = QPushButton(label)
            btn.setObjectName("secondaryBtn")
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, w=work, r=rest: self._apply_eye_preset(w, r)
            )
            preset_row.addWidget(btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        self._eye_status = QLabel("")
        self._eye_status.setWordWrap(True)
        self._eye_status.setStyleSheet(
            f"color: {self.owner._c('accent')}; font-size: 12px; font-weight: bold;"
            " background: transparent; padding-top: 4px;"
        )
        layout.addWidget(self._eye_status)

        reset_btn = QPushButton("从现在重新计时")
        reset_btn.setObjectName("secondaryBtn")
        reset_btn.setFixedHeight(26)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._on_eye_reset)
        layout.addWidget(reset_btn)

        note = QLabel("到点后宠物会弹气泡提醒你，无需盯着这个窗口")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {self.owner._c('text2')}; font-size: 10px; background: transparent;")
        self._eye_note = note
        layout.addWidget(note)
        layout.addStretch()

        self.refresh_eye_care(None)
        return card

    def _on_eye_toggle(self, checked):
        hub = self.owner._tools_hub
        if hub:
            hub.eye_care.set_enabled(checked)
            self.refresh_eye_care(hub.eye_care)
        else:
            self.settings.eye_care_enabled = checked
            self.refresh_eye_care(None)

    def _on_eye_intervals(self):
        hub = self.owner._tools_hub
        if hub:
            hub.eye_care.set_intervals(
                self._eye_work_spin.value(), self._eye_rest_spin.value()
            )
            self.refresh_eye_care(hub.eye_care)

    def _apply_eye_preset(self, work, rest):
        self._eye_work_spin.blockSignals(True)
        self._eye_rest_spin.blockSignals(True)
        self._eye_work_spin.setValue(work)
        self._eye_rest_spin.setValue(rest)
        self._eye_work_spin.blockSignals(False)
        self._eye_rest_spin.blockSignals(False)
        if not self._eye_toggle.isChecked():
            self._eye_toggle.setChecked(True)
        else:
            self._on_eye_intervals()

    def _on_eye_reset(self):
        hub = self.owner._tools_hub
        if hub:
            hub.eye_care.reset()
            self.refresh_eye_care(hub.eye_care)

    def refresh_eye_care(self, eye_care):
        if eye_care is None:
            enabled = self.settings.eye_care_enabled
            text = "护眼提醒已关闭" if not enabled else (
                f"每 {self.settings.eye_care_work_minutes} 分钟提醒一次"
            )
        else:
            text = eye_care.status_text()
        self._eye_status.setText(text)

    # 只在页面可见时刷新倒计时，避免隐藏时每秒重绘
    def showEvent(self, event):
        super().showEvent(event)
        if self.owner._tools_hub:
            self.owner._tools_hub.notify_status = True
        self.refresh_eye_care(self.owner._tools_hub.eye_care if self.owner._tools_hub else None)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.owner._tools_hub:
            self.owner._tools_hub.notify_status = False
