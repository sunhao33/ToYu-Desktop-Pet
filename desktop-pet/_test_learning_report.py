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
    MODE_AI, MODE_BASIC, PERIOD_MONTH, PERIOD_TODAY, PERIOD_WEEK,
    LearningReport,
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
check("报告有标题", md.startswith("# 学习/工作报告"), md[:30])
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
      "还没有足够的学习记录" in empty_md and "| 指标 |" not in empty_md,
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
# 3. 时段分布的条形图单位（曾经的 bug：秒当分钟用 → 条形图一律顶满）
# ══════════════════════════════════════════════════════════
md_today = report.render_markdown(PERIOD_TODAY)
seg = md_today[md_today.find("## 时段分布"):md_today.find("## 完成了什么")]
# 10 点最长为 60 分钟，应拿到满格 20 格；09 点 30 分钟应为 10 格
bar_10 = [ln for ln in seg.splitlines() if ln.startswith("10:00")]
bar_09 = [ln for ln in seg.splitlines() if ln.startswith("09:00")]
check("时段条形图有 10 点数据", bool(bar_10), seg[:80])
if bar_10 and bar_09:
    full = bar_10[0].count("█")
    half = bar_09[0].count("█")
    check("最长时段满格（20 格）", full == 20, "%d 格" % full)
    check("半小时段约一半格数", 8 <= half <= 12, "%d 格" % half)
    check("条形长度与时长成比例（不是一律顶满）", half < full,
          "10点 %d 格 vs 09点 %d 格" % (full, half))
    check("时长单位显示为分钟/小时", "分钟" in bar_09[0] or "小时" in bar_09[0],
          bar_09[0])
else:
    check("时段条形图有 09 点数据", False, seg[:80])

# 曾经的错误表现：时长为 0 分钟却满格
check("不存在「0 分钟却满格」的条目",
      not any("█" in ln and " 0 分钟" in ln for ln in seg.splitlines()),
      "发现 0 分钟但有条形图的条目")

# ══════════════════════════════════════════════════════════
# 4. 数据不足的判定（避免空表格报告）
# ══════════════════════════════════════════════════════════
class TinyTracker:
    """只有几秒钟的记录 —— 不该被当成有效数据。"""

    def get_sessions(self, date_str=None):
        return [{"app": "Code.exe", "title": "a.py", "secs": 5.0}]

    def get_hourly_data(self, date_str=None):
        data = [0.0] * 24
        data[10] = 5.0
        return data

    def get_focus_stats(self, date_str=None):
        return {"sessions": 1, "meaningful": 0, "longest_secs": 5.0,
                "total_secs": 5.0}


tiny = LearningReport(tracker=TinyTracker(), todo_widget=None)
check("只有几秒记录时判为数据不足",
      tiny.collect(PERIOD_TODAY)["has_data"] is False,
      "%s" % tiny.collect(PERIOD_TODAY)["total_screen_seconds"])
check("数据不足时报告给引导而非空表格",
      "还没有足够的学习记录" in tiny.render_markdown(PERIOD_TODAY))

# ══════════════════════════════════════════════════════════
# 5. AI 版：摘要、分析、错误处理
# ══════════════════════════════════════════════════════════
digest = report.build_ai_digest(report.collect(PERIOD_TODAY))
check("AI 摘要含有效学习时长", "有效学习总时长" in digest)
check("AI 摘要含应用分布", "主要用在" in digest)
check("AI 摘要含任务清单", "完成的任务" in digest)
check("AI 摘要含目标信息", "每日目标" in digest)
check("AI 摘要长度受控（避免超上下文）", len(digest) < 1500,
      "%d 字符" % len(digest))

# 成功路径
captured = {}


def fake_transport(messages):
    captured["messages"] = messages
    return "### 整体状态\n学习节奏稳定。\n\n### 下一步建议\n1. 把难点放上午。"

res = report.analyze_with_ai(PERIOD_TODAY, transport=fake_transport)
check("AI 分析成功", res["ok"] is True, res.get("error", ""))
check("AI 分析返回正文", "整体状态" in res["text"], res["text"][:40])
check("请求里带了系统提示词",
      captured["messages"][0]["role"] == "system", str(captured.get("messages"))[:60])
check("请求里带了数据摘要",
      "有效学习总时长" in captured["messages"][1]["content"],
      captured["messages"][1]["content"][:60])
