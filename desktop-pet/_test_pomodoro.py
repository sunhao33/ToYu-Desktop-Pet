"""回归测试：番茄轮次 + 今日专注时间轴。

覆盖：
  * 专注段记录：时长门槛、跨零点归属、持久化、60 天裁剪
  * 轮次统计：完成轮数、专注总时长、休息总时长
  * 状态机：专注自然结束 → 自动进休息；休息结束 → 提示但不自动开始
  * 提前停止也要记账（不做的话那段专注白费）
  * 时间轴：数据渲染、空状态提示、悬停提示文字

注意：测试全程用**独立的临时日志文件**，不碰用户的 focus_log.json。
"""

import os
import sys
import tempfile
import time
from datetime import date, datetime, timedelta

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.focus_log import (  # noqa: E402
    KIND_BREAK, KIND_FOCUS, FocusLog,
)

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def fresh_log():
    """独立临时文件的日志，测试之间互不影响。"""
    path = os.path.join(tempfile.mkdtemp(prefix="toyu_flog_"), "focus_log.json")
    return FocusLog(path), path


# ══════════════════════════════════════════════════════════
# 1. 记录
# ══════════════════════════════════════════════════════════
log, log_path = fresh_log()
check("新日志为空", log.rounds_today() == 0 and log.segments() == [])

check("不足 1 分钟的不记录", log.add(KIND_FOCUS, 59) == {}, "59 秒不该入账")
check("刚好 1 分钟记录", bool(log.add(KIND_FOCUS, 60)), "60 秒应入账")
check("入账后轮次为 1", log.rounds_today() == 1, str(log.rounds_today()))
check("None 时长不崩", log.add(KIND_FOCUS, None) == {})

log.clear_today()
check("清空今日生效", log.rounds_today() == 0)

base = datetime.now() - timedelta(hours=3)
log.add(KIND_FOCUS, 45 * 60, task="写文档", started=base)
log.add(KIND_BREAK, 5 * 60, started=base + timedelta(minutes=45))
log.add(KIND_FOCUS, 25 * 60, task="复习", started=base + timedelta(minutes=50))

check("轮次只数专注段", log.rounds_today() == 2, str(log.rounds_today()))
check("专注总时长正确", log.focus_minutes_today() == 70,
      str(log.focus_minutes_today()))
summary = log.summary()
check("汇总的休息时长正确", summary["break_minutes"] == 5,
      str(summary["break_minutes"]))
check("汇总段数正确", len(summary["segments"]) == 3,
      str(len(summary["segments"])))
check("记录里带任务名",
      any(s.get("task") == "写文档" for s in summary["segments"]))
check("记录里带开始结束时刻",
      all(s.get("start") and s.get("end") for s in summary["segments"]))
check("段按开始时间排序",
      [s["start_min"] for s in summary["segments"]]
      == sorted(s["start_min"] for s in summary["segments"]))

# 跨零点归到开始那天
yesterday_late = datetime.now().replace(hour=23, minute=50) - timedelta(days=1)
log.add(KIND_FOCUS, 20 * 60, started=yesterday_late)
yday = (date.today() - timedelta(days=1)).isoformat()
check("跨零点算在开始那天", len(log.segments(yday)) == 1,
      "%d 段" % len(log.segments(yday)))
check("跨零点的段不计入今日轮次", log.rounds_today() == 2,
      str(log.rounds_today()))

# 持久化
reloaded = FocusLog(log_path)
check("重新读取数据一致", reloaded.rounds_today() == log.rounds_today(),
      "%d vs %d" % (reloaded.rounds_today(), log.rounds_today()))

# 坏文件不崩
broken = FocusLog(log_path)
with open(log_path, "w", encoding="utf-8") as fh:
    fh.write("{ 这不是合法 json")
check("文件损坏时返回空而不崩", broken.rounds_today() == 0)
check("损坏文件后仍能写入", bool(broken.add(KIND_FOCUS, 600)))

# ══════════════════════════════════════════════════════════
# 2. 时间轴组件
# ══════════════════════════════════════════════════════════
from ui.widgets.focus_timeline import FocusTimeline  # noqa: E402

PALETTE = {
    "accent": "#C49A3C", "border": "#E8D5C0", "text": "#2C1810",
    "text2": "#8A7A66", "success": "#7FB069", "danger": "#E05A4F",
}
timeline = FocusTimeline(lambda k: PALETTE.get(k, "#888888"))
check("时间轴有最小高度", timeline.minimumHeight() >= 40,
      str(timeline.minimumHeight()))

