"""学习/工作报告 —— 把已有的记录组装成一份可读、可导出的报告。

两个版本：
  * **基础版**：纯本地统计，不联网、不需要 API Key。报告里的数字全部
    来自本机记录，任何人都能立刻看到。
  * **AI 版**：在基础版之上，把结构化摘要交给大模型做深度分析，
    产出针对个人的观察、问题诊断与可执行建议。

设计原则：
  * **只读已有接口，不自己重算**：所有数字都取自 ScreenTimeTracker 与
    待办历史，避免"报告说 3 小时、面板说 2 小时"这种自相矛盾。
  * **AI 只做分析，不产生数字**：交模型的是算好的摘要，模型不得引入
    新数字——否则 AI 会编，报告就不可信了。
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

# 报告版本
MODE_BASIC = "basic"     # 基础版：纯本地统计
MODE_AI = "ai"           # AI 版：附带大模型深度分析

MODE_LABEL = {MODE_BASIC: "基础版", MODE_AI: "AI 版"}

# 小于这个时长（分钟）就当作"没学"，避免几秒的误点开被当成有效数据
MIN_MEANINGFUL_MINUTES = 1


# AI 分析师的人设与约束。
# 关键约束的目的：
#   * 不许引入新数字 —— 模型很容易顺着数据"推算"出看似合理但错误的数字，
#     一旦报告里的数字不可信，整份报告就没价值了
#   * 不许说教和空话 —— "要保持专注"这类建议对用户零帮助
#   * 必须允许说"数据不足" —— 免得为了凑内容硬编
AI_ANALYST_PROMPT = """你是一位务实的学习效率分析师。用户会给你一份学习统计数据，
请基于这些数据写一段深度分析。

要求：
1. **只能使用给出的数字**，绝对不要自己推算、估算或引入任何新数字。
   如果你想说某个比例，而数据里没有，就不要说。
2. 用 Markdown 二级小标题组织内容，围绕这四块分析：
   - **整体状态**：这段时间的学习节奏怎么样（结合总量、每日分布、零学习天数）
   - **时间利用**：屏幕时间与有效学习的比例说明了什么；最专注的时段是否
     被合理利用；有没有明显的分心迹象
   - **值得注意的信号**：从数据里挑出 1~3 个真正值得留意的点
     （例如某天异常、应用构成偏科、连续专注能力、目标达成情况）
   - **下一步建议**：给 2~3 条具体、可立刻执行的建议。
     要具体到"做什么、什么时候做"，不要写"要保持专注""要提高效率"
     这种放到谁身上都成立的空话。
3. 语气客观直接，像一个了解情况的教练，不要奉承也不要训斥。
4. 如果数据太少（例如只有十几分钟或只有一两天），就直接说明
   "数据还太少，暂时看不出稳定规律"，然后只给一条最基础的起步建议。
   不要为了凑内容硬编分析。
