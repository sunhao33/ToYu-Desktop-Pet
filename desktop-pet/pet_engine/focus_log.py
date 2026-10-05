"""专注段与番茄轮次的记录。

心流模式需要两样现有数据里没有的东西：
  * **轮次**：一天完成了几个"专注→休息"循环
  * **专注段**：每次专注从几点开始、持续多久、做的是哪个任务

屏幕时间记录（screen_sessions.json）不适合承担这个职责：
它是被动的应用切换流水，不是主动声明的专注时段，两者语义不同。

存储位置与 flow_timers.json 同目录（%APPDATA%\\ToYu），
避免再散出一个新的数据目录。
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ToYu")
LOG_FILE = os.path.join(APP_DIR, "focus_log.json")

KEEP_DAYS = 60          # 只保留最近 60 天，避免文件无限增长

KIND_FOCUS = "focus"
KIND_BREAK = "break"
KIND_LABEL = {KIND_FOCUS: "专注", KIND_BREAK: "休息"}


def _today() -> str:
    return date.today().isoformat()


class FocusLog:
    """专注段日志：按日期存记录，支持今日轮次统计。"""

    def __init__(self, path: str = LOG_FILE):
        self._path = path
        self._data = None

    # ── 读写 ────────────────────────────────────────────────
    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        data = {}
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    data = loaded
        except (OSError, ValueError):
            data = {}
        self._data = data
        return data

    def _save(self):
        data = self._load()
        # 只保留最近 KEEP_DAYS 天
        if len(data) > KEEP_DAYS:
            keys = sorted(data.keys())
            for old in keys[:-KEEP_DAYS]:
                data.pop(old, None)
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, self._path)
        except OSError as exc:
            print("[FocusLog] 保存失败: %s" % exc)

    # ── 写入 ────────────────────────────────────────────────
    def add(self, kind: str, seconds: float, task: str = "",
            started: datetime = None) -> dict:
        """记一段。seconds 小于 60 秒的忽略 —— 误点开始又立刻停的不算。

        归到**开始时刻**所属的那一天：跨零点的专注段算在前一天，
        这与"今晚学到凌晨"的直觉一致。
        """
        if seconds is None or seconds < 60:
            return {}
        started = started or datetime.now() - timedelta(seconds=seconds)
        day = started.date().isoformat()
        record = {
            "kind": kind,
            "start": started.strftime("%H:%M"),
            "end": (started + timedelta(seconds=seconds)).strftime("%H:%M"),
            "start_min": started.hour * 60 + started.minute,
            "minutes": int(seconds // 60),
            "task": (task or "")[:40],
        }
        data = self._load()
        data.setdefault(day, []).append(record)
        self._save()
        return record

    def clear_today(self):
        data = self._load()
        if _today() in data:
            data.pop(_today())
            self._save()

    # ── 查询 ────────────────────────────────────────────────
    def today(self) -> list:
        return list(self._load().get(_today(), []))

    def rounds_today(self) -> int:
        """今日完成的专注轮次（以"专注段"数量计）。"""
        return sum(1 for r in self.today() if r.get("kind") == KIND_FOCUS)

    def focus_minutes_today(self) -> int:
        return sum(int(r.get("minutes", 0)) for r in self.today()
                   if r.get("kind") == KIND_FOCUS)

    def segments(self, day: str = None) -> list:
        """某天的记录，按开始时间排序。"""
        return sorted(self._load().get(day or _today(), []),
                      key=lambda r: r.get("start_min", 0))

    def summary(self, day: str = None) -> dict:
        records = self.segments(day)
        focus = [r for r in records if r.get("kind") == KIND_FOCUS]
        breaks = [r for r in records if r.get("kind") == KIND_BREAK]
        return {
            "rounds": len(focus),
            "focus_minutes": sum(int(r.get("minutes", 0)) for r in focus),
            "break_minutes": sum(int(r.get("minutes", 0)) for r in breaks),
            "segments": records,
        }
