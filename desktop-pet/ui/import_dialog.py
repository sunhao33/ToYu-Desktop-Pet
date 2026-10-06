"""Image import dialog with background removal preview."""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSlider, QFileDialog, QCheckBox, QGroupBox,
    QProgressBar, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

from image_processor.processor import (
    process_image, process_and_save, get_default_pet_path
)
from ui.theme import Palette, is_dark

class ImportDialog(QDialog):
    """Dialog for importing and processing a pet image."""

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._input_path = ""
        self._processed_image = None
        self.processed_image_path = ""
        self._app_data_dir = os.path.join(
            os.path.expanduser("~"), ".desktop_pet", "images"
        )
        # 跟随当前主题（原来写死浅色 + 蓝色系，深色下是一片白）
        self._dark = is_dark(settings)

        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Import Desktop Pet")
        self.setMinimumSize(520, 400)
        self.setStyleSheet(self._stylesheet())

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Choose Your Desktop Pet Image")
        title.setObjectName("title")
        layout.addWidget(title)

        preview_layout = QHBoxLayout()

        before_group = QGroupBox("Before")
        before_layout = QVBoxLayout(before_group)
        self._before_label = QLabel("No image selected")
        self._before_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._before_label.setMinimumSize(200, 200)
        _p = Palette(self._dark)
        self._before_label.setStyleSheet(
            "background: %s; border-radius: 8px; color: %s;"
            % (_p.input_bg, _p.text2))
        before_layout.addWidget(self._before_label)
        preview_layout.addWidget(before_group)

        arrow = QLabel("→")
        arrow.setObjectName("arrow")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(arrow)

        after_group = QGroupBox("After")
        after_layout = QVBoxLayout(after_group)
        self._after_label = QLabel("Processed result")
        self._after_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._after_label.setMinimumSize(200, 200)
        self._after_label.setStyleSheet(
            "background: %s; border-radius: 8px; color: %s;"
            "background-image: url(checkerboard);"
            % (_p.input_bg, _p.text2))
        after_layout.addWidget(self._after_label)
        preview_layout.addWidget(after_group)

        layout.addLayout(preview_layout)

        controls = QGroupBox("Processing Options")
        controls_layout = QVBoxLayout(controls)

        thresh_layout = QHBoxLayout()
        thresh_layout.addWidget(QLabel("White Threshold:"))
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(180, 255)
        self._threshold_slider.setValue(240)
        self._threshold_slider.setTickInterval(5)
        self._threshold_slider.valueChanged.connect(self._on_threshold_changed)
        thresh_layout.addWidget(self._threshold_slider)
        self._threshold_label = QLabel("240")
        self._threshold_label.setFixedWidth(35)
        thresh_layout.addWidget(self._threshold_label)
        controls_layout.addLayout(thresh_layout)

        self._ai_check = QCheckBox("Use AI background removal (rembg)")
        self._ai_check.setToolTip(
            "Uses deep learning for better results. Requires model download on first use."
        )
        self._ai_check.toggled.connect(self._on_ai_toggled)
        controls_layout.addWidget(self._ai_check)

        layout.addWidget(controls)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._select_btn = QPushButton("Select Image...")
        self._select_btn.setObjectName("primaryBtn")
        self._select_btn.clicked.connect(self._select_image)
        btn_layout.addWidget(self._select_btn)

        self._confirm_btn = QPushButton("Import as Pet")
        self._confirm_btn.setObjectName("primaryBtn")
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.clicked.connect(self._on_confirm)
        btn_layout.addWidget(self._confirm_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _select_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Pet Image",
            os.path.expanduser("~/Pictures"),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._input_path = path
            self._show_before(path)
            self._process_preview()
            self._confirm_btn.setEnabled(True)

    def _show_before(self, path):
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            self._before_label.setPixmap(pix)

    def _process_preview(self):
        if not self._input_path:
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        QApplication.processEvents()

        threshold = self._threshold_slider.value()
        use_ai = self._ai_check.isChecked()

        try:
            self._processed_image = process_image(
                self._input_path,
                threshold=threshold,
                use_ai=use_ai,
                output_size=(256, 256)
            )
            self._show_after()
        except Exception as e:
            self._after_label.setText(f"Error: {str(e)[:80]}")
            self._confirm_btn.setEnabled(False)
        finally:
            self._progress.setVisible(False)

    def _show_after(self):
        if self._processed_image is None:
            return

        data = self._processed_image.tobytes("raw", "RGBA")
        qimage = QImage(
            data,
            self._processed_image.width,
            self._processed_image.height,
            QImage.Format.Format_RGBA8888,
        )
        pix = QPixmap.fromImage(qimage)
        pix = pix.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        self._after_label.setPixmap(pix)

    def _on_threshold_changed(self, value):
        self._threshold_label.setText(str(value))

    def _on_ai_toggled(self, checked):
        self._threshold_slider.setEnabled(not checked)
        if self._input_path:
            self._process_preview()

    def _on_confirm(self):
        if not self._input_path:
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        QApplication.processEvents()

        try:
            threshold = self._threshold_slider.value()
            use_ai = self._ai_check.isChecked()

            if self._processed_image is None:
                self._processed_image = process_image(
                    self._input_path, threshold=threshold, use_ai=use_ai,
                    output_size=(256, 256)
                )

            self.processed_image_path = process_and_save(
                self._input_path, self._app_data_dir,
                threshold=threshold, use_ai=use_ai
            )
            self.accept()
        except Exception as e:
            self._after_label.setText(f"Error: {str(e)[:80]}")
        finally:
            self._progress.setVisible(False)

    def _stylesheet(self):
        """对话框整体样式（跟随主题）。

        原来写死浅色 + **蓝色系**（#4a90d9），既跟软件主色（土豆金
        #C49A3C）不是一家人，深色模式下还是一片白。
        """
        p = Palette(self._dark)
        return """
            QDialog {
                background: %(bg)s;
                color: %(text)s;
            }
            QLabel {
                color: %(text)s;
            }
            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: %(text)s;
            }
            QLabel#arrow {
                font-size: 28px;
                color: %(accent)s;
                font-weight: bold;
            }
            QGroupBox {
                font-weight: bold;
                color: %(text)s;
                border: 1px solid %(border)s;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton#primaryBtn {
                background: %(accent)s;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton#primaryBtn:hover {
                background: %(accent_h)s;
            }
            QPushButton#primaryBtn:disabled {
                background: %(disable_bg)s;
                color: %(disable_fg)s;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid %(border)s;
                background: %(card)s;
                color: %(text)s;
            }
            QPushButton:hover {
                background: %(hover_bg)s;
                border-color: %(accent)s;
            }
            QCheckBox {
                color: %(text)s;
            }
            QProgressBar {
                border: 1px solid %(border)s;
                border-radius: 4px;
                background: %(input_bg)s;
                color: %(text)s;
                text-align: center;
            }
            QProgressBar::chunk {
                background: %(accent)s;
                border-radius: 3px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: %(border)s;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                background: %(accent)s;
                border-radius: 8px;
                margin: -5px 0;
            }
        """ % {"bg": p.bg, "card": p.card, "text": p.text,
               "border": p.border, "accent": p.accent,
               "accent_h": p.accent_h, "hover_bg": p.hover_bg,
               "input_bg": p.input_bg, "disable_bg": p.disable_bg,
               "disable_fg": p.disable_fg}

    def set_dark(self, dark):
        """供主窗口切换主题时调用。"""
        self._dark = bool(dark)
        self.setStyleSheet(self._stylesheet())
        # 这两块预览底色是单独设的，要一起刷
        p = Palette(self._dark)
        for lbl, extra in ((getattr(self, "_before_label", None), ""),
                           (getattr(self, "_after_label", None),
                            "background-image: url(checkerboard);")):
            if lbl is not None:
                lbl.setStyleSheet(
                    "background: %s; border-radius: 8px; color: %s; %s"
                    % (p.input_bg, p.text2, extra))
