"""学习/工作报告的卡片式视图。

为什么不用 QLabel 直接显示 Markdown：那样看到的是**源码**
（`| 指标 | 数值 |`、`---`、`█` 原样铺在界面上），既不好看也不好读。

这里改成按**数据**渲染成真正的界面元素：
  * 概览：网格卡片，数字大号加粗，一眼看清
  * 学习占比：横向进度条 + 百分比
  * 应用分布：每行一根条形图，长度随时长成比例
  * 时段分布：24 小时热力条（深浅表示时长）
  * 完成任务：带时间与时长的小条目
  * 观察建议 / AI 分析：文字段落，AI 分析支持 Markdown 二级标题
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)


def _fmt_minutes(minutes) -> str:
    minutes = int(minutes)
    if minutes >= 60:
        h, m = divmod(minutes, 60)
        return "%d 小时 %d 分" % (h, m) if m else "%d 小时" % h
    return "%d 分钟" % minutes


def _fmt_seconds(seconds) -> str:
    return _fmt_minutes(int(seconds) // 60)


class BarRow(QWidget):
    """一行横向条形：左侧名称、中间条形、右侧时长。"""

    def __init__(self, name: str, value_text: str, ratio: float,
                 color: str, track: str, text_color: str, name_width=96,
                 bar_height=14, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        label = QLabel(name)
        label.setFixedWidth(name_width)
        label.setStyleSheet(
            f"color: {text_color}; font-size: 11px; background: transparent;")
        label.setToolTip(name)
        row.addWidget(label)

        # 条形：用底槽 + 填充块的嵌套布局实现，避免依赖图表库
        track_widget = QFrame()
        track_widget.setFixedHeight(bar_height)
        track_widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Fixed)
        track_widget.setStyleSheet(
            f"background: {track}; border-radius: {bar_height // 2}px;")
        track_layout = QHBoxLayout(track_widget)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)
        fill = QFrame()
        fill.setStyleSheet(
            f"background: {color}; border-radius: {bar_height // 2}px;")
        track_layout.addWidget(fill, max(0, int(round(ratio * 1000))))
        track_layout.addStretch(max(1, int(round((1 - ratio) * 1000))))
        row.addWidget(track_widget, 1)

        value = QLabel(value_text)
        value.setFixedWidth(78)
        value.setAlignment(Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignVCenter)
        value.setStyleSheet(
            f"color: {text_color}; font-size: 11px; background: transparent;")
        row.addWidget(value)


class MetricTile(QFrame):
    """概览里的一格指标。"""

    def __init__(self, caption: str, value: str, accent_value=False,
                 palette=None, parent=None):
        super().__init__(parent)
        p = palette or {}
        self.setStyleSheet(
            "QFrame { background: %s; border: 1px solid %s;"
            " border-radius: 8px; }"
            % (p.get("tile_bg", "transparent"), p.get("border", "#E0E0E0")))
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 8, 10, 8)
        box.setSpacing(2)
        cap = QLabel(caption)
        cap.setStyleSheet(
            "color: %s; font-size: 10px; background: transparent;"
            % p.get("text2", "#888"))
        box.addWidget(cap)
        val = QLabel(value)
        val.setStyleSheet(
            "color: %s; font-size: 15px; font-weight: bold;"
            " background: transparent;"
            % (p.get("accent", "#C49A3C") if accent_value
               else p.get("text", "#2C1810")))
        box.addWidget(val)


class AIPanel(QFrame):
    """AI 分析专属面板。

    单独放在报告卡片顶部，是因为 AI 分析是"AI 版"的核心价值，
    但报告正文段落多、需要滚动才能看到底部 —— 那样用户会以为
    点了没反应。这里固定在最上面，一眼能看到。
    """

    def __init__(self, palette_getter, parent=None):
        super().__init__(parent)
        self._c = palette_getter
        # 高度范围要约束住：AI 正文可能上千字，不限制就会把报告卡片
        # 顶得极高（甚至把下面的日历挤没）。超出部分在面板内部滚动。
        self.setMinimumHeight(70)
        self.setMaximumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 5px; background: transparent; }"
            "QScrollBar::handle:vertical { background: %s;"
            " border-radius: 2px; min-height: 16px; }" % self._c("handle"))
        outer.addWidget(self._scroll)

        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self._scroll.setWidget(holder)
        self._box = QVBoxLayout(holder)
        self._box.setContentsMargins(12, 10, 12, 10)
        self._box.setSpacing(6)

        self.setStyleSheet(
            "AIPanel { background: %s; border: 1px solid %s;"
            " border-radius: 8px; }" % (self._c("tab_bg"), self._c("accent")))
        self.hide()

    def _clear(self):
        while self._box.count():
            item = self._box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def show_loading(self):
        self._clear()
        self._box.addWidget(self._title("正在分析…"))
        tip = QLabel("用的是「AI 页」里配置的模型，通常需要几秒到十几秒。")
        tip.setWordWrap(True)
        tip.setStyleSheet(
            "color: %s; font-size: 10px; background: transparent;"
            % self._c("text2"))
        self._box.addWidget(tip)
        self.show()

    def show_text(self, text: str):
        self._clear()
        self._box.addWidget(self._title("AI 深度分析"))
        for raw in (text or "").splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                lab = QLabel(stripped.lstrip("#").strip())
                lab.setWordWrap(True)
                lab.setStyleSheet(
                    "color: %s; font-size: 11px; font-weight: bold;"
                    " background: transparent;" % self._c("accent"))
            elif stripped.startswith(("- ", "* ")):
                lab = QLabel("· " + stripped[2:].strip())
                lab.setWordWrap(True)
                lab.setStyleSheet(
                    "color: %s; font-size: 11px; background: transparent;"
                    % self._c("text"))
            else:
                lab = QLabel(stripped.strip("*"))
                lab.setWordWrap(True)
                lab.setStyleSheet(
                    "color: %s; font-size: 11px; background: transparent;"
                    % self._c("text"))
            self._box.addWidget(lab)
        note = QLabel("由 AI 基于本报告统计数据生成，仅供参考。")
        note.setWordWrap(True)
        note.setStyleSheet(
            "color: %s; font-size: 10px; background: transparent;"
            % self._c("text2"))
        self._box.addWidget(note)
        self.show()

    def show_error(self, message: str):
        self._clear()
        self._box.addWidget(self._title("AI 分析未完成"))
        lab = QLabel(message)
        lab.setWordWrap(True)
        lab.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;"
            % self._c("danger"))
        self._box.addWidget(lab)
        self.show()

    def _title(self, text: str) -> QLabel:
        lab = QLabel("🤖 " + text)
        lab.setStyleSheet(
            "color: %s; font-size: 12px; font-weight: bold;"
            " background: transparent;" % self._c("accent"))
        return lab


class ReportView(QWidget):
    """把报告数据渲染成卡片式界面。"""

    def __init__(self, palette_getter, parent=None):
        """palette_getter: callable(key) -> color，复用主窗口主题色。"""
        super().__init__(parent)
        self._c = palette_getter
        self.setStyleSheet("background: transparent;")
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(2, 2, 6, 2)
        self._box.setSpacing(14)
        # AI 分析面板常驻在视图外（由主窗口放在卡片顶部），这里只做引用
        self.ai_panel: AIPanel | None = None

    # ── 构建 ────────────────────────────────────────────────
    def show_report(self, data: dict, suggestions=None, ai_text: str = "",
                    ai_busy: bool = False, ai_error: str = ""):
        # AI 面板优先更新：它是"AI 版"的核心价值，不该埋在滚动区底部
        if self.ai_panel is not None:
            if ai_busy:
                self.ai_panel.show_loading()
            elif ai_error:
                self.ai_panel.show_error(ai_error)
            elif ai_text:
                self.ai_panel.show_text(ai_text)
            else:
                self.ai_panel.hide()

        self._clear()
        if not data.get("has_data"):
            self._add_empty(data)
            return

        self._add_overview(data)
        if len(data.get("days", [])) > 1:
            self._add_daily(data)
        if data.get("apps"):
            self._add_apps(data)
        if data.get("best_hour") is not None and any(data.get("hourly") or []):
            self._add_hourly(data)
        if data.get("tasks"):
            self._add_tasks(data)
        if suggestions:
            self._add_tips(suggestions)

    def _clear(self):
        while self._box.count():
            item = self._box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # ── 各段落 ──────────────────────────────────────────────
    def _section(self, title: str) -> QVBoxLayout:
        """加一个小标题，返回该段落的纵向布局。"""
        box = QVBoxLayout()
        box.setSpacing(8)
        label = QLabel(title)
        label.setStyleSheet(
            "color: %s; font-size: 12px; font-weight: bold;"
            " background: transparent;" % self._c("text"))
        box.addWidget(label)
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        holder.setLayout(box)
        self._box.addWidget(holder)
        return box

    def _add_overview(self, d: dict):
        box = self._section("概览")
        grid = QGridLayout()
        grid.setSpacing(8)

        tiles = [("有效学习", _fmt_seconds(d["total_study_seconds"]), True)]
        if d["total_screen_seconds"] > 0:
            tiles.append(("屏幕时间", _fmt_seconds(d["total_screen_seconds"]),
                          False))
            pct = (d["total_study_seconds"] / d["total_screen_seconds"] * 100)
            tiles.append(("学习占比", "%.0f%%" % pct, False))
        tiles.append(("完成任务", "%d 项" % len(d["tasks"]), False))

        focus = d.get("focus") or {}
        if focus.get("longest_secs"):
            tiles.append(("最长连续", _fmt_seconds(focus["longest_secs"]), False))
        if focus.get("sessions"):
            tiles.append(("记录段数", "%d 段" % focus["sessions"], False))
        goal = d.get("goal")
        if goal and goal.get("has_goal"):
            tiles.append(("每日目标",
                          "%d%%" % round(goal.get("ratio", 0) * 100), True))

        palette = self._palette()
        for index, (caption, value, accent) in enumerate(tiles):
            grid.addWidget(MetricTile(caption, value, accent, palette),
                           index // 4, index % 4)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        box.addLayout(grid)

    def _add_daily(self, d: dict):
        box = self._section("每日学习时长")
        values = d.get("daily", {})
        peak = max(values.values()) if values else 0
        if peak <= 0:
            box.addWidget(self._muted("这段时间没有记录到学习时长"))
            return
        goal_minutes = (d.get("goal") or {}).get("goal_minutes")
        accent = self._c("accent")
        track = self._c("border")
        text = self._c("text")
        for day in d["days"]:
            secs = values.get(day, 0.0)
            reached = bool(goal_minutes and secs >= goal_minutes * 60)
            name = day[5:]  # 只显示 MM-DD，省宽度
            if reached:
                name += " ✓"
            box.addWidget(BarRow(
                name, _fmt_seconds(secs), secs / peak if peak else 0,
                self._c("success") if reached else accent,
                track, text, name_width=62, bar_height=12))

    def _add_apps(self, d: dict):
        box = self._section("时间都用在哪")
        apps = sorted(d["apps"].items(), key=lambda kv: -kv[1])
        total = d["total_study_seconds"] or 1
        peak = apps[0][1] if apps else 0
        accent = self._c("accent")
        track = self._c("border")
        text = self._c("text")
        for app_name, secs in apps[:8]:
            box.addWidget(BarRow(
                app_name, "%s（%.0f%%）" % (_fmt_seconds(secs), secs / total * 100),
                secs / peak if peak else 0, accent, track, text,
                name_width=132, bar_height=14))

    def _add_hourly(self, d: dict):
        box = self._section("时段分布")
        hourly = [s / 60.0 for s in (d.get("hourly") or [])]
        if len(hourly) < 24:
            hourly = (hourly + [0.0] * 24)[:24]
        peak = max(hourly) if hourly else 0
        if peak <= 0:
            return
        best = d.get("best_hour")
        if best is not None:
            hint = QLabel("最专注：%02d:00 - %02d:00" % (best, best + 1))
            hint.setStyleSheet(
                "color: %s; font-size: 11px; background: transparent;"
                % self._c("accent"))
            box.addWidget(hint)

        # 24 小时热力条：每格一个方块，颜色深浅表示时长
        strip = QWidget()
        strip.setStyleSheet("background: transparent;")
        strip_box = QHBoxLayout(strip)
        strip_box.setContentsMargins(0, 0, 0, 0)
        strip_box.setSpacing(2)
        accent = self._c("accent")
        for hour in range(24):
            cell = QFrame()
            cell.setFixedHeight(30)
            cell.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Fixed)
            ratio = hourly[hour] / peak if peak else 0
            if ratio <= 0:
                style = "background: %s; border-radius: 3px;" % self._c("border")
                tip = "%02d:00 无记录" % hour
            else:
                # 用透明度表示强度（0.3~1.0），保证浅色主题下也看得清
                alpha = 0.30 + 0.70 * ratio
                color = self._blend(accent, alpha)
                style = "background: %s; border-radius: 3px;" % color
                tip = "%02d:00 %s" % (hour, _fmt_minutes(round(hourly[hour])))
            cell.setStyleSheet(style)
            cell.setToolTip(tip)
            strip_box.addWidget(cell)
        box.addWidget(strip)

        axis = QWidget()
        axis.setStyleSheet("background: transparent;")
        axis_box = QHBoxLayout(axis)
        axis_box.setContentsMargins(0, 0, 0, 0)
        axis_box.setSpacing(2)
        for hour in range(24):
            lab = QLabel("%d" % hour if hour % 6 == 0 else "")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(
                "color: %s; font-size: 9px; background: transparent;"
                % self._c("text2"))
            axis_box.addWidget(lab, 1)
        box.addWidget(axis)

    def _add_tasks(self, d: dict):
        box = self._section("完成了什么（%d 项）" % len(d["tasks"]))
        multi_day = len(d.get("days", [])) > 1
        for task in d["tasks"][:20]:
            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_box = QHBoxLayout(row)
            row_box.setContentsMargins(0, 0, 0, 0)
            row_box.setSpacing(8)

            stamp = QLabel(("%s %s" % (task["date"][5:], task["time"]))
                           if multi_day else task["time"])
            stamp.setFixedWidth(88 if multi_day else 42)
            stamp.setStyleSheet(
                "color: %s; font-size: 11px; background: transparent;"
                % self._c("text2"))
            row_box.addWidget(stamp)

            # 勾选标记用文字符号，不依赖 emoji 字体
            tick = QLabel("✓")
            tick.setFixedWidth(12)
            tick.setStyleSheet(
                "color: %s; font-size: 12px; font-weight: bold;"
                " background: transparent;" % self._c("success"))
            row_box.addWidget(tick)

            name = QLabel(task["text"])
            name.setWordWrap(True)
            name.setStyleSheet(
                "color: %s; font-size: 11px; background: transparent;"
                % self._c("text"))
            row_box.addWidget(name, 1)

            if task["duration"] >= 60:
                dur = QLabel(_fmt_seconds(task["duration"]))
                dur.setStyleSheet(
                    "color: %s; font-size: 10px; background: transparent;"
                    % self._c("text2"))
                row_box.addWidget(dur)
            box.addWidget(row)
        if len(d["tasks"]) > 20:
            box.addWidget(self._muted("…还有 %d 项" % (len(d["tasks"]) - 20)))

    def _add_tips(self, tips):
        box = self._section("观察与建议")
        for tip in tips:
            box.addWidget(self._bullet(tip))
    def _add_empty(self, d: dict):
        box = self._section("暂无数据")
        box.addWidget(self._muted("%s还没有足够的学习记录。" % d.get("period_label", "")))
        box.addWidget(self._muted("开始用 ToYu 专注学习后，这里会自动出现统计："
                                  "有效学习时长、应用分布、时段分析、完成任务清单。"))

    # ── 小工具 ──────────────────────────────────────────────
    def _palette(self) -> dict:
        return {
            "tile_bg": self._c("tab_bg"),
            "border": self._c("border"),
            "text": self._c("text"),
            "text2": self._c("text2"),
            "accent": self._c("accent"),
        }

    def _muted(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;"
            % self._c("text2"))
        return lab

    def _bullet(self, text: str) -> QWidget:
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        dot = QLabel("·")
        dot.setFixedWidth(8)
        dot.setStyleSheet(
            "color: %s; font-size: 14px; font-weight: bold;"
            " background: transparent;" % self._c("accent"))
        row.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setStyleSheet(
            "color: %s; font-size: 11px; background: transparent;"
            % self._c("text"))
        row.addWidget(lab, 1)
        return holder

    @staticmethod
    def _blend(color: str, alpha: float) -> str:
        """把颜色往背景方向混合，得到指定强度的色块。

        Qt 样式表里 rgba 在部分控件上表现不一致，直接算成实色最稳。
        """
        color = color.lstrip("#")
        if len(color) != 6:
            return "#C49A3C"
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        # 往白色方向混合：alpha 越小越浅
        r = int(r + (255 - r) * (1 - alpha))
        g = int(g + (255 - g) * (1 - alpha))
        b = int(b + (255 - b) * (1 - alpha))
        return "#%02X%02X%02X" % (r, g, b)
