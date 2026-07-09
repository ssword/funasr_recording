"""Waveform widget — symmetric bar visualization of audio amplitude."""

from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget

from src.state_machine import SessionState

# Waveform keeps a rolling window of recent RMS values for smooth animation.
_HISTORY_SIZE = 60
_ACTIVE_COLOR = QColor("#00ff88")
_IDLE_COLOR = QColor("#333333")
_FROZEN_COLOR = QColor(0, 255, 136, 100)


class WaveformWidget(QWidget):
    """Renders a symmetric amplitude waveform bar.

    - Idle/Connecting/Error: flat horizontal line.
    - Recording: animated green bars bouncing with RMS amplitude.
    - Processing: frozen at last frame, semi-transparent green.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(100)
        self._history: deque[float] = deque([0.0] * _HISTORY_SIZE, maxlen=_HISTORY_SIZE)
        self._state = SessionState.IDLE

    def set_state(self, state: SessionState) -> None:
        self._state = state
        if state == SessionState.IDLE:
            self._history = deque([0.0] * _HISTORY_SIZE, maxlen=_HISTORY_SIZE)
        self.update()

    def push_rms(self, rms: float) -> None:
        """Add an RMS amplitude value to the rolling history."""
        self._history.append(min(rms, 1.0))
        if self._state == SessionState.RECORDING:
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # type: ignore[attr-defined]

        w = self.width()
        h = self.height()
        center_y = h // 2

        if self._state in (SessionState.IDLE, SessionState.CONNECTING, SessionState.ERROR):
            # Flat horizontal line
            painter.setPen(QColor("#333333"))
            painter.drawLine(0, center_y, w, center_y)
        elif self._state == SessionState.RECORDING:
            painter.setPen(QColor("#00ff88"))
            self._draw_bars(painter, w, h, center_y, _ACTIVE_COLOR)
        elif self._state == SessionState.PROCESSING:
            self._draw_bars(painter, w, h, center_y, _FROZEN_COLOR)

        painter.end()

    def _draw_bars(
        self, painter: QPainter, w: int, h: int, center_y: int, color: QColor
    ) -> None:
        painter.setPen(color)
        painter.setBrush(color)
        bar_count = min(len(self._history), 30)
        bar_width = max(2, w // (bar_count * 2))
        gap = bar_width

        for i in range(bar_count):
            idx = len(self._history) - bar_count + i
            rms = self._history[idx]
            half_bar = int(rms * (h // 2 - 4))
            x = i * (bar_width + gap)

            # Symmetric bars: top and bottom
            painter.drawRect(x, center_y - half_bar, bar_width, half_bar)
            painter.drawRect(x, center_y, bar_width, half_bar)
