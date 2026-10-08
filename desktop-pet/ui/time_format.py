"""时长格式化的唯一实现。

## 为什么单独抽出来

原来项目里有 **4 处各写各的**：

    ui/timer_widget.py   f"{h:02d}:{m:02d}:{s:02d}"          固定 时:分:秒
    ui/mini_timer.py     _compact()  -> 不足 1 小时用 mm:ss
    ui/flow_window.py    _fmt_clock() -> 固定 时:分:秒
    ui/timer_popup.py    f"{h:02d}:{m:02d}:{s:02d}"          固定 时:分:秒

于是同一个剩余时间在不同窗口显示成两种样子（`00:25:00` 与 `25:00`），
用户看到的就是"计时不同步"。数值其实一致 —— 但**看不出是显示问题还是
真的跑偏**，很难排查（这次实测花了 50 次采样才确认）。

统一到一处之后，改格式只改这里，不会再出现两边不一致。

## 格式约定

固定 `HH:MM:SS`，**不做"不足 1 小时就省略小时位"的压缩**：

  · 两个窗口格式完全一致，不会出现"看起来不一样"
  · 小时位在倒计时里也会有（最长支持 23 小时），固定位宽不会跳来跳去
  · 数字跳动时位宽稳定，不会因为 59:59 -> 1:00:00 而整行位移

示例：`00:25:00` / `01:30:00` / `23:00:00`
"""


def format_clock(seconds):
    """把秒数格式化成 HH:MM:SS。负数按 0 处理。"""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        total = 0
    if total < 0:
        total = 0
    return "%02d:%02d:%02d" % (total // 3600,
                               (total % 3600) // 60,
                               total % 60)


def format_compact(seconds):
    """MM:SS（超过 1 小时才带小时位）。

    只用于**空间受限**的场合（如悬浮小窗的副标题行）。
    主显示一律用 format_clock，保证两个窗口读数写法一致。
    """
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        total = 0
    if total < 0:
        total = 0
    if total >= 3600:
        return format_clock(total)
    return "%02d:%02d" % (total // 60, total % 60)
