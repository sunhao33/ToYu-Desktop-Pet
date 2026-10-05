"""桌面状态上下文 —— 让 AI 知道"用户现在在干什么"。

设计要点：
  * **硬预算**：整块不超过 TOKEN_BUDGET（约 400 token）。超了就按优先级
    从低到高丢弃整块，而不是截半句话 —— 截断的上下文比没有更糟。
  * **优先级明确**：待办 > 今日专注 > 日程 > 宠物状态 > 前台应用 > 剪贴板。
    用户最可能问的和最相关的排前面。
  * **隐私默认关闭**：剪贴板内容与前台应用名**默认不注入**，
    需要在设置里显式开启。这两项是隐私敏感项，不能因为"有用"就默认开着。
  * **失败即降级**：任何一块取不到数据就跳过，绝不让上下文构建失败影响聊天。
"""

from __future__ import annotations

import os
from datetime import date
# 整块预算（字符数近似 token：中文约 1 字 1 token，英文约 4 字符 1 token，
# 这里按保守估计取 1.2 字符 ≈ 1 token）
TOKEN_BUDGET = 400
CHAR_BUDGET = int(TOKEN_BUDGET * 1.2)

# 优先级：数字越小越先保留。第二项是给人看的名字（会在"未包含"里出现）
BLOCKS = (
    ("todos", "待办", 1),
    ("focus", "学习情况", 2),
    ("schedule", "日程", 3),
    ("pet", "宠物状态", 4),
    ("foreground", "当前应用", 5),
    ("clipboard", "剪贴板", 6),
)
PRIORITY = {name: prio for name, _label, prio in BLOCKS}
LABELS = {name: label for name, label, _prio in BLOCKS}

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")