check("系统提示词要求不得引入新数字",
      "不要自己推算" in captured["messages"][0]["content"])
check("系统提示词要求不许说空话",
      "空话" in captured["messages"][0]["content"])

# 未注入 transport
res = report.analyze_with_ai(PERIOD_TODAY, transport=None)
check("未配置 transport 时明确报错", res["ok"] is False and "API Key" in res["error"],
      res["error"])

# 模型抛异常
def boom(messages):
    raise RuntimeError("网络超时")


res = report.analyze_with_ai(PERIOD_TODAY, transport=boom)
check("模型异常不崩且给出原因",
      res["ok"] is False and "网络超时" in res["error"], res["error"])

# 模型返回空
res = report.analyze_with_ai(PERIOD_TODAY, transport=lambda m: "   ")
check("模型返回空内容时报错", res["ok"] is False, res["error"])

# 数据不足时不调模型
calls = {"n": 0}


def counting(messages):
    calls["n"] += 1
    return "x"


res = tiny.analyze_with_ai(PERIOD_TODAY, transport=counting)
check("数据不足时不调用模型", calls["n"] == 0 and res["ok"] is False, res["error"])

# AI 版渲染
sample_ai = "### 分析\n内容。"
md_ai = report.render_markdown(PERIOD_TODAY, ai_text=sample_ai, mode=MODE_AI)
check("AI 版标题标明版本", "版本：AI 版" in md_ai, md_ai[:120])
check("AI 版含 AI 段落", "## 🤖 AI 深度分析" in md_ai)
check("AI 版含免责说明", "由 AI 基于本报告" in md_ai)
md_basic = report.render_markdown(PERIOD_TODAY, mode=MODE_BASIC)
check("基础版不含 AI 段落", "🤖 AI 深度分析" not in md_basic)
check("基础版标明版本", "版本：基础版" in md_basic)
check("报告标题已改为学习/工作报告",
      md_basic.startswith("# 学习/工作报告"), md_basic[:30])

# ══════════════════════════════════════════════════════════
# 6. 导出
# ══════════════════════════════════════════════════════════
tmp = tempfile.mkdtemp(prefix="toyu_report_test_")
p1 = report.export(PERIOD_TODAY, directory=tmp)
check("导出文件存在", os.path.exists(p1))
check("导出是 md 后缀", p1.endswith(".md"), p1)
check("导出内容非空", os.path.getsize(p1) > 100, "%d 字节" % os.path.getsize(p1))
with open(p1, encoding="utf-8") as fh:
    content = fh.read()
check("导出内容与渲染一致", content.startswith("# 学习/工作报告"))
check("文件名用新命名", "学习工作报告" in os.path.basename(p1),
      os.path.basename(p1))

p2 = report.export(PERIOD_TODAY, directory=tmp)
check("同名不覆盖（自动加序号）", p1 != p2 and os.path.exists(p1)
      and os.path.exists(p2), "%s / %s" % (os.path.basename(p1), os.path.basename(p2)))
check("序号后缀正确", re.search(r"_\d+\.md$", p2) is not None, os.path.basename(p2))

p3 = report.export(PERIOD_WEEK, directory=tmp)
check("不同周期导出到不同文件", p3 != p1 and "本周" in os.path.basename(p3),
      os.path.basename(p3))

# AI 版导出：文件名标出 AI 版，内容含分析
p_ai = report.export(PERIOD_TODAY, directory=tmp,
                     ai_text="### 整体状态\n测试分析。", mode=MODE_AI)
check("AI 版文件名标出 _AI版", "_AI版" in os.path.basename(p_ai),
      os.path.basename(p_ai))
with open(p_ai, encoding="utf-8") as fh:
    ai_content = fh.read()
check("AI 版文件含分析正文", "测试分析" in ai_content)
check("AI 版文件标明版本", "版本：AI 版" in ai_content)

# 基础版与 AI 版互不覆盖
p_basic = report.export(PERIOD_TODAY, directory=tmp, mode=MODE_BASIC)
check("基础版与 AI 版是不同文件", p_basic != p_ai,
      "%s / %s" % (os.path.basename(p_basic), os.path.basename(p_ai)))

ptxt = report.export(PERIOD_TODAY, fmt="txt", directory=tmp)
check("可导出纯文本", ptxt.endswith(".txt"), os.path.basename(ptxt))
check("没有残留临时文件", not os.path.exists(p1 + ".tmp"))

