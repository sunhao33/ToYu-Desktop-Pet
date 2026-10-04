"""回归测试：学习报告生成与导出。

覆盖：
  * 数据聚合：学习时长、应用分布、完成任务、时段、目标
  * 渲染：Markdown 结构完整、空数据给说明而不是空表格
  * 导出：文件写入、同名不覆盖、原子写入
  * AI 工具：export_learning_report 能生成与导出
  * 界面接线：数据面板有报告卡片、周期切换、导出按钮
"""

import os
import re
import sys
import tempfile
import time
from datetime import date, timedelta

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.report import (  # noqa: E402
    PERIOD_MONTH, PERIOD_TODAY, PERIOD_WEEK, LearningReport,
)

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=150):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def day(offset):
    return (date.today() - timedelta(days=offset)).isoformat()


# ══════════════════════════════════════════════════════════
# 合成数据（不碰真实数据文件）
# ══════════════════════════════════════════════════════════
class FakeTracker:
    PLAN = {
        0: [("Code.exe", "a.py", 5400), ("chrome.exe", "论文检索", 1800),
            ("哔哩哔哩.exe", "", 2400)],
        1: [("Code.exe", "b.py", 7200), ("Typora.exe", "笔记.md", 2400)],
        2: [("Code.exe", "c.py", 600)],          # 只有 10 分钟
        5: [("pycharm64.exe", "d.py", 9000)],
    }

    def get_sessions(self, date_str=None):
        for offset, sessions in self.PLAN.items():
            if date_str == day(offset):
                return [{"app": a, "title": t, "secs": float(s)} for a, t, s in sessions]
        return []

    def get_hourly_data(self, date_str=None):
        data = [0.0] * 24
        data[9] = 1800.0
        data[10] = 3600.0
        data[14] = 1200.0
        return data

    def get_focus_stats(self, date_str=None):
        return {"sessions": 8, "meaningful": 5, "longest_secs": 5400.0,
                "total_secs": 18000.0}


class FakeTodo:
    def get_task_history(self):
        return {
            day(0): [{"text": "写报告模块", "time": "09:30", "duration": 5400}],
            day(1): [{"text": "复习第三章", "time": "14:00", "duration": 2700}],
        }


class FakeGoal:
    def progress(self, date_str=None):
        return {"has_goal": True, "goal_minutes": 120, "study_minutes": 90,
                "ratio": 0.75, "reached": False, "remaining_minutes": 30}


class EmptyTracker:
    def get_sessions(self, date_str=None):
        return []

    def get_hourly_data(self, date_str=None):
        return [0.0] * 24

    def get_focus_stats(self, date_str=None):
        return {"sessions": 0, "meaningful": 0, "longest_secs": 0.0,
                "total_secs": 0.0}


report = LearningReport(tracker=FakeTracker(), todo_widget=FakeTodo(),
                        goal_tracker=FakeGoal())

# ══════════════════════════════════════════════════════════
# 1. 数据聚合
# ══════════════════════════════════════════════════════════
d = report.collect(PERIOD_TODAY)
check("今日学习时长只算学习类",
      abs(d["total_study_seconds"] - 7200) < 1,
      "%.0f 秒（期望 7200）" % d["total_study_seconds"])
check("屏幕时间含娱乐应用",
      abs(d["total_screen_seconds"] - 9600) < 1,
      "%.0f" % d["total_screen_seconds"])
check("任务被收集", len(d["tasks"]) == 1, "%d 项" % len(d["tasks"]))
check("应用分布不含娱乐应用", "哔哩哔哩.exe" not in d["apps"], str(list(d["apps"])))
check("最佳时段被识别", d["best_hour"] == 10, str(d["best_hour"]))
check("目标进度被带上", d["goal"] is not None and d["goal"]["has_goal"])
check("has_data 为真", d["has_data"] is True)

d7 = report.collect(PERIOD_WEEK)
check("本周统计 7 天", len(d7["days"]) == 7, str(len(d7["days"])))
check("本周学习时长累加正确",
      abs(d7["total_study_seconds"] - (7200 + 9600 + 600 + 9000)) < 1,
      "%.0f" % d7["total_study_seconds"])
check("本周任务累加正确", len(d7["tasks"]) == 2, "%d" % len(d7["tasks"]))
check("每日数据逐日记录", len(d7["daily"]) == 7, str(len(d7["daily"])))

d30 = report.collect(PERIOD_MONTH)
check("本月统计 30 天", len(d30["days"]) == 30, str(len(d30["days"])))

check("日期范围升序", report.date_range(PERIOD_WEEK) == sorted(report.date_range(PERIOD_WEEK)))
check("未知周期按今日处理", len(report.date_range("nonsense")) == 1)

# 空数据
empty = LearningReport(tracker=EmptyTracker(), todo_widget=None)
de = empty.collect(PERIOD_TODAY)
check("空数据时 has_data 为假", de["has_data"] is False)
check("无 tracker 时不崩", LearningReport().collect(PERIOD_TODAY)["has_data"] is False)

# ══════════════════════════════════════════════════════════
# 2. 渲染
# ══════════════════════════════════════════════════════════
md = report.render_markdown(PERIOD_TODAY)
check("报告有标题", md.startswith("# 学习报告"), md[:30])
check("报告含概览", "## 概览" in md)
check("报告含应用分布", "## 学习时间都用在哪" in md)
check("报告含时段分布", "## 时段分布" in md)
check("报告含完成清单", "## 完成了什么" in md)
check("报告含生成时间", "生成时间：" in md)
check("报告含建议", "## 观察与建议" in md)
check("报告是表格化的", "| 指标 | 数值 |" in md)
check("报告不含娱乐应用明细", "哔哩哔哩" not in md)
check("报告含目标信息", "120 分钟" in md, md[md.find("每日目标"):][:60])

