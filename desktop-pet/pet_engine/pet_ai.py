"""AI companion adapter — unified OpenAI-compatible API client.

Supports DeepSeek, OpenAI, Zhipu, Moonshot, Qwen, and any
OpenAI-compatible endpoint. Users provide their own API key.
"""

import json
import os
import threading
from typing import Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal

DEFAULT_SYSTEM_PROMPT = (
    "你是{name}，一个可爱的桌面宠物伴侣。"
    "你的性格：{personality}。"
    "你住在用户的电脑桌面上，陪伴他们工作和学习。"
    "回复要简短可爱，像朋友聊天一样自然，不要用markdown格式。"
    "一般1-3句话就好，除非用户问了需要详细回答的问题。"
    "偶尔用emoji表情，但不要太多。"
)

PERSONALITIES = {
    "温柔": "温柔体贴，善解人意，说话轻声细语，像一个暖心的朋友",
    "活泼": "活泼开朗，充满活力，喜欢开玩笑和发表情，像一个开心果",
    "傲娇": "表面高冷，内心关心，嘴上说不在乎其实很在意，典型的傲娇性格",
    "知性": "聪明博学，喜欢分享知识，说话有条理，像一个温柔的学霸",
    "元气": "元气满满，积极向上，喜欢鼓励别人，像一个永远充满正能量的小伙伴",
}

class AIMessage:
    """Single chat message."""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self):
        return {"role": self.role, "content": self.content}

class AIConfig:
    """AI configuration stored locally."""
    DEFAULT_PATH = "ai_config.json"

    def __init__(self):
        self.enabled = False
        self.api_base = "https://api.deepseek.com/v1"
        self.api_key = ""
        self.model = "deepseek-chat"
        self.name = "ToYu"
        self.personality = "温柔"
        self.system_prompt = ""
        self.max_history = 20  # Max messages to keep in context
        self.temperature = 0.8

    def get_system_prompt(self) -> str:
        """Get the system prompt with variables filled in."""
        if self.system_prompt:
            return self.system_prompt.format(
                name=self.name,
                personality=PERSONALITIES.get(self.personality, self.personality),
            )
        return DEFAULT_SYSTEM_PROMPT.format(
            name=self.name,
            personality=PERSONALITIES.get(self.personality, self.personality),
        )

    def save(self, path: str = None):
        path = path or self.DEFAULT_PATH
        data = {
            "enabled": self.enabled,
            "api_base": self.api_base,
            "api_key": self.api_key,
            "model": self.model,
            "name": self.name,
            "personality": self.personality,
            "system_prompt": self.system_prompt,
            "max_history": self.max_history,
            "temperature": self.temperature,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str = None) -> bool:
        path = path or self.DEFAULT_PATH
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.enabled = data.get("enabled", False)
            self.api_base = data.get("api_base", self.api_base)
            self.api_key = data.get("api_key", "")
            self.model = data.get("model", self.model)
            self.name = data.get("name", self.name)
            self.personality = data.get("personality", self.personality)
            self.system_prompt = data.get("system_prompt", "")
            self.max_history = data.get("max_history", self.max_history)
            self.temperature = data.get("temperature", self.temperature)
            return True
        except Exception:
            return False

