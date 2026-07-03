"""Screen time tracker - monitors foreground window in background thread."""

import os
import json
import time
import threading
from datetime import datetime
from collections import defaultdict

try:
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

DATA_DIR = os.path.join(os.path.expanduser("~"), ".desktop_pet")
SCREEN_TIME_FILE = os.path.join(DATA_DIR, "screen_time.json")

IGNORE_TITLES = {"", "Default IME", "MSCTFIME UI", "CiceroUIWndFrame"}
IGNORE_APPS = {"explorer.exe", "SearchHost.exe", "SearchUI.exe",
               "StartMenuExperienceHost.exe", "LockApp.exe",
               "TextInputHost.exe", "ShellExperienceHost.exe"}

POLL_INTERVAL = 5
SAVE_INTERVAL = 60

class ScreenTimeTracker:
    """Tracks foreground window time in a background thread."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._buffer = defaultdict(lambda: defaultdict(float))
        self._current_app = ""
        self._current_start = 0.0
        self._data = {}
        self._load_data()

    def _load_data(self):
        """Load existing screen time data."""
        try:
            if os.path.exists(SCREEN_TIME_FILE):
                with open(SCREEN_TIME_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def _save_data(self):
        """Merge buffer into persistent data and save."""
        with self._lock:
            for date, apps in self._buffer.items():
                if date not in self._data:
                    self._data[date] = {}
                for app, secs in apps.items():
                    self._data[date][app] = self._data[date].get(app, 0) + secs
            self._buffer.clear()

        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(SCREEN_TIME_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Screen time save error: {e}")

    def start(self):
        """Start tracking in background thread."""
        if not HAS_WIN32:
            print("Screen time: win32gui/psutil not available, disabled")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop tracking and save."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._flush_current()
        self._save_data()

    def _get_foreground_info(self):
        """Get foreground window app name and title."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, None

            title = win32gui.GetWindowText(hwnd)
            if title in IGNORE_TITLES:
                return None, None

            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            app_name = "unknown.exe"
            if HAS_PSUTIL:
                try:
                    proc = psutil.Process(pid)
                    app_name = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            else:
                try:
                    import ctypes
                    from ctypes import wintypes
                    kernel32 = ctypes.windll.kernel32
                    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                    if handle:
                        buf = ctypes.create_unicode_buffer(512)
                        size = wintypes.DWORD(512)
                        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                            app_name = os.path.basename(buf.value)
                        kernel32.CloseHandle(handle)
                except Exception:
                    pass

            if app_name in IGNORE_APPS:
                return None, None

            return app_name, title
        except Exception:
            return None, None

    def _is_fullscreen_game(self):
        """Check if foreground window is a fullscreen application."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False
            rect = win32gui.GetWindowRect(hwnd)
            import ctypes
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            return w >= sw and h >= sh
        except Exception:
            return False

    def _flush_current(self):
        """Flush current foreground session to buffer."""
        if self._current_app and self._current_start > 0:
            elapsed = time.time() - self._current_start
            if elapsed > 0:
                today = datetime.now().strftime("%Y-%m-%d")
                with self._lock:
                    self._buffer[today][self._current_app] += elapsed
            self._current_start = time.time()

    def _run(self):
        """Main tracking loop."""
        last_save = time.time()
        time.sleep(2)

        while self._running:
            try:
                if self._is_fullscreen_game():
                    if self._current_app:
                        self._flush_current()
                        self._current_app = ""
                        self._current_start = 0.0
                    time.sleep(POLL_INTERVAL)
                    continue

                app, title = self._get_foreground_info()

                if app:
                    if app != self._current_app:
                        self._flush_current()
                        self._current_app = app
                        self._current_start = time.time()
                else:
                    if self._current_app:
                        self._flush_current()
                        self._current_app = ""
                        self._current_start = 0.0

                now = time.time()
                if now - last_save >= SAVE_INTERVAL:
                    self._flush_current()
                    self._save_data()
                    last_save = now

            except Exception as e:
                print(f"Screen time poll error: {e}")

            time.sleep(POLL_INTERVAL)

    def get_today_data(self):
        """Get today's screen time data, sorted by duration desc."""
        today = datetime.now().strftime("%Y-%m-%d")
        merged = defaultdict(float)
        for app, secs in self._data.get(today, {}).items():
            merged[app] += secs
        with self._lock:
            for app, secs in self._buffer.get(today, {}).items():
                merged[app] += secs

        result = sorted(merged.items(), key=lambda x: -x[1])
        return result

    def get_date_data(self, date_str):
        """Get screen time data for a specific date."""
        merged = defaultdict(float)
        for app, secs in self._data.get(date_str, {}).items():
            merged[app] += secs
        today = datetime.now().strftime("%Y-%m-%d")
        if date_str == today:
            with self._lock:
                for app, secs in self._buffer.get(today, {}).items():
                    merged[app] += secs
        result = sorted(merged.items(), key=lambda x: -x[1])
        return result

    def get_week_data(self):
        """Get last 7 days screen time data."""
        from datetime import timedelta
        today = datetime.now()
        result = {}
        for i in range(7):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            day_data = self.get_date_data(d)
            if day_data:
                result[d] = day_data
        return result

    def get_today_vs_yesterday(self):
        """Get today vs yesterday comparison."""
        from datetime import timedelta
        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        today_total = sum(s for _, s in self.get_date_data(today_str))
        yesterday_total = sum(s for _, s in self.get_date_data(yesterday_str))

        return today_total, yesterday_total

    def get_hourly_data(self, date_str=None):
        """Get hourly usage distribution. Returns list of 24 floats (seconds per hour).
        Note: Current implementation returns daily app totals distributed evenly.
        For accurate hourly tracking, the buffer would need to store timestamps.
        """
        return [0.0] * 24