def _fmt_minutes(seconds: int) -> str:
    if seconds >= 3600:
        return "%d 小时 %d 分" % (seconds // 3600, (seconds % 3600) // 60)
    return "%d 分钟" % (seconds // 60)

class DesktopContextBuilder:
    """从主窗口收集"桌面状态"，拼成一段可注入的文本。"""

    def __init__(self, main_window=None, settings=None):
        self._main = main_window
        self._settings = settings or getattr(main_window, "settings", None)

    # ── 各数据块 ────────────────────────────────────────────
    def _block_todos(self) -> str:
        widget = getattr(self._main, "_todo_widget", None)
        if widget is None:
            return ""
        try:
            todos = list(getattr(widget, "todos", []))
        except RuntimeError:
            return ""
        pending = [t.text for t in todos if not t.done]
        done = sum(1 for t in todos if t.done)
        if not todos:
            return "待办：暂无"
        if not pending:
            return "待办：全部完成（共 %d 项）" % done
        head = "、".join(pending[:6])
        # 块内截断：只列前几条。措辞与"整块被丢弃"区分开，
        # 否则用户（和测试）分不清是列表被截短了还是整块没进去
        more = "（另有 %d 项未列出）" % (len(pending) - 6) if len(pending) > 6 else ""
        return "待办 %d 项未完成：%s%s" % (len(pending), head, more)

    def _block_focus(self) -> str:
        parts = []

        # 今日已完成任务与累计时长
        try:
            todo = getattr(self._main, "_todo_widget", None)
            if todo is not None:
                history = todo.get_task_history()
                today = history.get(date.today().isoformat(), [])
                total = sum(int(t.get("duration", 0) or 0) for t in today)
                if today:
                    parts.append("今日完成 %d 项、累计 %s" % (len(today), _fmt_minutes(total)))
                else:
                    parts.append("今日还没有完成的任务")
        except (RuntimeError, AttributeError, TypeError, ValueError):
            pass

        # 正在进行的专注
        try:
            timer = getattr(self._main, "_timer_widget", None)
            if timer is not None and timer.get_is_running():
                parts.append("正在专注（剩余 %s）"
                             % _fmt_minutes(timer.get_remaining_seconds()))
        except (RuntimeError, AttributeError):
            pass

        # 今日屏幕时间
        try:
            tracker = getattr(self._main, "_screen_tracker", None)
            if tracker is not None:
                secs = sum(int(s) for _a, s in tracker.get_today_data())
                if secs >= 60:
                    parts.append("屏幕时间约 %s" % _fmt_minutes(secs))
        except (RuntimeError, AttributeError, TypeError):
            pass

        return ("学习情况：" + "；".join(parts)) if parts else ""

    def _block_schedule(self) -> str:
        """今天与明天的日历标注。"""
        calendar = getattr(self._main, "_calendar", None)
        if calendar is None:
            return ""
        try:
            events = getattr(calendar, "_events", {}) or {}
        except RuntimeError:
            return ""
        if not isinstance(events, dict):
            return ""
        today = date.today()
        labels = []
        for delta, name in ((0, "今天"), (1, "明天")):
            key = (today.fromordinal(today.toordinal() + delta)).isoformat()
            items = events.get(key) or []
            texts = [str(e.get("text", "")).strip() for e in items
                     if isinstance(e, dict) and str(e.get("text", "")).strip()]
            if texts:
                labels.append("%s：%s" % (name, "、".join(texts[:3])))
        return ("日程：" + "；".join(labels)) if labels else ""

    def _block_pet(self) -> str:
        pet = getattr(self._main, "_pet", None)
        if pet is None:
            return "宠物：尚未启动"
        try:
            level = pet.affection.level
        except (RuntimeError, AttributeError):
            return ""
        mood = ""
        try:
            mood = pet.companion.get_status_text()
        except (RuntimeError, AttributeError):
            pass
        return "宠物：好感度 %d/100%s" % (level, ("，" + mood) if mood else "")

    def _block_foreground(self) -> str:
        """前台应用名 —— 隐私敏感，需显式开启。"""
        if not self._privacy_enabled("context/foreground_enabled"):
            return ""
        try:
            tracker = getattr(self._main, "_screen_tracker", None)
            if tracker is None:
                return ""
            sessions = tracker.get_sessions() or []
            if not sessions:
                return ""
            latest = sessions[-1]
            app = os.path.basename(str(latest.get("app", "")))
            title = str(latest.get("title", "")).strip()
            if not app:
                return ""
            return "当前应用：%s%s" % (app, ("（%s）" % title[:30]) if title else "")
        except (RuntimeError, AttributeError, TypeError, IndexError):
            return ""

    def _block_clipboard(self) -> str:
        """剪贴板最近内容 —— 隐私敏感，需显式开启。"""
        if not self._privacy_enabled("context/clipboard_enabled"):
            return ""
        try:
            hub = getattr(self._main, "_tools_hub", None)
            if hub is None:
                return ""
            history = getattr(hub.clipboard, "history", None) or []
            texts = []
            for item in history[:2]:
                text = str(item.get("text", "")).strip().replace("\n", " ")
                if text and not text.startswith("[图片]"):
                    texts.append(text[:40])
            if not texts:
                return ""
            return "剪贴板最近：%s" % " ｜ ".join(texts)
        except (RuntimeError, AttributeError, TypeError):
            return ""

    def _privacy_enabled(self, key: str) -> bool:
        if self._settings is None:
            return False
        try:
            val = self._settings._settings.value(key, False)
        except AttributeError:
            return False
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    # ── 组装 ────────────────────────────────────────────────
    def build(self, extra: str = "") -> str:
        """构建状态块。超预算时按优先级丢弃整块。"""
        blocks = []
        for name, getter in (
            ("todos", self._block_todos),
            ("focus", self._block_focus),
            ("schedule", self._block_schedule),
            ("pet", self._block_pet),
            ("foreground", self._block_foreground),
            ("clipboard", self._block_clipboard),
        ):
            try:
                text = getter()
            except Exception:  # noqa: BLE001 — 单块失败不能拖垮整体
                text = ""
            if text:
                blocks.append((PRIORITY.get(name, 9), name, text))

        blocks.sort(key=lambda item: item[0])

        kept = []
        used = 0
        dropped = []
        for _prio, name, text in blocks:
            cost = len(text) + 1
            if used + cost > CHAR_BUDGET:
                dropped.append(LABELS.get(name, name))
                continue
            kept.append(text)
            used += cost

        if extra:
            extra = extra.strip()
            if extra and used + len(extra) <= CHAR_BUDGET:
                kept.append(extra)
            elif extra:
                dropped.append("临时附注")

        if not kept:
            return ""

        body = "\n".join(kept)
        header = "[当前状态]"
        if dropped:
            # 块级丢弃：整块没进去（与块内截断是两回事，措辞要能区分）
            # 用中文块名而不是内部标识，避免把 "pet" 这种词丢给模型看
            header += "（因长度限制未包含：%s）" % "、".join(dropped)
        return "%s\n%s" % (header, body)

    def stats(self) -> dict:
        """返回各块的字符占用，便于调试与展示。"""
        out = {}
        for name, getter in (
            ("todos", self._block_todos),
            ("focus", self._block_focus),
            ("schedule", self._block_schedule),
            ("pet", self._block_pet),
            ("foreground", self._block_foreground),
            ("clipboard", self._block_clipboard),
        ):
            try:
                out[name] = len(getter() or "")
            except Exception:  # noqa: BLE001
                out[name] = -1
        out["_budget"] = CHAR_BUDGET
        return out
