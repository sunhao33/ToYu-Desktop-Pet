"""记忆记录契约 —— 强校验，不信任模型。

三层防护（借鉴团队 M2 的做法，实现全部重写）：
  1. **结构校验**：字段、类型、取值范围
  2. **槽位校验**：槽位必须在受控表内，且 kind/value_type 与表一致
  3. **置信度重算**：不信模型自报的 confidence，从证据文本里的
     "显性信号"重新估算 —— 小模型的置信度基本是瞎猜的

校验失败一律返回 (None, 原因)，调用方把原因回灌给模型让它重试，
而不是抛异常或者把脏数据写进记忆库。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from pet_engine.agent.slots import (
    ENUM_VALUES,
    KINDS,
    KIND_FACT,
    KIND_GOAL,
    KIND_PREFERENCE,
    NUMBER_RANGES,
    SLOT_RE,
    TYPE_BOOLEAN,
    TYPE_LIST,
    TYPE_NUMBER,
    TYPE_STRING,
    get_slot,
)

# ── 置信度：显性信号 → 地板值 ───────────────────────────────
# 用户明确表达"以后都这样"时，即使模型报的置信度很低，也应该采信；
# 反之只是随口一提，模型报 0.95 也不能全信。
EXPLICIT_SIGNAL_PATTERNS = (
    r"以后", r"下次", r"今后", r"从此", r"记住", r"默认",
    r"每次都", r"都按", r"都要", r"一律", r"统一",
    r"我习惯", r"我通常", r"我一般", r"我的习惯",
    r"别再", r"不要再用", r"不要再", r"别给我",
    r"一定要", r"务必", r"必须",
    r"从现在起", r"以后都",
)
EXPLICIT_SIGNAL_RE = re.compile("|".join(EXPLICIT_SIGNAL_PATTERNS))

# 弱信号：表达偏好但语气不确定
WEAK_SIGNAL_RE = re.compile(r"我?比较?喜欢|我更?想?要|最好|建议|倾向于|偏好")

# 显性信号时的置信度地板（用户说得这么明确，不该因为模型保守而丢掉）
EXPLICIT_FLOOR = 0.90
WEAK_FLOOR = 0.70

# 证据文本长度上限
MAX_EVIDENCE_LEN = 200
MAX_VALUE_LEN = 300

# 事实类槽位的默认有效期（天）；preference 不过期
FACT_TTL_DAYS = 30
GOAL_TTL_DAYS = 90

@dataclass
class MemoryRecord:
    """一条记忆。字段设计对齐 M2 的 Preference 记录（保留可追溯性）。"""

    memory_id: str
    created_at: str
    updated_at: str

    slot_id: str
    kind: str
    value: object
    value_type: str

    confidence: float
    evidence: str
    source_text: str = ""
    session_id: str = ""

    # 有效期：None 表示长期有效
    expires_at: str = ""
    # 这条记忆被命中/更新过几次（用于召回排序与"精准遗忘"）
    hits: int = 0
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "slot_id": self.slot_id,
            "kind": self.kind,
            "value": self.value,
            "value_type": self.value_type,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "source_text": self.source_text,
            "session_id": self.session_id,
            "expires_at": self.expires_at,
            "hits": self.hits,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryRecord":
        return cls(
            memory_id=str(data.get("memory_id", "")),
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            slot_id=str(data.get("slot_id", "")),
            kind=str(data.get("kind", "")),
            value=data.get("value"),
            value_type=str(data.get("value_type", "")),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            evidence=str(data.get("evidence", ""))[:MAX_EVIDENCE_LEN],
            source_text=str(data.get("source_text", ""))[:MAX_VALUE_LEN],
            session_id=str(data.get("session_id", "")),
            expires_at=str(data.get("expires_at", "")),
            hits=int(data.get("hits", 0) or 0),
            active=bool(data.get("active", True)),
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        now = now or datetime.now()
        try:
            return datetime.fromisoformat(self.expires_at) <= now
        except ValueError:
            return False

    def describe(self) -> str:
        """给人看的一行描述（记忆管理界面用）。"""
        value = self.value
        if isinstance(value, bool):
            value = "是" if value else "否"
        elif isinstance(value, list):
            value = "、".join(str(v) for v in value)
        return "%s = %s" % (self.slot_id, value)

def has_explicit_signal(text: str) -> bool:
    return bool(EXPLICIT_SIGNAL_RE.search(text or ""))

def reestimate_confidence(model_confidence: float, evidence: str,
                          source_text: str = "") -> float:
    """从证据文本重算置信度。

    规则：
      * 有显性信号（"以后都…"/"记住"/"我习惯"）→ 至少 0.90
      * 只有弱信号（"我喜欢"/"最好"）→ 至少 0.70
      * 两者都没有 → 取模型自报值与 0.6 的较小者（保守处理）
    这样模型既不能把随口一句吹成高置信，也不会把明确要求压得过低。
    """
    try:
        base = float(model_confidence)
    except (TypeError, ValueError):
        base = 0.0
    base = max(0.0, min(1.0, base))
    blob = "%s %s" % (evidence or "", source_text or "")

    if has_explicit_signal(blob):
        return round(max(base, EXPLICIT_FLOOR), 3)
    if WEAK_SIGNAL_RE.search(blob):
        return round(max(base, WEAK_FLOOR), 3)
    return round(min(base, 0.60), 3)

def _ttl_for(kind: str) -> str:
    """按 kind 决定过期时间；preference 不过期。"""
    now = datetime.now()
    if kind == KIND_FACT:
        return (now + timedelta(days=FACT_TTL_DAYS)).isoformat(timespec="seconds")
    if kind == KIND_GOAL:
        return (now + timedelta(days=GOAL_TTL_DAYS)).isoformat(timespec="seconds")
    return ""

def validate_value(slot_id: str, value, value_type: str) -> tuple[object, str]:
    """按槽位定义校验并归一化取值。返回 (归一化值, 错误)。"""
    # 类型一致性。注意 bool 是 int 的子类，必须先判 bool
    if value_type == TYPE_BOOLEAN:
        if not isinstance(value, bool):
            return None, "值类型应为布尔值，收到 %s" % type(value).__name__
    elif value_type == TYPE_NUMBER:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None, "值类型应为数字，收到 %s" % type(value).__name__
        value = int(value) if float(value).is_integer() else float(value)
        lo, hi = NUMBER_RANGES.get(slot_id, (None, None))
        if lo is not None and value < lo:
            return None, "值 %s 小于合理下限 %s" % (value, lo)
        if hi is not None and value > hi:
            return None, "值 %s 大于合理上限 %s" % (value, hi)
    elif value_type == TYPE_LIST:
        if not isinstance(value, list):
            return None, "值类型应为数组，收到 %s" % type(value).__name__
        if not value:
            return None, "数组不能为空"
        if len(value) > 20:
            return None, "数组元素过多（最多 20）"
        value = [str(v).strip() for v in value if str(v).strip()]
    elif value_type == TYPE_STRING:
        if not isinstance(value, str):
            return None, "值类型应为字符串，收到 %s" % type(value).__name__
        value = value.strip()
        if not value:
            return None, "字符串不能为空"
        if len(value) > MAX_VALUE_LEN:
            return None, "字符串过长（最多 %d 字）" % MAX_VALUE_LEN

    # 枚举检查
    allowed = ENUM_VALUES.get(slot_id)
    if allowed and value not in allowed:
        return None, "值只能是 %s 之一，收到 %r" % (allowed, value)

    return value, ""

# 允许模型返回的字段（多一个都拒绝，避免它夹带私货）
ALLOWED_FIELDS = {"slot_id", "value", "evidence", "confidence"}

def parse_memory(raw: dict, source_text: str = "", session_id: str = "",
                 memory_id: str = "") -> tuple[MemoryRecord | None, str]:
    """把模型返回的一条原始记录校验成 MemoryRecord。

    返回 (记录, 错误)。错误非空时记录为 None。
    """
    if not isinstance(raw, dict):
        return None, "每条记忆必须是 JSON 对象"

    unknown = set(raw) - ALLOWED_FIELDS
    if unknown:
        return None, "出现未定义的字段: %s（只允许 %s）" % (
            ", ".join(sorted(unknown)), ", ".join(sorted(ALLOWED_FIELDS)))

    slot_id = str(raw.get("slot_id", "")).strip()
    if not slot_id:
        return None, "缺少 slot_id"
    if not SLOT_RE.match(slot_id):
        return None, "slot_id 格式错误（应为 对象.属性 的小写形式）: %s" % slot_id

    meta = get_slot(slot_id)
    if meta is None:
        return None, "槽位 %s 不在受控表内，不得自创" % slot_id

    kind = meta["kind"]
    value_type = meta["value_type"]
    if kind not in KINDS:
        return None, "槽位定义异常: %s" % slot_id

    if "value" not in raw:
        return None, "缺少 value"
    value, err = validate_value(slot_id, raw.get("value"), value_type)
    if err:
        return None, "%s（槽位 %s）" % (err, slot_id)

    evidence = str(raw.get("evidence", "")).strip()
    if not evidence:
        return None, "缺少 evidence（必须说明为什么认为这是用户的稳定偏好）"
    evidence = evidence[:MAX_EVIDENCE_LEN]

    confidence = reestimate_confidence(raw.get("confidence", 0.0),
                                       evidence, source_text)

    now = datetime.now().isoformat(timespec="seconds")
    record = MemoryRecord(
        memory_id=memory_id or "mem_%s" % datetime.now().strftime("%Y%m%d%H%M%S%f")[:20],
        created_at=now,
        updated_at=now,
        slot_id=slot_id,
        kind=kind,
        value=value,
        value_type=value_type,
        confidence=confidence,
        evidence=evidence,
        source_text=(source_text or "")[:MAX_VALUE_LEN],
        session_id=session_id,
        expires_at=_ttl_for(kind),
    )
    return record, ""

def parse_memory_list(items, source_text: str = "", session_id: str = "",
                      max_items: int = 5) -> tuple[list[MemoryRecord], list[str]]:
    """批量校验。返回 (通过的记录, 被拒绝的原因列表)。

    刻意不做"部分失败就整体失败"：一条格式错不该丢掉其他正确的提取结果，
    但错误原因要回传给调用方（可用于日志与提示词自纠）。
    """
    records: list[MemoryRecord] = []
    errors: list[str] = []
    if not isinstance(items, list):
        return [], ["返回的 memories 不是数组"]
    for item in items[:max_items]:
        record, err = parse_memory(item, source_text=source_text,
                                   session_id=session_id)
        if err:
            errors.append(err)
        elif record is not None:
            records.append(record)
    return records, errors
