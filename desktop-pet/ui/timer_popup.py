"""Timer popup for ToYu — matches main app warm potato palette."""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QListWidget, QFrame)


class TodoTimerPopup(QWidget):
    """Minimal timer popup."""

    timer_finished = pyqtSignal(str, int)

    def __init__(self, todo_text, todos=None, history=None, parent=None):
        super().__init__(parent)
        self._todo_text = todo_text
        self._todos = todos or []
        self._history = history or {}
        self._elapsed = 0
        self._running = True
        self._paused = False
        self._drag_pos = None
        self._active_task = todo_text

        self._init_ui()
        self._refresh_task_list()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _init_ui(self):
        self.setFixedSize(360, 300)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )

        self.setStyleSheet("""
            #bg {
                background: #FFF8F0;
                border: 1px solid #E8D5C0;
                border-radius: 12px;
            }
        """)

        root = QWidget(self)
        root.setObjectName("bg")
        root.setGeometry(0, 0, 360, 300)

        lay = QVBoxLayout(root)
        lay.setContentsMargins(18, 18, 18, 16)
        lay.setSpacing(10)

        # ── Top: title + close
        top = QHBoxLayout()
        top.setSpacing(0)

        title = QLabel("⏱ 专注计时")
        title.setStyleSheet("color: #C49A3C; font-size: 15px; font-weight: bold; background: transparent;")
        top.addWidget(title)
        top.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { color: #8B7355; background: transparent;"
            " border: none; border-radius: 11px; font-size: 13px; }"
            "QPushButton:hover { color: #3E2723; background: #E8D5C0; }"
        )
        close_btn.clicked.connect(self._on_close)
        top.addWidget(close_btn)
        lay.addLayout(top)

        # ── Task name
        self._task_label = QLabel(self._active_task)
        self._task_label.setWordWrap(True)
        self._task_label.setStyleSheet("color: #5C3D1E; font-size: 12px; background: transparent;")
        lay.addWidget(self._task_label)

        # ── Timer
        self._time_label = QLabel("00:00:00")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setStyleSheet(
            "color: #2C1810; font-size: 38px; font-weight: 500;"
            " background: white; border-radius: 10px; padding: 10px 0;"
            " border: 1px solid #E8D5C0;"
        )
        lay.addWidget(self._time_label)

        # ── Buttons
        btns = QHBoxLayout()
        btns.setSpacing(8)

        self._pause_btn = QPushButton("⏸ 暂停")
        self._pause_btn.setFixedHeight(30)
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.setStyleSheet(
            "QPushButton { color: #7A6230; background: #FFF8E1;"
            " border: 1px solid #F0E0B0; border-radius: 8px;"
            " padding: 0 14px; font-size: 12px; }"
            "QPushButton:hover { background: #FFF3C4; }"
        )
        self._pause_btn.clicked.connect(self._on_pause)
        btns.addWidget(self._pause_btn)

        done_btn = QPushButton("✓ 完成")
        done_btn.setFixedHeight(30)
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(
            "QPushButton { color: #4A7A28; background: #E8F5E0;"
            " border: 1px solid #C8E0B8; border-radius: 8px;"
            " padding: 0 14px; font-size: 12px; }"
            "QPushButton:hover { background: #D5EDCA; }"
        )
        done_btn.clicked.connect(self._on_done)
        btns.addWidget(done_btn)

        stop_btn = QPushButton("■ 结束")
        stop_btn.setFixedHeight(30)
        stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_btn.setStyleSheet(
            "QPushButton { color: #A05050; background: #FDE8E8;"
            " border: 1px solid #F0C8C8; border-radius: 8px;"
            " padding: 0 14px; font-size: 12px; }"
            "QPushButton:hover { background: #F8D4D4; }"
        )
        stop_btn.clicked.connect(self._on_stop)
        btns.addWidget(stop_btn)

        lay.addLayout(btns)

        # ── Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #E8D5C0;")
        lay.addWidget(sep)

        # ── Task list
        list_title = QLabel("📊 专注记录")
        list_title.setStyleSheet("color: #C49A3C; font-size: 12px; font-weight: bold; background: transparent;")
        lay.addWidget(list_title)

        self._task_list = QListWidget()
        self._task_list.setStyleSheet("""
            QListWidget {
                background: white; border: 1px solid #E8D5C0;
                border-radius: 8px; outline: none; padding: 2px;
            }
            QListWidget::item {
                padding: 5px 8px; color: #5C3D1E; font-size: 11px;
                border-radius: 4px;
            }
            QListWidget::item:hover { background: #FFF8F0; }
            QListWidget::item:selected { background: #FFF3E0; color: #C49A3C; }
        """)
        self._task_list.setMaximumHeight(90)
        self._task_list.itemClicked.connect(self._on_task_select)
        lay.addWidget(self._task_list)

    def _refresh_task_list(self):
        self._task_list.clear()
        for todo in self._todos:
            if todo.done:
                continue
            text = todo.text
            spent = self._history.get(text, 0)
            prefix = "● " if text == self._active_task else "    "
            if spent > 0:
                m = spent // 60
                s = spent % 60
                t = f" · {m}m{s}s" if m > 0 else f" · {s}s"
            else:
                t = ""
            self._task_list.addItem(f"{prefix}{text}{t}")

    def _on_task_select(self, item):
        txt = item.text().strip().lstrip("●").strip()
        for todo in self._todos:
            if todo.text == txt or txt.startswith(todo.text):
                self._active_task = todo.text
                self._task_label.setText(todo.text)
                self._refresh_task_list()
                break

    def _tick(self):
        if self._running and not self._paused:
            self._elapsed += 1
            h = self._elapsed // 3600
            m = (self._elapsed % 3600) // 60
            s = self._elapsed % 60
            self._time_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _on_pause(self):
        self._paused = not self._paused
        self._pause_btn.setText("▶ 继续" if self._paused else "⏸ 暂停")

    def _on_done(self):
        self._timer.stop()
        self.timer_finished.emit(self._active_task, self._elapsed)
        self.close()

    def _on_stop(self):
        self._timer.stop()
        self.close()

    def _on_close(self):
        self._timer.stop()
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
