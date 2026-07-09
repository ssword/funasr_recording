"""Main application window — cyberpunk HUD orchestrating state, audio, ASR, UI."""

import logging
import os
import sqlite3

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QStatusBar,
    QMessageBox,
    QLabel,
    QSizePolicy,
    QSpacerItem,
)

from src.config import AppConfig
from src.database import Database
from src.state_machine import SessionState, StateMachine
from src.asr.client import AsrClient
from src.audio.worker import AudioWorker
from src.ui.waveform import WaveformWidget
from src.ui.button import NeonButton, ButtonVisualState
from src.ui.glass_panel import GlassPanel
from src.ui.particles import ParticleOverlay

logger = logging.getLogger(__name__)

_ERROR_MESSAGES = {
    "ws_fail": "无法连接语音服务，请确认服务已启动",
    "ws_disconnect": "语音服务连接中断，请重试",
    "disk_full": "磁盘空间不足，录音无法保存",
    "device_error": "录音设备异常，请检查麦克风",
    "ws_error": "语音服务连接中断，请重试",
    "mic_denied": "请授予麦克风权限",
}


class MainWindow(QMainWindow):
    """Cyberpunk HUD recording + transcription application window."""

    def __init__(
        self,
        config: AppConfig | None = None,
        db: Database | None = None,
    ) -> None:
        super().__init__()
        self._config = config or AppConfig()
        self._db = db or self._make_db()

        self.setWindowTitle("录音转写")
        self.resize(720, 900)

        # ── Core components ────────────────────────────────────────────
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

        # ── UI setup ───────────────────────────────────────────────────
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

    # ── UI Construction ─────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        # Base layout
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Particle overlay — full window, behind everything interactive
        self._particles = ParticleOverlay(central)
        self._particles.setGeometry(0, 0, 720, 900)

        # Content container (positioned above particles in z-order)
        content = QWidget(central)
        content.setAttribute(Qt.WA_TranslucentBackground)  # type: ignore[attr-defined]
        content.setAutoFillBackground(False)
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(0)

        # ── Waveform (top, largest area) ───────────────────────────────
        self._waveform = WaveformWidget()
        self._waveform.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # type: ignore[attr-defined]
        self._waveform.setMinimumHeight(220)
        content_layout.addWidget(self._waveform)

        content_layout.addSpacing(16)

        # ── Button (center, anchored) ──────────────────────────────────
        btn_container = QWidget()
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        self._button = NeonButton()
        self._button.setText("录音")
        self._button.clicked.connect(self._on_button_clicked)
        btn_layout.addWidget(self._button)
        content_layout.addWidget(btn_container)

        content_layout.addSpacing(16)

        # ── Glass panel (bottom text area) ─────────────────────────────
        self._glass = GlassPanel()
        self._glass.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # type: ignore[attr-defined]
        self._glass.setMinimumHeight(220)
        content_layout.addWidget(self._glass)

        # ── Status bar ─────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        self._status_bar.addWidget(self._status_label)
        self._time_label = QLabel("")
        self._time_label.setStyleSheet("color: #00ff8866; font-size: 13px; font-weight: bold;")
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

    # ── Resize ─────────────────────────────────────────────────────────

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._particles.setGeometry(0, 0, self.width(), self.height())

    # ── Button handler ─────────────────────────────────────────────────

    def _on_button_clicked(self) -> None:
        # Particle burst at button center (map to particle overlay coords)
        btn_pos = self._button.mapTo(self._particles, self._button.rect().center())
        self._particles.burst(btn_pos.x(), btn_pos.y())

        state = self._state_machine.state
        if state == SessionState.IDLE:
            from PySide6.QtMultimedia import QMediaDevices
            device = QMediaDevices.defaultAudioInput()
            if device.isNull():
                self._glass.show_error("请授予麦克风权限")
                self._button.setEnabled(False)
                self._status_label.setText("麦克风不可用")
                return
            self._button.setEnabled(True)
            self._start_session()
            self._state_machine.transition("click")
            self._asr_client.connect_to_server()
        elif state == SessionState.RECORDING:
            self._state_machine.transition("click")
            self._audio_worker.stop_recording()
            self._asr_client.send_stop()
        elif state == SessionState.ERROR:
            self._glass.clear()
            self._state_machine.transition("click")

    def _start_session(self) -> None:
        session = self._db.create_session()
        self._session_id = session["id"]
        self._db.insert_log(self._session_id, "INFO", "Session started")
        self._glass.clear()
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

    # ── State change handler ───────────────────────────────────────────

    def _on_state_changed(self, state: SessionState, trigger: str) -> None:
        vis = NeonButton.state_to_visual(state)
        self._button.set_visual_state(vis)
        # Short labels for round button; longer spec text on hover tooltip
        short_labels = {
            SessionState.IDLE: "录音",
            SessionState.CONNECTING: "…",
            SessionState.RECORDING: "停止",
            SessionState.PROCESSING: "…",
            SessionState.ERROR: "重试",
        }
        self._button.setText(short_labels.get(state, ""))
        self._button.setToolTip(self._state_machine.button_text)
        self._waveform.set_state(state)
        self._particles.set_state(state)

        if state == SessionState.CONNECTING:
            self._status_label.setText("正在连接语音服务…")
        elif state == SessionState.RECORDING:
            self._status_label.setText("● 录音中")
            self._status_label.setStyleSheet("color: #ff3355; font-size: 11px;")
        elif state == SessionState.PROCESSING:
            self._status_label.setText("◉ 处理中…")
            self._status_label.setStyleSheet("color: #ffaa00; font-size: 11px;")
            if self._timer:
                self._timer.stop()
            self._on_recording_finished()
        elif state == SessionState.IDLE:
            self._status_label.setText("就绪")
            self._status_label.setStyleSheet("color: #666; font-size: 11px;")
            self._time_label.setText("")
        elif state == SessionState.ERROR:
            self._status_label.setText("✕ 错误")
            self._status_label.setStyleSheet("color: #ff4444; font-size: 11px;")

    def _on_ws_disconnected(self) -> None:
        if self._state_machine.state in (
            SessionState.RECORDING,
            SessionState.PROCESSING,
        ):
            self._handle_error("ws_disconnect")

    def _on_recording_finished(self) -> None:
        if self._session_id is not None:
            self._db.update_status(self._session_id, "completed")
            wav_path = self._audio_worker.wav_path
            if wav_path:
                self._db.update_wav_path(self._session_id, wav_path)

    def _on_partial_result(self, text: str) -> None:
        self._glass.set_live_text(text)
        if self._session_id is not None:
            self._db.update_live_text(self._session_id, text)

    def _on_final_result(self, text: str) -> None:
        self._glass.set_offline_text(text)
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
        self._glass.clear()

    # ── Close protection ───────────────────────────────────────────────

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

        if self._asr_client:
            self._asr_client.disconnect_from_server()
        if self._timer:
            self._timer.stop()
        self._audio_thread.quit()
        self._audio_thread.wait(3000)
        super().closeEvent(event)
