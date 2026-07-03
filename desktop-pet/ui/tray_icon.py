"""System tray icon with context menu."""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction

from image_processor.processor import get_default_pet_path


class TrayIcon(QSystemTrayIcon):
    def __init__(self, pet_window, settings):
        super().__init__()
        self._pet = pet_window
        self._settings = settings
        self._on_change_pet = None

        icon = QIcon(get_default_pet_path())
        self.setIcon(icon)
        self.setToolTip("ToYu — 桌面土豆宠物")

        self._build_menu()
        self.setVisible(True)

    def _build_menu(self):
        self._menu = QMenu()

        show_action = QAction("显示 / 隐藏宠物", self._menu)
        show_action.triggered.connect(self._on_show_hide)
        self._menu.addAction(show_action)

        self._menu.addSeparator()

        change_action = QAction("更换宠物...", self._menu)
        change_action.triggered.connect(self._on_change)
        self._menu.addAction(change_action)

        self._menu.addSeparator()

        exit_action = QAction("退出", self._menu)
        exit_action.triggered.connect(self._on_exit)
        self._menu.addAction(exit_action)

        self.setContextMenu(self._menu)

    def _on_show_hide(self):
        if self._pet:
            self._pet.toggle_visibility()

    def _on_change(self):
        if self._on_change_pet:
            self._on_change_pet()

    def _on_exit(self):
        from PyQt6.QtWidgets import QApplication
        if self._pet:
            self._pet.close()
        QApplication.quit()
