"""工具调用协议 —— ToYu 智能体的契约层。

设计原则（借鉴团队 M2 偏好引擎的工程范式）：
  * **一份定义，两处使用**：工具的 JSON Schema 既喂给模型，也用于本地校验，
    避免 prompt 里写的和代码里校验的不一致。
  * **强校验，不信任模型**：模型返回的参数必须过完整校验才允许执行；
    校验失败当作工具错误回灌给模型，让它自己纠正，而不是抛异常中断。
  * **显式上限**：轮数、单次超时、总超时全部写死在这里，不散落在各处。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

# ── 硬上限（防止模型把软件拖死）──────────────────────────────
MAX_ROUNDS = 5                 # 一条用户消息最多几轮工具调用
MAX_CALLS_PER_ROUND = 4        # 单轮最多执行几个工具
TOOL_TIMEOUT_SECONDS = 20      # 单个工具最长执行时间
TOTAL_TIMEOUT_SECONDS = 90     # 整条消息的总预算
MAX_CONSECUTIVE_FAILURES = 2   # 同一工具连续失败几次就熔断

TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

# 参数类型 → Python 类型
_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


@dataclass
class ToolSpec:
    """一个工具的完整定义。"""

    name: str
    description: str
    parameters: dict                       # JSON Schema（object 根）
    handler: Callable[..., Any]
    needs_confirm: bool = False            # 破坏性操作，首次调用需用户确认
    returns: str = ""                      # 返回值说明，写进 prompt 帮模型理解

    def schema(self) -> dict:
        """OpenAI 兼容的 function 定义。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    """模型请求的一次工具调用。"""

    call_id: str
    name: str
    arguments: dict = field(default_factory=dict)
    raw_arguments: str = ""
    error: str = ""                # 参数解析/校验失败原因（非空则不执行）


@dataclass
class ToolResult:
    call_id: str
    name: str
    ok: bool
    content: str
    error: str = ""
    user_hint: str = ""            # 给用户看的人话；空则用 content

    def display(self) -> str:
        """面向用户的说法，屏蔽"熔断/超时"这类内部术语。"""
        return self.user_hint or self.error or self.content

    def to_message(self) -> dict:
        """转成回灌给模型的 tool 消息。"""
        return {
            "role": "tool",
            "tool_call_id": self.call_id,
            "name": self.name,
            "content": self.content,
        }


@dataclass
class ModelReply:
    """模型一次返回的归一化结果。"""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tools(self) -> bool:
        return bool(self.tool_calls)


def parse_tool_calls(raw_calls: Any) -> list[ToolCall]:
    """把模型返回的原始 tool_calls 归一化成 ToolCall 列表。

    兼容两种常见形状：
      * OpenAI 风格：{"id":..., "function": {"name":..., "arguments": "<json str>"}}
      * 简化风格（假模型/部分本地模型）：{"name":..., "arguments": {...}}
    """
    out: list[ToolCall] = []
    if not isinstance(raw_calls, list):
        return out

    for idx, item in enumerate(raw_calls):
        if not isinstance(item, dict):
            continue
        call_id = str(item.get("id") or "call_%d" % idx)
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        name = str(fn.get("name") or "").strip()
        args_raw = fn.get("arguments", {})

        call = ToolCall(call_id=call_id, name=name)
        if not name:
            call.error = "工具名为空"
            out.append(call)
            continue
        if not TOOL_NAME_RE.match(name):
            call.error = "工具名不合法: %s" % name
            out.append(call)
            continue

        if isinstance(args_raw, str):
            call.raw_arguments = args_raw
            text = args_raw.strip()
            if not text:
                call.arguments = {}
            else:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as exc:
                    call.error = "参数不是合法 JSON: %s" % exc
                    out.append(call)
                    continue
                if not isinstance(parsed, dict):
                    call.error = "参数必须是 JSON 对象"
                    out.append(call)
                    continue
                call.arguments = parsed
        elif isinstance(args_raw, dict):
            call.raw_arguments = json.dumps(args_raw, ensure_ascii=False)
            call.arguments = args_raw
        else:
            call.error = "参数类型不支持: %s" % type(args_raw).__name__
        out.append(call)

    return out


def validate_arguments(spec: ToolSpec, arguments: dict) -> tuple[dict, str]:
    """按 ToolSpec 的 JSON Schema 校验并归一化参数。

    返回 (归一化参数, 错误信息)。错误信息非空时不要执行这个工具。

    只支持工具实际用得到的子集：type/properties/required/enum/default/
    minimum/maximum/minLength/maxLength/items。刻意不引第三方校验库 ——
    整个 ToYu 的依赖要保持在 125MB 包体以内。
    """
    schema = spec.parameters or {}
    props = schema.get("properties") or {}
    required = schema.get("required") or []

    if not isinstance(arguments, dict):
        return {}, "参数必须是对象"

    # 未知字段直接拒绝：宁可让模型重试，也不要静默忽略它以为生效了
    unknown = [k for k in arguments if k not in props]
    if unknown:
        return {}, "出现未定义的参数: %s（允许的参数: %s）" % (
            ", ".join(sorted(unknown)), ", ".join(sorted(props)) or "无")

    cleaned: dict[str, Any] = {}
    for key, rule in props.items():
        if key not in arguments or arguments[key] is None:
            if key in required:
                return {}, "缺少必填参数: %s" % key
            if "default" in rule:
                cleaned[key] = rule["default"]
            continue

        value = arguments[key]
        expected = rule.get("type")
        if expected:
            py_type = _TYPE_MAP.get(expected)
            if py_type is not None:
                # bool 是 int 的子类，必须单独挡掉（integer 收到 True 要判错）
                if expected in ("integer", "number") and isinstance(value, bool):
                    return {}, "参数 %s 应为 %s，收到布尔值" % (key, expected)
                if expected == "boolean" and not isinstance(value, bool):
                    return {}, "参数 %s 应为布尔值" % key
                if not isinstance(value, py_type):
                    return {}, "参数 %s 应为 %s，收到 %s" % (
                        key, expected, type(value).__name__)

        if "enum" in rule and value not in rule["enum"]:
            return {}, "参数 %s 只能是 %s 之一，收到 %r" % (
                key, rule["enum"], value)

        if isinstance(value, str):
            if "minLength" in rule and len(value) < rule["minLength"]:
                return {}, "参数 %s 太短（至少 %d 字符）" % (key, rule["minLength"])
            if "maxLength" in rule and len(value) > rule["maxLength"]:
                return {}, "参数 %s 太长（最多 %d 字符）" % (key, rule["maxLength"])
            value = value.strip()

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in rule and value < rule["minimum"]:
                return {}, "参数 %s 不能小于 %s" % (key, rule["minimum"])
            if "maximum" in rule and value > rule["maximum"]:
                return {}, "参数 %s 不能大于 %s" % (key, rule["maximum"])

        if isinstance(value, list) and "items" in rule:
            item_type = _TYPE_MAP.get((rule["items"] or {}).get("type", ""))
            if item_type is not None:
                for elem in value:
                    if not isinstance(elem, item_type):
                        return {}, "参数 %s 的元素类型应为 %s" % (
                            key, rule["items"].get("type"))

        cleaned[key] = value

    return cleaned, ""
