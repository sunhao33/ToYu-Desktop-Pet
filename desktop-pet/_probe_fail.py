"""Debug: why does fail_tool report 已熔断 on the first call in the loop test?"""

import os
import sys
import threading
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.agent import (  # noqa: E402
    AgentLoop, ModelReply, ToolRegistry, ToolRuntime, ToolSpec, parse_tool_calls,
)

reg = ToolRegistry()
reg.register(ToolSpec(
    name="fail_tool", description="总是失败",
    parameters={"type": "object", "properties": {}},
    handler=lambda: "失败：这是故意的"))


def pump(ms=60):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


# 完全干净的 runtime，没有任何前置调用
rt = ToolRuntime(reg)
print("初始状态: _timed_out=%s _fail_streak=%s" % (rt._timed_out, rt._fail_streak))

reply = ModelReply(tool_calls=parse_tool_calls([{
    "id": "c1", "function": {"name": "fail_tool", "arguments": "{}"}}]))
loop = AgentLoop(reg, rt, lambda m, s: reply)

box = {}


def worker():
    try:
        box["out"] = loop.run([{"role": "user", "content": "测试"}])
    except Exception as exc:  # noqa: BLE001
        box["err"] = "%s: %s" % (type(exc).__name__, exc)


th = threading.Thread(target=worker, daemon=True)
th.start()
deadline = time.time() + 20
while th.is_alive() and time.time() < deadline:
    pump(60)
th.join(timeout=1)

print("输出:", repr(box.get("out")))
print("错误:", box.get("err"))
print("轨迹:")
for t in rt.trace():
    print("   %s ok=%s error=%r content=%r"
          % (t["name"], t["ok"], t["error"], t["content"][:50]))
print("结束后: _timed_out=%s _fail_streak=%s" % (rt._timed_out, rt._fail_streak))

sys.stdout.flush()
os._exit(0)
