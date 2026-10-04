"""回归测试：流式显示与指标采集（第 4 批）。

覆盖：
  * 打字机动画：完整性、跳过、空文本、超长文本不做动画
  * 聊天气泡流式追加：begin/append/finish 与一次性显示互不干扰
  * 指标采集：记录、聚合（工具成功率/记忆命中率/延迟）、JSONL 容错、
    轮转、清空
  * 主窗口接线：指标卡片、打字机开关跟随设置
"""

import json
import os
import sys
import tempfile
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.agent.metrics import MetricsRecorder  # noqa: E402
from pet_engine.agent.typing import (  # noqa: E402
    MAX_ANIMATED_CHARS, TypingAnimator,
)

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=100):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def run_animation(text, timeout=6.0):
    out = []
    animator = TypingAnimator()
    animator.chunk.connect(out.append)
    done = []
    animator.finished.connect(lambda: done.append(True))
    animator.start(text)
    deadline = time.time() + timeout
    while animator.is_running() and time.time() < deadline:
        pump(20)
    pump(80)
    return "".join(out), done


# ══════════════════════════════════════════════════════════
# 1. 打字机动画
# ══════════════════════════════════════════════════════════
text = "你好呀，我是 ToYu，今天也要加油哦！"
out, done = run_animation(text)
check("动画输出与原文完全一致", out == text, repr(out[:30]))
check("动画结束时发出 finished", bool(done))

out, _ = run_animation("")
check("空文本不输出也不崩", out == "")

# 逐字追加（分多帧）而不是一次性给
frames = []
animator = TypingAnimator()
animator.chunk.connect(frames.append)
animator.start("一二三四五六七八九十")
pump(200)
check("文本被分成多帧输出", len(frames) > 1, "%d 帧" % len(frames))
animator.finish_now()
pump(60)

# 跳过动画
skip = []
an2 = TypingAnimator()
an2.chunk.connect(skip.append)
long_text = "这是一段比较长的回复内容，" * 3
an2.start(long_text)
pump(40)
an2.finish_now()
pump(60)
check("跳过动画后内容完整", "".join(skip) == long_text,
      "%d / %d 字" % (len("".join(skip)), len(long_text)))
check("跳过后不再运行", not an2.is_running())

# 超长文本不做逐字动画（避免用户干等）
huge = "字" * (MAX_ANIMATED_CHARS + 50)
huge_frames = []
an3 = TypingAnimator()
an3.chunk.connect(huge_frames.append)
an3.start(huge)
pump(60)
check("超长文本一次性给出", len(huge_frames) == 1, "%d 帧" % len(huge_frames))
check("超长文本内容完整", "".join(huge_frames) == huge)

# 重复 start 不叠加
an4 = TypingAnimator()
acc = []
an4.chunk.connect(acc.append)
an4.start("第一次")
an4.start("第二次")
pump(300)
check("重复 start 只输出最后一次", "".join(acc) == "第二次", repr("".join(acc)))

# ══════════════════════════════════════════════════════════
# 2. 聊天气泡流式
# ══════════════════════════════════════════════════════════
from pet_engine.pet_bubble import ChatBubble  # noqa: E402

bubble = ChatBubble()
pump(100)
check("气泡有流式状态字段", hasattr(bubble, "_stream_label"))
check("初始没有流式气泡", bubble._stream_label is None)

bubble.begin_stream()
bubble.append_stream("你好")
bubble.append_stream("，我是 ToYu")
pump(60)
check("流式追加累积文本", bubble._stream_text == "你好，我是 ToYu",
      repr(bubble._stream_text))
check("流式标签已创建", bubble._stream_label is not None)
check("流式内容显示在气泡上",
      bubble._stream_label is not None and bubble._stream_label.text() == "你好，我是 ToYu")

bubble.finish_stream()
check("结束后清掉流式状态", bubble._stream_label is None)

