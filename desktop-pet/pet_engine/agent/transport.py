"""模型传输层 —— 负责和 OpenAI 兼容接口通信，并归一化返回。

刻意与 AgentLoop 解耦：loop 只依赖一个 callable(messages, schemas) -> ModelReply，
所以测试时可以塞一个假模型进去，不用联网也不用 API key。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from pet_engine.agent.protocol import ModelReply, parse_tool_calls

# 带工具的请求需要更长输出：以前写死 200，模型话还没说完就被截断了
DEFAULT_MAX_TOKENS = 900
DEFAULT_TIMEOUT = 45


class TransportError(RuntimeError):
    """网络/协议错误，由 caller 决定怎么呈现。"""


def openai_tool_transport(config, max_tokens: int = DEFAULT_MAX_TOKENS,
                          timeout: int = DEFAULT_TIMEOUT):
    """返回一个可直接喂给 AgentLoop 的 transport。"""

    def call(messages: list[dict], schemas: list[dict]) -> ModelReply:
        url = config.api_base.rstrip("/") + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % config.api_key,
        }
        body = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": max_tokens,
        }
        if schemas:
            body["tools"] = schemas
            body["tool_choice"] = "auto"

        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TransportError("API 错误 %s: %s" % (exc.code, detail[:160])) from exc
        except urllib.error.URLError as exc:
            raise TransportError("网络错误: %s" % exc.reason) from exc
        except json.JSONDecodeError as exc:
            raise TransportError("返回不是合法 JSON: %s" % exc) from exc

        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TransportError("返回格式异常: %s" % str(data)[:160]) from exc

        return ModelReply(
            content=(message.get("content") or "").strip(),
            tool_calls=parse_tool_calls(message.get("tool_calls")),
        )

    return call
