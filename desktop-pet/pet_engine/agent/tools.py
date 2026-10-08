"""工具注册表 —— 6 个首批工具。

每个工具都调用 ToYu 界面**已有的入口**（TodoWidget / MainWindow），
不新造数据通路 —— 这样 AI 做的操作和用户手点的效果完全一致，
也不会出现"AI 改了数据但界面没刷新"的问题。
"""

from __future__ import annotations

from pet_engine.agent.protocol import ToolSpec

# 参数 schema 里复用的片段。
# 说明文字刻意写得短：工具 schema 每次请求都要随 API 发送，
# 9 个工具的 schema 原本占 2452 字符（约 1226 token），比系统提示词还大。
# 精简原则：只留模型判断"什么时候用、填什么"必需的信息，删掉实现细节。
_TODO_TEXT = {
    "type": "string",
    "minLength": 1,
    "maxLength": 200,
}

# 「参数不合法」的专用前缀。
#
# 为什么要和「失败」区分开：Runtime 用 `text.startswith("失败")` 判断工具
# 是否失败，并据此累计"连续失败"次数，达到阈值就**熔断**该工具。
# 但**参数写错**与**工具坏了**是两回事 —— 前者模型看到错误信息后能自己
# 改对，后者才是真的没救。
#
# 不加区分的后果（已实测复现）：
#     模型把「番茄钟改 0 分钟」当一次失败   -> 记 1 次
#     接着改「601 分钟」又一次失败         -> 记 2 次，熔断
#     再改「30 分钟」（完全合法）           -> ★ 被熔断拒绝，无法自我纠正
#
# 所以参数类错误用这个前缀，Runtime 见到它不计入熔断，只把错误信息回灌
# 给模型重试 —— 与 schema 校验失败（arg_error）的既有处理保持一致。
ARG_ERROR_PREFIX = "参数错误："


# ── 偏好设置白名单 ───────────────────────────────────────────
#
# AI 能改哪些设置，**在这里一处收口**（同 slots.py 的思路：受控集合，
# 模型不得自创）。每一项都带一个 apply()，负责"改完立即生效"。
#
# 为什么不用「free-form 键值对」：模型可以编出任何键名，写进 QSettings
# 就是垃圾数据；而且自由键无法保证"改完界面真的跟着变"。
#
# 不放进白名单的（有意为之）：
#   · 自动启动 auto_start      —— 涉及开机行为，风险高
#   · 宠物坐标 pet_position    —— 用户拖出来的，不该被 AI 挪走
#   · 收藏夹 / 历史等数据类     —— 不是"设置"
class _Preference:
    """一条可被 AI 修改的设置。"""

    def __init__(self, apply_fn, describe, choices=""):
        self.apply = apply_fn
        self.describe = describe
        self.choices = choices


def _as_bool(value):
    """把模型给的值解析成布尔。拿不准就抛错（不猜）。"""
    v = str(value).strip().lower()
    if v in ("on", "true", "1", "yes", "开", "开启", "打开", "是"):
        return True
    if v in ("off", "false", "0", "no", "关", "关闭", "否"):
        return False
    raise ValueError("要 on 或 off，收到「%s」" % value)


def _as_int(value, low, high, unit=""):
    """解析整数并夹在 [low, high]，越界直接报错而不是静默截断。"""
    try:
        n = int(float(str(value).strip()))
    except (TypeError, ValueError):
        raise ValueError("要一个数字，收到「%s」" % value)
    if not (low <= n <= high):
        raise ValueError("范围是 %d~%d%s，收到 %d" % (low, high, unit, n))
    return n


def _apply_theme(mw, value):
    v = str(value).strip().lower()
    if v in ("dark", "深色", "暗色", "night"):
        want = True
    elif v in ("light", "浅色", "亮色", "day"):
        want = False
    else:
        raise ValueError("要 dark 或 light，收到「%s」" % value)
    if bool(getattr(mw, "_is_dark_mode", False)) != want:
        toggle = getattr(mw, "_toggle_dark_mode", None)
        if not callable(toggle):
            raise ValueError("主窗口不支持切换主题")
        toggle()
    return "深色" if want else "浅色"