# 空数据也能导出（给用户明确说明而不是报错）
p_empty = empty.export(PERIOD_TODAY, directory=tmp)
check("空数据也能导出", os.path.exists(p_empty))
with open(p_empty, encoding="utf-8") as fh:
    check("空数据导出含说明", "还没有" in fh.read())

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
check("报告卡片视图存在", getattr(mw, "_report_view", None) is not None)
check("AI 分析面板存在", getattr(mw, "_report_ai_panel", None) is not None)
check("周期按钮齐全",
      set(getattr(mw, "_report_btns", {})) == {"today", "week", "month"},
      str(list(getattr(mw, "_report_btns", {}))))
check("版本按钮齐全（基础版/AI 版）",
      set(getattr(mw, "_report_mode_btns", {})) == {"basic", "ai"},
      str(list(getattr(mw, "_report_mode_btns", {}))))
check("默认是基础版", mw._report_mode == MODE_BASIC, mw._report_mode)
check("有 AI 分析按钮", getattr(mw, "_report_ai_btn", None) is not None)
check("AI 按钮初始文案", "AI 分析" in mw._report_ai_btn.text(),
      mw._report_ai_btn.text())

mw._refresh_report_preview("week")
pump(300)


def view_text(view):
    """把卡片视图里的所有 QLabel 文本收集起来（用于断言内容是否渲染）。"""
    from PyQt6.QtWidgets import QLabel
    return "\n".join(lab.text() for lab in view.findChildren(QLabel))


# 注入确定性数据再断言渲染结果。
# 原因：时段分布只统计"当天"（多天叠加会失真），而测试运行时 ToYu
# 通常没在采集屏幕时间，当天 hourly 为空 —— 那一段就（正确地）不渲染。
# 直接断言会变成依赖运行环境的偶发失败。
mw._report_builder._tracker = FakeTracker()
mw._report_builder._todo = FakeTodo()
mw._report_builder._goal = FakeGoal()

mw._refresh_report_preview("week")
pump(400)
text_week = view_text(mw._report_view)
check("卡片视图渲染出概览标题", "概览" in text_week, text_week[:60])
check("卡片视图渲染出每日时长", "每日学习时长" in text_week)
check("卡片视图渲染出应用分布", "时间都用在哪" in text_week)
check("卡片视图渲染出时段分布", "时段分布" in text_week,
      "缺少该段落，实际：%s" % text_week[:110].replace("\n", " / "))
check("卡片视图渲染出最专注时段", "最专注" in text_week)
check("卡片视图渲染出完成任务", "完成了什么" in text_week)
check("卡片视图渲染出观察建议", "观察与建议" in text_week)
check("卡片视图不再显示 Markdown 源码",
      "| 指标 | 数值 |" not in text_week and "|---|" not in text_week,
      [ln for ln in text_week.splitlines() if "|" in ln][:2])
check("卡片视图用方块字渲染条形（不再是 █ 字符）",
      "█" not in text_week)
check("卡片视图显示有效学习", "有效学习" in text_week)
check("卡片视图显示时长数值", "小时" in text_week or "分钟" in text_week)
check("卡片视图显示完成任务明细",
      "写报告模块" in text_week or "复习第三章" in text_week,
      text_week[-150:].replace("\n", " / "))
check("切换周期后按钮选中", mw._report_btns["week"].isChecked())

# 基础版必须隐藏 AI 面板
mw._report_ai_text = ""
mw._report_mode = MODE_BASIC
mw._refresh_report_preview("week")
pump(300)
# 用 isHidden() 判断自身状态：isVisible() 还会看祖先链，
# 而测试时"数据面板"这一层没被切到前台，会让 isVisible() 恒为 False。
check("基础版隐藏 AI 面板", mw._report_ai_panel.isHidden())

# AI 分析完成后，AI 面板应显示在卡片顶部（不埋在滚动区里）
mw._report_ai_text = "### 整体状态\n这是测试分析正文。"
mw._report_mode = "ai"
mw._refresh_report_preview("week")
pump(400)
ai_panel_text = view_text(mw._report_ai_panel)
check("AI 分析显示在独立面板", not mw._report_ai_panel.isHidden(), "面板自身仍处于隐藏")
check("AI 面板含标题", "AI 深度分析" in ai_panel_text, ai_panel_text[:50])
check("AI 面板含正文", "这是测试分析正文" in ai_panel_text, ai_panel_text[:80])
check("AI 面板含免责说明", "仅供参考" in ai_panel_text)
check("AI 面板有高度上限（不挤掉其他卡片）",
      mw._report_ai_panel.maximumHeight() <= 300,
      "上限 %d px" % mw._report_ai_panel.maximumHeight())

