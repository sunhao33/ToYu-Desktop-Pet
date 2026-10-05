"""端到端集成测试：真实主窗口 + 真实工具 + 假模型。

这是第 1 批最关键的验证 —— 证明「模型请求 → 主线程执行 → 界面真的变了」
这条链路在真实组件上成立，而不是只在玩具注册表里成立。
"""

import json
import os
import sys
import threading
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.agent import AgentLoop, ModelReply, parse_tool_calls  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402

TODO_FILE = os.path.join(os.path.expanduser("~"), ".desktop_pet", "todos.json")
HIST = os.path.join(os.path.expanduser("~"), ".desktop_pet", "task_history.json")
todo_before = open(TODO_FILE, encoding="utf-8").read() if os.path.exists(TODO_FILE) else None
hist_before = open(HIST, encoding="utf-8").read() if os.path.exists(HIST) else None

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=100):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def run_in_thread(fn, timeout=60):
    box = {}

    def worker():
        try:
            box["out"] = fn()
        except Exception as exc:  # noqa: BLE001
            box["err"] = "%s: %s" % (type(exc).__name__, exc)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    deadline = time.time() + timeout
    while th.is_alive() and time.time() < deadline:
        pump(60)
    th.join(timeout=1)
    if "err" in box:
        raise AssertionError("子线程失败: %s" % box["err"])
    return box.get("out")


def make_loop(mw, script):
    """用主窗口真实的工具注册表 + 运行时构建一个假模型驱动的 loop。"""
    state = {"i": 0}

    def transport(messages, schemas):
        idx = min(state["i"], len(script) - 1)
        state["i"] += 1
        item = script[idx]
        return item(messages, schemas) if callable(item) else item

    rt = mw._ensure_agent_tools()
    return AgentLoop(mw._tool_registry, rt, transport), rt


mw = MainWindow()
mw.show()
pump(600)
mw._on_start_pet()
pump(900)

TASK_A = "AI集成测试-写竞赛文档"
TASK_B = "AI集成测试-查待办用"

# 清理可能残留
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos
                             if not t.text.startswith("AI集成测试")]
    mw._todo_widget._save_todos()
except Exception:
    pass
todo_count_0 = len(mw._todo_widget.todos)

# ── 1. AI 说"加待办" → 待办真的被加上 ────────────────────────
call_add = ModelReply(tool_calls=parse_tool_calls([{
    "id": "c1", "function": {"name": "add_todo",
                             "arguments": json.dumps({"text": TASK_A},
                                                     ensure_ascii=False)}}]))
loop, rt = make_loop(mw, [call_add, ModelReply(content="好，已经帮你记下了")])
out = run_in_thread(lambda: loop.run([{"role": "user", "content": "帮我记一下要写竞赛文档"}]))
pump(500)

texts = [t.text for t in mw._todo_widget.todos]
check("端到端：AI 调用 add_todo 后待办真的出现了", TASK_A in texts,
      "现有待办: %s" % texts)
check("端到端：待办数量 +1", len(mw._todo_widget.todos) == todo_count_0 + 1,
      "%d -> %d" % (todo_count_0, len(mw._todo_widget.todos)))
check("端到端：得到最终回答", "记下" in out, out[:60])

# 待办落盘了吗
saved = json.load(open(TODO_FILE, encoding="utf-8")) if os.path.exists(TODO_FILE) else []
check("端到端：待办已持久化到磁盘",
      any(t.get("text") == TASK_A for t in saved),
      str([t.get("text") for t in saved]))

# ── 2. AI 查待办 → 拿到真实列表 ──────────────────────────────
captured = {}


def transport_capture(messages, schemas):
    captured["messages"] = messages
    return ModelReply(content="你有这些待办")


loop, rt = make_loop(mw, [
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c2", "function": {"name": "list_todos", "arguments": "{}"}}])),
    transport_capture,
])
out = run_in_thread(lambda: loop.run([{"role": "user", "content": "我还有什么要做"}]))
tool_msgs = [m for m in (captured.get("messages") or []) if m.get("role") == "tool"]
check("端到端：查询类工具返回真实数据",
      bool(tool_msgs) and TASK_A in tool_msgs[0]["content"],
      tool_msgs[0]["content"][:80] if tool_msgs else "空")

