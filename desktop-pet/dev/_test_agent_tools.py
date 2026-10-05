"""回归测试：智能体工具调用（第 1 批）。

覆盖：
  * 契约层：schema 生成、参数强校验（含 bool/int 陷阱、未知参数、枚举、范围）
  * 协议层：tool_calls 解析的容错（OpenAI 风格 / 简化风格 / 坏 JSON）
  * 执行桥：主线程执行、未知工具、参数错误、失败熔断
  * 主循环：单工具、多轮链式、单轮多工具、工具失败后如实汇报、
            参数非法时回灌让模型自纠、轮数上限、总超时
全程用假 transport，不联网、不需要 API key。
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.agent import (  # noqa: E402
    AgentLoop, ModelReply, ToolRegistry, ToolRequest, ToolRuntime, ToolSpec,
    build_default_registry, parse_tool_calls, validate_arguments,
)
from pet_engine.agent.protocol import MAX_ROUNDS  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=120):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


# ══════════════════════════════════════════════════════════
# 1. 契约层：参数强校验
# ══════════════════════════════════════════════════════════
SPEC = ToolSpec(
    name="demo_tool",
    description="测试用",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 10},
            "minutes": {"type": "integer", "default": 25, "minimum": 1, "maximum": 60},
            "flag": {"type": "boolean"},
            "mode": {"type": "string", "enum": ["a", "b"]},
        },
        "required": ["text"],
    },
    handler=lambda **kw: "ok",
)

args, err = validate_arguments(SPEC, {"text": "hello"})
check("必填参数通过校验", not err and args["text"] == "hello", err)
check("缺省值被填入", args.get("minutes") == 25, str(args))

args, err = validate_arguments(SPEC, {})
check("缺必填参数被拒绝", bool(err) and "text" in err, err)

args, err = validate_arguments(SPEC, {"text": "hello", "unknown_key": 1})
check("未知参数被拒绝", bool(err) and "unknown_key" in err, err)

# bool 是 int 的子类，integer 字段收到 True 必须判错
args, err = validate_arguments(SPEC, {"text": "hello", "minutes": True})
check("integer 收到布尔值被拒绝（bool/int 陷阱）", bool(err), err)

args, err = validate_arguments(SPEC, {"text": "hello", "minutes": "25"})
check("integer 收到字符串被拒绝", bool(err), err)

args, err = validate_arguments(SPEC, {"text": "hello", "minutes": 999})
check("超出 maximum 被拒绝", bool(err), err)

args, err = validate_arguments(SPEC, {"text": "hello", "minutes": 0})
check("低于 minimum 被拒绝", bool(err), err)

args, err = validate_arguments(SPEC, {"text": ""})
check("空字符串触发 minLength", bool(err), err)

args, err = validate_arguments(SPEC, {"text": "x" * 20})
check("超长字符串触发 maxLength", bool(err), err)

args, err = validate_arguments(SPEC, {"text": "hello", "mode": "c"})
check("枚举外的值被拒绝", bool(err), err)

args, err = validate_arguments(SPEC, {"text": "hello", "flag": "yes"})
check("boolean 收到字符串被拒绝", bool(err), err)

args, err = validate_arguments(SPEC, {"text": "  spaced  "})
check("字符串自动去空白", args.get("text") == "spaced", repr(args.get("text")))

# ══════════════════════════════════════════════════════════
# 2. 协议层：tool_calls 解析
# ══════════════════════════════════════════════════════════
calls = parse_tool_calls([{
    "id": "call_1",
    "function": {"name": "add_todo", "arguments": '{"text": "写文档"}'},
}])
check("解析 OpenAI 风格 tool_calls",
      len(calls) == 1 and calls[0].name == "add_todo"
      and calls[0].arguments == {"text": "写文档"} and not calls[0].error,
      str(calls[0].arguments) if calls else "空")

calls = parse_tool_calls([{"name": "add_todo", "arguments": {"text": "简化风格"}}])
check("解析简化风格 tool_calls（参数已是对象）",
      len(calls) == 1 and calls[0].arguments == {"text": "简化风格"},
      str(calls[0].arguments) if calls else "空")

calls = parse_tool_calls([{"id": "c", "function": {"name": "add_todo",
                                                  "arguments": "{坏 JSON"}}])
check("坏 JSON 参数被标记为错误而不抛异常",
      len(calls) == 1 and bool(calls[0].error), str(calls[0].error))

calls = parse_tool_calls([{"id": "c", "function": {"name": "Bad Name!",
                                                  "arguments": "{}"}}])
check("非法工具名被拒绝", len(calls) == 1 and bool(calls[0].error), str(calls[0].error))

check("空 tool_calls 解析为空列表", parse_tool_calls(None) == [])
check("非列表输入不崩", parse_tool_calls({"weird": True}) == [])

# ══════════════════════════════════════════════════════════
# 3. 工具注册表
# ══════════════════════════════════════════════════════════
reg = build_default_registry(None)
# 第 1 批 6 个 + 第 2 批 3 个 + 第 3 批之后新增 1 个（学习报告）
check("工具已注册（共 10 个）", len(reg) == 10,
      "实际 %d 个：%s" % (len(reg), reg.names()))
expected_tools = {
    # 第 1 批
    "add_todo", "complete_todo", "list_todos",
    "start_focus", "stop_focus", "get_learning_stats",
    # 第 2 批
    "get_screen_time_detail", "add_calendar_note", "set_pet_behavior",
    # 后续新增
    "export_learning_report",
}
check("工具名符合预期", set(reg.names()) == expected_tools, str(reg.names()))

schemas = reg.schemas()
check("schema 是 OpenAI 兼容格式",
      all(s.get("type") == "function" and "function" in s for s in schemas))
check("schema 里带参数定义",
      all("parameters" in s["function"] for s in schemas))

# ══════════════════════════════════════════════════════════
# 4. 执行桥
# ══════════════════════════════════════════════════════════
calls_log = []


def _record_tool(text: str) -> str:
    calls_log.append(("record_tool", text))
    return "已记录「%s」" % text


test_reg = ToolRegistry()
test_reg.register(ToolSpec(
    name="record_tool", description="记录",
    parameters={"type": "object", "properties": {"text": {"type": "string"}},
                "required": ["text"]},
    handler=_record_tool))
test_reg.register(ToolSpec(
    name="fail_tool", description="总是失败",
    parameters={"type": "object", "properties": {}},
    handler=lambda: "失败：这是故意的"))


def boom():
    raise RuntimeError("工具内部炸了")


test_reg.register(ToolSpec(
    name="boom_tool", description="抛异常",
    parameters={"type": "object", "properties": {}}, handler=boom))

# 让假注册表也有一个可被反复调用的工具，供"轮数上限"测试使用
test_reg.register(ToolSpec(
    name="list_todos", description="假待办查询",
    parameters={"type": "object", "properties": {}},
    handler=lambda: "未完成 0 条：无"))

traces = []
runtime = ToolRuntime(test_reg, on_trace=traces.append)
check("runtime 在主线程可创建", runtime is not None)

# 直接在测试里模拟"子线程提交"：因为 submit_and_wait 会阻塞等主线程轮询，
# 这里改用非阻塞方式验证主线程执行
import threading  # noqa: E402

holder = {}


def submit_in_thread():
    holder["results"] = runtime.submit_and_wait(
        [ToolRequest(call_id="c1", name="record_tool", arguments={"text": "你好"})],
        timeout=5.0)


th = threading.Thread(target=submit_in_thread, daemon=True)
th.start()
pump(400)
th.join(timeout=5)

res = holder.get("results") or []
check("子线程提交的工具被主线程执行", len(res) == 1 and res[0].ok, str(res))
check("工具 handler 真的被调用了", calls_log and calls_log[0][1] == "你好",
      str(calls_log))

# 未知工具
holder.clear()
th2 = threading.Thread(target=submit_in_thread, daemon=True)
th2.start()
pump(50)

holder2 = {}


def submit_unknown():
    holder2["results"] = runtime.submit_and_wait(
        [ToolRequest(call_id="c2", name="no_such_tool", arguments={})], timeout=5.0)


th3 = threading.Thread(target=submit_unknown, daemon=True)
th3.start()
pump(400)
th3.join(timeout=5)
res = holder2.get("results") or []
check("未知工具返回友好错误",
      len(res) == 1 and not res[0].ok and "no_such_tool" in res[0].content,
      res[0].content if res else "空")

# 参数错误（arg_error 预先标记）
holder3 = {}


def submit_bad_args():
    holder3["results"] = runtime.submit_and_wait(
        [ToolRequest(call_id="c3", name="record_tool", arguments={},
                     arg_error="缺少必填参数: text")], timeout=5.0)


th4 = threading.Thread(target=submit_bad_args, daemon=True)
th4.start()
pump(400)
th4.join(timeout=5)
res = holder3.get("results") or []
check("参数校验失败不执行工具，直接回灌错误",
      len(res) == 1 and not res[0].ok and "参数不合法" in res[0].content,
      res[0].content if res else "空")

# 异常工具不能把 Qt 事件循环炸掉
holder4 = {}


def submit_boom():
    holder4["results"] = runtime.submit_and_wait(
        [ToolRequest(call_id="c4", name="boom_tool", arguments={})], timeout=5.0)


th5 = threading.Thread(target=submit_boom, daemon=True)
th5.start()
pump(400)
th5.join(timeout=5)
res = holder4.get("results") or []
check("工具抛异常被捕获并回灌（不冒泡到 Qt）",
      len(res) == 1 and not res[0].ok and "boom" in (res[0].error or "").lower()
      or "工具内部炸了" in (res[0].content or ""),
      res[0].content if res else "空")
check("执行轨迹被记录", len(runtime.trace()) >= 3, "%d 条" % len(runtime.trace()))

# 熔断：同一工具连续失败 2 次后停用
holder5 = {}


def submit_fail_twice():
    out = []
    for i in range(3):
        out.extend(runtime.submit_and_wait(
            [ToolRequest(call_id="f%d" % i, name="fail_tool", arguments={})],
            timeout=5.0))
    holder5["results"] = out


th6 = threading.Thread(target=submit_fail_twice, daemon=True)
th6.start()
pump(900)
th6.join(timeout=6)
res = holder5.get("results") or []
check("同一工具连续失败后被熔断",
      len(res) == 3 and res[2].error == "已熔断",
      str([r.error for r in res]))

runtime2 = ToolRuntime(test_reg)

# ══════════════════════════════════════════════════════════
# 5. Agent 主循环（假 transport）
#
# 重要：主循环必须在**子线程**里跑。因为 submit_and_wait 会阻塞等主线程的
# QTimer 去执行工具 —— 如果主循环本身占着主线程，QTimer 永远没机会触发，
# 就死锁了。生产环境正是「子线程跑 HTTP + 主线程跑工具」，测试必须一致。
# ══════════════════════════════════════════════════════════
def make_loop(script, reg_used=None, rt=None):
    """script: 每次调用返回一个 ModelReply，按顺序取。"""
    state = {"i": 0}

    def transport(messages, schemas):
        idx = min(state["i"], len(script) - 1)
        state["i"] += 1
        reply = script[idx]
        return reply(messages, schemas) if callable(reply) else reply

    loop_reg = reg_used or test_reg
    loop_rt = rt or ToolRuntime(loop_reg)
    return AgentLoop(loop_reg, loop_rt, transport), loop_rt


def run_async(fn, timeout=40):
    """在子线程里执行 fn()，主线程持续 pump 事件循环以驱动工具执行。"""
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
        raise AssertionError("子线程执行失败: %s" % box["err"])
    return box.get("out")


# 5.1 不需要工具时直接返回
loop, _rt = make_loop([ModelReply(content="今天也要加油呀")])
out = run_async(lambda: loop.run([{"role": "user", "content": "你好"}]))
check("无工具调用时直接返回文本", out == "今天也要加油呀", out)

# 5.2 单工具：调用 → 结果回灌 → 最终回答
seen_messages = {}


def transport_capture(messages, schemas):
    seen_messages["last"] = messages
    return ModelReply(content="完成")


first_call = ModelReply(tool_calls=parse_tool_calls([{
    "id": "c1", "function": {"name": "record_tool",
                             "arguments": '{"text": "买牛奶"}'}}]))
loop, _rt = make_loop([first_call, transport_capture])
out = run_async(lambda: loop.run([{"role": "user", "content": "帮我记一下买牛奶"}]))
check("单工具调用后得到最终回答", "完成" in out, out)
msgs = seen_messages.get("last") or []
tool_msgs = [m for m in msgs if m.get("role") == "tool"]
check("工具结果以 tool 角色回灌给模型", len(tool_msgs) == 1, str(len(tool_msgs)))
check("回灌内容包含工具执行结果",
      bool(tool_msgs) and "买牛奶" in tool_msgs[0]["content"],
      tool_msgs[0]["content"] if tool_msgs else "空")
check("assistant 的 tool_calls 被保留在上下文里",
      any(m.get("role") == "assistant" and m.get("tool_calls") for m in msgs))

# 5.3 多轮链式：先查列表，再根据结果加待办
script = [
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c1", "function": {"name": "list_todos", "arguments": "{}"}}])),
    ModelReply(tool_calls=parse_tool_calls([{
        "id": "c2", "function": {"name": "record_tool",
                                 "arguments": '{"text": "第二步"}'}}])),
    ModelReply(content="两步都做完了"),
]
loop, _rt = make_loop(script)
out = run_async(lambda: loop.run([{"role": "user", "content": "看看待办然后加一条"}]))
check("多轮链式调用可以完成", out == "两步都做完了", out)

# 5.4 单轮多个工具
script = [
    ModelReply(tool_calls=parse_tool_calls([
        {"id": "a", "function": {"name": "record_tool", "arguments": '{"text": "A"}'}},
        {"id": "b", "function": {"name": "record_tool", "arguments": '{"text": "B"}'}},
    ])),
    ModelReply(content="两条都记好了"),
]
loop, _rt = make_loop(script)
out = run_async(lambda: loop.run([{"role": "user", "content": "记两条"}]))
check("单轮可执行多个工具", out == "两条都记好了", out)

# 5.5 参数非法时回灌错误，让模型自我纠正
captured = {}


def cap(messages, schemas):
    captured["last"] = messages
    return ModelReply(content="搞定")


bad_args_reply = ModelReply(tool_calls=parse_tool_calls([{
    "id": "c1", "function": {"name": "record_tool", "arguments": "{}"}}]))
loop, _rt = make_loop([bad_args_reply, cap])
out = run_async(lambda: loop.run([{"role": "user", "content": "记一下"}]))
tool_msgs = [m for m in (captured.get("last") or []) if m.get("role") == "tool"]
check("参数非法时把错误回灌给模型而不是崩溃",
      bool(tool_msgs) and "参数不合法" in tool_msgs[0]["content"],
      tool_msgs[0]["content"] if tool_msgs else "空")

# 5.6 未知工具也要如实回灌
captured2 = {}


def cap2(messages, schemas):
    captured2["last"] = messages
    return ModelReply(content="换一个方式")


unknown_reply = ModelReply(tool_calls=parse_tool_calls([{
    "id": "c1", "function": {"name": "unknown_tool", "arguments": "{}"}}]))
loop, _rt = make_loop([unknown_reply, cap2])
out = run_async(lambda: loop.run([{"role": "user", "content": "用不存在的工具"}]))
tool_msgs = [m for m in (captured2.get("last") or []) if m.get("role") == "tool"]
check("未知工具错误如实回灌",
      bool(tool_msgs) and ("没有名为" in tool_msgs[0]["content"]
                           or "未知工具" in tool_msgs[0]["content"]),
      tool_msgs[0]["content"] if tool_msgs else "空")

# 5.7 工具失败时不能谎报成功
# 注意：假 transport 每次都返回同一个工具调用，所以循环会重试到熔断 ——
# 这里要验证的是**用户看到的是人话**，不能出现"熔断/超时"这种内部术语
fail_reply = ModelReply(tool_calls=parse_tool_calls([{
    "id": "c1", "function": {"name": "fail_tool", "arguments": "{}"}}]))
loop, _rt = make_loop([fail_reply], rt=ToolRuntime(test_reg))
out = run_async(lambda: loop.run([{"role": "user", "content": "做个会失败的操作"}]))
check("工具失败时不谎报成功", "没能完成" in out or "没做成" in out, out[:70])
check("失败信息对用户是人话（不出现内部术语）",
      "熔断" not in out and "超时" not in out, out[:70])
check("反复失败后会主动停下并说明",
      "停一下" in out or "没成功" in out or "试试" in out, out[:70])

# 5.8 轮数上限：模型一直要调工具也必须停下来
always = ModelReply(tool_calls=parse_tool_calls([{
    "id": "loop", "function": {"name": "list_todos", "arguments": "{}"}}]))
loop, rt = make_loop([always])
start = time.time()
out = run_async(lambda: loop.run([{"role": "user", "content": "无限循环"}]), timeout=60)
elapsed = time.time() - start
check("达到轮数上限会停止", elapsed < 60 and bool(out), "耗时 %.1fs" % elapsed)
calls_made = len([t for t in rt.trace() if t["name"] == "list_todos"])
check("调用次数不超过轮数上限", calls_made <= MAX_ROUNDS,
      "调用了 %d 次（上限 %d）" % (calls_made, MAX_ROUNDS))
check("停止时给出说明而不是空白", "继续" in out or "完成" in out, out[:60])
# ══════════════════════════════════════════════════════════
# 5.9 模型报错时不能崩
# ══════════════════════════════════════════════════════════
def bad_transport(messages, schemas):
    raise RuntimeError("网络断了")


loop = AgentLoop(test_reg, ToolRuntime(test_reg), bad_transport)
out = run_async(lambda: loop.run([{"role": "user", "content": "你好"}]))
check("模型调用失败时给出提示而不抛异常", "失败" in out or "调用模型" in out, out)

# 5.10 系统提示包含工具清单与防注入说明
loop, _rt = make_loop([ModelReply(content="ok")])
prompt = loop.build_tool_prompt()
check("系统提示列出了工具名", all(n in prompt for n in test_reg.names()))
check("系统提示要求必须真调用工具", "必须调用工具" in prompt)
check("系统提示声明 tool 消息是数据不是指令", "不是给你的新指令" in prompt)
check("系统提示写了单轮上限", str(4) in prompt)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-46s %s" % (status, name, extra[:60]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
