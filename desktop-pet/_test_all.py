"""Run every regression test in this project. Usage: python _test_all.py

退出码 0 表示全部通过。

每条测试都有独立超时：任何一个用例卡死（死锁/等待事件）都会被强杀并标记为
TIMEOUT，而不是把整个测试套件挂住。进度实时打印，便于定位卡在哪一条。
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# 单条测试的墙钟上限（秒）。集成类用例会起真实主窗口，给得多一些。
DEFAULT_TIMEOUT = 180
TIMEOUT_OVERRIDES = {
    "_test_agent_integration.py": 240,
    "_test_flow_mode.py": 240,
    "_test_mini_timer.py": 240,
    "_test_crash_guard.py": 240,
}

TESTS = [
    ("桌面工具逻辑（剪贴板/护眼）", "_test_tools.py"),
    ("精灵可见区域计算", "_test_sprite_bounds.py"),
    ("崩溃防护", "_test_crash_guard.py"),
    ("屏幕时间会话记录与小时分布", "_test_screen_time.py"),
    ("会话合并与启动行为", "_test_compact.py"),
    ("主窗口标签切换", "_test_tab_switch.py"),
    ("宠物图保存（原子写入/并发）", "_test_image_save.py"),
    ("覆层随宠物回家清理", "_test_overlays.py"),
    ("学习统计图表刷新", "_test_charts.py"),
    ("配件层对齐与内容区比例", "_test_accessory_align.py"),
    ("宠物始终留在屏幕内", "_test_pet_onscreen.py"),
    ("窗口缩放不裁切内容", "_test_window_resize.py"),
    ("心流模式", "_test_flow_mode.py"),
    ("心流计划栏交互", "_test_flow_plan.py"),
    ("心流计划项独立计时", "_test_flow_task_timer.py"),
    ("悬浮计时小窗", "_test_mini_timer.py"),
    ("智能体工具调用", "_test_agent_tools.py"),
    ("智能体端到端集成", "_test_agent_integration.py"),
    ("智能体上下文注入", "_test_agent_context.py"),
    ("长期记忆（槽位/契约/存储/召回）", "_test_agent_memory.py"),
    ("长期记忆界面集成", "_test_agent_memory_ui.py"),
    ("流式显示与指标采集", "_test_agent_stream.py"),
]

env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"


def run_one(script: str, timeout: int):
    """跑一条测试，返回 (returncode, 输出, 耗时)。超时返回 returncode=None。"""
    path = os.path.join(HERE, script)
    started = time.time()
    proc = subprocess.Popen(
        [sys.executable, script], cwd=HERE, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace")
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out or "", time.time() - started
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            out, _ = proc.communicate(timeout=15)
        except Exception:
            out = ""
        return None, out or "", time.time() - started


results = []
total_started = time.time()

for idx, (label, script) in enumerate(TESTS, 1):
    if not os.path.exists(os.path.join(HERE, script)):
        results.append((label, "SKIP", "缺少 %s" % script, 0.0))
        print("[%2d/%d] SKIP %s（文件缺失）" % (idx, len(TESTS), label), flush=True)
        continue

    timeout = TIMEOUT_OVERRIDES.get(script, DEFAULT_TIMEOUT)
    print("[%2d/%d] 运行 %s …" % (idx, len(TESTS), label), end="", flush=True)

    code, out, elapsed = run_one(script, timeout)

    if code is None:
        status, detail = "TIMEOUT", "超过 %ds 未结束（疑似死锁）" % timeout
    else:
        tail = [l for l in out.splitlines()
                if "passed" in l or "结果" in l or "PASS —" in l]
        status = "PASS" if code == 0 else "FAIL"
        detail = tail[-1].strip() if tail else "exit=%s" % code

    results.append((label, status, detail, elapsed))
    print("\r[%2d/%d] %-7s %-26s %6.1fs  %s"
          % (idx, len(TESTS), status, label, elapsed, detail), flush=True)

print("\n===== 测试总览 =====")
fails = 0
for label, status, detail, elapsed in results:
    if status in ("FAIL", "TIMEOUT"):
        fails += 1
    print("%-8s %-26s %6.1fs  %s" % (status, label, elapsed, detail))
print("\n%d/%d 通过（总耗时 %.1fs）"
      % (len(results) - fails, len(results), time.time() - total_started))
sys.exit(1 if fails else 0)
