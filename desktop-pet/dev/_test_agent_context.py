"""回归测试：上下文注入（第 2 批）+ 新增工具。

覆盖：
  * 状态块收集待办/学习/日程/宠物状态
  * 隐私开关：剪贴板与前台应用默认不注入，开启后才注入
  * 400 token 硬预算：超预算时按优先级丢整块，不截半句
  * 单块取数失败不影响整体
  * 新增工具：get_screen_time_detail / add_calendar_note / set_pet_behavior
"""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from pet_engine.agent.context import (  # noqa: E402
    CHAR_BUDGET, TOKEN_BUDGET, DesktopContextBuilder,
)
from ui.main_window import MainWindow  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, "PASS" if ok else "FAIL", extra))


def pump(ms=200):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


TASKS = ["上下文测试-写文档", "上下文测试-复习"]
CAL_NOTE = "上下文测试-交报告"

mw = MainWindow()
mw.show()
pump(500)
mw._on_start_pet()
pump(700)

# 清理残留
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos
                             if not t.text.startswith("上下文测试")]
    mw._todo_widget._save_todos()
except Exception:
    pass

# ══════════════════════════════════════════════════════════
# 1. 状态块收集
# ══════════════════════════════════════════════════════════
for text in TASKS:
    mw._todo_widget._input.setText(text)
    mw._todo_widget._on_add()
    pump(250)

builder = DesktopContextBuilder(mw, mw.settings)
block = builder.build()

check("状态块包含标题", "[当前状态]" in block, block[:40])
check("状态块包含待办", all(t in block for t in TASKS), block[:120])
check("状态块包含学习情况", "学习情况" in block or "今日" in block)
check("状态块包含宠物状态", "宠物" in block)

stats = builder.stats()
check("统计接口可用", isinstance(stats, dict) and "_budget" in stats, str(stats))
check("待办块有内容", stats.get("todos", 0) > 0, str(stats.get("todos")))
check("宠物块有内容", stats.get("pet", 0) > 0, str(stats.get("pet")))

# ══════════════════════════════════════════════════════════
# 2. 隐私开关（默认关闭）
# ══════════════════════════════════════════════════════════
check("剪贴板默认关闭", mw.settings.context_clipboard_enabled is False)
check("前台应用默认关闭", mw.settings.context_foreground_enabled is False)
check("默认状态块不含剪贴板", "剪贴板" not in block, block[-80:])
check("默认状态块不含当前应用", "当前应用" not in block, block[-80:])

# 造一条剪贴板历史并开启开关
try:
    hub = mw._tools_hub
    hub.clipboard._history = [{"text": "隐私测试内容", "time": "10:00"}]
    mw.settings.context_clipboard_enabled = True
    block_on = builder.build()
    check("开启后状态块含剪贴板内容", "隐私测试内容" in block_on, block_on[-80:])
    mw.settings.context_clipboard_enabled = False
    hub.clipboard._history = []
    hub.clipboard._save()
except Exception as exc:  # noqa: BLE001
    check("剪贴板开关可生效", False, str(exc))

# ══════════════════════════════════════════════════════════
# 3. 预算控制：超预算丢整块
# ══════════════════════════════════════════════════════════
check("预算为 %d token" % TOKEN_BUDGET, TOKEN_BUDGET == 400)

# 造一批超长待办把预算撑爆。注意待办块内部只列前 6 条（块内截断），
# 所以要靠"每一条都很长"把 6 条的总长度就顶到预算之上，才能触发块级丢弃。
# 另外给屏幕统计塞确定性数据 —— 否则"学习情况"块的体积会随当天实际使用
# 情况变化，测试会时好时坏（真实踩过一次）。
long_tasks = ["上下文测试-" + ("很长的任务名称" * 13) + str(i) for i in range(6)]
try:
    for text in long_tasks:
        mw._todo_widget._input.setText(text)
        mw._todo_widget._on_add()
    pump(400)

    # 确定性地填充今日屏幕时间（8 个应用，各 30 分钟）
    try:
        from datetime import date as _date
        today_key = _date.today().isoformat()
        mw._screen_tracker._data[today_key] = {
            "VS Code": 1800.0, "Chrome": 1800.0, "微信": 1800.0, "Word": 1800.0,
            "PDF 阅读器": 1800.0, "Typora": 1800.0, "终端": 1800.0, "计算器": 1800.0,
        }
        mw._screen_tracker._save()
    except Exception:
        pass
    pump(200)

    stats_big = builder.stats()
    total_raw = sum(v for k, v in stats_big.items() if not k.startswith("_"))
    check("确实构造出了超预算的原始数据", total_raw > CHAR_BUDGET,
          "原始 %d 字符 > 预算 %d｜分块 %s"
          % (total_raw, CHAR_BUDGET,
             {k: v for k, v in stats_big.items() if not k.startswith("_")}))

    big_block = builder.build()
    check("超预算时总长度仍受控", len(big_block) <= CHAR_BUDGET + 80,
          "%d 字符（预算 %d）" % (len(big_block), CHAR_BUDGET))
    check("超预算时按优先级丢弃整块并说明",
          "未包含" in big_block, big_block.split("\n")[0])
    check("低优先级的块先被丢（宠物/剪贴板）",
          ("宠物" in big_block.split("\n")[0]
           or "剪贴板" in big_block.split("\n")[0]),
          big_block.split("\n")[0])
    check("保留下来的都是高优先级块",
          "学习情况" in big_block or "今日" in big_block,
          big_block[:100])
