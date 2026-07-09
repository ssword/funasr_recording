"""Audio capture worker — runs QAudioSource on a dedicated QThread."""

import logging
import os
import wave
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QIODevice
from PySide6.QtMultimedia import (
    QAudioFormat,
    QAudioSource,
    QMediaDevices,
)

from src.audio.chunker import Chunker
from src.config import AppConfig

logger = logging.getLogger(__name__)


def _make_audio_format(sample_rate: int) -> QAudioFormat:
    fmt = QAudioFormat()
    fmt.setSampleRate(sample_rate)
    fmt.setChannelCount(1)
    fmt.setSampleFormat(QAudioFormat.Int16)  # type: ignore[attr-defined]
    return fmt


class AudioWorker(QObject):
    """Captures audio from default mic, chunks it, and emits signals.

    Must be moved to a QThread — QAudioSource requires an event loop.

    Emits:
        chunk_ready(bytes) — a complete audio chunk for the ASR client.
        rms_amplitude(float) — RMS amplitude of the chunk for waveform.
        device_error(str) — audio device failure.
        recording_started(str) — emitted when recording begins, with wav_path.
        recording_stopped — emitted when recording ends.
        disk_error(str) — disk write failure.
    """

    chunk_ready = Signal(bytes)
    rms_amplitude = Signal(float)
    device_error = Signal(str)
    recording_started = Signal(str)
    recording_stopped = Signal()
    disk_error = Signal(str)

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._source: QAudioSource | None = None
        self._io_device: QIODevice | None = None
        self._chunker: Chunker | None = None
        self._wav_file: wave.Wave_write | None = None
        self._wav_path: str = ""

    def start_recording(self) -> None:
        """Begin audio capture from the default microphone."""
        sample_rate = self._config.sample_rate
        chunk_ms = self._config.chunk_duration_ms
        recordings_dir = self._config.recordings_dir

        # Prepare WAV file path
        date_dir = datetime.now().strftime("%Y-%m-%d")
        wav_dir = os.path.join(recordings_dir, date_dir)
        os.makedirs(wav_dir, exist_ok=True)

        # Use a simple counter-based filename to avoid conflicts;
        # the session id will be associated later.
        import time
        filename = f"{int(time.time() * 1000)}.wav"
        self._wav_path = os.path.join(wav_dir, filename)

        fmt = _make_audio_format(sample_rate)
        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            self.device_error.emit("录音设备异常，请检查麦克风")
            return

        self._source = QAudioSource(device, fmt)
        self._chunker = Chunker(chunk_duration_ms=chunk_ms, sample_rate=sample_rate)

        # Open WAV for incremental writing
        try:
            self._wav_file = wave.open(self._wav_path, "wb")
            self._wav_file.setnchannels(1)
            self._wav_file.setsampwidth(2)
            self._wav_file.setframerate(sample_rate)
        except OSError as e:
            self.disk_error.emit(f"磁盘空间不足，录音无法保存: {e}")
            return

        self._io_device = self._source.start()
        if self._io_device is None:
            self.device_error.emit("录音设备异常，请检查麦克风")
            return

        self._io_device.readyRead.connect(self._on_ready_read)
        logger.info("Recording started")
        self.recording_started.emit(self._wav_path)

    def stop_recording(self) -> None:
        """Stop capture, flush remaining chunks, close WAV file."""
        if self._source is not None:
            self._source.stop()
            self._source = None

        if self._chunker is not None:
            for chunk in self._chunker.flush():
                self._write_wav(chunk)
                rms = self._chunker.compute_rms(chunk)
                self.rms_amplitude.emit(rms)
                self.chunk_ready.emit(chunk)

        if self._wav_file is not None:
            self._wav_file.close()
            self._wav_file = None

        self._io_device = None
        self._chunker = None
        logger.info("Recording stopped")
        self.recording_stopped.emit()

    def _on_ready_read(self) -> None:
        """Read available PCM data, chunk it, write to WAV, emit signals."""
        if self._io_device is None or self._chunker is None:
            return
        raw = self._io_device.readAll()
        data = bytes(raw.data())
        if not data:
            return

        for chunk in self._chunker.feed(data):
            self._write_wav(chunk)
            rms = self._chunker.compute_rms(chunk)
            self.rms_amplitude.emit(rms)
            self.chunk_ready.emit(chunk)

    def _write_wav(self, pcm: bytes) -> None:
        """Write PCM bytes to the open WAV file, emitting disk_error on failure."""
        if self._wav_file is None:
            return
        try:
            self._wav_file.writeframes(pcm)
        except OSError as e:
            self.disk_error.emit(f"磁盘空间不足，录音无法保存: {e}")

    @property
    def wav_path(self) -> str:
        return self._wav_path
