"""Application configuration backed by QSettings per ADR-0001."""

from typing import cast

from PySide6.QtCore import QSettings


_DEFAULTS: dict[str, str | int] = {
    "audio/chunk_duration_ms": 1600,
    "audio/sample_rate": 16000,
    "server/ws_url": "ws://localhost:10095",
    "storage/recordings_dir": "./recordings",
    "storage/log_file": "./logs/app.log",
}


class AppConfig:
    """Typed accessor for QSettings-based application configuration."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings("Prototype", "recording-app")

    def get(self, key: str) -> str | int:
        default: str | int = _DEFAULTS[key]
        return cast(str | int, self._settings.value(key, default, type(default)))

    def set(self, key: str, value: str | int) -> None:
        self._settings.setValue(key, value)

    @property
    def chunk_duration_ms(self) -> int:
        return int(self.get("audio/chunk_duration_ms"))

    @property
    def sample_rate(self) -> int:
        return int(self.get("audio/sample_rate"))

    @property
    def ws_url(self) -> str:
        return str(self.get("server/ws_url"))

    @property
    def recordings_dir(self) -> str:
        return str(self.get("storage/recordings_dir"))

    @property
    def log_file(self) -> str:
        return str(self.get("storage/log_file"))
