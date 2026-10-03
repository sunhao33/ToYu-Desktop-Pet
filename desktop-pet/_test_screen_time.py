"""Regression test for the screen-time tracker (session recording, hourly axis, focus stats)."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ui.screen_time_tracker as stt  # noqa: E402

# 把数据落到临时目录，避免污染真实数据
TMP = tempfile.mkdtemp(prefix="toyu_screen_")
stt.DATA_DIR = TMP
stt.SCREEN_TIME_FILE = os.path.join(TMP, "screen_time.json")
stt.SESSION_FILE = os.path.join(TMP, "screen_sessions.json")

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


# ── 标题清洗 ────────────────────────────────────────────────
check("标题去浏览器后缀", stt.normalize_title("论文.pdf - Google Chrome") == "论文.pdf",
      stt.normalize_title("论文.pdf - Google Chrome"))
check("标题去首尾星号", stt.normalize_title("*未命名 - 记事本*") == "未命名",
      stt.normalize_title("*未命名 - 记事本*"))
check("长标题被截断", len(stt.sanitize_title("あ" * 500)) <= stt.TITLE_LIMIT)
check("疑似身份证标题被隐藏",
      stt.sanitize_title("个人信息 110101199003071234") == "(已隐藏敏感标题)",
      stt.sanitize_title("个人信息 110101199003071234"))
check("普通数字标题不误杀", stt.sanitize_title("第 3 章 习题 2026") == "第 3 章 习题 2026")

# ── 老数据迁移 ──────────────────────────────────────────────
today = datetime.now().strftime("%Y-%m-%d")
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
with open(stt.SCREEN_TIME_FILE, "w", encoding="utf-8") as f:
    json.dump({yesterday: {"chrome.exe": 600.0, "Code.exe": 300.0}}, f)
tr = stt.ScreenTimeTracker()
migrated = tr.get_sessions(yesterday)
check("老数据迁移成会话", len(migrated) == 2, "迁移 %d 条" % len(migrated))
check("迁移数据标记 inferred", all(s.get("inferred") for s in migrated))
check("迁移保留时长", abs(sum(s["secs"] for s in migrated) - 900.0) < 1.0,
      "合计 %.0f 秒" % sum(s["secs"] for s in migrated))

# ── 会话写入与按小时聚合 ────────────────────────────────────
sessions = [
    {"app": "Code.exe", "title": "main_window.py", "start": f"{today} 09:30:00", "secs": 1800.0},
    {"app": "Code.exe", "title": "pet_ai.py", "start": f"{today} 10:00:00", "secs": 300.0},
    {"app": "chrome.exe", "title": "论文.pdf", "start": f"{today} 23:30:00", "secs": 3600.0},  # 跨天
    {"app": "Weixin.exe", "title": "", "start": f"{today} 15:05:00", "secs": 120.0},
]
tr._sessions[today] = sessions

buckets = tr.get_hourly_data(today)
check("小时分布长度 24", len(buckets) == 24)
check("9 点有 1800 秒", abs(buckets[9] - 1800.0) < 1.0, "9点=%.0f" % buckets[9])
check("10 点有 300 秒", abs(buckets[10] - 300.0) < 1.0, "10点=%.0f" % buckets[10])
check("15 点有 120 秒", abs(buckets[15] - 120.0) < 1.0, "15点=%.0f" % buckets[15])
check("23 点只放 1800 秒（跨天部分不越界）", abs(buckets[23] - 1800.0) < 1.0, "23点=%.0f" % buckets[23])
check("小时总和不超过当天总时长", sum(buckets) <= sum(s["secs"] for s in sessions) + 1,
      "小时合计 %.0f / 会话合计 %.0f" % (sum(buckets), sum(s["secs"] for s in sessions)))

# ── 标题统计与专注指标 ──────────────────────────────────────
titles = dict(tr.get_title_stats(today))
check("标题统计合并同一文件", titles.get(("Code.exe", "main_window.py")) == 1800.0, str(titles))
focus = tr.get_focus_stats(today, min_session=300)
check("会话总数", focus["sessions"] == 4, str(focus))
check("有效会话数（≥5分钟）", focus["meaningful"] == 3, str(focus))
check("最长单次会话", abs(focus["longest_secs"] - 3600.0) < 1.0, str(focus))

# ── 全屏暂停策略 ────────────────────────────────────────────
check("默认不屏蔽任何全屏应用", tr._should_pause("chrome.exe") is False)
tr.set_fullscreen_pause_apps(["game.exe"])
check("名单外的全屏应用不暂停", tr._should_pause("chrome.exe") is False)
check("名单内但非全屏也不暂停（_is_fullscreen 为假）", tr._should_pause("game.exe") is False)

# ── 落盘与重载 ──────────────────────────────────────────────
tr._save_sessions()
tr2 = stt.ScreenTimeTracker()
reloaded = tr2.get_sessions(today)
check("会话落盘后可重载", len(reloaded) == 4, "重载 %d 条" % len(reloaded))
check("落盘保留标题", any(s.get("title") == "main.py".replace("main.py", "pet_ai.py") for s in reloaded))

# ── 过期清理 ────────────────────────────────────────────────
old_date = (datetime.now() - timedelta(days=stt.SESSION_RETENTION_DAYS + 5)).strftime("%Y-%m-%d")
tr2._sessions[old_date] = [{"app": "old.exe", "title": "", "start": f"{old_date} 10:00:00", "secs": 60.0}]
tr2._prune_sessions()
check("超期会话被清理", old_date not in tr2._sessions)
check("今日会话未被清理", today in tr2._sessions)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-34s %s" % (status, name, extra))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
