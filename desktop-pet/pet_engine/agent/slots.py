"""受控槽位表 —— 学习域的偏好"格子"。

这是整个长期记忆系统的地基。核心约束（借鉴团队 M2 偏好引擎的工程范式）：
  **模型只能从这张表里选槽位，不得自创。** 表外的槽位一律拒绝。

为什么必须这样：不限词汇表的话，模型会为同一件事编出十种槽位名
（study.focus / study.focus_time / focus.duration…），攒一段时间后
记忆库就变成一堆互不相干的碎片，既检索不到也没法统计。

三类槽位（与 M2 的 profile/preferences/facts 分层对应）：
  * preference —— 稳定偏好，长期有效
  * goal       —— 目标/承诺，带时间范围
  * fact       —— 事实，可能过期

格式约定：`对象.属性`，每段 ^[a-z_][a-z0-9_]*$，只允许一个点。
"""

from __future__ import annotations

import re

# 槽位名格式（与契约校验共用）
SLOT_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*$")

# kind 取值
KIND_PREFERENCE = "preference"
KIND_GOAL = "goal"
KIND_FACT = "fact"

KINDS = (KIND_PREFERENCE, KIND_GOAL, KIND_FACT)

# 值类型
TYPE_STRING = "string"
TYPE_NUMBER = "number"
TYPE_BOOLEAN = "boolean"
TYPE_LIST = "list"

# ── 受控槽位表 ──────────────────────────────────────────────
# 每项：{description, kind, value_type, hint}
#   hint 会拼进抽取提示词，帮模型判断"什么时候该填这个槽位"
KNOWN_SLOTS: dict[str, dict] = {
    # ── 学习节奏 ────────────────────────────────────────────
    "study.focus_duration": {
        "description": "习惯的单次专注时长",
        "kind": KIND_PREFERENCE, "value_type": TYPE_NUMBER,
        "hint": "用户说「我一专注就是 50 分钟」「25 分钟太短了」时的分钟数",
    },
    "study.focus_time_of_day": {
        "description": "习惯在什么时段学习",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「晚上」「早上 6 点后」「午饭后」；取用户原话里的时段描述",
    },
    "study.break_interval": {
        "description": "习惯的休息间隔",
        "kind": KIND_PREFERENCE, "value_type": TYPE_NUMBER,
        "hint": "每专注多少分钟休息一次，取分钟数",
    },
    "study.daily_goal_minutes": {
        "description": "每天的专注时长目标",
        "kind": KIND_GOAL, "value_type": TYPE_NUMBER,
        "hint": "「我打算每天学 4 小时」→ 240",
    },
    "study.task_granularity": {
        "description": "任务拆分的粗细偏好",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「拆细一点」「别拆太碎」「一个大任务就够」",
    },
    "study.reminder_style": {
        "description": "希望的提醒方式",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「提前 10 分钟提醒」「到点再叫我」「别老提醒我」",
    },
    "study.distraction_policy": {
        "description": "专注时对打扰的处理方式",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「专注时别弹通知」「有急事要告诉我」",
    },

    # ── 助手交互 ────────────────────────────────────────────
    "assistant.answer_length": {
        "description": "回答长度的偏好",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "只能是「简短」「适中」「详细」三者之一",
    },
    "assistant.tone": {
        "description": "语气偏好",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「正式一点」「随意点」「别太肉麻」",
    },
    "assistant.use_emoji": {
        "description": "回答里是否使用表情符号",
        "kind": KIND_PREFERENCE, "value_type": TYPE_BOOLEAN,
        "hint": "说「别用 emoji」→ false；说「可以加表情」→ true",
    },
    "assistant.plan_first": {
        "description": "是否希望先给计划再执行",
        "kind": KIND_PREFERENCE, "value_type": TYPE_BOOLEAN,
        "hint": "说「先跟我说怎么做」→ true；说「直接做别问」→ false",
    },
    "assistant.proactive_level": {
        "description": "主动打扰的程度",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「少说话」「多提醒我」「没事别找我」",
    },

    # ── 记录与报告 ──────────────────────────────────────────
    "report.format": {
        "description": "学习报告/周报的格式",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「按 今日完成/明日计划/问题 三段写」",
    },
    "report.include_stats": {
        "description": "报告里是否带上数据",
        "kind": KIND_PREFERENCE, "value_type": TYPE_BOOLEAN,
        "hint": "说「带上时长统计」→ true",
    },
    "report.period": {
        "description": "报告的周期",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "如「每天」「每周一」「每周末」",
    },
    "todo.default_priority": {
        "description": "新建待办的默认优先级",
        "kind": KIND_PREFERENCE, "value_type": TYPE_STRING,
        "hint": "只能是「low」「normal」「high」三者之一",
    },

    # ── 目标与事实 ──────────────────────────────────────────
    "goal.current": {
        "description": "当前正在推进的目标",
        "kind": KIND_GOAL, "value_type": TYPE_STRING,
        "hint": "如「准备华北五省竞赛」「考研复习」",
    },
    "goal.deadline": {
        "description": "某个目标的截止时间",
        "kind": KIND_GOAL, "value_type": TYPE_STRING,
        "hint": "如「10 月 8 号交材料」；保留原话里的时间描述",
    },
    "fact.course": {
        "description": "在学什么课程/科目",
        "kind": KIND_FACT, "value_type": TYPE_STRING,
        "hint": "如「在学机器学习」「这学期有数据结构」",
    },
    "fact.identity": {
        "description": "用户身份信息",
        "kind": KIND_FACT, "value_type": TYPE_STRING,
        "hint": "如「大学生」「大二」「在天津」",
    },
}

# 枚举型槽位的允许值（契约校验会检查）
ENUM_VALUES = {
    "assistant.answer_length": ["简短", "适中", "详细"],
    "todo.default_priority": ["low", "normal", "high"],
}

# 数值型槽位的合理范围
NUMBER_RANGES = {
    "study.focus_duration": (5, 480),
    "study.break_interval": (1, 120),
    "study.daily_goal_minutes": (10, 1440),
}


def slot_names() -> list[str]:
    return sorted(KNOWN_SLOTS)


def get_slot(slot_id: str) -> dict | None:
    return KNOWN_SLOTS.get(slot_id)


def slots_by_kind(kind: str) -> list[str]:
    return sorted(s for s, meta in KNOWN_SLOTS.items() if meta["kind"] == kind)


def format_slot_table() -> str:
    """生成给模型看的槽位清单（拼进抽取提示词）。"""
    lines = []
    for kind in KINDS:
        names = slots_by_kind(kind)
        if not names:
            continue
        label = {"preference": "稳定偏好", "goal": "目标", "fact": "事实"}[kind]
        lines.append("【%s】" % label)
        for name in names:
            meta = KNOWN_SLOTS[name]
            lines.append("  %s（%s）—— %s"
                         % (name, meta["value_type"], meta["hint"]))
    return "\n".join(lines)
