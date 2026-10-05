"""Audit part 2: unused imports, dead code, suspicious logic patterns."""

import ast
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {"build", "build_dir", "build_dir2", "build_debug", "dist", "dist_dir",
             "dist_dir2", "__pycache__", "_staging", ".git", ".claude"}

unused = []
dead = []
logic = []


def py_files():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".py") and not f.startswith("_test") and not f.startswith("test_"):
                yield os.path.join(root, f)


for path in py_files():
    src = open(path, encoding="utf-8").read()
    rel = os.path.relpath(path, ROOT)
    if rel.startswith("_") and os.sep not in rel:
        continue
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue

    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                name = (a.asname or a.name).split(".")[0]
                imported[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    continue
                imported[a.asname or a.name] = node.lineno

    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            cur = node
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                used.add(cur.id)
    for name, line in imported.items():
        if name not in used:
            unused.append((rel, line, name))

    # 可能永不成立的条件
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            left = node.left
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, ast.Is) and isinstance(comp, ast.Constant) and comp.value is None:
                    if isinstance(left, ast.Call):
                        unused.append((rel, node.lineno, "与 None 比较的调用结果"))

print("=" * 78)
print("审计 2：未使用导入 / 可疑逻辑")
print("=" * 78)

grouped = defaultdict(list)
for rel, line, name in unused:
    grouped[rel].append((line, name))

print("\n--- 未使用的导入（%d 处）---" % len(unused))
for rel in sorted(grouped):
    items = grouped[rel]
    print("  %s: %s" % (rel, ", ".join("%s(L%d)" % (n, l) for l, n in items[:12])))

# ── 手工模式匹配：可疑逻辑 ──────────────────────────────────
PATTERNS = [
    (r"if\s+self\._pet\s*:", "对 Qt 对象做真值判断（窗口关闭后可能仍为真）"),
    (r"self\._pet\.\w+\(\).*#.*TODO|TODO|FIXME|XXX", "遗留标记"),
    (r"return\s+\[\]\s*$", "可能过早返回空值"),
    (r"except\s+Exception\s*:\s*\n\s*return\s+None", "异常转 None（调用方可能不检查）"),
    (r"\.text\(\)\.replace\(\"%\", \"\"\)", "解析百分比文本（易碎）"),
]

print("\n--- 可疑逻辑模式 ---")
for path in py_files():
    rel = os.path.relpath(path, ROOT)
    lines = open(path, encoding="utf-8").read().splitlines()
    for i, line in enumerate(lines, 1):
        for pat, desc in PATTERNS:
            if re.search(pat, line):
                logic.append((rel, i, desc, line.strip()[:90]))

grouped2 = defaultdict(list)
for rel, i, desc, text in logic:
    grouped2[(rel, desc)].append((i, text))
for (rel, desc), items in sorted(grouped2.items()):
    print("  [%s] %s (%d 处)" % (desc, rel, len(items)))
    for i, text in items[:3]:
        print("      L%-5d %s" % (i, text))
    if len(items) > 3:
        print("      ... 其余 %d 处" % (len(items) - 3))