finally:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos
                             if not t.text.startswith("上下文测试")]
    mw._todo_widget._save_todos()
    pump(300)

# ══════════════════════════════════════════════════════════
# 4. 单块失败不影响整体
# ══════════════════════════════════════════════════════════
class BrokenBuilder(DesktopContextBuilder):
    def _block_pet(self):
        raise RuntimeError("模拟宠物块取数失败")


safe = BrokenBuilder(mw, mw.settings).build()
check("单块抛异常时其他块仍然可用",
      "待办" in safe or "学习" in safe, safe[:80])

# 全部取数失败时返回空串而不是崩溃
class AllBroken(DesktopContextBuilder):
    def _block_todos(self):
        raise RuntimeError("x")

    def _block_focus(self):
        raise RuntimeError("x")

    def _block_schedule(self):
        raise RuntimeError("x")

    def _block_pet(self):
        raise RuntimeError("x")


check("所有块失败时返回空串", AllBroken(mw, mw.settings).build() == "")

# ══════════════════════════════════════════════════════════
# 5. 新增工具：屏幕时间明细
# ══════════════════════════════════════════════════════════
reg = mw._tool_registry
check("工具已扩充到 12 个（含改设置与切页）", len(reg) == 12,
      "%d 个：%s" % (len(reg), reg.names()))
for name in ("get_screen_time_detail", "add_calendar_note", "set_pet_behavior"):
    check("已注册工具 %s" % name, reg.get(name) is not None)

from pet_engine.agent import validate_arguments  # noqa: E402

spec = reg.get("get_screen_time_detail")
out = spec.handler(top=3)
check("屏幕时间明细可调用", isinstance(out, str) and len(out) > 0, out[:60])
check("屏幕时间明细不是失败", not out.startswith("失败"), out[:60])

args, err = validate_arguments(spec, {"top": 99})
check("屏幕时间 top 超上限被拒绝", bool(err), err)
args, err = validate_arguments(spec, {})
check("屏幕时间 top 有默认值", args.get("top") == 5, str(args))

# ══════════════════════════════════════════════════════════
# 6. 新增工具：日历标注
# ══════════════════════════════════════════════════════════
spec = reg.get("add_calendar_note")
out = spec.handler(date="明天", text=CAL_NOTE)
pump(300)
check("日历标注可写入", "已" in out and CAL_NOTE in out, out[:70])
check("日历标注落盘",
      any(CAL_NOTE in str(e.get("text", ""))
          for evts in (mw._calendar._events or {}).values()
          for e in evts if isinstance(e, dict)),
      str(list((mw._calendar._events or {}).items())[:1])[:100])

# 别名换算是否正确
from datetime import date, timedelta  # noqa: E402
tomorrow = (date.today() + timedelta(days=1)).isoformat()
check("「明天」被换算成正确日期",
      any(CAL_NOTE in str(e.get("text", ""))
          for e in (mw._calendar._events or {}).get(tomorrow, [])
          if isinstance(e, dict)),
      "期望日期 %s" % tomorrow)

out = spec.handler(date="不是日期", text="x")
check("非法日期被拒绝", out.startswith("失败"), out[:60])

args, err = validate_arguments(spec, {"date": "明天"})
check("日历标注缺 text 被拒绝", bool(err), err)

# ══════════════════════════════════════════════════════════
# 7. 新增工具：宠物行为
# ══════════════════════════════════════════════════════════
spec = reg.get("set_pet_behavior")
out = spec.handler(action="celebrate")
check("宠物行为可触发", not out.startswith("失败"), out[:60])
args, err = validate_arguments(spec, {"action": "fly"})
check("非法动作被拒绝", bool(err), err)

# ══════════════════════════════════════════════════════════
# 8. AI 实例真的拿到上下文
# ══════════════════════════════════════════════════════════
ai = mw._pet._ai
check("AI 实例设置了上下文提供者", ai._context_provider is not None)
prompt = ai.compose_system_prompt()
check("AI 系统提示包含状态块", "[当前状态]" in prompt, prompt[-100:])
check("状态块每次实时构建（不是缓存）",
      ai.build_state_block() == mw._build_ai_context())

# 清理
try:
    mw._todo_widget.todos = [t for t in mw._todo_widget.todos
                             if not t.text.startswith("上下文测试")]
    mw._todo_widget._save_todos()
except Exception:
    pass
try:
    for key, evts in list((mw._calendar._events or {}).items()):
        mw._calendar._events[key] = [e for e in evts
                                     if CAL_NOTE not in str(e.get("text", ""))]
        if not mw._calendar._events[key]:
            del mw._calendar._events[key]
    mw._calendar._save_events()
except Exception:
    pass

print("\n===== RESULTS =====")
fails = 0
for name, status, extra in results:
    fails += status == "FAIL"
    print("%-4s %-44s %s" % (status, name, extra[:54]))
print("\n%d/%d passed" % (len(results) - fails, len(results)))
sys.stdout.flush()
os._exit(1 if fails else 0)
