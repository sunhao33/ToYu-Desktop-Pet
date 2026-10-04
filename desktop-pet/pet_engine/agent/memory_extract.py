"""记忆抽取 —— 从对话里挖出稳定偏好。

三级降级链（借鉴团队 M2 的范式的核心设计，实现全部重写）：

    本地规则（纯正则，零依赖，永不失败）
        ↑ 模型不可用/返回空/全部校验失败时落到这里
    模型抽取（用用户自己配的 AI，返回严格 JSON）

关键取舍：
  * **不走反**。规则是兜底、模型是主力 —— 但规则也必须能独立工作，
    否则用户没配 API 时记忆功能就完全废掉。
  * **降级不静默**。模型失败时写 ERROR 日志并进冷却（默认 300 秒），
    冷却结束自动重试；状态可通过 health() 查询。
  * **抽取失败不影响聊天**。任何异常都吞掉并记为 degraded，
    绝不能让"记不住偏好"变成"没法对话"。
  * **只抽稳定偏好**。提示词里明确要求"随口一提不要记"，
    并且契约层会用显性信号重算置信度来二次把关。
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime

from pet_engine.agent.memory_contract import parse_memory_list
from pet_engine.agent.slots import format_slot_table

# ── 抽取提示词 ──────────────────────────────────────────────
EXTRACT_SYSTEM_PROMPT = """你是一个偏好抽取器。从用户的话里找出**稳定的偏好或目标**，
输出严格的 JSON。除此之外不要输出任何文字。

槽位只能从下面这张表里选，**不得自创**。表外的槽位会被系统拒绝：
{slots}

判断标准：
- 只记**长期有效**的偏好（"以后""每次""我习惯""记住""别再"这类表达）
- 随口一提、一次性的安排**不要记**（"帮我加个待办"不是偏好）
- 拿不准就不要输出，宁可少记也不要记错

输出格式（JSON，不要 markdown 代码块）：
{{"memories": [
  {{"slot_id": "表的槽位名",
    "value": 值,
    "confidence": 0.0~1.0,
    "evidence": "为什么认为这是稳定偏好（引用用户原话）"}}
]}}

没有找到稳定偏好时输出：{{"memories": []}}"""


# ── 规则抽取（纯正则，零依赖）────────────────────────────────
_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "半": 0.5}

# 显性信号：必须有这个才做规则抽取，否则宁可漏也不要错。
# 含两类：① 明确要求长期遵守 ② 表达目标/打算（目标类槽位需要）
_SIGNAL = re.compile(
    r"以后|下次|今后|记住|默认|每次都|都按|我习惯|我通常|我一般|别再|不要再"
    r"|我(?:打|计)算|我计划|我准备|我的目标|打算每|计划每")
# 目标类槽位额外接受"每天/每日"这类周期性表达
_GOAL_SIGNAL = re.compile(r"每天|每日|天天|每周|每个月")


def _cn_to_int(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token in _CN_NUM and isinstance(_CN_NUM[token], int):
        return _CN_NUM[token]
    # 十一 ~ 九十九 的简单处理
    if len(token) == 2 and token[0] == "十" and token[1] in _CN_NUM:
        return 10 + _CN_NUM[token[1]]
    if len(token) == 2 and token[0] in _CN_NUM and token[1] == "十":
        return _CN_NUM[token[0]] * 10
    if len(token) == 3 and token[0] in _CN_NUM and token[1] == "十" and token[2] in _CN_NUM:
        return _CN_NUM[token[0]] * 10 + _CN_NUM[token[2]]
    return None


def _minutes_of(text: str) -> int | None:
    """从「45 分钟」「一个半小时」「2 小时」里取分钟数。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:分钟|min)", text)
    if m:
        return int(float(m.group(1)))
    m = re.search(r"([0-9一二两三四五六七八九十]+)\s*个?\s*半?\s*小时", text)
    if m:
        base = _cn_to_int(m.group(1))
        if base is not None:
            return int(base * 60 * (1.5 if "半" in m.group(0) else 1))
    m = re.search(r"([0-9一二两三四五六七八九十]+)\s*个?\s*半小时", text)
    if m:
        base = _cn_to_int(m.group(1)) or 1
        return int(base * 30)
    return None


