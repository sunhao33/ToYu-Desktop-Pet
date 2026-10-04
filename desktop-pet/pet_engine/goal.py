"""每日专注目标 —— 进度计算与达成判定。

目标值来源优先级（高的覆盖低的）：
  1. 用户在界面上直接设的值（QSettings 里的 ui/daily_goal_minutes）
  2. 长期记忆里的 study.daily_goal_minutes（用户说过"我打算每天学 4 小时"）
  3. 没设 → 返回 None，界面显示"未设目标"，**不硬塞一个默认值**
     （硬塞会让人天天"未达成"，反而打击积极性）

进度来源：屏幕时间记录里的「有效学习时长」——只算学习类应用里
单次连续 ≥ MIN_SESSION_SECONDS 的会话，避免"点开就关"的噪声把目标刷满。
"""

from __future__ import annotations

from datetime import date

# 计入学习时长的最小连续时长（秒）。低于这个的算误点开，不计入。
MIN_SESSION_SECONDS = 180

# 学习类应用关键词（小写匹配）。用于从屏幕时间里挑出"算学习"的部分。
STUDY_APP_KEYWORDS = (
    # 编辑器 / IDE
    "code", "pycharm", "idea", "studio", "vim", "sublime", "jupyter",
    "cursor", "windsurf", "trae", "neovim", "emacs", "rstudio", "spyder",
    # 文档 / 笔记
    "word", "excel", "powerpnt", "wps", "typora", "obsidian", "notion",
    "onenote", "evernote", "logseq", "marktext", "zim",
    # 文献 / 阅读
    "acrobat", "pdf", "foxit", "sumatra", "caj", "zotero", "mendeley",
    "calibre", "kindle",
    # 专业工具
    "matlab", "spss", "anaconda", "python", "julia", "octave", "stata",
    "autocad", "solidworks", "mathematica", "origin", "chemdraw",
    # 终端 / 开发辅助
    "cmd", "powershell", "terminal", "xshell", "putty", "mobaxterm",
    "git", "sourcetree", "postman", "docker", "wsl",
    # AI 助手（写代码、查资料、解释概念都算学习行为）
    "chatgpt", "claude", "deepseek", "copilot", "kimi", "doubao", "豆包",
    "tongyi", "通义", "wenxin", "文心", "chatglm", "智谱", "harness",
)

# 明显是娱乐的（即使标题像学习也不算）—— 宁可不计入，也不虚增
ENTERTAINMENT_APP_KEYWORDS = (
    "bilibili", "哔哩哔哩", "iqiyi", "爱奇艺", "youku", "优酷", "douyin",
    "抖音", "tencentvideo", "腾讯视频", "steam", "wegame", "game",
    "netease", "网易云", "qqmusic", "spotify", "y.qq.com",
)

# 浏览器 / 通用阅读器：本身不判断，要看**窗口标题**里在干什么。
# 查资料、看文档是典型学习行为，不该一律排除；
# 但也不能把浏览器一律算学习，否则看视频也成了学习。
BROWSER_APP_KEYWORDS = (
    "chrome", "msedge", "edge", "firefox", "浏览器", "safari", "opera",
    "360se", "qqbrowser", "iexplore",
)

# 标题里出现这些词，浏览器里也算学习
STUDY_TITLE_KEYWORDS = (
    "论文", "文献", "课程", "课件", "教程", "讲义", "习题", "考题", "真题",
    "复习", "笔记", "实验报告", "毕业设计", "开题", "答辩",
    "文档", "手册", "api", "docs", "documentation", "reference",
    "github", "gitlab", "stack overflow", "stackoverflow", "csdn",
    "博客园", "掘金", "知乎", "wiki", "百科",
    "算法", "数据结构", "机器学习", "深度学习", "神经网络", "数学", "物理",
    "英语", "单词", "翻译", "考研", "考试", "作业", "报告",
    "coursera", "edx", "mooc", "学堂在线", "中国大学", "超星", "学习通",
)

# 标题里出现这些词，即使在"学习类"应用里也不算（比如 IDE 里开着视频）
DISTRACTION_TITLE_KEYWORDS = (
    "哔哩哔哩", "bilibili", "直播", "游戏", "抖音", "快手",
    "电视剧", "综艺", "动漫", "番剧",
)


def is_study_app(app: str, title: str = "") -> bool:
    """判断这条记录算不算"学习"。

    规则（顺序很重要）：
      1. 标题里有明确的娱乐词 → 不算（优先级最高，避免边学边玩被算满）
      2. 应用本身是学习工具（IDE / Office / 阅读器）→ 算
      3. 应用是娱乐应用 → 不算
      4. 应用是浏览器 → 只有标题里出现学习关键词才算
      5. 其他 → 不算（宁缺毋滥，不虚增时长）
    """
    app_l = (app or "").lower()
    title_l = (title or "").lower()
    blob = "%s %s" % (app_l, title_l)
    if not blob.strip():
        return False

    for kw in DISTRACTION_TITLE_KEYWORDS:
        if kw in title_l:
            return False
    for kw in ENTERTAINMENT_APP_KEYWORDS:
        if kw in blob:
            return False
    for kw in STUDY_APP_KEYWORDS:
        if kw in blob:
            return True
    # 浏览器：看标题在干什么
    if any(kw in app_l for kw in BROWSER_APP_KEYWORDS):
        return any(kw in title_l for kw in STUDY_TITLE_KEYWORDS)
    return False