def _apply_pomodoro(mw, value):
    on = _as_bool(value)
    check = getattr(mw, "_pomodoro_enable_check", None)
    if check is not None:
        check.setChecked(on)          # 走界面信号，状态与提示文案一起更新
    else:
        mw.settings.pomodoro_enabled = on
    updater = getattr(mw, "_update_pomodoro_status", None)
    if callable(updater):
        updater()
    return "开启" if on else "关闭"


def _apply_pomodoro_interval(mw, value):
    mins = _as_int(value, 5, 600, " 分钟")
    setter = getattr(mw, "_on_pomodoro_preset", None)
    if callable(setter):
        setter(mins)
    else:
        mw.settings.pomodoro_interval = mins
    return "%d 分钟" % mins


def _apply_eye_care(mw, value):
    on = _as_bool(value)
    hub = getattr(mw, "_tools_hub", None)
    if hub is not None and getattr(hub, "eye_care", None) is not None:
        hub.eye_care.set_enabled(on)
        if on:
            hub.eye_care.reset()      # 重新计时，避免立刻弹一条过期提醒
        page = getattr(mw, "_desktop_tools_page", None)
        refresher = getattr(page, "refresh_eye_care", None)
        if callable(refresher):
            refresher(hub.eye_care)
    else:
        mw.settings.eye_care_enabled = on
    return "开启" if on else "关闭"


def _apply_flow_mode(mw, value):
    on = _as_bool(value)
    active = bool(getattr(mw, "_flow_active", False))
    if on and not active:
        enter = getattr(mw, "enter_flow_mode", None)
        if not callable(enter):
            raise ValueError("主窗口不支持心流模式")
        enter()
    elif not on and active:
        exit_fn = getattr(mw, "exit_flow_mode", None)
        if not callable(exit_fn):
            raise ValueError("主窗口不支持退出心流模式")
        exit_fn()
    return "开启" if on else "关闭"


def _apply_pet_scale(mw, value):
    pet = getattr(mw, "_pet", None)
    if pet is None:
        raise ValueError("宠物还没启动")
    try:
        cur = float(pet._scale)
    except (AttributeError, TypeError, ValueError):
        cur = 1.0
    v = str(value).strip().lower()
    # 先按"相对说法"折算，再校验范围（不再用 max/min 静默截断）
    if v in ("bigger", "big", "大", "放大", "大一点"):
        target = cur + 0.2
    elif v in ("smaller", "small", "小", "缩小", "小一点"):
        target = cur - 0.2
    else:
        try:
            target = float(v)
        except (TypeError, ValueError):
            raise ValueError("要 0.5~2.0 的数字，或 bigger/smaller")

    if not (0.5 <= target <= 2.0):
        # 明确拒绝而不是静默截断：模型/用户说 2.1 却变成 2.0，
        # 回读时对不上，也违背工具描述里承诺的范围语义。
        raise ValueError("范围是 0.5~2.0，收到 %.2f" % target)
    pet.set_scale(target)             # set_scale 内部会夹范围并持久化
    return "%.1f 倍" % float(pet._scale)
    if not (0.5 <= target <= 2.0):
        # 明确拒绝而不是静默截断：模型/用户说 2.1 却变成 2.0，
        # 回读时对不上，也违背工具描述里承诺的范围语义。
        raise ValueError("范围是 0.5~2.0，收到 %.2f" % target)
    pet.set_scale(target)             # set_scale 内部会夹范围并持久化
    return "%.1f 倍" % float(pet._scale)


