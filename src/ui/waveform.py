"""Cyberpunk waveform widget — glowing symmetric bar visualization.

Renders audio amplitude as neon green bars with:
- Bloom/glow effect (wider semi-transparent pass behind main bars)
- State-dependent behavior: idle flat line, recording animated, processing frozen
- Subtle scan line overlay for HUD feel
"""

from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QBrush
from PySide6.QtWidgets import QWidget

from src.state_machine import SessionState

_HISTORY_SIZE = 80
_NEON_GREEN = QColor(0, 255, 136)
_FROZEN_COLOR = QColor(0, 255, 136, 80)
_IDLE_LINE = QColor(40, 42, 46)
_BAR_COUNT = 40


class WaveformWidget(QWidget):
    """Cyberpunk waveform — glowing neon bars with bloom."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self._history: deque[float] = deque([0.0] * _HISTORY_SIZE, maxlen=_HISTORY_SIZE)
        self._state = SessionState.IDLE

    def set_state(self, state: SessionState) -> None:
        self._state = state
        if state == SessionState.IDLE:
            self._history = deque([0.0] * _HISTORY_SIZE, maxlen=_HISTORY_SIZE)
        self.update()

    def push_rms(self, rms: float) -> None:
        self._history.append(min(rms, 1.0))
        if self._state == SessionState.RECORDING:
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # type: ignore[attr-defined]

        w, h = self.width(), self.height()
        center_y = h // 2
        max_half = h // 2 - 8

        if self._state == SessionState.RECORDING:
            self._draw_active(painter, w, h, center_y, max_half)
        elif self._state == SessionState.PROCESSING:
            self._draw_frozen(painter, w, h, center_y, max_half)
        else:
            # Idle / Connecting / Error — subtle horizontal line
            painter.setPen(QPen(_IDLE_LINE, 1))
            painter.drawLine(0, center_y, w, center_y)

        painter.end()

    def _draw_active(
        self, painter: QPainter, w: int, h: int, center_y: int, max_half: int
    ) -> None:
        bar_count = min(len(self._history), _BAR_COUNT)
        bar_width = max(3, w // (bar_count * 2))
        gap = max(1, bar_width // 2)

        for i in range(bar_count):
            idx = len(self._history) - bar_count + i
            rms = self._history[idx]
            half_bar = int(rms * max_half)
            x = i * (bar_width + gap)

            # Bloom layer (wider, semi-transparent)
            bloom_pen = QPen(QColor(0, 255, 136, 40), bar_width + 4)
            painter.setPen(bloom_pen)
            painter.drawLine(x, center_y - half_bar, x, center_y + half_bar)

            # Core bar
            bar_pen = QPen(_NEON_GREEN, bar_width)
            painter.setPen(bar_pen)
            painter.drawLine(x, center_y - half_bar, x, center_y + half_bar)

            # Bright tip
            tip_pen = QPen(QColor(180, 255, 200), bar_width)
            painter.setPen(tip_pen)
            tip_len = max(2, int(half_bar * 0.15))
            painter.drawLine(x, center_y - half_bar, x, center_y - half_bar + tip_len)
            painter.drawLine(x, center_y + half_bar - tip_len, x, center_y + half_bar)

    def _draw_frozen(
        self, painter: QPainter, w: int, h: int, center_y: int, max_half: int
    ) -> None:
        # Same as active but with frozen, dimmer colors
        bar_count = min(len(self._history), _BAR_COUNT)
        bar_width = max(3, w // (bar_count * 2))
        gap = max(1, bar_width // 2)

        for i in range(bar_count):
            idx = len(self._history) - bar_count + i
            rms = self._history[idx]
            half_bar = int(rms * max_half)
            x = i * (bar_width + gap)

            bloom_pen = QPen(QColor(0, 255, 136, 15), bar_width + 4)
            painter.setPen(bloom_pen)
            painter.drawLine(x, center_y - half_bar, x, center_y + half_bar)

            bar_pen = QPen(_FROZEN_COLOR, bar_width)
            painter.setPen(bar_pen)
            painter.drawLine(x, center_y - half_bar, x, center_y + half_bar)
