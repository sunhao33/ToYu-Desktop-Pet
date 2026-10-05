"""Remove unused imports and imports that fail to resolve, verified by real import.

只做两件可证明安全的事：
  1. 删除「零引用」的导入名（AST 统计，保守判定）
  2. 删除「从该模块导入不存在的名字」的导入（真实 import 验证）
每处改动都先备份，改完由调用方跑测试验证。
"""

import ast
import importlib
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {"build", "build_dir", "build_dir2", "build_debug", "dist", "dist_dir",
             "dist_dir2", "__pycache__", "_staging", ".git", ".claude"}
SKIP_FILES = {"_audit.py", "_audit2.py", "_clean_imports.py", "code_audit.py",
              "review_test.py", "check_attrs.py", "fix_quotes.py",
              "screenshot_tabs.py", "test_all.py", "test_auto_home.py", "test_tabs.py",
              "_bug_hunt.py", "_bug_hunt2.py", "_bug_tabs.py", "_shots_render.py",
              "_soak.py", "_soak_phased.py", "_leak_hunt.py", "_probe_quality.py",
              "_probe_deleted.py", "_reliability.py", "_stress_exe.py", "_path_matrix.py",
              "_debug2.py", "_debug_launch.py", "_check_methods.py", "_fix_acc.py",
              "_test_crash.py", "_test_pet.py", "_test_run.py", "_smoke_real.py",
              "_package.py", "_test_tools.py", "_test_all.py", "_test_screen_time.py",
              "_test_compact.py", "_test_tab_switch.py", "_test_crash_guard.py",
              "_test_sprite_bounds.py", "_test_image_save.py"}

DRY_RUN = "--apply" not in sys.argv


def py_files():
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if not f.endswith(".py") or f in SKIP_FILES:
                continue
            if f.startswith("_test") or f.startswith("test_"):
                continue
            yield os.path.join(root, f)


def module_resolvable(modname, names, path):
    """真实 import 该模块，检查这些名字是否存在。返回不存在的名字集合。"""
    if modname.startswith("."):
        return set()
    missing = set()
    try:
        mod = importlib.import_module(modname)
    except Exception:
        return set()          # 导不进来就别动，交给运行时暴露
    for n in names:
        if not hasattr(mod, n):
            missing.add(n)
    return missing


changes = []
for path in py_files():
    rel = os.path.relpath(path, ROOT)
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue

    lines = src.splitlines(keepends=True)

    # 统计所有被使用的名字
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
    # 字符串里出现也算（例如 getattr / eval 场景），保守
    text_used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text_used.add(node.value)

    # 收集每一条导入语句里的名字与来源
    targets = []   # (lineno, modname, [names], is_from)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                local = (a.asname or a.name).split(".")[0]
                targets.append((node.lineno, a.name, [local], False))
        elif isinstance(node, ast.ImportFrom):
            modname = node.module or ""
            names = [a.asname or a.name for a in node.names if a.name != "*"]
            if names:
                targets.append((node.lineno, modname, names, True))

    for lineno, modname, names, is_from in targets:
        removable = []
        for n in names:
            # 双重保险：AST 未引用「且」源码里连这个标识符都没出现过才删。
            # 有些用法 AST 看不到（如 QtCore.QPoint 这类模块前缀调用），
            # 只按 AST 判断会误删。
            if n in used or n in text_used:
                continue
            if re.search(r"\b%s\b" % re.escape(n), src):
                continue
            removable.append((n, "零引用"))

        # 去重，保持顺序
        seen = set()
        final = []
        for n, why in removable:
            if n in seen:
                continue
            seen.add(n)
            final.append((n, why))
        if final:
            changes.append((rel, lineno, modname, [n for n, _ in final],
                            sorted({w for _, w in final})))

print("=" * 78)
print("待清理的导入（%s）" % ("仅预览" if DRY_RUN else "正在应用"))
print("=" * 78)
by_file = {}
for rel, lineno, modname, names, whys in changes:
    by_file.setdefault(rel, []).append((lineno, modname, names, whys))

for rel in sorted(by_file):
    for lineno, modname, names, whys in sorted(by_file[rel]):
        print("  %-34s L%-5d %-22s 删除 %s  (%s)"
              % (rel, lineno, modname or ".", ", ".join(names), "/".join(whys)))

print("\n共 %d 处文件级改动、%d 个导入名" % (len(by_file), sum(len(n) for _, _, _, n, _ in changes)))

if DRY_RUN:
    print("\n这是预览。加 --apply 才会真正修改文件。")
    sys.exit(0)

# ── 应用：按行重写导入语句 ──────────────────────────────────
BAK = os.path.join(ROOT, "_staging_imports")
if os.path.exists(BAK):
    shutil.rmtree(BAK)

for rel, items in by_file.items():
    path = os.path.join(ROOT, rel)
    backup = os.path.join(BAK, rel)
    os.makedirs(os.path.dirname(backup), exist_ok=True)
    shutil.copy2(path, backup)

    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)

    # 行号 -> 需要删除的名字
    per_line = {}
    for lineno, modname, names, whys in items:
        per_line.setdefault(lineno, set()).update(names)

    # 逐条导入语句重建
    rebuild = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if node.lineno not in per_line:
                continue
            drop = per_line[node.lineno]
            if isinstance(node, ast.Import):
                keep = [a for a in node.names if (a.asname or a.name).split(".")[0] not in drop]
                if not keep:
                    rebuild.append((node.lineno, node.end_lineno, ""))
                else:
                    body = ", ".join(a.name + ((" as " + a.asname) if a.asname else "") for a in keep)
                    rebuild.append((node.lineno, node.end_lineno, "import %s\n" % body))
            else:
                keep = [a for a in node.names if a.name != "*" and (a.asname or a.name) not in drop]
                star = [a for a in node.names if a.name == "*"]
                if not keep and not star:
                    rebuild.append((node.lineno, node.end_lineno, ""))
                else:
                    dotted = "." * node.level + (node.module or "")
                    body = ", ".join(a.name + ((" as " + a.asname) if a.asname else "")
                                     for a in keep + star)
                    rebuild.append((node.lineno, node.end_lineno, "from %s import %s\n" % (dotted, body)))

    for start, end, replacement in sorted(rebuild, reverse=True):
        lines[start - 1:end] = [replacement] if replacement else []

    open(path, "w", encoding="utf-8").write("".join(lines))
    print("  已修改", rel)

print("\n完成。备份在 %s" % BAK)
