"""流式显示 —— 打字机效果。

为什么用打字机而不是真的 SSE 流式：
  * ToYu 要兼容任何 OpenAI 兼容端点，**不是所有端点都支持 SSE 流式**；
    打字机对模型侧零要求，任何 provider 都能用
  * 真正的价值是"不用干等"：先在气泡里显示"思考中…"，
    拿到完整回复后再逐字展开，感知延迟大幅下降
  * 零新增依赖、零协议改动、失败时自动退回一次性显示

可随时在设置里关掉（关掉就退回一次性显示）。
"""

from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

# 每个 tick 显示的字符数（中文按字算，2 字/25ms ≈ 80 字/秒，接近阅读速度）
CHARS_PER_TICK = 2
TICK_MS = 25
# 超过这个长度就不逐字了（长文逐字太慢，改为分段）——直接全量显示
MAX_ANIMATED_CHARS = 400


class TypingAnimator(QObject):
    """把一段文本分帧吐出来，驱动界面逐字追加。

    finished 在动画结束时发出，便于调用方做收尾（比如清掉光标）。
    """

    chunk = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full = ""
        self._pos = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)

    def start(self, text: str):
        """开始播放。空文本立即结束。"""
        self._timer.stop()
        self._full = text or ""
        self._pos = 0
        if not self._full:
            self.finished.emit()
            return
        if len(self._full) > MAX_ANIMATED_CHARS:
            # 太长：不做逐字动画，一次性给完（避免用户等到不耐烦）
            self.chunk.emit(self._full)
            self._pos = len(self._full)
            self.finished.emit()
            return
        self._timer.start(TICK_MS)

    def finish_now(self):
        """立即显示剩余全部内容（用户点了一下想直接看全文）。"""
        self._timer.stop()
        if self._pos < len(self._full):
            self.chunk.emit(self._full[self._pos:])
            self._pos = len(self._full)
        self.finished.emit()

    def is_running(self) -> bool:
        return self._timer.isActive()

    def _step(self):
        if self._pos >= len(self._full):
            self._timer.stop()
            self.finished.emit()
            return
        nxt = self._full[self._pos:self._pos + CHARS_PER_TICK]
        self._pos += CHARS_PER_TICK
        self.chunk.emit(nxt)
        if self._pos >= len(self._full):
            self._timer.stop()
            self.finished.emit()
