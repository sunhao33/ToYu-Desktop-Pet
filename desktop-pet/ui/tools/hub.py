"""Desktop tool logic: clipboard history and eye-care reminders.

Pure Python logic (no Qt) so it can be tested headlessly. UI lives in
ui/tools/desktop_tools_page.py and the background driver in DesktopToolsHub.
"""

import json
import os
import time
from datetime import datetime

MAX_HISTORY = 100
REJECT_MARKER = "[图片]"


def get_data_dir():
    """Writable app data directory. Never the PyInstaller _MEIPASS temp dir."""
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "ToYu")
    os.makedirs(path, exist_ok=True)
    return path


class ClipboardHistory:
    """Clipboard history with persistence.

    Entries are dicts: {"text": str, "time": "MM-DD HH:MM"}.
    """

    def __init__(self, settings):
        self.settings = settings
        self.enabled = settings.clipboard_enabled
        self._history = self._clean(settings.clipboard_history)
        self._last_text = None

    @property
    def history(self):
        return self._history

    def set_enabled(self, on):
        self.enabled = bool(on)
        self.settings.clipboard_enabled = self.enabled

    def poll(self, text):
        """Feed the current clipboard text. Returns True if history changed."""
        if not self.enabled:
            return False
        if text is None:
            return False
        if text == self._last_text:
            return False
        self._last_text = text
        stripped = text.strip()
        if not stripped or len(stripped) > 20000:
            return False
        if self.is_stored(text):
            self._move_to_front(text)
            return True
        return self.add(text)

    def add(self, text):
        if not text or not text.strip():
            return False
        if self.is_stored(text):
            self._move_to_front(text)
            return True
        self._history.insert(0, {"text": text, "time": datetime.now().strftime("%m-%d %H:%M")})
        del self._history[MAX_HISTORY:]
        self._save()
        return True

    def clear(self):
        self._history = []
        self._save()

    def is_stored(self, text):
        return any(item["text"] == text for item in self._history)

    def _move_to_front(self, text):
        item = next(item for item in self._history if item["text"] == text)
        self._history.remove(item)
        self._history.insert(0, item)
        self._save()

    def _clean(self, raw):
        out = []
        for item in raw:
            if not isinstance(item, dict) or "text" not in item:
                continue
            if item.get("text") == REJECT_MARKER:
                continue
            out.append({"text": item["text"], "time": item.get("time", "")})
        return out

    def _save(self):
        self.settings.clipboard_history = self._history


class EyeCareReminder:
    """Reminds you to look away from the screen after a work interval.

    Uses a timestamp deadline so sleep/suspend does not drift.
    """

    def __init__(self, settings, on_rest=None, on_resume=None):
        self.settings = settings
        self.on_rest = on_rest
        self.on_resume = on_resume
        self.enabled = settings.eye_care_enabled
        self.work_minutes = settings.eye_care_work_minutes
        self.rest_minutes = settings.eye_care_rest_minutes
        self.resting = False
        self._deadline = self._load_deadline()
        self._finished_work_intervals = 0

    @property
    def finished_work_intervals(self):
        return self._finished_work_intervals

    def set_enabled(self, on):
        self.enabled = bool(on)
        self.settings.eye_care_enabled = self.enabled
        if self.enabled:
            self.reset()

    def set_intervals(self, work_minutes, rest_minutes):
        self.work_minutes = max(1, int(work_minutes))
        self.rest_minutes = max(1, int(rest_minutes))
        self.settings.eye_care_work_minutes = self.work_minutes
        self.settings.eye_care_rest_minutes = self.rest_minutes
        self._finished_work_intervals = 0
        self.reset()

    def reset(self):
        self.resting = False
        self._deadline = time.time() + self.work_minutes * 60
        self._save_deadline()

    def remaining_seconds(self):
        return max(0, int(self._deadline - time.time()))

    def status_text(self):
        if not self.enabled:
            return "护眼提醒已关闭"
        mins, secs = divmod(self.remaining_seconds(), 60)
        if self.resting:
            return f"休息中 · 还有 {mins} 分 {secs} 秒"
        return f"下次休息 · 还有 {mins} 分 {secs} 秒"

    def check_tick(self):
        if not self.enabled:
            return
        if time.time() < self._deadline:
            return
        if not self.resting:
            self.resting = True
            self._finished_work_intervals += 1
            self._deadline = time.time() + self.rest_minutes * 60
            self._save_deadline()
            if self.on_rest:
                self.on_rest(self.rest_minutes, self._finished_work_intervals)
        else:
            self.resting = False
            self._deadline = time.time() + self.work_minutes * 60
            self._save_deadline()
            if self.on_resume:
                self.on_resume()

    def _load_deadline(self):
        stamp = self.settings.eye_care_deadline
        if stamp and stamp > time.time():
            return stamp
        return time.time() + self.work_minutes * 60

    def _save_deadline(self):
        self.settings.eye_care_deadline = self._deadline


