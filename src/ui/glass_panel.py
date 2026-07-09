"""Glass panel widget — frosted glass text display with neon accents.

A semi-transparent dark panel with:
- Frosted glass background (subtle gradient + blur effect via alpha layers)
- Thin neon edge glow that brightens on content change
- Hairline divider between live and offline text sections
- Auto-scrolling text areas with terminal-style rendering
"""

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QLinearGradient,
    QBrush,
    QFont,
    QFontDatabase,
)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class GlassPanel(QWidget):
    """Frosted glass panel containing live and offline transcription text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent;")

        self._edge_glow = 0.0
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._decay_glow)
        self._glow_timer.start(50)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        # Try monospace font for HUD feel, fallback to system default
        font = QFont("SF Mono", 13)
        if not QFontDatabase.hasFamily("SF Mono"):
            font = QFont("Menlo", 13)
            if not QFontDatabase.hasFamily("Menlo"):
                font = QFont("Courier New", 13)

        # Live transcription
        self._live_text = QTextEdit()
        self._live_text.setReadOnly(True)
        self._live_text.setPlaceholderText("实时转写将在此显示…")
        self._live_text.setFont(font)
        self._live_text.setStyleSheet("""
            QTextEdit {
                color: #00ff88;
                background: transparent;
                border: none;
                padding: 4px 0;
            }
            QTextEdit QScrollBar:vertical {
                width: 4px;
                background: transparent;
            }
            QTextEdit QScrollBar::handle:vertical {
                background: #00ff8833;
                border-radius: 2px;
            }
        """)
        self._live_text.setMinimumHeight(80)
        layout.addWidget(self._live_text)

        # Divider
        self._divider_glow = 0.0

        # Offline transcription
        self._offline_text = QTextEdit()
        self._offline_text.setReadOnly(True)
        self._offline_text.setPlaceholderText("离线转写结果将在此显示…")
        self._offline_text.setFont(font)
        self._offline_text.setStyleSheet("""
            QTextEdit {
                color: #66cc99;
                background: transparent;
                border: none;
                padding: 4px 0;
            }
            QTextEdit QScrollBar:vertical {
                width: 4px;
                background: transparent;
            }
            QTextEdit QScrollBar::handle:vertical {
                background: #66cc9933;
                border-radius: 2px;
            }
        """)
        self._offline_text.setMinimumHeight(80)
        layout.addWidget(self._offline_text)

    def set_live_text(self, text: str) -> None:
        self._live_text.setPlainText(text)
        self._trigger_glow()

    def set_offline_text(self, text: str) -> None:
        self._offline_text.setPlainText(text)
        self._trigger_glow()

    def clear(self) -> None:
        self._live_text.clear()
        self._offline_text.clear()

    def show_error(self, message: str) -> None:
        self._live_text.setPlainText(message)
        self._live_text.setStyleSheet("""
            QTextEdit {
                color: #ff4444;
                background: transparent;
                border: none;
                padding: 4px 0;
            }
        """)

    def _trigger_glow(self) -> None:
        self._edge_glow = 1.0

    def _decay_glow(self) -> None:
        if self._edge_glow > 0.001:
            self._edge_glow *= 0.94
            self.update()
        if self._divider_glow > 0.001:
            self._divider_glow *= 0.94

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # type: ignore[attr-defined]
        w, h = self.width(), self.height()

        # ── Glass background ──────────────────────────────────────────
        bg_gradient = QLinearGradient(0, 0, 0, h)
        bg_gradient.setColorAt(0, QColor(15, 18, 20, 220))
        bg_gradient.setColorAt(0.5, QColor(10, 12, 14, 230))
        bg_gradient.setColorAt(1, QColor(15, 18, 20, 220))
        painter.setPen(Qt.NoPen)  # type: ignore[attr-defined]
        painter.setBrush(QBrush(bg_gradient))
        painter.drawRoundedRect(QRectF(0, 0, w, h), 12, 12)

        # ── Edge glow ─────────────────────────────────────────────────
        glow_alpha = int(self._edge_glow * 120)
        glow_pen = QPen(QColor(0, 255, 136, glow_alpha), 1.5)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)  # type: ignore[attr-defined]
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 12, 12)

        # ── Hairline divider ──────────────────────────────────────────
        div_y = self._live_text.height() + 32  # approximate divider position
        div_alpha = int(40 + self._edge_glow * 80)
        div_pen = QPen(QColor(0, 255, 136, div_alpha), 1)
        painter.setPen(div_pen)
        painter.drawLine(16, div_y, w - 16, div_y)

        painter.end()
