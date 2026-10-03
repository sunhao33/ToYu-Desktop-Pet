"""工具执行桥 —— 解决"HTTP 在子线程、工具必须在主线程"的矛盾。

问题：AIWorker 在 Python 子线程里跑 HTTP；但工具要操作 Qt 界面
      （加待办、开计时），**绝不能在子线程碰 Qt 对象**，否则崩溃。

解法：子线程把工具调用放进队列 → 主线程用 QTimer 轮询 → 主线程执行
      → 结果回填并唤醒子线程。子线程只做等待，不碰任何 Qt 对象。

这个设计的好处是完全不需要改现有线程模型，只加一个队列和一个轮询定时器。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from PyQt6.QtCore import QObject, QTimer

from pet_engine.agent.protocol import ToolResult, ToolSpec


@dataclass
class ToolRequest:
    """一次待执行的工具调用。"""

    call_id: str
    name: str
    arguments: dict
    spec: ToolSpec | None = None
    arg_error: str = ""


@dataclass
class _Pending:
    request: ToolRequest
    done: threading.Event = field(default_factory=threading.Event)
    result: ToolResult | None = None


class ToolRuntime(QObject):
    """工具运行时。

    必须由**主线程**创建。子线程调用 submit_and_wait() 提交并等待，
    主线程的 QTimer 负责取出并执行。
    """

    POLL_INTERVAL_MS = 40          # 主线程轮询间隔：够快，又不至于吃 CPU

    def __init__(self, registry, parent=None, on_trace: Callable[[str], None] = None):
        super().__init__(parent)
        self._registry = registry
        self._on_trace = on_trace
        self._lock = threading.Lock()
        self._queue: list[_Pending] = []
        self._fail_streak: dict[str, int] = {}      # 工具名 → 连续失败次数
        self._timed_out: set[str] = set()           # 本轮已熔断的工具
        self._history: list[dict] = []              # 执行轨迹（可回放）

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(self.POLL_INTERVAL_MS)

    # ── 子线程侧 ────────────────────────────────────────────
    def submit_and_wait(self, requests: list[ToolRequest],
                        timeout: float = 25.0) -> list[ToolResult]:
        """提交一批工具调用并等待主线程执行完毕（在子线程里调用）。"""
        if not requests:
            return []

        pending_items = []
        with self._lock:
            for req in requests:
                item = _Pending(request=req)
                self._queue.append(item)
                pending_items.append(item)

        results: list[ToolResult] = []
        for item in pending_items:
            # 单个工具超时：不整体失败，把它当作该工具的错误回灌给模型
            if item.done.wait(timeout):
                results.append(item.result or ToolResult(
                    call_id=item.request.call_id, name=item.request.name,
                    ok=False, content="工具执行没有返回结果", error="empty result"))
            else:
                results.append(ToolResult(
                    call_id=item.request.call_id, name=item.request.name,
                    ok=False, error="工具执行超时",
                    content="工具「%s」执行超时（超过 %d 秒），已跳过"
                            % (item.request.name, int(timeout)),
                    user_hint="这个操作响应太慢，我先跳过了"))
        return results

    def reset_round_state(self):
        """一条新的用户消息开始时重置熔断状态。

        熔断是"这一轮别再无脑重试"的保护，不是永久拉黑 ——
        所以每次新消息都清零，否则某个工具一旦失败两次就再也不能用了。
        """
        with self._lock:
            self._timed_out.clear()
            self._fail_streak.clear()

    # ── 主线程侧 ────────────────────────────────────────────
    def _drain(self):
        with self._lock:
            items = self._queue
            self._queue = []
        for item in items:
            try:
                result = self._execute(item.request)
            except Exception as exc:  # noqa: BLE001 — 工具异常绝不能冒泡到 Qt 事件循环
                result = ToolResult(
                    call_id=item.request.call_id, name=item.request.name,
                    ok=False, error="%s: %s" % (type(exc).__name__, exc),
                    content="工具「%s」执行时出错：%s" % (item.request.name, exc))
            item.result = result
            self._record(result)
            item.done.set()

    def _execute(self, req: ToolRequest) -> ToolResult:
        name = req.name

        # 参数校验失败：直接回灌错误，让模型自己纠正
        if req.arg_error:
            return ToolResult(call_id=req.call_id, name=name, ok=False,
                              error=req.arg_error,
                              content="参数不合法：%s" % req.arg_error)

        spec = req.spec or self._registry.get(name)
        if spec is None:
            known = "、".join(self._registry.names())
            return ToolResult(call_id=req.call_id, name=name, ok=False,
                              error="未知工具", 
                              content="没有名为「%s」的工具。可用工具：%s" % (name, known))

        # 熔断：同一工具连续失败多次就不再重试，避免死循环
        if name in self._timed_out:
            return ToolResult(call_id=req.call_id, name=name, ok=False,
                              error="已熔断",
                              content="工具「%s」本轮已连续失败，不再重试" % name,
                              user_hint="这个操作试了几次都没成功，我先停一下")

        spec = self._registry.get(name)
        try:
            output = spec.handler(**req.arguments)
        except TypeError as exc:
            return ToolResult(call_id=req.call_id, name=name, ok=False,
                              error="参数不匹配: %s" % exc,
                              content="调用工具「%s」的参数不对：%s" % (name, exc))

        text = "" if output is None else str(output)
        ok = not text.startswith("失败")
        if not ok:
            self._bump_failure(name)
        else:
            self._fail_streak[name] = 0
        return ToolResult(call_id=req.call_id, name=name, ok=ok,
                          content=text or "（工具没有返回内容）",
                          error="" if ok else text)

    def _bump_failure(self, name: str):
        from pet_engine.agent.protocol import MAX_CONSECUTIVE_FAILURES
        streak = self._fail_streak.get(name, 0) + 1
        self._fail_streak[name] = streak
        if streak >= MAX_CONSECUTIVE_FAILURES:
            self._timed_out.add(name)

    def _record(self, result: ToolResult):
        self._history.append({
            "call_id": result.call_id,
            "name": result.name,
            "ok": result.ok,
            "content": result.content[:500],
            "error": result.error[:200],
        })
        if self._on_trace is not None:
            try:
                self._on_trace("🔧 %s %s" % (result.name, "✓" if result.ok else "✗"))
            except Exception:
                pass

    def trace(self) -> list[dict]:
        """执行轨迹（供界面展示 / 问题回放）。"""
        return list(self._history)

    def clear_trace(self):
        self._history = []
