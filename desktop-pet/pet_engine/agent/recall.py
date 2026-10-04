"""记忆召回 —— 从记忆库里挑出与当前问题相关的几条。

**刻意不引入向量库**（chromadb / sentence-transformers 动辄 1~3 GB，
与 ToYu「端侧轻量化」的定位直接冲突）。改用可解释的轻量打分：

    score = 0.55 * 文本相关度     （问题与记忆的字符重合）
          + 0.25 * 时间新近度     （越新越优先）
          + 0.20 * 命中历史       （被用过、被确认过的更可信）
    再乘以置信度系数

字符重合对中文很实用：中文没有词边界，用 2-gram 重合度比按空格分词稳得多，
也完全不需要分词库。
"""

from __future__ import annotations

import re
from datetime import datetime

from pet_engine.agent.memory_contract import MemoryRecord

MAX_RECALL = 5                 # 最多注入几条
MIN_SCORE = 0.18               # 低于此分不注入，避免塞无关记忆
MIN_RELEVANCE = 0.08           # **相关度硬门槛**：低于此分直接淘汰
MAX_BLOCK_CHARS = 400          # 召回块长度上限

# 关键词提升：问句里出现这些词时，对应 kind 的记忆加分
KIND_HINTS = {
    "study": ["学习", "专注", "时间", "怎么学", "效率", "习惯"],
    "assistant": ["回答", "回复", "语气", "说话", "风格", "简short", "详细"],
    "report": ["报告", "周报", "日报", "总结", "汇报"],
    "todo": ["待办", "任务", "安排", "计划", "优先级"],
    "goal": ["目标", "计划", "打算", "想要", "准备"],
    "fact": ["我", "我的", "我是"],
}

_STOP = re.compile(r"[\s，。？！、；：\"'（）()\[\]{}…—\-·,.?!:;]+")


def _normalize(text: str) -> str:
    return _STOP.sub("", (text or "").lower())


def _bigrams(text: str) -> set[str]:
    """中文友好：2-gram 集合。长度不足 2 的退化为单字。"""
    norm = _normalize(text)
    if len(norm) < 2:
        return {norm} if norm else set()
    return {norm[i:i + 2] for i in range(len(norm) - 1)}


def relevance(query: str, record: MemoryRecord) -> float:
    """问题与一条记忆的文本相关度（0~1）。"""
    q = _bigrams(query)
    if not q:
        return 0.0
    # 记忆侧文本 = 槽位名 + 值 + 证据
    value = record.value
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    blob = "%s %s %s %s" % (record.slot_id.replace(".", " "), value,
                            record.evidence, record.source_text)
    m = _bigrams(blob)
    if not m:
        return 0.0
    inter = len(q & m)
    # 用查询侧覆盖率为主（问句短、记忆长，用并集会把分数压得很低）
    return inter / max(1, len(q))


def recency(record: MemoryRecord, now: datetime | None = None) -> float:
    """时间新近度（0~1）。"""
    now = now or datetime.now()
    try:
        updated = datetime.fromisoformat(record.updated_at)
    except (ValueError, TypeError):
        return 0.3
    days = max(0.0, (now - updated).total_seconds() / 86400.0)
    # 半衰期 30 天
    return 1.0 / (1.0 + days / 30.0)


def hit_factor(record: MemoryRecord) -> float:
    """命中历史系数（0~1）。"""
    return min(1.0, record.hits / 5.0)


def score(query: str, record: MemoryRecord, now: datetime | None = None) -> float:
    base = (0.55 * relevance(query, record)
            + 0.25 * recency(record, now)
            + 0.20 * hit_factor(record))
    return round(base * (0.5 + 0.5 * float(record.confidence or 0.0)), 4)


def recall(store, query: str, limit: int = MAX_RECALL) -> list[tuple[MemoryRecord, float]]:
    """返回 (记录, 分数) 列表，按分数降序。

    先用相关度硬门槛筛一遍：**时间新但完全无关的记忆不该被注入**。
    只靠总分不行 —— 新近度 0.25 + 命中 0.20 就足以把一条无关记忆
    顶过 MIN_SCORE，那等于每次对话都在往上下文里塞无关内容。
    """
    if store is None or not (query or "").strip():
        return []
    scored = []
    for record in store.all():
        rel = relevance(query, record)
        if rel < MIN_RELEVANCE:
            continue
        value = score(query, record)
        if value >= MIN_SCORE:
            scored.append((record, value))
    scored.sort(key=lambda item: (-item[1], item[0].slot_id))
    return scored[:limit]


def build_memory_block(store, query: str, limit: int = MAX_RECALL) -> str:
    """拼成可注入的文本块。没有相关记忆时返回空串。"""
    picked = recall(store, query, limit=limit)
    if not picked:
        return ""

    lines = ["[关于这位用户]"]
    used = len(lines[0])
    included = []
    for record, _value in picked:
        line = "- %s：%s" % (record.slot_id, _fmt_value(record.value))
        if used + len(line) + 1 > MAX_BLOCK_CHARS:
            break
        lines.append(line)
        used += len(line) + 1
        included.append(record)

    if not included:
        return ""
    # 命中计数：被真正用上才 +1
    for record in included:
        try:
            store.touch(record.slot_id)
        except Exception:  # noqa: BLE001
            pass
    return "\n".join(lines)


def _fmt_value(value) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        return "、".join(str(v) for v in value)
    return str(value)


def explain(store, query: str, limit: int = MAX_RECALL) -> list[dict]:
    """调试用：给出每条候选的分数明细，便于解释"为什么记住了这条"。"""
    out = []
    for record in (store.all() if store else []):
        out.append({
            "slot_id": record.slot_id,
            "value": _fmt_value(record.value),
            "relevance": round(relevance(query, record), 3),
            "recency": round(recency(record), 3),
            "hits": record.hits,
            "confidence": record.confidence,
            "score": score(query, record),
        })
    out.sort(key=lambda d: -d["score"])
    return out[:max(limit, 5)]
