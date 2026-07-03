"""AI companion adapter — unified OpenAI-compatible API client.

Supports DeepSeek, OpenAI, Zhipu, Moonshot, Qwen, and any
OpenAI-compatible endpoint. Users provide their own API key.
"""

import json
import os
import threading
from typing import Optional, Callable

from PyQt6.QtCore import QObject, pyqtSignal


# ── Default system prompt ──
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


class AICompanion:
    """Manages AI chat state and API calls."""

    HISTORY_PATH = "ai_chat_history.json"

    def __init__(self, config: AIConfig = None):
        self.config = config or AIConfig()
        self._history: list[AIMessage] = []
        self._worker: Optional[AIWorker] = None
        self._pending_callbacks: list[tuple[Callable, Callable]] = []
        self._load_history()

    def is_available(self) -> bool:
        return self.config.enabled and bool(self.config.api_key)

    def chat(self, user_input: str, on_response: Callable[[str], None],
             on_error: Callable[[str], None] = None):
        """Send a message and get async response."""
        if not self.is_available():
            if on_error:
                on_error("AI 未启用，请先在设置中配置 API")
            return

        # Add user message to history
        self._history.append(AIMessage("user", user_input))

        # Trim history
        if len(self._history) > self.config.max_history:
            self._history = self._history[-self.config.max_history:]

        # Build messages for API
        messages = [{"role": "system", "content": self.get_system_prompt_with_context()}]
        for msg in self._history:
            messages.append(msg.to_dict())

        # Start async call
        self._worker = AIWorker(self.config, messages)
        self._worker.finished.connect(lambda text: self._on_response(text, on_response))
        self._worker.error.connect(lambda err: self._on_error(err, on_error))
        self._worker.start()

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