# 流式后再用一次性显示，不应出现两个气泡
before_rows = bubble._msg_layout.count()
bubble.begin_stream()
bubble.append_stream("第一次")
bubble.show_response("第二次")
pump(60)
after_rows = bubble._msg_layout.count()
check("流式未完就一次性显示时不会重复气泡",
      after_rows <= before_rows + 2, "%d -> %d 行" % (before_rows, after_rows))

# 用动画器驱动完整流程
bubble2 = ChatBubble()
animator2 = TypingAnimator()
animator2.chunk.connect(bubble2.append_stream)
bubble2.show_response_streamed("用动画显示的回复", animator2)
pump(100)
check("show_response_streamed 会启动动画",
      bubble2._stream_label is not None or animator2.is_running())
deadline = time.time() + 5
while animator2.is_running() and time.time() < deadline:
    pump(30)
pump(80)
check("动画跑完后显示完整", bubble2._stream_text == "用动画显示的回复",
      repr(bubble2._stream_text))

# animator 为 None 时退回一次性显示
bubble3 = ChatBubble()
bubble3.show_response_streamed("没有动画", None)
pump(60)
check("animator 为 None 时退回一次性显示", bubble3._stream_label is None)

# 空文本不创建空气泡
bubble4 = ChatBubble()
rows_before = bubble4._msg_layout.count()
bubble4.show_response_streamed("", TypingAnimator())
pump(60)
check("空文本不产生空气泡", bubble4._msg_layout.count() == rows_before + 1,
      "%d -> %d" % (rows_before, bubble4._msg_layout.count()))

# ══════════════════════════════════════════════════════════
# 3. 指标采集
# ══════════════════════════════════════════════════════════
path = os.path.join(tempfile.mkdtemp(prefix="toyu_met_"), "events.jsonl")
rec = MetricsRecorder(path)
check("空记录时汇总全为 0",
      rec.summary()["turns"] == 0 and rec.summary()["tool_success_rate"] == 0.0)

# 3 轮：2 轮带工具（成功 3 次、失败 1 次），1 轮无工具
rec.record("turn", tool_calls=2, tool_ok=2, model_ms=1000, tool_ms=20,
           perceived_ms=1200, reply_chars=80, recall=2)
rec.record("turn", tool_calls=2, tool_ok=1, model_ms=2000, tool_ms=40,
           perceived_ms=2200, reply_chars=60, recall=0)
rec.record("turn", tool_calls=0, tool_ok=0, model_ms=800, tool_ms=0,
           perceived_ms=900, reply_chars=40, recall=0, degraded=True)
rec.flush()

s = rec.summary()
check("轮数统计正确", s["turns"] == 3, str(s["turns"]))
check("带工具的轮数正确", s["turns_with_tools"] == 2, str(s["turns_with_tools"]))
check("工具调用总数正确", s["tool_calls_total"] == 4, str(s["tool_calls_total"]))
check("工具成功数正确", s["tool_calls_ok"] == 3, str(s["tool_calls_ok"]))
check("工具成功率正确", abs(s["tool_success_rate"] - 0.75) < 1e-6,
      str(s["tool_success_rate"]))
check("记忆命中率正确", abs(s["recall_rate"] - 1 / 3) < 0.001, str(s["recall_rate"]))
check("降级轮数正确", s["degraded_turns"] == 1, str(s["degraded_turns"]))
check("平均模型耗时正确", abs(s["avg_model_ms"] - 1266.7) < 1.0,
      str(s["avg_model_ms"]))
check("平均端到端延迟正确", abs(s["avg_perceived_ms"] - 1433.3) < 1.0,
      str(s["avg_perceived_ms"]))

# 3.1 存储格式与容错
with open(path, "r", encoding="utf-8") as fh:
    lines = [l for l in fh.read().splitlines() if l.strip()]
check("以 JSONL 追加存储", len(lines) == 3, "%d 行" % len(lines))
check("每行是合法 JSON",
      all(isinstance(json.loads(l), dict) for l in lines))

# 混入坏行不应该让整个统计失败
with open(path, "a", encoding="utf-8") as fh:
    fh.write("这不是 json\n")
    fh.write("\n")
    fh.write('{"ts": "2020-01-01T00:00:00", "event": "turn"}\n')  # 超期