def _apply_pet_speed(mw, value):
    v = str(value).strip().lower()
    table = {
        "slow": (0.6, 1.4), "慢": (0.6, 1.4), "慢一点": (0.6, 1.4),
        "normal": (1.2, 2.6), "中": (1.2, 2.6), "正常": (1.2, 2.6),
        "fast": (2.0, 4.0), "快": (2.0, 4.0), "快一点": (2.0, 4.0),
    }
    if v not in table:
        raise ValueError("要 slow / normal / fast")
    lo, hi = table[v]
    mw.settings.walking_speed_min = lo
    mw.settings.walking_speed_max = hi
    pet = getattr(mw, "_pet", None)
    if pet is not None:
        try:
            pet.physics.update_speed_range(lo, hi)
        except (AttributeError, RuntimeError):
            pass                      # 运行中改速度失败不影响设置已保存
    return {"slow": "慢", "normal": "中", "fast": "快"}[
        {"慢": "slow", "慢一点": "slow", "中": "normal", "正常": "normal",
         "快": "fast", "快一点": "fast"}.get(v, v)]


def _apply_typing(mw, value):
    on = _as_bool(value)
    mw.settings.typing_enabled = on
    pet = getattr(mw, "_pet", None)
    if pet is not None:
        try:
            pet._typing_enabled = on
        except (AttributeError, RuntimeError):
            pass
    return "开启" if on else "关闭"


def _apply_house(mw, value):
    on = _as_bool(value)
    mw.settings.house_enabled = on
    if on:
        spawn = getattr(mw, "_spawn_house", None)
        if callable(spawn) and getattr(mw, "_house", None) is None:
            spawn()
    else:
        close = getattr(mw, "_close_house", None)
        if callable(close):
            close()
    return "开启" if on else "关闭"


def _apply_mini_timer(mw, value):
    on = _as_bool(value)
    mw.settings.mini_timer_enabled = on
    if not on:
        hide = getattr(mw, "hide_mini_timer", None)
        if callable(hide):
            hide()
    return "开启" if on else "关闭"


def _apply_daily_goal(mw, value):
    mins = _as_int(value, 10, 1440, " 分钟")
    ensure = getattr(mw, "_ensure_goal_tracker", None)
    tracker = ensure() if callable(ensure) else getattr(mw, "_goal_tracker", None)
    if tracker is None:
        raise ValueError("目标模块不可用")
    tracker.set_goal_minutes(mins)
    refresh = getattr(mw, "_refresh_goal", None)
    if callable(refresh):
        refresh()
    return "%d 分钟（%.1f 小时）" % (mins, mins / 60.0)


_PREFERENCE_KEYS = {
    "theme": _Preference(_apply_theme, "界面主题", "dark / light"),
    "pomodoro": _Preference(_apply_pomodoro, "番茄钟总开关", "on / off"),
    "interval": _Preference(_apply_pomodoro_interval,
                            "番茄钟提醒间隔（分钟）", "5 ~ 600"),
    "eye_care": _Preference(_apply_eye_care, "护眼提醒开关", "on / off"),
    "flow": _Preference(_apply_flow_mode, "心流模式开关", "on / off"),
    "scale": _Preference(_apply_pet_scale, "宠物大小",
                         "0.5 ~ 2.0 或 bigger/smaller"),
    "speed": _Preference(_apply_pet_speed, "宠物行走速度",
                         "slow / normal / fast"),
    "typing": _Preference(_apply_typing, "自动打字效果", "on / off"),
    "house": _Preference(_apply_house, "像素小房子开关", "on / off"),
    "mini": _Preference(_apply_mini_timer, "悬浮计时小窗开关", "on / off"),
    "goal": _Preference(_apply_daily_goal, "每日学习目标（分钟）", "10 ~ 1440"),
}

# 工具 schema 里用的短键名 -> 上面完整键名。
#
# 为什么两套名字：schema 每次请求都要随 API 发送，enum 里每个名字都会
# 被完整写一遍。用长键名（pomodoro_interval / daily_goal）时单这一个
# 工具的 schema 就有 597 字符，占掉全部 12 个工具的近 1/6。
# 短别名 + 描述里给一句对照表，语义不丢，体积明显下降。

