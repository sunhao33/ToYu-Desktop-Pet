"""回归测试：长期记忆的界面集成（第 3 批）。

验证真实主窗口上的完整链路：
  * 记忆库、卡片、隐私开关接线正确
  * 一轮对话后自动抽取偏好并入库（用假模型，不联网）
  * 相关记忆被注入系统提示、无关记忆不被注入
  * 精准遗忘：单条删除 / 一键清空（含自动备份）
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

from pet_engine.agent.memory_store import MemoryStore  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=200):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


mw = MainWindow()
mw.show()
pump(600)
mw._on_start_pet()
pump(800)

# 用临时库，避免污染真实记忆
mw._memory_store = MemoryStore(
    os.path.join(tempfile.mkdtemp(prefix="toyu_memui_"), "memories.json"))
if mw._memory_extractor is not None:
    mw._memory_extractor._store = mw._memory_store

# ══════════════════════════════════════════════════════════
# 1. 接线
# ══════════════════════════════════════════════════════════
check("记忆卡片已创建", getattr(mw, "_memory_card", None) is not None)
check("记忆库可用", mw._memory_store is not None)
check("抽取器已创建", mw._memory_extractor is not None)
check("AI 拿到记忆提供者", mw._pet._ai._memory_provider is not None)
check("宠物拿到轮次结束回调", mw._pet._on_turn_finished is not None)
check("记忆开关默认开启", mw.settings.memory_enabled is True)

mw._refresh_memory_card()
pump(200)
check("空库摘要正确", "已记住 0 条" in mw._memory_summary.text(),
      mw._memory_summary.text())
check("空库时清空按钮禁用", not mw._clear_memory_btn.isEnabled())
check("空库时显示引导文案", mw._memory_list.count() >= 1)

# ══════════════════════════════════════════════════════════
# 2. 一轮对话后自动抽取（假模型）
# ══════════════════════════════════════════════════════════


def fake_transport(messages):
    return json.dumps({"memories": [
        {"slot_id": "study.focus_duration", "value": 50,
         "confidence": 0.5, "evidence": "用户说以后每次专注都用 50 分钟"},
        {"slot_id": "assistant.use_emoji", "value": False,
         "confidence": 0.4, "evidence": "用户说以后别再用 emoji"},
    ]}, ensure_ascii=False)


mw._memory_extractor._transport = fake_transport
check("抽取器处于正常状态", mw._memory_extractor.health()["degraded"] is False)

mw._extract_memories_async("以后我每次专注都用 50 分钟，别再用 emoji 了")
# 等待后台线程完成
deadline = time.time() + 10
while mw._memory_store.count() < 2 and time.time() < deadline:
    pump(150)
pump(400)

check("对话后自动抽取并入库", mw._memory_store.count() == 2,
      "%d 条" % mw._memory_store.count())
check("卡片摘要已更新", "已记住 2 条" in mw._memory_summary.text(),
      mw._memory_summary.text())
check("清空按钮已启用", mw._clear_memory_btn.isEnabled())
check("列表出现记忆行", mw._memory_list.count() - 1 == 2,
      "%d 行" % (mw._memory_list.count() - 1))

rec = mw._memory_store.get("study.focus_duration")
check("置信度被重算（模型只报 0.5，有显性信号应到 0.9）",
      rec is not None and rec.confidence >= 0.9,
      str(rec.confidence) if rec else "")

# 过短文本不抽取
before = mw._memory_store.count()
mw._extract_memories_async("嗯")
pump(400)
check("过短输入不触发抽取", mw._memory_store.count() == before)

# 记忆开关关闭时不抽取
mw.settings.memory_enabled = False
mw._extract_memories_async("以后我打算每天学 8 小时")
pump(400)
check("关闭开关后不再抽取", mw._memory_store.count() == before,
      "%d 条" % mw._memory_store.count())
mw.settings.memory_enabled = True

# ══════════════════════════════════════════════════════════
# 3. 注入系统提示
# ══════════════════════════════════════════════════════════
ai = mw._pet._ai
prompt_rel = ai.compose_system_prompt("我专注应该用多久")
check("相关问题会注入记忆块", "[关于这位用户]" in prompt_rel, prompt_rel[-120:])
check("注入的是相关记忆", "study.focus_duration" in prompt_rel)

prompt_irrel = ai.compose_system_prompt("qqq zzz xxx yyy")
check("无关问题不注入记忆块", "[关于这位用户]" not in prompt_irrel,
      prompt_irrel[-100:])

block = mw._build_memory_block("emoji 能用吗")
check("按不同问题召回不同记忆", "assistant.use_emoji" in block, block[:120])

# 桌面状态块与记忆块同时存在
prompt_both = ai.compose_system_prompt("专注")
check("状态块与记忆块可共存",
      "[当前状态]" in prompt_both, prompt_both[-160:])

# ══════════════════════════════════════════════════════════
# 4. 精准遗忘
# ══════════════════════════════════════════════════════════
mw._forget_memory("assistant.use_emoji")
pump(300)
check("单条遗忘生效", mw._memory_store.get("assistant.use_emoji") is None)
check("遗忘后计数减少", mw._memory_store.count() == 1,
      "%d 条" % mw._memory_store.count())
check("遗忘后卡片刷新", "已记住 1 条" in mw._memory_summary.text(),
      mw._memory_summary.text())
check("被遗忘的记忆不再注入",
      "assistant.use_emoji" not in ai.compose_system_prompt("emoji 能用吗"))

before_files = set(os.listdir(os.path.dirname(mw._memory_store._path)))
mw._forget_all_memories()
pump(300)
check("一键清空生效", mw._memory_store.count() == 0,
      "%d 条" % mw._memory_store.count())
after_files = set(os.listdir(os.path.dirname(mw._memory_store._path)))
check("清空前自动备份", len(after_files - before_files) >= 1,
      "新增文件 %s" % sorted(after_files - before_files))
check("清空后卡片更新", "已记住 0 条" in mw._memory_summary.text(),
      mw._memory_summary.text())

# ══════════════════════════════════════════════════════════
# 5. 抽取失败不能影响对话
# ══════════════════════════════════════════════════════════
def boom_transport(messages):
    raise RuntimeError("模拟网络故障")


mw._memory_extractor._transport = boom_transport
errors = []
mw._extract_memories_async("以后我每次专注都用 30 分钟")
pump(700)
check("抽取失败不抛异常（已降级）", mw._memory_extractor.health()["degraded"] is True,
      mw._memory_extractor.health()["reason"])
check("降级时规则兜底仍然入库", mw._memory_store.count() >= 1,
      "%d 条" % mw._memory_store.count())
check("降级告警显示到状态栏", "降级" in mw._status.text() or "⚠" in mw._status.text(),
      mw._status.text()[:60])

# 恢复后自动回到正常
mw._memory_extractor._transport = fake_transport
mw._memory_extractor._degraded_at = time.time() - 999
mw._extract_memories_async("以后我打算每天学 3 小时")
pump(900)
check("冷却结束后自动恢复", mw._memory_extractor.health()["degraded"] is False,
      mw._memory_extractor.health()["reason"])

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-46s %s" % (status, name, extra[:50]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