timeline.set_records([])
check("空数据不崩", timeline._records == [])
timeline.set_records(log.summary()["segments"])
check("能接收记录", len(timeline._records) == 3, str(len(timeline._records)))

timeline.resize(420, 48)
timeline.grab()
check("离屏绘制不崩", True)

# 悬停提示：落在第一段内
seg = sorted(log.summary()["segments"], key=lambda s: s["start_min"])[0]
timeline.set_records([seg])
from PyQt6.QtCore import QPointF  # noqa: E402
from PyQt6.QtGui import QMouseEvent  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402

x_inside = timeline.width() * (seg["start_min"] + 1) / 1440.0
ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(x_inside, 10),
                 Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                 Qt.KeyboardModifier.NoModifier)
timeline.mouseMoveEvent(ev)
tip = timeline.toolTip()
check("悬停显示该段明细", seg["start"] in tip and "专注" in tip, tip)
check("悬停提示含时长", "%d 分钟" % seg["minutes"] in tip, tip)

# 悬停在空白处 → 给整体概览
ev2 = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(2, 10),
                  Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                  Qt.KeyboardModifier.NoModifier)
timeline.set_records([])
timeline.mouseMoveEvent(ev2)
check("无记录时提示开始专注", "还没有专注记录" in timeline.toolTip(),
      timeline.toolTip())

# ══════════════════════════════════════════════════════════
# 3. 界面接线与状态机（用临时日志，绝不写用户数据）
# ══════════════════════════════════════════════════════════
from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()
mw.show()
pump(700)
mw._on_start_pet()
pump(600)
mw.enter_flow_mode()
pump(1000)
fw = mw._flow_window

# 换成临时日志，避免污染真实数据
fw._focus_log, _tmp_log_path = fresh_log()
fw._focus_log.clear_today()

check("心流窗口有轮次标签", getattr(fw, "_rounds_label", None) is not None)
check("心流窗口有时间轴", getattr(fw, "_timeline", None) is not None)
check("心流窗口有休息按钮", getattr(fw, "_break_btn", None) is not None)
check("有本轮时长标签", getattr(fw, "_round_len_label", None) is not None)
check("状态行默认隐藏（不重复计时面板的『准备开始』）",
      not fw._state_label.isVisible() or fw._state_label.text() == "",
      repr(fw._state_label.text()))
check("状态行有统一设置入口", callable(getattr(fw, "_set_state", None)))
check("休息按钮文案无 emoji（避免渲染成方块）",
      "分钟" in fw._break_btn.text() and "☕" not in fw._break_btn.text(),
      fw._break_btn.text())
check("初始轮次为第 1 轮", "1" in fw._rounds_label.text(), fw._rounds_label.text())
check("初始今日轮次为 0", "0" in fw._rounds_total.text(), fw._rounds_total.text())
check("右栏有专注轮次一行", "rounds" in getattr(fw, "_stat_rows", {}),
      str(list(getattr(fw, "_stat_rows", {}))))

# ── 计时器预设时长（曾经 60/90 分钟被截成 59 分钟）──
# 原因：_set_preset 只设分钟框（上限 59），从不使用小时框。
# 注意 _set_preset 只更新三个 spin 框与显示，_remaining_seconds 是
# 点"开始"时才设置的 —— 所以这里断言的应该是 spin 框的换算结果。
timer_probe = mw._timer_widget


def probe_total():
    return (timer_probe._hour_spin.value() * 3600
            + timer_probe._min_spin.value() * 60
            + timer_probe._sec_spin.value())


