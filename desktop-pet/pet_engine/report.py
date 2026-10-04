"""学习报告 —— 把已有的记录组装成一份可读、可导出的报告。

设计原则：
  * **只读已有接口，不自己重算**：所有数字都取自 ScreenTimeTracker 与
    待办历史，避免"报告说 3 小时、面板说 2 小时"这种自相矛盾。
  * **多出口**：界面预览 + 导出文件 + 供 AI 调用的文本，共用同一套渲染。
  * **空数据不输出空表格**：没有记录时给一句明确的说明，而不是一堆 0。
  * **导出不覆盖**：同名文件自动加序号。
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from pet_engine.goal import is_study_app, study_seconds_from_sessions

REPORT_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                          "ToYu", "reports")

PERIOD_TODAY = "today"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"

PERIOD_LABEL = {
    PERIOD_TODAY: "今日",
    PERIOD_WEEK: "本周",
    PERIOD_MONTH: "本月",
}


def _fmt_minutes(minutes) -> str:
    minutes = int(minutes)
    if minutes >= 60:
        return "%d 小时 %d 分" % (minutes // 60, minutes % 60)
    return "%d 分钟" % minutes


def _fmt_seconds(seconds) -> str:
    return _fmt_minutes(int(seconds) // 60)


def _bar(minutes, max_minutes, width=12) -> str:
    """用方块画一个简易条形（纯文本也能看出对比）。"""
    if max_minutes <= 0:
        return ""
    filled = int(round(minutes / max_minutes * width))
    return "█" * max(0, min(width, filled))


class LearningReport:
    """生成学习报告。"""

    def __init__(self, main_window=None, tracker=None, todo_widget=None,
                 goal_tracker=None, memory_store=None):
        self._main = main_window
        self._tracker = tracker or getattr(main_window, "_screen_tracker", None)
        self._todo = todo_widget or getattr(main_window, "_todo_widget", None)
        self._goal = goal_tracker
        self._memory = memory_store

    # ── 日期范围 ────────────────────────────────────────────
    @staticmethod
    def date_range(period: str) -> list[str]:
        """返回要统计的日期列表（升序）。"""
        today = date.today()
        if period == PERIOD_WEEK:
            days = 7
        elif period == PERIOD_MONTH:
            days = 30
        else:
            days = 1
        return [(today - timedelta(days=i)).isoformat()
                for i in range(days - 1, -1, -1)]

    # ── 数据聚合 ────────────────────────────────────────────
    def collect(self, period: str = PERIOD_TODAY) -> dict:
        days = self.date_range(period)
        data = {
            "period": period,
            "period_label": PERIOD_LABEL.get(period, "今日"),
            "days": days,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_screen_seconds": 0.0,
            "total_study_seconds": 0.0,
            "tasks": [],                 # [{date, text, time, duration}]
            "apps": {},                  # app -> seconds（仅学习类）
            "all_apps": {},              # app -> seconds（全部，用于对比）
            "hourly": [0.0] * 24,
            "daily": {},                 # date -> study seconds
            "focus": {"sessions": 0, "meaningful": 0, "longest_secs": 0.0},
            "goal": None,
            "best_hour": None,
            "has_data": False,
        }
        if self._tracker is None:
            return data

        for day in days:
            try:
                sessions = self._tracker.get_sessions(day) or []
            except Exception:  # noqa: BLE001
                sessions = []
            day_study = 0.0
            for sess in sessions:
                secs = float(sess.get("secs", 0) or 0)
                app = sess.get("app", "") or "(未知)"
                title = sess.get("title", "") or ""
                data["total_screen_seconds"] += secs
                data["all_apps"][app] = data["all_apps"].get(app, 0.0) + secs
                if secs < 180 or not is_study_app(app, title):
                    continue
                day_study += secs
                data["apps"][app] = data["apps"].get(app, 0.0) + secs
            data["daily"][day] = day_study
            data["total_study_seconds"] += day_study

            # 时段分布（只统计最后一天，避免叠加失真）
            if day == days[-1]:
                try:
                    hourly = self._tracker.get_hourly_data(day) or []
                    data["hourly"] = [float(v) for v in hourly][:24]
                except Exception:  # noqa: BLE001
                    pass
                try:
                    focus = self._tracker.get_focus_stats(day)
                    if isinstance(focus, dict):
                        data["focus"] = focus
                except Exception:  # noqa: BLE001
                    pass

        # 完成任务
        try:
            history = self._todo.get_task_history() if self._todo else {}
        except Exception:  # noqa: BLE001
            history = {}
        for day in days:
            for item in history.get(day, []) or []:
                if not isinstance(item, dict):
                    continue
                data["tasks"].append({
                    "date": day,
                    "text": str(item.get("text", "")),
                    "time": str(item.get("time", "")),
                    "duration": int(item.get("duration", 0) or 0),
                })

        # 最佳时段（学习时长最高的小时）
        if any(data["hourly"]):
            idx = max(range(24), key=lambda i: data["hourly"][i])
            if data["hourly"][idx] > 0:
                data["best_hour"] = idx

        # 目标
        if self._goal is not None:
            try:
                data["goal"] = self._goal.progress()
            except Exception:  # noqa: BLE001
                data["goal"] = None

        data["has_data"] = bool(data["total_screen_seconds"]
                                or data["tasks"])
        return data

    # ── 渲染：Markdown ──────────────────────────────────────
    def render_markdown(self, period: str = PERIOD_TODAY) -> str:
        d = self.collect(period)
        lines = ["# 学习报告 · %s" % d["period_label"]]
        if d["period"] != PERIOD_TODAY:
            lines.append("")
            lines.append("统计区间：%s ~ %s" % (d["days"][0], d["days"][-1]))
        lines.append("")
        lines.append("生成时间：%s" % d["generated_at"])
        lines.append("")

        if not d["has_data"]:
            lines.append("> 这段时间还没有学习记录。")
            lines.append(">")
            lines.append("> 开始用 ToYu 专注学习后，这里会自动出现统计：")
            lines.append("> 有效学习时长、应用分布、时段分析、完成任务清单。")
            return "\n".join(lines)

        # ── 概览 ──
        lines.append("## 概览")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|---|---|")
        lines.append("| 有效学习 | %s |" % _fmt_seconds(d["total_study_seconds"]))
        lines.append("| 屏幕时间 | %s |" % _fmt_seconds(d["total_screen_seconds"]))
        if d["total_screen_seconds"] > 0:
            pct = d["total_study_seconds"] / d["total_screen_seconds"] * 100
            lines.append("| 学习占比 | %.0f%% |" % pct)
        lines.append("| 完成任务 | %d 项 |" % len(d["tasks"]))
        focus = d["focus"] or {}
        if focus.get("sessions"):
            lines.append("| 记录段数 | %d 段（其中 ≥5 分钟 %d 段）|"
                         % (focus.get("sessions", 0), focus.get("meaningful", 0)))
        if focus.get("longest_secs"):
            lines.append("| 最长连续 | %s |" % _fmt_seconds(focus["longest_secs"]))
        if d["goal"] and d["goal"].get("has_goal"):
            g = d["goal"]
            lines.append("| 每日目标 | %d 分钟（今日已完成 %d%%）|"
                         % (g["goal_minutes"], round(g.get("ratio", 0) * 100)))
        lines.append("")

        # ── 每日趋势（多天时才有意义）──
        if len(d["days"]) > 1:
            lines.append("## 每日学习时长")
            lines.append("")
            peak = max(d["daily"].values()) if d["daily"] else 0
            for day in d["days"]:
                secs = d["daily"].get(day, 0.0)
                mark = ""
                goal_minutes = (d["goal"] or {}).get("goal_minutes")
                if goal_minutes and secs >= goal_minutes * 60:
                    mark = " ✓"
                lines.append("- %s　%s　%s%s"
                             % (day, _bar(secs / 60, peak / 60),
                                _fmt_seconds(secs), mark))
            lines.append("")

        # ── 应用分布 ──
        if d["apps"]:
            lines.append("## 学习时间都用在哪")
            lines.append("")
            lines.append("| 应用 | 时长 | 占比 |")
            lines.append("|---|---|---|")
            total = d["total_study_seconds"] or 1
            for app_name, secs in sorted(d["apps"].items(),
                                         key=lambda kv: -kv[1])[:10]:
                lines.append("| %s | %s | %.0f%% |"
                             % (app_name, _fmt_seconds(secs), secs / total * 100))
            lines.append("")

        # ── 时段分布 ──
        if d["best_hour"] is not None:
            lines.append("## 时段分布")
            lines.append("")
            lines.append("最专注的时段：**%02d:00 - %02d:00**"
                         % (d["best_hour"], d["best_hour"] + 1))
            lines.append("")
            peak = max(d["hourly"]) if d["hourly"] else 0
            if peak > 0:
                lines.append("```")
                for hour in range(24):
                    secs = d["hourly"][hour]
                    if secs <= 0:
                        continue
                    lines.append("%02d:00 %s %s"
                                 % (hour, _bar(secs / 60, peak / 60, 20),
                                    _fmt_seconds(secs)))
                lines.append("```")
                lines.append("")

        # ── 完成任务 ──
        if d["tasks"]:
            lines.append("## 完成了什么")
            lines.append("")
            for task in d["tasks"][:30]:
                dur = ("（%d 分钟）" % (task["duration"] // 60)
                       if task["duration"] >= 60 else "")
                day_prefix = ("%s " % task["date"]) if len(d["days"]) > 1 else ""
                lines.append("- %s%s　%s%s"
                             % (day_prefix, task["time"], task["text"], dur))
            if len(d["tasks"]) > 30:
                lines.append("- …还有 %d 项" % (len(d["tasks"]) - 30))
            lines.append("")

        # ── 建议 ──
        tips = self._suggestions(d)
        if tips:
            lines.append("## 观察与建议")
            lines.append("")
            for tip in tips:
                lines.append("- %s" % tip)
            lines.append("")

        return "\n".join(lines)

    # ── 建议（基于数据的客观观察，不做说教）──────────────────
    def _suggestions(self, d: dict) -> list[str]:
        tips = []
        total = d["total_study_seconds"]
        screen = d["total_screen_seconds"]
        if screen > 0 and total > 0:
            pct = total / screen * 100
            if pct >= 70:
                tips.append("学习占屏幕时间的 %.0f%%，时间利用得很集中。" % pct)
            elif pct < 35:
                tips.append("学习只占屏幕时间的 %.0f%%，"
                            "可以考虑用专注计时减少分心。" % pct)

        if len(d["days"]) > 1:
            vals = [v for v in d["daily"].values()]
            if vals and max(vals) > 0:
                zero_days = sum(1 for v in vals if v <= 0)
                if zero_days:
                    tips.append("有 %d 天没有记录到学习时间。" % zero_days)
                best_day = max(d["daily"], key=lambda k: d["daily"][k])
                tips.append("学习最多的一天是 %s（%s）。"
                            % (best_day, _fmt_seconds(d["daily"][best_day])))

        if d["best_hour"] is not None:
            hour = d["best_hour"]
            if hour >= 22 or hour < 6:
                tips.append("最专注的时段在 %02d:00，注意别熬夜。" % hour)
            elif 8 <= hour <= 11:
                tips.append("最专注的时段在上午 %02d:00，可以把它留给最难的任务。"
                            % hour)

        if not d["tasks"]:
            tips.append("这段时间没有完成记录。"
                        "把任务写进待办并勾选完成，报告会更完整。")
        return tips

    # ── 渲染：纯文本（给 AI 用，紧凑）────────────────────────
    def render_text(self, period: str = PERIOD_TODAY, max_chars: int = 1200) -> str:
        d = self.collect(period)
        if not d["has_data"]:
            return "%s没有学习记录。" % d["period_label"]
        parts = [
            "%s：有效学习 %s，屏幕时间 %s，完成 %d 项任务"
            % (d["period_label"], _fmt_seconds(d["total_study_seconds"]),
               _fmt_seconds(d["total_screen_seconds"]), len(d["tasks"]))
        ]
        if d["apps"]:
            top = sorted(d["apps"].items(), key=lambda kv: -kv[1])[:4]
            parts.append("主要用在：" + "、".join(
                "%s %s" % (a, _fmt_seconds(s)) for a, s in top))
        if d["best_hour"] is not None:
            parts.append("最专注时段 %02d:00" % d["best_hour"])
        if d["goal"] and d["goal"].get("has_goal"):
            g = d["goal"]
            parts.append("每日目标 %d 分钟，今日完成 %d%%"
                         % (g["goal_minutes"], round(g.get("ratio", 0) * 100)))
        if d["tasks"]:
            names = [t["text"] for t in d["tasks"][:5]]
            parts.append("完成：" + "、".join(names))
        text = "；".join(parts)
        return text[:max_chars]

    # ── 导出 ────────────────────────────────────────────────
    def export(self, period: str = PERIOD_TODAY, fmt: str = "md",
               directory: str | None = None) -> str:
        """导出报告文件，返回文件路径。

        同名文件自动加序号，不覆盖已有文件。
        """
        content = (self.render_markdown(period) if fmt == "md"
                   else self.render_text(period, max_chars=100000))
        out_dir = directory or REPORT_DIR
        os.makedirs(out_dir, exist_ok=True)

        stamp = datetime.now().strftime("%Y-%m-%d")
        base = "学习报告_%s_%s" % (PERIOD_LABEL.get(period, "今日"), stamp)
        ext = ".md" if fmt == "md" else ".txt"
        path = os.path.join(out_dir, base + ext)
        seq = 2
        while os.path.exists(path):
            path = os.path.join(out_dir, "%s_%d%s" % (base, seq, ext))
            seq += 1

        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
        return path
