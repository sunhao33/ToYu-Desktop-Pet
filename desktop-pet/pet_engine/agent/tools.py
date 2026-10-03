"""工具注册表 —— 6 个首批工具。

每个工具都调用 ToYu 界面**已有的入口**（TodoWidget / MainWindow），
不新造数据通路 —— 这样 AI 做的操作和用户手点的效果完全一致，
也不会出现"AI 改了数据但界面没刷新"的问题。
"""

from __future__ import annotations

from typing import Any

from pet_engine.agent.protocol import ToolSpec

# 参数 schema 里复用的片段
_TODO_TEXT = {
    "type": "string",
    "minLength": 1,
    "maxLength": 200,
}


class ToolRegistry:
    """工具注册表：注册、查询、生成 schema、分派执行。"""

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    # ── 注册 ────────────────────────────────────────────────
    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def all(self) -> list[ToolSpec]:
        return [self._tools[n] for n in self.names()]

    def schemas(self) -> list[dict]:
        """喂给模型的工具定义列表。"""
        return [t.schema() for t in self.all()]

    def __len__(self) -> int:
        return len(self._tools)


def build_default_registry(main_window) -> ToolRegistry:
    """构建首批 6 个工具。

    main_window 为 None 时（例如纯逻辑测试）仍然返回注册表，
    但执行时会被 handler 内部的安全检查拒绝 —— 不抛异常。
    """
    reg = ToolRegistry()

    def _todo():
        return getattr(main_window, "_todo_widget", None)

    # ── 待办：新增 ──────────────────────────────────────────
    def add_todo(text: str) -> str:
        widget = _todo()
        if widget is None:
            return "失败：待办组件不可用"
        try:
            widget._input.setText(text)
            widget._on_add()
        except RuntimeError:
            return "失败：待办组件已被销毁"
        total = len(getattr(widget, "todos", []))
        return "已添加待办「%s」，当前共 %d 条" % (text, total)

    reg.register(ToolSpec(
        name="add_todo",
        description="给用户添加一条待办事项。当用户说「帮我记一下」「加个待办」"
                    "「我要做…」时使用。",
        parameters={
            "type": "object",
            "properties": {
                "text": dict(_TODO_TEXT, description="待办内容，简洁的一句话"),
            },
            "required": ["text"],
        },
        handler=add_todo,
        returns="添加结果与当前待办总数",
    ))

    # ── 待办：完成 ──────────────────────────────────────────
    def complete_todo(text: str) -> str:
        widget = _todo()
        if widget is None:
            return "失败：待办组件不可用"
        try:
            target = None
            keyword = text.strip()
            for item in getattr(widget, "todos", []):
                if item.text == keyword:
                    target = item
                    break
            if target is None:
                for item in getattr(widget, "todos", []):
                    if keyword and keyword in item.text:
                        target = item
                        break
            if target is None:
                pending = [t.text for t in getattr(widget, "todos", []) if not t.done]
                return "没找到「%s」。当前未完成待办：%s" % (
                    text, "、".join(pending[:8]) or "（空）")
            if target.done:
                return "「%s」已经是完成状态" % target.text
            widget._toggle_todo_by_ref(target)
        except RuntimeError:
            return "失败：待办组件已被销毁"
        return "已把「%s」标记为完成" % target.text

    reg.register(ToolSpec(
        name="complete_todo",
        description="把某条待办标记为已完成。text 可以是完整名称，也可以是"
                    "能唯一匹配的部分内容。",
        parameters={
            "type": "object",
            "properties": {
                "text": dict(_TODO_TEXT, description="要完成的待办名称或其中的关键词"),
            },
            "required": ["text"],
        },
        handler=complete_todo,
        returns="完成结果；找不到时返回当前未完成列表",
    ))

    # ── 待办：查看 ──────────────────────────────────────────
    def list_todos(include_done: bool = False) -> str:
        widget = _todo()
        if widget is None:
            return "失败：待办组件不可用"
        try:
            todos = list(getattr(widget, "todos", []))
        except RuntimeError:
            return "失败：待办组件已被销毁"
        pending = [t for t in todos if not t.done]
        done = [t for t in todos if t.done]
        if not todos:
            return "用户目前还没有任何待办"
        lines = ["未完成 %d 条：%s" % (len(pending),
                                     "、".join(t.text for t in pending) or "（无）")]
        if include_done:
            lines.append("已完成 %d 条：%s" % (len(done),
                                            "、".join(t.text for t in done) or "（无）"))
        else:
            lines.append("已完成 %d 条" % len(done))
        return "\n".join(lines)

    reg.register(ToolSpec(
        name="list_todos",
        description="查看用户的待办列表。用户问「我还有什么要做」「待办有哪些」"
                    "或你需要先了解情况再决定下一步时使用。",
        parameters={
            "type": "object",
            "properties": {
                "include_done": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否一并列出已完成的事项",
                },
            },
        },
        handler=list_todos,
        returns="未完成与已完成的数量与内容",
    ))

    # ── 专注：开始 ──────────────────────────────────────────
    def start_focus(minutes: int = 25) -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        try:
            main_window.start_focus_session(int(minutes))
        except RuntimeError:
            return "失败：计时组件已被销毁"
        return "已开始 %d 分钟专注计时（桌面右上角会出现计时小窗）" % int(minutes)

    reg.register(ToolSpec(
        name="start_focus",
        description="开始一段专注倒计时。用户说「我要专注」「开始计时」"
                    "「来个番茄钟」时使用。",
        parameters={
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "default": 25,
                    "minimum": 1,
                    "maximum": 600,
                    "description": "专注时长（分钟），没说就用 25",
                },
            },
        },
        handler=start_focus,
        returns="计时是否已开始",
    ))

    # ── 专注：停止 ──────────────────────────────────────────
    def stop_focus() -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        try:
            timer = getattr(main_window, "_timer_widget", None)
            if timer is None:
                return "失败：计时组件不可用"
            if not timer.get_is_running() and timer.get_remaining_seconds() <= 0:
                return "当前没有正在进行的专注计时"
            elapsed = timer.get_elapsed_seconds()
            main_window.stop_focus_session()
        except RuntimeError:
            return "失败：计时组件已被销毁"
        return "已停止专注计时（本次已专注 %d 分钟）" % (elapsed // 60)

    reg.register(ToolSpec(
        name="stop_focus",
        description="停止当前的专注计时。用户说「不专注了」「停一下」"
                    "「结束计时」时使用。",
        parameters={"type": "object", "properties": {}},
        handler=stop_focus,
        returns="停止结果与本次已专注时长",
    ))

    # ── 学习数据 ────────────────────────────────────────────
    def get_learning_stats() -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        parts = []

        # 今日已完成任务与累计时长（读任务历史）
        try:
            todo = _todo()
            if todo is not None:
                history = todo.get_task_history()
                from datetime import date
                today = history.get(date.today().isoformat(), [])
                total = sum(int(t.get("duration", 0) or 0) for t in today)
                names = [t.get("text", "") for t in today]
                parts.append("今日已完成 %d 项任务，累计 %d 分钟%s" % (
                    len(today), total // 60,
                    ("：" + "、".join(names[:6])) if names else ""))
        except (RuntimeError, AttributeError):
            pass

        # 今日屏幕时间与记录段数
        try:
            tracker = getattr(main_window, "_screen_tracker", None)
            if tracker is not None:
                secs = sum(int(s) for _a, s in tracker.get_today_data())
                sessions = len(tracker.get_sessions())
                parts.append("今日屏幕时间约 %d 小时 %d 分，共 %d 段记录" % (
                    secs // 3600, (secs % 3600) // 60, sessions))
        except (RuntimeError, AttributeError, TypeError):
            pass

        if not parts:
            return "暂时拿不到学习数据（统计组件可能还没就绪）"
        return "\n".join(parts)

    reg.register(ToolSpec(
        name="get_learning_stats",
        description="查询用户今天的学习情况：完成了多少任务、累计学习多久、"
                    "屏幕时间多长。用户问「我今天学得怎么样」「我今天专注了多久」"
                    "时使用。",
        parameters={"type": "object", "properties": {}},
        handler=get_learning_stats,
        returns="今日任务完成情况、累计时长、屏幕时间",
    ))

    return reg