md7 = report.render_markdown(PERIOD_WEEK)
check("本周报告含统计区间", "统计区间：" in md7)
check("本周报告含每日趋势", "## 每日学习时长" in md7)
check("本周报告含条形示意", "█" in md7)

empty_md = empty.render_markdown(PERIOD_TODAY)
check("空数据报告给说明而不是空表格",
      "还没有学习记录" in empty_md and "| 指标 |" not in empty_md,
      empty_md[:60])
check("空数据报告仍含引导", "专注" in empty_md)

txt = report.render_text(PERIOD_WEEK)
check("紧凑文本含关键数字", "本周" in txt and "有效学习" in txt, txt[:60])
check("紧凑文本长度受控", len(txt) <= 1200, "%d 字符" % len(txt))
check("空数据紧凑文本简洁", len(empty.render_text(PERIOD_TODAY)) < 40,
      empty.render_text(PERIOD_TODAY))

# 极端长度限制
check("可限制紧凑文本长度",
      len(report.render_text(PERIOD_WEEK, max_chars=30)) <= 30)

# ══════════════════════════════════════════════════════════
# 3. 导出
# ══════════════════════════════════════════════════════════
tmp = tempfile.mkdtemp(prefix="toyu_report_test_")
p1 = report.export(PERIOD_TODAY, directory=tmp)
check("导出文件存在", os.path.exists(p1))
check("导出是 md 后缀", p1.endswith(".md"), p1)
check("导出内容非空", os.path.getsize(p1) > 100, "%d 字节" % os.path.getsize(p1))
with open(p1, encoding="utf-8") as fh:
    content = fh.read()
check("导出内容与渲染一致", content.startswith("# 学习报告"))

p2 = report.export(PERIOD_TODAY, directory=tmp)
check("同名不覆盖（自动加序号）", p1 != p2 and os.path.exists(p1)
      and os.path.exists(p2), "%s / %s" % (os.path.basename(p1), os.path.basename(p2)))
check("序号后缀正确", re.search(r"_\d+\.md$", p2) is not None, os.path.basename(p2))

p3 = report.export(PERIOD_WEEK, directory=tmp)
check("不同周期导出到不同文件", p3 != p1 and "本周" in os.path.basename(p3),
      os.path.basename(p3))

ptxt = report.export(PERIOD_TODAY, fmt="txt", directory=tmp)
check("可导出纯文本", ptxt.endswith(".txt"), os.path.basename(ptxt))
check("没有残留临时文件", not os.path.exists(p1 + ".tmp"))

# 空数据也能导出（给用户明确说明而不是报错）
p_empty = empty.export(PERIOD_TODAY, directory=tmp)
check("空数据也能导出", os.path.exists(p_empty))
with open(p_empty, encoding="utf-8") as fh:
    check("空数据导出含说明", "还没有学习记录" in fh.read())

# ══════════════════════════════════════════════════════════
# 4. 界面与 AI 工具
# ══════════════════════════════════════════════════════════
from ui.main_window import MainWindow  # noqa: E402

mw = MainWindow()
mw.show()
pump(600)
mw._on_start_pet()
pump(800)

check("报告构建器可创建", mw._ensure_report() is not None)
check("报告预览控件存在", getattr(mw, "_report_preview", None) is not None)
check("周期按钮齐全",
      set(getattr(mw, "_report_btns", {})) == {"today", "week", "month"},
      str(list(getattr(mw, "_report_btns", {}))))

mw._refresh_report_preview("week")
pump(300)
check("预览有内容", len(mw._report_preview.text()) > 30,
      mw._report_preview.text()[:40])
check("预览过长时提示导出",
      "完整报告请点" in mw._report_preview.text()
      or len(mw._report_preview.text().splitlines()) <= 29)
check("切换周期后按钮选中", mw._report_btns["week"].isChecked())

mw._refresh_report_preview(PERIOD_MONTH)
pump(250)
check("切到本月后选中态跟着变",
      mw._report_btns["month"].isChecked()
      and not mw._report_btns["week"].isChecked())

# 导出并检查状态栏
import pet_engine.report as report_mod  # noqa: E402
orig_dir = report_mod.REPORT_DIR
report_mod.REPORT_DIR = tmp
try:
    mw._report_period = PERIOD_TODAY
    mw._export_report("today")
    pump(300)
    check("界面导出成功并提示", "已导出" in mw._status.text()
          or "报告已导出" in mw._status.text(), mw._status.text()[:60])
finally:
    report_mod.REPORT_DIR = orig_dir

# AI 工具
reg = mw._tool_registry
check("工具数增至 10", len(reg) == 10, "%d 个：%s" % (len(reg), reg.names()))
spec = reg.get("export_learning_report")
check("报告工具已注册", spec is not None)
if spec is not None:
    from pet_engine.agent import validate_arguments  # noqa: E402
    out = spec.handler(period="week")
    check("AI 能生成报告", len(out) > 10 and "本周" in out, out[:60])
    args, err = validate_arguments(spec, {"period": "year"})
    check("非法周期被拒绝", bool(err), err)
    args, err = validate_arguments(spec, {})
    check("周期有默认值", args.get("period") == "today", str(args))
    out2 = spec.handler(period="today", save_file=True)
    check("AI 能导出报告", "导出" in out2 or ".md" in out2, out2[:80])

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-42s %s" % (status, name, extra[:46]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