def extract_with_rules(text: str, source_text: str = "") -> list[dict]:
    """纯正则抽取。只在有显性信号时才返回结果，保证精确率。"""
    text = (text or "").strip()
    if not text or not (_SIGNAL.search(text) or _GOAL_SIGNAL.search(text)):
        return []

    found: list[dict] = []

    def add(slot_id, value, evidence):
        found.append({"slot_id": slot_id, "value": value,
                      "confidence": 0.9, "evidence": evidence[:120]})

    # 单次专注时长
    if re.search(r"专注|番茄|一次学|一口气", text):
        minutes = _minutes_of(text)
        if minutes and 5 <= minutes <= 480:
            add("study.focus_duration", minutes,
                "用户提到专注时长：%s" % text[:60])

    # 目标类：按优先级取第一条命中的，避免同一句话既记"每日目标"
    # 又记"当前目标"（结构化更强的优先）
    goal_done = False
    if re.search(r"每天|天天|每日", text):
        minutes = _minutes_of(text)
        if minutes and 10 <= minutes <= 1440:
            add("study.daily_goal_minutes", minutes,
                "用户设定了每日目标：%s" % text[:60])
            goal_done = True
    if not goal_done:
        m = re.search(r"(?:截止|deadline|ddl|要交|交付)[^，。；\n]{0,8}"
                      r"(\d{1,2}\s*月\s*\d{1,2}\s*[日号]?|\d{4}-\d{2}-\d{2})", text)
        if m:
            add("goal.deadline", m.group(1).strip(),
                "用户提到了截止时间：%s" % text[:60])
            goal_done = True
    if not goal_done:
        m = re.search(r"我(?:在|正在)?(?:准备|打算|计划|想要)([^，。；\n]{2,30})", text)
        if m:
            add("goal.current", m.group(1).strip(),
                "用户提到了当前目标：%s" % text[:60])

    # 休息间隔
    if re.search(r"休息", text):
        minutes = _minutes_of(text)
        if minutes and 1 <= minutes <= 120:
            add("study.break_interval", minutes,
                "用户提到休息间隔：%s" % text[:60])

    # 学习时段
    m = re.search(r"(早上|早晨|上午|中午|午休后|下午|傍晚|晚上|夜里|深夜|凌晨)"
                  r"[^，。；\n]{0,12}(学习|看书|写代码|工作|专注)", text)
    if m:
        add("study.focus_time_of_day", m.group(1),
            "用户提到习惯时段：%s" % text[:60])

    # emoji 偏好
    if re.search(r"别(?:再)?(?:用|发|加)?\s*(?:emoji|表情)", text, re.I):
        add("assistant.use_emoji", False, "用户表示不要用表情符号")
    elif re.search(r"可以(?:用|加)\s*(?:emoji|表情)", text, re.I):
        add("assistant.use_emoji", True, "用户表示可以用表情符号")

    # 回答长度
    if re.search(r"简短|简洁|说重点|别啰嗦|一句话", text):
        add("assistant.answer_length", "简短", "用户希望回答简短")
    elif re.search(r"详细|展开说|讲清楚|多解释", text):
        add("assistant.answer_length", "详细", "用户希望回答详细")

    # 先给计划
    if re.search(r"先(?:跟|和)?我?说|先给(?:我)?(?:个)?计划|先讲思路", text):
        add("assistant.plan_first", True, "用户希望先看到计划")
    elif re.search(r"直接(?:做|开始)|别(?:问|确认)那么多", text):
        add("assistant.plan_first", False, "用户希望直接执行")

    # 报告格式
    m = re.search(r"(?:报告|周报|日报)[^。\n]{0,10}(?:按|用)\s*([^，。；\n]{2,30})", text)
    if m:
        add("report.format", m.group(1).strip(), "用户指定了报告格式")

    # 身份
    m = re.search(r"我(?:是|在读|在)([^，。；\n]{2,20}?(?:大学生|研究生|博士生|老师|工程师|高三|大[一二三四]))", text)
    if m:
        add("fact.identity", m.group(1).strip(), "用户说明了自己的身份")

    # 注：当前目标已在前面按优先级抽取过（结构化更强的槽位优先），
    # 这里不再重复，否则同一句话会同时记两条

    # 去重（同一槽位只保留第一条）
    seen = set()
    unique = []
    for item in found:
        if item["slot_id"] in seen:
            continue
        seen.add(item["slot_id"])
        unique.append(item)
    return unique[:5]