for minutes in (25, 45, 60, 90):
    timer_probe._set_preset(minutes)
    check("%d 分钟预设换算正确" % minutes, probe_total() == minutes * 60,
          "实际 %d 秒（应为 %d）" % (probe_total(), minutes * 60))
    check("%d 分钟显示正确" % minutes,
          timer_probe._time_display.text()
          == "%02d:%02d:00" % (minutes // 60, minutes % 60),
          timer_probe._time_display.text())

timer_probe._set_preset(90)
check("90 分钟用小时框承载",
      timer_probe._hour_spin.value() == 1 and timer_probe._min_spin.value() == 30,
      "%d 时 %d 分" % (timer_probe._hour_spin.value(),
                       timer_probe._min_spin.value()))
timer_probe._set_preset(60)
check("60 分钟用小时框承载",
      timer_probe._hour_spin.value() == 1 and timer_probe._min_spin.value() == 0,
      "%d 时 %d 分" % (timer_probe._hour_spin.value(),
                       timer_probe._min_spin.value()))
timer_probe._set_preset(25)
check("不足 1 小时不用小时框",
      timer_probe._hour_spin.value() == 0 and timer_probe._min_spin.value() == 25,
      "%d 时 %d 分" % (timer_probe._hour_spin.value(),
                       timer_probe._min_spin.value()))

# 真跑一次，确认 _on_start 用的是修正后的值
timer_probe._set_preset(60)
timer_probe._on_start()
pump(1200)
check("60 分钟开始后剩余接近 1 小时",
      timer_probe._remaining_seconds >= 3595,
      "%d 秒" % timer_probe._remaining_seconds)
timer_probe._on_reset()
pump(200)

# 状态行：设置文本时显示，清空时隐藏
fw._set_state("测试状态")
check("设置状态后显示", fw._state_label.isVisible()
      and fw._state_label.text() == "测试状态")
fw._set_state("")
check("清空状态后隐藏", not fw._state_label.isVisible())

# 开始专注后应标明本轮时长（避免"选 25 却看到 24 分"的误解）
fw.start_focus(25)
pump(400)
check("开始专注后标明本轮时长",
      "25" in fw._round_len_label.text(), fw._round_len_label.text())
check("开始专注后状态行有内容", bool(fw._state_label.text()),
      repr(fw._state_label.text()))
mw.stop_focus_session()
pump(300)

fw.refresh_timeline()
fw._refresh_rounds()
pump(200)
check("空日志时时间轴为空", len(fw._timeline._records) == 0)

# 记录一段并刷新
fw._focus_started_at = datetime.now() - timedelta(minutes=30)
fw._focus_task = "测试专注"
fw._round_kind = "focus"
fw._record_session()
pump(300)
check("记账后轮次变 1", fw._focus_log.rounds_today() == 1,
      str(fw._focus_log.rounds_today()))
check("记账后时间轴有 1 段", len(fw._timeline._records) == 1,
      str(len(fw._timeline._records)))
check("轮次总数文案更新", "1" in fw._rounds_total.text(), fw._rounds_total.text())
check("记账后清空开始时刻（避免重复记账）",
      fw._focus_started_at is None)
before = fw._focus_log.rounds_today()
fw._record_session()
check("重复调用不会重复记账", fw._focus_log.rounds_today() == before,
      "%d vs %d" % (fw._focus_log.rounds_today(), before))

# 状态机：专注自然结束应自动进休息
fw._focus_started_at = datetime.now() - timedelta(minutes=25)
fw._round_kind = "focus"
fw._focus_task = "第二轮"
rounds_before = fw._focus_log.rounds_today()
fw._on_focus_complete()
pump(1500)
check("专注结束自动进入休息", fw._round_kind == "break", fw._round_kind)
check("进休息时把专注段记上账",
      fw._focus_log.rounds_today() == rounds_before + 1,
      "%d -> %d" % (rounds_before, fw._focus_log.rounds_today()))
check("休息中状态标签有提示", "休息" in fw._state_label.text(),
      fw._state_label.text())

# 休息结束：提示但不自动开始下一轮
# 先把计时器停在"已结束"状态，与实际流程一致：
# 自然结束时 _on_tick 会先把 _is_running 置 False，再发完成信号。
timer = mw._timer_widget
if timer.get_is_running():
    timer._on_pause()
timer._remaining_seconds = 0
fw._focus_started_at = datetime.now() - timedelta(minutes=5)
fw._round_kind = "break"
fw._on_focus_complete()
pump(400)
check("休息结束回到待开始状态", fw._round_kind == "focus", fw._round_kind)
check("休息结束提示可以开始下一轮",
      "下一轮" in fw._state_label.text() or "下一轮" in fw._status.text(),
      fw._state_label.text() + " | " + fw._status.text())
check("休息结束不会自动开始计时",
      not timer.get_is_running(), "不该擅自开始专注")
check("休息段也被记账",
      any(r.get("kind") == KIND_BREAK for r in fw._focus_log.segments()),
      "休息段缺失")

# 提前停止也要记账
fw._focus_started_at = datetime.now() - timedelta(minutes=7)
fw._focus_task = "提前停止的专注"
fw._round_kind = "focus"
n_before = len(fw._focus_log.segments())
mw.stop_focus_session()
pump(300)
check("提前停止也记账", len(fw._focus_log.segments()) == n_before + 1,
      "%d -> %d" % (n_before, len(fw._focus_log.segments())))

mw.exit_flow_mode()
pump(300)

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-40s %s" % (status, name, extra[:46]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
