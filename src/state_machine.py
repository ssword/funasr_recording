"""Session state machine — five states with defined transitions and signals."""

from enum import Enum, auto

from PySide6.QtCore import QObject, Signal


class SessionState(Enum):
    IDLE = auto()
    CONNECTING = auto()
    RECORDING = auto()
    PROCESSING = auto()
    ERROR = auto()


# Valid transitions: (current_state, trigger) → new_state
_TRANSITIONS: dict[tuple[SessionState, str], SessionState] = {
    (SessionState.IDLE, "click"): SessionState.CONNECTING,
    (SessionState.CONNECTING, "ws_ok"): SessionState.RECORDING,
    (SessionState.CONNECTING, "ws_fail"): SessionState.ERROR,
    (SessionState.RECORDING, "click"): SessionState.PROCESSING,
    (SessionState.RECORDING, "ws_disconnect"): SessionState.ERROR,
    (SessionState.RECORDING, "disk_full"): SessionState.ERROR,
    (SessionState.RECORDING, "device_error"): SessionState.ERROR,
    (SessionState.PROCESSING, "final_result"): SessionState.IDLE,
    (SessionState.PROCESSING, "ws_error"): SessionState.ERROR,
    (SessionState.ERROR, "click"): SessionState.IDLE,
}


_BUTTON_TEXT: dict[SessionState, str] = {
    SessionState.IDLE: "请按按钮开始录音",
    SessionState.CONNECTING: "连接中…",
    SessionState.RECORDING: "请再次按按钮来停止录音",
    SessionState.PROCESSING: "处理中…",
    SessionState.ERROR: "重试",
}


class StateMachine(QObject):
    """Manages session state and emits state_changed(state, trigger) on change."""

    state_changed = Signal(SessionState, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = SessionState.IDLE

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def button_text(self) -> str:
        return _BUTTON_TEXT[self._state]

    def transition(self, trigger: str) -> None:
        """Attempt a state transition. Invalid transitions are silently ignored."""
        key = (self._state, trigger)
        if key in _TRANSITIONS:
            self._state = _TRANSITIONS[key]
            self.state_changed.emit(self._state, trigger)