class DesktopToolsHub:
    """Owns the desktop-tool background loops and hands state to the UI.

    notify(kind, title, body) is called for user-visible events.
    """

    POLL_MS = 1000

    def __init__(self, settings, notify=None, pet=None):
        self.settings = settings
        self.notify = notify
        self.pet = pet
        self.clipboard = ClipboardHistory(settings)
        self.eye_care = EyeCareReminder(
            settings,
            on_rest=self._on_rest,
            on_resume=self._on_resume,
        )
        self._listeners = []
        self._timer = None
        self._last_clip_text = None
        self.notify_status = False

    # ── wiring ──────────────────────────────────────────────
    def set_listeners(self, clipboard_cb=None, status_cb=None, eyedata_cb=None):
        if clipboard_cb:
            self._listeners.append(("clipboard", clipboard_cb))
        if status_cb:
            self._listeners.append(("status", status_cb))
        if eyedata_cb:
            self._listeners.append(("eyedata", eyedata_cb))

    def start(self):
        if self._timer is None:
            from PyQt6.QtCore import QTimer

            self._timer = QTimer()
            self._timer.timeout.connect(self._tick)
        self._timer.start(self.POLL_MS)

    def stop(self):
        if self._timer is not None:
            self._timer.stop()

    @property
    def running(self):
        return self._timer is not None and self._timer.isActive()

    # ── loop ────────────────────────────────────────────────
    def _tick(self):
        self._poll_clipboard()
        self.eye_care.check_tick()
        if self.notify_status:
            self._emit("status", self.eye_care)

    def _poll_clipboard(self):
        from PyQt6.QtWidgets import QApplication

        board = QApplication.clipboard()
        mime = board.mimeData()
        if mime is not None and mime.hasImage() and not mime.hasText():
            text = REJECT_MARKER
        else:
            text = board.text()
        if text == self._last_clip_text:
            return
        self._last_clip_text = text
        if text == REJECT_MARKER:
            return
        if self.clipboard.poll(text):
            self._emit("clipboard", list(self.clipboard.history))
            self.settings.clipboard_history = self.clipboard.history

    def _on_rest(self, rest_minutes, count):
        self.settings.clipboard_history = self.clipboard.history
        if self.notify:
            self.notify("eye_rest", f"👀  该让眼睛歇一会儿了！", f"{rest_minutes} 分钟后再继续 · 已专注 {count} 轮")
        self._emit("eyedata", self.eye_care)

    def _on_resume(self):
        if self.notify:
            self.notify("eye_resume", "✨  休息结束，继续加油！", "远眺一下再回到屏幕吧")

    def _emit(self, kind, payload):
        for target, callback in self._listeners:
            if target != kind:
                continue
            try:
                callback(payload)
            except Exception:
                pass

    # ── persistence ─────────────────────────────────────────
    def flush(self):
        self.settings.clipboard_history = self.clipboard.history
        self.eye_care._save_deadline()

    def summary(self):
        """Small dict for the status bar / docs."""
        return {
            "clipboard_enabled": self.clipboard.enabled,
            "clipboard_count": len(self.clipboard.history),
            "eye_care_enabled": self.eye_care.enabled,
            "eye_care_status": self.eye_care.status_text(),
        }