# 页面标签（与 main_window._PAGE_ORDER 一致）与工具子页映射
_PAGE_LABELS = {
    "pet": "宠物",
    "ai": "AI",
    "tools": "工具",
    "settings": "宠物设置",
}
_TOOLS_SUB = {
    "todo": 0,
    "desktop": 1,
    "data": 2,
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
        description="添加待办。用户说「帮我记一下」「加个待办」「我要做…」时用。",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "minLength": 1, "maxLength": 200,
                         "description": "待办内容"},
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
        description="把待办标记为已完成。text 可给完整名称或能唯一匹配的关键词。",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "minLength": 1, "maxLength": 200,
                         "description": "待办名称或关键词"},
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
        description="查看待办列表。用户问「我还有什么要做」或你需要先了解情况时用。",
        parameters={
            "type": "object",
            "properties": {
                "include_done": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否一并列出已完成",
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
        # 把这次时长写进长期记忆的 study.focus_duration。
        # 原来只有「用户口头提到专注时长」才会记（memory_extract 的正则），
        # 而**实际跑的那一段反而没记** —— 于是记忆里的偏好与真实使用
        # 长期对不上，读出来的建议时长也就不可信。
        # 这里在真正开始计时后补记一次，两个来源就一致了。
        try:
            main_window.remember_focus_duration(int(minutes))
        except (AttributeError, RuntimeError):
            pass
        return "已开始 %d 分钟专注计时（桌面右上角会出现计时小窗）" % int(minutes)

    reg.register(ToolSpec(
        name="start_focus",
        description="开始专注倒计时。用户说「我要专注」「开始计时」时用。",
        parameters={
            "type": "object",
            "properties": {
                "minutes": {
                    "type": "integer",
                    "default": 25,
                    "minimum": 1,
                    "maximum": 600,
                    "description": "分钟数",
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

    # ── 屏幕时间明细 ────────────────────────────────────────
    def get_screen_time_detail(top: int = 5) -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        tracker = getattr(main_window, "_screen_tracker", None)
        if tracker is None:
            return "失败：屏幕统计组件不可用"
        try:
            today = tracker.get_today_data()
            if not today:
                return "今天还没有屏幕使用记录"
            ranked = sorted(today, key=lambda p: p[1], reverse=True)[:max(1, min(top, 10))]
            lines = ["今日屏幕时间前 %d 名：" % len(ranked)]
            for app, secs in ranked:
                lines.append("· %s：%d 分钟" % (app, int(secs) // 60))
            try:
                focus = tracker.get_focus_stats()
                if isinstance(focus, dict) and focus.get("sessions"):
                    lines.append("共 %d 段记录，最长一段 %d 分钟"
                                 % (focus.get("sessions", 0),
                                    int(focus.get("longest_secs", 0)) // 60))
            except Exception:  # noqa: BLE001 — 附加信息取不到不影响主结果
                pass
            return "\n".join(lines)
        except (RuntimeError, AttributeError, TypeError):
            return "失败：读取屏幕统计时出错"

    reg.register(ToolSpec(
        name="get_screen_time_detail",
        description="今天各应用的使用时长排名。用户问「哪个软件用得最多」时用。",
        parameters={
            "type": "object",
            "properties": {
                "top": {
                    "type": "integer", "default": 5, "minimum": 1, "maximum": 10,
                    "description": "返回前几名",
                },
            },
        },
        handler=get_screen_time_detail,
        returns="按使用时长排序的应用列表",
    ))

    # ── 日历标注 ────────────────────────────────────────────
    def add_calendar_note(date: str, text: str) -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        calendar = getattr(main_window, "_calendar", None)
        if calendar is None:
            return "失败：日历组件不可用"

        # 让模型可以只说"今天/明天"，由这里换算成真实日期
        from datetime import date as _date, timedelta as _timedelta
        key = (date or "").strip()
        aliases = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2}
        if key in aliases:
            key = (_date.today() + _timedelta(days=aliases[key])).isoformat()
        elif not key:
            key = _date.today().isoformat()
        else:
            import re as _re
            if not _re.match(r"^\d{4}-\d{2}-\d{2}$", key):
                return "失败：日期格式应为 YYYY-MM-DD，或使用 今天/明天/后天"

        try:
            events = getattr(calendar, "_events", None)
            if not isinstance(events, dict):
                return "失败：日历数据不可读"
            events.setdefault(key, []).append({"text": text, "color": "yellow"})
            calendar._save_events()
            try:
                calendar._update_calendar()
            except Exception:  # noqa: BLE001 — 刷新失败不影响已写入的数据
                pass
        except (RuntimeError, AttributeError, TypeError):
            return "失败：写入日历时出错"
        return "已在 %s 添加标注「%s」" % (key, text)

    reg.register(ToolSpec(
        name="add_calendar_note",
        description="给日历某天加标注（考试、截止日期）。用户说「记一下周三要交报告」时用。",
        parameters={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string", "default": "今天",
                    "description": "YYYY-MM-DD，或 今天/明天/后天",
                },
                "text": {"type": "string", "minLength": 1, "maxLength": 200,
                         "description": "标注内容"},
            },
            "required": ["text"],
        },
        handler=add_calendar_note,
        returns="写入结果与最终使用的日期",
    ))

    # ── 宠物行为 ────────────────────────────────────────────
    _PET_ACTIONS = ("dance", "celebrate", "tired", "sleep", "sparkle")

    def set_pet_behavior(action: str = "dance") -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        pet = getattr(main_window, "_pet", None)
        if pet is None:
            return "失败：宠物还没有启动"
        mapping = {
            "dance": ("trigger_dance", "跳舞"),
            "celebrate": ("trigger_celebrate", "庆祝"),
            "tired": ("trigger_tired", "累了"),
            "sleep": ("trigger_sleep", "睡觉"),
            "sparkle": ("trigger_sparkle_burst", "闪光"),
        }
        if action not in mapping:
            return "失败：action 只能是 %s" % "、".join(_PET_ACTIONS)
        method_name, label = mapping[action]
        method = getattr(pet, method_name, None)
        if method is None:
            return "失败：宠物不支持这个动作"
        try:
            method()
        except (RuntimeError, TypeError):
            return "失败：执行动作时出错"
        return "宠物正在%s" % label

    reg.register(ToolSpec(
        name="set_pet_behavior",
        description="让宠物做动作。用户说「跳个舞」「庆祝一下」时用。",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(_PET_ACTIONS),
                    "default": "dance",
                    "description": "动作类型",
                },
            },
        },
        handler=set_pet_behavior,
        returns="动作是否已触发",
    ))

    # ── 学习/工作报告 ───────────────────────────────────────
    def export_learning_report(period: str = "today",
                               save_file: bool = False) -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        builder = None
        ensure = getattr(main_window, "_ensure_report", None)
        if callable(ensure):
            builder = ensure()
        if builder is None:
            try:
                from pet_engine.report import LearningReport
                builder = LearningReport(main_window=main_window)
            except Exception as exc:  # noqa: BLE001
                return "失败：报告模块不可用（%s）" % exc
        try:
            if save_file:
                path = builder.export(period, fmt="md")
                # 顺便刷新界面预览，保证界面上看到的和 AI 说的是同一份
                refresh = getattr(main_window, "_refresh_report_preview", None)
                if callable(refresh):
                    try:
                        refresh(period)
                    except Exception:  # noqa: BLE001
                        pass
                return "报告已导出到 %s\n\n%s" % (
                    path, builder.render_text(period, max_chars=600))
            return builder.render_text(period, max_chars=900)
        except Exception as exc:  # noqa: BLE001
            return "失败：生成报告时出错（%s）" % str(exc)[:80]

    reg.register(ToolSpec(
        name="export_learning_report",
        description="生成学习/工作报告（今日/本周/本月）并可选导出文件。"
                    "用户说「帮我出一份报告」「这周学得怎么样」时用。",
        parameters={
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["today", "week", "month"],
                    "default": "today",
                    "description": "统计范围",
                },
                "save_file": {
                    "type": "boolean",
                    "default": False,
                    "description": "是否导出成 Markdown 文件",
                },
            },
        },
        handler=export_learning_report,
        returns="报告正文（或导出结果与路径）",
    ))

    # ── 偏好设置：让 AI 真的能改软件 ─────────────────────────
    #
    # 为什么需要：原来 10 个工具全是"查询 / 业务操作"，**没有任何一个能改
    # 设置**。用户说「打开深色模式」「番茄钟改成 45 分钟」时，模型只能嘴上
    # 答应，软件毫无变化 —— 这就是"AI 改了但没落实到软件里"的根源。
    #
    # 设计要点（与项目既有的工程纪律一致）：
    #   1. key 走**受控白名单**，模型不能自创键名（同 slots.py 的思路）
    #   2. 改完**立即生效**：调用对应的界面/逻辑刷新，而不只是写 QSettings
    #   3. 返回**改动后的真实值**：模型只能照实复述，不许编造成功
    #   4. 危险项不进白名单（自动启动、宠物坐标等一概不开放）
    def set_preference(key: str, value: str) -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        spec = _PREFERENCE_KEYS.get(key)
        if spec is None:
            # 用 ARG_ERROR_PREFIX 而不是"失败"：键名写错属于参数问题，
            # 不该计入熔断（否则模型试错两次就再也改不了设置）
            return "%s不支持的设置项「%s」。可用：%s" % (
                ARG_ERROR_PREFIX, key, "、".join(sorted(_PREFERENCE_KEYS)))
        try:
            return spec.apply(main_window, value)
        except ValueError as exc:
            # 值不合法（越界/类型错/枚举外）—— 同样属于参数问题，让模型重试
            return "%s设置「%s」的值不合法：%s" % (ARG_ERROR_PREFIX, key, exc)
        except Exception as exc:      # noqa: BLE001 — 其余异常算真失败
            return "失败：设置「%s」时出错（%s）" % (key, str(exc)[:80])

    reg.register(ToolSpec(
        name="set_preference",
        description=(
            "修改软件设置并立即生效（真改，不是聊天）。用户要求改动软件本身时用，"
            "如「打开深色模式」「番茄钟改 45 分钟」「宠物走慢点」。布尔值用 on/off。"
            "改完照实复述返回的实际值。"),
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "enum": sorted(_PREFERENCE_KEYS),
                },
                "value": {
                    "type": "string",
                    "maxLength": 24,
                },
            },
            "required": ["key", "value"],
        },
        handler=set_preference,
        returns="改动结果与生效后的实际值",
    ))

    # ── 切换页面：让 AI 把界面带到用户面前 ───────────────────
    def switch_page(page: str, tools_sub: str = "") -> str:
        if main_window is None:
            return "失败：主窗口不可用"
        label = _PAGE_LABELS.get(page)
        if label is None:
            return "%s没有「%s」这个页面。可用：%s" % (
                ARG_ERROR_PREFIX, page, "、".join(sorted(_PAGE_LABELS)))
        if tools_sub and tools_sub not in _TOOLS_SUB:
            # 原来这里静默忽略非法子页名然后照常切页，模型会以为"切到
            # desktop 了"其实停在别的子页。明确报错让它改。
            return "%s「%s」不是有效的工具子页。可用：%s" % (
                ARG_ERROR_PREFIX, tools_sub, "、".join(sorted(_TOOLS_SUB)))
        try:
            # 主窗口可能被收起（悬浮小窗模式），先恢复出来
            restore = getattr(main_window, "_restore_main_window", None)
            if callable(restore):
                try:
                    restore()
                except Exception:      # noqa: BLE001
                    pass
            sub = _TOOLS_SUB.get(tools_sub) if tools_sub else None
            goto = getattr(main_window, "_goto_page", None)
            if not callable(goto):
                return "失败：主窗口不支持切页"
            goto(label, tools_sub=sub)
        except RuntimeError:
            return "失败：主窗口已被销毁"
        if sub is not None and tools_sub:
            return "已切到「%s」页的「%s」" % (label, tools_sub)
        return "已切到「%s」页" % label

    reg.register(ToolSpec(
        name="switch_page",
        description=(
            "把主窗口切到指定页面并置前。用户说「打开数据面板」「进心流模式」时用。"),
        parameters={
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "enum": sorted(_PAGE_LABELS),
                },
                "tools_sub": {
                    "type": "string",
                    "enum": sorted(_TOOLS_SUB),
                },
            },
            "required": ["page"],
        },
        handler=switch_page,
        returns="是否成功切页",
    ))

    return reg