def study_seconds_from_sessions(sessions, min_session=MIN_SESSION_SECONDS) -> float:
    """从会话记录里算出"有效学习时长"（秒）。

    只统计学习类应用、且单次连续不少于 min_session 的会话。
    """
    total = 0.0
    for sess in sessions or []:
        if not isinstance(sess, dict):
            continue
        secs = float(sess.get("secs", 0) or 0)
        if secs < min_session:
            continue
        if is_study_app(sess.get("app", ""), sess.get("title", "")):
            total += secs
    return total


class DailyGoalTracker:
    """每日目标的读写与进度计算。"""

    # QSettings 键名
    KEY_GOAL = "goal/daily_minutes"
    KEY_CELEBRATED = "goal/celebrated_dates"
    KEY_LAST_PERIOD = "goal/last_period"

    def __init__(self, settings=None, tracker=None, memory_store=None):
        self._settings = settings
        self._tracker = tracker          # ScreenTimeTracker
        self._memory = memory_store      # MemoryStore（可为 None）

    # ── 目标值 ──────────────────────────────────────────────
    def goal_minutes(self):
        """当前目标（分钟）。没设返回 None。"""
        explicit = self._explicit_goal()
        if explicit:
            return explicit
        remembered = self._remembered_goal()
        if remembered:
            return remembered
        return None

    def _explicit_goal(self):
        if self._settings is None:
            return None
        try:
            val = self._settings._settings.value(self.KEY_GOAL, 0)
            minutes = int(val or 0)
            return minutes if minutes > 0 else None
        except (AttributeError, TypeError, ValueError):
            return None

    def _remembered_goal(self):
        """从长期记忆里取 study.daily_goal_minutes。"""
        if self._memory is None:
            return None
        try:
            record = self._memory.get("study.daily_goal_minutes")
        except Exception:  # noqa: BLE001
            return None
        if record is None:
            return None
        try:
            minutes = int(record.value)
            return minutes if minutes > 0 else None
        except (TypeError, ValueError):
            return None

    def set_goal_minutes(self, minutes):
        """设置目标。传 0 或 None 表示清除。"""
        if self._settings is None:
            return
        try:
            if not minutes:
                self._settings._settings.remove(self.KEY_GOAL)
            else:
                self._settings._settings.setValue(self.KEY_GOAL, int(minutes))
        except (AttributeError, TypeError, ValueError):
            pass

    def goal_source(self):
        """目标来自哪里（界面用来提示用户）。"""
        if self._explicit_goal():
            return "manual"
        if self._remembered_goal():
            return "memory"
        return "none"

    # ── 进度 ────────────────────────────────────────────────
    def today_study_seconds(self, date_str=None) -> float:
        """今天（或指定日期）的有效学习时长（秒）。"""
        if self._tracker is None:
            return 0.0
        try:
            sessions = self._tracker.get_sessions(date_str)
        except Exception:  # noqa: BLE001
            return 0.0
        return study_seconds_from_sessions(sessions)

    def progress(self, date_str=None) -> dict:
        """返回进度信息（供界面渲染）。"""
        today = date_str or date.today().isoformat()
        goal = self.goal_minutes()
        seconds = self.today_study_seconds(today)
        minutes = int(seconds // 60)

        info = {
            "date": today,
            "goal_minutes": goal,
            "study_minutes": minutes,
            "study_seconds": int(seconds),
            "source": self.goal_source(),
            "ratio": 0.0,
            "reached": False,
            "remaining_minutes": 0,
            "has_goal": goal is not None,
        }
        if goal:
            info["ratio"] = max(0.0, min(1.0, seconds / (goal * 60.0)))
            info["reached"] = seconds >= goal * 60
            info["remaining_minutes"] = max(0, goal - minutes)
        return info

    # ── 达成庆祝（每天只一次）────────────────────────────────
    def _celebrated(self) -> set:
        if self._settings is None:
            return set()
        try:
            raw = self._settings._settings.value(self.KEY_CELEBRATED, "")
        except AttributeError:
            return set()
        if not raw:
            return set()
        if isinstance(raw, (list, tuple)):
            return {str(x) for x in raw}
        return {p for p in str(raw).split(",") if p}

    def _save_celebrated(self, days: set):
        if self._settings is None:
            return
        # 只保留最近 60 天，避免键值无限增长
        recent = sorted(days)[-60:]
        try:
            self._settings._settings.setValue(self.KEY_CELEBRATED, ",".join(recent))
        except AttributeError:
            pass

    def should_celebrate(self, date_str=None) -> bool:
        """是否该为"今天达成目标"庆祝一次（已庆祝过就返回 False）。"""
        today = date_str or date.today().isoformat()
        info = self.progress(today)
        if not info["reached"]:
            return False
        if today in self._celebrated():
            return False
        days = self._celebrated()
        days.add(today)
        self._save_celebrated(days)
        return True

    def text(self) -> str:
        """给界面用的一行文案。"""
        info = self.progress()
        if not info["has_goal"]:
            return "今日学习 %d 分钟 · 未设目标" % info["study_minutes"]
        if info["reached"]:
            return "今日学习 %d 分钟 · 已达成目标（%d 分钟）✓" % (
                info["study_minutes"], info["goal_minutes"])
        return "今日学习 %d / %d 分钟 · 还差 %d 分钟" % (
            info["study_minutes"], info["goal_minutes"],
            info["remaining_minutes"])