class AIWorker(QObject):
    """Background worker for non-blocking API calls."""
    finished = pyqtSignal(str)   # AI response text
    error = pyqtSignal(str)      # Error message

    def __init__(self, config: AIConfig, messages: list):
        super().__init__()
        self._config = config
        self._messages = messages

    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        try:
            import urllib.request
            import urllib.error

            url = self._config.api_base.rstrip("/") + "/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.api_key}",
            }
            body = {
                "model": self._config.model,
                "messages": self._messages,
                "temperature": self._config.temperature,
                "max_tokens": 200,
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            content = data["choices"][0]["message"]["content"].strip()
            self.finished.emit(content)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            self.error.emit(f"API 错误 {e.code}: {body[:100]}")
        except urllib.error.URLError as e:
            self.error.emit(f"网络错误: {e.reason}")
        except KeyError:
            self.error.emit("API 返回格式异常")
        except Exception as e:
            self.error.emit(f"未知错误: {str(e)[:80]}")

class AIAgentWorker(QObject):
    """在子线程里跑 Agent 主循环（多轮工具调用）。

    必须在子线程：工具执行要回主线程，如果主循环自己占着主线程就会死锁。
    结果通过信号回到主线程。
    """

    finished = pyqtSignal(str)
    trace = pyqtSignal(str)

    def __init__(self, loop, messages: list, runtime):
        super().__init__()
        self._loop = loop
        self._messages = messages
        self._runtime = runtime

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            text = self._loop.run(self._messages)
            self.finished.emit(text or "（我没想出该说什么）")
        except Exception as exc:  # noqa: BLE001 — 子线程异常绝不能冒泡
            self.finished.emit("[出错了: %s]" % str(exc)[:120])


class AICompanion:
    """Manages AI chat state and API calls."""

    HISTORY_PATH = "ai_chat_history.json"

    def __init__(self, config: AIConfig = None, tool_registry=None,
                 tool_runtime=None):
        self.config = config or AIConfig()
        self._history: list[AIMessage] = []
        self._worker: Optional[AIWorker] = None
        self._agent_worker: Optional[AIAgentWorker] = None
        self._pending_callbacks: list[tuple[Callable, Callable]] = []
        # 工具能力是可选的：没有注册表就退回原来的单轮问答，行为不变
        self._tool_registry = tool_registry
        self._tool_runtime = tool_runtime
        self._on_trace: Optional[Callable[[str], None]] = None
        # 上下文提供者：返回"桌面状态块"文本。为 None 时退回旧行为
        self._context_provider: Optional[Callable[[], str]] = None
        self._context = ""          # 兼容旧的 inject_context（一次性附注）
        self._load_history()

    # ── 上下文注入 ──────────────────────────────────────────
    def set_context_provider(self, provider):
        """注入上下文提供者。每次对话实时取一次，避免状态过期。"""
        self._context_provider = provider

    def build_state_block(self) -> str:
        """取一次最新的桌面状态块。取不到就返回空串，绝不影响聊天。"""
        if self._context_provider is None:
            return ""
        try:
            return (self._context_provider() or "").strip()
        except Exception as exc:  # noqa: BLE001
            print("[Context] 状态块构建失败: %s" % exc)
            return ""

    def compose_system_prompt(self) -> str:
        """人格提示 + 桌面状态 + 一次性附注。"""
        parts = [self.get_system_prompt_with_context()]
        block = self.build_state_block()
        if block:
            parts.append(block)
        return "\n\n".join(p for p in parts if p)

    # ── 工具能力 ────────────────────────────────────────────
    def set_tools(self, registry, runtime):
        """注入工具注册表与运行时（由主窗口在初始化时调用）。"""
        self._tool_registry = registry
        self._tool_runtime = runtime

    def set_trace_callback(self, callback):
        """设置执行轨迹回调（界面用来显示"正在做什么"）。"""
        self._on_trace = callback

    @property
    def tools_enabled(self) -> bool:
        return (self._tool_registry is not None
                and self._tool_runtime is not None
                and len(self._tool_registry) > 0)

    def is_available(self) -> bool:
        return self.config.enabled and bool(self.config.api_key)

    def chat(self, user_input: str, on_response: Callable[[str], None],
             on_error: Callable[[str], None] = None):
        """Send a message and get async response."""
        if not self.is_available():
            if on_error:
                on_error("AI 未启用，请先在设置中配置 API")
            return

        self._history.append(AIMessage("user", user_input))

        if len(self._history) > self.config.max_history:
            self._history = self._history[-self.config.max_history:]

        system_prompt = self.compose_system_prompt()

        # 有工具时走 Agent 主循环：模型可以多轮调用工具再回答
        if self.tools_enabled:
            self._chat_with_tools(system_prompt, on_response, on_error)
            return

        messages = [{"role": "system", "content": system_prompt}]
        for msg in self._history:
            messages.append(msg.to_dict())

        self._worker = AIWorker(self.config, messages)
        self._worker.finished.connect(lambda text: self._on_response(text, on_response))
        self._worker.error.connect(lambda err: self._on_error(err, on_error))
        self._worker.start()

    def _chat_with_tools(self, system_prompt, on_response, on_error):
        """带工具的一轮对话。"""
        try:
            from pet_engine.agent import AgentLoop
            from pet_engine.agent.transport import openai_tool_transport
        except Exception as exc:  # noqa: BLE001
            if on_error:
                on_error("工具模块加载失败: %s" % exc)
            return

        loop = AgentLoop(
            self._tool_registry, self._tool_runtime,
            openai_tool_transport(self.config),
            on_trace=self._on_trace)

        # 系统提示 = 人格提示 + 工具使用准则
        messages = [{"role": "system",
                     "content": system_prompt + "\n\n" + loop.build_tool_prompt()}]
        for msg in self._history:
            messages.append(msg.to_dict())

        self._agent_worker = AIAgentWorker(loop, messages, self._tool_runtime)
        self._agent_worker.finished.connect(
            lambda text: self._on_response(text, on_response))
        self._agent_worker.start()

    def _on_response(self, text: str, callback: Callable):
        self._history.append(AIMessage("assistant", text))
        self._save_history()
        callback(text)

    def _on_error(self, err: str, callback: Callable):
        if callback:
            callback(f"[{err}]")

    def clear_history(self):
        self._history.clear()
        self._save_history()

    def _save_history(self):
        """Save chat history to local JSON."""
        try:
            data = [m.to_dict() for m in self._history[-200:]]  # Keep last 200
            with open(self.HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_history(self):
        """Load chat history from local JSON."""
        try:
            if os.path.exists(self.HISTORY_PATH):
                with open(self.HISTORY_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._history = [AIMessage(d["role"], d["content"]) for d in data[-200:]]
        except Exception:
            self._history = []

    def get_history(self) -> list[AIMessage]:
        """Get chat history for display."""
        return self._history

    def inject_context(self, affection_level: int = 0, time_period: str = "",
                       mood: str = "", extra: str = ""):
        """Inject real-time context into the system prompt."""
        ctx_parts = []
        if affection_level >= 0:
            ctx_parts.append(f"当前好感度: {affection_level}/100")
        if time_period:
            ctx_parts.append(f"当前时段: {time_period}")
        if mood:
            ctx_parts.append(f"当前心情: {mood}")
        if extra:
            ctx_parts.append(extra)
        self._context = "\n".join(ctx_parts) if ctx_parts else ""

    def get_system_prompt_with_context(self) -> str:
        """Get system prompt with injected context."""
        base = self.config.get_system_prompt()
        if hasattr(self, '_context') and self._context:
            base += "\n\n[当前状态]\n" + self._context
        return base

    def get_summary(self) -> str:
        """Get a short summary of recent conversation for companion system."""
        if not self._history:
            return ""
        recent = self._history[-6:]
        return "\n".join(f"{m.role}: {m.content[:50]}" for m in recent)
