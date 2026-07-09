"""Main application window — orchestrates state machine, audio, ASR, and UI."""

import logging
import os
import sqlite3

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QTextEdit,
    QStatusBar,
    QMessageBox,
    QLabel,
    QSizePolicy,
)

from src.config import AppConfig
from src.database import Database
from src.state_machine import SessionState, StateMachine
from src.asr.client import AsrClient
from src.audio.worker import AudioWorker
from src.ui.waveform import WaveformWidget

logger = logging.getLogger(__name__)

# Error messages per spec
_ERROR_MESSAGES = {
    "ws_fail": "无法连接语音服务，请确认服务已启动",
    "ws_disconnect": "语音服务连接中断，请重试",
    "disk_full": "磁盘空间不足，录音无法保存",
    "device_error": "录音设备异常，请检查麦克风",
    "ws_error": "语音服务连接中断，请重试",
    "mic_denied": "请授予麦克风权限",
}


class MainWindow(QMainWindow):
    """Single-window recording + transcription application."""

    def __init__(
        self,
        config: AppConfig | None = None,
        db: Database | None = None,
    ) -> None:
        super().__init__()
        self._config = config or AppConfig()
        self._db = db or self._make_db()

        self.setWindowTitle("录音转写")
        self.resize(480, 600)

        # ── Core components ────────────────────────────────────────────────
        self._state_machine = StateMachine(self)
        self._asr_client = AsrClient(self)
        self._asr_client.set_url(self._config.ws_url)

        self._audio_thread = QThread(self)
        self._audio_worker = AudioWorker(self._config)
        self._audio_worker.moveToThread(self._audio_thread)
        self._audio_thread.start()

        self._session_id: int | None = None
        self._timer: QTimer | None = None
        self._elapsed_seconds = 0

        # ── UI setup ───────────────────────────────────────────────────────
        self._setup_ui()
        self._connect_signals()

    def _make_db(self) -> Database:
        db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "sessions.db"
        )
        conn = sqlite3.connect(db_path)
        db = Database(conn)
        db.initialize()
        return db

    # ── UI ─────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Waveform
        self._waveform = WaveformWidget()
        self._waveform.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)  # type: ignore[attr-defined]
        self._waveform.setFixedHeight(100)
        layout.addWidget(self._waveform)

        # Record button
        self._button = QPushButton("请按按钮开始录音")
        self._button.setMinimumHeight(48)
        self._button.setStyleSheet("""
            QPushButton {
                background-color: #00ff88;
                color: #111;
                border: none;
                border-radius: 24px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:pressed {
                background-color: #00cc6a;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #999;
            }
        """)
        self._button.clicked.connect(self._on_button_clicked)
        layout.addWidget(self._button)

        # Live transcription
        self._live_text = QTextEdit()
        self._live_text.setReadOnly(True)
        self._live_text.setPlaceholderText("实时转写将在此显示…")
        self._live_text.setStyleSheet("color: #aaa; background: #1a1a1a;")
        self._live_text.setMinimumHeight(80)
        layout.addWidget(self._live_text)

        # Offline transcription
        self._offline_text = QTextEdit()
        self._offline_text.setReadOnly(True)
        self._offline_text.setPlaceholderText("离线转写结果将在此显示…")
        self._offline_text.setStyleSheet("color: #777; background: #1a1a1a;")
        self._offline_text.setMinimumHeight(80)
        layout.addWidget(self._offline_text)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就绪")
        self._status_bar.addWidget(self._status_label)
        self._time_label = QLabel("")
        self._status_bar.addPermanentWidget(self._time_label)

    def _connect_signals(self) -> None:
        sm = self._state_machine
        sm.state_changed.connect(self._on_state_changed)

        asr = self._asr_client
        asr.connected.connect(lambda: sm.transition("ws_ok"))
        asr.disconnected.connect(self._on_ws_disconnected)
        asr.partial_result.connect(self._on_partial_result)
        asr.final_result.connect(self._on_final_result)
        asr.error.connect(lambda msg: self._handle_error("ws_fail"))

        worker = self._audio_worker
        worker.chunk_ready.connect(asr.send_audio)
        worker.rms_amplitude.connect(self._waveform.push_rms)
        worker.device_error.connect(lambda msg: self._handle_error("device_error"))
        worker.disk_error.connect(lambda msg: self._handle_error("disk_full"))

    # ── Button handler ─────────────────────────────────────────────────────

    def _on_button_clicked(self) -> None:
        state = self._state_machine.state
        if state == SessionState.IDLE:
            # Check microphone permission
            from PySide6.QtMultimedia import QMediaDevices
            device = QMediaDevices.defaultAudioInput()
            if device.isNull():
                self._show_error_in_ui("请授予麦克风权限")
                self._button.setEnabled(False)
                self._status_label.setText("麦克风不可用")
                return
            self._button.setEnabled(True)
            self._start_session()
            self._state_machine.transition("click")
            self._asr_client.connect_to_server()
        elif state == SessionState.CONNECTING:
            pass  # button does nothing while connecting
        elif state == SessionState.RECORDING:
            self._state_machine.transition("click")
            self._audio_worker.stop_recording()
            self._asr_client.send_stop()
        elif state == SessionState.PROCESSING:
            pass  # button does nothing while processing
        elif state == SessionState.ERROR:
            self._state_machine.transition("click")

    def _start_session(self) -> None:
        session = self._db.create_session()
        self._session_id = session["id"]
        self._db.insert_log(self._session_id, "INFO", "Session started")
        self._live_text.clear()
        self._offline_text.clear()
        self._start_timer()
        self._audio_worker.start_recording(self._session_id)

    def _start_timer(self) -> None:
        self._elapsed_seconds = 0
        self._time_label.setText("00:00")
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        self._elapsed_seconds += 1
        m, s = divmod(self._elapsed_seconds, 60)
        self._time_label.setText(f"{m:02d}:{s:02d}")

    # ── State change handler ───────────────────────────────────────────────

    def _on_state_changed(self, state: SessionState, trigger: str) -> None:
        self._waveform.set_state(state)
        self._button.setText(self._state_machine.button_text)

        if state == SessionState.CONNECTING:
            self._status_label.setText("正在连接语音服务…")
        elif state == SessionState.RECORDING:
            self._status_label.setText("录音中")
        elif state == SessionState.PROCESSING:
            self._status_label.setText("正在处理转写…")
            if self._timer:
                self._timer.stop()
            self._on_recording_finished()
        elif state == SessionState.IDLE:
            self._status_label.setText("就绪")
            self._time_label.setText("")
        elif state == SessionState.ERROR:
            self._status_label.setText("错误")

    def _on_ws_disconnected(self) -> None:
        """Handle unexpected WebSocket disconnection."""
        if self._state_machine.state in (
            SessionState.RECORDING,
            SessionState.PROCESSING,
        ):
            self._handle_error("ws_disconnect")

    def _on_recording_finished(self) -> None:
        """Called when entering Processing state."""
        if self._session_id is not None:
            self._db.update_status(self._session_id, "completed")
            wav_path = self._audio_worker.wav_path
            if wav_path:
                self._db.update_wav_path(self._session_id, wav_path)

    def _on_partial_result(self, text: str) -> None:
        self._live_text.setPlainText(text)
        if self._session_id is not None:
            self._db.update_live_text(self._session_id, text)

    def _on_final_result(self, text: str) -> None:
        self._offline_text.setPlainText(text)
        if self._session_id is not None:
            self._db.update_offline_text(self._session_id, text)
        self._state_machine.transition("final_result")

    def _handle_error(self, error_type: str) -> None:
        message = _ERROR_MESSAGES.get(error_type, "未知错误")
        logger.error("Error: %s — %s", error_type, message)

        if self._session_id is not None:
            self._db.update_status(self._session_id, "error")
            self._db.update_error_message(self._session_id, message)
            self._db.insert_log(self._session_id, "ERROR", message)

        self._state_machine.transition(error_type)
        self._live_text.clear()

    # ── Close protection ───────────────────────────────────────────────────

    def _show_error_in_ui(self, message: str) -> None:
        """Display an error message in the live text area."""
        self._live_text.setPlainText(message)
        self._live_text.setStyleSheet("color: #ff4444; background: #1a1a1a;")

    def closeEvent(self, event) -> None:
        if self._state_machine.state == SessionState.RECORDING:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "录音正在进行，确定退出吗？",
                QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
                QMessageBox.No,  # type: ignore[attr-defined]
            )
            if reply == QMessageBox.No:  # type: ignore[attr-defined]
                event.ignore()
                return

        # Cleanup
        if self._asr_client:
            self._asr_client.disconnect_from_server()
        if self._timer:
            self._timer.stop()
        self._audio_thread.quit()
        self._audio_thread.wait(3000)
        super().closeEvent(event)
