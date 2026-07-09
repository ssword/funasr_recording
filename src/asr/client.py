"""FunASR WebSocket client — manages connection lifecycle."""

import logging

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtWebSockets import QWebSocket

from src.asr.protocol import (
    encode_audio_message,
    encode_control_message,
    parse_response,
    is_final_result,
    extract_text,
)

logger = logging.getLogger(__name__)


class AsrClient(QObject):
    """Wraps a QWebSocket connection to the FunASR server.

    Emits:
        connected — when the WebSocket handshake completes.
        disconnected — when the connection drops.
        partial_result(text: str) — streaming is_final=false result.
        final_result(text: str) — offline is_final=true result.
        error(message: str) — connection or protocol error.
    """

    connected = Signal()
    disconnected = Signal()
    partial_result = Signal(str)
    final_result = Signal(str)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ws: QWebSocket | None = None
        self._url = "ws://localhost:10095"
        self._accumulated_text = ""

    def set_url(self, url: str) -> None:
        self._url = url

    def connect_to_server(self) -> None:
        """Open WebSocket and perform FunASR handshake."""
        if self._ws is not None:
            self._ws.deleteLater()
        self._ws = QWebSocket()
        self._ws.connected.connect(self._on_connected)
        self._ws.disconnected.connect(self._on_disconnected)
        self._ws.textMessageReceived.connect(self._on_message)
        self._ws.errorOccurred.connect(self._on_error)
        self._accumulated_text = ""
        self._ws.open(QUrl(self._url))

    def disconnect_from_server(self) -> None:
        """Gracefully close the WebSocket."""
        if self._ws is not None:
            self._ws.close()
            self._ws = None

    def send_audio(self, chunk: bytes) -> None:
        """Send a raw PCM audio chunk to the server."""
        if self._ws and self._ws.state() == QWebSocket.ConnectedState:  # type: ignore[attr-defined]
            msg = encode_audio_message(chunk)
            self._ws.sendTextMessage(msg)

    def send_stop(self) -> None:
        """Tell the server to finalize and return offline result."""
        if self._ws and self._ws.state() == QWebSocket.ConnectedState:  # type: ignore[attr-defined]
            msg = encode_control_message("stop")
            self._ws.sendTextMessage(msg)

    # ── Private slots ─────────────────────────────────────────────────────

    def _on_connected(self) -> None:
        """Handshake: send start control message, then emit connected."""
        logger.info("WebSocket connected")
        if self._ws:
            self._ws.sendTextMessage(encode_control_message("start"))
        self.connected.emit()

    def _on_disconnected(self) -> None:
        logger.info("WebSocket disconnected")
        self.disconnected.emit()

    def _on_message(self, raw: str) -> None:
        result = parse_response(raw)
        if result is None:
            return
        text = extract_text(result)
        if is_final_result(result):
            self._accumulated_text = text
            self.final_result.emit(text)
        else:
            self._accumulated_text = text
            self.partial_result.emit(text)

    def _on_error(self, error_code) -> None:
        # error_code is QAbstractSocket.SocketError
        msg = f"WebSocket error: {error_code}"
        logger.error(msg)
        self.error.emit(msg)

    @property
    def accumulated_text(self) -> str:
        return self._accumulated_text