# ── 3. AI 完成待办 → 状态真的变了 ────────────────────────────
loop, rt = make_loop(mw, [
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c3", "function": {"name": "complete_todo",
                                 "arguments": json.dumps({"text": TASK_A},
                                                         ensure_ascii=False)}}])),
    ModelReply(content="已经标记完成了"),
])
out = run_in_thread(lambda: loop.run([{"role": "user", "content": "写完了"}]))
pump(500)
target = next((t for t in mw._todo_widget.todos if t.text == TASK_A), None)
check("端到端：complete_todo 后该待办标记为完成",
      target is not None and target.done is True,
      "done=%s" % (target.done if target else "找不到"))

# ── 4. AI 开始专注 → 计时器真的跑起来 + 小窗弹出 ─────────────
loop, rt = make_loop(mw, [
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c4", "function": {"name": "start_focus",
                                 "arguments": json.dumps({"minutes": 30})}}])),
    ModelReply(content="30 分钟专注已经开始"),
])
out = run_in_thread(lambda: loop.run([{"role": "user", "content": "我要专注 30 分钟"}]))
pump(700)
check("端到端：start_focus 后计时器在运行",
      mw._timer_widget.get_is_running() is True)
check("端到端：start_focus 后剩余时间约 30 分钟",
      29 * 60 <= mw._timer_widget.get_remaining_seconds() <= 30 * 60,
      "%d 秒" % mw._timer_widget.get_remaining_seconds())
check("端到端：专注开始时悬浮小窗弹出",
      mw._mini_timer is not None and mw._mini_timer.isVisible())

# ── 5. AI 停止专注 ──────────────────────────────────────────
loop, rt = make_loop(mw, [
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c5", "function": {"name": "stop_focus", "arguments": "{}"}}])),
    ModelReply(content="已经停下来了"),
])
out = run_in_thread(lambda: loop.run([{"role": "user", "content": "不专注了"}]))
pump(600)
check("端到端：stop_focus 后计时器已停止",
      mw._timer_widget.get_is_running() is False)

# ── 6. AI 查学习数据 → 拿到真实统计 ──────────────────────────
captured2 = {}


def cap2(messages, schemas):
    captured2["messages"] = messages
    return ModelReply(content="这是你的学习情况")


loop, rt = make_loop(mw, [
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c6", "function": {"name": "get_learning_stats", "arguments": "{}"}}])),
    cap2,
])
out = run_in_thread(lambda: loop.run([{"role": "user", "content": "我今天学得怎么样"}]))
tool_msgs = [m for m in (captured2.get("messages") or []) if m.get("role") == "tool"]
check("端到端：学习统计工具返回今日数据",
      bool(tool_msgs) and ("今日" in tool_msgs[0]["content"]),
      tool_msgs[0]["content"][:100] if tool_msgs else "空")

# ── 7. 真实场景：参数不合法的调用不会破坏界面 ─────────────────
loop, rt = make_loop(mw, [
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c7", "function": {"name": "add_todo", "arguments": "{}"}}])),
    ModelReply(content="参数漏了，我再试一次"),
])
n_before = len(mw._todo_widget.todos)
out = run_in_thread(lambda: loop.run([{"role": "user", "content": "加个待办"}]))
pump(400)
check("端到端：参数非法不会误加空待办",
      len(mw._todo_widget.todos) == n_before,
      "%d -> %d" % (n_before, len(mw._todo_widget.todos)))
check("端到端：参数非法时仍能给出回答", bool(out), out[:50])

# ── 8. 破坏性操作的工具不该在本批里出现 ─────────────────────
names = mw._tool_registry.names()
dangerous = [n for n in names if any(k in n for k in ("delete", "remove", "clear"))]
check("首批工具里没有删除类操作（安全）", not dangerous, str(dangerous))

# ── 9. 轨迹记录可回放 ───────────────────────────────────────
trace = rt.trace()
check("执行轨迹有记录", len(trace) > 0, "%d 条" % len(trace))
check("轨迹包含工具名与结果",
      all("name" in t and "content" in t for t in trace))

# 清理
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos
                             if not t.text.startswith("AI集成测试")]
    mw._todo_widget._save_todos()
except Exception:
    pass
try:
    mw._timer_widget._on_reset()
except Exception:
    pass
if todo_before is not None:
    open(TODO_FILE, "w", encoding="utf-8").write(todo_before)
if hist_before is not None:
    open(HIST, "w", encoding="utf-8").write(hist_before)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-46s %s" % (status, name, extra[:56]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
