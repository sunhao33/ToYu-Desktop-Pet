"""回归测试：每日目标 + 进度环。

覆盖：
  * 学习时长判定：学习类应用算、娱乐不算、浏览器看标题、IDE 里看视频不算
  * 有效时长门槛：单次连续不足 3 分钟的不计入（滤掉误点开）
  * 目标值来源优先级：手动 > 记忆 > 未设（不硬塞默认值）
  * 进度计算：比例、是否达成、还差多少
  * 达成庆祝每天只触发一次
  * 进度环组件：ratio 归一化、文字、达成换色
  * 三处界面接线：主页 / 心流窗口 / 数据面板
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.goal import (  # noqa: E402
    MIN_SESSION_SECONDS, DailyGoalTracker, is_study_app,
    study_seconds_from_sessions,
)
from ui.widgets.progress_ring import ProgressRing  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


# ══════════════════════════════════════════════════════════
# 1. 学习判定
# ══════════════════════════════════════════════════════════
cases = [
    ("Code.exe", "main_window.py", True, "IDE 写代码"),
    ("pycharm64.exe", "test.py", True, "PyCharm"),
    ("Cursor.exe", "app.ts", True, "Cursor"),
    ("Typora.exe", "笔记.md", True, "笔记"),
    ("Acrobat.exe", "教材.pdf", True, "PDF"),
    ("matlab.exe", "sim.m", True, "MATLAB"),
    ("DeepSeek Harness.exe", "", True, "AI 开发工具"),
    ("ChatGPT.exe", "", True, "AI 助手"),
    ("chrome.exe", "机器学习 - 搜索", True, "浏览器查资料"),
    ("msedge.exe", "论文.pdf - 个人", True, "浏览器看论文"),
    ("msedge.exe", "GitHub - 项目", True, "浏览器看代码"),
    ("firefox.exe", "知乎 - 算法题", True, "浏览器看技术内容"),
    ("chrome.exe", "淘宝 - 购物", False, "浏览器购物"),
    ("chrome.exe", "新建标签页", False, "浏览器空白页"),
    ("哔哩哔哩.exe", "", False, "B站"),
    ("Code.exe", "哔哩哔哩 - 看视频", False, "IDE 里看视频（标题拦下）"),
    ("msedge.exe", "哔哩哔哩 - 视频", False, "浏览器看B站"),
    ("Weixin.exe", "", False, "微信"),
    ("QQMusic.exe", "", False, "音乐"),
    ("Steam.exe", "", False, "游戏平台"),
    ("ToYu.exe", "ToYu — 桌面土豆宠物", False, "本程序"),
    ("", "", False, "空记录"),
]
bad = []
for app_name, title, expect, note in cases:
    got = is_study_app(app_name, title)
    if got != expect:
        bad.append("%s/%s 期望%s 得到%s" % (app_name, title, expect, got))
check("学习判定全部正确（%d 例）" % len(cases), not bad, "; ".join(bad[:3]))

# ══════════════════════════════════════════════════════════
# 2. 有效时长计算
# ══════════════════════════════════════════════════════════
sessions = [
    {"app": "Code.exe", "title": "main.py", "secs": 1800},      # 计入 30 分
    {"app": "Code.exe", "title": "x.py", "secs": 60},           # 太短，不计
    {"app": "哔哩哔哩.exe", "title": "", "secs": 3600},          # 娱乐，不计
    {"app": "chrome.exe", "title": "论文检索", "secs": 600},     # 计入 10 分
    {"app": "Weixin.exe", "title": "", "secs": 900},            # 不计
    {"app": "Typora.exe", "title": "笔记", "secs": MIN_SESSION_SECONDS},  # 刚好够
]
total = study_seconds_from_sessions(sessions)
check("有效时长只算学习类且够长的",
      abs(total - (1800 + 600 + MIN_SESSION_SECONDS)) < 1,
      "得到 %.0f 秒（期望 %d）" % (total, 1800 + 600 + MIN_SESSION_SECONDS))
check("空会话返回 0", study_seconds_from_sessions([]) == 0)
check("坏数据不崩",
      study_seconds_from_sessions([None, "x", {"app": "Code.exe"}]) == 0)
check("可自定义门槛",
      study_seconds_from_sessions(sessions, min_session=10) > total)


# ══════════════════════════════════════════════════════════
# 3. 目标追踪器
# ══════════════════════════════════════════════════════════
class FakeSettings:
    """最小可用的设置替身（只用 _settings 的 value/setValue/remove）。"""

    class _Inner:
        def __init__(self):
            self.store = {}

        def value(self, key, default=None):
            return self.store.get(key, default)

        def setValue(self, key, value):
            self.store[key] = value

        def remove(self, key):
            self.store.pop(key, None)

    def __init__(self):
        self._settings = FakeSettings._Inner()


class FakeTracker:
    def __init__(self, sessions=None):
        self.sessions = sessions or []

    def get_sessions(self, date_str=None):
        return self.sessions


class FakeMemory:
    def __init__(self, value=None):
        self._value = value

    def get(self, slot_id):
        if self._value is None:
            return None
        return type("R", (), {"value": self._value})()


st = FakeSettings()
tr = FakeTracker([{"app": "Code.exe", "title": "a.py", "secs": 3600}])
gt = DailyGoalTracker(settings=st, tracker=tr, memory_store=None)

check("未设目标时返回 None（不硬塞默认值）", gt.goal_minutes() is None)
check("未设目标时来源为 none", gt.goal_source() == "none")
info = gt.progress()
check("未设目标时 has_goal 为假", info["has_goal"] is False)
check("未设目标时比例仍为 0", info["ratio"] == 0.0)

gt.set_goal_minutes(120)
check("设置目标后可读回", gt.goal_minutes() == 120)
check("手动设置时来源为 manual", gt.goal_source() == "manual")

info = gt.progress()
check("今天学习时长被正确计算", info["study_minutes"] == 60,
      "%d 分钟" % info["study_minutes"])
check("进度比例正确", abs(info["ratio"] - 0.5) < 0.01, "%.3f" % info["ratio"])
check("未达成时 reached 为假", info["reached"] is False)
check("还差时长正确", info["remaining_minutes"] == 60,
      "%d" % info["remaining_minutes"])

# 达成
tr.sessions = [{"app": "Code.exe", "title": "a.py", "secs": 7200}]
info = gt.progress()
check("学习满目标时 reached 为真", info["reached"] is True)
check("达成后比例封顶为 1", info["ratio"] == 1.0, "%.3f" % info["ratio"])
check("达成后还差为 0", info["remaining_minutes"] == 0)

# 庆祝每天只一次
check("首次达成应庆祝", gt.should_celebrate() is True)
check("同一天不重复庆祝", gt.should_celebrate() is False)

# 未达成不庆祝
st2 = FakeSettings()
gt2 = DailyGoalTracker(settings=st2, tracker=FakeTracker([]), memory_store=None)
gt2.set_goal_minutes(60)
check("未达成不庆祝", gt2.should_celebrate() is False)

# 清除目标
gt.set_goal_minutes(0)
check("清除目标后返回 None", gt.goal_minutes() is None)
check("清除后可再次设置", (gt.set_goal_minutes(45), gt.goal_minutes() == 45)[1])

# 记忆来源
st3 = FakeSettings()
gt3 = DailyGoalTracker(settings=st3, tracker=FakeTracker([]),
                       memory_store=FakeMemory(90))
check("从记忆读目标", gt3.goal_minutes() == 90)
check("记忆来源标记正确", gt3.goal_source() == "memory")
gt3.set_goal_minutes(30)
check("手动设置覆盖记忆值", gt3.goal_minutes() == 30)
check("覆盖后来源变为 manual", gt3.goal_source() == "manual")

# 记忆值异常不崩
gt4 = DailyGoalTracker(settings=FakeSettings(), tracker=FakeTracker([]),
                       memory_store=FakeMemory("不是数字"))
check("记忆值非法时忽略", gt4.goal_minutes() is None)

# 文案
gt.set_goal_minutes(120)
tr.sessions = [{"app": "Code.exe", "title": "a.py", "secs": 1800}]
check("未达成文案含还差", "还差" in gt.text(), gt.text())
tr.sessions = [{"app": "Code.exe", "title": "a.py", "secs": 7200}]
check("达成文案含已达成", "已达成" in gt.text(), gt.text())

# ══════════════════════════════════════════════════════════
# 4. 进度环组件
# ══════════════════════════════════════════════════════════
ring = ProgressRing(size=64, thickness=6)
check("环尺寸固定", ring.width() == 64 and ring.height() == 64)
ring.set_state(0.5, "50%")
check("ratio 被正确保存", ring.ratio() == 0.5)
ring.set_state(2.0, "超了")
check("ratio 超过 1 被封顶", ring.ratio() == 1.0)
ring.set_state(-1, "负")
check("ratio 负数被归零", ring.ratio() == 0.0)
ring.set_state("abc", "非法")   # type: ignore
check("非法 ratio 不崩", ring.ratio() == 0.0)
ring.set_state(1.0, "100%", full_color="#4CAF50")
check("可设置达成色", ring._full_color is not None)
ring.set_state(0.3, "30%", dim=True)
check("可设置调淡状态", ring._dim is True)
# 绘制不崩（离屏渲染一次）
ring.resize(64, 64)
ring.grab()
check("离屏绘制不崩", True)

# ══════════════════════════════════════════════════════════
# 5. 界面接线
# ══════════════════════════════════════════════════════════
from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()
mw.show()
pump(600)
mw._on_start_pet()
pump(800)

check("主页有目标环", getattr(mw, "_goal_ring", None) is not None)
check("数据面板有目标环", getattr(mw, "_data_goal_ring", None) is not None)
check("有目标文案标签", getattr(mw, "_goal_label", None) is not None)
check("有 7 天历史标签", getattr(mw, "_goal_history_label", None) is not None)
check("追踪器可创建", mw._ensure_goal_tracker() is not None)

mw._refresh_goal()
pump(200)
check("未设目标时环显示未设",
      "未设" in mw._goal_ring._text or "%" in mw._goal_ring._text,
      mw._goal_ring._text)
check("未设目标时提示可设置",
      "未设目标" in mw._goal_label.text() or "未设" in mw._goal_label.text(),
      mw._goal_label.text())

# 设置目标后三处都更新
tracker = mw._ensure_goal_tracker()
tracker.set_goal_minutes(60)
mw._refresh_goal()
pump(300)
check("设置后主页环显示百分比", "%" in mw._goal_ring._text, mw._goal_ring._text)
check("设置后数据面板环同步", "%" in mw._data_goal_ring._text,
      mw._data_goal_ring._text)
check("设置后文案显示目标",
      "60" in mw._goal_label.text(), mw._goal_label.text())
check("历史标签显示 7 天",
      "近 7 天" in mw._goal_history_label.text(), mw._goal_history_label.text())

# 心流窗口
mw.enter_flow_mode()
pump(900)
fw = mw._flow_window
check("心流窗口有目标环", hasattr(fw, "_goal_ring"))
if hasattr(fw, "_goal_ring"):
    check("心流窗口环显示百分比", "%" in fw._goal_ring._text, fw._goal_ring._text)
    check("心流窗口文本显示目标",
          "60" in fw._goal_text.text(), fw._goal_text.text().replace("\n", " "))
mw.exit_flow_mode()
pump(400)

# 清理：不留目标设置给用户
tracker.set_goal_minutes(0)
mw._refresh_goal()
pump(150)
check("清理后回到未设目标", tracker.goal_minutes() is None)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-40s %s" % (status, name, extra[:48]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
