"""Regression test: pet image saving must be idempotent, atomic, and multi-instance safe."""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402
from image_processor.processor import process_and_save  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


TMP = tempfile.mkdtemp(prefix="toyu_proc_")
src = os.path.join(TMP, "mypet.png")

# 造一张带白底的图，确保处理流程真的会改动像素
img = Image.new("RGB", (120, 120), (255, 255, 255))
for x in range(40, 80):
    for y in range(30, 90):
        img.putpixel((x, y), (200, 120, 40))
img.save(src)

out_dir = os.path.join(TMP, "out")

# ── 1. 基本功能 ──────────────────────────────────────────────
path = process_and_save(src, out_dir, threshold=200, use_ai=False)
check("返回路径符合命名约定", os.path.basename(path) == "mypet_pet.png", os.path.basename(path))
check("输出文件已生成", os.path.exists(path))
first_bytes = open(path, "rb").read()
check("输出是有效 PNG", first_bytes[:8] == b"\x89PNG\r\n\x1a\n")

# ── 2. 幂等：内容不变则不重写 ────────────────────────────────
mtime_before = os.path.getmtime(path)
time.sleep(1.1)                       # 让 mtime 有可观测差异
path2 = process_and_save(src, out_dir, threshold=200, use_ai=False)
mtime_after = os.path.getmtime(path)
check("内容未变时不重复写盘", mtime_before == mtime_after,
      "mtime %s -> %s" % (mtime_before, mtime_after))
check("两次调用返回同一路径", path == path2)

# ── 3. 内容变化时必须真的写进去 ──────────────────────────────
img2 = Image.new("RGB", (120, 120), (255, 255, 255))
for x in range(10, 110):
    for y in range(10, 110):
        img2.putpixel((x, y), (30, 90, 200))
img2.save(src)
path3 = process_and_save(src, out_dir, threshold=200, use_ai=False)
second_bytes = open(path3, "rb").read()
check("源图变化后输出被更新", second_bytes != first_bytes)

# ── 4. 不留临时文件 ─────────────────────────────────────────
leftovers = [f for f in os.listdir(out_dir) if f.endswith(".tmp")]
check("没有残留临时文件", not leftovers, str(leftovers))

# ── 5. 模拟「另一个实例正读取该图」时仍能完成写入 ────────────
holder = Image.open(path3)            # 惰性读取，持有句柄
holder.load()
try:
    process_and_save(src, out_dir, threshold=200, use_ai=False)
    check("他方持有该图时仍可安全写入", True)
except Exception as exc:  # noqa: BLE001
    check("他方持有该图时仍可安全写入", False, "%s: %s" % (type(exc).__name__, exc))
finally:
    holder.close()

# ── 6. 并发写入不产生损坏文件 ────────────────────────────────
import threading  # noqa: E402

errors = []


def worker():
    try:
        process_and_save(src, out_dir, threshold=200, use_ai=False)
    except Exception as exc:  # noqa: BLE001
        errors.append("%s: %s" % (type(exc).__name__, exc))


threads = [threading.Thread(target=worker) for _ in range(6)]
for t in threads:
    t.start()
for t in threads:
    t.join()
check("6 线程并发处理无异常", not errors, str(errors[:3]))
final = open(path3, "rb").read()
check("并发后文件仍是完整 PNG", final[:8] == b"\x89PNG\r\n\x1a\n" and len(final) > 100,
      "%d bytes" % len(final))
leftovers = [f for f in os.listdir(out_dir) if f.endswith(".tmp")]
check("并发后无残留临时文件", not leftovers, str(leftovers))

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-32s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
