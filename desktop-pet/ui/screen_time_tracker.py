"""Screen time tracker - monitors foreground window in a background thread.

记录粒度是「会话」：应用名 + 窗口标题 + 开始时间 + 持续秒数。
有了时间戳才能统计「几点在学习」，有了标题才能区分「浏览器里在看论文还是刷视频」。
"""

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
SESSION_FILE = os.path.join(DATA_DIR, "screen_sessions.json")

IGNORE_TITLES = {"", "Default IME", "MSCTFIME UI", "CiceroUIWndFrame"}
IGNORE_APPS = {"explorer.exe", "SearchHost.exe", "SearchUI.exe",
               "StartMenuExperienceHost.exe", "LockApp.exe",
               "TextInputHost.exe", "ShellExperienceHost.exe"}

# 全屏时暂停统计的应用（默认空：全屏看网课/看 PDF 也该算学习时间）
DEFAULT_FULLSCREEN_PAUSE = []
TITLE_LIMIT = 120
SESSION_RETENTION_DAYS = 30

POLL_INTERVAL = 5
SAVE_INTERVAL = 60


def normalize_title(title):
    """去掉窗口标题里的噪声，避免同一份文档被切成很多段。"""
    text = (title or "").strip()
    # 先去掉未保存标记，再去浏览器/编辑器后缀，最后统一清掉残余符号
    text = text.strip(" *·").strip()
    for suffix in (" - Google Chrome", " - Microsoft​ Edge", " - Mozilla Firefox",
                   " - Visual Studio Code", " - Notepad", " - 记事本"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].rstrip()
    return text.strip(" *·-—").strip()


def sanitize_title(title):
    """标题只用于本地统计：截断 + 过滤明显的敏感串（密码/身份证/银行卡样式）。"""
    text = normalize_title(title)[:TITLE_LIMIT]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 15:  # 疑似身份证/银行卡号
        return "(已隐藏敏感标题)"
    return text


