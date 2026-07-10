"""Particle system widget — ambient and reactive particles for cyberpunk HUD.

Rendered as a transparent overlay. Particles drift slowly during idle,
intensify during recording, and burst on button click.
"""

import math
import random

from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QBrush
from PySide6.QtWidgets import QWidget

from src.state_machine import SessionState

_PARTICLE_COLOR = QColor(0, 255, 136)  # neon green
_MAX_PARTICLES_IDLE = 30
_MAX_PARTICLES_RECORDING = 80
_BURST_COUNT = 40
_FPS = 30


class Particle:
    """A single drifting particle with position, velocity, life, and size."""

    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size")

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        life: float = 1.0,
        size: float = 2.0,
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = size

    def update(self, dt: float) -> bool:
        """Move particle; return False when dead."""
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        # Slight drift toward center for ambient feel
        self.vx *= 0.999
        self.vy *= 0.999
        return self.life > 0

    @property
    def alpha(self) -> float:
        return max(0.0, self.life / self.max_life)


class ParticleOverlay(QWidget):
    """Transparent overlay that renders a particle system.

    Call set_state() to change particle behavior per session state.
    Call burst(x, y) to spawn a burst of particles at a point.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")
        self._particles: list[Particle] = []
        self._state = SessionState.IDLE
        self._max_particles = _MAX_PARTICLES_IDLE

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000 // _FPS)

    def set_state(self, state: SessionState) -> None:
        self._state = state
        if state == SessionState.RECORDING:
            self._max_particles = _MAX_PARTICLES_RECORDING
        else:
            self._max_particles = _MAX_PARTICLES_IDLE

    def burst(self, cx: float, cy: float) -> None:
        """Spawn a radial burst of particles from (cx, cy)."""
        for _ in range(_BURST_COUNT):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(80, 250)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            life = random.uniform(0.3, 0.8)
            size = random.uniform(1.5, 3.5)
            p = Particle(cx, cy, vx, vy, life, size)
            self._particles.append(p)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for p in self._particles:
            alpha = int(p.alpha * 255)
            color = QColor(0, 255, 136, alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            # Draw as small luminous dot with soft gradient
            radius = p.size * 2
            gradient = QRadialGradient(QPointF(p.x, p.y), radius)
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(0, 255, 136, 0))
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(QPointF(p.x, p.y), radius, radius)

        painter.end()

    def _tick(self) -> None:
        dt = 1.0 / _FPS

        # Spawn new ambient particles
        deficit = self._max_particles - len(self._particles)
        for _ in range(deficit):
            x = random.uniform(0, self.width())
            y = random.uniform(0, self.height())
            vx = random.uniform(-15, 15)
            vy = random.uniform(-25, -5)  # slight upward drift
            life = random.uniform(2.0, 6.0)
            size = random.uniform(1.0, 2.5)
            self._particles.append(Particle(x, y, vx, vy, life, size))

        # Update existing particles
        self._particles = [p for p in self._particles if p.update(dt)]

        # Wrap-around particles that drift off-screen
        for p in self._particles:
            if p.x < -20:
                p.x = self.width() + 20
            elif p.x > self.width() + 20:
                p.x = -20
            if p.y < -20:
                p.y = self.height() + 20
            elif p.y > self.height() + 20:
                p.y = -20

        self.update()