class MemoryExtractor:
    """模型抽取 + 规则兜底。"""

    RECOVER_SECONDS = 300       # 降级后多久重试模型

    def __init__(self, transport=None, store=None, on_log=None):
        """transport: callable(messages) -> str（模型返回的原始文本）。"""
        self._transport = transport
        self._store = store
        self._on_log = on_log
        self._degraded = False
        self._degraded_at = 0.0
        self._degrade_reason = ""
        self._stats = {"model": 0, "rules": 0, "empty": 0, "failed": 0}

    # ── 状态 ────────────────────────────────────────────────
    def health(self) -> dict:
        return {
            "degraded": self._degraded,
            "reason": self._degrade_reason,
            "since": (datetime.fromtimestamp(self._degraded_at).isoformat(timespec="seconds")
                      if self._degraded_at else ""),
            "stats": dict(self._stats),
        }

    def _log(self, level: str, message: str):
        if self._on_log is not None:
            try:
                self._on_log(level, message)
            except Exception:  # noqa: BLE001
                pass

    def _enter_degraded(self, reason: str):
        """进入降级：写 ERROR 告警 + 记录时间，冷却结束后自动重试。"""
        self._degraded = True
        self._degraded_at = time.time()
        self._degrade_reason = reason
        self._log("ERROR", "记忆抽取降级告警：%s（%d 秒后自动重试模型）"
                  % (reason, self.RECOVER_SECONDS))

    def _should_try_model(self) -> bool:
        if self._transport is None:
            return False
        if not self._degraded:
            return True
        return (time.time() - self._degraded_at) >= self.RECOVER_SECONDS

    # ── 主入口 ──────────────────────────────────────────────
    def extract(self, user_text: str, extra_text: str = "",
                session_id: str = "") -> dict:
        """从一轮对话里抽取偏好。返回统计信息，不抛异常。"""
        text = (user_text or "").strip()
        result = {"source": "none", "records": [], "rejected": [],
                  "added": 0, "updated": 0, "degraded": self._degraded}

        if len(text) < 4:
            self._stats["empty"] += 1
            return result

        raw_items: list[dict] = []

        # 1) 模型抽取
        if self._should_try_model():
            try:
                output = self._transport(self._build_messages(text))
                items = self._parse_model_output(output)
                if items is None:
                    raise ValueError("模型返回不是合法 JSON")
                raw_items = items
                self._stats["model"] += 1
                if self._degraded:
                    # 冷却结束且这次成功 → 自动恢复
                    self._degraded = False
                    self._degrade_reason = ""
                    self._log("INFO", "记忆抽取已从降级状态恢复")
            except Exception as exc:  # noqa: BLE001
                self._stats["failed"] += 1
                self._enter_degraded("%s: %s" % (type(exc).__name__, str(exc)[:80]))
                raw_items = []

        # 2) 模型没给出结果 → 规则兜底
        if not raw_items:
            raw_items = extract_with_rules(text)
            if raw_items:
                self._stats["rules"] += 1
                result["source"] = "rules"
            else:
                self._stats["empty"] += 1
                return result
        else:
            result["source"] = "model"

        records, errors = parse_memory_list(
            raw_items, source_text=text, session_id=session_id)
        result["records"] = records
        result["rejected"] = errors

        if errors:
            self._log("WARN", "记忆抽取被拒绝 %d 条：%s"
                      % (len(errors), "；".join(errors[:3])))

        # 3) 入库
        if records and self._store is not None:
            outcome = self._store.upsert_many(records)
            result["added"] = outcome.get("added", 0)
            result["updated"] = outcome.get("updated", 0)

        result["degraded"] = self._degraded
        return result

    # ── 提示词与解析 ────────────────────────────────────────
    def _build_messages(self, text: str) -> list[dict]:
        system = EXTRACT_SYSTEM_PROMPT.format(slots=format_slot_table())
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ]

    @staticmethod
    def _parse_model_output(output) -> list[dict] | None:
        """从模型输出里抠出 memories 数组。返回 None 表示格式不可用。"""
        if output is None:
            return None
        if isinstance(output, dict):
            data = output
        else:
            raw = str(output).strip()
            if not raw:
                return None
            # 容忍 markdown 代码块包裹
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I).strip()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # 再试一次：截取第一个 { 到最后一个 }
                start, end = raw.find("{"), raw.rfind("}")
                if start < 0 or end <= start:
                    return None
                try:
                    data = json.loads(raw[start:end + 1])
                except json.JSONDecodeError:
                    return None
        if not isinstance(data, dict):
            return None
        items = data.get("memories")
        if items is None:
            return None
        if not isinstance(items, list):
            return []
        return [i for i in items if isinstance(i, dict)]
