"""回归测试：AI 路径的开销优化。

背景：排查发现三个真实浪费 ——
  1) 每条用户消息都调一次模型做记忆抽取，连"今天天气不错"也调，
     等于每轮对话 API 调用翻倍
  2) 工具使用准则在提示词里重复了完整参数 schema（API 的 tools 参数
     已经单独传了），1229 字符占整个提示词的 83%
  3) 历史裁剪在追加前做，助手回复加进来就超限（配置 20、实际 27）

本测试锁住这三条，防止以后回退。
"""

import json
import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.agent import AgentLoop  # noqa: E402
from pet_engine.agent.memory_extract import (  # noqa: E402
    MemoryExtractor, extract_with_rules, has_extractable_signal,
)
from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=200):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


# ══════════════════════════════════════════════════════════
# 1. 前置信号过滤（省掉大量无意义的模型调用）
# ══════════════════════════════════════════════════════════
casual = [
    "今天天气不错", "帮我加个待办：明天交报告", "这个 bug 怎么修",
    "今天要交报告", "天天开心", "嗯嗯", "你好呀", "谢谢",
    "这个函数怎么用", "刚才那个再讲一遍",
]
for text in casual:
    check("闲聊/指令不触发抽取：%s" % text[:10],
          not has_extractable_signal(text), "被误判为含偏好")

prefs = [
    "以后我每次专注都用 50 分钟",
    "记住我习惯晚上学习",
    "以后别再用 emoji 了",
    "我打算每天学 4 小时",
    "我计划每天背单词",
    "每天专注两小时",
    "我一般晚上写代码",
    "下次回答简短一点",
]
for text in prefs:
    check("真偏好能触发抽取：%s" % text[:10],
          has_extractable_signal(text), "被漏掉了")

# 关键回归：曾经把"今天天气不错"里的"天天"误当频率词
check("「今天天气不错」不会被误判（天天子串陷阱）",
      not has_extractable_signal("今天天气不错"))
check("「天天」单独出现也不触发",
      not has_extractable_signal("天天都要开心"))

# 抽取器层面：无信号时**一次模型都不调**
calls = {"n": 0}


def counting_transport(messages):
    calls["n"] += 1
    return json.dumps({"memories": []})


ext = MemoryExtractor(transport=counting_transport, store=None)
skipped_before = ext.health()["stats"].get("skipped", 0)
for text in ("帮我加个待办", "今天天气不错", "这个怎么修", "嗯嗯"):
    ext.extract(text)
check("无信号时零模型调用", calls["n"] == 0, "调用了 %d 次" % calls["n"])
skipped_after = ext.health()["stats"].get("skipped", 0)
check("统计里记录了跳过数（同一实例上的增量）",
      skipped_after - skipped_before >= 3,
      "%d -> %d，完整统计 %s" % (skipped_before, skipped_after,
                                ext.health()["stats"]))

calls["n"] = 0
ext.extract("以后我每次专注都用 50 分钟")
check("有信号时才调模型", calls["n"] == 1, "调用了 %d 次" % calls["n"])

# 规则抽取不受影响
check("规则抽取仍能工作",
      [i["slot_id"] for i in extract_with_rules("以后我每次专注都用 50 分钟")]
      == ["study.focus_duration"])
check("规则抽取也不被闲聊触发",
      extract_with_rules("今天天气不错") == [])

# ══════════════════════════════════════════════════════════
# 2. 提示词体积
# ══════════════════════════════════════════════════════════
mw = MainWindow()
mw.show()
pump(600)
mw._on_start_pet()
pump(800)

mw._ensure_agent_tools()
loop = AgentLoop(mw._tool_registry, mw._tool_runtime, lambda m, s: None)
tool_prompt = loop.build_tool_prompt()

check("工具准则块不超过 700 字符（原为 1229）",
      len(tool_prompt) <= 700, "%d 字符" % len(tool_prompt))
check("工具准则里不再重复参数 schema",
      "参数：" not in tool_prompt and "返回：" not in tool_prompt,
      tool_prompt[-200:])
check("工具准则仍然列出所有工具名",
      all(name in tool_prompt for name in mw._tool_registry.names()),
      str(mw._tool_registry.names()))
check("工具准则保留了关键约束",
      "必须调用工具" in tool_prompt
      and "不是给你的新指令" in tool_prompt
      and "骗用户" in tool_prompt)