5. 全文控制在 400 字以内，不要重复罗列我已经给你的数字。"""


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
    """生成学习/工作报告。"""

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

        data["has_data"] = bool(
            int(data["total_study_seconds"] // 60) >= MIN_MEANINGFUL_MINUTES
            or data["tasks"])
        return data

    # ── 给界面用的结构化入口 ────────────────────────────────
    def snapshot(self, period: str = PERIOD_TODAY) -> dict:
        """取一份渲染用的数据快照。

        界面按**数据**渲染成卡片，而不是去解析 Markdown 字符串 ——
        后者既脆弱又不好控制样式。Markdown 只用于导出。
        """
        return self.collect(period)

    def suggestions(self, data: dict) -> list:
        """基于数据的客观观察（供界面与 Markdown 共用）。"""
        return self._suggestions(data)

    @staticmethod
    def is_sparse(data: dict) -> bool:
        """数据是否过少（导出的报告会几乎是空的）。

        判定标准不是"有没有数据"，而是"数据够不够撑起一份报告"：
        只有一两天记录时报出的月度报告几乎全是 0，用户打开会以为文件坏了。
        """
        if not data.get("has_data"):
            return True
        days_with_data = sum(1 for v in (data.get("daily") or {}).values() if v > 0)
        return days_with_data <= 1 and len(data.get("days", [])) > 1

    # ── AI 分析 ─────────────────────────────────────────────
    def build_ai_digest(self, data: dict) -> str:
        """把统计数据整理成给模型的摘要。

        刻意只给**已经算好的数字**，并要求模型不得引入新数字 ——
        否则模型会自行推算或编造，报告就不可信了。
        """
        parts = ["统计区间：%s ~ %s（共 %d 天）"
                 % (data["days"][0], data["days"][-1], len(data["days"]))]
        parts.append("有效学习总时长：%s" % _fmt_seconds(data["total_study_seconds"]))
        parts.append("屏幕总时长：%s" % _fmt_seconds(data["total_screen_seconds"]))
        if data["total_screen_seconds"] > 0:
            parts.append("学习占屏幕比例：%.0f%%"
                         % (data["total_study_seconds"]
                            / data["total_screen_seconds"] * 100))
        parts.append("完成任务数：%d" % len(data["tasks"]))

        focus = data["focus"] or {}
        if focus.get("sessions"):
            parts.append("记录段数：%d（其中单次≥5 分钟的 %d 段）"
                         % (focus.get("sessions", 0), focus.get("meaningful", 0)))
        if focus.get("longest_secs"):
            parts.append("最长连续专注：%s" % _fmt_seconds(focus["longest_secs"]))

        if len(data["days"]) > 1:
            per_day = ["%s %s" % (day, _fmt_seconds(secs))
                       for day, secs in sorted(data["daily"].items())]
            parts.append("每日分布：" + "；".join(per_day))
            vals = [v for v in data["daily"].values()]
            parts.append("零学习天数：%d" % sum(1 for v in vals if v <= 0))

        if data["apps"]:
            top = sorted(data["apps"].items(), key=lambda kv: -kv[1])[:6]
            parts.append("主要用在：" + "、".join(
                "%s %s" % (a, _fmt_seconds(s)) for a, s in top))

        if data["best_hour"] is not None:
            parts.append("最专注时段：%02d:00-%02d:00"
                         % (data["best_hour"], data["best_hour"] + 1))
            hourly = [(h, round(s / 60)) for h, s in enumerate(data["hourly"])
                      if s >= 60]
            if hourly:
                parts.append("各时段分钟数：" + "、".join(
                    "%02d 点 %d 分" % (h, m) for h, m in hourly))

        if data["tasks"]:
            names = [t["text"] for t in data["tasks"][:10]]
            parts.append("完成的任务：" + "、".join(names))

        goal = data["goal"]
        if goal and goal.get("has_goal"):
            parts.append("每日目标 %d 分钟，今日完成 %d%%"
                         % (goal["goal_minutes"], round(goal.get("ratio", 0) * 100)))
        else:
            parts.append("用户还没有设置每日目标")
        return "\n".join(parts)

    def analyze_with_ai(self, period: str = PERIOD_TODAY,
                        transport=None, timeout: int = 45) -> dict:
        """生成 AI 深度分析。

        transport: callable(messages) -> str，由界面注入（复用用户配置的 API）。
        返回 {"ok": bool, "text": str, "error": str}
        """
        if transport is None:
            return {"ok": False, "text": "", "error": "未配置 API Key，无法生成 AI 分析"}

        data = self.collect(period)
        if not data["has_data"]:
            return {"ok": False, "text": "",
                    "error": "%s还没有足够的学习记录，先生成一些数据再用 AI 分析"
                             % data["period_label"]}

        digest = self.build_ai_digest(data)
        messages = [
            {"role": "system", "content": AI_ANALYST_PROMPT},
            {"role": "user", "content": "以下是我的学习数据，请分析：\n\n" + digest},
        ]
        try:
            text = transport(messages)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "text": "",
                    "error": "调用模型失败：%s" % str(exc)[:120]}
        text = (text or "").strip()
        if not text:
            return {"ok": False, "text": "", "error": "模型返回了空内容"}
        return {"ok": True, "text": text, "error": ""}

    # ── 渲染：Markdown ──────────────────────────────────────
    def render_markdown(self, period: str = PERIOD_TODAY,
                        ai_text: str = "", mode: str = MODE_BASIC) -> str:
        d = self.collect(period)
        lines = ["# 学习/工作报告 · %s" % d["period_label"]]
        if d["period"] != PERIOD_TODAY:
            lines.append("")
            lines.append("统计区间：%s ~ %s" % (d["days"][0], d["days"][-1]))
        lines.append("")
        lines.append("生成时间：%s" % d["generated_at"])
        lines.append("版本：%s" % MODE_LABEL.get(mode, "基础版"))
        lines.append("")

        if not d["has_data"]:
            lines.append("> 这段时间还没有足够的学习记录。")
            lines.append(">")
            lines.append("> 开始用 ToYu 专注学习后，这里会自动出现统计：")
            lines.append("> 有效学习时长、应用分布、时段分析、完成任务清单。")
            if ai_text:
                lines.append("")
                lines.append("## 🤖 AI 深度分析")
                lines.append("")
                lines.append(ai_text)
            return "\n".join(lines)

        # 数据过少时先说明，避免拿到文件的人以为报告坏了
        if self.is_sparse(d):
            lines.append("> ⚠ 本区间记录到的学习数据很少，"
                         "因此下面多处显示为 0。")
            lines.append(">")
            lines.append("> 这不是报告出错，而是 ToYu 在这段时间里"
                         "没有被使用（或屏幕时间采集未开启）。")
            lines.append("> 连续使用几天后，报告会明显更有参考价值。")
            lines.append("")

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
            # hourly 是秒；_bar 收的是分钟。这里必须先换算，
            # 否则比例会被放大 60 倍，条形图一律顶满而时长显示 0 分钟。
            hourly_minutes = [s / 60.0 for s in d["hourly"]]
            peak = max(hourly_minutes) if hourly_minutes else 0
            if peak > 0:
                lines.append("```")
                for hour in range(24):
                    mins = hourly_minutes[hour]
                    if mins < 0.5:
                        continue
                    lines.append("%02d:00 %s %s"
                                 % (hour, _bar(mins, peak, 20),
                                    _fmt_minutes(round(mins))))
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
            lines.append("## 观察与建议（基于数据）")
            lines.append("")
            for tip in tips:
                lines.append("- %s" % tip)
            lines.append("")

        # ── AI 深度分析（AI 版才追加）──
        if ai_text:
            lines.append("## 🤖 AI 深度分析")
            lines.append("")
            lines.append(ai_text.strip())
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append("*以上分析由 AI 基于本报告的统计数据生成，"
                         "仅供参考；统计数字均由本机记录计算得出。*")
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
               directory: str | None = None, ai_text: str = "",
               mode: str = MODE_BASIC) -> str:
        """导出报告文件，返回文件路径。

        同名文件自动加序号，不覆盖已有文件。
        AI 版会在文件名里标出 _AI版，避免和基础版混淆。
        """
        if fmt == "md":
            content = self.render_markdown(period, ai_text=ai_text, mode=mode)
        else:
            content = self.render_text(period, max_chars=100000)
            if ai_text:
                content += "\n\n=== AI 深度分析 ===\n" + ai_text.strip()
        out_dir = directory or REPORT_DIR
        os.makedirs(out_dir, exist_ok=True)

        stamp = datetime.now().strftime("%Y-%m-%d")
        suffix = "_AI版" if (ai_text and mode == MODE_AI) else ""
        base = "学习工作报告_%s_%s%s" % (
            PERIOD_LABEL.get(period, "今日"), stamp, suffix)
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
