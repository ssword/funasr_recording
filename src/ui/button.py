"""Neon ring pulse button — cyberpunk HUD interaction element.

Features:
- Breathing glow animation (ambient pulse)
- Shockwave ring expansion on click
- Orbiting particle wisps around the ring edge
- State-dependent colors (idle green, recording red-pulse, processing amber)
"""

import math
from enum import Enum

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Property
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QRadialGradient,
    QBrush,
    QConicalGradient,
    QFont,
)
from PySide6.QtWidgets import QPushButton

from src.state_machine import SessionState


class ButtonVisualState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


_STATE_COLORS = {
    ButtonVisualState.IDLE: QColor("#00ff88"),
    ButtonVisualState.CONNECTING: QColor("#ffaa00"),
    ButtonVisualState.RECORDING: QColor("#ff3355"),
    ButtonVisualState.PROCESSING: QColor("#ffaa00"),
    ButtonVisualState.ERROR: QColor("#ff4444"),
}

_BUTTON_RADIUS = 80
_RING_WIDTH = 4
_FPS = 60
_WISP_COUNT = 6


class NeonButton(QPushButton):
    """A circular neon-ring button with pulse, shockwave, and wisps.

    Emits:
        clicked — standard QPushButton signal, plus triggers shockwave animation.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(_BUTTON_RADIUS * 2 + 40, _BUTTON_RADIUS * 2 + 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Disable stylesheet background — we paint everything ourselves
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("background: transparent; border: none;")

        self._visual_state = ButtonVisualState.IDLE
        self._pulse_phase = 0.0
        self._shockwave_radius = 0.0
        self._shockwave_alpha = 0.0
        self._wisp_phase = 0.0
        self._flash_alpha = 0.0
        self._hover_alpha = 0.0

        # Animation timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(1000 // _FPS)

        # Click triggers shockwave
        self.clicked.connect(self._on_click)

    def set_visual_state(self, state: ButtonVisualState) -> None:
        self._visual_state = state
        self.update()

    # ── Animation tick ────────────────────────────────────────────────────

    def _tick(self) -> None:
        dt = 1.0 / _FPS
        self._pulse_phase += dt * 1.5  # breathing speed
        self._wisp_phase += dt * 0.8

        # Decay shockwave
        if self._shockwave_alpha > 0.001:
            self._shockwave_radius += dt * 600
            self._shockwave_alpha *= 0.92
        else:
            self._shockwave_alpha = 0.0

        # Decay flash
        if self._flash_alpha > 0.001:
            self._flash_alpha *= 0.88
        else:
            self._flash_alpha = 0.0

        self.update()

    def _on_click(self) -> None:
        self._shockwave_radius = 0.0
        self._shockwave_alpha = 1.0
        self._flash_alpha = 0.6

    # ── Paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = _BUTTON_RADIUS
        color = _STATE_COLORS[self._visual_state]

        # ── Shockwave ring ─────────────────────────────────────────────
        if self._shockwave_alpha > 0.01:
            sw_color = QColor(color.red(), color.green(), color.blue(),
                              int(self._shockwave_alpha * 120))
            sw_pen = QPen(sw_color, _RING_WIDTH)
            painter.setPen(sw_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy),
                                self._shockwave_radius, self._shockwave_radius)

        # ── Outer glow aura ────────────────────────────────────────────
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
        glow_alpha = int(40 + pulse * 40 + self._hover_alpha * 30)
        glow_gradient = QRadialGradient(QPointF(cx, cy), radius + 20)
        glow_color = QColor(color.red(), color.green(), color.blue(), glow_alpha)
        glow_gradient.setColorAt(0, glow_color)
        glow_gradient.setColorAt(0.7, QColor(color.red(), color.green(), color.blue(), 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow_gradient))
        painter.drawEllipse(QPointF(cx, cy), radius + 20, radius + 20)

        # ── Button body ────────────────────────────────────────────────
        body_gradient = QRadialGradient(QPointF(cx - radius * 0.15, cy - radius * 0.2),
                                        radius * 1.1)
        body_base = QColor(20, 22, 24)
        body_gradient.setColorAt(0, QColor(35, 38, 42))
        body_gradient.setColorAt(1, body_base)
        painter.setBrush(QBrush(body_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # ── Flash overlay ──────────────────────────────────────────────
        if self._flash_alpha > 0.01:
            flash_color = QColor(255, 255, 255, int(self._flash_alpha * 200))
            painter.setBrush(QBrush(flash_color))
            painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # ── Neon ring ──────────────────────────────────────────────────
        ring_alpha = 180 + int(pulse * 75)
        ring_color = QColor(color.red(), color.green(), color.blue(), ring_alpha)
        ring_pen = QPen(ring_color, _RING_WIDTH)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # ── Orbiting wisps ─────────────────────────────────────────────
        for i in range(_WISP_COUNT):
            angle = self._wisp_phase + (2 * math.pi * i / _WISP_COUNT)
            wx = cx + math.cos(angle) * (radius + 8)
            wy = cy + math.sin(angle) * (radius + 8)
            wisp_alpha = int(80 + pulse * 60)
            wisp_color = QColor(color.red(), color.green(), color.blue(), wisp_alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(wisp_color)
            painter.drawEllipse(QPointF(wx, wy), 3, 3)

        # ── Text ───────────────────────────────────────────────────────
        text_color = QColor(220, 220, 220) if self._flash_alpha < 0.1 else QColor(30, 30, 30)
        painter.setPen(text_color)
        font = QFont("Helvetica Neue", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self.text()
        )

        painter.end()

    def enterEvent(self, event) -> None:
        self._hover_alpha = 1.0
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_alpha = 0.0
        super().leaveEvent(event)

    @staticmethod
    def state_to_visual(state: SessionState) -> ButtonVisualState:
        mapping = {
            SessionState.IDLE: ButtonVisualState.IDLE,
            SessionState.CONNECTING: ButtonVisualState.CONNECTING,
            SessionState.RECORDING: ButtonVisualState.RECORDING,
            SessionState.PROCESSING: ButtonVisualState.PROCESSING,
            SessionState.ERROR: ButtonVisualState.ERROR,
        }
        return mapping[state]
