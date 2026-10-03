"""Session compaction + auto-start regression checks (temporary probe)."""

import json
import os
import sys
import tempfile
from datetime import datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ui.screen_time_tracker as stt  # noqa: E402

TMP = tempfile.mkdtemp(prefix="toyu_compact_")
stt.DATA_DIR = TMP
stt.SCREEN_TIME_FILE = os.path.join(TMP, "screen_time.json")
stt.SESSION_FILE = os.path.join(TMP, "screen_sessions.json")

results = []
def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))

today = datetime.now().strftime("%Y-%m-%d")

print("=== 1. 碎会话合并 ===")
raw = []
for i in range(200):  # 模拟切标签：同一页面被切成 200 段 2 秒碎片
    raw.append({"app": "chrome.exe", "title": "论文.pdf",
                "start": "%s 10:%02d:%02d" % (today, i // 60, i % 60), "secs": 2.0})
raw.append({"app": "chrome.exe", "title": "B站", "start": "%s 11:00:00" % today, "secs": 600.0})
raw.append({"app": "Code.exe", "title": "a.py", "start": "%s 12:00:00" % today, "secs": 0.5})  # 1 秒内碎片
compacted = stt.ScreenTimeTracker._compact(raw)
check("碎片被合并（200 段 → 1 段 + 长会话）", len(compacted) == 2, "合并后 %d 段" % len(compacted))
check("合并后秒数守恒", abs(sum(s["secs"] for s in compacted) - (200 * 2 + 600)) < 1.0,
      "合计 %.0f 秒（期望 1000）" % sum(s["secs"] for s in compacted))
check("子秒碎片被丢弃", all(s["secs"] > 1 for s in compacted))
check("不同标题不被合并", any(s["title"] == "B站" for s in compacted))

print("\n=== 2. 长会话不被误合并 ===")
keep = [
    {"app": "Code.exe", "title": "x.py", "start": "%s 09:00:00" % today, "secs": 1800.0},
    {"app": "Code.exe", "title": "x.py", "start": "%s 09:30:00" % today, "secs": 1800.0},
]
check("两段 30 分钟同一文件保持独立", len(stt.ScreenTimeTracker._compact(keep)) == 2)

print("\n=== 3. 落盘体积可控 ===")
tr = stt.ScreenTimeTracker()
tr._sessions[today] = raw
tr._save_sessions()
size = os.path.getsize(stt.SESSION_FILE)
with open(stt.SESSION_FILE, encoding="utf-8") as f:
    saved = json.load(f)[today]
check("落盘后只剩合并结果", len(saved) == 2, "文件内 %d 段" % len(saved))
check("文件体积 < 2KB", size < 2048, "%d bytes" % size)

print("\n=== 4. 落盘后统计仍正确 ===")
buckets = tr.get_hourly_data(today)
check("10 点碎片合并后仍有记录", buckets[10] > 0, "10点=%.0f" % buckets[10])
check("11 点长会话记录", abs(buckets[11] - 600.0) < 1.0, "11点=%.0f" % buckets[11])

print("\n=== 5. 老用户启动自动拉起宠物 ===")
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
from ui.main_window import MainWindow
mw = MainWindow()
mw._first_launch = None  # 清掉构造期的值，只验证 _restore_state 的行为
mw._restore_state()
check("有历史宠物时也会自动启动", mw._first_launch is True,
      "_first_launch=%s（应为 True 才会自动拉起）" % mw._first_launch)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-34s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
