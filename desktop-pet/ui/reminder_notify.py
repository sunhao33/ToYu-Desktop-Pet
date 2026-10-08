"""提醒气泡的统一出口（倒计时 / 番茄钟 / 护眼提醒 三个来源共用）。

## 为什么需要这个模块

原来三个提醒器各自 `PomodoroNotificationBubble(...)` + `show_near(pet)`：

    · 倒计时结束   -> main_window._on_timer_complete
    · 番茄钟休息   -> pet_window._fire_pomodoro
    · 护眼提醒     -> main_window._on_tools_notify

同一时刻有两个提醒到点，就会**弹出两个气泡叠在一起**；而且它们各自定位，
看着"位置也不在一起"。这正是反馈里说的「番茄钟提示休息和护眼提醒有严重冲突，
位置也不在一起」。

## 做法

同一时间**只显示一个**提醒气泡，其余进队列，前一个淡出后自动接上。
这样：

  · 不会重叠 —— 排队显示
  · 位置一致 —— 都由同一个类贴在宠物头顶
  · 顺序可预期 —— 先到先显示

队列有长度上限，避免长时间挂机后积压一堆过期提醒。
"""

from collections import deque

# 队列上限。超出时丢掉**最旧**的（过期的提醒补弹反而打扰用户，
# 之前 _bug_hunt 里就记录过"关机期间过期的护眼提醒会在启动瞬间补弹"）。
MAX_QUEUE = 3


class ReminderNotifier:
    """同一时间只显示一个提醒气泡，其余排队。"""

    def __init__(self):
        self._current = None          # 正在显示的气泡
        self._queue = deque()         # 待显示的 (title, subtitle)
        self._pet_getter = None       # 取宠物的回调（宠物可能被重建）

    def set_pet_getter(self, getter):
        """注入"取当前宠物窗口"的回调。

        不直接持有宠物引用：宠物在"回家/重新启动"时会被销毁重建，
        持有旧引用会拿到已删除的 C++ 对象。
        """
        self._pet_getter = getter

    def _pet(self):
        if self._pet_getter is None:
            return None
        try:
            pet = self._pet_getter()
        except Exception:             # noqa: BLE001
            return None
        if pet is None:
            return None
        try:
            return pet if pet.isVisible() else None
        except RuntimeError:          # C++ 对象已销毁
            return None

    def notify(self, title, subtitle="", kind="", on_finish=None):
        """请求显示一条提醒。

        返回 True 表示立即显示，False 表示已排队。
        没有宠物可见时返回 False 并丢弃 —— 由调用方决定是否改走状态栏。
        """
        if self._pet() is None:
            return False
        if self._current is not None:
            if len(self._queue) >= MAX_QUEUE:
                self._queue.popleft()      # 丢掉最旧的
            self._queue.append((title, subtitle, kind, on_finish))
            return False
        self._show(title, subtitle, kind, on_finish)
        return True

    def _show(self, title, subtitle, kind, on_finish):
        pet = self._pet()
        if pet is None:
            self._current = None
            return
        try:
            from pet_engine.pet_bubble import PomodoroNotificationBubble
            bubble = PomodoroNotificationBubble(
                pet, title=title, subtitle=subtitle)
        except Exception as exc:      # noqa: BLE001
            print("[Reminder] 创建提醒气泡失败: %s" % exc)
            self._current = None
            self._drain()
            return

        # 淡出结束后接着显示下一条。挂到气泡自己的淡出定时器上，
        # 不改动气泡类，避免影响其它地方对它的使用。
        bubble._reminder_finished = False

        def _on_faded():
            if getattr(bubble, "_reminder_finished", False):
                return
            bubble._reminder_finished = True
            if self._current is bubble:
                self._current = None
            if on_finish is not None:
                try:
                    on_finish(kind)
                except Exception as exc:   # noqa: BLE001
                    print("[Reminder] 回调失败: %s" % exc)
            self._drain()

        # 气泡内部 _fade_timer 停止即表示淡出完成；用 destroyed 信号最稳妥
        try:
            bubble.destroyed.connect(lambda *_: _on_faded())
        except Exception:             # noqa: BLE001
            pass

        self._current = bubble
        try:
            bubble.show_near(pet)
        except Exception as exc:      # noqa: BLE001
            print("[Reminder] 显示提醒失败: %s" % exc)
            self._current = None
            _on_faded()

    def _drain(self):
        if self._current is not None or not self._queue:
            return
        title, subtitle, kind, on_finish = self._queue.popleft()
        self._show(title, subtitle, kind, on_finish)

    def dismiss_current(self):
        """立刻收起当前提醒（用户切页/关闭宠物时用）。"""
        bubble, self._current = self._current, None
        if bubble is not None:
            try:
                bubble.close()
            except RuntimeError:
                pass
        self._queue.clear()

    def pending_count(self):
        return len(self._queue)
