"""Static audit: scan the project for known bug patterns and code smells.

只报告可验证的模式，不猜测。输出按严重度分组。
"""

import ast
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {"build", "build_dir", "build_dir2", "build_debug", "dist", "dist_dir",
             "dist_dir2", "__pycache__", "_staging", ".git", ".claude"}
SKIP_FILES = {"_package.py", "_soak.py", "_soak_phased.py", "_leak_hunt.py",
              "_bug_hunt.py", "_bug_hunt2.py", "_bug_tabs.py", "_shots_render.py",
              "_reliability.py", "_stress_exe.py", "_path_matrix.py"}

findings = defaultdict(list)


def add(severity, category, path, line, detail):
    findings[severity].append((category, os.path.relpath(path, ROOT), line, detail))


def py_files():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            if f in SKIP_FILES or f.startswith("_test") or f.startswith("test_"):
                continue
            yield os.path.join(root, f)


# ── 1. 语法树级别检查 ────────────────────────────────────────
for path in py_files():
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src, filename=path)
    except SyntaxError as exc:
        add("高", "语法错误", path, exc.lineno or 0, str(exc))
        continue

    for node in ast.walk(tree):
        # 可变默认参数
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d]
            for d in defaults:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    add("高", "可变默认参数", path, d.lineno,
                        "%s() 的默认值是可变对象，会在多次调用间共享" % node.name)
        # 裸 except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            add("中", "裸 except", path, node.lineno, "捕获所有异常包括 KeyboardInterrupt/SystemExit")
        # except Exception: pass（吞异常）
        if isinstance(node, ast.ExceptHandler) and not node.body:
            add("中", "空 except", path, node.lineno, "异常被静默吞掉")
        if isinstance(node, ast.ExceptHandler):
            body = node.body
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                add("中", "except: pass", path, node.lineno,
                    "异常被静默忽略（第 %d 行）" % node.lineno)
        # QPoint/QRect 上做整除
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.FloorDiv):
            if isinstance(node.left, ast.Attribute) and node.left.attr in ("width", "height", "x", "y"):
                add("低", "几何整除", path, node.lineno,
                    "对几何属性做整除，负数坐标时会向负无穷取整")

print("=" * 78)
print("静态审计结果")
print("=" * 78)

order = ["高", "中", "低"]
total = 0
for sev in order:
    items = findings.get(sev, [])
    if not items:
        continue
    print("\n--- 严重度 %s（%d 项）---" % (sev, len(items)))
    grouped = defaultdict(list)
    for cat, path, line, detail in items:
        grouped[(cat, path)].append((line, detail))
    for (cat, path), entries in sorted(grouped.items()):
        print("  [%s] %s  (%d 处)" % (cat, path, len(entries)))
        for line, detail in entries[:4]:
            print("      L%-5d %s" % (line, detail[:100]))
        if len(entries) > 4:
            print("      ... 其余 %d 处" % (len(entries) - 4))
    total += len(items)

print("\n合计 %d 项" % total)