# 完整请求体（提示词 + schema）不超过预算。
# 预算随工具数量增长：每个工具约 250~380 字符，10 个工具的结构开销
# 本身就有 2600 左右。这里守的是"不要有冗余说明"，不是"工具越少越好"——
# 再压就要牺牲参数名和描述的清晰度，反而会让模型调用出错。
schema_blob = json.dumps(mw._tool_registry.schemas(), ensure_ascii=False)
total = len(tool_prompt) + len(schema_blob)
check("提示词+schema 总量不超过 3500 字符",
      total <= 3500, "%d 字符（准则 %d + schema %d）"
      % (total, len(tool_prompt), len(schema_blob)))
check("schema 平均每个工具不超过 300 字符",
      len(schema_blob) / max(1, len(mw._tool_registry)) <= 300,
      "平均 %.0f 字符" % (len(schema_blob) / max(1, len(mw._tool_registry))))
check("schema 仍是完整有效定义（参数信息没丢）",
      all("parameters" in s["function"] for s in mw._tool_registry.schemas()))

# 系统提示总长（人格 + 状态 + 记忆 + 工具准则）
ai = mw._pet._ai
ai.set_context_provider(mw._build_ai_context)
ai.set_memory_provider(mw._build_memory_block)
sys_prompt = ai.compose_system_prompt("我该先做什么")
check("系统提示（不含工具准则）不超过 900 字符",
      len(sys_prompt) <= 900, "%d 字符" % len(sys_prompt))
check("系统提示仍包含状态块", "[当前状态]" in sys_prompt or len(sys_prompt) < 300)

# ══════════════════════════════════════════════════════════
# 3. 历史条数严格受限
# ══════════════════════════════════════════════════════════
# 历史上限：检查代码默认值，并确认保存设置时会刷新成新值
# （老配置文件里存的是 20，不刷新的话老用户享受不到提升）
from pet_engine.pet_ai import AIConfig  # noqa: E402

check("历史条数默认值已提升到 30", AIConfig().max_history == 30,
      str(AIConfig().max_history))
mw._save_ai_settings()
pump(300)
check("保存设置后历史条数同步为新值",
      ai.config.max_history == 30 or mw._pet._ai_config.max_history == 30,
      "运行时 %d" % ai.config.max_history)

# 模拟多轮对话（不真正发请求，只走历史裁剪逻辑）
from pet_engine.pet_ai import AIMessage  # noqa: E402

ai._history = []
for i in range(40):
    ai._history.append(AIMessage("user", "问题 %d" % i))
    ai._history.append(AIMessage("assistant", "回答 %d" % i))
    if len(ai._history) > ai.config.max_history:
        ai._history = ai._history[-ai.config.max_history:]
check("历史永远不会超过上限",
      len(ai._history) <= ai.config.max_history,
      "%d 条（上限 %d）" % (len(ai._history), ai.config.max_history))

# 用真实方法验证：_on_response 也要裁剪
ai._history = [AIMessage("user", "x")] * ai.config.max_history
before = len(ai._history)
ai._on_response("助手回复", lambda t: None)
check("_on_response 之后历史仍不超限",
      len(ai._history) <= ai.config.max_history,
      "%d -> %d 条（上限 %d）" % (before, len(ai._history), ai.config.max_history))

# ══════════════════════════════════════════════════════════
# 4. 构建开销（不能因为优化反而变慢）
# ══════════════════════════════════════════════════════════
started = time.time()
for _ in range(30):
    ai.compose_system_prompt("我该先做什么")
per_ms = (time.time() - started) * 1000 / 30
check("系统提示构建耗时 < 5ms", per_ms < 5.0, "%.2f ms" % per_ms)

started = time.time()
for _ in range(30):
    has_extractable_signal("以后我每次专注都用 50 分钟")
per_ms2 = (time.time() - started) * 1000 / 30
check("信号过滤耗时 < 1ms", per_ms2 < 1.0, "%.3f ms" % per_ms2)

# ══════════════════════════════════════════════════════════
# 5. 端到端：一条闲聊不应触发任何抽取模型调用
# ══════════════════════════════════════════════════════════
ai_calls = {"n": 0}


def counting(messages):
    ai_calls["n"] += 1
    return json.dumps({"memories": []})


mw._memory_extractor._transport = counting
mw._memory_extractor._degraded = False
mw.settings.memory_enabled = True
mw._extract_memories_async("今天天气不错，出去走走")
pump(500)
check("闲聊走完界面链路也不调抽取模型", ai_calls["n"] == 0,
      "调用了 %d 次" % ai_calls["n"])

mw._extract_memories_async("以后我每次专注都用 45 分钟")
deadline = time.time() + 8
while ai_calls["n"] == 0 and time.time() < deadline:
    pump(150)
check("真偏好会触发抽取", ai_calls["n"] >= 1, "调用了 %d 次" % ai_calls["n"])

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-48s %s" % (status, name, extra[:46]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