check("坏行被跳过、统计仍可用", rec.summary()["turns"] == 3,
      str(rec.summary()["turns"]))

# 3.2 天数过滤
check("days 参数能过滤旧数据", rec.summary(days=1)["turns"] == 3,
      str(rec.summary(days=1)["turns"]))
check("recent 可取出最近事件", len(rec.recent(limit=2)) >= 1)

# 3.3 清空
rec.clear()
check("清空后统计归零", rec.summary()["turns"] == 0)

# 3.4 写入失败不影响调用方（目录不可写时不抛异常）
bad = MetricsRecorder(os.path.join("\0invalid", "x.jsonl"))
bad.record("turn", tool_calls=1)
bad.flush()
check("写入失败不抛异常", True)

# 3.5 未 flush 的记录也能被 load 看到
rec2 = MetricsRecorder(os.path.join(tempfile.mkdtemp(prefix="toyu_met2_"), "e.jsonl"))
rec2.record("turn", tool_calls=1, tool_ok=1)
check("load 前会自动 flush", rec2.summary()["turns"] == 1,
      str(rec2.summary()["turns"]))

# ══════════════════════════════════════════════════════════
# 4. 主窗口接线
# ══════════════════════════════════════════════════════════
from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()
mw.show()
pump(500)
mw._on_start_pet()
pump(800)

check("指标卡片已创建", getattr(mw, "_metrics_card", None) is not None)
check("指标文案控件已创建", getattr(mw, "_metrics_label", None) is not None)
ai = mw._pet._ai
check("AI 实例挂了指标采集器", ai.metrics is not None)
check("打字机开关已接到宠物",
      hasattr(mw._pet, "_typing_enabled")
      and mw._pet._typing_enabled == mw.settings.typing_enabled,
      "%s vs %s" % (mw._pet._typing_enabled, mw.settings.typing_enabled))

mw._refresh_metrics_card()
pump(150)
check("指标卡片有文案", len(mw._metrics_label.text()) > 0,
      mw._metrics_label.text()[:40])

# 造数据后卡片显示统计
ai.metrics.clear()
for _ in range(3):
    ai.metrics.record("turn", tool_calls=1, tool_ok=1, model_ms=1200,
                      tool_ms=25, perceived_ms=1300, reply_chars=70, recall=1)
ai.metrics.flush()
mw._refresh_metrics_card()
pump(150)
card_text = mw._metrics_label.text()
check("卡片显示轮数", "3 轮对话" in card_text, card_text[:60])
check("卡片显示工具成功率", "成功率" in card_text, card_text[:80])
check("卡片显示记忆命中率", "记忆命中率" in card_text, card_text[:120])

mw._clear_metrics()
pump(150)
check("清空后卡片回到空状态", "还没有对话记录" in mw._metrics_label.text(),
      mw._metrics_label.text()[:40])

# 端到端指标：模拟一轮带工具的对话后应有记录
before_turns = ai.metrics.summary()["turns"]
from pet_engine.agent.protocol import ModelReply, parse_tool_calls  # noqa: E402


class _FakeWorker:
    stats = {"tool_calls": 2, "tool_ok": 1, "rounds": 2, "model_ms": 900,
             "tool_ms": 30, "total_ms": 950, "reply_chars": 55,
             "hit_round_limit": False, "transport_error": ""}


ai._agent_worker = _FakeWorker()
ai._turn_started = time.time() - 1.0
got = []
ai._on_agent_response("测试回复", lambda t: got.append(t))
pump(100)
after = ai.metrics.summary()
check("一轮对话会写入指标", after["turns"] == before_turns + 1,
      "%d -> %d" % (before_turns, after["turns"]))
check("指标记录了工具调用", after["tool_calls_total"] >= 2,
      str(after["tool_calls_total"]))
check("回复仍然正常交给界面", got == ["测试回复"], str(got))
ai.metrics.clear()

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-46s %s" % (status, name, extra[:50]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