class ScreenTimeTracker:
    """Tracks foreground window time in a background thread."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._buffer = defaultdict(lambda: defaultdict(float))   # date -> app -> secs
        self._session_buffer = defaultdict(list)                 # date -> [session]
        self._current_app = ""
        self._current_title = ""
        self._current_start = 0.0
        self._data = {}
        self._sessions = {}
        self._fullscreen_pause = set(DEFAULT_FULLSCREEN_PAUSE)
        self._record_titles = True
        self._load_data()
        self._load_sessions()

    # ── 持久化 ──────────────────────────────────────────────
    def _load_data(self):
        try:
            if os.path.exists(SCREEN_TIME_FILE):
                with open(SCREEN_TIME_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def _load_sessions(self):
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for date, items in raw.items():
                    self._sessions[date] = [s for s in items if isinstance(s, dict) and s.get("app")]
            else:
                self._migrate_from_totals()
        except Exception:
            self._sessions = {}

    def _migrate_from_totals(self):
        """老数据只有 {日期: {应用: 秒数}}，迁移成会话（起始时间未知，标记为推断）。"""
        for date, apps in self._data.items():
            items = []
            for app, secs in apps.items():
                if secs <= 0:
                    continue
                items.append({
                    "app": app, "title": "", "start": f"{date} 00:00:00",
                    "secs": round(float(secs), 1), "inferred": True,
                })
            if items:
                self._sessions[date] = items
        if self._sessions:
            self._save_sessions()

    def _prune_sessions(self):
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=SESSION_RETENTION_DAYS)).strftime("%Y-%m-%d")
        for date in [d for d in self._sessions if d < cutoff]:
            del self._sessions[date]

    @staticmethod
    def _compact(items):
        """合并碎会话。

        窗口标题频繁变化（切标签、切文件）会产生大量几秒钟的碎片，
        不合并的话会话文件会无限膨胀、每次落盘都要重写整个文件。
        规则：同一应用同一标题、且中间没有断开时合并；1 秒以内的碎片丢弃。
        """
        try:
            ordered = sorted(items, key=lambda s: s.get("start", ""))
        except Exception:
            return items

        merged = []
        for sess in ordered:
            secs = float(sess.get("secs", 0) or 0)
            if secs <= 1:
                continue
            if merged:
                last = merged[-1]
                same_target = (last.get("app") == sess.get("app")
                               and last.get("title") == sess.get("title"))
                if same_target and secs < 10:
                    last["secs"] = round(float(last.get("secs", 0)) + secs, 1)
                    continue
            merged.append(dict(sess))
        return merged

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

    def _save_sessions(self):
        with self._lock:
            for date, items in self._session_buffer.items():
                self._sessions.setdefault(date, []).extend(items)
            self._session_buffer.clear()
            for date in list(self._sessions):
                self._sessions[date] = self._compact(self._sessions[date])
        self._prune_sessions()
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = SESSION_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._sessions, f, ensure_ascii=False, indent=1)
            os.replace(tmp, SESSION_FILE)
        except Exception as e:
            print(f"Session save error: {e}")

    # ── 设置 ────────────────────────────────────────────────
    def set_record_titles(self, enabled):
        self._record_titles = bool(enabled)

    def set_fullscreen_pause_apps(self, apps):
        self._fullscreen_pause = {a.strip().lower() for a in apps if a.strip()}

    # ── 生命周期 ────────────────────────────────────────────
    def start(self):
        if not HAS_WIN32:
            print("Screen time: win32gui/psutil not available, disabled")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        self._flush_current()
        self._save_data()
        self._save_sessions()

    # ── 采集 ────────────────────────────────────────────────
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

    def _is_fullscreen(self):
        """Check if foreground window covers the whole screen."""
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

    def _should_pause(self, app_name):
        """全屏时才暂停，且只暂停用户名单里的应用。

        以前只要全屏就暂停，导致全屏看网课/看 PDF/写代码这些学习时间全被漏记。
        """
        if not self._fullscreen_pause:
            return False
        if (app_name or "").lower() not in self._fullscreen_pause:
            return False
        return self._is_fullscreen()

    def _flush_current(self):
        """把当前会话写进缓冲。"""
        if not self._current_app or self._current_start <= 0:
            return
        elapsed = time.time() - self._current_start
        if elapsed > 0:
            today = datetime.now().strftime("%Y-%m-%d")
            started = datetime.fromtimestamp(self._current_start)
            title = sanitize_title(self._current_title) if self._record_titles else ""
            entry = {
                "app": self._current_app,
                "title": title,
                "start": started.strftime("%Y-%m-%d %H:%M:%S"),
                "secs": round(elapsed, 1),
            }
            with self._lock:
                self._buffer[today][self._current_app] += elapsed
                self._session_buffer[today].append(entry)
        self._current_start = time.time()

    def _run(self):
        """Main tracking loop."""
        last_save = time.time()
        time.sleep(2)

        while self._running:
            try:
                app, title = self._get_foreground_info()

                if app and self._should_pause(app):
                    if self._current_app:
                        self._flush_current()
                        self._current_app = ""
                        self._current_title = ""
                        self._current_start = 0.0
                elif app:
                    # 应用切换，或同一应用内标题变化，都算新会话
                    normalized = normalize_title(title)
                    if app != self._current_app or normalized != self._current_title:
                        self._flush_current()
                        self._current_app = app
                        self._current_title = normalized
                        self._current_start = time.time()
                else:
                    if self._current_app:
                        self._flush_current()
                        self._current_app = ""
                        self._current_title = ""
                        self._current_start = 0.0

                now = time.time()
                if now - last_save >= SAVE_INTERVAL:
                    self._flush_current()
                    self._save_data()
                    self._save_sessions()
                    last_save = now

            except Exception as e:
                print(f"Screen time poll error: {e}")

            time.sleep(POLL_INTERVAL)

    # ── 查询：总量 ──────────────────────────────────────────
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

    # ── 查询：会话与时间轴 ──────────────────────────────────
    def get_sessions(self, date_str=None):
        """返回指定日期（默认今天）的会话列表，按开始时间排序。"""
        date = date_str or datetime.now().strftime("%Y-%m-%d")
        items = list(self._sessions.get(date, []))
        if date == datetime.now().strftime("%Y-%m-%d"):
            with self._lock:
                items += list(self._session_buffer.get(date, []))
                if self._current_app and self._current_start > 0:
                    started = datetime.fromtimestamp(self._current_start)
                    items.append({
                        "app": self._current_app,
                        "title": sanitize_title(self._current_title) if self._record_titles else "",
                        "start": started.strftime("%Y-%m-%d %H:%M:%S"),
                        "secs": round(time.time() - self._current_start, 1),
                    })
        return sorted(items, key=lambda s: s.get("start", ""))

    def get_hourly_data(self, date_str=None):
        """按小时分布的使用秒数（长度 24 的浮点列表）。

        以会话开始时刻所在小时归集；跨小时的长会话按比例摊到各小时。
        """
        buckets = [0.0] * 24
        for sess in self.get_sessions(date_str):
            try:
                started = datetime.strptime(sess["start"], "%Y-%m-%d %H:%M:%S")
            except (KeyError, ValueError):
                continue
            remaining = float(sess.get("secs", 0))
            hour = started.hour
            minute_offset = started.minute * 60 + started.second
            cursor = hour
            left_in_hour = 3600 - minute_offset
            while remaining > 0 and cursor < 24:
                take = min(remaining, left_in_hour)
                buckets[cursor] += take
                remaining -= take
                cursor += 1
                left_in_hour = 3600
        return buckets

    def get_title_stats(self, date_str=None, top=15):
        """按窗口标题统计，用来看「同一款软件里到底在干什么」。"""
        merged = defaultdict(float)
        for sess in self.get_sessions(date_str):
            key = (sess.get("app", ""), sess.get("title", "") or "(无标题)")
            merged[key] += float(sess.get("secs", 0))
        return sorted(merged.items(), key=lambda kv: -kv[1])[:top]

    def get_focus_stats(self, date_str=None, min_session=60):
        """专注相关指标：会话数、有效会话（≥min_session 秒）、最长连续单次。"""
        sessions = [s for s in self.get_sessions(date_str) if s.get("secs", 0) > 0]
        meaningful = [s for s in sessions if s["secs"] >= min_session]
        longest = max((s["secs"] for s in meaningful), default=0.0)
        return {
            "sessions": len(sessions),
            "meaningful": len(meaningful),
            "longest_secs": round(longest, 1),
            "total_secs": round(sum(s["secs"] for s in sessions), 1),
        }
