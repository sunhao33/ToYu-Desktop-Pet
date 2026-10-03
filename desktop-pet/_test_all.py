"""Run every regression test in this project. Usage: python _test_all.py

退出码 0 表示全部通过。
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = [
    ("桌面工具逻辑（剪贴板/护眼）", "_test_tools.py"),
    ("精灵可见区域计算", "_test_sprite_bounds.py"),
    ("崩溃防护", "_test_crash_guard.py"),
]

env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"

results = []
for label, script in TESTS:
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        results.append((label, "SKIP", "缺少 %s" % script))
        continue
    proc = subprocess.run([sys.executable, script], cwd=HERE, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace")
    tail = [l for l in (proc.stdout or "").splitlines() if "passed" in l or "结果" in l or "PASS —" in l]
    results.append((label, "PASS" if proc.returncode == 0 else "FAIL",
                    tail[-1].strip() if tail else "exit=%s" % proc.returncode))

print("\n===== 测试总览 =====")
fails = 0
for label, status, detail in results:
    fails += status == "FAIL"
    print("%-4s %-26s %s" % (status, label, detail))
print("\n%d/%d 通过" % (len(results) - fails, len(results)))
sys.exit(1 if fails else 0)