mw._report_ai_text = ""
mw._report_mode = "basic"
mw._refresh_report_preview("week")
pump(200)
check("回到基础版后隐藏 AI 面板", mw._report_ai_panel.isHidden())

mw._refresh_report_preview(PERIOD_MONTH)
pump(250)
check("切到本月后选中态跟着变",
      mw._report_btns["month"].isChecked()
      and not mw._report_btns["week"].isChecked())

# ── AI 版界面链路（注入假 transport，不发真实请求）──
mw._pet._ai_config.api_key = "sk-test-only-for-key-check"
check("配置 key 后判定为就绪", mw._ai_key_ready() is True)

ai_calls = {"n": 0}


def fake_ai(messages):
    ai_calls["n"] += 1
    return "### 整体状态\n测试分析内容。\n\n### 下一步建议\n1. 建议一。"


def toast_text():
    label = getattr(mw, "_toast_label", None)
    return label.text() if label is not None else ""


mw._report_transport_override = fake_ai
# 用「本周」而不是「今日」：今日可能还没开始记录，会走"数据不足"分支。
# 本周包含历史数据，能走到真正调用模型那一步。
mw._report_period = PERIOD_WEEK
mw._generate_ai_report()
deadline = time.time() + 15
while mw._report_ai_busy and time.time() < deadline:
    pump(150)
pump(300)
check("AI 分析被调用一次", ai_calls["n"] == 1, "%d 次" % ai_calls["n"])
check("AI 文本已保存", bool(mw._report_ai_text), repr(mw._report_ai_text[:30]))
check("分析后切到 AI 版", mw._report_mode == MODE_AI, mw._report_mode)
check("AI 版按钮选中", mw._report_mode_btns["ai"].isChecked())
check("AI 完成后按钮变为重新分析", "重新分析" in mw._report_ai_btn.text(),
      mw._report_ai_btn.text())
check("AI 完成后不停留在忙碌态", mw._report_ai_busy is False)
check("AI 完成后面板显示分析",
      not mw._report_ai_panel.isHidden()
      and "测试分析内容" in view_text(mw._report_ai_panel),
      view_text(mw._report_ai_panel)[:60])
check("完成时弹出可见提示", "AI 分析完成" in toast_text(), toast_text()[:50])

# 切换区间应清掉旧分析（数据区间变了，分析不再对应）
mw._on_report_period(PERIOD_MONTH)
pump(200)
check("切换区间后清掉 AI 分析", mw._report_ai_text == "",
      repr(mw._report_ai_text[:30]))

# 数据不足时应明确拒绝（而不是调用模型后瞎编）
no_data_calls = {"n": 0}


def counting_ai(messages):
    no_data_calls["n"] += 1
    return "x"


mw._report_transport_override = counting_ai
mw._report_period = PERIOD_TODAY
mw._generate_ai_report()
deadline = time.time() + 12
while mw._report_ai_busy and time.time() < deadline:
    pump(150)
pump(300)
if no_data_calls["n"] == 0:
    check("今日数据不足时不调用模型", True, "今日无记录，正确拒绝")
    check("数据不足时给出明确提示", "没有足够" in toast_text(),
          toast_text()[:60])
else:
    check("今日有数据时正常分析", mw._report_ai_text != "", "有数据，走了成功路径")

# AI 分析失败时回到基础版并提示
def failing_ai(messages):
    raise RuntimeError("模拟模型不可用")


mw._report_transport_override = failing_ai
mw._report_period = PERIOD_WEEK
mw._report_ai_text = ""
mw._report_mode = MODE_AI
mw._generate_ai_report()
deadline = time.time() + 12
while mw._report_ai_busy and time.time() < deadline:
    pump(150)
pump(300)
check("AI 失败后回到基础版", mw._report_mode == MODE_BASIC, mw._report_mode)
check("AI 失败后清空分析文本", mw._report_ai_text == "")
check("AI 失败后按钮恢复可用", mw._report_ai_btn.isEnabled())
check("AI 失败给出可见提示", "模拟模型不可用" in toast_text(),
      toast_text()[:70])

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
