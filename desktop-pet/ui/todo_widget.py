"""Todo widget for ToYu Desktop Pet — with timer integration."""

import os
import json
from datetime import datetime, date
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QSizePolicy, QComboBox
)

# Theme colors
ACCENT = "#C49A3C"
ACCENT_HOVER = "#D4AE50"
DARK = "#3E2723"
MID = "#5C3D1E"
LIGHT_BG = "#FFF8F0"
CARD_BG = "#FFFFFF"
TEXT = "#2C1810"
TEXT_SEC = "#8B7355"
BORDER = "#E8D5C0"
SUCCESS = "#6B9B37"
DANGER = "#C0392B"
DONE_GREEN = "#4CAF50"
TIMER_COLOR = "#4A90D9"

# Data paths
DATA_DIR = os.path.join(os.path.expanduser("~"), ".desktop_pet")


class TodoItem:
    """Single todo item."""
    def __init__(self, text, done=False, created_at=None, priority="normal"):
        self.text = text
        self.done = done
        self.created_at = created_at or datetime.now().isoformat()
        self.priority = priority


class TodoWidget(QWidget):
    """Todo list widget with inline action buttons and timer."""

    task_completed = pyqtSignal()
    task_added = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.todos = []
        self.data_file = os.path.join(DATA_DIR, "todos.json")
        self.history_file = os.path.join(DATA_DIR, "task_history.json")
        self._timer_popups = []  # keep references
        self._load_todos()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Input row ──
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("添加待办事项...")
        self._input.setFixedHeight(32)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: {CARD_BG}; border: 1px solid {BORDER};
                border-radius: 6px; padding: 0 8px; color: {TEXT}; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
        """)
        self._input.returnPressed.connect(self._on_add)
        input_row.addWidget(self._input)

        self._priority_combo = QComboBox()
        self._priority_combo.addItems(["低", "普通", "高"])
        self._priority_combo.setCurrentIndex(1)
        self._priority_combo.setFixedHeight(32)
        self._priority_combo.setFixedWidth(72)
        self._priority_combo.setStyleSheet("""
            QComboBox {
                background: white; border: 1px solid #E8D5C0;
                border-radius: 6px; padding: 0 6px; color: #2C1810; font-size: 12px;
            }
            QComboBox::drop-down {
                border: none; width: 20px;
            }
            QComboBox::down-arrow {
                image: none; border-left: 4px solid transparent;
                border-right: 4px solid transparent; border-top: 5px solid #8B7355;
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background: white; color: #2C1810;
                border: 1px solid #E8D5C0; border-radius: 4px;
                selection-background-color: #FFF0E6;
                selection-color: #FF6B47;
                outline: none; font-size: 12px;
                padding: 2px;
            }
            QComboBox QAbstractItemView::item {
                padding: 4px 8px; min-height: 24px;
            }
        """)
        input_row.addWidget(self._priority_combo)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(32, 32)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: white; border: none;
                border-radius: 6px; font-size: 18px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
        """)
        add_btn.clicked.connect(self._on_add)
        input_row.addWidget(add_btn)

        layout.addLayout(input_row)

        # ── Filter row ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)

        self._filter_all = self._make_filter_btn("全部")
        self._filter_active = self._make_filter_btn("进行中")
        self._filter_done = self._make_filter_btn("已完成")
        self._filter_all.clicked.connect(lambda: self._set_filter("all"))
        self._filter_active.clicked.connect(lambda: self._set_filter("active"))
        self._filter_done.clicked.connect(lambda: self._set_filter("done"))
        filter_row.addWidget(self._filter_all)
        filter_row.addWidget(self._filter_active)
        filter_row.addWidget(self._filter_done)
        filter_row.addStretch()

        self._stats_label = QLabel("完成: 0/0")
        self._stats_label.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")
        filter_row.addWidget(self._stats_label)

        layout.addLayout(filter_row)

        # ── List ──
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: transparent; border: none;
                outline: none;
            }}
            QListWidget::item {{
                background: {CARD_BG}; border: 1px solid {BORDER};
                border-radius: 8px; margin: 2px 0; padding: 4px;
            }}
            QListWidget::item:hover {{
                border-color: {ACCENT};
            }}
        """)
        self._list.setSpacing(4)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(self._list)

        # ── Clear done button ──
        clear_btn = QPushButton("清除已完成")
        clear_btn.setFixedHeight(28)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid {BORDER}; border-radius: 6px;
                font-size: 11px;
            }}
            QPushButton:hover {{ color: {DANGER}; border-color: {DANGER}; }}
        """)
        clear_btn.clicked.connect(self._on_clear_done)
        layout.addWidget(clear_btn)

        self._current_filter = "all"
        self._update_filter_style()
        self._refresh_list()

    def _make_filter_btn(self, text):
        btn = QPushButton(text)
        btn.setFixedHeight(24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_SEC};
                border: 1px solid transparent; border-radius: 4px;
                padding: 0 8px; font-size: 11px;
            }}
            QPushButton:hover {{ color: {ACCENT}; }}
        """)
        return btn

    def _set_filter(self, f):
        self._current_filter = f
        self._update_filter_style()
        self._refresh_list()

    def _update_filter_style(self):
        for btn, key in [(self._filter_all, "all"), (self._filter_active, "active"), (self._filter_done, "done")]:
            if key == self._current_filter:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {ACCENT}; color: white;
                        border: 1px solid {ACCENT}; border-radius: 4px;
                        padding: 0 8px; font-size: 11px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; color: {TEXT_SEC};
                        border: 1px solid transparent; border-radius: 4px;
                        padding: 0 8px; font-size: 11px;
                    }}
                    QPushButton:hover {{ color: {ACCENT}; }}
                """)

    def _on_add(self):
        text = self._input.text().strip()
        if not text:
            return
        priority_map = {0: "low", 1: "normal", 2: "high"}
        priority = priority_map.get(self._priority_combo.currentIndex(), "normal")
        item = TodoItem(text, priority=priority)
        self.todos.append(item)
        self._input.clear()
        self._save_todos()
        self._refresh_list()
        QTimer.singleShot(100, self.task_added.emit)

    def _toggle_todo_by_ref(self, todo):
        todo.done = not todo.done
        if todo.done:
            self._record_task_done(todo.text)
            QTimer.singleShot(100, self.task_completed.emit)
        self._save_todos()
        self._refresh_list()

    def _delete_todo_by_ref(self, todo):
        if todo in self.todos:
            self.todos.remove(todo)
            self._save_todos()
            self._refresh_list()

    def _start_timer(self, todo):
        """Open a timer popup for the todo item."""
        from ui.timer_popup import TodoTimerPopup
        history = self._load_history()
        # Flatten history: {task_text: total_seconds}
        flat = {}
        for day_tasks in history.values():
            for t in day_tasks:
                text = t["text"]
                dur = t.get("duration", 0)
                flat[text] = flat.get(text, 0) + dur
        popup = TodoTimerPopup(todo.text, todos=self.todos, history=flat, parent=None)
        popup.timer_finished.connect(self._on_timer_finished)
        popup.show()
        self._timer_popups.append(popup)

    def _on_timer_finished(self, todo_text, elapsed):
        """Timer completed — record to history."""
        self._record_task_done(todo_text, elapsed)
        # Mark todo as done if it matches
        for t in self.todos:
            if t.text == todo_text and not t.done:
                t.done = True
                break
        self._save_todos()
        self._refresh_list()
        QTimer.singleShot(100, self.task_completed.emit)

    def _on_clear_done(self):
        self.todos = [t for t in self.todos if not t.done]
        self._save_todos()
        self._refresh_list()

    def _get_filtered_todos(self):
        if self._current_filter == "active":
            return [t for t in self.todos if not t.done]
        elif self._current_filter == "done":
            return [t for t in self.todos if t.done]
        return self.todos

    def _refresh_list(self):
        self._list.clear()
        filtered = self._get_filtered_todos()

        for todo in filtered:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 52))

            widget = QFrame()
            widget.setStyleSheet(f"""
                QFrame {{
                    background: {CARD_BG};
                    border: 1px solid {BORDER};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border-color: {ACCENT};
                }}
            """)
            row = QHBoxLayout(widget)
            row.setContentsMargins(10, 6, 6, 6)
            row.setSpacing(6)

            # Status indicator
            status = QLabel("●")
            if todo.done:
                status.setStyleSheet(f"color: {DONE_GREEN}; font-size: 16px; background: transparent;")
            else:
                priority_colors = {"low": "#8BC34A", "normal": ACCENT, "high": DANGER}
                color = priority_colors.get(todo.priority, ACCENT)
                status.setStyleSheet(f"color: {color}; font-size: 16px; background: transparent;")
            row.addWidget(status)

            # Text
            text_label = QLabel(todo.text)
            text_label.setWordWrap(True)
            if todo.done:
                text_label.setStyleSheet(f"""
                    QLabel {{
                        color: {TEXT_SEC}; font-size: 12px;
                        text-decoration: line-through; background: transparent;
                    }}
                """)
            else:
                text_label.setStyleSheet(f"""
                    QLabel {{ color: {TEXT}; font-size: 12px; background: transparent; }}
                """)
            row.addWidget(text_label, 1)

            # Timer button (only for active tasks)
            if not todo.done:
                timer_btn = QPushButton("⏱")
                timer_btn.setFixedSize(26, 26)
                timer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                timer_btn.setToolTip("开始计时")
                timer_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {TIMER_COLOR}; color: white; border: none;
                        border-radius: 13px; font-size: 13px;
                    }}
                    QPushButton:hover {{ background: #3A80C9; }}
                """)
                timer_btn.clicked.connect(lambda checked=False, t=todo: self._start_timer(t))
                row.addWidget(timer_btn)

            # Toggle button
            if todo.done:
                toggle_btn = QPushButton("↩")
                toggle_btn.setToolTip("撤销完成")
                toggle_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {TEXT_SEC}; color: white; border: none;
                        border-radius: 13px; font-size: 13px; font-weight: bold;
                    }}
                    QPushButton:hover {{ background: {ACCENT}; }}
                """)
            else:
                toggle_btn = QPushButton("✓")
                toggle_btn.setToolTip("标记完成")
                toggle_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {SUCCESS}; color: white; border: none;
                        border-radius: 13px; font-size: 13px; font-weight: bold;
                    }}
                    QPushButton:hover {{ background: {ACCENT}; }}
                """)
            toggle_btn.setFixedSize(26, 26)
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            toggle_btn.clicked.connect(lambda checked=False, t=todo: self._toggle_todo_by_ref(t))
            row.addWidget(toggle_btn)

            # Delete button
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(26, 26)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setToolTip("删除")
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {TEXT_SEC};
                    border: none; border-radius: 13px; font-size: 12px;
                }}
                QPushButton:hover {{ background: {DANGER}; color: white; }}
            """)
            del_btn.clicked.connect(lambda checked=False, t=todo: self._delete_todo_by_ref(t))
            row.addWidget(del_btn)

            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

        # Update stats
        total = len(self.todos)
        done = sum(1 for t in self.todos if t.done)
        self._stats_label.setText(f"完成: {done}/{total}")

    # ── Task history for calendar ──

    def _record_task_done(self, task_text, elapsed_seconds=0):
        """Record a completed task to daily history."""
        today = date.today().isoformat()
        history = self._load_history()
        if today not in history:
            history[today] = []
        history[today].append({
            "text": task_text,
            "time": datetime.now().strftime("%H:%M"),
            "duration": elapsed_seconds,
        })
        self._save_history(history)

    def _load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_history(self, history):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_task_history(self):
        """Return task history dict for calendar use."""
        return self._load_history()

    # ── Persistence ──

    def _load_todos(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.todos = [TodoItem(**item) for item in data]
        except Exception:
            self.todos = []

    def _save_todos(self):
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            data = [
                {"text": t.text, "done": t.done, "created_at": t.created_at, "priority": t.priority}
                for t in self.todos
            ]
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_incomplete_count(self):
        return sum(1 for t in self.todos if not t.done)
