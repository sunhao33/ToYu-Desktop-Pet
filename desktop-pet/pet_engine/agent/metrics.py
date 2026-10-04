"""量化指标采集 —— 评审要"用数据论证"，这些就是数据。

记录内容（每次对话一条）：
  * 是否用了工具、用了几个、成功几个
  * 模型调用耗时、工具执行耗时
  * 是否从记忆召回、召回几条
  * 是否走了降级链（规则兜底）
  * 感知延迟（从用户发消息到界面开始显示）

存储：%APPDATA%\\ToYu\\metrics\\events.jsonl（追加写，JSON 行格式）
      —— 用 JSONL 而不是 JSON 数组：追加写不需要读整个文件，
      也不会因为一次写入失败丢掉全部历史。

聚合：summary() 直接算成功率、平均耗时等，供界面展示。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        "ToYu", "metrics")
EVENTS_FILE = os.path.join(DATA_DIR, "events.jsonl")

MAX_LINES = 20000          # 超过就轮转，避免文件无限增长
KEEP_DAYS = 90


class MetricsRecorder:
    """极简指标采集器：只追加，不阻塞。"""

    def __init__(self, path: str | None = None):
        self._path = path or EVENTS_FILE
        self._buffer: list[dict] = []

    # ── 记录 ────────────────────────────────────────────────
    def record(self, event: str, **fields):
        """记一条事件。任何异常都吞掉 —— 埋点绝不能影响主流程。"""
        item = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event}
        item.update(fields)
        self._buffer.append(item)
        if len(self._buffer) >= 5:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        items, self._buffer = self._buffer, []
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as fh:
                for item in items:
                    fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            self._rotate_if_needed()
        except Exception as exc:  # noqa: BLE001
            print("[Metrics] 写入失败: %s" % exc)

    def _rotate_if_needed(self):
        try:
            if not os.path.exists(self._path):
                return
            with open(self._path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
            if len(lines) <= MAX_LINES:
                return
            # 只保留最近的 KEEP_DAYS 天
            cutoff = (datetime.now() - timedelta(days=KEEP_DAYS)).isoformat()
            kept = []
            for line in lines[-MAX_LINES:]:
                try:
                    if json.loads(line).get("ts", "") >= cutoff:
                        kept.append(line)
                except json.JSONDecodeError:
                    continue
            with open(self._path, "w", encoding="utf-8") as fh:
                fh.writelines(kept)
        except Exception:  # noqa: BLE001
            pass

    # ── 读取与聚合 ──────────────────────────────────────────
    def load(self, days: int = 30) -> list[dict]:
        self.flush()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        out = []
        try:
            if not os.path.exists(self._path):
                return []
            with open(self._path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if item.get("ts", "") >= cutoff:
                        out.append(item)
        except Exception as exc:  # noqa: BLE001
            print("[Metrics] 读取失败: %s" % exc)
        return out

    def summary(self, days: int = 30) -> dict:
        """聚合成评审能直接看的一组指标。"""
        events = self.load(days)
        turns = [e for e in events if e.get("event") == "turn"]
        tool_calls = [e for e in events if e.get("event") == "tool_call"]

        def _avg(values):
            values = [v for v in values if isinstance(v, (int, float))]
            return round(sum(values) / len(values), 1) if values else 0

        total_tools = sum(int(t.get("tool_calls", 0) or 0) for t in turns)
        ok_tools = sum(int(t.get("tool_ok", 0) or 0) for t in turns)
        with_tools = [t for t in turns if int(t.get("tool_calls", 0) or 0) > 0]
        recalled = [t for t in turns if int(t.get("recall", 0) or 0) > 0]
        degraded = [t for t in turns if t.get("degraded")]

        return {
            "days": days,
            "turns": len(turns),
            "turns_with_tools": len(with_tools),
            "tool_calls_total": total_tools,
            "tool_calls_ok": ok_tools,
            "tool_success_rate": (round(ok_tools / total_tools, 3)
                                  if total_tools else 0.0),
            "tool_calls_avg_per_turn": (round(total_tools / len(turns), 2)
                                        if turns else 0.0),
            "recall_turns": len(recalled),
            "recall_rate": (round(len(recalled) / len(turns), 3)
                            if turns else 0.0),
            "degraded_turns": len(degraded),
            "avg_model_ms": _avg([t.get("model_ms") for t in turns]),
            "avg_tool_ms": _avg([t.get("tool_ms") for t in tool_calls]),
            "avg_perceived_ms": _avg([t.get("perceived_ms") for t in turns]),
            "avg_reply_chars": _avg([t.get("reply_chars") for t in turns]),
        }

    def recent(self, limit: int = 10) -> list[dict]:
        return self.load(days=7)[-limit:]

    def clear(self):
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except Exception as exc:  # noqa: BLE001
            print("[Metrics] 清理失败: %s" % exc)
