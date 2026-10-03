"""ToYu 智能体能力包。

模块划分：
    protocol.py   契约层：工具定义、参数强校验、硬上限常量
    tools.py      工具实现：首批 6 个，全部走界面已有入口
    runtime.py    执行桥：子线程提交 → 主线程执行的线程安全通道
    loop.py       Agent 主循环：多轮工具调用 + 三重刹车
    transport.py  模型传输：OpenAI 兼容 function calling
"""

from pet_engine.agent.loop import AgentLoop
from pet_engine.agent.protocol import (
    MAX_ROUNDS,
    TOTAL_TIMEOUT_SECONDS,
    ModelReply,
    ToolCall,
    ToolResult,
    ToolSpec,
    parse_tool_calls,
    validate_arguments,
)
from pet_engine.agent.runtime import ToolRequest, ToolRuntime
from pet_engine.agent.tools import ToolRegistry, build_default_registry

__all__ = [
    "AgentLoop",
    "ModelReply",
    "ToolCall",
    "ToolRequest",
    "ToolRegistry",
    "ToolResult",
    "ToolRuntime",
    "ToolSpec",
    "MAX_ROUNDS",
    "TOTAL_TIMEOUT_SECONDS",
    "build_default_registry",
    "parse_tool_calls",
    "validate_arguments",
]
